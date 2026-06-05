# coding: utf-8

"""
This module contains the implementation of :class:`lin.Message`.

.. note::
    Could use `@dataclass <https://docs.python.org/3.7/library/dataclasses.html>`__
    starting with Python 3.7.
"""

from __future__ import absolute_import, division

import warnings
from copy import deepcopy
from math import isinf, isnan

LIN_RECEIVE = 0x00
LIN_MASTER_WRITE = 0x01
LIN_MASTER_READ = 0x02
LIN_SLAVE_WRITE = 0x03
LIN_BM_WRITE = 0x00   
LIN_BM_TXTASK = 0x01

def calculatePID(ucId):
    chChecksum = ucId
    chMask = [0] * 8
    byte = [0] * 8
    for nIndex in range(8):
        chMask[nIndex] = nIndex + 1
        byte[nIndex] = (chChecksum >> nIndex) & 1

    # chP0 = ID0+ID1+ID2+ID4
    chP0 = byte[0] ^ byte[1] ^ byte[2] ^ byte[4]

    # chP1 = ID1+ID3+ID4+ID5
    chP1 = byte[1] + byte[3] + byte[4] + byte[5]
    chP1 = ~chP1

    # 00010110 -> p00010110
    chP0 = chP0 << 6
    chP1 = chP1 << 7
    chChecksum = chChecksum + chP0 + chP1
    ucId = chChecksum
    return ucId & 0xFF


def calculateChecksum(xData, xDataLen, pId):
    sum_val = pId
    for i in range(xDataLen):
        sum_val += xData[i]
        while sum_val > 0xFF:
            sum_val -= 0xFF
    return ~sum_val & 0xFF

class Message(object):
    """
    The :class:`~lin.Message` object is used to represent LIN messages for
    sending, receiving and other purposes like converting between different
    logging formats.

    Messages lin use extended identifiers, be remote or error frames, contain
    data and may be associated to a channel.

    Messages are always compared by identity and never by value, because that
    may introduce unexpected behaviour. See also :meth:`~lin.Message.equals`.

    :func:`~copy.copy`/:func:`~copy.deepcopy` is supported as well.

    Messages do not support "dynamic" attributes, meaning any others than the
    documented ones, since it uses :attr:`~object.__slots__`.
    """

    __slots__ = (
        "timestamp",
        "msgtype",
        "is_enhanced_checksum",
        "lin_id",
        "pid",
        "channel",
        "checksum",
        "dlc",
        "data",
        "__weakref__",              # support weak references to messages
        "_dict"                     # see __getattr__
    )

    def __getattr__(self, key):
        # TODO keep this for a version, in order to not break old code
        # this entire method (as well as the _dict attribute in __slots__ and the __setattr__ method)
        # can be removed in 4.0
        # this method is only called if the attribute was not found elsewhere, like in __slots_
        if key not in self.__slots__:
            raise AttributeError
        try:
            warnings.warn("Custom attributes of messages are deprecated and will be removed in 4.0", DeprecationWarning)
            return self._dict[key]
        except KeyError:
            raise AttributeError("'message' object has no attribute '{}'".format(key))

    def __setattr__(self, key, value):
        # see __getattr__
        try:
            super(Message, self).__setattr__(key, value)
        except AttributeError:
            warnings.warn("Custom attributes of messages are deprecated and will be removed in 4.0", DeprecationWarning)
            self._dict[key] = value

    def __init__(self, timestamp=0.0, lin_id=0,
                channel=None,
                 dlc=None, data=None,
                 check=False,
                 msgtype=LIN_RECEIVE, is_enhanced_checksum=False, checksum = None
                 ):
        """
        To create a message object, simply provide any of the below attributes
        together with additional parameters as keyword arguments to the constructor.

        :param bool check: By default, the constructor of this class does not strictly check the input.
                           Thus, the caller must prevent the creation of invalid messages or
                           set this parameter to `True`, to raise an Error on invalid inputs.
                           Possible problems include the `dlc` field not matching the length of `data`
                           or creating a message with both `is_remote_frame` and `is_error_frame` set to `True`.
        :param int msgtype: The type of the message. Must be one of the following:
                            LIN_RECEIVE = 0x00
                            LIN_MASTER_WRITE = 0x01
                            LIN_MASTER_READ = 0x02
                            LIN_SLAVE_WRITE = 0x03
        :raises ValueError: iff `check` is set to `True` and one or more arguments were invalid
        """
        self._dict = dict() # see __getattr__

        self.timestamp = timestamp
        self.lin_id = lin_id

        self.channel = channel

        self.msgtype = msgtype
        self.is_enhanced_checksum = is_enhanced_checksum

        if isinstance(data, bytearray):
            self.data = data
        else:
            try:
                self.data = bytearray(data)
            except TypeError:
                err = "Couldn't create message from {} ({})".format(data, type(data))
                raise TypeError(err)

        if dlc is None:
            self.dlc = len(self.data)
        else:
            self.dlc = dlc
        self.dlc = max(0, min(self.dlc, 8))

        self.pid = calculatePID(self.lin_id)

        if checksum is None:
            self.checksum = calculateChecksum(self.data, self.dlc, self.pid if self.is_enhanced_checksum else 0)
        else:
            self.checksum = checksum
        if check:
            self._check()

    def __str__(self):
        field_strings = ["Timestamp: {0:>15.6f}".format(self.timestamp)]
        lin_id_string = "ID: 0x{0:08X}".format(self.lin_id)
        field_strings.append(lin_id_string.rjust(12, " "))

        field_strings.append("DLC: {0:2d}".format(self.dlc))
        data_strings = []
        if self.data is not None:
            for index in range(0, min(self.dlc, len(self.data))):
                data_strings.append("{0:02x}".format(self.data[index]))
        if data_strings:  # if not empty
            field_strings.append(" ".join(data_strings).ljust(24, " "))
        else:
            field_strings.append(" " * 24)

        field_strings.append("ChecksumType: ")
        if self.is_enhanced_checksum:
            field_strings.append("Enhanced")
        else:
            field_strings.append("Classic")
        field_strings.append("Checksum: 0x{0:02X}".format(self.checksum))
        if self.channel is not None:
            try:
                field_strings.append("Channel: {}".format(self.channel))
            except UnicodeEncodeError:
                pass

        return "    ".join(field_strings).strip()

    def __len__(self):
        # return the dlc such that it also works on remote frames
        return self.dlc

    def __bool__(self):
        # For Python 3
        return True

    def __nonzero__(self):
        # For Python 2
        return self.__bool__()

    def __repr__(self):
        args = ["timestamp={}".format(self.timestamp),
                "lin_id={:#x}".format(self.lin_id),
                "extended_id={}".format(self.is_extended_id)]

        if self.is_remote_frame:
            args.append("is_remote_frame={}".format(self.is_remote_frame))

        if self.is_error_frame:
            args.append("is_error_frame={}".format(self.is_error_frame))

        if self.channel is not None:
            args.append("channel={!r}".format(self.channel))                

        data = ["{:#02x}".format(byte) for byte in self.data]
        args += ["dlc={}".format(self.dlc),
                 "data=[{}]".format(", ".join(data))]

        if self.is_fd:
            args.append("is_fd=True")
            args.append("bitrate_switch={}".format(self.bitrate_switch))
            args.append("error_state_indicator={}".format(self.error_state_indicator))

        return "lin.Message({})".format(", ".join(args))

    def __format__(self, format_spec):
        if not format_spec:
            return self.__str__()
        else:
            raise ValueError("non empty format_specs are not supported")

    def __bytes__(self):
        return bytes(self.data)

    def __copy__(self):
        new = Message(
            timestamp=self.timestamp,
            lin_id=self.lin_id,
            is_extended_id=self.is_extended_id,
            is_remote_frame=self.is_remote_frame,
            is_error_frame=self.is_error_frame,
            channel=self.channel,
            dlc=self.dlc,
            data=self.data,
            is_fd=self.is_fd,
            bitrate_switch=self.bitrate_switch,
            error_state_indicator=self.error_state_indicator,
            is_enhanced_checksum=self.is_enhanced_checksum,
            is_masterread=self.is_masterread
        )
        new._dict.update(self._dict)
        return new

    def __deepcopy__(self, memo):
        new = Message(
            timestamp=self.timestamp,
            lin_id=self.lin_id,
            is_extended_id=self.is_extended_id,
            is_remote_frame=self.is_remote_frame,
            is_error_frame=self.is_error_frame,
            channel=deepcopy(self.channel, memo),
            dlc=self.dlc,
            data=deepcopy(self.data, memo),
            is_fd=self.is_fd,
            bitrate_switch=self.bitrate_switch,
            error_state_indicator=self.error_state_indicator,
            is_enhanced_checksum=self.is_enhanced_checksum,
            is_masterread=self.is_masterread
        )
        new._dict.update(self._dict)
        return new

    def _check(self):
        """Checks if the message parameters are valid.
        Assumes that the types are already correct.

        :raises ValueError: iff one or more attributes are invalid
        """

        if self.timestamp < 0.0:
            raise ValueError("the timestamp may not be negative")
        if isinf(self.timestamp):
            raise ValueError("the timestamp may not be infinite")
        if isnan(self.timestamp):
            raise ValueError("the timestamp may not be NaN")

        if self.is_remote_frame and self.is_error_frame:
            raise ValueError("a message cannot be a remote and an error frame at the sane time")

        if self.lin_id < 0:
            raise ValueError("arbitration IDs may not be negative")

        elif 0x3F <= self.lin_id:
            raise ValueError("Normal arbitration IDs must be less than 0x3F")

        if self.dlc < 0:
            raise ValueError("DLC may not be negative")
        elif 8 < self.dlc:
            raise ValueError("DLC was {} but it should be <= 8 for normal Lin frames".format(self.dlc))

        elif self.dlc != len(self.data):
            raise ValueError("the DLC and the length of the data must match up for non remote frames")

    def equals(self, other, timestamp_delta=1.0e-6):
        """
        Compares a given message with this one.

        :param lin.Message other: the message to compare with

        :type timestamp_delta: float or int or None
        :param timestamp_delta: the maximum difference at which two timestamps are
                                still considered equal or None to not compare timestamps

        :rtype: bool
        :return: True iff the given message equals this one
        """
        return (
            # check for identity first and finish fast
            self is other or
            # then check for equality by value
            (
                (
                    timestamp_delta is None or
                    abs(self.timestamp - other.timestamp) <= timestamp_delta
                ) and
                self.arbitration_id == other.arbitration_id and
                self.is_extended_id == other.is_extended_id and
                self.dlc == other.dlc and
                self.data == other.data and
                self.is_remote_frame == other.is_remote_frame and
                self.is_error_frame == other.is_error_frame and
                self.channel == other.channel and
                self.is_fd == other.is_fd and
                self.bitrate_switch == other.bitrate_switch and
                self.error_state_indicator == other.error_state_indicator
            )
        )
