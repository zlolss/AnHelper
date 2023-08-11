
import os
from . import device, common
import threading, time, cv2
import socket
import numpy as np

_minicaps={}

# todo: 
#   传输数据损坏或长时间无数据更新时需要重启
#   设备离线时需要停止服务


class CONST:
    JPG = 0
    IMG = 1
    CV2 = 2
    PACKAGEDIR = os.path.dirname(os.path.abspath(__file__))
    PREBUILDDIR = os.path.join(PACKAGEDIR,'prebuild/minicap/')
    DEFAULTPARAMS = { 'port': 15534, 'maxfps':15, 'jpeg_quality':80, 
                    'cache_size':60, 'cache_types':[JPG]}
    
    
    
def getMinicap(device_id = None, **params):
    global _minicaps
    
    if device_id in _minicaps:
        _minicaps[device_id].updateParams(**params)
        return _minicaps[device_id]
        
    device_id = device.getDevice(device_id).id    
    if device_id in _minicaps:
        _minicaps[device_id].updateParams(**params)
        return _minicaps[device_id]
        
    newcap = _Minicap(device_id, **params)
    _minicaps[device_id] = newcap
        
    return _minicaps[device_id]
    

    
class _Client(threading.Thread):

    def __init__(self, device_id, port, cache_size=30, cache_types = [CONST.JPG, CONST.CV2]):
        super().__init__()
        self.id = device_id
        self.port = port
        self.buff = b''
        self.header = None
        self.cache = common.Cache(maxsize = cache_size)
        self.cachetypes = cache_types
        self.stopped = True
        self.iserror = False
        self.conn = None
        self.capcount = 0
        self.framecondition = threading.Condition()
        
    def __parseHeader(self):
        HEADLEN = 24
        self.__collectBuff(HEADLEN)
        buff = self.buff
        
        seekl, seekr = 0, HEADLEN
        hbuff = self.buff[seekl:seekr]
        ''' 0 	1 	unsigned char 	Version (currently 1)
        1 	1 	unsigned char 	Size of the headerer (from byte 0)
        2-5 	4 	uint32 (low endian) 	Pid of the process
        6-9 	4 	uint32 (low endian) 	Real display width in pixels
        10-13 	4 	uint32 (low endian) 	Real display height in pixels
        14-17 	4 	uint32 (low endian) 	Virtual display width in pixels
        18-21 	4 	uint32 (low endian) 	Virtual display height in pixels
        22 	1 	unsigned char 	Display orientation
        23 	1 	unsigned char 	Quirk bitflags (see below)'''
        width, height = np.frombuffer(hbuff[14:18],dtype=np.uint32).squeeze(), np.frombuffer(hbuff[18:22],dtype=np.uint32).squeeze()
        rotation = np.frombuffer(hbuff[0:1],dtype=np.uint8).squeeze()
        header = {
            'version': np.frombuffer(hbuff[0:1],dtype=np.uint8).squeeze(),
            'headerer_size': np.frombuffer(hbuff[1:2],dtype=np.uint8).squeeze(),
            'minicap_pid': np.frombuffer(hbuff[2:6],dtype=np.uint32).squeeze(),
            'real_width': np.frombuffer(hbuff[6:10],dtype=np.uint32).squeeze(),
            'real_height': np.frombuffer(hbuff[10:14],dtype=np.uint32).squeeze(),
            'virtual_width': width,
            'virtual_height': height,
            'rotation': rotation,
            'quirk': np.frombuffer(hbuff[0:1],dtype=np.uint8).squeeze(),
            'width': width if rotation==0 else height,
            'height': height if rotation==0 else width
        }
        self.header = header
        self.buff = self.buff[HEADLEN:]
        return header
    
    
    def __collectBuff(self, req_len=0):
        try:
            while len(self.buff)<req_len:
                new_buff = self.conn.recv(req_len)
                self.buff += new_buff
        except:
            pass
        return self.buff
    
    
    def __parseFrame(self):
        self.__collectBuff(4)
        req_len = np.frombuffer(self.buff[:4],dtype=np.uint32).squeeze()
        self.buff = self.buff[4:]
        self.__collectBuff(req_len)
        with self.cache.withnew as newcache:
            
            jpgbuff = self.buff[:req_len]
            
            newcache['ts'] = time.time()
            newcache[CONST.JPG] = jpgbuff
            
            for ctype in self.cachetypes:
                newcache[ctype] = self.decodeJPGBuff(jpgbuff, ctype)
                
            self.buff = self.buff[req_len:]
        
        with self.framecondition:
            self.framecondition.notify_all()
            
    
    def decodeJPGBuff(self, jpgbuff, ctype=CONST.CV2):
        if ctype == CONST.CV2:
            return cv2.imdecode(np.frombuffer(jpgbuff, dtype = np.uint8), cv2.COLOR_RGB2BGR)
            
        elif ctype == CONST.IMG:
            return Image.frombytes('RGB',(self.header['width'],self.header['height']), jpgbuff,'jpeg', 'RGB', 'raw')
        elif ctype == CONST.JPG:
            return jpgbuff
    
    
    def cap(self, captype = CONST.CV2, sync=False):
        if sync or self.capcount<=0:
            with self.framecondition:
                self.framecondition.wait(timeout=1.)
        with self.cache.withlatest as cache:
            self.capcount += 1
            capcache = cache.get(captype, None)
            if capcache is not None:
                return capcache
            jpgcache = cache.get(CONST.JPG, None)
            if jpgcache is not None:
                return self.decodeJPGBuff(jpgcache, captype)
        return None
        
    
    def run(self):
        self.stopped = False
        # todo 重复打开端口错误
        self.conn = socket.socket()
        self.conn.connect(('127.0.0.1',self.port)) 
        # todo 判断端口是否正确连接并采取相应措施
        self.__parseHeader()
        
        while not(self.stopped):
            self.__parseFrame()
            
        self.conn.close()
        
        
    def stop(self):
        self.stopped = True
        self.conn.shutdown(socket.SHUT_RDWR)
        '''
        socket.shutdown(how)
        关闭一半或全部的连接。如果 how 为 SHUT_RD，则后续不再允许接收。如果 how 为 SHUT_WR，则后续不再允许发送。如果 how 为 SHUT_RDWR，则后续的发送和接收都不允许。
        '''
        self.join()
        
        
    
class _Minicap:
    
    
    def __init__(self, device_id=None, autorotation=True, **params):
        self.device = device.getDevice(device_id)
        self.id = self.device.id
        self.params = dict(CONST.DEFAULTPARAMS, **params)
        self.isinstalled = False
        self.isensured = False
        self.server = None
        self.autorotation = autorotation
        self.orientation = None
        self.screensize = None
        self.client = None
        self.stopping = False
        if autorotation:
            self.device.supervisorAdd('Orientation')
        
        
    def install(self, fix_mumu=True):
        if self.isinstalled:
            return self.params['remote_bin_path'], self.params['remote_dir']
        print('正在部署minicap。。。', end='')
        dev = self.device
        self.__stopServer()
        abi = dev.abi
        sdk = dev.sdk
        if fix_mumu and sdk == 32 and abi == "x86_64":
            abi = "x86"
        binName = 'minicap' if int(sdk)>=16 else 'minicap-nopie'
        libName = 'minicap.so'
        binPath = os.path.join(CONST.PREBUILDDIR, f'{abi}/bin/{binName}')
        libPath = os.path.join(CONST.PREBUILDDIR, f'{abi}/lib/android-{sdk}/{libName}')
        remoteDir = dev.tmpdir
        remoteBinPath = dev.pushTmp(binPath)
        dev.pushTmp(libPath)
        dev.shell(f'chmod 777 {remoteBinPath}')
        self.params['remote_bin_path'] = remoteBinPath
        self.params['remote_dir'] = remoteDir
        print('ok')
        self.isinstalled = True
        return remoteBinPath, remoteDir
    
    
    def updateParams(self, **params):
        thesame = [v==self.params.get(k,None) for k,v in params.items()]
        if len(thesame)>0 and not all(thesame):
            self.params = dict(self.params, **params)
            self.restart()
    
    
    @property
    def isServerRun(self):
        return self.server and self.server.poll() is None
        
    
    def start(self):
        self.__startServer()
        self.__startClient()
        
        
    def stop(self):
        # 同时只能执行一个关闭过程
        if self.stopping:
            if self.server is not None:
                self.server.wait()
            self.stopping = False
            return
            
        self.stopping = True
        self.__stopClient()
        self.__stopServer()
        self.stopping = False
        
    def close(self):
        self.stop()
        
        
    def restart(self):
        self.stop()
        self.start()
        
    
    def cap(self, captype=CONST.CV2, sync = False):
        if self.stopping:
            self.server.wait()
        if self.autorotation and self.device.supervisor.params['Orientation']!=self.orientation:
            self.restart()
        if self.client is None or not(self.client.is_alive()):
            self.start()
        return self.client.cap(captype, sync)
    
    
    def __startClient(self):
        if self.client is not None and self.client.is_alive():
            return 
        self.client = _Client(self.id, self.params['port'], self.params['cache_size'], cache_types = self.params['cache_types'])
        self.client.start()
        
        
    def __stopClient(self):
        if self.client is None or not(self.client.is_alive()):
            return
        #self.client.stopped = True
        self.client.stop()
        #self.client.join()
    

    def __stopServer(self):
        self.device.shell('pkill minicap')
        if self.server is None:
            return
        self.server.terminate()
        self.server.wait()
    
    
    def __startServer(self):
        if self.isServerRun:
            return 
        remoteBinPath, remoteDir = self.install()
        self.orientation = self.device.getOrientation()
        rotation = self.orientation*90
        self.screensize = self.device.getWMSize()
        screenSize = '%dx%d'%(self.screensize['width'], self.screensize['height'])
        maxfps = self.params['maxfps']
        jpegQuality = self.params['jpeg_quality']
        port = self.params['port']
        cmd = f'LD_LIBRARY_PATH={remoteDir} {remoteBinPath} -P {screenSize}@{screenSize}/{rotation} -r {maxfps} -Q {jpegQuality}'

        self.server = self.device.shell(cmd, readout=False)
        
        while True:
            if 'jpg encoder' in self.server.stderr.readline().decode().lower():
                break
                
        self.device.adb(f'forward tcp:{port} localabstract:minicap')
        
      