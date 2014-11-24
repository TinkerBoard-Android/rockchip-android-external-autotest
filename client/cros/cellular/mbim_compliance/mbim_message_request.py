# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
All of the MBIM request message type definitions are in this file. These
definitions inherit from MBIMControlMessage.

Reference:
    [1] Universal Serial Bus Communications Class Subclass Specification for
        Mobile Broadband Interface Model
        http://www.usb.org/developers/docs/devclass_docs/
        MBIM10Errata1_073013.zip
"""
import logging
import math

from autotest_lib.client.cros.cellular.mbim_compliance import mbim_constants
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_message


class MBIMControlMessageRequest(mbim_message.MBIMControlMessage):
    """ MBIMMessage Request Message base class. """
    MESSAGE_TYPE = mbim_message.MESSAGE_TYPE_REQUEST
    _FIELDS = (('I', 'message_type', mbim_message.FIELD_TYPE_PAYLOAD_ID),
               ('I', 'message_length', ''),
               ('I', 'transaction_id', ''))
    _DEFAULTS = {'message_length': 0, 'transaction_id': 0}


class MBIMOpen(MBIMControlMessageRequest):
    """ The class for MBIM_OPEN_MSG. """

    _FIELDS = (('I', 'max_control_transfer', ''),)
    _DEFAULTS = {'message_type': mbim_constants.MBIM_OPEN_MSG}


class MBIMClose(MBIMControlMessageRequest):
    """ The class for MBIM_CLOSE_MSG. """

    _DEFAULTS = {'message_type': mbim_constants.MBIM_CLOSE_MSG}


class MBIMCommandSecondary(MBIMControlMessageRequest):
    """ The class for MBIM_COMMAND_MSG. """

    _FIELDS = (('I', 'total_fragments', ''),
               ('I', 'current_fragment', ''))


class MBIMCommand(MBIMControlMessageRequest):
    """ The class for MBIM_COMMAND_MSG. """

    _FIELDS = (('I', 'total_fragments', ''),
               ('I', 'current_fragment', ''),
               ('16s', 'device_service_id', mbim_message.FIELD_TYPE_PAYLOAD_ID),
               ('I', 'cid', mbim_message.FIELD_TYPE_PAYLOAD_ID),
               ('I', 'command_type', ''),
               ('I', 'information_buffer_length', ''))
    _DEFAULTS = {'message_type': mbim_constants.MBIM_COMMAND_MSG,
                 'total_fragments': 0x00000001,
                 'current_fragment': 0x00000000,
                 'information_buffer_length': 0}
    _SECONDARY_FRAGMENT = MBIMCommandSecondary


class MBIMHostError(MBIMControlMessageRequest):
    """ The class for MBIM_ERROR_MSG. """

    _FIELDS = (('I', 'error_status_code', ''),)
    _DEFAULTS = {'message_type': mbim_constants.MBIM_HOST_ERROR_MSG}


def fragment_request_packets(message, max_fragment_length):
    """
    Fragments request messages into a multiple fragment packets if the total
    message length is greater than the |max_fragment_length| specified by the
    device.

    It splits the payload_buffer fields into the primary and secondary
    fragments.

    @param message: Monolithic message object.
    @param max_fragment_length: Max length of each fragment expected by device.
    @returns List of fragmented packets.

    """
    primary_frag_class = message.__class__.find_primary_parent_fragment()
    secondary_frag_class = primary_frag_class.get_secondary_fragment()
    if not secondary_frag_class:
        mbim_errors.log_and_raise(
                mbim_errors.MBIMComplianceControlMessageError,
                'No secondary fragment class defined')
    # Let's recreate the primary frag object from the raw data of the
    # initial message.
    raw_data = message.create_raw_data(payload_buffer=message.payload_buffer)
    message = primary_frag_class(raw_data=raw_data)

    primary_struct_len = primary_frag_class.get_struct_len(get_all=True)
    secondary_struct_len = secondary_frag_class.get_struct_len(get_all=True)
    total_length = message.message_length
    total_payload_length = total_length - primary_struct_len
    remaining_payload_length = total_payload_length
    remaining_payload_buffer = message.payload_buffer
    primary_frag_length = max_fragment_length
    primary_payload_length =  primary_frag_length - primary_struct_len
    remaining_payload_length -= primary_payload_length
    num_fragments = 1
    num_fragments += int(
            math.ceil(remaining_payload_length /
                      float(max_fragment_length - secondary_struct_len)))

    packets = []
    message_field_names = message.__class__.get_field_names(get_all=True)
    message_field_values = [getattr(message, field_name)
                            for field_name in message_field_names]
    args_list = dict(zip(message_field_names, message_field_values))
    args_list['current_fragment'] = 1
    args_list['total_fragments'] = num_fragments
    args_list['message_length'] = primary_frag_length
    primary_message = primary_frag_class(**args_list)

    primary_message.print_all_fields()
    packet = primary_message.create_raw_data(
            payload_buffer=remaining_payload_buffer[:primary_payload_length])
    remaining_payload_buffer = (
            remaining_payload_buffer[primary_payload_length:])
    packets.append(packet)

    for fragment_num in range(1, num_fragments):
        secondary_frag_length = min(
                max_fragment_length,
                remaining_payload_length + secondary_struct_len)
        secondary_payload_length = secondary_frag_length - secondary_struct_len
        remaining_payload_length -= secondary_payload_length
        args_list['current_fragment'] = fragment_num
        args_list['total_fragments'] = num_fragments
        args_list['message_length'] = secondary_frag_length
        secondary_message = secondary_frag_class(**args_list)
        secondary_message.print_all_fields()
        packet = secondary_message.create_raw_data(
                payload_buffer=remaining_payload_buffer[:secondary_payload_length])
        remaining_payload_buffer = (
                remaining_payload_buffer[secondary_payload_length:])
        packets.append(packet)

    logging.debug('Request Num Fragments: %d, Total len: %d, Max Frag len: %d',
                  num_fragments, total_length, max_fragment_length)
    return packets


def generate_request_packets(message, max_fragment_length):
    """
    Generates raw data corresponding to the incoming message request object.

    @param message: One of the defined MBIM request messages.
    @param max_fragment_length: Max length of each fragment expected by device.
    @returns List of raw byte array packets.

    """
    if message.MESSAGE_TYPE != mbim_message.MESSAGE_TYPE_REQUEST:
        mbim_errors.log_and_raise(
                mbim_errors.MBIMComplianceControlMessageError,
                'Not a valid request message (%s)' % message.__name__)
    message_class = message.__class__
    message_class.transaction_id = message.get_transaction_id()
    message_class.message_length = message_class.get_struct_len(get_all=True)
    if message.payload_buffer:
        message_class.message_length += len(message.payload_buffer)

    if message.message_length < max_fragment_length:
        packet = message.create_raw_data(payload_buffer=message.payload_buffer)
        packets = [packet]
    else:
        packets = fragment_request_packets(message, max_fragment_length)

    return packets
