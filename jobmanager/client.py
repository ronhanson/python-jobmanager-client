#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
(c) 2015 Ronan Delacroix
Job Manager Client
:author: Ronan Delacroix
"""
import os
import signal
import tbx.log
import tbx.text
import tbx.service
import tbx.settings
from jobmanager.common.job import Job
import pprint
import logging
import sys
import traceback
import mongoengine
from datetime import datetime, timedelta
from multiprocessing import Process
import time


settings = tbx.settings.from_file('client', application_name='jobmanager')
POOL_SIZE = settings.JOBS.AMOUNT


class JobManagerClientService(tbx.service.Service):
    """
    """
    pending_status = 'pending'
    running_status = 'running'
    completed_status = 'success'

    def setup(self):
        super(JobManagerClientService, self).setup()
        self.current_jobs = []
        self.process_number_list = list(range(1, POOL_SIZE+1))

    def destroy(self):
        logging.warning("Destroying service %s" % self.service_name)
        for job in self.current_jobs:
            job.terminate()
            job.join()
        logging.info("Processes terminated.")
        return None

    def find_some_jobs(self):
        """
        Find as much jobs possible from the DB.
        :return:
        """
        amount = self.available_slot
        nb = 0
        jobs = []
        if not amount:
            return jobs

        job_found = Job.objects(status=self.pending_status).order_by('+created').modify(status=self.running_status)
        while job_found:
            nb += 1
            jobs.append(job_found)
            if nb >= amount or nb >= POOL_SIZE: #maximum of POOL_SIZE jobs at once...
                break
            job_found = Job.objects(status=self.pending_status).order_by('+created').modify(status=self.running_status)
        if len(jobs) > 0:
            logging.info("Found %d new jobs in database (%d slot available over %d)." % (len(jobs), self.available_slot, POOL_SIZE))
        return jobs

    @property
    def available_slot(self):
        return POOL_SIZE - len(self.current_jobs)

    def check_current_jobs(self):
        initial_amount = len(self.current_jobs)
        #logging.debug("Checking current job status : there was %d jobs running," % (initial_amount))

        for proc in list(self.current_jobs): #iterate over copy of the list (to be able to remove)
            try:
                #import pdb
                #pdb.set_trace()
                job = proc.job
                job.reload()
                if job.timeout and job.started:
                    if datetime.utcnow() > (job.started + timedelta(seconds=job.timeout)):
                        logging.error("Job %s (pid : %d) Timeout" % (job.uuid, proc.pid))
                        proc.terminate()
                        proc.join()
                        logging.error("Job %s terminated." % job.uuid)

                if not proc.is_alive():
                    proc.join(1)
                    logging.info("Job %s was found finished. Exit code : %d" % (job.uuid, proc.exitcode))
                    if proc.exitcode == 0:
                        proc.callback_success()
                    else:
                        proc.callback_error(proc.exitcode)

                    #check job status and TTL
                    if job.status == 'error' and job.ttl > 1:
                        logging.info("Job %s has TTL of %d, creating a duplicated job to retry it." % (job.uuid, job.ttl))
                        from copy import deepcopy
                        new_job = deepcopy(job)
                        new_job.id = None
                        new_job.uuid = tbx.text.random_short_slug()
                        new_job.ttl = new_job.ttl - 1
                        new_job.status = "pending"
                        new_job.created = datetime.utcnow()
                        new_job.started = None
                        new_job.finished = None
                        new_job.details = "Job retried! New job created from job %s" % job.uuid
                        new_job.history = []
                        new_job.save()
                        logging.info("New job %s created... Set to be retried!" % (new_job.uuid))
                        logging.info("Now sleeping a bit to let other job manager have a chance to get that new job...")
                        time.sleep(4.5)

                    if proc in self.current_jobs:
                        self.current_jobs.remove(proc)
                    self.process_number_list.append(proc.process_number)
            except AssertionError:
                continue
        if initial_amount != len(self.current_jobs):
            logging.info("Cleaning current job list: there was %d jobs running, now %d are running." % (initial_amount, len(self.current_jobs)))

    def run(self):
        """
        Run method (launched every few seconds)
        """
        #logging.debug("Run %s with %d processes, %d busy (debug:%s)" % (self.service_name, POOL_SIZE, len(self.current_jobs), self.debug))

        #clean current jobs
        self.check_current_jobs()

        #find new jobs
        jobs = self.find_some_jobs()

        #process found jobs
        for job in jobs:
            self.process_job(job)

        return

    def process_job(self, job):
        """
        Method used to launch a job in a separate process
        """
        logging.info('Found one job with status %s. Launching processing...' % job.status)

        process_number = self.process_number_list.pop(0)

        proc = None

        def check_job_success():
            try:
                self.current_jobs.remove(proc)
                self.process_number_list.append(process_number)
            except:
                pass
            job.reload()
            logging.debug("Job %s success callback : %s" % (job.uuid, job.status))
            if job.status not in ['success', 'error']:
                job.save_as_successful()

        def check_job_error(exitcode):
            try:
                self.current_jobs.remove(proc)
                self.process_number_list.append(process_number)
            except:
                pass
            logging.error("Job %s ERROR callback" % (job.uuid))
            job.reload()
            if job.status != 'error':
                job.details = "Error (callback) : exitcode=%s" % str(exitcode)
                job.save_as_error(text="Error - exitcode=%s" % str(exitcode))

        proc = Process(
            name="Process-%02d-%s" % (process_number, job.uuid),
            target=launch_job,
            args=(job, process_number,)
        )
        proc.start()
        proc.job = job
        proc.process_number = process_number
        proc.callback_success = check_job_success
        proc.callback_error = check_job_error

        self.current_jobs.append(proc)
        return


def launch_job(job, process_number):
    """
    Connect to database prior to launch the func method.
    Useful as new processes don't have active connections...
    :param func:
    :return:
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    tbx.log.configure_logging("jobmanager-client-%02d" % process_number, application_name='jobmanager', settings=settings.LOG, force=True)

    mongoengine.connect(host=settings.DATABASE.HOST, port=settings.DATABASE.PORT, db=settings.DATABASE.NAME)
    try:
        job.run()
        exit(0)
    except Exception as e:
        logging.error("Error while running job %s" % job.uuid)
        logging.exception(e)
        exit(1)

