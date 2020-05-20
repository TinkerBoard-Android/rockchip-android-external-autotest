# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import re

from autotest_lib.client.bin import utils

_KERNEL_A = {'name': 'KERN-A', 'kernel': 2, 'root': 3}
_KERNEL_B = {'name': 'KERN-B', 'kernel': 4, 'root': 5}

# Time to wait for new kernel to be marked successful after auto update.
_KERNEL_UPDATE_TIMEOUT = 120


def _cgpt(host, flag, kernel):
    """
    Helper function to return numeric cgpt value.

    @param host: The DUT to execute the command on.
    @param flag: Additional flag to pass to cgpt
    @param kernel: The kernel we want to interact with.

    """
    return int(host.run(['cgpt', 'show', '-n', '-i', str(kernel['kernel']),
                         flag, '$(rootdev -s -d)']).stdout.strip())

def get_kernel_state(host):
    """
    Returns the (<active>, <inactive>) kernel state as a pair.

    @param host: The DUT to execute the command on.

    """
    rootdev = host.run(['rootdev','-s']).stdout.strip()
    active_root = int(re.findall('\d+\Z', rootdev)[0])
    if active_root == _KERNEL_A['root']:
        return _KERNEL_A, _KERNEL_B
    elif active_root == _KERNEL_B['root']:
        return _KERNEL_B, _KERNEL_A
    else:
        raise Exception('Encountered unknown root partition: %s' % active_root)

def get_next_kernel(host):
    """
    Return the kernel that has priority for the next boot.

    @param host: The DUT to execute the command on.

    """
    priority_a = _cgpt(host, '-P', _KERNEL_A)
    priority_b = _cgpt(host, '-P', _KERNEL_B)
    return _KERNEL_A if priority_a > priority_b else _KERNEL_B

def get_kernel_success(host, kernel):
    """
    Return boolean success flag for the specified kernel.

    @param host: The DUT to execute the command on.
    @param kernel: Information of the given kernel, either _KERNEL_A
                   or _KERNEL_B.

    """
    return _cgpt(host, '-S', kernel) != 0

def get_kernel_tries(host, kernel):
    """Return tries count for the specified kernel.

    @param host: The DUT to execute the command on.
    @param kernel: Information of the given kernel, either _KERNEL_A
                   or _KERNEL_B.

    """
    return _cgpt(host, '-T', kernel)

def verify_kernel_state_after_update(host):
    """
    Ensure the next kernel to boot is the currently inactive kernel.

    This is useful for checking after completing an update.

    @param host: The DUT to execute the command on.
    @returns the inactive kernel.

    """
    inactive_kernel = get_kernel_state(host)[1]
    next_kernel = get_next_kernel(host)
    if next_kernel != inactive_kernel:
        raise Exception('The kernel for next boot is %s, but %s was expected.'
                        % (next_kernel['name'], inactive_kernel['name']))
    return inactive_kernel

def verify_boot_expectations(host, expected_kernel, error_message):
    """Verifies that we fully booted into the expected kernel state.

    This method both verifies that we booted using the correct kernel
    state and that the OS has marked the kernel as good.

    @param expected_kernel: kernel that we are verifying with,
                            eg I expect to be booted onto partition 4.
    @param error_message: string include in except message text
                          if we booted with the wrong partition.

    """
    # Figure out the newly active kernel.
    active_kernel = get_kernel_state(host)[0]

    if active_kernel != expected_kernel:
        # Kernel crash reports should be wiped between test runs, but
        # may persist from earlier parts of the test, or from problems
        # with provisioning.
        #
        # Kernel crash reports will NOT be present if the crash happened
        # before encrypted stateful is mounted.
        kernel_crashes = glob.glob('/var/spool/crash/kernel.*.kcrash')
        if kernel_crashes:
            error_message += ': kernel_crash'
            logging.debug('Found %d kernel crash reports:',
                          len(kernel_crashes))
            # The crash names contain timestamps that may be useful:
            #   kernel.20131207.005945.0.kcrash
            for crash in kernel_crashes:
                logging.debug('  %s', os.path.basename(crash))

        # Print out some information to make it easier to debug
        # the rollback.
        logging.debug('Dumping partition table.')
        host.run('cgpt show $(rootdev -s -d)')
        logging.debug('Dumping crossystem for firmware debugging.')
        host.run('crossystem --all')
        raise Exception(error_message)

    # Make sure chromeos-setgoodkernel runs.
    try:
        utils.poll_for_condition(
            lambda: (get_kernel_tries(host, active_kernel) == 0
                     and get_kernel_success(host, active_kernel)),
            timeout=_KERNEL_UPDATE_TIMEOUT, sleep_interval=5)
    except Exception:
        services_status = host.run(['status', 'system-services']).stdout
        if services_status != 'system-services start/running\n':
            raise Exception('Chrome failed to reach login screen')
        else:
            raise Exception('update-engine failed to call '
                            'chromeos-setgoodkernel')
