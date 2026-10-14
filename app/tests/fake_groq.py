"""Local HTTP simulation; no cloud connection or credential is needed."""
from contextlib import contextmanager
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time


@contextmanager
def server():
    state={'calls':0,'bodies':[],'mode':'ok','headers':{},'delay':0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            body=json.dumps({'data':[{'id':'qwen/qwen3.8-27b','active':True}]}).encode()
            if state['mode']=='big_metadata':body=b'x'*100001
            self.send_response(200); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            state['calls']+=1
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['bodies'].append(payload)
            if state['delay']: time.sleep(state['delay'])
            code=int(state['mode']) if state['mode'] in {'401','429','404','500'} else 200
            self.send_response(code)
            for key,value in state['headers'].items(): self.send_header(key,str(value))
            self.send_header('Content-Type','text/event-stream' if payload.get('stream') else 'application/json')
            self.end_headers()
            if code!=200: self.wfile.write(b'{"error":"test failure"}'); return
            usage={'prompt_tokens':80,'completion_tokens':10,'total_tokens':90}
            if payload.get('stream'):
                if state['mode']=='big_stream':self.wfile.write(b'data: '+b'x'*100010+b'\n\n');return
                events=[{'id':'fake','choices':[{'delta':{'content':'Public answer'},'finish_reason':None}]}]
                if state['mode']=='many_chunks':
                    events=[{'id':'fake','choices':[{'delta':{'content':'Proof αβγ. '*2},'finish_reason':None}]} for _ in range(2000)]
                if state['mode']!='disconnect':
                    events.append({'choices':[{'delta':{},'finish_reason':'length' if state['mode']=='length' else 'stop'}],'x_groq':{'usage':usage}})
                for event in events:
                    self.wfile.write(b'data: '+json.dumps(event).encode()+b'\n\n'); self.wfile.flush()
                if state['mode']!='disconnect': self.wfile.write(b'data: [DONE]\n\n')
            else:
                message={'content':'Public answer'}
                finish='stop'
                if payload.get('response_format'): message={'content':'{"answer":"Public answer"}'}
                if payload.get('tools'):
                    message={'content':None,'tool_calls':[{'id':'test','type':'function','function':{'name':payload['tools'][0]['function']['name'],'arguments':'{"topic":"physics"}'}}]}
                    finish='tool_calls'
                    if state['mode']=='bad_tools':message['tool_calls'][0]['function']['arguments']='{"topic":12,"unexpected":"x"}'
                if state['mode']=='malformed': self.wfile.write(b'not-json'); return
                self.wfile.write(json.dumps({'id':'fake','usage':usage,'choices':[{'message':message,'finish_reason':finish}]}).encode())
    class FakeServer(ThreadingHTTPServer):
        def handle_error(self,*args):pass  # Expected socket closes in fault cases.
    instance=FakeServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=instance.serve_forever,daemon=True);thread.start()
    try: yield 'http://127.0.0.1:'+str(instance.server_port),state
    finally: instance.shutdown(); instance.server_close(); thread.join(timeout=2)
