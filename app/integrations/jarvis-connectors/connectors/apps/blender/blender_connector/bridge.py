"""Token-protected local JSON bridge. Network threads never call bpy.
Run start_bridge.py from Blender Scripting workspace or with blender --python.
"""
from __future__ import annotations
import hmac
import json
import os
from pathlib import Path
import queue
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .catalog import validate_action
from .operations import BlenderOperations

BIND='127.0.0.1'
DEFAULT_PORT=8769
MAX_BODY=256*1024
MAX_PENDING=32
MAX_RESULTS=256
TTL=600


class BoundedHTTPServer(ThreadingHTTPServer):
    """Bound authenticated and unauthenticated slow clients alike."""
    daemon_threads=True
    def __init__(self,*args,**kwargs):
        self.slots=threading.BoundedSemaphore(16)
        super().__init__(*args,**kwargs)
    def process_request(self,request,address):
        request.settimeout(2)
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:super().process_request(request,address)
        except BaseException:
            self.slots.release()
            raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()

def config_file():
    return Path(os.getenv('JARVIS_BLENDER_CONFIG',str(Path.home()/'.jarvis'/'blender-bridge.json'))).expanduser()

def _atomic_write(path, payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
    try:
        fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(payload,f,indent=2);f.flush();os.fsync(f.fileno())
        # Publish a complete scope without replacing another instance, even under a race.
        os.link(str(tmp),str(path))
        if os.name!='nt': os.chmod(path,0o600)
    finally:
        try:tmp.unlink(missing_ok=True)
        except OSError:pass

class Bridge:
    def __init__(self,operations=None,port=DEFAULT_PORT,token=None,write_config=True):
        if not isinstance(port,int) or not 1024<=port<=65535:raise ValueError('Port range 1024..65535')
        self.ops=operations or BlenderOperations()
        self.port=port
        self.scope_id=uuid.uuid4().hex
        self.snapshot={}
        self.last_pump=time.monotonic()
        self.token=token or os.getenv('JARVIS_BLENDER_TOKEN') or secrets.token_urlsafe(40)
        if len(self.token)<32:raise ValueError('Use a token of at least 32 characters')
        self.pending=queue.Queue(maxsize=MAX_PENDING)
        self.jobs={}
        self._lock=threading.RLock()
        self._server=None
        self._thread=None
        self.started=time.monotonic()
        self.write_config=write_config
        self.stopped=False

    def start(self):
        if self._server: return self
        if self.write_config and config_file().exists():
            raise RuntimeError('Scope configuration already exists; explicitly attach or stop its owner first.')
        parent=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass # prevent leaking tokens and requests
            def _json(self,code,data):
                encoded=json.dumps(data,ensure_ascii=True,default=str).encode('utf-8')
                self.send_response(code);self.send_header('Content-Type','application/json')
                self.send_header('Cache-Control','no-store')
                self.send_header('Content-Length',str(len(encoded)))
                self.send_header('Connection','close');self.end_headers();self.wfile.write(encoded)
            def _authorized(self):
                auth=self.headers.get('Authorization','')
                if not hmac.compare_digest(auth,'Bearer '+parent.token):
                    self._json(401,{'ok':False,'error':'unauthorized'});return False
                return True
            def do_GET(self):
                if not self._authorized():return
                path=urlsplit(self.path).path
                if path=='/v1/health':
                    self._json(200,{'ok':True,'connected':True,'uptime_seconds':round(time.monotonic()-parent.started,2),'queue_depth':parent.pending.qsize(),'scope_id':parent.scope_id,'main_thread_age':round(time.monotonic()-parent.last_pump,2),'state':parent.snapshot})
                elif path.startswith('/v1/jobs/'):
                    job_id=path.removeprefix('/v1/jobs/')
                    if not job_id or '/' in job_id:self._json(404,{'ok':False,'error':'not found'});return
                    with parent._lock:job=parent.jobs.get(job_id)
                    if job is None:self._json(404,{'ok':False,'error':'job not found'})
                    else:self._json(200,{'ok':True,'scope_id':parent.scope_id,'job':job.copy()})
                else:self._json(404,{'ok':False,'error':'not found'})
            def do_POST(self):
                if not self._authorized():return
                if urlsplit(self.path).path!='/v1/execute':self._json(404,{'ok':False,'error':'not found'});return
                try:
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<=size<=MAX_BODY:self._json(413,{'ok':False,'error':'invalid request size'});return
                    item=json.loads(self.rfile.read(size))
                    if not isinstance(item,dict) or set(item)!={'action','params','scope_id'}:raise ValueError('Expected action and params')
                    if item['scope_id'] != parent.scope_id: raise ValueError('Bridge scope changed')
                    name=item['action'];params=validate_action(name,item['params'])
                except (ValueError,TypeError,UnicodeDecodeError) as e:
                    self._json(400,{'ok':False,'error':str(e)[:180]});return
                with parent._lock:
                    parent._cleanup()
                    if parent.pending.full() or len(parent.jobs)>=MAX_RESULTS:
                        self._json(429,{'ok':False,'error':'bridge queue full'});return
                    job_id=uuid.uuid4().hex
                    parent.jobs[job_id]={'id':job_id,'action':name,'status':'queued','created':time.time()}
                    try:parent.pending.put_nowait((job_id,name,params))
                    except queue.Full:
                        del parent.jobs[job_id];self._json(429,{'ok':False,'error':'bridge queue full'});return
                self._json(202,{'ok':True,'job_id':job_id,'status':'queued'})
        self._server=BoundedHTTPServer((BIND,self.port),Handler)
        self._server.daemon_threads=True
        self.port=self._server.server_address[1]
        self._thread=threading.Thread(target=self._server.serve_forever,name='JarvisBlenderHTTP',daemon=True)
        self._thread.start()
        if self.write_config:
            try:
                _atomic_write(config_file(),{'host':BIND,'port':self.port,'token':self.token,'protocol':'jarvis-blender-v1','scope_id':self.scope_id,'pid':os.getpid()})
            except BaseException:
                self.stop()
                raise
        return self

    def _cleanup(self):
        now=time.time()
        # Never delete running jobs. Retain completed jobs for 10 minutes.
        for key,job in list(self.jobs.items()):
            if job['status'] in ('done','error') and now-job.get('finished',now)>TTL:del self.jobs[key]

    def pump(self):
        """Call ONLY from the bpy main thread via bpy.app.timers.register.
        One expensive Blender operation per timer tick; no bpy from HTTP worker.
        """
        if self.stopped:return None
        self.last_pump=time.monotonic()
        if hasattr(self.ops,'bpy'):
            b=self.ops.bpy
            self.snapshot={'version':b.app.version_string,'file':b.data.filepath,'selected':b.context.view_layer.objects.active.name if b.context.view_layer.objects.active else None}
        try:job_id,action,params=self.pending.get_nowait()
        except queue.Empty:return .05
        with self._lock:
            job=self.jobs.get(job_id)
            if job is None:return .05
            job['status']='running';job['started']=time.time()
        try:
            result=self.ops.execute(action,params)
            with self._lock:job.update(status='done',result=result,finished=time.time())
        except Exception as e:
            with self._lock:job.update(status='error',error={'type':type(e).__name__,'message':str(e)[:1500]},finished=time.time())
        finally:self.pending.task_done()
        return .01

    def stop(self):
        self.stopped=True
        if self._server:self._server.shutdown();self._server.server_close();self._server=None
        if self._thread:self._thread.join(timeout=3);self._thread=None
        if self.write_config:
            p=config_file()
            # Avoid deleting a config overwritten by a newer Blender process.
            try:
                data=json.loads(p.read_text(encoding='utf-8'))
                if data.get('token')==self.token and data.get('port')==self.port:p.unlink()
            except (FileNotFoundError,ValueError,OSError):pass
