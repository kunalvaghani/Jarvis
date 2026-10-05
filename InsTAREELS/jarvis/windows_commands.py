"""Pinned Windows reference recipes: literal bindings, no generated code execution."""
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1] / 'integrations/windows-command-reference'
CATALOG_SHA = '3f0f7102af9d90fc1bcca462e81e0d50a165c4fa2d4c695a83ebac7266687499'
SOURCE_SHA = 'e86e22949a53a28b41832e06eebe4080f23d6a1ded0e5486a7edd31076ff91a5'


def catalog():
    raw = (ROOT / 'catalog.json').read_bytes()
    source = (ROOT / 'Jarvis_Windows_11_Commands.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA or hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Windows command reference changed; review recipes before executing.')
    rows = json.loads(raw)
    if [r['id'] for r in rows] != list(range(1, 494)):
        raise ValueError('Incomplete Windows command reference.')
    return rows


def search(query, limit=12):
    words = set(re.findall(r'\w+', query.casefold()))
    rows = catalog()
    if query.strip().isdigit():
        rows = [r for r in rows if r['id'] == int(query)]
    else:
        rows = sorted(rows, key=lambda r: -len(words & set(re.findall(r'\w+', r['task'].casefold()+' '+r['category'].casefold()))))
        rows = [r for r in rows if words & set(re.findall(r'\w+', r['task'].casefold()+' '+r['category'].casefold()))]
    return [{k:r[k] for k in ('id','task','category','backend','parameters','approval','prerequisite','note')} for r in rows[:limit]]


def match(text):
    """Exact names/aliases only. Questions, negations and compounds stay with existing routing."""
    text = re.sub(r'\s+(?:for me|please)$', '', text.strip(), flags=re.I).casefold()
    if re.match(r"^(?:do not|don't|never|why|what|how)\b", text):
        return None
    rows = catalog()
    aliases = {}
    for r in rows:
        names = [r['task'].casefold()]
        if r['id'] <= 94 and r['command'].startswith('Start-Process'):
            names += ['open '+r['task'].casefold(), 'launch '+r['task'].casefold()]
        if 37 <= r['id'] <= 64:
            names += ['open '+r['task'].casefold()+' settings']
        if r.get('app'):
            names += [r['app']+' '+r['task'].casefold()]
        for name in names:
            aliases.setdefault(name, []).append(r['id'])
    aliases.update({'open settings':[37], 'open chrome':[66], 'open edge':[65],
                    'open vscode':[70], 'open vs code':[70], 'open store':[75],
                    'open camera app':[1], 'open camera':[1], 'open youtube':[88]})
    # Prefer a semantic launch over a keyboard equivalent or duplicate query.
    matches = aliases.get(text, [])
    if len(matches) > 1:
        launching = [i for i in matches if i <= 94 and rows[i-1]['command'].startswith('Start-Process')]
        matches = launching if len(launching) == 1 else matches
    return matches[0] if len(matches) == 1 else None


def parse(text):
    from .commands import Command
    if text.casefold() in {'list windows commands','show windows commands'}:
        return Command('windows_catalog', '.')
    m = re.fullmatch(r'(?:find|search) windows commands(?: for)? (.+)', text, re.I)
    if m:
        return Command('windows_catalog', m[1])
    m = re.fullmatch(r'windows commands? ([\d, ]+)(?:\s+(\{.*\}))?', text, re.I|re.S)
    if m:
        ids = [int(i.strip()) for i in m[1].split(',')]
        return Command('windows_command', json.dumps(ids), m[2] or '{}')
    m=re.fullmatch(r'(.+?)\s+(\{.*\})',text,re.S)
    if m:
        ident=match(m[1])
        if ident:return Command('windows_command',json.dumps([ident]),m[2])
    # Bind explicit spoken/literal hosts and filesystem targets without inference.
    for task,ident in (('dns lookup',193),('check host reachability',194),('traceroute',204)):
        m=re.fullmatch(re.escape(task)+r'\s+([\w.-]{1,200})',text,re.I)
        if m:return Command('windows_command',json.dumps([ident]),json.dumps({'host':m[1]}))
    m=re.fullmatch(r'test tcp port ([\w.-]{1,200}) (\d{1,5})',text,re.I)
    if m:return Command('windows_command','[195]',json.dumps({'host':m[1],'port':int(m[2])}))
    path_token=r'(?:"[^"\r\n]+"|\x27[^\x27\r\n]+\x27|[a-z]:\\[^\s]+)'
    m=re.fullmatch(r'(copy file|move file) ('+path_token+r') to ('+path_token+r')',text,re.I)
    if m:
        return Command('windows_command',json.dumps([143 if m[1].casefold()=='copy file' else 145]),
                       json.dumps({'path1':m[2].strip('\"\x27'),'path2':m[3].strip('\"\x27')}))
    m=re.fullmatch(r'(.+?) ('+path_token+r')',text,re.I)
    if m:
        ident=match(m[1])
        if ident and set(catalog()[ident-1]['parameters'])=={'path1'}:
            return Command('windows_command',json.dumps([ident]),json.dumps({'path1':m[2].strip('\"\x27')}))
    ident = match(text)
    # Preserve established command kinds and compound/UI grammar. The Actions
    # open handler below replaces matching launches without changing parsing.
    if re.match(r'^(?:open|launch|start|press|scroll|use shortcut)\b',text,re.I):
        return None
    return Command('windows_command', json.dumps([ident]), '{}') if ident else None


def prepare(ids, bindings):
    if (not isinstance(ids,list) or not 1 <= len(ids) <= 20 or
            any(type(i) is not int or not 1 <= i <= 493 for i in ids) or not isinstance(bindings,dict)):
        raise ValueError('Use 1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“20 command IDs from 1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“493 and a JSON parameter object.')
    rows = catalog()
    prepared = []
    scoped = len(ids) > 1
    if scoped and set(bindings)-{str(i) for i in ids}:
        raise ValueError('Batch parameters must be keyed by command ID.')
    for i in ids:
        row = rows[i-1]
        params = bindings.get(str(i), {}) if scoped else bindings
        fields = row['parameters']
        # Process examples must never terminate the sample Notepad process by default.
        if i in {103,105,106}:
            fields = {'process_name': {'type':'string','required':True}}
        if not isinstance(params,dict) or set(params)-set(fields):
            raise ValueError('Unknown parameters for command '+str(i)+': '+', '.join(fields))
        missing = set(fields)-set(params)
        if missing:
            raise ValueError('Command '+str(i)+' needs parameters '+', '.join(sorted(missing))+'. Say search windows commands '+str(i)+' for examples.')
        for key,value in params.items():
            if not isinstance(value,(str,int,float,list,tuple,bool)) or isinstance(value,dict) or len(json.dumps(value)) > 10000:
                raise ValueError('Parameters must be bounded literal values.')
            if fields[key]['type']=='integer' and (type(value) is not int or value < 1 or value > (65535 if key=='port' else 2147483647)):
                raise ValueError('Invalid integer parameter '+key)
            if fields[key]['type']=='string' and not isinstance(value,str):
                raise ValueError('String required for '+key)
            if fields[key]['type']=='literal':
                example=fields[key].get('example')
                if isinstance(example,str) and not isinstance(value,str):raise ValueError('Literal text required for '+key)
                if type(example) in {int,bool} and type(value) is not type(example):raise ValueError('Wrong literal type for '+key)
                if isinstance(example,(list,tuple)) and (not isinstance(value,(list,tuple)) or len(value)!=len(example) or any(type(n) is not int for n in value)):
                    raise ValueError('A fixed-size integer coordinate/color tuple is required.')
            if key.startswith('path') or fields[key]['type']=='path':
                if not isinstance(value,str):raise ValueError('Path must be literal text.')
                path = Path(value)
                if not path.is_absolute() or '\x00' in value:
                    raise ValueError('Use an explicit absolute path for '+key)
                # Never recursively move/delete a drive root, junction or symbolic link.
                if i in {144,145,148,149,153}:
                    if any(c in value for c in '*?') or path.resolve()==Path(path.anchor) or path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):
                        raise ValueError('Recursive/file changes require a concrete non-root, non-link target.')
            if key=='app_id' and not re.fullmatch(r'[\w.!-]{1,250}',value):
                raise ValueError('Invalid registered AppUserModelID.')
            if fields[key]['type']=='filename' and (not isinstance(value,str) or not value or any(c in value for c in '<>:"/\\|?*') or value in {'.','..'}):
                raise ValueError('Use one simple new filename.')
            if key in {'host','printer','process_name'} and (not value or len(value)>200 or any(ord(c)<32 for c in value)):
                raise ValueError('Invalid '+key)
        prepared.append((row,params))
    if 294 in ids and (295 not in ids or ids.index(295)<ids.index(294)):
        raise ValueError('Mouse down needs mouse up later in the same batch.')
    kinds = {r['type'] for r,_ in prepared}
    if len(kinds)>1 or any(i>=480 for i in ids) and any(i<480 for i in ids):
        raise ValueError('Use one backend per batch; separate Office batches from other PowerShell recipes.')
    if any(i>=480 for i in ids):
        excel=word=False
        for i in ids:
            if i==480: excel=True
            elif 481<=i<=490 and not excel: raise ValueError('Start an owned Excel instance with command 480 in this batch.')
            if i==491:word=True
            elif i>=492 and not word:raise ValueError('Start an owned Word document with command 491 in this batch.')
            if i in {481,482}: workbook=True
            if 483<=i<=489 and not any(j in ids[:ids.index(i)] for j in {481,482}):
                raise ValueError('Create/open a workbook before worksheet commands.')
            if 484<=i<=487 and 483 not in ids[:ids.index(i)]:
                raise ValueError('Select a worksheet with command 483 first.')
            if i==490:excel=False
    if 482 in ids and 481 in ids:
        raise ValueError('Choose create workbook (481) or open workbook (482), not both in one batch.')
    return prepared


def ps_literal(value):
    return "'"+str(value).replace("'","''")+"'"


def powershell(prepared):
    result = ["$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8",
              "foreach ($m in @('Microsoft.PowerShell.Utility','Microsoft.PowerShell.Management')) { Import-Module (Join-Path $PSHOME ('Modules\\'+$m+'\\'+$m+'.psd1')) -Force }"]
    for row,params in prepared:
        i=row['id']; code=row['command']
        for replacement in sorted(row['replacements'],key=lambda r:r['start'],reverse=True):
            value=params[replacement['parameter']]
            value=ps_literal(value) if replacement['quote'] else str(value)
            code=code[:replacement['start']]+value+code[replacement['end']:]
        if i in {103,105,106}:
            code = ('Wait-Process' if i==106 else 'Stop-Process')+' -Name '+ps_literal(params['process_name'])
            code += ' -Timeout 10' if i==106 else ' -Force' if i==105 else ''
        if i in {103,104,105}:
            import psutil
            # Bind one process, protect Jarvis, its worker children and host chain.
            protected={os.getpid()}
            current=psutil.Process()
            protected.update(p.pid for p in current.parents())
            protected.update(p.pid for p in current.children(recursive=True))
            query='Get-Process -Id '+str(params['pid']) if i==104 else 'Get-Process -Name '+ps_literal(params['process_name'])
            code='$targets=@('+query+'); if ($targets.Count -ne 1) { throw "Name one exact process/PID" }; '
            code+='if (@('+','.join(str(p) for p in sorted(protected))+') -contains $targets[0].Id) { throw "Jarvis or host processes cannot be terminated" }; '
            code+='if ($targets[0].ProcessName -match "^(System|Idle|csrss|lsass|wininit|winlogon|services)$") { throw "Protected system process" }; '
            code+='Stop-Process -Id $targets[0].Id'+(' -Force' if i==105 else '')
        if i==148: code=code.replace('-Confirm','-Confirm:$false')
        if i==146:code='Rename-Item -LiteralPath '+ps_literal(params['path1'])+' -NewName '+ps_literal(params['name'])
        if i==97:code='Get-Process | Where-Object ProcessName -like '+ps_literal(params['pattern'])
        if i==204:code='tracert.exe '+ps_literal(params['host'])
        if i==86: code="Start-Process explorer.exe -ArgumentList "+ps_literal('shell:AppsFolder\\'+params['app_id'])
        if i==171: code="Get-ChildItem Env: | Select-Object Name,@{Name='Value';Expression={'[redacted]'}}"
        if i==180: code='powercfg.exe /batteryreport /output '+ps_literal(params['path1'])
        if i==204: code += ' -h 8 -w 500'
        # Output is an observation/dispatch result, never a fabricated postcondition.
        result.append(". { "+code+" } | Select-Object -First 100 | Out-String -Width 180")
        if re.match(r'^(?:shutdown|rundll32|powercfg|netsh|ipconfig|tracert)\.exe\b',code):
            result.append("if ($LASTEXITCODE -ne 0) { throw 'Native command returned failure' }")
        result.append("Write-Output 'Command "+str(i)+" returned; inspect the result before repeating.'")
    return '\n'.join(result)


def run_ps(script, cancelled, timeout=25):
    if cancelled():raise ValueError('Cancelled before command dispatch.')
    with tempfile.TemporaryDirectory(prefix='jarvis-windows-') as cwd, tempfile.TemporaryFile() as output:
        script_path=Path(cwd)/'recipe.ps1'
        script_path.write_bytes(b'\xef\xbb\xbf'+script.encode('utf-8'))
        child=subprocess.Popen(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script_path)],
            cwd=cwd,stdin=subprocess.DEVNULL,stdout=output,stderr=output,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        end=time.monotonic()+timeout
        try:
            while child.poll() is None:
                if cancelled() or time.monotonic()>end or output.seek(0,2)>1000000:
                    raise ValueError('Windows command stopped/timed out; action may have occurred. Inspect state before retrying.')
                time.sleep(.03)
            output.seek(0); text=output.read(12001).decode('utf-8',errors='replace')
            if child.returncode: raise ValueError('Windows command failed; no replay. '+text[:4000])
            return text[:12000]
        finally:
            if child.poll() is None:child.kill()
            child.wait(timeout=2)


def execute(actions, ids, bindings, cancelled=lambda:False):
    prepared=prepare(ids,bindings)  # Entire batch validated before the first effect.
    detail=json.dumps([{'id':r['id'],'task':r['task'],'parameters':p} for r,p in prepared],ensure_ascii=False)
    if any(r['approval'] for r,_ in prepared):
        actions._approve('windows_command',detail,cancelled)
    if cancelled():raise ValueError('Cancelled before Windows command dispatch.')
    actions.report('tool', ('Opening ' if len(ids)==1 and ids[0]<=94 else 'Executing Windows commands ')+', '.join(r['task'] for r,_ in prepared))
    if prepared[0][0]['type']=='PS':
        return run_ps(powershell(prepared),cancelled)
    request={'operation':'windows_commands','ids':ids,'bindings':bindings}
    if prepared[0][0]['type']=='WEB':
        browser=actions._browser()
        request.pop('operation')
        request['url']=browser.last_url
        return json.dumps(browser.request('windows_commands',cancelled,**request),ensure_ascii=False)
    ui=actions._ui(); handle=ui._handle()
    snapshot=ui.runner({'operation':'list','handle':handle,'owner_pid':os.getpid()},cancelled)
    request.update(handle=handle,owner_pid=os.getpid(),signature=snapshot['signature'],target_pid=snapshot.get('target_pid'))
    return json.dumps(ui.runner(request,cancelled),ensure_ascii=False)


# The interpreter admits only these methods on pinned recipe ASTs. No eval/exec,
# import, user attribute names, loops, generated scripts or arbitrary Python.
METHODS = frozenset('press hotkey click rightClick doubleClick middleClick tripleClick moveTo moveRel mouseDown mouseUp dragRel dragTo scroll position size screenshot save pixel pixelMatchesColor locateOnScreen center write keyDown keyUp windows window wait set_focus maximize minimize restore print_control_identifiers child_window click_input window_text goto title get_by_role get_by_label get_by_placeholder locator fill select_option check uncheck get_by_text inner_text'.split())


def interpret(prepared, env, guard=lambda row:None):
    results=[]
    for row,params in prepared:
        substitutions={(r['line'],r['column']):params[r['parameter']] for r in row['replacements']}
        tree=ast.parse(row['command'])
        def value(node):
            pos=(getattr(node,'lineno',None),getattr(node,'col_offset',None))
            if pos in substitutions:return substitutions[pos]
            if isinstance(node,ast.Constant):return node.value
            if isinstance(node,ast.Tuple):return tuple(value(n) for n in node.elts)
            if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -value(node.operand)
            if isinstance(node,ast.Name) and node.id in env:return env[node.id]
            if isinstance(node,ast.Attribute) and node.attr in METHODS|{'first'}:
                obj=value(node.value)
                return getattr(obj,node.attr)
            if isinstance(node,ast.Call):
                if isinstance(node.func,ast.Name) and node.func.id not in {'Desktop','print'}:
                    raise ValueError('Unsupported recipe function.')
                function=value(node.func)
                args=[value(a) for a in node.args]
                kwargs={k.arg:value(k.value) for k in node.keywords if k.arg}
                guard(row)
                return function(*args,**kwargs)
            raise ValueError('Unsupported recipe expression.')
        for statement in tree.body:
            guard(row)
            if isinstance(statement,ast.Assign) and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name):
                env[statement.targets[0].id]=value(statement.value)
            elif isinstance(statement,ast.Expr):
                observed=value(statement.value)
                if observed is not None:results.append(str(observed)[:2000])
            else:raise ValueError('Unsupported recipe statement.')
        results.append('Command '+str(row['id'])+(' observed.' if row['readonly'] else ' dispatched once; outcome needs inspection.'))
    return {'message':'\n'.join(results)[:12000],'verified':all(r['readonly'] for r,_ in prepared)}
