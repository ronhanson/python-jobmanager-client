#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
(c) 2015 Ronan Delacroix
Job Manager Client
:author: Ronan Delacroix
"""
import os
import pip
import signal
import tbx
import tbx.log
import tbx.text
import tbx.process
import tbx.service
import tbx.settings
from jobmanager.common.job import Job, Client, ClientStatus
import socket
import psutil
import platform
import pprint
import logging
import sys
import atexit
import traceback
from threading import Event, Thread
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

        self.client = Client()
        self.client.hostname = socket.gethostname()
        self.client.pid = os.getpid()
        self.client.pool_size = POOL_SIZE
        self.client.job_types = [k.__name__ for k in tbx.code.get_subclasses(Job)]
        self.client.platform = tbx.code.safe_dict(platform.uname)
        self.client.boot_time = datetime.fromtimestamp(psutil.boot_time())
        self.client.python_version = sys.version.split(' ')[0]
        self.client.python_packages = sorted(["%s==%s" % (i.key, i.version) for i in pip.get_installed_distributions()])

        self.client.save()

        self.client_status_index = 0

        self.update_client_status()

        client_status_update_timing = settings.CLIENT.CLIENT_STATUS_UPDATE_TIMING or 10

        self.status_update_thread, self.status_update_stopper,  = tbx.process.call_repeatedly(self.update_client_status, client_status_update_timing)

        self.log_info("Service setup complete.")

    def update_client_status(self):
        self.client.save()

        partitions = []
        try:
            for f in psutil.disk_partitions():
                usage = psutil.disk_usage(path=f.mountpoint)
                p = {
                    'type': f.fstype,
                    'device': f.device,
                    'mountpoint': f.mountpoint,
                    'total': usage.total,
                    'used': usage.used,
                    'percent': usage.percent,
                }
                partitions.append(p)
        except Exception as e:
            pass

        self_process = psutil.Process(os.getpid())
        processes = [{'ppid': self_process.ppid(), 'pid': self_process.pid, 'cmd': ' '.join(self_process.cmdline())}]
        for c in self_process.children():
            try:
                processes.append({'ppid': c.ppid(), 'pid': c.pid, 'cmd': ' '.join(c.cmdline())})
            except psutil.Error:
                pass

        self.client_status_index += 1

        status = ClientStatus()
        status.index = self.client_status_index
        status.client = self.client
        status.current_jobs = [proc.job for proc in self.current_jobs]

        virtual_memory = psutil.virtual_memory()
        swap_memory = psutil.swap_memory()

        status.system_status = {
            'processes': processes,
            'cpu': {
                'percent': psutil.cpu_percent(),
                'percents': psutil.cpu_percent(percpu=True)
            },
            'memory': {
                'virtual': {
                    'total': virtual_memory.total,
                    'used': virtual_memory.used,
                    'percent': virtual_memory.percent,
                },
                'swap': {
                    'total': swap_memory.total,
                    'used': swap_memory.used,
                    'percent': swap_memory.percent,
                },
            },
            'disk': partitions,
            #'disk_io': safe_dict(psutil.disk_io_counters, perdisk=False)
        }
        status.save()

    def destroy(self):
        self.log_warning("Destroying service %s" % self.service_name)
        #self.status_update_stopper()
        for proc in self.current_jobs:
            proc.terminate()
            proc.join()
        self.log_info("Processes terminated.")
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

        job_found = Job.objects(status=self.pending_status).order_by('+created').modify(status=self.running_status, client_hostname=self.client.hostname, client_uuid=self.client.uuid)
        while job_found:
            nb += 1
            jobs.append(job_found)
            if nb >= amount or nb >= POOL_SIZE: #maximum of POOL_SIZE jobs at once...
                break
            job_found = Job.objects(status=self.pending_status).order_by('+created').modify(status=self.running_status, client_hostname=self.client.hostname, client_uuid=self.client.uuid)
        if len(jobs) > 0:
            self.log_info("Found %d new jobs in database (%d slot available over %d)." % (len(jobs), self.available_slot, POOL_SIZE))
        return jobs

    @property
    def available_slot(self):
        return POOL_SIZE - len(self.current_jobs)

    def check_current_jobs(self):
        initial_amount = len(self.current_jobs)
        #logging.debug("Checking current job status : there was %d jobs running," % (initial_amount), extra=self.extra_log_arguments)

        for proc in list(self.current_jobs): #iterate over copy of the list (to be able to remove)
            try:
                #import pdb
                #pdb.set_trace()
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

                    if proc in self.current_jobs:
                        self.current_jobs.remove(proc)
                    self.process_number_list.append(proc.process_number)
            except AssertionError:
                continue
        if initial_amount != len(self.current_jobs):
            self.log_info("Cleaning current job list: there was %d jobs running, now %d are running." % (initial_amount, len(self.current_jobs)))

    def run(self):
        """
        Run method (launched every few seconds)
        """
        #self.log_debug("Run %s with %d processes, %d busy (debug:%s)" % (self.service_name, POOL_SIZE, len(self.current_jobs), self.debug))

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
        self.log_info('Found one job with status %s. Launching processing...' % job.status)

        process_number = self.process_number_list.pop(0)

        proc = None

        def check_job_success():
            try:
                self.current_jobs.remove(proc)
                self.process_number_list.append(process_number)
            except:
                pass
            job.reload()
            self.log_debug("Job %s success callback : %s" % (job.uuid, job.status))
            if job.status not in ['success', 'error']:
                job.save_as_successful()

        def check_job_error(exitcode):
            try:
                self.current_jobs.remove(proc)
                self.process_number_list.append(process_number)
            except:
                pass

            self.log_error("Job %s ERROR callback" % (job.uuid))
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

    @property
    def extra_log_arguments(self):
        return {
            'client_hostname': self.client.hostname,
            'client_uuid': self.client.uuid,
        }

    def log_debug(self, text):
        logging.debug("%s - %s" % (self, text), extra=self.extra_log_arguments)

    def log_info(self, text):
        logging.info("%s - %s" % (self, text), extra=self.extra_log_arguments)

    def log_warning(self, text):
        logging.warning("%s - %s" % (self, text), extra=self.extra_log_arguments)

    def log_error(self, text):
        logging.error("%s - %s" % (self, text), extra=self.extra_log_arguments)

    def log_exception(self, text):
        logging.exception("%s - %s" % (self, text), extra=self.extra_log_arguments)

    def __str__(self):
        return "JobManagerClient %s @ %s" % (self.client.uuid, self.client.hostname)

    def __repr__(self):
        return self.__str__()


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
    except Exception:
        logging.exception("Error while running job %s" % job.uuid, extra={'job_uuid': job.uuid, 'client_uuid': job.client_uuid, 'client_hostname': socket.gethostname()})
        exit(1)

