#!/usr/bin/env python2
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging

import common
from autotest_lib.client.common_lib import utils as client_utils

try:
    from chromite.lib import metrics
except ImportError:
    metrics = client_utils.metrics_mock


class _BaseUpdateServoFw(object):
    """Base class to update firmware on servo"""

    # Command to update servo with --force.
    # param 1: servo board (servo_v4|servo_micro)
    # param 2: serial number of main device on the board
    UPDATER = 'servo_updater -b %s -s %s --force --reboot'

    # Command to read current version on the servo
    # param 1: serial number of main device on the board
    SERVO_VERSION = 'cat $(servodtool device -s %s usb-path)/configuration'

    # Command to read servod config file with extracting value by key
    # param 1: servo port, provided by servo config
    # param 2: required parammeter (key) from config file
    SERVOD_CONFIG = 'cat /var/lib/servod/config_%s | grep %s'

    # Command to get PATH to the latest available firmware on the host
    # param 1: servo board (servo_v4|servo_micro)
    LATEST_VERSION_FW = 'realpath /usr/share/servo_updater/firmware/%s.bin'

    # Command to get servo product supported by device
    # param 1: serial number of main device on the board
    SERVO_PRODUCT = 'cat $(servodtool device -s %s usb-path)/product'

    def __init__(self, servo_host):
        self._host = servo_host
        # keep flag that class support and can run updater
        self._supported = None

    def check_needs(self):
        """Check if class supports update for particular servo type"""
        if self._supported is None:
            if not self._host:
                self._supported = False
            elif not self._host.is_labstation():
                self._supported = False
            elif not self._host.servo_serial:
                self._supported = False
            elif not self._check_needs():
                self._supported = False
            else:
                self._supported = self._is_outdated_version()
        return self._supported

    def update(self):
        """Update firmware on the servo.

        Steps:
        1) Verify servo is not updated by checking the versions.
        2) Try to get serial number for the servo.
        3) Updating firmware with --force. Standard update happens
        during servod startup.
        """
        if not self.check_needs():
            return
        if not self.get_serial_number():
            logging.info('Serial number is not detected. It means no update'
                         ' will be performed on servo.')
            return
        self._update_firmware()

    def _check_needs(self):
        """Check is servo type supported"""
        raise NotImplementedError('Please implement method to perform'
                                  ' check of supporting the servo type')

    def get_board(self):
        """Return servo type supported by updater"""
        raise NotImplementedError('Please implement method to return'
                                  ' servo type')

    def get_serial_number(self):
        """Return serial number for main servo device on servo"""
        raise NotImplementedError('Please implement method to return'
                                  ' serial number')

    def _update_firmware(self):
        """Run servo_updater.

        Method generate a metric to collect statistics of update.
        """
        board = self.get_board()
        serial_number = self.get_serial_number()
        cmd = self.UPDATER % (board, serial_number)
        logging.info('Servo fw update: %s', cmd)
        result = self._host.run(cmd, ignore_status=True).stdout.strip()
        logging.debug('Servo fw update finished; %s', result)
        logging.info('Servo fw update finished')
        metrics.Counter(
            'chromeos/autotest/audit/servo/fw_update'
            ).increment(fields={'status': 'success'})

    def _get_config_value(self, key):
        """Read configuration value by provided key.

        @param key: key from key=value pair in config file.
                    eg: 'HUB' or 'SERVO_MICRO_SERIAL'
        """
        """Read value from servod config file"""
        cmd = self.SERVOD_CONFIG % (self._host.servo_port, key)
        result = self._host.run(cmd, ignore_status=True).stdout.strip()
        if result:
            return result[len(key)+1:]
        return None

    def _current_version(self):
        """Get current version on servo device"""
        cmd = self.SERVO_VERSION % self.get_serial_number()
        version = self._host.run(cmd, ignore_status=True).stdout.strip()
        logging.debug('Current version: %s', version)
        return version

    def _latest_version(self):
        """Get latest version available on servo-host"""
        cmd = self.LATEST_VERSION_FW % self.get_board()
        filepath = self._host.run(cmd, ignore_status=True).stdout.strip()
        if not filepath:
            return None
        version = os.path.basename(os.path.splitext(filepath)[0]).strip()
        logging.debug('Latest version: %s', version)
        return version

    def _is_outdated_version(self):
        """Compare version to determine request to update the Servo or not.

        Method generate metrics to collect statistics with version.
        """
        current_version = self._current_version()
        latest_version = self._latest_version()
        if not current_version or not latest_version:
            return True
        if current_version == latest_version:
            return False
        metrics.Counter(
            'chromeos/autotest/audit/servo/fw_need_update'
            ).increment(fields={'version': current_version})
        return True

    def _get_product(self):
        """Get servo product from servo device"""
        cmd = self.SERVO_PRODUCT % self.get_serial_number()
        return self._host.run(cmd, ignore_status=True).stdout.strip()


class UpdateServoV4Fw(_BaseUpdateServoFw):
    """Servo firmware updater for servo_v4 version.

    Update firmware will be only if new version present and servo
    was not updated.
    """
    def get_board(self):
        """Return servo type supported by updater"""
        return 'servo_v4'

    def get_serial_number(self):
        # serial number of servo_v4 match with device number
        return self._host.servo_serial

    def _check_needs(self):
        """Check if servo is servo_v4.

        Check servo type.
        Check access to the serial number.
        """
        if self._get_product() != 'Servo V4':
            return False
        if not self.get_serial_number():
            return False
        return True


class UpdateServoMicroFw(_BaseUpdateServoFw):
    """Servo firmware updater for servo_micro version.

    Update firmware will be only if new version present and servo
    was not updated.
    """
    def __init__(self, servo_host):
        super(UpdateServoMicroFw, self).__init__(servo_host)
        self._serial_number = None

    def get_board(self):
        """Return servo type supported by updater"""
        return 'servo_micro'

    def get_serial_number(self):
        # serial number of servo_v4 match with device number
        if self._serial_number is None:
            # servo_micro serial number is not match to serial on
            # the servo device servod is keeping it in config file
            serial = self._get_config_value('SERVO_MICRO_SERIAL')
            self._serial_number = serial if serial is not None else ''
        return self._serial_number

    def _check_needs(self):
        """Check if servo is servo_micro.

        Check servo type.
        Check access to the serial number.
        """
        if not self.get_serial_number():
            # set does not include servo_micro
            return False
        if self._get_product() != 'Servo Micro':
            return False
        return True