# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging, time
from autotest_lib.client.common_lib import base_job, log


TIME_FMT = '%Y-%m-%d %H:%M:%S'
DEFAULT_POLL_INTERVAL_SECONDS = 10


def gather_job_hostnames(afe, job):
    """
    Collate and return names of hosts used in |job|.

    @param afe: an instance of AFE as defined in server/frontend.py.
    @param job: the job to poll on.
    @return iterable of hostnames on which |job| was run, using None as
            placeholders.
    """
    hosts = []
    for e in afe.run('get_host_queue_entries', job=job.id):
        if not e['host']:
            logging.warn('Job %s (%s) has an entry with no host!',
                         job.name, job.id)
            hosts.append(None)
        else:
            hosts.append(e['host']['hostname'])
    return hosts


def wait_for_jobs_to_start(afe, jobs, interval=DEFAULT_POLL_INTERVAL_SECONDS):
    """
    Wait for the job specified by |job.id| to start.

    @param afe: an instance of AFE as defined in server/frontend.py.
    @param jobs: the jobs to poll on.
    """
    job_ids = [j.id for j in jobs]
    while job_ids:
        for job_id in list(job_ids):
            if len(afe.get_jobs(id=job_id, not_yet_run=True)) > 0:
                continue
            job_ids.remove(job_id)
            logging.debug('Re-imaging job %d running.', job_id)
        if job_ids:
            time.sleep(interval)


def wait_for_jobs_to_finish(afe, jobs, interval=DEFAULT_POLL_INTERVAL_SECONDS):
    """
    Wait for the jobs specified by each |job.id| to finish.

    @param afe: an instance of AFE as defined in server/frontend.py.
    @param jobs: the jobs to poll on.
    """
    job_ids = [j.id for j in jobs]
    while job_ids:
        for job_id in list(job_ids):
            if not afe.get_jobs(id=job_id, finished=True):
                continue
            job_ids.remove(job_id)
            logging.debug('Re-imaging job %d finished.', job_id)
        if job_ids:
            time.sleep(interval)


def wait_for_and_lock_job_hosts(afe, jobs, manager,
                                interval=DEFAULT_POLL_INTERVAL_SECONDS):
    """
    Poll until devices have begun reimaging, locking them as we go.

    Gather the hosts chosen for |job| -- which must be in the Running
    state itself -- and as they each individually come online and begin
    Running, lock them.  Poll until all chosen hosts have gone to Running
    and been locked using |manager|.

    @param afe: an instance of AFE as defined in server/frontend.py.
    @param jobs: an iterable of Running frontend.Jobs
    @param manager: a HostLockManager instance.  Hosts will be added to it
                    as they start Running, and it will be used to lock them.
    @return iterable of the hosts that were locked.
    """
    def get_all_hosts(my_jobs):
        all_hosts = []
        for job in my_jobs:
            all_hosts.extend(gather_job_hostnames(afe, job))
        return all_hosts

    locked_hosts = set()
    expected_hosts = get_all_hosts(jobs)

    while sorted(list(locked_hosts)) != sorted(expected_hosts):
        hosts_to_check = [e for e in expected_hosts if e]
        if hosts_to_check:
            running_hosts = afe.get_hosts(hosts_to_check, status='Running')
            hostnames = [h.hostname for h in running_hosts]
            logging.debug('Discovered %r hosts in Running state.', hostnames)
            if set(hostnames) - locked_hosts != set():
                # New hosts to lock!
                manager.add(hostnames)
                manager.lock()
            locked_hosts = locked_hosts.union(hostnames)
        time.sleep(interval)
        expected_hosts = get_all_hosts(jobs)

    return locked_hosts


def _collate_aborted(current_value, entry):
    """
    reduce() over a list of HostQueueEntries for a job; True if any aborted.

    Functor that can be reduced()ed over a list of
    HostQueueEntries for a job.  If any were aborted
    (|entry.aborted| exists and is True), then the reduce() will
    return True.

    Ex:
      entries = AFE.run('get_host_queue_entries', job=job.id)
      reduce(_collate_aborted, entries, False)

    @param current_value: the current accumulator (a boolean).
    @param entry: the current entry under consideration.
    @return the value of |entry.aborted| if it exists, False if not.
    """
    return current_value or ('aborted' in entry and entry['aborted'])


def _status_is_relevant(status):
    """
    Indicates whether the status of a given test is meaningful or not.

    @param status: frontend.TestStatus object to look at.
    @return True if this is a test result worth looking at further.
    """
    return not (status.test_name.startswith('SERVER_JOB') or
                status.test_name.startswith('CLIENT_JOB'))


def wait_for_results(afe, tko, jobs):
    """
    Wait for results of all tests in all jobs in |jobs|.

    Currently polls for results every 5s.  Yields one Status object per test
    as results become available.

    @param afe: an instance of AFE as defined in server/frontend.py.
    @param tko: an instance of TKO as defined in server/frontend.py.
    @param jobs: a list of Job objects, as defined in server/frontend.py.
    @return a list of Statuses, one per test.
    """
    while jobs:
        for job in list(jobs):
            if not afe.get_jobs(id=job.id, finished=True):
                continue

            jobs.remove(job)

            entries = afe.run('get_host_queue_entries', job=job.id)
            if reduce(_collate_aborted, entries, False):
                yield Status('ABORT', job.name)
            else:
                statuses = tko.get_status_counts(job=job.id)
                for s in filter(_status_is_relevant, statuses):
                    yield Status(s.status, s.test_name, s.reason,
                                 s.test_started_time,
                                 s.test_finished_time)
        time.sleep(5)


def gather_per_host_results(afe, tko, jobs, name_prefix=''):
    """
    Gather currently-available results for all |jobs|, aggregated per-host.

    For each job in |jobs|, gather per-host results and summarize into a single
    log entry.  For example, a FAILed SERVER_JOB and successful actual test
    is reported as a FAIL.

    @param afe: an instance of AFE as defined in server/frontend.py.
    @param tko: an instance of TKO as defined in server/frontend.py.
    @param jobs: a list of Job objects, as defined in server/frontend.py.
    @param name_prefix: optional string to prepend to Status object names.
    @return a list of Statuses, one per host used in a Job.
    """
    to_return = {}
    for job in jobs:
        for s in tko.get_status_counts(job=job.id):
            candidate = Status(s.status,
                               name_prefix+s.hostname,
                               s.reason,
                               s.test_started_time,
                               s.test_finished_time)
            if (s.hostname not in to_return or
                candidate.is_worse_than(to_return[s.hostname])):
                to_return[s.hostname] = candidate

        # If we didn't find more specific data above for a host, fill in here.
        # For jobs that didn't even make it to finding a host, just collapse
        # into a single log entry.
        for e in afe.run('get_host_queue_entries', job=job.id):
            host = e['host']['hostname'] if e['host'] else 'hostless' + job.name
            if host not in to_return:
                to_return[host] = Status(Status.STATUS_MAP[e['status']],
                                         job.name,
                                         'Did not run',
                                         begin_time_str=job.created_on)

    return to_return


def record_and_report_results(statuses, record_entry):
    """
    Record all Statuses in |statuses| and return True if all were GOOD.

    @param statuses: iterable of Status objects.
    @param record_entry: a callable to use for logging.
               prototype:
                   record_entry(base_job.status_log_entry)
    @return True if all Statuses are good.
    """
    all_good = True
    for status in statuses:
        status.record_all(record_entry)
        all_good = all_good and status.is_good()
    return all_good


class Status(object):
    """
    A class representing a test result.

    Stores all pertinent info about a test result and, given a callable
    to use, can record start, result, and end info appropriately.

    @var _status: status code, e.g. 'INFO', 'FAIL', etc.
    @var _test_name: the name of the test whose result this is.
    @var _reason: message explaining failure, if any.
    @var _begin_timestamp: when test started (int, in seconds since the epoch).
    @var _end_timestamp: when test finished (int, in seconds since the epoch).

    @var STATUS_MAP: a dict mapping host queue entry status strings to canonical
                     status codes; e.g. 'Aborted' -> 'ABORT'
    """
    _status = None
    _test_name = None
    _reason = None
    _begin_timestamp = None
    _end_timestamp = None

    STATUS_MAP = {'Failed': 'FAIL', 'Aborted': 'ABORT', 'Completed': 'GOOD'}

    class sle(base_job.status_log_entry):
        """
        Thin wrapper around status_log_entry that supports stringification.
        """
        def __str__(self):
            return self.render()

        def __repr__(self):
            return self.render()


    def __init__(self, status, test_name, reason='', begin_time_str=None,
                 end_time_str=None):
        """
        Constructor

        @param status: status code, e.g. 'INFO', 'FAIL', etc.
        @param test_name: the name of the test whose result this is.
        @param reason: message explaining failure, if any; Optional.
        @param begin_time_str: when test started (in TIME_FMT); now() if None.
        @param end_time_str: when test finished (in TIME_FMT); now() if None.
        """

        self._status = status
        self._test_name = test_name
        self._reason = reason
        if begin_time_str:
            self._begin_timestamp = int(time.mktime(
                datetime.datetime.strptime(
                    begin_time_str, TIME_FMT).timetuple()))
        else:
            self._begin_timestamp = int(time.time())

        if end_time_str:
            self._end_timestamp = int(time.mktime(
                datetime.datetime.strptime(
                    end_time_str, TIME_FMT).timetuple()))
        else:
            self._end_timestamp = int(time.time())


    def is_good(self):
        return self._status == 'GOOD'


    def is_worse_than(self, candidate):
        """
        Return whether |self| represents a "worse" failure than |candidate|.

        "Worse" is defined the same as it is for log message purposes in
        common_lib/log.py.  We also consider status with a specific error
        message to represent a "worse" failure than one without.

        @param candidate: a Status instance to compare to this one.
        @return True if |self| is "worse" than |candidate|.
        """
        if self._status != candidate._status:
            return (log.job_statuses.index(self._status) <
                    log.job_statuses.index(candidate._status))
        # else, if the statuses are the same...
        if self._reason and not candidate._reason:
            return True
        return False


    def record_start(self, record_entry):
        """
        Use record_entry to log message about start of test.

        @param record_entry: a callable to use for logging.
               prototype:
                   record_entry(base_job.status_log_entry)
        """
        record_entry(Status.sle('START', None, self._test_name, '',
                                None, self._begin_timestamp))


    def record_result(self, record_entry):
        """
        Use record_entry to log message about result of test.

        @param record_entry: a callable to use for logging.
               prototype:
                   record_entry(base_job.status_log_entry)
        """
        record_entry(Status.sle(self._status, None, self._test_name,
                                self._reason, None, self._end_timestamp))


    def record_end(self, record_entry):
        """
        Use record_entry to log message about end of test.

        @param record_entry: a callable to use for logging.
               prototype:
                   record_entry(base_job.status_log_entry)
        """
        record_entry(Status.sle('END %s' % self._status, None, self._test_name,
                                '', None, self._end_timestamp))


    def record_all(self, record_entry):
        """
        Use record_entry to log all messages about test results.

        @param record_entry: a callable to use for logging.
               prototype:
                   record_entry(base_job.status_log_entry)
        """
        self.record_start(record_entry)
        self.record_result(record_entry)
        self.record_end(record_entry)
