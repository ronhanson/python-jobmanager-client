#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
(c) 2015 Ronan Delacroix
Job Manager Client
:author: Ronan Delacroix
"""
import tbx.service
from jobmanager.common.job import Job
import pprint
import logging
import sys
import traceback
import mongoengine

settings = tbx.settings.from_file('client', application_name='jobmanager')


from multiprocessing import Pool
POOL_SIZE = settings.JOBS.AMOUNT


class JobManagerClientService(tbx.service.Service):
    """
    """
    pending_status = 'pending'
    running_status = 'running'
    completed_status = 'success'

    def setup(self):
        super(JobManagerClientService, self).setup()
        self.process_pool = Pool(processes=POOL_SIZE, maxtasksperchild=1)

    def destroy(self):
        logging.warning("Destroying service %s" % self.service_name)
        self.process_pool.terminate()
        self.process_pool.join()
        logging.info("Process pool terminated.")
        return None

    def find_some_jobs(self):
        """
        Find as much jobs possible from the DB.
        :return:
        """
        nb = 0
        jobs = []
        job_found = Job.objects(status=self.pending_status).modify(status=self.running_status)
        while job_found:
            nb += 1
            jobs.append(job_found)
            if nb >= self.process_pool._processes: #maximum of POOL_SIZE jobs at once...
                break
            job_found = Job.objects(status=self.pending_status).modify(status=self.running_status)
        return jobs

    def run(self):
        logging.info("Run %s with %s processes (debug:%s)" % (self.service_name, self.process_pool._processes, self.debug))

        jobs = self.find_some_jobs()

        for job in jobs:
            self.process_job(job)

        return

    def process_job(self, job):
        logging.info('Found one job with status %s. Launching processing...' % job.status)

        def check_job_success(err):
            job.reload()
            logging.debug("Job success callback : %s" % job.status)
            logging.debug(err)
            if job.status not in ['success', 'error']:
                job.save_as_successful()

        def check_job_error(err):
            logging.error("Job ERROR callback")
            logging.exception(err)
            job.reload()
            if job.status != 'error':
                job.details = "Exception : %s" % (str(err))
                job.save_as_error(text=str(err))

        self.process_pool.apply_async(connect_and_launch, args=(job.run,), callback=check_job_success, error_callback=check_job_error)
        return


def connect_and_launch(func):
    """
    Connect to database prior to launch the func method.
    Useful as new processes don't have active connections...
    :param func:
    :return:
    """
    mongoengine.connect(host=settings.DATABASE.HOST, port=settings.DATABASE.PORT, db=settings.DATABASE.NAME)
    func()