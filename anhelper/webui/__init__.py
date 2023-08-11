from flask import Flask, render_template, Response, request
from werkzeug.serving import make_server
import threading, os
from .. import minicap, minitouch, ime, version
from socketman import WebsocketServer
import json

# todo: 无设备连接时需要错误提示

class CONST:
    PACKAGEDIR = os.path.dirname(os.path.abspath(__file__))
    HTMLDIR = os.path.join(PACKAGEDIR,'templates/')
    HOMEPAGENAME = 'index.html'
    DEFAULTPARAMS = {'host':'127.0.0.1', 'port':5000, 'device_id':None, 'frame_provider': None }



class WebUI(threading.Thread):
    
    def __init__(self, **params):
        super().__init__()
        self.params = dict(CONST.DEFAULTPARAMS, **params)
        self.minicap = minicap.getMinicap(self.params['device_id'])
        self.minitouch = minitouch.getMinitouch(self.params['device_id'])
        self.contact = None
        self.id = self.minicap.id if self.minicap is not None else '未连接'
        self.frameprovider = lambda :self.minicap.cap( captype=minicap.CONST.JPG, sync=True) if self.params['frame_provider'] is None else self.params['frame_provider']
        self.stopped = False
        app = Flask(__name__)
        self.app = app
        self.server = make_server(
            host = self.params['host'], 
            port = self.params['port'], 
            app = app,
            threaded = True
            )
        self.url = f'http://localhost:{self.params["port"]}'
        
        self.websocket_server = WebsocketServer(host='localhost', port = self.params['port']+1)
        
        @self.websocket_server.ON_RECV
        def recv_handler(txt, wsid):
            print(txt)
            try:
                switchchanges = json.loads(txt)
                for k, v in switchchanges.items():
                    if k == 'running' and v==False:
                        t = threading.Thread(target = self.stop)
                        t.start()
                    elif k== 'action':
                        self.doAction(*v)
                        #self.stop()
                    #print(f'{k}: {v}')
                    #self.switches[k] = v
                    #if k in ['pause', 'running']:
                    #    with self.switches['pause_condition']:
                    #        self.switches['pause_condition'].notify_all()
            except Exception as e:
                print(e)
                pass
            
        
                
        @app.route('/')
        def homepage():
            #if os.path.exists(CONST.HOMEPAGE):
            webvars = {'device_id':self.id, 'websocket_url':self.websocket_server.url, 'version' : version.version}
            print(webvars)
            return render_template(CONST.HOMEPAGENAME, **webvars)
            return 'homepage lost.'
        

        @app.route('/check')
        def check():
            return 'hello world.'
            
        
        @app.route('/video_feed')
        def video_feed():
            def wrapcap():
                while not(self.stopped):
                    frame = self.frameprovider()
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                        )
            return Response(
                wrapcap(), 
                mimetype='multipart/x-mixed-replace; boundary=frame'
                )


    def doAction(self, a, x, y):
        if a=='down':
            self.contact.down(x, y)
        elif a=='up':
            self.contact.up()
        elif a=='move':
            self.contact.moveto(x, y)
    
    
    def run(self):
        self.websocket_server.start()
        #print('socket start')
        self.contact = self.minitouch.useContact()
        self.server.serve_forever()
        '''    
        self.app.run(
            host=self.params['host'], 
            port=self.params['port'], 
            debug=False, 
            use_reloader=False
            )
        '''   
        
    def stop(self):
        #import requests
        #requests.get(f'http://localhost:{self.params["port"]}/shutdown')
        self.stopped = True
        self.server.shutdown()
        #print('wsstopped')
        self.join()
        #print('joined')
        self.websocket_server.stop()    
        #print('socketstopped')
        self.minicap.close()
        #self.contact.close()
        self.minitouch.close()
        #print('minicap_stopped')