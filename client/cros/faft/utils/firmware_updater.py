# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A module to support automatic firmware update.

See FirmwareUpdater object below.
"""
import json
import os

from autotest_lib.client.common_lib.cros import chip_utils
from autotest_lib.client.cros.faft.utils import (flashrom_handler,
                                                 shell_wrapper)


class FirmwareUpdaterError(Exception):
    """Error in the FirmwareUpdater module."""


class FirmwareUpdater(object):
    """An object to support firmware update.

    This object will create a temporary directory in /var/tmp/faft/autest with
    two subdirectory keys/ and work/. You can modify the keys in keys/
    directory. If you want to provide a given shellball to do firmware update,
    put shellball under /var/tmp/faft/autest with name chromeos-firmwareupdate.
    """

    DAEMON = 'update-engine'
    CBFSTOOL = 'cbfstool'
    HEXDUMP = 'hexdump -v -e \'1/1 "0x%02x\\n"\''

    def __init__(self, os_if):
        self.os_if = os_if
        self._temp_path = '/var/tmp/faft/autest'
        self._cbfs_work_path = os.path.join(self._temp_path, 'cbfs')
        self._keys_path = os.path.join(self._temp_path, 'keys')
        self._work_path = os.path.join(self._temp_path, 'work')
        self._bios_path = 'bios.bin'
        self._ec_path = 'ec.bin'

        pubkey_path = os.path.join(self._keys_path, 'root_key.vbpubk')
        self._real_bios_handler = flashrom_handler.FlashromHandler(
                self.os_if,
                pubkey_path,
                self._keys_path,
                'bios',
        )
        self._real_ec_handler = flashrom_handler.FlashromHandler(
                self.os_if,
                pubkey_path,
                self._keys_path,
                'ec',
        )

        # _detect_image_paths always needs to run during initialization
        # or after extract_shellball is called.
        #
        # If we are setting up the temp dir from scratch, we'll transitively
        # call _detect_image_paths since extract_shellball is called.
        # Otherwise, we need to scan the existing temp directory.
        if not self.os_if.is_dir(self._temp_path):
            self._setup_temp_dir()
        else:
            self._detect_image_paths()

    @property
    def _bios_handler(self):
        """Return the BIOS flashrom handler, after initializing it if necessary

        @rtype: flashrom_handler.FlashromHandler
        """
        if not self._real_bios_handler.initialized:
            bios_file = os.path.join(self._work_path, self._bios_path)
            self._real_bios_handler.init(bios_file)

        return self._real_bios_handler

    @property
    def _ec_handler(self):
        """Return the EC flashrom handler, after initializing it if necessary.
        If there's no usable EC flash, this will raise an exception, instead of
        allowing further attempts to run flashrom commands.

        @rtype: flashrom_handler.FlashromHandler
        @raise: FirmwareUpdaterError
        """
        # Raise an exception early if there's no usable EC flash.
        if not self._real_ec_handler.is_available():
            # Can't tell for sure whether it's broken or simply nonexistent.
            raise FirmwareUpdaterError("No usable EC flash was detected.")

        if not self._real_ec_handler.initialized:
            ec_file = os.path.join(self._work_path, self._ec_path)

            if os.path.exists(ec_file):
                self._real_ec_handler.init(ec_file)
            else:
                self.os_if.log(
                        "Shellball EC image missing: %s\n"
                        "Trying current flash contents instead." % ec_file)
                self._real_ec_handler.init()

        return self._real_ec_handler

    def _setup_temp_dir(self):
        """Setup temporary directory.

        Devkeys are copied to _key_path. Then, shellball (default:
        /usr/sbin/chromeos-firmwareupdate) is extracted to _work_path.
        """
        self.cleanup_temp_dir()

        self.os_if.create_dir(self._temp_path)
        self.os_if.create_dir(self._cbfs_work_path)
        self.os_if.create_dir(self._work_path)
        self.os_if.copy_dir('/usr/share/vboot/devkeys', self._keys_path)

        original_shellball = '/usr/sbin/chromeos-firmwareupdate'
        working_shellball = os.path.join(self._temp_path,
                                         'chromeos-firmwareupdate')
        self.os_if.copy_file(original_shellball, working_shellball)
        self.extract_shellball()

    def cleanup_temp_dir(self):
        """Cleanup temporary directory."""
        if self.os_if.is_dir(self._temp_path):
            self.os_if.remove_dir(self._temp_path)

    def stop_daemon(self):
        """Stop update-engine daemon."""
        self.os_if.log('Stopping %s...' % self.DAEMON)
        cmd = 'status %s | grep stop || stop %s' % (self.DAEMON, self.DAEMON)
        self.os_if.run_shell_command(cmd)

    def start_daemon(self):
        """Start update-engine daemon."""
        self.os_if.log('Starting %s...' % self.DAEMON)
        cmd = 'status %s | grep start || start %s' % (self.DAEMON, self.DAEMON)
        self.os_if.run_shell_command(cmd)

    def retrieve_fwid(self):
        """Retrieve shellball's fwid tuple.

        This method should be called after _setup_temp_dir.

        Returns:
            Shellball's fwid tuple (ro_fwid, rw_fwid).
        """
        self._bios_handler.new_image(
                os.path.join(self._work_path, self._bios_path))
        # Remove the tailing null characters
        ro_fwid = self._bios_handler.get_section_fwid('ro').rstrip('\0')
        rw_fwid = self._bios_handler.get_section_fwid('a').rstrip('\0')
        return (ro_fwid, rw_fwid)

    def retrieve_ecid(self):
        """Retrieve shellball's ecid.

        This method should be called after _setup_temp_dir.

        Returns:
            Shellball's ecid.
        """
        self._ec_handler.new_image(
                os.path.join(self._work_path, self._ec_path))
        fwid = self._ec_handler.get_section_fwid('rw')
        # Remove the tailing null characters
        return fwid.rstrip('\0')

    def retrieve_ec_hash(self):
        """Retrieve the hex string of the EC hash."""
        return self._ec_handler.get_section_hash('rw')

    def modify_ecid_and_flash_to_bios(self):
        """Modify ecid, put it to AP firmware, and flash it to the system.

        This method is used for testing EC software sync for EC EFS (Early
        Firmware Selection). It creates a slightly different EC RW image
        (a different EC fwid) in AP firmware, in order to trigger EC
        software sync on the next boot (a different hash with the original
        EC RW).

        The steps of this method:
         * Modify the EC fwid by appending a '~', like from
           'fizz_v1.1.7374-147f1bd64' to 'fizz_v1.1.7374-147f1bd64~'.
         * Resign the EC image.
         * Store the modififed EC RW image to CBFS component 'ecrw' of the
           AP firmware's FW_MAIN_A and FW_MAIN_B, and also the new hash.
         * Resign the AP image.
         * Flash the modified AP image back to the system.
        """
        self.cbfs_setup_work_dir()

        fwid = self.retrieve_ecid()
        if fwid.endswith('~'):
            raise FirmwareUpdaterError('The EC fwid is already modified')

        # Modify the EC FWID and resign
        fwid = fwid[:-1] + '~'
        self._ec_handler.set_section_fwid('rw', fwid)
        self._ec_handler.resign_ec_rwsig()

        # Replace ecrw to the new one
        ecrw_bin_path = os.path.join(self._cbfs_work_path,
                                     chip_utils.ecrw.cbfs_bin_name)
        self._ec_handler.dump_section_body('rw', ecrw_bin_path)

        # Replace ecrw.hash to the new one
        ecrw_hash_path = os.path.join(self._cbfs_work_path,
                                      chip_utils.ecrw.cbfs_hash_name)
        with open(ecrw_hash_path, 'w') as f:
            f.write(self.retrieve_ec_hash())

        # Store the modified ecrw and its hash to cbfs
        self.cbfs_replace_chip(chip_utils.ecrw.fw_name, extension='')

        # Resign and flash the AP firmware back to the system
        self.cbfs_sign_and_flash()

    def resign_firmware(self, version=None, work_path=None):
        """Resign firmware with version.

        Args:
            version: new firmware version number, default to no modification.
            work_path: work path, default to the updater work path.
        """
        if work_path is None:
            work_path = self._work_path
        self.os_if.run_shell_command(
                '/usr/share/vboot/bin/resign_firmwarefd.sh '
                '%s %s %s %s %s %s %s %s' %
                (os.path.join(work_path, self._bios_path),
                 os.path.join(self._temp_path, 'output.bin'),
                 os.path.join(self._keys_path, 'firmware_data_key.vbprivk'),
                 os.path.join(self._keys_path, 'firmware.keyblock'),
                 os.path.join(self._keys_path,
                              'dev_firmware_data_key.vbprivk'),
                 os.path.join(self._keys_path, 'dev_firmware.keyblock'),
                 os.path.join(self._keys_path, 'kernel_subkey.vbpubk'),
                 ('%d' % version) if version is not None else ''))
        self.os_if.copy_file(
                '%s' % os.path.join(self._temp_path, 'output.bin'),
                '%s' % os.path.join(work_path, self._bios_path))

    def _read_manifest(self, shellball=None):
        """This gets the manifest from the shellball or the extracted directory.
        If a shellball path is specified, it gets the info by running --manifest
        on it; otherwise, it reads manifest.json from the extracted work path.

        @param shellball: Path of the shellball to use the manifest from.
        @type shellball: str
        @return: the manifest information, or None
        @rtype: dict
        """

        if shellball:
            output = self.os_if.run_shell_command_get_output(
                    'sh %s --manifest' % shellball)
            manifest_text = '\n'.join(output or [])
        else:
            manifest_file = os.path.join(self._work_path, 'manifest.json')
            manifest_text = self.os_if.read_file(manifest_file)

        if manifest_text:
            return json.loads(manifest_text)
        else:
            # TODO(dgoyette): Perhaps raise an exception for empty manifest?
            return None

    def _detect_image_paths(self, shellball=None):
        """Scans shellball manifest to find correct bios and ec image paths.
        If a shellball path is specified, it gets the info by running --manifest
        on it; otherwise, it reads manifest.json from the extracted work path.

        @param shellball: Path of the shellball to use the manifest from.
        @type shellball: str
        """
        model_result = self.os_if.run_shell_command_get_output(
                'mosys platform model')

        if not model_result:
            return

        model_name = model_result[0]

        if not model_name:
            return

        manifest = self._read_manifest(shellball)

        if manifest:
            model_info = manifest.get(model_name)
            if model_info:

                try:
                    self._bios_path = model_info['host']['image']
                except KeyError:
                    pass

                try:
                    self._ec_path = model_info['ec']['image']
                except KeyError:
                    pass

    def extract_shellball(self, append=None):
        """Extract the working shellball.

        Args:
            append: decide which shellball to use with format
                chromeos-firmwareupdate-[append]. Use 'chromeos-firmwareupdate'
                if append is None.
        Returns:
            string: the full path of the shellball
        """
        working_shellball = os.path.join(self._temp_path,
                                         'chromeos-firmwareupdate')
        if append:
            working_shellball = working_shellball + '-%s' % append

        self.os_if.run_shell_command(
                'sh %s --sb_extract %s' % (working_shellball, self._work_path))

        self._detect_image_paths(working_shellball)
        return working_shellball

    def repack_shellball(self, append=None):
        """Repack shellball with new fwid.

        New fwid follows the rule: [orignal_fwid]-[append].

        Args:
            append: save the new shellball with a suffix, for example,
                chromeos-firmwareupdate-[append]. Use 'chromeos-firmwareupdate'
                if append is None.
        Returns:
            string: The full path to the shellball
        """

        working_shellball = os.path.join(self._temp_path,
                                         'chromeos-firmwareupdate')
        if append:
            new_shellball = working_shellball + '-%s' % append
            self.os_if.copy_file(working_shellball, new_shellball)
            working_shellball = new_shellball

        self.os_if.run_shell_command(
                'sh %s --sb_repack %s' % (working_shellball, self._work_path))

        self._detect_image_paths(working_shellball)
        return working_shellball

    def run_firmwareupdate(self, mode, updater_append=None, options=[]):
        """Do firmwareupdate with updater in temp_dir.

        Args:
            updater_append: decide which shellball to use with format
                chromeos-firmwareupdate-[append]. Use'chromeos-firmwareupdate'
                if updater_append is None.
            mode: ex.'autoupdate', 'recovery', 'bootok', 'factory_install'...
            options: ex. ['--noupdate_ec', '--force'] or [] for
                no option.
        """
        if updater_append:
            updater = os.path.join(
                    self._temp_path,
                    'chromeos-firmwareupdate-%s' % updater_append)
        else:
            updater = os.path.join(self._temp_path, 'chromeos-firmwareupdate')
        command = '/bin/sh %s --mode %s %s' % (updater, mode,
                                               ' '.join(options))

        if mode == 'bootok':
            # Since CL:459837, bootok is moved to chromeos-setgoodfirmware.
            new_command = '/usr/sbin/chromeos-setgoodfirmware'
            command = 'if [ -e %s ]; then %s; else %s; fi' % (
                    new_command, new_command, command)

        self.os_if.run_shell_command(command)

    def cbfs_setup_work_dir(self):
        """Sets up cbfs on DUT.

        Finds bios.bin on the DUT and sets up a temp dir to operate on
        bios.bin.  If a bios.bin was specified, it is copied to the DUT
        and used instead of the native bios.bin.

        Returns:
            The cbfs work directory path.
        """

        self.os_if.remove_dir(self._cbfs_work_path)
        self.os_if.copy_dir(self._work_path, self._cbfs_work_path)

        return self._cbfs_work_path

    def cbfs_extract_chip(self, fw_name, extension='.bin'):
        """Extracts chip firmware blob from cbfs.

        For a given chip type, looks for the corresponding firmware
        blob and hash in the specified bios.  The firmware blob and
        hash are extracted into self._cbfs_work_path.

        The extracted blobs will be <fw_name><extension> and
        <fw_name>.hash located in cbfs_work_path.

        Args:
            fw_name: Chip firmware name to be extracted.
            extension: Extension of the name of the cbfs component.

        Returns:
            Boolean success status.
        """

        bios = os.path.join(self._cbfs_work_path, self._bios_path)
        fw = fw_name
        cbfs_extract = '%s %s extract -r FW_MAIN_A -n %s%%s -f %s%%s' % (
                self.CBFSTOOL, bios, fw, os.path.join(self._cbfs_work_path,
                                                      fw))

        cmd = cbfs_extract % (extension, extension)
        if self.os_if.run_shell_command_get_status(cmd) != 0:
            return False

        cmd = cbfs_extract % ('.hash', '.hash')
        if self.os_if.run_shell_command_get_status(cmd) != 0:
            return False

        return True

    def cbfs_get_chip_hash(self, fw_name):
        """Returns chip firmware hash blob.

        For a given chip type, returns the chip firmware hash blob.
        Before making this request, the chip blobs must have been
        extracted from cbfs using cbfs_extract_chip().
        The hash data is returned as hexadecimal string.

        Args:
            fw_name:
                Chip firmware name whose hash blob to get.

        Returns:
            Boolean success status.

        Raises:
            shell_wrapper.ShellError: Underlying remote shell
                operations failed.
        """

        hexdump_cmd = '%s %s.hash' % (
                self.HEXDUMP, os.path.join(self._cbfs_work_path, fw_name))
        hashblob = self.os_if.run_shell_command_get_output(hexdump_cmd)
        return hashblob

    def cbfs_replace_chip(self, fw_name, extension='.bin'):
        """Replaces chip firmware in CBFS (bios.bin).

        For a given chip type, replaces its firmware blob and hash in
        bios.bin.  All files referenced are expected to be in the
        directory set up using cbfs_setup_work_dir().

        Args:
            fw_name: Chip firmware name to be replaced.
            extension: Extension of the name of the cbfs component.

        Returns:
            Boolean success status.

        Raises:
            shell_wrapper.ShellError: Underlying remote shell
                operations failed.
        """

        bios = os.path.join(self._cbfs_work_path, self._bios_path)
        rm_hash_cmd = '%s %s remove -r FW_MAIN_A,FW_MAIN_B -n %s.hash' % (
                self.CBFSTOOL, bios, fw_name)
        rm_bin_cmd = '%s %s remove -r FW_MAIN_A,FW_MAIN_B -n %s%s' % (
                self.CBFSTOOL, bios, fw_name, extension)
        expand_cmd = '%s %s expand -r FW_MAIN_A,FW_MAIN_B' % (self.CBFSTOOL,
                                                              bios)
        add_hash_cmd = ('%s %s add -r FW_MAIN_A,FW_MAIN_B -t raw -c none '
                        '-f %s.hash -n %s.hash') % (
                                self.CBFSTOOL, bios,
                                os.path.join(self._cbfs_work_path,
                                             fw_name), fw_name)
        add_bin_cmd = ('%s %s add -r FW_MAIN_A,FW_MAIN_B -t raw -c lzma '
                       '-f %s%s -n %s%s') % (
                               self.CBFSTOOL, bios,
                               os.path.join(self._cbfs_work_path, fw_name),
                               extension, fw_name, extension)
        truncate_cmd = '%s %s truncate -r FW_MAIN_A,FW_MAIN_B' % (
                self.CBFSTOOL, bios)

        self.os_if.run_shell_command(rm_hash_cmd)
        self.os_if.run_shell_command(rm_bin_cmd)
        try:
            self.os_if.run_shell_command(expand_cmd)
        except shell_wrapper.ShellError:
            self.os_if.log(
                    ('%s may be too old, '
                     'continuing without "expand" support') % self.CBFSTOOL)

        self.os_if.run_shell_command(add_hash_cmd)
        self.os_if.run_shell_command(add_bin_cmd)
        try:
            self.os_if.run_shell_command(truncate_cmd)
        except shell_wrapper.ShellError:
            self.os_if.log(
                    ('%s may be too old, '
                     'continuing without "truncate" support') % self.CBFSTOOL)

        return True

    def cbfs_sign_and_flash(self):
        """Signs CBFS (bios.bin) and flashes it."""
        self.resign_firmware(work_path=self._cbfs_work_path)
        self._bios_handler.new_image(
                os.path.join(self._cbfs_work_path, self._bios_path))
        self._bios_handler.write_whole()
        return True

    def get_temp_path(self):
        """Get temp directory path."""
        return self._temp_path

    def get_keys_path(self):
        """Get keys directory path."""
        return self._keys_path

    def get_cbfs_work_path(self):
        """Get cbfs work directory path."""
        return self._cbfs_work_path

    def get_work_path(self):
        """Get work directory path."""
        return self._work_path

    def get_bios_relative_path(self):
        """Gets the relative path of the bios image in the shellball."""
        return self._bios_path

    def get_ec_relative_path(self):
        """Gets the relative path of the ec image in the shellball."""
        return self._ec_path
