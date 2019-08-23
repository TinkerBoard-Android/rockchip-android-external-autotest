# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Server side bluetooth tests on adapter pairing and connecting to a bluetooth
HID device.
"""

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.bluetooth import bluetooth_adapter_tests
from autotest_lib.server.cros.multimedia import remote_facade_factory


class bluetooth_AdapterPairing(
        bluetooth_adapter_tests.BluetoothAdapterTests):
    """Server side bluetooth adapter pairing and connecting to bluetooth device

    This test tries to verify that the adapter of the DUT could
    pair and connect to a bluetooth HID device correctly.

    In particular, the following subtests are performed. Look at the
    docstrings of the subtests for more details.
    -

    Refer to BluetoothAdapterTests for all subtests performed in this test.

    """

    # TODO(josephsih): Reduce the sleep intervals to speed up the tests.
    PAIR_TEST_SLEEP_SECS = 5

    def pairing_test(self, device, pairing_twice=False, suspend_resume=False,
                     reboot=False):
        """Running Bluetooth adapter tests about pairing to a device."""

        # Reset the adapter to forget previously paired devices if any.
        self.test_reset_on_adapter()

        # The adapter must be set to the pairable state.
        self.test_pairable()

        # Test if the adapter could discover the target device.
        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        self.test_discover_device(device.address)

        # Test if the discovery could be stopped.
        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        self.test_stop_discovery()

        # Test if the discovered device class of service is correct.
        self.test_device_class_of_service(device.address,
                                          device.class_of_service)

        # Test if the discovered device class of device is correct.
        self.test_device_class_of_device(device.address,
                                         device.class_of_device)

        # Verify that the adapter could pair with the device.
        # Also set the device trusted when pairing is done.
        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        self.test_pairing(device.address, device.pin, trusted=True)

        # Verify that the adapter could connect to the device.
        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        self.test_connection_by_adapter(device.address)

        # Test if the discovered device name is correct.
        # Sometimes, it takes quite a long time after discovering
        # the device (more than 60 seconds) to resolve the device name.
        # Hence, it is safer to test the device name after pairing and
        # connection is done.
        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        self.test_device_name(device.address, device.name)

        # Test if the device is still connected after suspend/resume.
        if suspend_resume:
            self.suspend_resume()

            time.sleep(self.PAIR_TEST_SLEEP_SECS)
            self.test_device_is_paired(device.address)

            # After a suspend/resume, we need to wake the peripheral
            # as it is not connected.
            time.sleep(self.PAIR_TEST_SLEEP_SECS)
            self.test_connection_by_device(device)

            time.sleep(self.PAIR_TEST_SLEEP_SECS)
            self.test_device_name(device.address, device.name)

        # Test if the device is still connected after reboot.
        # if reboot:
        #     self.host.reboot()

        #     time.sleep(self.PAIR_TEST_SLEEP_SECS)
        #     self.test_device_is_paired(device.address)

        #     # After a reboot, we need to wake the peripheral
        #     # as it is not connected.
        #     time.sleep(self.PAIR_TEST_SLEEP_SECS)
        #     self.test_connection_by_adapter(device.address)

        #     time.sleep(self.PAIR_TEST_SLEEP_SECS)
        #     self.test_device_is_connected(device.address)

        #     time.sleep(self.PAIR_TEST_SLEEP_SECS)
        #     self.test_device_name(device.address, device.name)

        # Verify that the adapter could disconnect the device.
        self.test_disconnection_by_adapter(device.address)

        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        if device.can_init_connection:
            # Verify that the device could initiate the connection.
            self.test_connection_by_device(device)
        else:
            # Reconnect so that we can test disconnection from the kit
            self.test_connection_by_adapter(device.address)

        # TODO(alent): Needs a new capability, but this is a good proxy
        if device.can_init_connection:
            # Verify that the device could initiate the disconnection.
            self.test_disconnection_by_device(device)
        else:
            # Reconnect so that we can test disconnection from the kit
            self.test_disconnection_by_adapter(device.address)

        # Verify that the adapter could remove the paired device.
        self.test_remove_pairing(device.address)

        # Check if the device could be re-paired after being forgotten.
        if pairing_twice:
            # Test if the adapter could discover the target device again.
            time.sleep(self.PAIR_TEST_SLEEP_SECS)
            self.test_discover_device(device.address)

            # Verify that the adapter could pair with the device again.
            # Also set the device trusted when pairing is done.
            time.sleep(self.PAIR_TEST_SLEEP_SECS)
            self.test_pairing(device.address, device.pin, trusted=True)

            # Verify that the adapter could remove the paired device again.
            time.sleep(self.PAIR_TEST_SLEEP_SECS)
            self.test_remove_pairing(device.address)


    def connect_disconnect_loop(self, device, loops):

        # First pair and disconnect, to emulate real life scenario
        self.test_discover_device(device.address)
        # self.bluetooth_facade.is_discovering() doesn't work as expected:
        # crbug:905374
        # self.test_stop_discovery()
        self.bluetooth_facade.stop_discovery()
        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        self.test_pairing(device.address, device.pin, trusted=True)
        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        # Disconnect the device
        self.test_disconnection_by_adapter(device.address)
        total_duration_by_adapter = 0
        loop_cnt = 0
        for i in xrange(0, loops):

            # Verify device didn't connect automatically
            time.sleep(2)
            self.test_device_is_not_connected(device.address)

            start_time = time.time()
            self.test_connection_by_adapter(device.address)
            end_time = time.time()
            time_diff = end_time - start_time

            # Verify device is now connected
            self.test_device_is_connected(device.address)
            self.test_disconnection_by_adapter(device.address)

            if not bool(self.fails):
                loop_cnt += 1
                total_duration_by_adapter += time_diff
                logging.info('%d: Connection establishment duration %f sec',
                             i, time_diff)
            else:
               break

        if not bool(self.fails):
            logging.info('Average duration (by adapter) %f sec',
                         total_duration_by_adapter/loop_cnt)


    def auto_reconnect_loop(self, device, loops):
        # Let the adapter pair, and connect to the target device first
        self.test_discover_device(device.address)
        # self.bluetooth_facade.is_discovering() doesn't work as expected:
        # crbug:905374
        # self.test_stop_discovery()
        self.bluetooth_facade.stop_discovery()
        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        self.test_pairing(device.address, device.pin, trusted=True)
        time.sleep(self.PAIR_TEST_SLEEP_SECS)
        self.test_connection_by_adapter(device.address)

        total_reconnection_duration = 0
        loop_cnt = 0
        for i in xrange(loops):
            # Restart and clear peer HID device
            self.restart_peers()
            start_time = time.time()

            # Verify that the device is reconnecting
            self.test_device_is_connected(device.address)
            end_time = time.time()
            time_diff = end_time - start_time

            if not bool(self.fails):
                total_reconnection_duration += time_diff
                loop_cnt += 1
                logging.info('%d: Reconnection duration %f sec', i, time_diff)
            else:
               break

        if not bool(self.fails):
            logging.info('Average Reconnection duration %f sec',
                         total_reconnection_duration/loop_cnt)


    def run_once(self, host, device_type, num_iterations=1, min_pass_count=1,
                 pairing_twice=False, suspend_resume=False, reboot=False):
        """Running Bluetooth adapter tests about pairing to a device.

        @param host: the DUT, usually a chromebook
        @param device_type : the bluetooth HID device type, e.g., 'MOUSE'
        @param num_iterations: the number of rounds to execute the test
        @param min_pass_count: the minimal pass count to pass this test
        @param pairing_twice: True if the host tries to pair the device
                again after the paired device is removed.
        @param suspend_resume: True if the host suspends/resumes after
                pairing.
        @param reboot: True if the host reboots after pairing.

        """
        self.host = host
        factory = remote_facade_factory.RemoteFacadeFactory(host)
        self.bluetooth_facade = factory.create_bluetooth_hid_facade()
        self.input_facade = factory.create_input_facade()
        self.check_chameleon()

        pass_count = 0
        self.total_fails = {}
        for iteration in xrange(1, num_iterations + 1):
            self.fails = []

            # Get the device object and query some important properties.
            device = self.get_device(device_type)
            self.pairing_test(device, pairing_twice, suspend_resume, reboot)

            if bool(self.fails):
                self.total_fails['Round %d' % iteration] = self.fails
            else:
                pass_count += 1

            fail_count = iteration - pass_count
            logging.info('===  (pass = %d, fail = %d) / total %d  ===\n',
                         pass_count, fail_count, num_iterations)

        if pass_count < min_pass_count:
            raise error.TestFail(self.total_fails)
