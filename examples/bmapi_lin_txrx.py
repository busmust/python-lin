from lin.interfaces.bmlin import BmLinBus
from lin.message import Message
from lin.message import LIN_RECEIVE, LIN_MASTER_WRITE, LIN_MASTER_READ, LIN_SLAVE_WRITE
import sys
import time

def send_one(bus, msg):
    bus.send(msg, timeout=1.0)
    print(f'send  {msg}')

def send_periodic(bus, msg):
    return bus.send_periodic(msg, 0.1)
# /**
#  * @brief BMAPI test program: Transmit or receive messages according to command line arguments:
#  * @param[in]  argc    Number of command line arguments
#  * @param[in]  argv[0] Path of this program
#  * @param[in]  argv[1] Channel: Selected port index
#  * @param[in]  argv[2] Mode(master/slave)-MsgType(receive/write/read)-SendType(txtask/bmwrite)
#  * @return     Program exit code
#  */
if __name__ == '__main__':    
    channel = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    mode = sys.argv[2] if len(sys.argv) > 2 else "master-write-txtask"
    ismaster = 1 if "master" in mode else 0
    bus = BmLinBus(channel=channel, is_master=ismaster, bitrate=19200, pullup=True)
    print(f'Open BUSMUST Lin channel {channel} {mode} using 19200 baudrate ...')
    msgtype = LIN_RECEIVE
    if ismaster:
        if "write" in mode:
            msgtype = LIN_MASTER_WRITE
        elif "read" in mode:
            msgtype = LIN_MASTER_READ
    else:
        if "write" in mode:
            msgtype = LIN_SLAVE_WRITE
    if msgtype:
        msg = Message(lin_id=0x3, is_enhanced_checksum=False, msgtype=msgtype, data=bytes([0x90, 0x80, 10, 11, 12, 13, 14, 15]))
        if "-txtask" in mode :
            txtask = send_periodic(bus, msg)
            print('Start sending')
            while True:
                try:
                    msg = bus.recv(1)
                    if msg is not None:
                        print(msg)
                except KeyboardInterrupt:
                    txtask.stop()
                    print('Stop sending')
                    break
        else:
            send_one(bus, msg)
    else:
        print('Start receiving')
        while True:
            try:
                msg = bus.recv(1)
                if msg is not None:
                    print(msg)
            except KeyboardInterrupt:
                break
