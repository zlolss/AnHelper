from . import device
import os, base64

# todo: 输入法close后还原

_imes = {}

class CONST:
    PACKAGEDIR = os.path.dirname(os.path.abspath(__file__))
    PREBUILDAPK = os.path.join(PACKAGEDIR,'prebuild/ADBKeyboard.apk')
    PACKAGENAME = 'com.android.adbkeyboard'
    IMENAME = 'com.android.adbkeyboard/.AdbIME'

def getIME(device_id = None):
    global _imes
    if device_id in _imes:
        return _imes[device_id]
        
    device_id = device.getDevice(device_id).id
    if device_id in _imes:
        return _imes[device_id]
        
    newime = _IME(device_id)
    _imes[device_id] = newime
    return _imes[device_id]
    

class _IME:

    def __init__(self, device_id=None):
        self.device = device.getDevice(device_id)
        self.id = self.device.id
        self.isinstalled = False
        self.isensured = False

        
    def install(self):
        if self.isinstalled:
            # Raise
            print('ADBkeyboard安装失败，可能无法正常工作。')
            return 
        print('正在安装ADBkeyboard。。。', end='')
        if not self.device.installAPK(CONST.PREBUILDAPK, packagename = CONST.PACKAGENAME):
            # Raise
            pass
        self.device.shell(f'ime enable {CONST.IMENAME}')
        print('ok')
        self.isinstalled = True
        
    
    def getEnabled(self):
        imeEnabled = self.device.shell('ime list -s')
        return CONST.IMENAME in imeEnabled
        
    
    def getSelected(self):
        currentIme = self.device.shell('settings get secure default_input_method').strip()
        return CONST.IMENAME in currentIme
    
    
    def getActive(self):
        return self.device.getIMEInputActive()
    
    
    def select(self):
        dev = self.device
        dev.shell(f'ime set {CONST.IMENAME}')
        
    
    def ensure(self):
        if not(self.getSelected()):
            if not(self.getEnabled()):
                self.install()
            self.select()
        self.isensured = True
    
    
    def b64Encode(self, txt):
        return str(base64.b64encode(txt.encode('utf-8')))[1:]
    
    
    def input(self, txt):
        if not self.isensured:
            self.ensure()
        return  self.device.shell(f'am broadcast -a ADB_INPUT_B64 --es msg {self.b64Encode(txt)}', readout=False)
        
    
    def inputSafe(self, txt):
        self.ensure()
        return  self.device.shell(f'am broadcast -a ADB_INPUT_B64 --es msg {self.b64Encode(txt)}', readout=True)