# coding: utf-8

"""
Ctypes wrapper module for BUSMUST Lin Interface on win32/win64 systems.

Authors: busmust <busmust@126.com>, BUSMUST Co.,Ltd.
"""

# Import Standard Python Modules
# ==============================
import ctypes
import logging
import sys
import time
from typing import List
try:
    # Try builtin Python 3 Windows API
    from _winapi import WaitForSingleObject, INFINITE
    HAS_EVENTS = True
except ImportError:
    try:
        # Try pywin32 package
        from win32event import WaitForSingleObject, INFINITE
        HAS_EVENTS = True
    except ImportError:
        # Use polling instead
        HAS_EVENTS = False

# Import Modules
# ==============
from lin import BusABC, Message, LinError
from lin.message import LIN_RECEIVE, LIN_MASTER_WRITE, LIN_MASTER_READ, LIN_SLAVE_WRITE
from lin.bus import BusState
from lin.util import len2dlc, dlc2len
from .exceptions import BmError

# Define Module Logger
# ====================
LOG = logging.getLogger(__name__)

# Import safely Vector API module for Travis tests
bmapi = None
try:
    from . import bmapi
except Exception as exc:
    LOG.error('Could not import bmapi, please check your BMAPI path: %s', exc)
    raise exc

class BmLinTaskWrapper:
    def __init__(self, bus, store_task=True):
        self._bus = bus
        self._txtask_index = -1
        self._bmtxtask = None
        self._store_task = store_task

    def start(self):
        assert self._txtask_index == -1, "Task is already started"
        index = self.get_first_free_txtask_index()
        if index == -1:
            print("The upper limit of hardware sending tasks is now using software to send tasks")
            return False
        self._bmtxtask.type = bmapi.BM_TXTASK_FIXED
        self._txtask_index = index
        self._bus.add_periodic_txtask(self)
        command = bmapi.BM_CAN_TXTASK_TABLE | bmapi.BM_CAN_CTRL_WR
        bmapi.BM_Control(self._bus._handle, command, index, self._bus._channelinfo.port, ctypes.byref(self._bmtxtask), ctypes.sizeof(self._bmtxtask))
        return True

    def stop(self):
        exist = False
        for task in self._bus._periodic_tasks:
            if isinstance(task, BmLinTaskWrapper):
                if self._txtask_index == task._txtask_index:
                    exist = True
                    break
        if exist:
            self._bus.del_periodic_txtask(self)
            self._bmtxtask.type = bmapi.BM_TXTASK_INVALID
            command = bmapi.BM_CAN_TXTASK_TABLE | bmapi.BM_CAN_CTRL_WR
            bmapi.BM_Control(self._bus._handle, command, self._txtask_index, self._bus._channelinfo.port, ctypes.byref(self._bmtxtask), ctypes.sizeof(self._bmtxtask))
            self._txtask_index = -1

    def get_first_free_txtask_index(self):
        for i in range(self._bus._ntxtask):
            exist = False
            for task in self._bus._periodic_tasks:
                if isinstance(task, BmLinTaskWrapper):
                    if i == task._txtask_index:
                        exist = True
                        break
            if not exist:
                return i
        return -1

class BmLinBus(BusABC):
    """The Lin Bus implemented for the BUSMUST USB-LIN interface."""

    __initialized = False

    @classmethod
    def __init_class__(cls):
        if bmapi is None:
            raise ImportError("The BMAPI has not been loaded")
        if not BmLinBus.__initialized:
            bmapi.BM_Init()
            bmapi.BM_SetLogLevel(bmapi.BM_LOG_ERR)
            BmLinBus.__initialized = True

    def __init__(self, channel, 
                 is_master=True,
                 bitrate=19200, 
                 pullup=None, voltage=True,
                 lin_filter=None,
                 remote_ip=None,
                 remote_enumeration_timeout=100,
                 **kwargs):
        """
        :param int channel:
            The channel index to create this bus with, which is the index to all available ports when enumerating Busmust devices.
            Lin also be a string of the channel's full name. i.e. "BM-LIN-L1(1234) CH1"
        :param bool is_master:
            If master mode should be supported.
        :param int bitrate:
            Bitrate in bits/s.
        :param bool pullup:
            If 1KOhm Lin terminal register should be enabled.
        :param bool voltage:
            If use internal 12V DC-DC for pulling up should be enabled.
        """
        BmLinBus.__init_class__()
        self._bmapi = bmapi # Enable external access

        infolist = bmapi.BM_ChannelInfoListTypeDef()
        numOfInfo = ctypes.c_int(len(infolist.entries))
        if remote_ip is None:
            bmapi.BM_EnumerateByCap(ctypes.byref(infolist), ctypes.byref(numOfInfo), bmapi.BM_LIN_CAP)
        else:
            remote_ip_obj = (ctypes.c_uint8 * 4)()
            if type(remote_ip) is bytes:
                for i in range(4):
                    remote_ip_obj[i] = remote_ip[i]
            elif type(remote_ip) is str:
                parts = remote_ip.split('.')
                for i in range(4):
                    remote_ip_obj[i] = int(parts[i])
            else:
                raise BmError(bmapi.BM_ERROR_NODRIVER, "Channel remote address format error:" + str(remote_ip), "BmLinBus.__init__")
            bmapi.BM_EnumerateRemote(ctypes.byref(infolist), ctypes.byref(numOfInfo), remote_ip_obj, remote_enumeration_timeout)
        if isinstance(channel, int):
            if channel < numOfInfo.value:
                self._channelinfo = infolist.entries[channel]
            else:
                raise BmError(bmapi.BM_ERROR_NODRIVER, "Channel %d is not connected or is in use by another app." % channel, "BmLinBus.__init__")
        elif isinstance(channel, str):
            for info in infolist.entries:
                if info.name.decode() == channel:
                    self._channelinfo = info
                    break
            else:
                raise BmError(bmapi.BM_ERROR_NODRIVER, "Channel %s is not connected or is in use by another app." % channel, "BmLinBus.__init__")

        self._mode = bmapi.BM_LIN_MASTER_MODE
        if not is_master:
            self._mode = bmapi.BM_LIN_SLAVE_MODE

        self._tres = bmapi.BM_TRESISTOR_DISABLED
        if pullup == None:
            self._tres = bmapi.BM_TRESISTOR_PULLUP_1K if is_master else bmapi.BM_TRESISTOR_DISABLED
        else:
            self._tres = bmapi.BM_TRESISTOR_PULLUP_1K if pullup else bmapi.BM_TRESISTOR_DISABLED
        self._bitrate = bmapi.BM_BitrateTypeDef()
        self._bitrate.nbitrate = int(bitrate)

        self._handle = bmapi.BM_ChannelHandle()
        bmapi.BM_OpenEx(
            ctypes.byref(self._handle), 
            ctypes.byref(self._channelinfo), 
            self._mode, 
            self._tres, 
            ctypes.byref(self._bitrate), 
            ctypes.cast(ctypes.c_void_p(), ctypes.POINTER(bmapi.BM_RxFilterListTypeDef)), 0
        )
        voltage = bmapi.BM_LIN_VOLTAGE_12V_OUT if voltage else bmapi.BM_LIN_VOLTAGE_12V_IN
        bmapi.BM_SetLinVoltage(self._handle, voltage)
        self.channel_info = self._channelinfo.name.decode()

        startTimestamp = ctypes.c_uint32()
        bmapi.BM_GetTimestamp(self._handle, ctypes.byref(startTimestamp))
        self._time_offset = time.time() - startTimestamp.value * 1e-9

        self._notification = bmapi.BM_NotificationHandle()
        bmapi.BM_GetNotification(self._handle, ctypes.byref(self._notification))

        self._periodic_tasks: List[BmLinTaskWrapper] = []
        self._is_shutdown: bool = False
        time.sleep(0.05)

        self._state = BusState.ACTIVE
        ntxtask = ctypes.c_int(0) 

        try:
            result = bmapi.BM_Control(self._handle, bmapi.BM_GET_STAT, bmapi.BM_STAT_MAX_TXTASK, self._channelinfo.port, ctypes.byref(ntxtask), 4)
            if result > 0:
                buf = ctypes.create_string_buffer(256)
                bmapi.BM_GetErrorText(result, buf, len(buf), 0)
                raise BmError(result, buf.value.decode(), "BmLinBus.__init__")
        except BmError as e:
            ntxtask.value = 0
        self._ntxtask = ntxtask.value

        bmtxtask = bmapi.BM_TxTaskTypeDef()
        for index in range(self._ntxtask):
            bmtxtask.type = bmapi.BM_TXTASK_INVALID
            command = bmapi.BM_CAN_TXTASK_TABLE | bmapi.BM_CAN_CTRL_WR
            bmapi.BM_Control(self._handle, command, index, self._channelinfo.port, ctypes.byref(bmtxtask), ctypes.sizeof(bmtxtask))


    def send_periodic(self, msg, period, duration=None, store_task=True):
        bmtxtask = bmapi.BM_TxTaskTypeDef()
        txtask = BmLinTaskWrapper(self, store_task=store_task)
        bmtxtask.type = bmapi.BM_TXTASK_FIXED
        bmtxtask.unused = 0
        bmtxtask.flags |= bmapi.BM_LIN_MESSAGE_FLAGS_ENHANCED_CHECKSUM if msg.is_enhanced_checksum else 0
        bmtxtask.flags |= bmapi.BM_LIN_MESSAGE_FLAGS_TRANSMIT if not (msg.msgtype == LIN_MASTER_READ) else 0
        bmtxtask.length = msg.dlc
        bmtxtask.e2e = 0
        bmtxtask.reserved = 0
        cycle = round(period * 1000) if not (msg.msgtype == LIN_SLAVE_WRITE) else 0
        if duration is not None:
            nrounds = round(duration / period)
            bmtxtask.nrounds = nrounds if nrounds < 0xFFFF else 0xFFFF - 1
        else:
            bmtxtask.nrounds = 0xFFFF
        bmtxtask.cycle = cycle
        bmtxtask.nmessages = 1
        for i in range(bmtxtask.length):
            bmtxtask.payload[i] = msg.data[i]
        bmtxtask.id = msg.lin_id | (msg.checksum << 8)
        txtask._bus = self
        txtask._bmtxtask = bmtxtask
        succeed = txtask.start()
        if self._ntxtask <= 0 or succeed == False:
            return super().send_periodic(msg, period)
        return txtask

    def stop_all_periodic_tasks(self, remove_tasks=True):
        """Stop sending any messages that were started using **bus.send_periodic**.

        .. note::
            The result is undefined if a single task throws an exception while being stopped.

        :param bool remove_tasks:
            Stop tracking the stopped tasks.
        """
        if self._ntxtask <= 0:
            super().stop_all_periodic_tasks()
        else:
            # Stop tasks with store_task=True
            # For hardware tasks (BmLinTaskWrapper), check _store_task attribute
            # For software tasks, they are only in _periodic_tasks if store_task=True
            for txtask in self._periodic_tasks:
                if isinstance(txtask, BmLinTaskWrapper):
                    if txtask._store_task:
                        txtask.stop()
                else:
                    # Software task (ThreadBasedCyclicSendTask)
                    # These are only in _periodic_tasks if store_task was True
                    txtask.stop(remove_tasks)
            if remove_tasks:
                # Remove stopped tasks from the list
                self._periodic_tasks = [t for t in self._periodic_tasks
                                        if isinstance(t, BmLinTaskWrapper) and not t._store_task]
            with self._lock:
                bmapi.BM_ClearBuffer(self._handle)

    def add_periodic_txtask(self, txtask):
        self._periodic_tasks.append(txtask)

    def del_periodic_txtask(self, txtask):
        self._periodic_tasks.remove(txtask)
        
    def set_filters(self, lin_ids: List[int]):
        """Apply filtering to all messages received by this Bus.

        All messages that match at least one filter are returned.
        If `filters` is `None` or a zero length sequence, all
        messages are matched.

        Calling without passing any filters will reset the applied
        filters to ``None``.
        """
        self._lin_ids = lin_ids or None
        self._apply_filters(self._lin_ids)
    def _apply_filters(self, lin_ids: List[int]):
        if lin_ids:
            if len(lin_ids) >= 1:
                bmfilters = bmapi.BM_RxFilterListTypeDef()
                bmfilters.entries[0].id_value = 0
                bmfilters.entries[0].id_mask = 0
                try:
                    for i in range(len(lin_ids)):
                        filter_id = (filter[i] & 0x3F)
                        bmfilters.entries[0].type = bmapi.BM_RXFILTER_BASIC
                        if filter_id < 32:
                            bmfilters.entries[0].id_value |= ctypes.c_uint32(1 << filter_id)
                        else:
                            bmfilters.entries[0].id_mask |= ctypes.c_uint32(1 << (filter_id -32))
                    bmapi.BM_SetRxFilters(self._handle, ctypes.byref(bmfilters), 1)
                    time.sleep(0.05)
                except BmError as exc:
                    LOG.warning("Could not set filters: %s", exc)
                    # go to fallback
                else:
                    self._is_filtered = True
                    return
            else:
                LOG.warning("Only up to one filter per extended or standard ID allowed")
                # go to fallback

        # fallback: reset filters
        self._is_filtered = False
        try:
            bmfilters = bmapi.BM_RxFilterListTypeDef() # Default as invalid
            # Filter 0: allow all messages to pass
            bmfilters.entries[0].type = bmapi.BM_RXFILTER_BASIC
            bmfilters.entries[0].flags_mask = 0
            bmfilters.entries[0].flags_value = 0
            bmfilters.entries[0].id_mask = 0
            bmfilters.entries[0].id_value = 0
            bmapi.BM_SetRxFilters(self._handle, ctypes.byref(bmfilters), 2)
            time.sleep(0.05)
        except BmError as exc:
            LOG.warning("Could not reset filters: %s", exc)

    
    def filters(self):
        """
        Modify the filters of this bus. See :meth:`~lin.BusABC.set_filters`
        for details.
        """
        return self._lin_ids

    def recv(self, timeout):
        end_time = time.time() + timeout if timeout is not None else None

        bmmsg = bmapi.BM_DataTypeDef()
        channel = ctypes.c_uint32()
        timestamp = ctypes.c_uint32()

        while True:
            try:
                bmapi.BM_Read(self._handle, ctypes.byref(bmmsg))
            except BmError as exc:
                if exc.bm_error_code != bmapi.BM_ERROR_QRCVEMPTY:
                    raise
            else:
                linmsg = ctypes.cast(bmmsg.payload, ctypes.POINTER(bmapi.BM_LinMessageTypeDef))
                msg_id = linmsg.contents.id
                dlc = linmsg.contents.ctrl.DLC
                utcts = ctypes.c_uint64(0)
                status = bmapi.BM_GetDataPtpTimestamp(self._handle, ctypes.byref(bmmsg), ctypes.byref(utcts))
                if bmapi.BM_ERROR_OK != status:
                    utcts.value = bmapi.BM_GetHostPtpTime() 
                timestamp = utcts.value * 1e-9
                channel = bmmsg.header.schn
                checksum = linmsg.contents.ctrl.CHECKSUM
                is_enhanced_checksum = linmsg.contents.ctrl.ENHANCED_CHECKSUM
                msg = Message(
                    timestamp=timestamp,
                    lin_id=msg_id & 0x3F,
                    dlc=dlc,
                    checksum=checksum, is_enhanced_checksum=is_enhanced_checksum,
                    data=linmsg.contents.payload[:dlc],
                    channel=channel)
                return msg


            if end_time is not None and time.time() > end_time:
                return None

            # Wait for receive event to occur
            if timeout is None:
                time_left_ms = INFINITE
            else:
                time_left = end_time - time.time()
                time_left_ms = max(0, int(time_left * 1000))
            bmapi.BM_WaitForNotifications(ctypes.byref(self._notification), 1, time_left_ms)

    def send(self, msg, timeout=None):
        timeoutms = int(timeout*1000) if timeout is not None else -1
        timestamp = ctypes.c_uint32()
        if type(msg) is bmapi.BM_LinMessageTypeDef:
            bmmsg = msg
        else:
            bmmsg = bmapi.BM_LinMessageTypeDef()
            bmmsg.id = msg.lin_id & 0x3F
            bmmsg.ctrl.DLC = msg.dlc
            bmmsg.payload[:msg.dlc] = msg.data
            bmmsg.ctrl.TRANSMIT = 1 if not (msg.msgtype == LIN_MASTER_READ) else 0
            bmmsg.ctrl.ENHANCED_CHECKSUM = 1 if msg.is_enhanced_checksum else 0
            bmmsg.ctrl.CHECKSUM = msg.checksum 
        bmapi.BM_WriteLinMessage(self._handle, ctypes.byref(bmmsg), 0, timeoutms, ctypes.byref(timestamp))
            
    def cancel_send(self):
        bmapi.BM_CancelWrite(self._handle)

    def shutdown(self):
        if self._handle:
            bmapi.BM_Close(self._handle)
        self._handle = bmapi.BM_ChannelHandle()
        
    def reset(self):
        bmapi.BM_Reset(self._handle)

    @property
    def state(self):
        return self._state


    @classmethod
    def enumerate(cls):
        BmLinBus.__init_class__()
        infolist = bmapi.BM_ChannelInfoListTypeDef()
        numOfInfo = ctypes.c_int(len(infolist.entries))
        bmapi.BM_EnumerateByCap(ctypes.byref(infolist), ctypes.byref(numOfInfo), bmapi.BM_LIN_CAP)
        channellist = []
        for i in range(numOfInfo.value):
            channellist.append({
                'index': i,
                'name': infolist.entries[i].name.decode(),
                # Add other exports here
            })
        return channellist