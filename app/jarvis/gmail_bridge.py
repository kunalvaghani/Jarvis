"""Bounded local extension transport. Leased actions are never dispatched twice."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from uuid import uuid4


class GmailBridge:
    def __init__(self, token, source_hash=''):
        self.token=token;self.source_hash=source_hash;self.pending=None;self.result=None;self.identity=None
        self.lock=threading.Lock();self.ready=threading.Event()
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def authorized(self):
                return (self.client_address[0]=='127.0.0.1' and self.headers.get('Host')=='127.0.0.1:29923'
                    and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+owner.token))
            def reply(self,status,data):
                raw=json.dumps(data).encode();self.send_response(status)
                self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                if not self.authorized():return self.reply(403,{})
                if self.path!='/job':return self.reply(404,{})
                with owner.lock:
                    job=owner.pending;owner.pending=None # Lease once, including uncertain outcomes.
                self.reply(200,job or {})
            def do_POST(self):
                if not self.authorized():return self.reply(403,{})
                if self.path!='/result':return self.reply(404,{})
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=65536:raise ValueError()
                    row=json.loads(self.rfile.read(size))
                    if not isinstance(row,dict) or row.get('id')!=owner.identity or (owner.source_hash and row.get('adapter_hash')!=owner.source_hash):raise ValueError()
                    with owner.lock:
                        if owner.ready.is_set():raise ValueError()
                        owner.result=row;owner.ready.set()
                    self.reply(200,{'accepted':True})
                except (ValueError,TypeError):self.reply(400,{})
        class Server(ThreadingHTTPServer):
            def get_request(self):
                connection,address=super().get_request();connection.settimeout(3)
                return connection,address
        self.server=Server(('127.0.0.1',29923),Handler)
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def call(self,request,timeout=15):
        self.identity=uuid4().hex;self.result=None;self.ready.clear()
        with self.lock:self.pending={'id':self.identity,'request':request}
        if not self.ready.wait(timeout):
            with self.lock:self.pending=None
            raise ValueError('Gmail extension did not confirm the operation. Load/reload the local adapter and select Gmail. Inspect the draft before retrying; no action replayed.')
        row=self.result
        if row.get('error'):raise ValueError(str(row['error'])[:500])
        if not isinstance(row.get('result'),dict):raise ValueError('Invalid Gmail extension readback; inspect before retry.')
        return row['result']

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)


def configured(base):
    import hashlib
    path=base/'.jarvis-runtime/gmail-extension/connection.json'
    if not path.exists():return None
    config=json.loads(path.read_text());token=config.get('token')
    if not isinstance(token,str) or len(token)!=64:raise ValueError('Regenerate the local Gmail adapter with launchers/Setup Jarvis Gmail.cmd.')
    names=('manifest.json','background.js','gmail-content.js','keepalive.js')
    reviewed=base/'integrations/gmail-chrome';installed=path.parent
    source_hash=hashlib.sha256(b''.join((reviewed/name).read_bytes() for name in names)).hexdigest()
    if config.get('source_hash')!=source_hash or any((installed/name).read_bytes()!=(reviewed/name).read_bytes() for name in names):
        raise ValueError('Gmail adapter source changed. Run launchers/Setup Jarvis Gmail.cmd and reload the extension before use.')
    return GmailBridge(token,source_hash)
