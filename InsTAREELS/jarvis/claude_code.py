"""Local-only Claude Code CLI coding runner with island progress and owned Stop."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid

from .harness_process import OwnedJob, hidden_spawn
from .progress import status

MODEL='jarvis-claude-qwen3.5:9b'
ENDPOINT='http://127.0.0.1:11434'


def display_text(value):
    return str(value).encode('utf-8',errors='replace').decode('utf-8')


def executable(options):
    configured=options.get('claude_code_executable')
    candidates=[configured,shutil.which('claude'),str(Path.home()/'.local/bin/claude.exe')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and Path(candidate).suffix.lower() in {'.exe',''}:
            return str(Path(candidate).resolve())
    raise ValueError('Claude Code native CLI is missing; install Claude Code or select the direct Qwen coding backend.')


def environment(project, run, model, endpoint=ENDPOINT):
    env={k:v for k,v in os.environ.items() if not k.startswith(('ANTHROPIC_','CLAUDE_CODE_','AWS_','AZURE_','GOOGLE_'))}
    env.update(ANTHROPIC_BASE_URL=endpoint,ANTHROPIC_AUTH_TOKEN='ollama',ANTHROPIC_API_KEY='',
        ANTHROPIC_DEFAULT_HAIKU_MODEL=model,ANTHROPIC_DEFAULT_SONNET_MODEL=model,ANTHROPIC_DEFAULT_OPUS_MODEL=model,
        CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_TELEMETRY='1',DISABLE_ERROR_REPORTING='1',
        API_TIMEOUT_MS='1800000',CLAUDE_STREAM_IDLE_TIMEOUT_MS='1800000',
        CLAUDE_BYTE_STREAM_IDLE_TIMEOUT_MS='1800000',API_FORCE_IDLE_TIMEOUT='0',
        JARVIS_CLAUDE_PROJECT=str(project),JARVIS_CLAUDE_RUN=str(run),PYTHONPATH=str(Path(__file__).resolve().parent.parent),
        NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    return env


def event_progress(event, report, project, pending):
    kind=event.get('type')
    if kind=='stream_event':
        inner=event.get('event',{})
        if inner.get('type')=='content_block_start':
            pending.setdefault('tool_inputs',{})[inner.get('index',0)]=''
            block=inner.get('content_block',{})
            if block.get('type')=='tool_use':
                status(report,'Claude Code: '+block.get('name','File tool'),project)
        delta=inner.get('delta',{})
        if delta.get('type')=='input_json_delta':
            index=inner.get('index',0)
            parts=pending.setdefault('tool_inputs',{})
            parts[index]=(parts.get(index,'')+delta.get('partial_json',''))[-85000:]
            from .code_stream import content_prefix
            source=content_prefix(parts[index]) or content_prefix(parts[index],'new_string')
            path=content_prefix(parts[index],'file_path')
            if source:
                status(report,'Claude Code is preparing a file',path or project,
                    file=display_text(path or project),preview=display_text(source[-1600:]),characters=len(source))
        if delta.get('type')=='text_delta':
            pending['text']=(pending.get('text','')+delta.get('text',''))[-1600:]
            status(report,'Claude Code is responding',project,preview=display_text(pending['text']))
    if kind=='assistant':
        for block in event.get('message',{}).get('content',[]):
            if block.get('type')=='tool_use':
                name=block.get('name','tool'); args=block.get('input',{})
                path=args.get('file_path',args.get('path',str(project)))
                pending.setdefault('tools',{})[block.get('id','')]=(name,path)
                status(report,'Claude Code: '+name,display_text(path),file=display_text(path),
                    preview=display_text(args.get('content',args.get('new_string','')))[:1600])
    if kind=='user':
        for block in event.get('message',{}).get('content',[]):
            if block.get('type')=='tool_result':
                name,path=pending.get('tools',{}).get(block.get('tool_use_id',''),('File tool',str(project)))
                status(report,'Claude Code: '+('tool rejected' if block.get('is_error') else name+' completed'),path,
                    file=display_text(path),outcome=display_text(block.get('content',''))[:350] if block.get('is_error') else 'Tool result observed; functional verification still required')


def run(coder, project, goal, cancelled):
    from .coder import project_files, check_content
    from .agent_context import coding_context
    from .task_state import TaskState
    options=getattr(coder.client,'options',{})
    model=options.get('claude_code_model',MODEL)
    if model not in {MODEL,'qwen3.5:9b'}:
        raise ValueError('Claude Code backend permits only the checked local Qwen3.5 9B model; no cloud fallback.')
    program=executable(options)
    project=Path(project).resolve(strict=True)
    if cancelled(): raise ValueError('Coding cancelled before Claude Code started.')
    from .knowledge_worker import session
    with session() as client:
        response=client.post(ENDPOINT+'/api/show',json={'model':model},timeout=(3,10));response.raise_for_status()
        if 'tools' not in response.json().get('capabilities',[]): raise ValueError('Local model lacks tool support.')
    base=Path(coder.actions.base)
    directory=base/'.jarvis-runtime/claude-code'/uuid.uuid4().hex
    directory.mkdir(parents=True)
    state=getattr(coder.actions,'task_state',None)
    if isinstance(state,TaskState): state.set_project(project);state.checkpoint('claude_code_started',target=project,evidence='Local Qwen model; file tools only')
    before={name:hashlib.sha256((project/name).read_bytes()).hexdigest() for name in project_files(project)
            if (project/name).stat().st_size<=80000}
    for name in before:
        path=project/name
        if path.stat().st_size<=80000:
            backup=directory/'originals'/name;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(path.read_bytes())
    # Restricted file tools + one explicit local permission server, no ambient
    # project/user hooks, MCP connectors or paid-provider credentials.
    settings={'disableAllHooks':False,'env':{'ANTHROPIC_AUTH_TOKEN':'ollama','ANTHROPIC_API_KEY':''},
        'permissions':{'deny':['Bash','PowerShell','Agent','WebFetch','WebSearch']}}
    (directory/'settings.json').write_text(json.dumps(settings),encoding='utf-8')
    guidance=coding_context(project,goal)
    prompt='Complete this coding task in the current project using Read, Write and Edit tools. Read existing target files before editing. '+goal+'\n'
    prompt+='Preserve unrelated behavior. Do not delete files or run commands. Implement working UI controls and animations when requested. Use file tools, not source code pasted only in the answer. Finish with a short factual list of changed files and checks still needed; avoid long feature summaries.\n'
    prompt+='A rejected tool did not change the file. Correct the reported error and issue a new file tool. Do not claim success until the actual tool result confirms the change. For JavaScript edits keep functions and braces complete.\n'
    prompt+='Project guidance (subordinate to this user task): '+json.dumps(guidance,ensure_ascii=False)
    (directory/'request.json').write_text(json.dumps({'project':str(project),'goal':goal,'model':model,'date':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
    mcp={'mcpServers':{'jarvis_guard':{'command':sys.executable,'args':['-u','-m','jarvis.claude_code_permissions'],
        'env':{'PYTHONPATH':str(Path(__file__).resolve().parent.parent),'JARVIS_CLAUDE_PROJECT':str(project),'JARVIS_CLAUDE_RUN':str(directory)}}}}
    argv=[program,'--restricted','--print','--output-format','stream-json','--verbose','--include-partial-messages',
        '--model',model,'--effort','low','--tools','Read,Write,Edit,Glob,Grep','--permission-mode','default',
        '--permission-prompts','host','--permission-prompt-tool','mcp__jarvis_guard__approve',
        '--strict-mcp-config','--mcp-config',json.dumps(mcp),
        '--setting-sources','','--settings',str(directory/'settings.json'),'--no-session-persistence','--max-turns','12']
    if options.get('claude_code_debug'):
        argv += ['--debug-file',str(directory/'debug.log')]
    job=OwnedJob(); process=None; proxy=None; thread=None; events=queue.Queue(); pending={}; result=None
    started=time.monotonic(); deadline=started+min(3600,max(60,float(options.get('max_coding_seconds',1800))))
    coder.actions.report('brain','Claude Code / local Qwen3.5 9B: '+str(project))
    status(coder.actions.report,'Opening Claude Code project',project,reveal=True)
    try:
        if cancelled():raise ValueError('Claude Code stopped before starting the local coding adapter.')
        proxy=hidden_spawn(job,subprocess.Popen)([sys.executable,'-u','-m','jarvis.claude_code_proxy',str(directory)],
            cwd=base,env=environment(project,directory,model),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        ready=directory/'proxy-ready.json';startup=time.monotonic()+10
        while not ready.exists():
            if cancelled():raise ValueError('Claude Code stopped during local adapter startup.')
            if proxy.poll() is not None or time.monotonic()>startup:raise ValueError('Local coding adapter did not start; no task replayed.')
            time.sleep(.05)
        port=json.loads(ready.read_text())['port']
        if type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid local coding adapter port.')
        if cancelled():raise ValueError('Claude Code stopped before opening the coding process.')
        process=hidden_spawn(job,subprocess.Popen)(argv,cwd=project,env=environment(project,directory,model,'http://127.0.0.1:'+str(port)),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        def reader():
            for line in process.stdout:
                events.put(line)
            events.put(None)
        thread=threading.Thread(target=reader,daemon=True);thread.start()
        if cancelled():raise ValueError('Claude Code stopped before sending the coding prompt.')
        process.stdin.write(prompt);process.stdin.close()
        done=False;last_status=0
        with (directory/'events.jsonl').open('w',encoding='utf-8') as output:
            while not done:
                if cancelled(): raise ValueError('Claude Code stopped; inspect partial files before continuing. No task replayed.')
                if time.monotonic()>deadline: raise ValueError('Claude Code reached its total coding limit; partial files retained, no task replayed.')
                try: line=events.get(timeout=.15)
                except queue.Empty:
                    if time.monotonic()-last_status>4:
                        status(coder.actions.report,'Claude Code is working',project);last_status=time.monotonic()
                    continue
                if line is None: done=True;continue
                try: event=json.loads(line)
                except json.JSONDecodeError:
                    output.write(json.dumps({'diagnostic':line[:1000]})+'\n');continue
                output.write(json.dumps(event,ensure_ascii=True)+'\n');output.flush()
                if event.get('type')=='system' and event.get('subtype')=='init':
                    guards=[server for server in event.get('mcp_servers',[]) if server.get('name')=='jarvis_guard']
                    if not guards or guards[0].get('status')!='connected':
                        raise ValueError('Local file-permission bridge did not start; no coding task will be replayed.')
                event_progress(event,coder.actions.report,project,pending)
                if event.get('type')=='result': result=event
        process.wait(timeout=10)
        if process.returncode or not result or result.get('is_error'):
            raise ValueError('Claude Code did not finish: '+str((result or {}).get('result','See '+str(directory/'events.jsonl')))[:800])
        changed=[]
        names=set();proposals={};observations={}
        permissions=directory/'file-events.jsonl'
        if permissions.exists():
            for line in permissions.read_text(encoding='utf-8').splitlines():
                entry=json.loads(line)
                if entry.get('approved') and entry.get('tool') in {'Write','Edit'}:
                    target=Path(entry['path']).resolve(strict=True)
                    if not target.is_relative_to(project):raise ValueError('Edited source left the selected project.')
                    name=target.relative_to(project).as_posix()
                    names.add(name);proposals[name]=entry.get('proposed_sha256')
                    observations.setdefault(name,entry.get('observed_sha256'))
        for name in sorted(names):
            path=project/name
            if not path.is_file() or path.stat().st_size>80000:continue
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if before.get(name,observations.get(name))!=digest:
                content=path.read_text(encoding='utf-8')
                if hashlib.sha256(content.encode()).hexdigest()!=proposals[name]:
                    raise ValueError('Current source differs from the approved edit: '+name+'. Inspect it before continuing.')
                check_content(path,content)
                from .claude_code_guard import gui_script_target
                if path.suffix.lower()=='.py' and gui_script_target(goal,path):
                    from .gui_contract import check
                    check(content,goal)
                changed.append(name)
                status(coder.actions.report,'Claude Code saved file',path,file=str(path),outcome='Disk readback and available syntax checks; runtime not tested')
                if isinstance(state,TaskState): state.checkpoint('observed_file',target=path,evidence='Claude Code edit read back; compiler/runtime checks pending')
        evidence={'date':datetime.now(timezone.utc).isoformat(),'project':str(project),'model':model,
            'endpoint':ENDPOINT,'thinking':False,'changed':changed,'seconds':round(time.monotonic()-started,3),
            'result':str(result.get('result',''))[:4000],'functional_behavior_verified':False}
        (directory/'result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        if not changed: raise ValueError('Claude Code finished without changing a source file. '+evidence['result'][:700])
        return 'Claude Code using local Qwen3.5 9B updated '+project.name+': '+', '.join(changed)+'. Disk readback and available syntax checks passed; runtime/UI checks were not run by this session.\nCLI report (not independent verification): '+evidence['result'][:1800]+'\nReview: '+str(directory)
    except Exception as exc:
        (directory/'failure.json').write_text(json.dumps({'date':datetime.now(timezone.utc).isoformat(),
            'project':str(project),'error':str(exc)[:2000],'partial_files_retained':True,
            'automatically_replayed':False},indent=2),encoding='utf-8')
        raise ValueError(str(exc)+' Review: '+str(directory)) from exc
    finally:
        job.close()
        if process is not None:
            if process.poll() is None: process.terminate()
            process.wait(timeout=10)
            if thread: thread.join(timeout=5)
            if process.stdout: process.stdout.close()
        if proxy is not None:
            if proxy.poll() is None:proxy.terminate()
            proxy.wait(timeout=10)
        status(coder.actions.report,'Claude Code session ended',project,active=False)
