"""Task-owned Responses relay to local Ollama; bounded source tools only."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

MODELS={'qwen3.5:9b','jarvis-codex-qwen3.5:9b'}
ORIGIN='http://127.0.0.1:11434'
TOOLS={'mcp__jarvis_files__'+name for name in ('Read','Write','Edit','Glob','Grep')}


def prepare(path, payload):
    if urlsplit(path).path!='/v1/responses': raise ValueError('Only local Responses inference is enabled.')
    if not isinstance(payload,dict) or payload.get('model') not in MODELS:
        raise ValueError('Only local Qwen3.5 9B is enabled; no cloud fallback.')
    if payload.get('previous_response_id') or payload.get('conversation'):
        raise ValueError('Ollama requires full stateless input history.')
    # Native shell/apply_patch/web tools are deliberately absent from the model.
    tools=[]
    for tool in payload.get('tools',[]):
        if tool.get('type')=='function' and tool.get('name') in TOOLS: tools.append(tool)
        elif tool.get('type')=='namespace' and tool.get('name')=='mcp__jarvis_files':
            for inner in tool.get('tools',[]):
                name='mcp__jarvis_files__'+inner.get('name','')
                if inner.get('type')=='function' and name in TOOLS:
                    tools.append({**inner,'name':name})
    if not tools: raise ValueError('Required Jarvis source tools are not connected.')
    result={**payload,'tools':tools,'think':False,'parallel_tool_calls':False,'store':False,
            'max_output_tokens':min(payload.get('max_output_tokens',6000),6000)}
    if isinstance(result.get('input'),list):
        history=[]
        for item in result['input']:
            if item.get('type')=='function_call':
                item=dict(item)
                if item.get('namespace')=='mcp__jarvis_files':
                    item['name']='mcp__jarvis_files__'+item['name'];item.pop('namespace')
                if item.get('name') not in TOOLS: raise ValueError('Unsupported function in input history.')
            history.append(item)
        result['input']=history
    result.pop('reasoning',None)
    result.pop('include',None)
    return result


def validate(event):
    items=[]
    if event.get('type') in {'response.output_item.added','response.output_item.done'}:
        items.append(event.get('item',{}))
    if event.get('type') in {'response.completed','response.incomplete'}:
        items += event.get('response',{}).get('output',[])
    for item in items:
        if item.get('type') not in {'message','reasoning','function_call'}:
            raise ValueError('Local model returned an unsupported tool type.')
        if item.get('type')=='function_call' and item.get('name') not in TOOLS:
            raise ValueError('Local model returned an unoffered tool; task stopped without replay.')


def restore(event):
    """Restore Codex's exact namespace/name pair after Ollama's flat call."""
    validate(event)
    items=[]
    if isinstance(event.get('item'),dict): items.append(event['item'])
    if isinstance(event.get('response'),dict): items += event['response'].get('output',[])
    for item in items:
        if item.get('type')=='function_call':
            item['namespace']='mcp__jarvis_files'
            item['name']=item['name'].removeprefix('mcp__jarvis_files__')
    return event


def serve(run):
    import requests
    run=Path(run).resolve(strict=True)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2000000: raise ValueError('Invalid inference request size.')
                raw=json.loads(self.rfile.read(length))
                (run/'tool-schema.json').write_text(json.dumps(raw.get('tools',[]),indent=2),encoding='utf-8')
                payload=prepare(self.path,raw)
            except (ValueError,TypeError) as exc:
                self.send_error(400,str(exc));return
            # Do not retry inference or an interrupted agent turn here.
            with (run/'proxy-events.jsonl').open('a',encoding='utf-8') as out:
                out.write(json.dumps({'stage':'started','model':payload['model'],'thinking':False,
                    'tools':[t['name'] for t in payload['tools']]})+'\n')
            try:
                with requests.Session() as client:
                    client.trust_env=False
                    with client.post(ORIGIN+'/v1/responses',json=payload,stream=True,timeout=(3,1800)) as response:
                        self.send_response(response.status_code)
                        self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
                        self.send_header('Cache-Control','no-store');self.send_header('Connection','close');self.end_headers()
                        if 'text/event-stream' in response.headers.get('Content-Type',''):
                            with (run/'stream.jsonl').open('a',encoding='utf-8') as progress:
                                for line in response.iter_lines(chunk_size=1):
                                    if line.startswith(b'data:') and line[5:].strip()!=b'[DONE]':
                                        event=restore(json.loads(line[5:]))
                                        line=b'data: '+json.dumps(event).encode()
                                        if event.get('type') in {'response.output_text.delta','response.function_call_arguments.delta','response.output_item.added','response.output_item.done'}:
                                            # Reasoning never appears in the island preview.
                                            if event.get('item',{}).get('type')!='reasoning':
                                                progress.write(json.dumps(event)+'\n');progress.flush()
                                    self.wfile.write(line+b'\n');self.wfile.flush()
                        else:
                            data=response.json()
                            if response.ok: restore({'type':'response.completed','response':data})
                            self.wfile.write(json.dumps(data).encode());self.wfile.flush()
                with (run/'proxy-events.jsonl').open('a',encoding='utf-8') as out:
                    out.write(json.dumps({'stage':'completed','thinking':False,'model':payload['model'],'status':response.status_code})+'\n')
            except (requests.RequestException,ValueError,BrokenPipeError,ConnectionResetError,OSError) as exc:
                with (run/'proxy-events.jsonl').open('a',encoding='utf-8') as out:
                    out.write(json.dumps({'stage':'failed','error':str(exc)[:400]})+'\n')
                self.close_connection=True
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    (run/'proxy-ready.json').write_text(json.dumps({'port':server.server_port,'host':'127.0.0.1'}))
    try: server.serve_forever(poll_interval=.2)
    finally: server.server_close()


if __name__=='__main__': serve(sys.argv[1])
