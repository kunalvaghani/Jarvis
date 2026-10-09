"""Owned Codex stdio MCP source tools: checked reads, backups and exact edits."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from .claude_code_guard import decide

READS = {}


def check_component_markup(content, plan):
    """Reject a provable DOM property mismatch before applying model source."""
    from html.parser import HTMLParser
    import re
    text_ids={s['selector'][1:] for c in plan.get('checks',[]) for s in c.get('steps',[])
              if s.get('action')=='text' and re.fullmatch(r'#[A-Za-z][\w-]*',s.get('selector',''))}
    class Tags(HTMLParser):
        def handle_starttag(self,tag,attrs):
            name=dict(attrs).get('id')
            if tag in {'input','textarea'} and name in text_ids:
                raise ValueError('Registered text assertion for #'+name+' requires a text-bearing element, not '+tag+
                    '. Render visible textContent and preserve the browser check. No source was saved.')
    Tags().feed(content)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def execute(tool, args, *, context=None):
    # Native Jarvis workers have independent thread-local workspace contexts.
    # Legacy stdio clients retain their process-local environment/READS contract.
    root = Path(context.root if context is not None else os.environ['JARVIS_CODEX_PROJECT']).resolve(strict=True)
    run = Path(context.run if context is not None else os.environ['JARVIS_CODEX_RUN']).resolve(strict=True)
    reads = context.reads if context is not None else READS
    request_data=json.loads((run/'request.json').read_text(encoding='utf-8'))
    if tool=='Edit' and request_data.get('platform_component') and request_data.get('repair_diagnostics'):
        plan=json.loads((run/'validation-contract.json').read_text(encoding='utf-8'))
        if len(plan.get('files',[]))==1:
            raise ValueError('One-file component repair requires Read then Write of the complete corrected file addressing all observed failures. Partial Edit was not applied.')
    if tool=='Plan':
        from .codex_validation import declare
        return declare(root,run,args)
    if tool in {'Write','Edit'} and json.loads((run/'request.json').read_text(encoding='utf-8')).get('require_validation') and not (run/'validation-contract.json').exists():
        raise ValueError('Call Plan before writing. Declare all files and tests, e.g. files=[{path:"main.py",role:"logic",purpose:"Implement requested logic"},{path:"test_main.py",role:"test",purpose:"Assert requested behavior"}], checks=[{kind:"python_tests",path:"test_main.py"}]. Then implement both files. For UI use a browser check with actual interaction/assertion steps.')
    try:path, content = decide(root, tool, args)
    except ValueError as error:
        # Rejected proposals never became disk files. Preserve syntax evidence
        # separately from attempted/applied mutations for the next repair turn.
        if tool=='Write' and isinstance(args.get('content'),str):
            import ast
            rejected_js=None
            try:
                raw=Path(args.get('file_path',''))
                relative=(raw if raw.is_absolute() else root/raw).relative_to(root).as_posix()
                from .codex_validation import source_path
                source_path(root,relative)
                if Path(relative).suffix.lower()=='.py':ast.parse(args['content'])
                elif Path(relative).suffix.lower() in {'.js','.mjs','.cjs'} and 'Generated JavaScript failed node --check' in str(error):
                    import re
                    match=re.search(r'source\.(?:mjs|js|cjs):(\d+)',str(error))
                    number=int(match[1]) if match else 1
                    lines=args['content'].splitlines()
                    excerpt='\n'.join(str(i+1)+': '+lines[i] for i in range(max(0,number-5),min(len(lines),number+3)))
                    message=str(error)+'\nRejected source near the error:\n'+excerpt
                    with (run/'file-events.jsonl').open('a',encoding='utf-8') as output:
                        output.write(json.dumps({'stage':'rejected','path':relative,'error':message,'proposed_source':args['content'][:20000]})+'\n')
                    rejected_js=message
            except SyntaxError as syntax:
                lines=args['content'].splitlines();line=syntax.lineno or 1
                excerpt='\n'.join(str(i+1)+': '+lines[i] for i in range(max(0,line-6),min(len(lines),line+3)))
                hint=' A preceding try needs a matching except/finally; finish its handler or remove the unnecessary try.' if "expected 'except' or 'finally'" in str(syntax) else ''
                message=str(error)+hint+'\nRejected source near the error:\n'+excerpt
                with (run/'file-events.jsonl').open('a',encoding='utf-8') as output:
                    output.write(json.dumps({'stage':'rejected','path':relative,'error':message,'proposed_source':args['content'][:20000]})+'\n')
                raise ValueError(message) from error
            except (ValueError,OSError,TypeError):pass
            if rejected_js:raise ValueError(rejected_js) from error
        raise
    # Reject all linked ancestors, including links that resolve inside the root.
    for parent in [path, *path.parents]:
        if parent == root: break
        if parent.is_symlink(): raise ValueError('Linked source paths are outside the editable scope.')
    path = path.resolve()
    allowed=request_data.get('allowed_paths')
    if tool in {'Write','Edit'} and allowed is not None and path.relative_to(root).as_posix().casefold() not in {n.casefold() for n in allowed}:
        raise ValueError('This file belongs to another worker; writes are limited to the assigned exact paths.')
    if tool in {'Write','Edit'} and request_data.get('test_first'):
        contract_path=run/'validation-contract.json'
        plan=json.loads(contract_path.read_text(encoding='utf-8'))
        tests=[f['path'] for f in plan['files'] if f['role']=='test']
        relative=path.relative_to(root).as_posix()
        missing=[name for name in tests if not (root/name).is_file()]
        if missing and relative not in tests:
            raise ValueError('Save the assigned behavioral test first: '+', '.join(missing)+'. Then implement your assigned source. No implementation write was applied.')
    if tool == 'Read':
        data = path.read_bytes()
        observed = hashlib.sha256(data).hexdigest()
        if digest(path) != observed:
            raise ValueError('Source changed during Read; inspect fresh bytes before editing.')
        source = data.decode('utf-8').replace('\r\n','\n').replace('\r','\n')
        reads[str(path)] = observed
        return {'path': str(path), 'content': source, 'sha256': reads[str(path)]}
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
    if path.exists() and reads.get(str(path)) != observed:
        raise ValueError('Read the current file before modifying it; its bytes may have changed.')
    if path.exists() and path.read_text(encoding='utf-8')==content:
        raise ValueError('The proposed source is unchanged. Diagnose the observed failing assertion and make a real source correction; no save was applied.')
    if request_data.get('platform_component'):
        if path.suffix.lower() in {'.html','.htm'}:
            check_component_markup(content,json.loads((run/'validation-contract.json').read_text(encoding='utf-8')))
    goal = json.loads((run/'request.json').read_text(encoding='utf-8'))['goal']
    if path.suffix.lower() == '.py':
        from .code_context import check_python_interfaces
        contract_path=run/'validation-contract.json'
        plan=json.loads(contract_path.read_text(encoding='utf-8')) if contract_path.exists() else None
        interface_goal=goal
        if any(f['path']==path.relative_to(root).as_posix() and f['role']=='test' for f in (plan or {}).get('files',[])):
            import re
            if re.search(r'\b(?:convert|rewrite|replace)\b.{0,60}\b'+re.escape(path.name)+r'\b',goal,re.I) and re.search(r'\b(?:unittest|test cases|test assertions|test harness|test suite)\b',goal,re.I):
                interface_goal+=' rewrite the explicitly selected test harness'
        if path.exists(): check_python_interfaces(path.read_text(encoding='utf-8'), content, interface_goal)
        from .codex_validation import desktop_gui_target
        if tool == 'Write' and desktop_gui_target(root,path,goal,plan):
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
    reads[str(path)] = digest(path)
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
    specs.append({'name':'Plan','description':'Declare every expected file with its purpose and role, and real executable checks before writing code. During repair, empty arguments retrieve the existing validated Plan read-only. Preserve recorded files/checks. Browser backend must accept --port N --data-dir PATH and serve its frontend plus API on 127.0.0.1.',
        'inputSchema':{'type':'object','properties':{
            'files':{'type':'array','items':{'type':'object','properties':{'path':{'type':'string'},'role':{'type':'string','enum':['frontend','backend','entrypoint','logic','test','configuration','documentation']},'purpose':{'type':'string'}},'required':['path','role','purpose'],'additionalProperties':False}},
            'checks':{'type':'array','items':{'type':'object','properties':{'kind':{'type':'string','enum':['python_tests','node_tests','python_script','node_script','browser','npm_build','npm_test','npm_typecheck']},'path':{'type':'string'},'animation_selectors':{'type':'array','items':{'type':'string'}},'server':{'type':'object','properties':{'kind':{'type':'string','enum':['python','node']},'path':{'type':'string'}},'required':['kind','path'],'additionalProperties':False},'steps':{'type':'array','items':{'type':'object','properties':{'action':{'type':'string','enum':['click','fill','text','value','reload']},'selector':{'type':'string'},'value':{'type':'string'}},'required':['action'],'additionalProperties':False}}},'required':['kind','path'],'additionalProperties':False}}},'additionalProperties':False}})
    properties=specs[-1]['inputSchema']['properties']['checks']['items']['properties']
    properties['kind']['enum'].append('browser_component')
    properties.update(entry={'type':'string'},component={'type':'string','enum':['markup','styles','logic']},
                      suppress_resources={'type':'array','items':{'type':'string'}},required_selectors={'type':'array','items':{'type':'string'}})
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
