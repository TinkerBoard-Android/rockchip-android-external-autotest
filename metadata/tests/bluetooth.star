
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# !!! GENERATED FILE. DO NOT EDIT !!!

load('//metadata/test_common.star', 'test_common')

def define_tests():
    return [
        test_common.define_test(
            'bluetooth/AdapterAUSanity',
            suites = ['bluetooth'],
        ),
        test_common.define_test(
            'bluetooth/AdapterAdvSanity',
            suites = ['bluetooth_qualification'],
        ),
        test_common.define_test(
            'bluetooth/AdapterAudioLink',
            suites = ['bluetooth_flaky'],
        ),
        test_common.define_test(
            'bluetooth/AdapterCLSanity',
            suites = ['bluetooth_qualification'],
        ),
        test_common.define_test(
            'bluetooth/AdapterMDSanity',
            suites = ['bluetooth_qualification'],
        ),
        test_common.define_test(
            'bluetooth/AdapterReboot',
            suites = [],
        ),
        test_common.define_test(
            'bluetooth/AdapterSRSanity',
            suites = ['bluetooth_qualification'],
        ),
        test_common.define_test(
            'bluetooth/AdapterSanity',
            suites = [],
        ),
        test_common.define_test(
            'bluetooth/PeerUpdate',
            suites = ['bluetooth_e2e', 'bluetooth_mtbf'],
        ),
        test_common.define_test(
            'bluetooth/RegressionClient',
            suites = [],
        ),
        test_common.define_test(
            'bluetooth/RegressionServer',
            suites = [],
        ),
        test_common.define_test(
            'bluetooth/TurnOnOffUI',
            suites = ['bluetooth_flaky'],
        )
    ]
