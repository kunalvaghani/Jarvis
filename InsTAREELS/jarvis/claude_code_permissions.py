"""Local stdio MCP permission handler for the owned Claude Code session."""
import json
import os
from pathlib import Path
import sys


def approve(tool, args):
    from .claude_code_guard import decide, gui_script_target
    import hashlib
    root=Path(os.environ['JARVIS_CLAUDE_PROJECT']).resolve(strict=True)
    run=Path(os.environ['JARVIS_CLAUDE_RUN']).resolve(strict=True)
    try:
        path,content=decide(root,tool,args)
        signature=None
        events=run/'file-events.jsonl'
        if content is not None:
            signature=hashlib.sha256(json.dumps({'tool':tool,'path':str(path.resolve()),
                'input':{k:v for k,v in args.items() if k!='file_path'}},sort_keys=True,ensure_ascii=True).encode()).hexdigest()
            if events.exists() and any(json.loads(line).get('signature')==signature for line in events.read_text(encoding='utf-8').splitlines()):
                raise ValueError('This mutation was already approved in this session. Inspect current source before a different correction; identical uncertain edits are not replayed.')
        request_path=run/'request.json'
        goal=json.loads(request_path.read_text(encoding='utf-8')).get('goal','') if request_path.exists() else ''
        if content is not None and path.suffix.lower()=='.py':
            from .code_context import check_python_interfaces
            if path.exists():check_python_interfaces(path.read_text(encoding='utf-8'),content,goal)
            # A full rewrite of an explicitly named GUI script must contain a
            # reachable interface. Helpers in modular apps are not GUI entries.
            if tool=='Write' and gui_script_target(goal,path):
                from .gui_contract import check
                check(content,goal)
        if content is not None and path.exists():
            original=path.read_bytes()
            if tool=='Write':
                # Native Read can bypass permission prompts; all full overwrites
                # are guarded against the bytes present at session start.
                backup=run/'originals'/path.relative_to(root)
                if backup.exists() and backup.read_bytes()!=original:
                    raise ValueError('File changed during this session; use a unique targeted Edit or start a fresh task after inspection.')
            backup=run/'originals'/path.relative_to(root)
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists(): backup.write_bytes(original)
        with events.open('a',encoding='utf-8') as out:
            out.write(json.dumps({'tool':tool,'path':str(path),'approved':True,
                'signature':signature,
                'observed_sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
                'proposed_sha256':hashlib.sha256(content.encode()).hexdigest() if content is not None else None})+'\n')
        return {'behavior':'allow','updatedInput':args}
    except (OSError,ValueError,TypeError,KeyError) as exc:
        return {'behavior':'deny','message':str(exc)[:700]}


def main():
    for line in sys.stdin:
        request=None
        try:
            request=json.loads(line)
            method=request.get('method');params=request.get('params',{})
            if 'id' not in request: continue
            if method=='initialize':
                result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'jarvis-file-permissions','version':'1.0'}}
            elif method=='ping': result={}
            elif method=='tools/list':
                result={'tools':[{'name':'approve','description':'Validate a proposed source-file tool in the selected Jarvis project. Used as Claude Code permission handler; does not execute tools.',
                    'inputSchema':{'type':'object','properties':{'tool_name':{'type':'string'},'input':{'type':'object'}},'required':['tool_name','input']}}]}
            elif method=='tools/call':
                args=params.get('arguments') or {}
                if params.get('name')!='approve': raise ValueError('Unknown permission tool.')
                result={'content':[{'type':'text','text':json.dumps(approve(args.get('tool_name'),args.get('input') or {}))}]}
            else:
                print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32601,'message':'Unknown method'}}),flush=True);continue
            print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)
        except Exception as exc:
            if isinstance(request,dict) and 'id' in request:
                print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':str(exc)[:400]}}),flush=True)


if __name__=='__main__': main()
