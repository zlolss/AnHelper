# todo: ---------
import threading, time

class ParamSupervisor(threading.Thread):
    '''
    调用father对应getParam方法获取参数
    '''
    def __init__(self, father, interval=1., stop_callback=lambda :None):
        super().__init__()
        self.father = father
        self.params = {}
        self.interval = interval
        self.stopped = False
        self.stopcallback = stop_callback
        self.setDaemon(True)
        
        
    def getMethodName(self, param):
        return f'get{param}'
        
    def addParam(self, param):
        if param in self.params:
            return
        pname = self.getMethodName(param)
        if pname not in self.father.__dir__():
            print(f'get param:{pname} failed')
            return 
        self.params[param] = None
        
    def updateParam(self, param):
        try:
            pname = self.getMethodName(param)
            self.params[param] = eval(f'self.father.{pname}()')
        except:
            print('参数获取错误，supervisor正在停止')
            self.stopped = True
            self.stopcallback()
        
        
    def run(self):
        while not(self.stopped):
            params = list(self.params.keys())
            for param in params:
                self.updateParam(param)
            time.sleep(self.interval)


class Cache:

    def __init__(self, maxsize = 10):
        self.size = maxsize
        self.seek = 0
        self.latestseek = 0
        self.newseek = 0
        self.data = [{} for i in range(maxsize+1)]

    
    def nextSeek(self, seek):
        return seek+1 if seek<self.size else 0
    
    
    class GetCache:
        def __init__(self, father, seek, isnew = False):
            self.father = father
            self.seek = seek
            self.isnew = isnew
            
        def __enter__(self):
            #self.father.locked.add(self.seek)
            return self.father.data[self.seek]
            
        def __exit__(self, exc_type, exc_value, traceback):
            #self.father.locked.remove(self.seek)
            if self.isnew:
                self.father.latestseek = self.seek
            pass
            
    
    @property
    def withnew(self):
        # 写入
        seek = self.newseek
        self.newseek = self.nextSeek(self.newseek)
        return self.GetCache(self, seek, isnew = True)
        
    
    @property
    def withlatest(self):
        # 读取
        return self.GetCache(self, self.latestseek)
        