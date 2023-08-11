from . import device
import os, threading, socket, subprocess, time


_minitouches = {}


class CONST:
    PACKAGEDIR = os.path.dirname(os.path.abspath(__file__))
    PREBUILDDIR = os.path.join(PACKAGEDIR,'prebuild/minitouch/')
    DEFAULTPARAMS = { 'port': 15544, 'frq':120}
    COMMIT = 'c'
    RESETALL = 'r'
    TOUCHUP = 'u'
    TOUCHDOWN = 'd'
    TOUCHMOVE = 'm'
    WAIT = 'w'
                    

def getMinitouch(device_id = None, **params):
    global _minitouches
    
    if device_id in _minitouches:
        _minitouches[device_id].updateParams(**params)
        return _minitouches[device_id]
        
    device_id = device.getDevice(device_id).id    
    if device_id in _minitouches:
        _minitouches[device_id].updateParams(**params)
        return _minitouches[device_id]
        
    newtouch = _Minitouch(device_id, **params)
    _minitouches[device_id] = newtouch
        
    return _minitouches[device_id]


class _Client(threading.Thread):

    def __init__(self, device_id, port, max_cache_size=255):
        super().__init__()
        self.id = device_id
        self.port = port
        self.header = None
        self.cache = []
        self.stopped = True
        self.iserror = False
        self.conn = None
        self.condition = threading.Condition()
    

    def __parseHeader(self):
    
        headertext = self.conn.recv(1024).decode('utf-8')
        while len(headertext.split('\n'))<3:
            headertext += self.conn.recv(1024).decode('utf-8')
        _header = {}
        lines = headertext.split('\n')
        #print(lines)
        for line in lines:
            l = line.split()
            if len(l)<=0:
                continue
            if l[0] == 'v':
                _header['version'] = int(l[1])
            elif l[0] == '^':
                _header['max-contacts'] = int(l[1])
                _header['max-x'] = int(l[2])
                _header['max-y'] = int(l[3])
                _header['max-pressure'] = int(l[4])
            elif l[0] == '$':
                _header['pid'] = int(l[1])
        self.header = _header
        return _header

    
    def _sendRaw(self, raw):
        #print(raw)
        return self.conn.send(raw.encode('utf-8'))
        
    
    def xyDecode(self, x, y):
        # 比例坐标转为触控坐标
        if x>=0 and x<=1 and y>=0 and y<=1:
            x, y = x*self.header['max-x'], y*self.header['max-y']
        return int(x), int(y)
    
    def pressureLimit(self, pressure=None):
        pressure = self.header['max-pressure'] if pressure is None or pressure>self.header['max-pressure'] else pressure
        return int(pressure)
    
    def _send(self, head, contact_or_ms=None, x=None, y=None, pressure=None):
        
        #print(f'client_send:{head} {contact_or_ms} {x} {y} {pressure}')
        
        if head in [CONST.COMMIT, CONST.RESETALL]:
            cmd = f'{head}\n'
        elif head in [CONST.WAIT, CONST.TOUCHUP]:
            contact_or_ms = 0 if contact_or_ms is None else contact_or_ms
            cmd = f'{head} {int(contact_or_ms)}\n'
        elif head in [CONST.TOUCHDOWN, CONST.TOUCHMOVE] and x is not None and y is not None:
            pressure = self.pressureLimit(pressure)
            x, y = self.xyDecode(x, y)
            cmd = f'{head} {int(contact_or_ms)} {x} {y} {pressure}\n'
        else:
            return False
        return self._sendRaw(cmd)        
    
    
    def notify(self):
        with self.condition:
            self.condition.notify_all()
    
    
    def send(self, *params):
        # input: head, contact_or_ms, px, py, pressure
        # sample:
        # 'c'
        # 'd', 0, 0.1, 0.1, 50
        self.cache.append(params)
        self.notify()
    
    
    def __sendCache(self):
        
        sendlen = len(self.cache)
        
        for i in range(sendlen):
            self._send(*self.cache[i])
            
        self.cache = self.cache[sendlen:]
        return sendlen
        
    
    def run(self):
        
        # todo 重复打开端口错误
        self.conn = socket.socket()
        self.conn.connect(('127.0.0.1',self.port)) 
        # todo 判断端口是否正确连接并采取相应措施
        
        self.__parseHeader()
        
        self._send(CONST.RESETALL)
        
        self.stopped = False
        
        while not(self.stopped):
            with self.condition:
                self.condition.wait()
            while len(self.cache)>0:
                self.__sendCache()
            
        self.conn.close()
        
    
class _Contact:

    def __init__(self, father, contact_id):
        self.id = contact_id
        self.father = father
        self.islocked = False
        self.isremoved = False
        self.sendcache = []
        self.condition = threading.Condition()
        self.idlecondition = threading.Condition()
        self.framedurationts = 1./father.params['frq']
        self.x = None
        self.y = None
        self.pressed = False
        self.supervisor = threading.Thread(target=self.supervisorThread)
        self.supervisor.start()
        
        
    def __enter__(self):
        self.islocked = True
        return self
        
        
    def __exit__(self, exc_type, exc_value, traceback):
        self.islocked = False
        
    
    @property
    def inuse(self):
        return self.islocked or self.isbusy
    
    
    @property
    def isbusy(self):
        return len(self.sendcache)>0
        
    
    def supervisorThread(self):
        status = ''
        wait_until_ts = None
        while not self.isremoved:
            
            if status == '' and self.isbusy:
                params = self.sendcache[0]
                self.sendcache = self.sendcache[1:]
                
                if params[0]==CONST.WAIT:
                    status = 'wait'
                    wait_until_ts = time.time()+int(params[1])/1000
                
                elif params[0] == CONST.COMMIT:
                    pass
                    
                else:
                    self._send(*params)
                    self._send(CONST.COMMIT)
                    time.sleep(self.framedurationts)
                    
            elif status == 'wait':
                if time.time()>=wait_until_ts:
                    status = ''
                else:
                    time.sleep(self.framedurationts)

            else:
                with self.idlecondition:
                    self.idlecondition.notify_all()
                    
                with self.condition:
                    self.condition.wait()
                
                
    def notify(self):
        with self.condition:
            self.condition.notify_all()
    
    
    def clearCache(self):
        self.sendcache = []
            
        
    def close(self):
        
        self.clearCache()
        with self.idlecondition:
            self.idlecondition.notify_all()
            
        self._send(CONST.TOUCHUP, self.id)
        
        self.islocked = False
        
    
    def remove(self):
        self.isremoved = True
        self.notify()
        self.close()
        self.supervisor.join()
        
    
    def xyEncode(self, x, y):
        return self.father.xyEncode(x, y)
        '''
        if x>1 or y>1:
            screensize = self.father.screensize
            x , y = x/screensize['width'], y/screensize['height']
        return x, y
        '''
        
    def xyLimit(self, x, y):
        x = 1 if x>1 else x
        y = 1 if y>1 else y
        x = 0 if x<0 else x
        y = 0 if y<0 else y 
        return x, y
    
    
    def _send(self, *params):
        # input: head, contact_or_ms, px, py, pressure
        # sample:
        # 'c'
        # 'd', 0, 0.1, 0.1, 50
        if len(params)<=0:
            return
        if len(params)>=4:
            params = list(params)
            params[2:4] = self.xyLimit(*self.xyEncode(*params[2:4]))
        head = params[0]
        if head in [CONST.TOUCHDOWN]:
            self.pressed = True
            self.x , self.y = params[2:4]
        elif head in [CONST.TOUCHMOVE]:
            self.x , self.y = params[2:4]
        elif head in [CONST.RESETALL, CONST.TOUCHUP]:
            self.pressed = False   
        
        #print(params)
        return self.father.send(*params)
    

    def _sendBackground(self, *params):
        self.sendcache.append(params)
        self.notify()
        return len(self.sendcache)
        
        
    def _sendChain(self, chain, background=True):
        for params in chain:
            self._sendBackground(*params)
        self.notify()
        if not(background):
            with self.idlecondition:
                self.idlecondition.wait()
        return True
        #results = [self._send(*params) for params in chain]
        #return all(results)
    
    
    def _updateChain(self, chain, background=True):
        self.clearCache()
        return self._sendChain(chain, background)
    
    
    def down(self, x=None, y=None, pressure=None, background = True):
        if (x is None or y is None):
            if self.x is not None and self.y is not None:
                x, y = self.x, self.y
            else:
                return False
                
        chain = [[CONST.TOUCHDOWN , self.id, x, y, pressure], [CONST.COMMIT]]
        
        return self._updateChain(chain, background)
        
    
    def up(self, background = True):
        
        chain = [[CONST.TOUCHUP , self.id], [CONST.COMMIT]]
        
        return self._updateChain(chain, background)
        
    
    def moveto(self, x, y, pressure=None, background = True ):
    
        chain = [[CONST.TOUCHMOVE ,self.id, x, y, pressure], [CONST.COMMIT]]
        
        return self._updateChain(chain, background)
                
        
    def move(self, offsetx, offsety, pressure=None, background = True):
        if self.x is None or self.y is None:
            return False
            
        offsetx, offsety = self.xyEncode(offsetx, offsety)    
        x, y = self.x+offsetx, self.y+offsety
        
        chain = [[CONST.TOUCHMOVE ,self.id, x, y, pressure], [CONST.COMMIT]]
        
        return self._updateChain(chain, background)
        
    '''    
    def _wait(self, ms=10, background = True):
        
        params = [CONST.WAIT, ms]
        
        if background:
            self._sendBackground(*params)
            self.notify()
            return True
            
        return self._send(*params)
    '''
    
    def tap(self, x, y, pressure=None, duration_ms=50, background = True):
        # 简化点击指令
        chain = [
            [CONST.TOUCHDOWN , self.id, x, y, pressure],
            [CONST.COMMIT],
            [CONST.WAIT, duration_ms],
            [CONST.TOUCHUP , self.id],
            [CONST.COMMIT]
            ]
        
        return self._updateChain(chain, background)        
        
    
    def swipe(self, x1, y1, x2, y2, pressure=None, duration_ms=200, background=True):
        frames = int(duration_ms/1000/self.framedurationts)
        xp = (x2-x1)/frames
        yp = (y2-y1)/frames
        
        chain = [[CONST.TOUCHDOWN , self.id, x1, y1, pressure], [CONST.COMMIT]]
        for i in range(1,frames):
            chain.append([CONST.WAIT, self.framedurationts])
            chain.append([CONST.TOUCHMOVE ,self.id, x1+xp*i, y1+yp*i, pressure])
            chain.append([CONST.COMMIT])
        
        chain.append([CONST.TOUCHUP , self.id])
        chain.append([CONST.COMMIT])
        
        return self._updateChain(chain, background)

    
    
class _Minitouch:
    
    def __init__(self, device_id=None, autorotation=True, **params):
        self.device = device.getDevice(device_id)
        self.id = self.device.id
        self.params = dict(CONST.DEFAULTPARAMS, **params)
        self.isinstalled = False
        self.isensured = False
        self.server = None
        self.client = None
        self.orientation = None
        self.__screensize = None
        self.autorotation = autorotation
        self.contacts = []
        self.stopping = False
        self.default_contact = None
        if autorotation:
            self.device.supervisorAdd('Orientation')
            self.device.supervisorAdd('WMSize')
            
            
    def install(self):
        if self.isinstalled:
            return self.params['remote_bin_path'], self.params['remote_dir']
        print('正在部署minitouch。。。', end='')
        dev = self.device
        self.__stopServer()
        abi = dev.abi
        sdk = dev.sdk
        binName = 'minitouch' if int(sdk)>=16 else 'minitouch-nopie'
        binPath = os.path.join(CONST.PREBUILDDIR, f'{abi}/bin/{binName}')
        remoteDir = dev.tmpdir
        remoteBinPath = dev.pushTmp(binPath)
        dev.shell(f'chmod 777 {remoteBinPath}')
        self.params['remote_bin_path'] = remoteBinPath
        self.params['remote_dir'] = remoteDir
        print('ok')
        self.isinstalled = True
        return remoteBinPath, remoteDir
        
    
    @property
    def isServerRun(self):
        return self.server and self.server.poll() is None
    
    @property
    def screensize(self):
        return self.device.supervisor.params['WMSize'] if self.autorotation else self.__screensize
    
    def start(self):
        self.__startServer()
        self.__startClient()
        self.default_contact = self.useContact()
        
        
        
    def stop(self):
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
        

    def updateParams(self, **params):
        thesame = [v==self.params.get(k,None) for k,v in params.items()]
        if len(thesame)>0 and not all(thesame):
            self.params = dict(self.params, **params)
            self.restart()
    

    def __startClient(self):
        if self.client is not None and self.client.is_alive():
            return 
        self.client = _Client(self.id, self.params['port'])
        self.client.start()
        while self.client.stopped:
            time.sleep(1)
        self.contacts = [_Contact(self, i) for i in range(self.client.header['max-contacts'])]
        
        
    def __stopClient(self):
        if self.client is None or not(self.client.is_alive()):
            return
        for contact in self.contacts:
            contact.remove()
        self.client.stopped = True
        self.client.notify()
        self.client.join()
    

    def __stopServer(self):
        self.device.shell('pkill minitouch')
        if self.server is None:
            return
        self.server.terminate()
        self.server.wait()
    
    
    def __startServer(self):
        if self.isServerRun:
            return 
        remoteBinPath, remoteDir = self.install()
        self.orientation = self.device.getOrientation()
        self.__screensize = self.device.getWMSize()
        port = self.params['port']
        self.server = self.device.shell(remoteBinPath, readout=False)
        while True:
            if 'contacts' in self.server.stderr.readline().decode().lower():
                break        
            # todo: event无写入权限的处理（需要root）    
        self.device.adb(f'forward tcp:{port} localabstract:minitouch')
        
    
    def xyEncode(self, x, y):
        # 统一为比例坐标
        # 输入坐标使用比例坐标，或按照屏幕分辨率而非触控分辨率
        orientation = self.device.supervisor.params['Orientation'] if self.autorotation else self.orientation
        if x>1 or y>1:
            if orientation in [1,3]:
                x , y = x/self.screensize['height'], y/self.screensize['width']
            else:
                x , y = x/self.screensize['width'], y/self.screensize['height']
        
        return x, y
    

    def xyTransform(self, x, y):
        # 输入比例坐标
        # 使屏幕左上角始终为坐标原点
        # orientation*90为屏幕顺时针旋转度数
        orientation = self.device.supervisor.params['Orientation'] if self.autorotation else self.orientation
        
        if orientation == 1:
            x, y = 1-y, x
            
        elif orientation == 2:
            x, y = 1-x, 1-y 
            
        elif orientation ==3:
            x, y = y, 1-x
        
        return x, y
    
        
    def ensure(self):
        if self.client is None or not(self.client.is_alive()):
            self.restart()
        
    def send(self, *params):
        # input: head, contact_or_ms, px, py, pressure
        # sample:
        # 'c'
        # 'd', 0, 0.1, 0.1, 50
        self.ensure()
        if len(params)>=4:
            params = list(params)
            params[2:4] = self.xyTransform(*self.xyEncode(*params[2:4]))
        return self.client.send(*params)
    
    
    def useContact(self, cid=None):
        self.ensure()
        if cid is not None:
            return self.contacts[cid]
        for contact in self.contacts[::-1]:
            if not(contact.inuse):
                contact.islocked = True
                return contact
        print('所有contact均被占用，请使用with ... as 或 使用后close()以释放')
        return None
    
    
    def down(self, x=None, y=None, pressure=None, background = True):
        self.ensure()
        return self.default_contact.down(x=x, y=y, pressure=pressure, background=background)

        
    
    def up(self, background = True):
        
        return self.default_contact.up(background=background)
        
    
    def moveto(self, x, y, pressure=None, background = True ):
    
        return self.default_contact.moveto(x=x, y=y, pressure=pressure, background=background)
                
        
    def move(self, offsetx, offsety, pressure=None, background = True):
    
        return self.default_contact.move(x=offsetx, y=offsety, pressure=pressure, background=background)