# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Batch of Bluetooth LE tests for Better Together"""

import logging
import base64
import json

from autotest_lib.server.cros.bluetooth.bluetooth_adapter_quick_tests import \
     BluetoothAdapterQuickTests
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_pairing_tests import \
     BluetoothAdapterPairingTests
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_tests import \
    test_retry_and_log

class bluetooth_AdapterLEBetterTogether(BluetoothAdapterQuickTests,
        BluetoothAdapterPairingTests):
    """A Batch of Bluetooth LE tests for Better Together. This test is written
       as a batch of tests in order to reduce test time, since auto-test ramp up
       time is costly. The batch is using BluetoothAdapterQuickTests wrapper
       methods to start and end a test and a batch of tests.

       This class can be called to run the entire test batch or to run a
       specific test only
    """

    BETTER_TOGETHER_SERVICE_UUID = 'b3b7e28e-a000-3e17-bd86-6e97b9e28c11'
    CLIENT_RX_CHARACTERISTIC_UUID = '00000100-0004-1000-8000-001a11000102'
    CLIENT_TX_CHARACTERISTIC_UUID = '00000100-0004-1000-8000-001a11000101'
    CCCD_VALUE_INDICATION = 0x02
    TEST_ITERATION = 3

    # The following messages were captured during a smart unlock process. These
    # are the messages exchanged between the phone and the chromebook to
    # authorize each other in order to unlock the chromebook.
    CONNECTION_OPEN_MESSAGE = b'\x80\x00\x01\x00\x01\x00\x00'
    MESSAGE_1 = b'\x1c\x03\x00\xc7\x7b\x22\x66\x65\x61\x74\x75\x72'\
                 '\x65\x22\x3a\x22\x61\x75\x74\x68\x22\x2c\x22\x70'\
                 '\x61\x79\x6c\x6f\x61\x64\x22\x3a\x22\x43\x6c\x6b'\
                 '\x4b\x56\x41\x67\x42\x45\x41\x45\x79\x54\x67\x70'\
                 '\x4b\x43\x41\x45\x53\x52\x67\x6f\x68\x41\x49\x37'\
                 '\x6e\x78\x63\x34\x6b\x44\x4d\x68\x6d\x68\x6e\x4d'\
                 '\x75\x69\x7a\x79\x62\x47\x54\x5f\x31\x4e\x6c\x52'\
                 '\x4c\x6c\x6d\x32\x59\x34\x72\x35\x78\x6f\x6e\x69'\
                 '\x47\x51\x35\x49\x6a\x45\x69\x45\x41\x75\x45\x64'\
                 '\x43\x4c\x37\x36\x44\x70\x30\x70\x6a\x6a\x75\x74'\
                 '\x56\x6a\x47\x35\x38\x62\x55\x49\x57\x42\x57\x49'\
                 '\x41\x4f\x5a\x39\x38\x46\x43\x49\x4f\x79\x58\x68'\
                 '\x2d\x6b\x66\x6f\x51\x41\x52\x49\x42\x72\x68\x49'\
                 '\x67\x7a\x35\x62\x49\x37\x53\x6f\x59\x47\x56\x36'\
                 '\x6b\x4e\x4e\x74\x6d\x73\x59\x53\x6a\x75\x68\x4d'\
                 '\x68\x61\x66\x51\x6c\x4d\x44\x55\x68\x78\x42\x36'\
                 '\x44\x50\x52\x79\x4c\x5a\x62\x30\x3d\x22\x7d'

    MESSAGE_2 = b'\x2c\x03\x00\xfb\x7b\x22\x66\x65\x61\x74\x75\x72'\
                 '\x65\x22\x3a\x22\x61\x75\x74\x68\x22\x2c\x22\x70'\
                 '\x61\x79\x6c\x6f\x61\x64\x22\x3a\x22\x43\x6f\x41'\
                 '\x42\x43\x68\x77\x49\x41\x52\x41\x43\x4b\x68\x43'\
                 '\x34\x69\x38\x45\x47\x73\x76\x71\x6e\x78\x5f\x66'\
                 '\x66\x4c\x33\x59\x42\x61\x6b\x35\x59\x4d\x67\x51'\
                 '\x49\x44\x52\x41\x42\x45\x6d\x42\x41\x71\x5f\x47'\
                 '\x62\x72\x49\x42\x6c\x42\x42\x76\x73\x6a\x73\x32'\
                 '\x67\x47\x56\x59\x70\x76\x73\x50\x6f\x64\x57\x6e'\
                 '\x70\x50\x42\x6e\x5a\x71\x41\x61\x46\x6b\x30\x59'\
                 '\x54\x48\x76\x79\x6b\x55\x76\x6b\x4a\x79\x6c\x35'\
                 '\x56\x54\x7a\x48\x53\x35\x43\x6e\x41\x65\x56\x4d'\
                 '\x79\x38\x49\x76\x44\x5f\x67\x65\x6d\x4e\x65\x42'\
                 '\x61\x76\x58\x70\x70\x52\x62\x4b\x43\x42\x34\x5f'\
                 '\x35\x35\x79\x4a\x50\x4e\x6b\x5f\x76\x45\x66\x53'\
                 '\x38\x57\x5a\x7a\x6d\x58\x64\x5a\x4d\x68\x72\x74'\
                 '\x31\x61\x6d\x67\x46\x7a\x6e\x35\x4b\x65\x61\x2d'\
                 '\x77\x5f\x58\x55\x53\x49\x47\x54\x6e\x55\x33\x6d'\
                 '\x68\x45\x36\x67\x63\x5a\x4c\x4b\x49\x52\x79\x4d'\
                 '\x61\x39\x68\x78\x41\x4f\x30\x4b\x6f\x7a\x6d\x68'\
                 '\x43\x71\x6d\x4d\x42\x54\x4a\x6e\x57\x4e\x6f\x52'\
                 '\x62\x22\x7d'

    MESSAGE_3 = b'\x3c\x03\x00\xae\x7b\x22\x66\x65\x61\x74\x75\x72'\
                 '\x65\x22\x3a\x22\x65\x61\x73\x79\x5f\x75\x6e\x6c'\
                 '\x6f\x63\x6b\x22\x2c\x22\x70\x61\x79\x6c\x6f\x61'\
                 '\x64\x22\x3a\x22\x43\x6b\x41\x4b\x48\x41\x67\x42'\
                 '\x45\x41\x49\x71\x45\x44\x30\x72\x52\x69\x54\x77'\
                 '\x32\x41\x6e\x6e\x5f\x5f\x5f\x59\x33\x6c\x68\x55'\
                 '\x53\x65\x45\x79\x42\x41\x67\x4e\x45\x41\x45\x53'\
                 '\x49\x46\x59\x61\x64\x36\x33\x43\x75\x52\x34\x67'\
                 '\x37\x77\x4d\x41\x4b\x61\x65\x76\x2d\x72\x7a\x38'\
                 '\x66\x64\x6f\x47\x46\x2d\x67\x44\x4c\x6a\x37\x50'\
                 '\x47\x62\x43\x6f\x57\x54\x66\x6f\x45\x69\x43\x38'\
                 '\x4a\x56\x62\x4c\x48\x75\x49\x35\x42\x76\x38\x43'\
                 '\x4c\x74\x73\x53\x51\x35\x50\x4c\x6e\x72\x5a\x41'\
                 '\x70\x68\x6b\x75\x4c\x78\x2d\x56\x59\x64\x6c\x32'\
                 '\x53\x4d\x71\x5f\x36\x41\x3d\x3d\x22\x7d'

    MESSAGE_4 = b'\x4c\x03\x00\xc2\x7b\x22\x66\x65\x61\x74\x75\x72'\
                 '\x65\x22\x3a\x22\x65\x61\x73\x79\x5f\x75\x6e\x6c'\
                 '\x6f\x63\x6b\x22\x2c\x22\x70\x61\x79\x6c\x6f\x61'\
                 '\x64\x22\x3a\x22\x43\x6c\x41\x4b\x48\x41\x67\x42'\
                 '\x45\x41\x49\x71\x45\x4d\x61\x4e\x6c\x75\x43\x56'\
                 '\x63\x72\x59\x37\x68\x70\x34\x68\x46\x74\x69\x6f'\
                 '\x45\x4d\x6b\x79\x42\x41\x67\x4e\x45\x41\x45\x53'\
                 '\x4d\x47\x6c\x68\x33\x55\x68\x44\x77\x58\x4b\x70'\
                 '\x58\x46\x5f\x5a\x6e\x4f\x61\x30\x36\x4a\x48\x4b'\
                 '\x69\x6b\x56\x68\x51\x62\x32\x50\x4d\x36\x62\x62'\
                 '\x76\x78\x51\x6a\x47\x50\x47\x73\x66\x79\x42\x5a'\
                 '\x74\x52\x67\x39\x5f\x65\x36\x6f\x42\x5a\x79\x5f'\
                 '\x74\x35\x42\x45\x74\x78\x49\x67\x51\x75\x37\x42'\
                 '\x62\x6e\x75\x4e\x57\x64\x67\x6d\x42\x36\x4d\x47'\
                 '\x75\x68\x54\x79\x34\x33\x43\x37\x32\x2d\x58\x44'\
                 '\x58\x35\x4b\x4f\x6a\x67\x6d\x56\x74\x48\x58\x41'\
                 '\x68\x4e\x67\x3d\x22\x7d'

    CONNECTION_CLOSE_MESSAGE = b'\xd2\x00\x00'

    test_wrapper = BluetoothAdapterQuickTests.quick_test_test_decorator
    batch_wrapper = BluetoothAdapterQuickTests.quick_test_batch_decorator

    @test_wrapper('Smart Unlock', devices={'BLE_PHONE':1})
    def smart_unlock_test(self):
        """Simulate the Smart Unlock flow, here are the steps that involve
           1. Set the discovery filter to match LE devices only.
           2. Start the discovery.
           3. Stop the discovery after the device was found.
           4. Set the LE connection parameters to reduce the min and max
              connection intervals to 6.
           5. Pause the discovery sessions from all the clients.
           6. Connect the device.
           7. Unpause the discovery sessions once the device was connected.
           8. Set the Trusted property of the device to true.
           9. Verify all the services were resolved.
           10. Start notification on the RX characteristic of the
               Proximity Service.
           11. Exchange some messages with the peer device to authorize it.
           12. Stop the notification.
           13. Disconnect the device.
        """

        filter = {'Transport':'le'}
        parameters = {'MinimumConnectionInterval':6,
                      'MaximumConnectionInterval':6}
        address = self.devices['BLE_PHONE'][0].address

        # We don't use the control file for iteration since it will involve the
        # device setup steps which don't reflect the real user scenario.
        for i in range(self.TEST_ITERATION):
            self.test_set_discovery_filter(filter)
            self.test_discover_device(address)
            self.test_stop_discovery()

            self.test_set_le_connection_parameters(address, parameters)
            self.test_pause_discovery()
            self.test_connection_by_adapter(address)
            self.test_unpause_discovery()

            self.test_set_trusted(address)
            self.test_service_resolved(address)
            self.test_find_object_path(address)

            self.test_start_notify(self.rx_object_path,
                                   self.CCCD_VALUE_INDICATION)
            self.test_messages_exchange(
                self.rx_object_path, self.tx_object_path, address)
            self.test_stop_notify(self.rx_object_path)
            self.test_disconnection_by_adapter(address)

            self.test_remove_device_object(address)


    @test_retry_and_log(False)
    def test_remove_device_object(self, address):
        """Test the device object can be removed from the adapter"""
        return self.bluetooth_facade.remove_device_object(address)


    @test_retry_and_log(False)
    def test_find_object_path(self, address):
        """Test the object path can be found for a device"""
        self.tx_object_path = None
        self.rx_object_path = None
        attr_map = self.bluetooth_facade.get_gatt_attributes_map(address)
        attr_map_json = json.loads(attr_map)
        servs_json = attr_map_json['services']
        for uuid_s in servs_json:
            if uuid_s == self.BETTER_TOGETHER_SERVICE_UUID:
                chrcs_json = servs_json[uuid_s]['characteristics']
                for uuid_c in chrcs_json:
                    if uuid_c == self.CLIENT_TX_CHARACTERISTIC_UUID:
                        self.tx_object_path = chrcs_json[uuid_c]['path']
                    if uuid_c == self.CLIENT_RX_CHARACTERISTIC_UUID:
                        self.rx_object_path = chrcs_json[uuid_c]['path']

        return self.tx_object_path and self.rx_object_path


    @test_retry_and_log(False)
    def test_messages_exchange(
        self, rx_object_path, tx_object_path, address):
        """Test message exchange with the peer, Better Together performs the
           messages exchange for authorizing the peer device before unlocking
           the Chromebook.
        """

        self.test_message_exchange(
            rx_object_path,
            tx_object_path,
            self.CONNECTION_OPEN_MESSAGE,
            'connection open message')

        self.test_message_exchange(
            rx_object_path,
            tx_object_path,
            self.MESSAGE_1,
            'message 1')

        self.test_message_exchange(
            rx_object_path,
            tx_object_path,
            self.MESSAGE_2,
            'message 2')

        # Better Together gets connection info multiple times to ensure
        # the device is close enough by checking the RSSI, here we simulate it.
        for i in range(9):
            self.test_get_connection_info(address)

        self.test_message_exchange(
            rx_object_path,
            tx_object_path,
            self.MESSAGE_3,
            'message 3')

        self.test_message_exchange(
            rx_object_path,
            tx_object_path,
            self.MESSAGE_4,
            'message 4')

        for i in range(2):
            self.test_get_connection_info(address)

        self.test_message_exchange(
            rx_object_path,
            tx_object_path,
            self.CONNECTION_CLOSE_MESSAGE,
            'connection close message')

        return True


    @test_retry_and_log(False)
    def test_message_exchange(
        self, rx_object_path, tx_object_path, message, message_type):
        """Test message exchange between DUT and the peer device"""
        ret_msg = self.bluetooth_facade.exchange_messages(
            tx_object_path, rx_object_path, message)

        if not ret_msg:
            logging.error("Failed to write message: %s", message_type)
            return False

        return base64.standard_b64decode(ret_msg) == message


    @batch_wrapper('Better Together')
    def better_together_batch_run(self, num_iterations=1, test_name=None):
        """Run the Bluetooth LE for Better Together test batch or a specific
           given test. The wrapper of this method is implemented in
           batch_decorator. Using the decorator a test batch method can
           implement the only its core tests invocations and let the
           decorator handle the wrapper, which is taking care for whether to
           run a specific test or the batch as a whole, and running the batch
           in iterations

           @param num_iterations: how many iterations to run
           @param test_name: specific test to run otherwise None to run the
                             whole batch
        """
        self.smart_unlock_test()


    def run_once(self, host, num_iterations=1, test_name=None,
                 flag='Quick Sanity'):
        """Run the batch of Bluetooth LE tests for Better Together

        @param host: the DUT, usually a chromebook
        @param num_iterations: the number of rounds to execute the test
        @test_name: the test to run, or None for all tests
        """

        # Initialize and run the test batch or the requested specific test
        self.quick_test_init(host, use_btpeer=True, flag=flag)
        self.better_together_batch_run(num_iterations, test_name)
        self.quick_test_cleanup()
