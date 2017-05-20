#!/usr/bin/env python

# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A script to parse apache error logs

The script gets the contents of the log file through stdin, and emits a counter
metric for the beginning of each error message it recognizes.
"""
from __future__ import print_function

import argparse
import re
import sys

import common

from chromite.lib import metrics
from chromite.lib import ts_mon_config

from autotest_lib.site_utils.stats import log_daemon_common


LOOP_INTERVAL = 60
ERROR_LOG_METRIC = '/chromeos/autotest/apache/error_log'
ERROR_LOG_LINE_METRIC = '/chromeos/autotest/apache/error_log_line'
ERROR_LOG_MATCHER = re.compile(
    r'^\[[^]]+\] ' # The timestamp. We don't need this.
    r'\[:(?P<log_level>\S+)\] '
    r'\[pid \d+[^]]+\] ' # The PID, possibly followed by a task id.
    # There may be other sections, such as [remote <ip>]
    r'(?P<sections>\[[^]]+\] )*'
    r'\S' # first character after pid must be non-space; otherwise it is
          # indented, meaning it is just a continuation of a previous message.
    r'(?P<mod_wsgi>od_wsgi)?' # Note: the 'm' of mod_wsgi was already matched.
)


def EmitErrorLogMetric(m):
  """Emits a Counter metric for error log messages.

  @param m: A regex match object
  """
  log_level = m.group('log_level') or ''
  # It might be interesting to see whether the error/warning was emitted
  # from python at the mod_wsgi process or not.
  mod_wsgi_present = bool(m.group('mod_wsgi'))

  metrics.Counter(ERROR_LOG_METRIC).increment(fields={
      'log_level': log_level,
      'mod_wsgi': mod_wsgi_present})


def EmitErrorLogLineMetric(_m):
  """Emits a Counter metric for each error log line.

  @param _m: A regex match object.
  """
  metrics.Counter(ERROR_LOG_LINE_METRIC).increment()


MATCHERS = [
    (ERROR_LOG_MATCHER, EmitErrorLogMetric),
    (re.compile(r'.*'), EmitErrorLogLineMetric),
]


def ParseArgs():
    """Parses the command line arguments."""
    p = argparse.ArgumentParser(
        description='Parses apache logs and emits metrics to Monarch')
    p.add_argument('--output-logfile')
    p.add_argument('--debug-metrics-file',
                   help='Output metrics to the given file instead of sending '
                   'them to production.')
    return p.parse_args()


def Main():
    """Sets up logging and runs matchers against stdin"""
    args = ParseArgs()
    log_daemon_common.SetupLogging(args)

    # Set up metrics sending and go.
    ts_mon_args = {}
    if args.debug_metrics_file:
        ts_mon_args['debug_file'] = args.debug_metrics_file

    with ts_mon_config.SetupTsMonGlobalState('apache_error_log_metrics',
                                             **ts_mon_args):
      log_daemon_common.RunMatchers(sys.stdin, MATCHERS)
      metrics.Flush()


if __name__ == '__main__':
    Main()
