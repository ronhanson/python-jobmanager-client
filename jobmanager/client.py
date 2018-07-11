#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
(c) 2014-2018 Ronan Delacroix
Job Manager Client
:author: Ronan Delacroix
"""
import os
import signal
import tbx
import tbx.log
import tbx.text
import tbx.process
import tbx.service
import tbx.settings
from jobmanager.common.job import Job
from jobmanager.common.host import Host
import socket
import platform
import logging
import sys
import atexit
import traceback
import mongoengine
from datetime import datetime, timedelta
from multiprocessing import Process
import time
import jobmanager.common as common


class JobManagerClientService(tbx.service.Service, common.LogProxy):
    """
    Job Manager Client Service
    """

    @property
    def name(self):
        if not hasattr(self, "_hostname"):
            self._hostname = socket.gethostname()
        return "JobManagerClient @ %s" % (self._hostname)

    def setup(self, db_host, db_port, db_name, imports, slots, log_file=None, update_timing=10):
        super(JobManagerClientService, self).setup()

        self.log_file = log_file

        mongoengine.connect(host=db_host, port=db_port, db=db_name)
        self.log_info("Connected to database %s@%s:%d" % (db_name, db_host, db_port))

        self.current_job_processes = []

        self.host = Host.localhost()
        self.host.client_service = self

        self.host.do_import(imports)
        self.host.update_slots(slots)
        self.host.check_capacity()
        self.host.update_status()

        max_processes_amount = sum(self.host.job_slots.values())
        self.process_number_list = list(range(1, max_processes_amount+1))

        status_update_thread, self.status_update_stopper,  = tbx.process.call_repeatedly(self.host.update_status, update_timing)

        self.log_info("Service setup complete.")

    @property
    def current_jobs(self):
        return [proc.job for proc in self.current_job_processes]

    @property
    def current_job_slots(self):
        current_job_types = [job.type for job in self.current_jobs]
        return {t: current_job_types.count(t) for t in current_job_types}

    @property
    def available_job_slots(self):
        return {
            key: self.host.job_slots[key] - self.current_job_slots.get(key, 0)
            for key in self.host.job_slots.keys() if self.host.job_slots[key]
        }

    def destroy(self):
        self.log_warning("Destroying service %s" % self.service_name)
        self.status_update_stopper()
        for proc in self.current_job_processes:
            proc.terminate()
            proc.join()
        self.log_info("Processes terminated.")
        return None

    def find_some_jobs(self):
        """
        Find as much jobs possible from the DB.
        :return:
        """
        max_amounts = self.available_job_slots
        nb = 0
        jobs = []
        if not sum(max_amounts.values()):
            return jobs

        old_subclasses = Job._subclasses
        try:
            def find_one_job():
                revamped_job_slots = ["Job.%s" % c for c in max_amounts.keys() if max_amounts[c] > 0]
                Job._subclasses = revamped_job_slots

                return Job.objects(status='pending').order_by('+created').modify(
                                status='running',
                                hostname=self.host.hostname)

            job_found = find_one_job()
            while job_found:
                max_amounts[job_found.type] = max_amounts[job_found.type] - 1
                nb += 1
                jobs.append(job_found)
                if not sum(max_amounts.values()):
                    break

                job_found = find_one_job()

            if len(jobs) > 0:
                found_types = [j.type for j in jobs]
                found_counts = {t: found_types.count(t) for t in found_types}
                found_summary = ", ".join(["%s (X%d)" % (k, v) for k, v in found_counts.items()])
                self.log_info("Found %d new jobs in database : %s" % (len(jobs), found_summary))

        except:
            self.log_exception("Error while fetching new jobs!")
            return []
        finally:
            Job._subclasses = old_subclasses  # reset

        return jobs

    def check_current_jobs(self):
        initial_amount = len(self.current_job_processes)

        for proc in list(self.current_job_processes): #iterate over copy of the list (to be able to remove)
            try:
                job = proc.job
                job.reload()
                if job.timeout and job.started:
                    if datetime.utcnow() > (job.started + timedelta(seconds=job.timeout)):
                        self.log_error("Job %s (pid : %d) Timeout" % (job.uuid, proc.pid))
                        proc.terminate()
                        proc.join()
                        self.log_error("Job %s terminated." % job.uuid)

                if not proc.is_alive():
                    proc.join(1)
                    self.log_info("Job %s was found finished. Exit code : %d" % (job.uuid, proc.exitcode))
                    if proc.exitcode == 0:
                        proc.callback_success()
                    else:
                        proc.callback_error(proc.exitcode)

                    #check job status and TTL
                    if job.status == 'error' and job.ttl > 1:
                        self.log_info("Job %s has TTL of %d, creating a duplicated job to retry it." % (job.uuid, job.ttl))
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
                        self.log_info("New job %s created... Set to be retried!" % (new_job.uuid))
                        self.log_info("Now sleeping a bit to let other job manager have a chance to get that new job...")
                        time.sleep(self.loop_duration*1.05)

                    if proc in self.current_job_processes:
                        self.current_job_processes.remove(proc)
                    self.process_number_list.append(proc.process_number)
            except AssertionError:
                continue
        if initial_amount != len(self.current_job_processes):
            self.log_info("Cleaning current job list: there was %d jobs running, now %d are running." % (initial_amount, len(self.current_job_processes)))

    def run(self):
        """
        Run method (launched every few seconds)
        """

        # Clean current jobs
        self.check_current_jobs()

        # Find new jobs
        jobs = self.find_some_jobs()

        # Process found jobs
        for job in jobs:
            self.process_job(job)

        # Sleeps a tiny bit to shift if I managed to get a job.
        # That avoids job managers to be in sync when they query the database.
        if len(jobs):
            time.sleep(self.loop_duration*len(jobs)/10)

        return

    def process_job(self, job):
        """
        Method used to launch a job in a separate process
        """
        self.log_info('Found one %s job. Launching processing...' % job.status)

        process_number = self.process_number_list.pop(0)

        proc = None

        def check_job_success():
            try:
                self.current_job_processes.remove(proc)
                self.process_number_list.append(process_number)
            except:
                pass
            job.reload()
            self.log_debug("Job %s success callback : %s" % (job.uuid, job.status))
            if job.status not in ['success', 'error']:
                job.status = "success"
                job.status_text = "Job Successful"
                job.completion = 100
                job.save()
                #job.save_as_successful()

        def check_job_error(exitcode):
            try:
                self.current_job_processes.remove(proc)
                self.process_number_list.append(process_number)
            except:
                pass
            job.reload()
            self.log_error("Job %s ERROR callback" % (job.uuid))
            if job.status != 'error':
                job.details = "Error (callback) : exitcode=%s" % str(exitcode)
                job.status = "error"
                job.status_text = "Error - exitcode=%s" % str(exitcode)
                job.save()

        # Detach non-serializable thread/lock arguments
        status_update_stopper = self.status_update_stopper
        self.status_update_stopper = None

        # Start process
        proc = Process(
            name="Process-%02d-%s" % (process_number, job.uuid),
            target=launch_job,
            args=(job, process_number, self)
        )
        proc.start()

        # Reattach non-serializable thread/lock arguments
        self.status_update_stopper = status_update_stopper

        proc.job = job
        proc.process_number = process_number
        proc.callback_success = check_job_success
        proc.callback_error = check_job_error

        self.current_job_processes.append(proc)
        return


def launch_job(job, process_number, client_service):
    """
    Connect to database prior to launch the func method.
    Useful as new processes don't have active connections...
    :param func:
    :return:
    """
    if platform.system() != 'Windows':
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGUSR1, signal.SIG_IGN)
        signal.signal(signal.SIGUSR2, signal.SIG_IGN)

    if client_service.log_file:
        (root, ext) = os.path.splitext(client_service.log_file)
        process_log_file = root + ".process-%02d" % process_number + ext
        logger = logging.getLogger()
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                logger.removeHandler(handler)
        tbx.log.add_logging_file_handler(logging.getLogger(), process_log_file)

    mongoengine.connect(host=client_service.db_host, port=client_service.db_port, db=client_service.db_name)
    try:
        job.reload()  # reload job otherwise weak referenced object in it won't exist after forking processes
        job.run()
        exit(0)
    except Exception:
        logging.exception("Error while running job %s" % job.uuid, extra={'job_uuid': job.uuid, 'hostname': job.hostname})
        exit(1)

