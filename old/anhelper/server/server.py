import logging
from anhelper.vars import Constant, CONST, SHARED_PARAMS_INDEX, SERVER_STATUS, DEVICE_PARAMS_INDEX, ACTION, MESSAGE
loglevel = logging.INFO
logger = logging.getLogger()
logger.setLevel(loglevel)
handler = logging.StreamHandler()
handler.setLevel(loglevel)  # 设置处理器的等级为DEBUG
logger.addHandler(handler)

from multiprocessing import shared_memory
from threading import Thread
import time, os
import numpy as np
import socketman

from anhelper.device import getDevice, listDevices, connectDevice
from anhelper.minicap import getMinicap
from anhelper.minitouch import getMinitouch
from anhelper.ime import getIME


class ServerHeart(Thread):

    def __init__(self, beatfunc, interval = 0.5):
        super().__init__()
        self._beatfunc = beatfunc
        self._interval = interval
        self.stopped = False

    def run(self):
        self.stopped = True
        while(self.stopped):
            self._beatfunc()
            time.sleep(self._interval)

    def stop(self):
        self.stopped = False


class AnhelperServer(Thread):

    def __init__(self):
        super().__init__()
        self.pid = os.getpid()
        self.heart = ServerHeart(beatfunc=self.heartbeat, interval=CONST.heartbeat_interval)
        self.devices_list = None
        self.params = None
        self.connections = {}
        self.devices = {}
        self.deviceparams = {}
        self.caps = {}
        self.imes = {}
        self.touchs = {}
        self.frames = {}
        self.frames_sm = {}
        self.websocket = None
        self.stopped = False
        self.minport = CONST.baseport

    def initParams(self):
        params = [None for i in range(len(SHARED_PARAMS_INDEX))]
        params[SHARED_PARAMS_INDEX.HEARTBEATTIME] = time.time()
        params[SHARED_PARAMS_INDEX.SERVERPID] = self.pid
        self.devices_list = listDevices()
        params[SHARED_PARAMS_INDEX.NUMOFDEVICES] = len(self.devices_list)
        params[SHARED_PARAMS_INDEX.SERVERSTATUS] = SERVER_STATUS.starting
        return params

    def i_am_ntr(self):
        try:
            shared_params = shared_memory.ShareableList(name=CONST.shared_params)
            logger.warning("shared param list already exists")
            if (time.time() - shared_params[SHARED_PARAMS_INDEX.HEARTBEATTIME] < CONST.heartbeat_interval*2):
                # and (self.pid > shared_params[SHARED_PARAMS_INDEX.SERVERPID])
                logger.error("I am NTR!!!")
                return True
            else:
                shared_params.shm.unlink()
                return False
        except:
            return False

    def heartbeat(self):
        self.params[SHARED_PARAMS_INDEX.HEARTBEATTIME] = time.time()

    def initDeviceParams(self, dname):
        logger.info("Initializing device params for device: " + dname)
        device = self.devices[dname]
        params = [None for i in range(len(DEVICE_PARAMS_INDEX))]
        params[DEVICE_PARAMS_INDEX.NAME] = dname
        params[DEVICE_PARAMS_INDEX.ACTIONPORT] = self.params[SHARED_PARAMS_INDEX.ACTIONPORT]
        params[DEVICE_PARAMS_INDEX.FRAMENAME] = CONST.get_shared_frame_name(dname)
        whd = device.getWM()
        orientation = device.getOrientation()
        params[DEVICE_PARAMS_INDEX.WIDTH] = whd['width']
        params[DEVICE_PARAMS_INDEX.HEIGHT] = whd['height']
        params[DEVICE_PARAMS_INDEX.ORIENTATION] = orientation
        params[DEVICE_PARAMS_INDEX.CAPSERVER] = False
        params[DEVICE_PARAMS_INDEX.IMESERVER] = False
        params[DEVICE_PARAMS_INDEX.TOUCHSERVER] = False
        return params


    def ensureDevice(self, name):
        logger.info("Ensuring device %s", name)
        if name in self.devices:
            logger.info("Device %s already exists", name)
            return self.devices[name]
        self.devices[name] = getDevice(name)
        dparams = self.initDeviceParams(name)
        sdname = CONST.get_shared_device_name(name)
        # todo 应该先清除原有的共享内存区域，再创建新的
        logger.info("Creating shared memory for device %s, %s", name, sdname)
        try:
            self.deviceparams[name] = shared_memory.ShareableList(
                sequence = dparams ,
                name = sdname
                )
        except Exception as e:
            logger.error("Failed to create shared memory for device %s, %s", name, e)
            try:
                self.deviceparams[name] = shared_memory.ShareableList(
                    name=sdname
                    )

                for i in range(len(dparams)):
                    self.deviceparams[name][i] = dparams[i]

            except Exception as e:
                logger.error("Failed to connect shared memory for device %s, %s", name, e)
                raise RuntimeError(e)
        logger.info("Created shared memory for device %s", name)
        return self.devices[name] # 返回deviceparams
    
    def ensureime(self, dname):
        logger.info("ensure ime")
        if dname in self.imes:
            logger.info("IME server for device %s already exists", dname)
            return 
        self.imes[dname] = getIME(dname)
        self.deviceparams[dname][DEVICE_PARAMS_INDEX.IMESERVER] = True
        logger.info("Created IME server for device %s", dname)

    def ensurecap(self, dname):
        self.ensureDevice(dname)
        if dname in self.frames:
            return
        if dname not in self.caps:
            cap = getMinicap(dname, port=self.minport) # 多设备避免端口冲突
            self.minport += 1
            logger.info("Created minicap for device %s", dname)
            self.caps[dname] = cap
        else:
            cap = self.caps[dname]
        sampleimg = cap.cap()
        logger.info("sample ready")

        sfname = CONST.get_shared_frame_name(dname)
        sfsize = sampleimg.nbytes
        sfdtype = sampleimg.dtype
        logger.info("sfname: %s", sfname)
        # todo:向客户端发送sampleimg
        
        try:
            sm = shared_memory.SharedMemory(
                name=sfname,
                create=False #,
                #size=sfsize
                )
            sm.close()
            sm.unlink()
        except:
            pass
        logger.info("Clear shared frame for device %s", dname)
        sm = shared_memory.SharedMemory(
                name=sfname,
                create=True,
                size=sfsize
                )
        self.frames_sm[dname] = sm
        logger.info(f"Created shared memery with size{sfsize}")
        self.frames[dname] = np.ndarray(
                shape=sampleimg.shape,
                dtype=sfdtype,
                buffer=sm.buf)
        logger.info("Created shared frame for device %s", dname)
        cap.setIMatBuffer(self.frames[dname])
        logger.info("Set cap buffer for device %s", dname)
        self.deviceparams[dname][DEVICE_PARAMS_INDEX.FRAMESIZE] = sfsize
        self.deviceparams[dname][DEVICE_PARAMS_INDEX.HEIGHT] = sampleimg.shape[0]
        self.deviceparams[dname][DEVICE_PARAMS_INDEX.WIDTH] = sampleimg.shape[1]
        self.deviceparams[dname][DEVICE_PARAMS_INDEX.COLORBYTES] = sampleimg.shape[2]
        self.deviceparams[dname][DEVICE_PARAMS_INDEX.FRAMENAME] = sfname
        self.deviceparams[dname][DEVICE_PARAMS_INDEX.CAPSERVER] = True
        logger.info(f"device params ready: {self.deviceparams[dname]}")
        # todo 分配抓图共享内存
        return sampleimg
    
    def ensuretouch(self, dname):
        if dname in self.touchs:
            return 
        self.touchs[dname] = getMinitouch(dname)
        self.deviceparams[dname][DEVICE_PARAMS_INDEX.TOUCHSERVER] = True
        logger.info(f"minitouch ready for {dname}")

    def doAction(self, action, param, conn):
        #logger.warning("war_doAction: %s, %s, %s" % (action, param, conn))
        logger.info("doAction: %s, %s, %s" % (action, param, conn))   
        action = int(action) # debug: json包将key部分int型变成字符串
        #logger.info(f"typeof action: {type(action)}, is listdevice{action==ACTION.listdevice} {ACTION.listdevice==action} {int(ACTION.listdevice)==action}" )
        if action==ACTION.setdevice:
            logger.info("do action setdevice")
            dname = param
            self.connections[conn]['device'] = dname
            device = self.ensureDevice(dname)
            #deviceparams = self.deviceparams[name]
            sdname = CONST.get_shared_device_name(dname)
            conn.send({MESSAGE.shared_device_params_name: sdname})

        elif action==ACTION.listdevice:
            logger.info("do action listdevice")
            self.devices_list = listDevices()
            self.params[SHARED_PARAMS_INDEX.NUMOFDEVICES] = len(self.devices_list)
            msg = {MESSAGE.device_list: self.devices_list}
            logger.info(f"listdevice:{msg}")
            conn.send(msg)

        else:
            
            # deviceparamsname = ? 如何标识设备 用adb提供的设备名
            dname = self.connections[conn].get('device')
            if dname not in self.devices:
                if dname is None:
                    txt = "未指定设备"
                else:
                    txt = f"不存在名为{name}的设备"
                logger.error(txt)
                conn.send({MESSAGE.error:txt})
                return

            if action in [ACTION.ensurecap, ACTION.callcapserver]:
                logger.info(f'do ensure cap')
                self.ensurecap(dname)
            elif action == ACTION.getframe: # todo 由于websockets发送包大小限制导致无法发送max_size: 'Optional[int]' = 1048576
                logger.info(f'do getframe')
                self.ensurecap(dname)
                if dname not in self.caps:
                    logger.error(f'{dname}未启动cap进程')
                else:
                    # 为了避免过大的包仅发送一个黑屏样本
                    blacksample = self.caps[dname].cap().copy()
                    blacksample[:,:,:] = 0
                    conn.send({MESSAGE.frame:blacksample})
            
            elif action == ACTION.callimeserver:
                logger.info(f'do callimeserver')
                self.ensureime(dname)

            elif action == ACTION.ime:
                logger.info(f'do ime send')
                txt = param
                self.imes[dname].input(txt)

            elif action == ACTION.calltouchserver:
                logger.info(f'do calltouchserver')
                self.ensuretouch(dname)

            elif action == ACTION.press:
                logger.info(f'do press {param}')
                self.ensuretouch(dname)
                with self.touchs[dname].useContact() as c:
                    logger.info(f'do press {param[:2]}')
                    c.tap(*param[:2])

            else:
                logger.warning("unknown action: %s" % action)
            pass
        #todo：

    def connHandler(self, msg, conn):
        logger.warning(f'{time.time()}:{conn}收到消息{msg}')
        if not(isinstance(msg,dict)):
            logger.error(f'接收到非字典类{type(msg)},{msg}')
            raise RuntimeError(f'接收到非字典类{msg}')
        #logger.info('check conn')
        if not(conn in self.connections):
            self.connections[conn] = {}
        #logger.info('check action')
        for k,v in msg.items():
            self.doAction(k,v, conn)

    def run(self):
        if self.i_am_ntr():
            return
        try:
            self.params = shared_memory.ShareableList(
                sequence = self.initParams() ,
                name=CONST.shared_params
                )
        except:

            try:
                self.params = shared_memory.ShareableList(
                    name=CONST.shared_params
                    )
                params = self.initParams()
                for i in range(len(params)):
                    self.params[i] = params[i]

            except Exception as e:
                raise RuntimeError(e)


        self.heart.start()
        self.websocket = socketman.createServer(port=CONST.actionport, onrecv=self.connHandler)
        self.params[SHARED_PARAMS_INDEX.ACTIONPORT] = CONST.actionport
        self.params[SHARED_PARAMS_INDEX.SERVERSTATUS] = SERVER_STATUS.running
        logger.warn(f'服务参数:\n{self.params}')
        while not(self.stopped):
            time.sleep(1)
        self.websocket.close()
        self.params[SHARED_PARAMS_INDEX.SERVERSTATUS] = SERVER_STATUS.stopped
        # todo 创建websocket端口（websocket连接时需要绑定连接的设备，不可更改/client端相应代码需要修改）
        # todo 循环，检测已连接设备，并监听每个设备的状态、截图和处理控制信息








