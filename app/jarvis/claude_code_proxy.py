"""Task-owned loopback Anthropic adapter; local model only, thinking disabled.

Claude Code omits rather than disables third-party thinking. Qwen defaults to
thinking, so make the supported Ollama Messages API control explicit. The CLI
and this server share one Windows job; no daemon, restart or request replay.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

MODELS={'qwen3.5:9b','jarvis-claude-qwen3.5:9b'}
ORIGIN='http://127.0.0.1:11434'


def prepare(path, payload):
    route=urlsplit(path).path
    if route not in {'/v1/messages','/v1/messages/count_tokens'}:
        raise ValueError('Only local Messages API and token counts are enabled.')
    if not isinstance(payload,dict) or payload.get('model') not in MODELS:
        raise ValueError('Only the configured local Qwen3.5 9B model is enabled.')
    result={**payload,'thinking':{'type':'disabled'}}
    if route=='/v1/messages':
        tokens=result.get('max_tokens',6000)
        if type(tokens) is not int or tokens<1:raise ValueError('Invalid generation token budget.')
        result['max_tokens']=min(tokens,6000)
    # Effort names are not supported by this model's boolean thinking controls.
    if isinstance(result.get('output_config'),dict):
        result['output_config']={k:v for k,v in result['output_config'].items() if k!='effort'}
    return route,result


def serve(run):
    import requests
    from .knowledge_worker import session
    run=Path(run).resolve(strict=True)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2000000:raise ValueError('Invalid request size.')
                route,payload=prepare(self.path,json.loads(self.rfile.read(length)))
            except (ValueError,TypeError) as exc:
                self.send_error(400,str(exc));return
            try:
                with session() as client:
                    client.trust_env=False
                    client.gpu_role='coding'
                    # Forward no provider credentials or user-selected hosts.
                    with client.post(ORIGIN+route,json=payload,stream=True,timeout=(3,900),
                        headers={'anthropic-version':'2023-06-01','x-api-key':'ollama'}) as response:
                        self.send_response(response.status_code)
                        self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
                        self.send_header('Cache-Control','no-store')
                        self.send_header('Connection','close');self.end_headers()
                        for chunk in response.iter_content(chunk_size=None):
                            if chunk:self.wfile.write(chunk);self.wfile.flush()
                with (run/'proxy-events.jsonl').open('a',encoding='utf-8') as out:
                    out.write(json.dumps({'route':route,'model':payload['model'],'thinking':False,'status':response.status_code})+'\n')
            except (requests.RequestException,BrokenPipeError,ConnectionResetError,OSError):
                # Closing the owned job also closes both loopback connections.
                self.close_connection=True
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    (run/'proxy-ready.json').write_text(json.dumps({'port':server.server_port,'host':'127.0.0.1'}))
    try:server.serve_forever(poll_interval=.2)
    finally:server.server_close()


if __name__=='__main__':serve(sys.argv[1])
