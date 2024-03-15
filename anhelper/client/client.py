import logging
from ..vars import Constant, CONST, SHARED_PARAMS_INDEX, SERVER_STATUS, DEVICE_PARAMS_INDEX, ACTION, MESSAGE
loglevel = logging.INFO
logger = logging.getLogger()
logger.setLevel(loglevel)
handler = logging.StreamHandler()
handler.setLevel(loglevel)  # 设置处理器的等级为DEBUG
logger.addHandler(handler)
from multiprocessing import shared_memory
from threading import Thread
import time
import numpy as np
import socketman

_serverprocess = None

def createServer():
    global _serverprocess
    import subprocess
    # todo:
    logger.warning('starting server')
    try:
        #_serverprocess = subprocess.Popen(['python', '-m', 'anhelper.server'])
        _serverprocess = subprocess.Popen(['python', '-m', 'anhelper.server']) # debug todo
    except Exception as e:
        logger.error(e)
    pass

def waitUntilTimeout(getter:callable, timeout:float=10, discription=''):
    t0 = time.time()
    while(not(getter())):
        time.sleep(0.1)
        if time.time() - t0>timeout:
            logger.error(f'wait timeout:{discription}')
            raise RuntimeError(f'timeout:{discription}')
            return


class WatcherStatus(Constant):
    inited = 'watcher inited'
    starting = 'watcher starting'
    nobeat = 'watcher no heartbeat'
    beating = 'beating'
    waitserver = 'waiting server'
    servertimeout = 'server timeout'

class ClientWatcher(Thread):
    # 监听server的heatbeat状态
    def __init__(self) -> None:
        super().__init__()
        self.status = WatcherStatus.inited
        self.lastchecktime = 0
        self.shared_params = None
        self.stopped = True
        self.setwaitflag = False

    @property
    def lastheartbeattime(self):
        if self.shared_params is not None:
            try:
                return self.shared_params[SHARED_PARAMS_INDEX.HEARTBEATTIME]
            except:
                return None

    @property
    def server_status(self):
        if self.shared_params is not None:
            try:
                return self.shared_params[SHARED_PARAMS_INDEX.SERVERSTATUS]
            except:
                return SERVER_STATUS.noserver

    def heartbeatCheck(self):
        checktime  = time.time()
        if self.status == WatcherStatus.waitserver:
            if checktime - self.lastheartbeattime > CONST.waitserver_timeout:
                logger.info('server timeout')
                self.status = WatcherStatus.servertimeout
            elif self.shared_params[SHARED_PARAMS_INDEX.SERVERSTATUS] == SERVER_STATUS.running:
                self.status = WatcherStatus.beating
            else:
                return
        if self.lastheartbeattime is None and self.status == WatcherStatus.beating:
            self.status = WatcherStatus.nobeat
        elif  checktime - self.lastheartbeattime < CONST.heartbeat_interval*2:
            self.status = WatcherStatus.beating
        else:
            self.status = WatcherStatus.nobeat
        self.lastchecktime = checktime

    def setwait(self):
        self.setwaitflag = True

    def run(self) -> None:
        logger.info("Dog is running")
        self.stopped = False
        while not(self.stopped):
            if self.setwaitflag:
                self.setwaitflag = False
                self.status = WatcherStatus.waitserver
            if self.lastheartbeattime is None:
                logger.info("waiting for lastheartbeattime")
                try:
                    self.shared_params = shared_memory.ShareableList(name=CONST.shared_params)
                except:
                    if self.status != WatcherStatus.waitserver:
                        self.status = WatcherStatus.nobeat
            else:
                self.heartbeatCheck()
            if self.status == WatcherStatus.nobeat:
                logger.warning("Dog is not beating")
            else:
                pass
                #logger.debug("Dog is beating")
            time.sleep(CONST.heartbeat_interval)

    def stop(self) -> None:
        self.stopped = True
    def __del__(self):
        self.stop()
        super.__del__()

watcher = ClientWatcher()

class Client:
    def __init__(self, devicename=None, ensure=True) -> None:
        self.__frame_sm = None
        self.frame = None # 共享画面
        self.frame_sample = None
        self.__trace_sm = None
        self.__trace = None
        self.deviceparams = None
        self.conn = None # 输入推送
        self.devicename = devicename
        self.__messagecache = None
        from threading import Condition
        self.__wait_message_condition = Condition()
        self.__wait_message_flag = False
        if ensure:
            self.ensure()


    def wait_message(self, message_type=None):
        self.__wait_message_flag = True
        with self.__wait_message_condition:
            self.__wait_message_condition.wait()
        self.__wait_message_flag = False
        pass # 服务返回特定消息
        # todo timeout

    def askfor(self, msg):
        self.conn.send(msg)
        self.wait_message()
        return self.__messagecache

    def ensure_device(self) -> None:
        if self.deviceparams is not None:
            logger.warning("不能重复绑定设备")
            return
        self.ensure_connection()
        if self.devicename is None:
            devicelist = self.askfor({ACTION.listdevice:0})
            #devicelist = msg.get(MESSAGE.device_list)
            if not(isinstance(devicelist, dict)) or len(devicelist)<=0:
                raise RuntimeError("没有检测到安卓设备连接")
            self.devicename = list(devicelist.keys())[0]
            logger.warning(f'未指定设备，默认连接第一个android设备：{self.devicename}')
        deviceparamsname = self.askfor({ACTION.setdevice: self.devicename})
        #deviceparamsname = CONST.get_shared_device_name(dname)
        if deviceparamsname==None:
            raise RuntimeError("指定设备{self.devicename}无法连接")
            # todo: 设备无法连接后尝试连接第一个设备
        try:
            self.deviceparams = shared_memory.ShareableList(name=deviceparamsname)
            logger.info(f'成功连接设备{self.devicename}：{self.deviceparams}')
        except:
            logger.warning("Device %s is not exist" % self.devicename)
            raise RuntimeError("Device %s is not exist" % self.devicename)
        #if not(self.deviceparams[DEVICE_PARAMS_INDEX.ONLINE]):
        #    logger.warning(f'设备{self.devicename}不在线')


    def ensure_cap(self):
        if self.deviceparams[DEVICE_PARAMS_INDEX.CAPSERVER] and (self.frame is not None):
            return True
        self.ensure_device()
        self.conn.send({ACTION.callcapserver:True})
        waitUntilTimeout(
            getter=lambda :self.deviceparams[DEVICE_PARAMS_INDEX.CAPSERVER],
            discription="wait for cap server"
            )
        logger.info("等待帧样本")
        self.frame_sample = self.askfor({ACTION.getframe:True})
        sfname = self.deviceparams[DEVICE_PARAMS_INDEX.FRAMENAME]
        sfsize = self.frame_sample.nbytes
        logger.info(f'{self.devicename} 共享内存名：{sfname} 大小：{sfsize}')
        try:
            self.__frame_sm = shared_memory.SharedMemory(
                name=sfname ,
                create=False,
                size=sfsize)
            logger.info(f'{self.devicename} 共享内存已连接')
            self.frame = np.ndarray(
                shape=self.frame_sample.shape,
                dtype=self.frame_sample.dtype,
                buffer=self.__frame_sm.buf)
            logger.info(f'{self.devicename} 共享内存已映射')
            self.frame.flags.writeable = False
        except:
            logger.warning("Frame %s is not exist" % self.deviceparams[DEVICE_PARAMS_INDEX.FRAMENAME])
        # todo: bind trace
        pass
        return True

    def ensure_touch(self):
        if self.deviceparams[DEVICE_PARAMS_INDEX.TOUCHSERVER]:
            return True
        self.ensure_device()
        self.conn.send({ACTION.calltouchserver:True})
        waitUntilTimeout(
            getter=lambda :self.deviceparams[DEVICE_PARAMS_INDEX.TOUCHSERVER],
            discription="wait for cap server"
            )
        return True

    def ensure_ime(self):
        if self.deviceparams[DEVICE_PARAMS_INDEX.IMESERVER]:
            return True
        self.ensure_device()
        self.conn.send({ACTION.callimeserver:True})
        waitUntilTimeout(
            getter=lambda :self.deviceparams[DEVICE_PARAMS_INDEX.IMESERVER],
            discription="wait for cap server"
            )
        return True

    def ensure_server(self) -> None:
        # ensure server
        global watcher
        if not(watcher.is_alive()):
            watcher.start()
        starttime = time.time()
        while(watcher.status != WatcherStatus.beating):
            if watcher.status == WatcherStatus.nobeat:
                logger.warning("Dog is not beating start server")
                createServer()
                watcher.setwait()
            elif time.time() - starttime > CONST.waitserver_timeout:
                logger.error("wait server timeout")
                raise Exception("wait server timeout")
            elif watcher.status == WatcherStatus.waitserver:
                logger.info("Dog is beating wait server")
            else:
                logger.error(f"status: {watcher.status}")
            time.sleep(CONST.heartbeat_interval)

    def ensure_connection(self) -> None:
        self.ensure_server()
        if self.conn is not None:
            logger.warning("Connection is exist")
            return
        def handle_recv(msg, conn):
            if not(isinstance(msg,dict)):
                raise RuntimeError(f'服务器返回非字典类{msg}')
            for k,v in msg.items():
                if k==MESSAGE.handshake:
                    # todo: notification
                    pass
                    #conn.send({ACTION.setdevice: self.devicename}) # 初次连接绑定设备
                if self.__wait_message_flag: # wait message
                    self.__messagecache = v
                    with self.__wait_message_condition:
                        self.__wait_message_condition.notify()

        global watcher
        self.conn = socketman.connect(
            uri = f"ws://127.0.0.1:{watcher.shared_params[SHARED_PARAMS_INDEX.ACTIONPORT]}",
            onrecv=handle_recv
            )

        pass

    def ensure(self):
        self.ensure_device()

    def close(self):
        if self.conn is not None:
            self.conn.close()
        if self.__frame_sm is not None:
            self.__frame_sm.close()
        if self.__trace_sm is not None:
            self.__trace_sm.close()

    def __del__(self):
        self.close()
        super.__del__()

    def cap(self):
        self.ensure_cap()
        return self.frame

    def imesend(self, txt):
        self.ensure_ime()
        self.conn.send({ACTION.ime:txt})

    def adb(self, cmd):
        self.ensure_device()
        self.conn.send({ACTION.adb:cmd})

    def shell(self, cmd):
        self.ensure_device()
        self.conn.send({ACTION.shell:cmd})

    def touch(self, px, py, action=ACTION.press, contactid=0, pressure=None):
        # px,py为屏幕坐标比例[0,1]
        self.ensure_touch()
        self.conn.send({ACTION.press:[px, py, action, contactid, pressure]})


    # todo conn.callback, contact*
