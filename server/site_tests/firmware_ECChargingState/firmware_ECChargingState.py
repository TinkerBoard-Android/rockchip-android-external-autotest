# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_ECChargingState(FirmwareTest):
    """
    Type-C servo-v4 based EC charging state test.
    """
    version = 1

    # The delay to wait for the AC state to update
    AC_STATE_UPDATE_DELAY = 3

    def initialize(self, host, cmdline_args):
        super(firmware_ECChargingState, self).initialize(host, cmdline_args)
        if not self.check_ec_capability(['battery', 'charging']):
            raise error.TestNAError("Nothing needs to be tested on this DUT")
        if self.servo.get_servo_version() != 'servo_v4_with_ccd_cr50':
            raise error.TestNAError("This test can only be run with servo-v4 "
                    "+ CCD. If you don't have a Type-C servo-v4, please run "
                    "the test manually.")
        if host.is_ac_connected() != True:
            raise error.TestFail("This test must be run with AC power.")
        self.switcher.setup_mode('normal')
        self.ec.send_command("chan save")
        self.ec.send_command("chan 0")

    def cleanup(self):
        try:
            self.ec.send_command("chan restore")
        except Exception as e:
            logging.error("Caught exception: %s", str(e))
        super(firmware_ECChargingState, self).cleanup()

    def check_ac_state(self):
        """Check if AC is plugged."""
        ac_state = int(self.ec.send_command_get_output("chgstate",
            ["ac\s*=\s*(0|1)\s*"])[0][1])
        if ac_state == 1:
            return 'on'
        elif ac_state == 0:
            return 'off'
        else:
            return 'unknown'

    def run_once(self, host):
        """Execute the main body of the test."""

        if host.is_ac_connected() != True:
            raise error.TestFail("This test must be run with AC power.")

        logging.info("Suspend, unplug AC, and then wake up the device.")
        self.suspend()
        self.switcher.wait_for_client_offline()

        # Call set_servo_v4_role_to_snk() instead of directly setting
        # servo_v4 role to snk, so servo_v4_role can be recovered to
        # default src in cleanup().
        self.set_servo_v4_role_to_snk()
        time.sleep(self.AC_STATE_UPDATE_DELAY)

        # Verify servo v4 is sinking power.
        if self.check_ac_state() != 'off':
            raise error.TestFail("Fail to unplug AC.")

        self.servo.power_normal_press()
        self.switcher.wait_for_client()

        batt_state = host.get_battery_state()
        if batt_state != 'Discharging':
            raise error.TestFail("Wrong battery state. Expected: "
                    "Discharging, got: %s." % batt_state)

        logging.info("Suspend, plug AC, and then wake up the device.")
        self.suspend()
        self.switcher.wait_for_client_offline()
        self.servo.set_servo_v4_role('src')
        time.sleep(self.AC_STATE_UPDATE_DELAY)

        # Verify servo v4 is sourcing power.
        if self.check_ac_state() != 'on':
            raise error.TestFail("Fail to plug AC.")

        self.servo.power_normal_press()
        self.switcher.wait_for_client()

        batt_state = host.get_battery_state()
        if batt_state != 'Charging' and batt_state != 'Fully charged':
            raise error.TestFail("Wrong battery state. Expected: "
                    "Charging/Fully charged, got: %s." % batt_state)
