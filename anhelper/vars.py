from enum import IntEnum
import numpy as np

class Constant:
    def __setattr__(self, name, value):
        if name in self.__dict__:
            raise AttributeError(f"{name} is a constant and cannot be changed.")
        super().__setattr__(name, value)


class SERVER_STATUS(Constant):
    running = 0
    stopped = 1
    noserver = 2
    starting = 3

class SHARED_PARAMS_INDEX(IntEnum):
    HEARTBEATTIME = 0
    SERVERPID = 1
    SERVERSTATUS = 2
    NUMOFDEVICES = 3
    ACTIONPORT = 4

class DEVICE_PARAMS_INDEX(IntEnum):
    ID = 0
    ONLINE = 1
    PRODUCT = 2
    MODEL = 3
    NAME = 4
    ADBID = 5
    WIDTH = 6
    HEIGHT = 7
    COLORBYTES = 8
    #ROTATION = 9
    FRAMESIZE = 10
    ACTIONPORT = 11
    CAPSERVER = 12
    TOUCHSERVER = 13
    IMESERVER = 14
    FRAMENAME = 15
    ORIENTATION = 16
    FRAMESHAPE = 17

class ACTION(Constant):
    touchdown = 0
    touchup = 1
    callcapserver = 2
    calltouchserver = 3
    callimeserver = 4
    ime = 5
    adb = 6
    shell = 7
    press = 8
    move = 9
    moveto = 10
    setdevice = 11
    handshake = 12
    ensurecap = 13
    ensureime = 14
    ensuretouch = 15
    listdevice = 16
    getframe = 17

class MESSAGE(Constant):
    shared_device_params_name = 0
    handshake = 1
    device_list = 2
    device_params = 3
    error = 4
    frame = 5



class CONST(Constant):
    shared_tag = "anhelper_shared_"
    shared_frame_head  = shared_tag + "frame_"
    shared_trace_head  = shared_tag + "trace_"
    shared_params = shared_tag + "params"
    shared_device_head = shared_tag + "device_"
    '''
    shared_params:[heartbeat_timestamp, serverpid, server_status, numofdevices]
    '''
    heartbeat_interval = 0.5
    waitserver_timeout = 10
    frame_data_type = np.uint8
    actionport = 5012
    baseport = 15530

    @staticmethod
    def get_shared_device_name(devicename):
        return CONST.shared_device_head + str(devicename)

    @staticmethod
    def get_shared_frame_name(devicename):
        return CONST.shared_frame_head + str(devicename)

    @staticmethod
    def shared_device(device_id):
        '''
        连接的安卓设备参数[id,w,h, colorbytes,rotation, framesize, actionport]
        '''
        return CONST.shared_device_head + str(device_id)

    @staticmethod
    def shared_frame(device_id):
        '''
        获取的画面帧
        '''
        return CONST.shared_frame_head + str(device_id)

    @staticmethod
    def shared_trace(device_id):
        '''
        操作跟踪
        '''
        return CONST.shared_trace_head + str(device_id)
