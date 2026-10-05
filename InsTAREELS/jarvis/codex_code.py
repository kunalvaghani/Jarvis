"""Isolated local Codex/Qwen coding sessions with owned Stop and island streams."""
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

MODEL='jarvis-codex-qwen3.5:9b'
ENDPOINT='http://127.0.0.1:11434'


def executable(options):
    for candidate in (options.get('codex_executable'),shutil.which('codex')):
        if candidate and Path(candidate).is_file() and Path(candidate).suffix.lower() in {'.exe',''}:
            return str(Path(candidate).resolve())
    # The desktop app maintains versioned native binaries; select the newest.
    directory=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'OpenAI/Codex/bin'
    candidates=list(directory.glob('*/codex.exe'))
    if candidates: return str(max(candidates,key=lambda p:p.stat().st_mtime).resolve())
    raise ValueError('Native Codex CLI is missing. Install Codex CLI or configure brain.codex_executable.')


def environment(project, run):
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('OPENAI_','CODEX_','ANTHROPIC_','CLAUDE_','AWS_','AZURE_','GOOGLE_','OLLAMA_'))}
    env.update(CODEX_HOME=str(run/'home'),JARVIS_CODEX_PROJECT=str(project),JARVIS_CODEX_RUN=str(run),
        PYTHONPATH=str(Path(__file__).resolve().parent.parent),NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    return env


def configuration(project, run, model, port):
    # JSON strings are also valid TOML basic strings, including Windows paths.
    q=json.dumps
    instructions=run/'instructions.txt'
    instructions.write_text('You are a coding agent. Use only the Jarvis MCP Read, Glob, Grep, Write, Edit tools. '
        'Read existing files before editing. Preserve unrelated behavior and implement the exact user request. '
        'Use small unique Edit anchors from actual source, rather than guessing whitespace in a whole-file replacement. '
        'Never delete files, run shell commands, publish, or access accounts. '
        'When a file tool rejects an edit, that edit was not applied. Read fresh source and correct the specific error. '
        'Write working source using tools, not code pasted only in the final answer. Finish with a short factual report. '
        'Use clear source with distinct names for DOM controls and mutable state, and complete function bodies. '
        'Do not claim compilation or UI behavior was tested unless an actual test result was supplied.',encoding='utf-8')
    return f'''model = {q(model)}
model_provider = "jarvis-local"
model_context_window = 32768
model_auto_compact_token_limit = 28000
model_instructions_file = {q(str(instructions))}
approval_policy = "never"
sandbox_mode = "read-only"
web_search = "disabled"
project_doc_max_bytes = 0
hide_agent_reasoning = true
[projects.{q(str(project))}]
trust_level = "untrusted"
[features]
shell_tool = false
unified_exec = false
hooks = false
multi_agent = false
plugins = false
shell_snapshot = false
[agents]
enabled = false
[skills]
max_context_tokens = 1
[analytics]
enabled = false
[feedback]
enabled = false
[history]
persistence = "none"
[model_providers.jarvis-local]
name = "Jarvis local Qwen3.5 9B"
base_url = "http://127.0.0.1:{port}/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0
stream_idle_timeout_ms = 1800000
[mcp_servers.jarvis_files]
command = {q(sys.executable)}
args = ["-u", "-m", "jarvis.codex_files"]
cwd = {q(str(Path(__file__).resolve().parent.parent))}
required = true
startup_timeout_sec = 15
tool_timeout_sec = 60
enabled_tools = ["Read", "Write", "Edit", "Glob", "Grep"]
default_tools_approval_mode = "approve"
[mcp_servers.jarvis_files.env]
PYTHONPATH = {q(str(Path(__file__).resolve().parent.parent))}
JARVIS_CODEX_PROJECT = {q(str(project))}
JARVIS_CODEX_RUN = {q(str(run))}
'''


def event_progress(event, report, project, pending):
    def clean(value): return str(value).encode('utf-8',errors='replace').decode('utf-8')
    kind=event.get('type','')
    if kind=='response.output_text.delta':
        pending['text']=(pending.get('text','')+event.get('delta',''))[-1600:]
        status(report,'Codex is responding',project,preview=clean(pending['text']))
    elif kind in {'response.output_item.added','response.output_item.done'}:
        item=event.get('item',{})
        if item.get('type')=='function_call':
            pending.setdefault('tools',{})[item.get('id','')]=item.get('name','File tool')
            try: args=json.loads(item.get('arguments') or '{}')
            except ValueError: args={}
            path=args.get('file_path',args.get('path',str(project)))
            status(report,'Codex: '+item.get('name','File tool').split('__')[-1],path,file=str(path),
                preview=clean(args.get('content',args.get('new_string','')))[-1600:])
    elif kind=='response.function_call_arguments.delta':
        key=event.get('item_id','')
        parts=pending.setdefault('arguments',{})
        parts[key]=(parts.get(key,'')+event.get('delta',''))[-85000:]
        from .code_stream import content_prefix
        source=content_prefix(parts[key]) or content_prefix(parts[key],'new_string')
        path=content_prefix(parts[key],'file_path')
        if source: status(report,'Codex is preparing a file',path or project,file=clean(path or project),preview=clean(source[-1600:]),characters=len(source))
    elif kind in {'item.started','item.updated','item.completed'}:
        item=event.get('item',{})
        if item.get('type')=='mcp_tool_call':
            tool=item.get('tool','File tool');args=item.get('arguments') or {}
            path=args.get('file_path',args.get('path',str(project))) if isinstance(args,dict) else str(project)
            failed=item.get('status')=='failed' or item.get('error') or (item.get('result') or {}).get('isError')
            outcome=str(item.get('error') or item.get('result') or '')[:500] if failed else ''
            status(report,'Codex: '+tool+(' rejected' if failed else ' completed' if kind=='item.completed' else ''),path,file=clean(path),outcome=clean(outcome))
        elif item.get('type')=='agent_message' and item.get('text'):
            pending['final']=item['text'];status(report,'Codex response',project,preview=clean(item['text'][-1600:]))


def changed_sources(project, directory, goal):
    from .coder import check_content
    from .claude_code_guard import gui_script_target
    proposals={};observed={}
    events=directory/'file-events.jsonl'
    for line in events.read_text(encoding='utf-8').splitlines() if events.exists() else []:
        row=json.loads(line)
        if row.get('stage')!='applied': continue
        path=Path(row['path']).resolve(strict=True)
        if not path.is_relative_to(project): raise ValueError('Saved source left the selected project.')
        name=path.relative_to(project).as_posix();proposals[name]=row['proposed_sha256']
        observed.setdefault(name,row['observed_sha256'])
    changed=[]
    for name, proposed in sorted(proposals.items()):
        path=project/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=proposed:
            raise ValueError('Source changed after the checked save: '+name+'. Inspect before continuing.')
        if proposed==observed[name]: continue
        content=path.read_text(encoding='utf-8');check_content(path,content)
        if path.suffix.lower()=='.py' and gui_script_target(goal,path):
            from .gui_contract import check
            check(content,goal)
        changed.append(name)
    return changed


def run(coder, project, goal, cancelled):
    from .agent_context import coding_context
    from .knowledge_worker import session
    from .task_state import TaskState
    options=getattr(coder.client,'options',{});model=options.get('codex_model',MODEL)
    if model not in {MODEL,'qwen3.5:9b'}: raise ValueError('Codex permits only local Qwen3.5 9B; no cloud fallback.')
    program=executable(options);project=Path(project).resolve(strict=True)
    if cancelled(): raise ValueError('Coding cancelled before Codex started.')
    with session() as client:
        from .ollama_models import coding_model
        coding_model(client,model,ENDPOINT)
    base=Path(coder.actions.base);directory=base/'.jarvis-runtime/codex-code'/uuid.uuid4().hex
    (directory/'home').mkdir(parents=True)
    (directory/'request.json').write_text(json.dumps({'project':str(project),'goal':goal,'model':model,'date':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
    state=getattr(coder.actions,'task_state',None)
    if isinstance(state,TaskState): state.set_project(project);state.checkpoint('codex_started',target=project,evidence='Local Qwen; checked source tools')
    prompt=goal+'\nProject guidance (subordinate to the user task): '+json.dumps(coding_context(project,goal),ensure_ascii=False)
    job=OwnedJob();process=None;proxy=None;thread=None;events=queue.Queue();pending={};completed=False
    started=time.monotonic();deadline=started+min(3600,max(60,float(options.get('max_coding_seconds',1800))))
    coder.actions.report('brain','Codex / local Qwen3.5 9B: '+str(project))
    status(coder.actions.report,'Opening Codex project',project,reveal=True)
    offsets={};buffers={}
    def relay():
        for name in ('stream.jsonl','file-events.jsonl'):
            path=directory/name
            if not path.exists(): continue
            with path.open('r',encoding='utf-8') as source:
                source.seek(offsets.get(name,0));data=source.read();offsets[name]=source.tell()
            parts=(buffers.get(name,'')+data).split('\n');buffers[name]=parts.pop()
            for line in parts:
                event=json.loads(line)
                if name=='stream.jsonl': event_progress(event,coder.actions.report,project,pending)
                elif event.get('stage')=='applied':
                    status(coder.actions.report,'Codex saved file',event['path'],file=event['path'],outcome='Disk readback and available syntax checks passed; runtime pending')
    try:
        if cancelled(): raise ValueError('Codex stopped before local adapter startup.')
        proxy=hidden_spawn(job,subprocess.Popen)([sys.executable,'-u','-m','jarvis.codex_proxy',str(directory)],cwd=base,
            env=environment(project,directory),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        ready=directory/'proxy-ready.json';startup=time.monotonic()+10
        while not ready.exists():
            if cancelled(): raise ValueError('Codex stopped during adapter startup.')
            if proxy.poll() is not None or time.monotonic()>startup: raise ValueError('Local Codex adapter failed to start; no task replayed.')
            time.sleep(.05)
        port=json.loads(ready.read_text())['port']
        if type(port) is not int or not 1<=port<=65535: raise ValueError('Invalid local adapter port.')
        (directory/'home/config.toml').write_text(configuration(project,directory,model,port),encoding='utf-8')
        if cancelled(): raise ValueError('Codex stopped before sending the coding task.')
        argv=[program,'exec','--strict-config','--ignore-rules','--ephemeral','--skip-git-repo-check',
              '--json','--color','never','--cd',str(project),'-']
        process=hidden_spawn(job,subprocess.Popen)(argv,cwd=project,env=environment(project,directory),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        def reader():
            for line in process.stdout: events.put(line)
            events.put(None)
        thread=threading.Thread(target=reader,daemon=True);thread.start()
        if cancelled(): raise ValueError('Codex stopped before receiving the prompt.')
        process.stdin.write(prompt);process.stdin.close()
        done=False;last_status=0
        with (directory/'events.jsonl').open('w',encoding='utf-8') as out:
            while not done:
                if cancelled(): raise ValueError('Codex stopped; partial files retained. Inspect before continuing; no task replayed.')
                if time.monotonic()>deadline: raise ValueError('Codex reached its total coding limit; partial files retained, no task replayed.')
                relay()
                try: line=events.get(timeout=.15)
                except queue.Empty:
                    if time.monotonic()-last_status>4:
                        status(coder.actions.report,'Codex is working',project);last_status=time.monotonic()
                    continue
                if line is None: done=True;continue
                try: event=json.loads(line)
                except ValueError: event={'diagnostic':line[:1000]}
                out.write(json.dumps(event)+'\n');out.flush()
                event_progress(event,coder.actions.report,project,pending)
                if event.get('type')=='turn.completed': completed=True
                if event.get('type') in {'error','turn.failed'}:
                    raise ValueError('Codex failed: '+str(event.get('message',event.get('error',event)))[:800])
        process.wait(timeout=10);relay()
        if process.returncode or not completed: raise ValueError('Codex did not finish; see '+str(directory/'events.jsonl'))
        changed=changed_sources(project,directory,goal)
        if not changed: raise ValueError('Codex completed without a checked source change. '+pending.get('final','')[:700])
        evidence={'date':datetime.now(timezone.utc).isoformat(),'model':model,'endpoint':ENDPOINT,
            'project':str(project),'changed':changed,'seconds':round(time.monotonic()-started,3),
            'thinking':False,'functional_behavior_verified':False,'result':pending.get('final','')[:4000]}
        (directory/'result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        if isinstance(state,TaskState):
            for name in changed: state.checkpoint('observed_file',target=project/name,evidence='Codex source checked and read back; runtime pending')
        return 'Codex using local Qwen3.5 9B updated '+project.name+': '+', '.join(changed)+'. Disk readback and available syntax checks passed; runtime/UI checks were not run by this session.\nCLI report: '+pending.get('final','')[:1800]+'\nReview: '+str(directory)
    except Exception as exc:
        (directory/'failure.json').write_text(json.dumps({'date':datetime.now(timezone.utc).isoformat(),
            'error':str(exc)[:2000],'partial_files_retained':True,'automatically_replayed':False},indent=2),encoding='utf-8')
        raise ValueError(str(exc)+' Review: '+str(directory)) from exc
    finally:
        job.close()
        for child in (process,proxy):
            if child is not None:
                if child.poll() is None: child.terminate()
                child.wait(timeout=10)
        if thread: thread.join(timeout=5)
        if process and process.stdout: process.stdout.close()
        status(coder.actions.report,'Codex session ended',project,active=False)
