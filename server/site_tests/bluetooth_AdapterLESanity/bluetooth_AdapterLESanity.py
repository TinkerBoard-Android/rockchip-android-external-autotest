# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Batch of of Bluetooth LE sanity tests"""

import time

from autotest_lib.server.cros.bluetooth.bluetooth_adapter_controller_role_tests\
     import bluetooth_AdapterControllerRoleTests
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_quick_tests import \
     BluetoothAdapterQuickTests
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_pairing_tests import \
     BluetoothAdapterPairingTests
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_hidreports_tests \
     import BluetoothAdapterHIDReportTests
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_tests import \
     EXT_ADV_MODELS


# TODO(b/161174805) - veyron_fievel and veyron_mickey experiencing an
# unexpected re-connect to peer, causing peer tests to fail. LE Role tests are
# being hit especially hard, so temporarily disabling these tests on veyron
LAB_VEYRON_MODELS = ['veyron_mickey', 'veyron_fievel']

class bluetooth_AdapterLESanity(BluetoothAdapterQuickTests,
        BluetoothAdapterPairingTests,
        BluetoothAdapterHIDReportTests,
        bluetooth_AdapterControllerRoleTests):
    """A Batch of Bluetooth LE sanity tests. This test is written as a batch
       of tests in order to reduce test time, since auto-test ramp up time is
       costly. The batch is using BluetoothAdapterQuickTests wrapper methods to
       start and end a test and a batch of tests.

       This class can be called to run the entire test batch or to run a
       specific test only
    """

    test_wrapper = BluetoothAdapterQuickTests.quick_test_test_decorator
    batch_wrapper = BluetoothAdapterQuickTests.quick_test_batch_decorator

    @test_wrapper('Discovery Test', devices={"BLE_MOUSE":1})
    def le_discovery_test(self):
        """Performs discovery test with mouse peripheral"""
        device = self.devices['BLE_MOUSE'][0]

        self.test_discover_device(device.address)

        # Removed due to b:149093897 - the raspi peer can't instantly update
        # the advertised name, causing this test to fail
        # self.test_device_name(device.address, device.name)


    @test_wrapper('Connect Disconnect Loop', devices={'BLE_MOUSE':1})
    def le_connect_disconnect_loop(self):
        """Run connect/disconnect loop initiated by DUT.
           The test also checks that there are no undesired
           reconnections.
           TODO(ysahvit) - add connection creation attempts
                           initiated by HID device
        """

        device = self.devices['BLE_MOUSE'][0]
        self.connect_disconnect_loop(device=device, loops=3)


    @test_wrapper('Mouse Reports', devices={'BLE_MOUSE':1})
    def le_mouse_reports(self):
        """Run all bluetooth mouse reports tests"""

        device = self.devices['BLE_MOUSE'][0]
        # Let the adapter pair, and connect to the target device.
        self.test_discover_device(device.address)
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_pairing(device.address, device.pin, trusted=True)

        # With raspberry pi peer, it takes a moment before the device is
        # registered as an input device. Without delay, the input recorder
        # doesn't find the device
        time.sleep(1)
        self.run_mouse_tests(device=device)


    @test_wrapper('Keyboard Reports', devices={'BLE_KEYBOARD':1})
    def le_keyboard_reports(self):
        """Run all bluetooth keyboard reports tests"""

        device = self.devices['BLE_KEYBOARD'][0]
        # Let the adapter pair, and connect to the target device.
        self.test_discover_device(device.address)
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_pairing(device.address, device.pin, trusted=True)

        # With raspberry pi peer, it takes a moment before the device is
        # registered as an input device. Without delay, the input recorder
        # doesn't find the device
        time.sleep(1)
        self.run_keyboard_tests(device=device)


    @test_wrapper('Auto Reconnect', devices={'BLE_MOUSE':1})
    def le_auto_reconnect(self):
        """LE reconnection loop by reseting HID and check reconnection"""

        device = self.devices['BLE_MOUSE'][0]
        self.auto_reconnect_loop(device=device,
                                 loops=3,
                                 check_connected_method=\
                                 self.test_mouse_left_click)


    @test_wrapper('GATT Client', devices={'BLE_KEYBOARD':1})
    def le_gatt_client_attribute_browse_test(self):
        """Browse the whole tree-structured GATT attributes"""

        device = self.devices['BLE_KEYBOARD'][0]
        self.test_discover_device(device.address)
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_pairing(device.address, device.pin, trusted=True)
        self.test_service_resolved(device.address)
        self.test_gatt_browse(device.address)


    @test_wrapper('LE secondary Test', devices={'BLE_KEYBOARD':1},
                  skip_models=LAB_VEYRON_MODELS)
    def le_role_secondary(self):
        """Tests connection as secondary"""

        self.verify_controller_capability(
                        required_roles=['peripheral'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')
        self.controller_secondary_role_test(kbd, kbd_test_func)


    @test_wrapper('LE primary Before secondary Test',
                  devices={'BLE_KEYBOARD':1, 'BLE_MOUSE':1},
                  skip_models=LAB_VEYRON_MODELS)
    def le_role_primary_before_secondary(self):
        """Tests connection as primary and then as secondary"""

        self.verify_controller_capability(
                        required_roles=['central-peripheral'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        mouse = self.devices['BLE_MOUSE'][0]

        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')
        mouse_test_func = self.test_mouse_left_click

        hid_test_device = (mouse, mouse_test_func, 'pre')
        self.controller_secondary_role_test(
                kbd, kbd_test_func, secondary_info=hid_test_device)


    @test_wrapper('LE secondary Before primary Test', devices={'BLE_KEYBOARD':1,
                                                          'BLE_MOUSE':1},
                  skip_models=LAB_VEYRON_MODELS)
    def le_role_secondary_before_primary(self):
        """Tests connection as secondary and then as primary"""

        self.verify_controller_capability(
                        required_roles=['central-peripheral'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        mouse = self.devices['BLE_MOUSE'][0]

        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')
        mouse_test_func = self.test_mouse_left_click

        hid_test_device = (mouse, mouse_test_func, 'mid')
        self.controller_secondary_role_test(
                kbd, kbd_test_func, secondary_info=hid_test_device)


    @test_wrapper('LE Sender Role Test', devices={'BLE_KEYBOARD':1},
                  skip_models=LAB_VEYRON_MODELS)
    def le_role_sender(self):
        """Tests basic Nearby Sender role"""

        self.verify_controller_capability(
                        required_roles=['central'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')

        self.nearby_sender_role_test(kbd, kbd_test_func)


    @test_wrapper('LE Sender Role Test During HID',
                  devices={'BLE_KEYBOARD':1, 'BLE_MOUSE':1},
                  skip_models=LAB_VEYRON_MODELS)
    def le_role_sender_during_hid(self):
        """Tests Nearby Sender role while already connected to HID device"""

        self.verify_controller_capability(
                        required_roles=['central-peripheral'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        mouse = self.devices['BLE_MOUSE'][0]

        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')
        mouse_test_func = self.test_mouse_left_click

        hid_test_device = (mouse, mouse_test_func, 'pre')
        self.nearby_sender_role_test(
                kbd, kbd_test_func, secondary_info=hid_test_device)


    @test_wrapper('LE HID Test During Sender Role',
                  devices={'BLE_KEYBOARD':1, 'BLE_MOUSE':1},
                  skip_models=LAB_VEYRON_MODELS)
    def le_role_hid_during_sender(self):
        """Tests HID device while already in Nearby Sender role"""

        self.verify_controller_capability(
                        required_roles=['central'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        mouse = self.devices['BLE_MOUSE'][0]

        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')
        mouse_test_func = self.test_mouse_left_click

        hid_test_device = (mouse, mouse_test_func, 'mid')
        self.nearby_sender_role_test(
                kbd, kbd_test_func, secondary_info=hid_test_device)


    @test_wrapper('LE Receiver Role Test', devices={'BLE_KEYBOARD':1},
                  skip_models=LAB_VEYRON_MODELS)
    def le_role_receiver(self):
        """Tests basic Nearby Receiver role"""

        self.verify_controller_capability(
                        required_roles=['peripheral'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')

        self.nearby_receiver_role_test(kbd, kbd_test_func)


    @test_wrapper('LE Receiver Role Test During HID',
                  devices={'BLE_KEYBOARD':1, 'BLE_MOUSE':1},
                  skip_models=LAB_VEYRON_MODELS)
    def le_role_receiver_during_hid(self):
        """Tests Nearby Receiver role while already connected to HID device"""

        self.verify_controller_capability(
                        required_roles=['central-peripheral'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        mouse = self.devices['BLE_MOUSE'][0]

        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')
        mouse_test_func = self.test_mouse_left_click

        hid_test_device = (mouse, mouse_test_func, 'pre')
        self.nearby_receiver_role_test(
                kbd, kbd_test_func, secondary_info=hid_test_device)


    # TODO(b/162324887) - platforms supporting extended advertising do not
    # properly resume advertising after connecting an LE device
    @test_wrapper('LE HID Test During Receiver Adv',
                  devices={'BLE_KEYBOARD':1, 'BLE_MOUSE':1},
                  skip_models=EXT_ADV_MODELS+LAB_VEYRON_MODELS)
    def le_role_hid_during_receiver_adv(self):
        """Tests HID device while already in Nearby Receiver role adv state"""

        self.verify_controller_capability(
                        required_roles=['central-peripheral'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        mouse = self.devices['BLE_MOUSE'][0]

        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')
        mouse_test_func = self.test_mouse_left_click

        hid_test_device = (mouse, mouse_test_func, 'mid')
        self.nearby_receiver_role_test(
                kbd, kbd_test_func, secondary_info=hid_test_device)


    @test_wrapper('LE HID Test During Receiver Role',
                  devices={'BLE_KEYBOARD':1, 'BLE_MOUSE':1},
                  skip_models=LAB_VEYRON_MODELS)
    def le_role_hid_during_receiver_connection(self):
        """Tests HID device while already in Nearby Receiver role connection"""

        self.verify_controller_capability(
                        required_roles=['central-peripheral'],
                        test_type=self.flag)

        kbd = self.devices['BLE_KEYBOARD'][0]
        mouse = self.devices['BLE_MOUSE'][0]

        kbd_test_func = lambda device: self.test_keyboard_input_from_trace(
                device, 'simple_text')
        mouse_test_func = self.test_mouse_left_click

        hid_test_device = (mouse, mouse_test_func, 'end')
        self.nearby_receiver_role_test(
                kbd, kbd_test_func, secondary_info=hid_test_device)


    @batch_wrapper('LE Sanity')
    def le_sanity_batch_run(self, num_iterations=1, test_name=None):
        """Run the LE sanity test batch or a specific given test.
           The wrapper of this method is implemented in batch_decorator.
           Using the decorator a test batch method can implement the only its
           core tests invocations and let the decorator handle the wrapper,
           which is taking care for whether to run a specific test or the
           batch as a whole, and running the batch in iterations

           @param num_iterations: how many interations to run
           @param test_name: specifc test to run otherwise None to run the
                             whole batch
        """
        self.le_connect_disconnect_loop()
        self.le_mouse_reports()
        self.le_keyboard_reports()
        self.le_auto_reconnect()
        self.le_discovery_test()


    def run_once(self, host, num_iterations=1, test_name=None,
                 flag='Quick Sanity'):
        """Run the batch of Bluetooth LE sanity tests

        @param host: the DUT, usually a chromebook
        @param num_iterations: the number of rounds to execute the test
        @test_name: the test to run, or None for all tests
        """

        # Initialize and run the test batch or the requested specific test
        self.quick_test_init(host, use_btpeer=True, flag=flag)
        self.le_sanity_batch_run(num_iterations, test_name)
        self.quick_test_cleanup()
