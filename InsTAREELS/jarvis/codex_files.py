"""Owned Codex stdio MCP source tools: checked reads, backups and exact edits."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from .claude_code_guard import decide, gui_script_target

READS = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def execute(tool, args):
    root = Path(os.environ['JARVIS_CODEX_PROJECT']).resolve(strict=True)
    run = Path(os.environ['JARVIS_CODEX_RUN']).resolve(strict=True)
    path, content = decide(root, tool, args)
    # Reject all linked ancestors, including links that resolve inside the root.
    for parent in [path, *path.parents]:
        if parent == root: break
        if parent.is_symlink(): raise ValueError('Linked source paths are outside the editable scope.')
    path = path.resolve()
    if tool == 'Read':
        source = path.read_text(encoding='utf-8')
        READS[str(path)] = digest(path)
        return {'path': str(path), 'content': source, 'sha256': READS[str(path)]}
    if tool in {'Glob', 'Grep'}:
        from .coder import project_files
        names = project_files(root)
        names = [n for n in names if (root/n).resolve().is_relative_to(path)]
        if tool == 'Glob':
            import fnmatch
            pattern=args.get('pattern','*')
            return {'files': [n for n in names if fnmatch.fnmatch(n,pattern) or
                (pattern.startswith('**/') and fnmatch.fnmatch(n,pattern[3:]))][:160]}
        pattern = args.get('pattern', '')
        if not isinstance(pattern, str) or not pattern or len(pattern)>200:
            raise ValueError('Grep needs bounded literal text.')
        matches = []
        for name in names:
            target, _ = decide(root, 'Read', {'file_path': name})
            for number, line in enumerate(target.read_text(encoding='utf-8').splitlines(), 1):
                if pattern.casefold() in line.casefold():
                    matches.append({'file': name, 'line': number, 'text': line[:300]})
                    if len(matches)>=60: return {'matches': matches}
        return {'matches': matches}
    observed = digest(path)
    if path.exists() and READS.get(str(path)) != observed:
        raise ValueError('Read the current file before modifying it; its bytes may have changed.')
    goal = json.loads((run/'request.json').read_text(encoding='utf-8'))['goal']
    if path.suffix.lower() == '.py':
        from .code_context import check_python_interfaces
        if path.exists(): check_python_interfaces(path.read_text(encoding='utf-8'), content, goal)
        if tool == 'Write' and gui_script_target(goal, path):
            from .gui_contract import check
            check(content, goal)
    signature = hashlib.sha256(json.dumps({'tool':tool,'path':str(path),'args':args},sort_keys=True).encode()).hexdigest()
    events = run/'file-events.jsonl'
    if events.exists() and any(json.loads(line).get('signature') == signature for line in events.read_text(encoding='utf-8').splitlines()):
        raise ValueError('An identical mutation was already attempted. Inspect current source before a different correction.')
    if path.exists():
        backup = run/'originals'/path.relative_to(root)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists(): backup.write_bytes(path.read_bytes())
    entry = {'tool':tool,'path':str(path),'approved':True,'signature':signature,
             'observed_sha256':observed,'proposed_sha256':hashlib.sha256(content.encode()).hexdigest()}
    with events.open('a', encoding='utf-8') as out:
        out.write(json.dumps({**entry,'stage':'attempted'})+'\n');out.flush()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',newline='',dir=path.parent,
                                     prefix='.jarvis-codex-',suffix='.tmp',delete=False) as out:
        temp = Path(out.name);out.write(content)
    if digest(path) != observed:
        raise ValueError('Source changed before saving; proposed file retained at '+str(temp))
    os.replace(temp, path)
    if digest(path) != entry['proposed_sha256']:
        raise ValueError('Saved source changed during readback; inspect it before continuing.')
    # Our successful atomic save/readback is a fresh observation too. Further
    # exact edits can use it; any external byte change still requires a Read.
    READS[str(path)] = digest(path)
    with events.open('a', encoding='utf-8') as out:
        out.write(json.dumps({**entry,'stage':'applied'})+'\n')
    return {'path':str(path),'saved':True,'sha256':digest(path),
            'checks':'Disk readback and available syntax checks passed. Runtime/UI not tested.'}


def tool_specs():
    specs = []
    for name in ('Read','Write','Edit','Glob','Grep'):
        props = {'file_path':{'type':'string'}} if name in {'Read','Write','Edit'} else {'path':{'type':'string'},'pattern':{'type':'string'}}
        required = ['file_path'] if name in {'Read','Write','Edit'} else ['pattern']
        if name=='Write': props['content']={'type':'string'};required.append('content')
        if name=='Edit':
            props.update(old_string={'type':'string'},new_string={'type':'string'},replace_all={'type':'boolean'})
            required += ['old_string','new_string']
        description = {'Read':'Read a current source file before editing; returns its exact source and hash.',
            'Write':'Create or replace a source file. Read existing files first. Syntax checked before saving.',
            'Edit':'Apply an exact unique text replacement after Read. Prefer a small unique old_string; never guess whitespace or replace an entire file unnecessarily. Preserves unrelated source.',
            'Glob':'List supported source files within this project by relative wildcard.',
            'Grep':'Find literal text in bounded supported project source files.'}[name]
        specs.append({'name':name,'description':description,'inputSchema':{'type':'object','properties':props,'required':required,'additionalProperties':False}})
    return specs


def main():
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            if 'id' not in request: continue
            method = request.get('method'); params = request.get('params', {})
            if method=='initialize':
                result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'jarvis-codex-files','version':'1.0'}}
            elif method=='ping': result={}
            elif method=='tools/list': result={'tools':tool_specs()}
            elif method=='tools/call':
                try:
                    value=execute(params['name'],params.get('arguments') or {})
                    text=('File: '+value['path']+'\nSHA256: '+value['sha256']+'\nCurrent source:\n'+value['content']) if params['name']=='Read' else json.dumps(value)
                    result={'content':[{'type':'text','text':text}]}
                except (OSError,ValueError,TypeError,KeyError) as exc:
                    result={'isError':True,'content':[{'type':'text','text':str(exc)[:700]}]}
            else: raise ValueError('Unknown MCP method.')
            print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)
        except Exception as exc:
            if isinstance(request,dict) and 'id' in request:
                print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':str(exc)[:400]}}),flush=True)


if __name__=='__main__': main()
