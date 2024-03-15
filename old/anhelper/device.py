import subprocess
import sys, os
from .common import ParamSupervisor
from .adb import ADB_PATH

_devices = {}

# todo 检查设备在线状态

class CONST:
    STATUS_AVAILABLE = True
    TABLET_720P = {'width':1280, 'height':720, 'density':240}
    


def listDevicesL():
    cmd = f'{ADB_PATH} devices -l'
    subp = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    rl = subp.stdout.readlines()
    def parseDevicesList(rawlines):
        devicelist = {}
        for line in rawlines:
            lineitems = line.decode().split()
            if len(lineitems)>2 and lineitems[1].lower() in ['device']:
                devicelist[lineitems[0]] = lineitems[1:]
        return devicelist
    return parseDevicesList(rl)


def listDevices():
    return listDevicesL()
    

def connectDevice(ip='127.0.0.1',port='16416'):
    cmd = f'{ADB_PATH} connect {ip}:{port}'
    subp = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    results = subp.stdout.read().decode().split()
    return results[0].lower() in ['connected','already']
    
    
def getDevice(device_id=None):
    global _devices
    if device_id not in _devices:
        devicelist = listDevicesL()
        if device_id is None and len(devicelist)>=1:
            device_id = list(devicelist.keys())[0]
        elif device_id not in devicelist:
            if len(devicelist)==0:
                print(f'未检测到任何通过adb连接的设备，请先连接')
            else:
                print(f'指定安卓设备{device_id}未通过adb连接，请先连接')
            return None
        _devices[device_id] = _Device(device_id = device_id, header = devicelist[device_id])
    return _devices[device_id]




class _Device:
    
    
    def __init__(self, device_id = None, header = None):
        self.id = device_id
        self.isenable = True
        self.tmpdir = '/data/local/tmp/'
        self.header = header
        self.wmphysical = None
        self.supervisor = ParamSupervisor(self, stop_callback=self.remove)
        self.isenable = True
        
    
    def remove(self):
        global _devices
        print('设备停止工作')
        self.isenable = False
        _devices.pop(self.id)
        
        
    def supervisorStart(self):
        if self.supervisor is not None and self.supervisor.is_alive():
            return 
        self.supervisor.start()
        
        
    def supervisorStop(self):
        if self.supervisor is None or not(self.supervisor.is_alive()):
            return
        self.supervisor.stopped = True
        self.supervisor.join()
        
        
    def supervisorAdd(self, param):
        self.supervisor.addParam(param)
        self.supervisorStart()
        
        
    @staticmethod
    def pathjoin(*paths):
        pathitems = []
        for path in paths:
            pathitems+=path.split('/')
        return '/'.join(pathitems)
        
        
    @property    
    def adbhead(self):
        if self.id:
            return f'{ADB_PATH} -s {self.id} '
        return f'{ADB_PATH} '
        
    
    def getStatus(self):
        return self.getOnline()
    
    
    def requireRoot(self):
        self.adb('root', readout=True)
        
    
    def adb(self, cmd, readout=True):
        acmd = self.adbhead+cmd
        subp =  subprocess.Popen(acmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        if readout:
            return subp.stdout.read().decode('utf-8').strip()
        return subp
        
        
    def shell(self, cmd, readout=True):
        return self.adb(f'shell "{cmd}"', readout)
        
    
    def getOnline(self):
        return self.id in listDevicesL()
    
    
    def getOrientation(self):
        #0 原始竖屏， 1 左横屏， 3 右横屏
        key = 'orientation='
        s = self.shell(f"dumpsys display | grep \'{key}\' | head -1", readout=True)
        i = s.find(key)
        oid = i+len(key)
        if (len(s)<oid):
            return 0
        return int(s[oid])
        
        
    def getIMEInputActive(self):
        # 检测输入框是否存在 或 当前是否可以使用输入法输入
        return self.shell("dumpsys input_method | grep mServedInputConnectionWrapper", readout=True).strip().split('=')[-1].lower() !='null'

    
    @property    
    def ABI(self):
        pname =f'_{sys._getframe().f_code.co_name}'
        if pname not in vars(self):
            vars(self)[pname] = self.shell("getprop ro.product.cpu.abi", readout=True).strip()
        return vars(self)[pname]
    
    
    @property
    def abi(self):
        return self.ABI
            
            
    @property    
    def SDK(self):
        pname =f'_{sys._getframe().f_code.co_name}'
        if pname not in vars(self):
            self.__dict__[pname] = int(self.shell("getprop ro.build.version.sdk", readout=True).strip())
        return vars(self)[pname]      


    @property
    def sdk(self):
        return self.SDK

        
    def installAPK(self, apkpath, packagename=None):
    
        if os.path.splitext(apkpath)[-1].lower() != '.apk':
            return False
            
        tmppath = self.pushTmp(apkpath)
        
        if packagename:
            cmd = f'pm install -r -i {packagename} {tmppath}'
        else:
            cmd = f'pm install -r {tmppath}'
            
        self.shell(cmd)
        
        return True
    
    
    def pushTmp(self, fpath):
        fname = os.path.basename(fpath)
        tmppath = self.pathjoin(self.tmpdir, fname)
        self.adb(f'push {fpath} {tmppath}')
        return tmppath
    
    
    def getWMSize(self):
        wmSizes = [l.lower() for l in self.shell('wm size').split('\r\n')]
        overideSize = None
        for line in wmSizes:
            if 'physical' in line:
                physicalSize = [int(x) for x in line.split()[-1].split('x')]
            elif 'override' in line:
                overideSize = [int(x) for x in line.split()[-1].split('x')]
        if self.wmphysical is None:
            self.wmphysical = {}
        self.wmphysical['width'], self.wmphysical['height'] = physicalSize
        if overideSize:
            wh =  overideSize
        else:
            wh = physicalSize
        return {'width':wh[0], 'height':wh[1]}
    
    
    def getWMDensity(self):
        wmDensitys = [l.lower() for l in self.shell('wm density').split('\r\n')]
        overideDensity = None
        for line in wmDensitys:
            if 'physical' in line:
                physicalDensity = int(line.split()[-1])
            elif 'override' in line:
                overideDensity = int(line.split()[-1])
        if self.wmphysical is None:
            self.wmphysical = {}
        self.wmphysical['density'] = physicalDensity
        if overideDensity:
            density = overideDensity
        else:
            density = physicalDensity
        return {'density': density}
    
    
    def getWM(self):
        wmSize = self.getWMSize()
        wmDensity = self.getWMDensity()
        return dict(wmSize, **wmDensity)
        
        
    def setWM(self, width, height, density = None, fit_orientation = True):
        if fit_orientation: # 确保方向与设备的物理屏幕一致
            pwm = self.wmphysical if self.wmphysical else self.getWMSize()
            width, height = (width, height) if ((width/height)>1) ^ ((pwm['width']/pwm['height'])<=1) else (height, width)
        self.shell(f'wm size {width}x{height}')
        if density:
            self.shell(f'wm density {density}')
            
            
    def resetWM(self):
        self.shell(f'wm size reset')
        self.shell(f'wm density reset')
        
        
    