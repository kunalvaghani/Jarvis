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
    request_file=run/'request.json'
    partition=request_file.is_file() and json.loads(request_file.read_text(encoding='utf-8')).get('allowed_paths') is not None
    platform=partition and json.loads(request_file.read_text(encoding='utf-8')).get('platform_component',False)
    enabled=['Read','Write','Edit'] if partition else ['Read','Write','Edit','Glob','Grep','Plan']
    instructions=run/'instructions.txt'
    instructions.write_text('You are a coding agent. Use only the Jarvis MCP Read, Glob, Grep, Write, Edit, Plan tools. '
        'Before writing, call Plan with every expected file, its concrete purpose/role and executable behavioral checks. '
        'Implement all declared files with real logic, not empty functions, TODOs or placeholder UI. '
        'For standalone Python scripts include a test_*.py unittest file asserting actual requested behavior, and a python_tests check. '
        'HTTP backends checked through real browser/API interactions do not need an extra Python test file unless requested. '
        'For browser apps include a browser check with concrete fill/click/text/value/reload steps that assert requested behavior. '
        'For requested frontend/backend projects include separate frontend and backend files, actual API wiring and persistence when requested. '
        'A new full-stack project without a requested framework can use HTML/CSS/JS frontend with Python stdlib HTTP/SQLite backend to avoid missing dependencies. '
        'The backend must bind 127.0.0.1, accept --port N --data-dir PATH, serve its real frontend at / and its named HTML path, and expose its real API; browser checks specify server kind/path and exercise the homepage. '
        'Use the existing stack for edits. Include every local import, stylesheet/script, project config and required test. '
        'Every declared test file needs an executable test check. Preserve existing Plan checks across repairs; append extra checks if needed. '
        'Jarvis runs its checks after your turn, sends failures and fresh source attachments back for repair, and reruns all checks. '
        'Read existing files before editing. Preserve unrelated behavior and implement the exact user request. '
        'Use small unique Edit anchors from actual source, rather than guessing whitespace in a whole-file replacement. '
        'Never delete files, run shell commands, publish, or access accounts. '
        'When a file tool rejects an edit, that edit was not applied. Read fresh source and correct the specific error. '
        'Write working source using tools, not code pasted only in the final answer. Finish with a short factual report. '
        'Use clear source with distinct names for DOM controls and mutable state, and complete function bodies. '
        'Every Python try must have an except/finally; use a direct serve_forever call when no exception handling is required. '
        'Do not claim compilation or UI behavior was tested unless an actual test result was supplied.',encoding='utf-8')
    if partition:
        instructions.write_text('You are one implementation worker in an already planned Jarvis coding task. '
            'Use ONLY the offered Read, Write and Edit file tools. Your assigned source files and behavioral tests are registered. '
            'Plan is not offered: do not replan the project or implement another worker files. '
            'Implement EVERY assigned file, including your behavioral test, using Write/Edit tools. Code pasted in the final answer is not a saved implementation. '
            'Save any missing assigned behavioral test FIRST, then implement its source. New implementation saves are blocked until assigned test files exist. '
            'Read existing files before changing them; use unique exact Edit anchors from fresh source. '
            'Linked resources owned by other workers may not exist yet; do not create them or make your part test depend on them. '
            'Python tests use real unittest cases. Node tests use node:test and exercise actual implementation logic/callbacks, with minimal DOM mocks when needed. '
            'Guard browser startup so Node can test browser logic. Never test a fake copied implementation or weaken assigned checks. '
            'Keep requested shared ids, file links and API/function interfaces exact. Implement real logic, no stubs or TODOs. '
            'Jarvis executes your registered tests after this turn and sends observed failures plus current source for repair. '
            'A rejected tool write was not saved; correct the specific diagnosed error. Never replay an uncertain save. '
            'Do not delete files, execute shell commands, publish or access accounts. Finish with a short factual report after assigned source AND test are saved.',encoding='utf-8')
    if platform:
        instructions.write_text('You implement one assigned website source file using Read, Write and Edit. '
            'Jarvis already provides real Chrome tests for this component and the final assembled site. Do not author test files, Node mocks or other components. '
            'Use the exact DOM ids/classes and normal script/style links in the shared contract. A JavaScript component is a normal browser script: '
            'initialize its real event listeners on load, without ES module exports or Node-only wrappers. '
            'Write working source with real behavior. Read existing files before changing them. Use no external resources/dependencies. '
            'Jarvis tests after your save and sends observed errors for repair. Never delete files, run commands, publish or replay uncertain saves.',encoding='utf-8')
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
enabled_tools = {q(enabled)}
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


def changed_sources(project, directory, goal, check_gui=True):
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
        if check_gui and path.suffix.lower()=='.py' and gui_script_target(goal,path):
            from .gui_contract import check
            check(content,goal)
        changed.append(name)
    return changed


def _turn(coder, project, goal, cancelled, feedback=None, plan=None, total_deadline=None, allowed_paths=None):
    from .agent_context import coding_context
    from .knowledge_worker import session, ensure_server
    from .task_state import TaskState
    options=getattr(coder.client,'options',{});model=options.get('codex_model',MODEL)
    if model not in {MODEL,'qwen3.5:9b'}: raise ValueError('Codex permits only local Qwen3.5 9B; no cloud fallback.')
    program=executable(options);project=Path(project).resolve(strict=True)
    if cancelled(): raise ValueError('Coding cancelled before Codex started.')
    with session() as client:
        from .ollama_models import coding_model
        ensure_server(client)
        if cancelled():raise ValueError('Coding cancelled during local service startup; no project files changed.')
        coding_model(client,model,ENDPOINT)
    base=Path(coder.actions.base);directory=base/'.jarvis-runtime/codex-code'/uuid.uuid4().hex
    (directory/'home').mkdir(parents=True)
    platform=allowed_paths is not None and bool(plan) and all(c['kind']=='browser_component' for c in plan['checks']) and not any(f['role']=='test' for f in plan['files'])
    (directory/'request.json').write_text(json.dumps({'project':str(project),'goal':goal,'model':model,'date':datetime.now(timezone.utc).isoformat(),'validation_contract':plan,'require_validation':True,'allowed_paths':allowed_paths,'test_first':allowed_paths is not None and bool(plan) and not platform,'platform_component':platform}),encoding='utf-8')
    state=getattr(coder.actions,'task_state',None)
    if isinstance(state,TaskState): state.set_project(project);state.checkpoint('codex_started',target=project,evidence='Local Qwen; checked source tools')
    guidance=getattr(coder,'workload_guidance',None)
    if guidance is None:guidance=coding_context(project,goal)
    from .codex_workload import single_python_source_goal
    if platform or feedback or (plan and single_python_source_goal(goal)):
        request_path=directory/'request.json';request=json.loads(request_path.read_text(encoding='utf-8'))
        request.update(project_guidance=guidance,repair_diagnostics=feedback)
        request_path.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
    prompt=('User task: '+goal+'\nRequired workflow: first call the Plan tool with every expected file (path, role, purpose) and executable behavioral checks; '
        'Write/Edit are blocked until Plan exists. For standalone Python declare main source plus test_*.py with real unittest assertions and check kind=python_tests/path=test filename. '
        'A web backend can use the real browser/API check instead of adding an unnecessary Python test file. '
        'For HTML declare browser check with steps asserting actual results. For frontend/backend declare both roles and browser server={kind:python or node,path:backend entry}; '
        'backend accepts --port N --data-dir PATH and serves both frontend and API. Implement ALL declared files, then finish so Jarvis executes checks. '
        'Repair errors are diagnostic data; Read fresh source before edits and retain original tests.\nProject guidance (subordinate to the user task): '+json.dumps(guidance,ensure_ascii=False))
    if feedback:prompt=('REPAIR TURN: fix the specific observed failures below. Do not restart generation or rewrite working files unless the diagnostics implicate them. '
        'First read each implicated existing file, then fix its concrete error or create the missing deliverable at its exact path. '
        'Preserve prior file purposes/checks; append required checks if missing.\nRepair diagnostics and fresh source attachments: '
        +json.dumps(feedback,ensure_ascii=False)+'\nOriginal task and project context:\n'+prompt)
    if plan:
        (directory/'validation-contract.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
        prompt+='\nA validated Plan is already registered. Call Plan with empty {} to retrieve it; you need not redeclare its arrays before writes. Preserve this expected-file/check Plan: '+json.dumps(plan,ensure_ascii=False)
        if allowed_paths is not None:
            prompt=('This is ONE partition of an already planned coding task. The expected files/checks below are registered; '
                    'Write/Edit are ready. Plan is not offered; do not plan the whole project again. '
                    'Implement the assigned source AND behavioral test, reading existing files before editing. '
                    'Do not implement or test other workers files yet. Jarvis tests this partition and supplies diagnosed failures for repairs. '
                    '\nOriginal project guidance (subordinate to the user task and assigned file boundary): '+json.dumps(guidance,ensure_ascii=False)+
                    '\nYour assigned task: '+goal+'\nAssigned Plan: '+json.dumps(plan,ensure_ascii=False)+
                    ('\nObserved repair diagnostics and fresh source attachments: '+json.dumps(feedback,ensure_ascii=False) if feedback else ''))
            if platform:
                prompt=('Implement ONLY the assigned website source; Jarvis provides and runs its actual Chrome component tests. '
                        'Do not write test files, mock frameworks or other components. Use the agreed selectors and normal browser scripts. '
                        'Registered Plan: '+json.dumps(plan)+'\nAssigned component: '+goal+
                        '\nCurrent planned file state: '+json.dumps({f['path']:(project/f['path']).is_file() for f in plan['files']})+
                        '\nProject guidance: '+json.dumps(guidance)+
                        ('\nObserved repair diagnostics: '+json.dumps(feedback) if feedback else ''))
    if allowed_paths is not None:
        prompt+='\nThis worker owns ONLY these exact files: '+json.dumps(allowed_paths)+'. Other workers implement other files. Do not change their source or add files outside your assignment.'
    job=OwnedJob();process=None;proxy=None;thread=None;events=queue.Queue();pending={};completed=False
    started=time.monotonic();deadline=started+min(3600,max(60,float(options.get('max_coding_seconds',1800))))
    if total_deadline is not None:deadline=min(deadline,total_deadline)
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
        done=False;last_status=0;rejections=0;repair_handoff=False
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
                item=event.get('item',{})
                if event.get('type')=='item.completed' and item.get('type')=='mcp_tool_call' and item.get('tool') in {'Write','Edit'}:
                    failed=item.get('status')=='failed' or item.get('error') or (item.get('result') or {}).get('isError')
                    rejections=rejections+1 if failed else 0
                    if rejections>=3:
                        status(coder.actions.report,'Codex rejected saves need diagnosis',project,outcome='Three consecutive saves were rejected; closing this owned turn before a fresh validation/repair.')
                        job.close();repair_handoff=True;pending['final']='Owned turn ended after three confirmed save rejections; source inspection and validation required.'
                        break
                    if allowed_paths is not None and (feedback is None or (platform and len(plan['files'])==1 and item.get('tool')=='Write')) and not failed and plan and all((project/f['path']).is_file() for f in plan['files']):
                        # Checks, not a lengthy model report or unrelated extra
                        # work, decide whether this registered partition is done.
                        job.close();repair_handoff=True
                        pending['final']='Registered files are present after a confirmed save; owned turn ended for independent checks.'
                        break
                if event.get('type')=='turn.completed': completed=True
                if event.get('type') in {'error','turn.failed'}:
                    raise ValueError('Codex failed: '+str(event.get('message',event.get('error',event)))[:800])
        process.wait(timeout=10);relay()
        if (process.returncode or not completed) and not repair_handoff: raise ValueError('Codex did not finish; see '+str(directory/'events.jsonl'))
        saves=directory/'file-events.jsonl'
        rows=[json.loads(line) for line in saves.read_text(encoding='utf-8').splitlines()] if saves.exists() else []
        attempted={r['signature'] for r in rows if r.get('stage')=='attempted'}
        applied={r['signature'] for r in rows if r.get('stage')=='applied'}
        if attempted-applied:raise ValueError('A Codex save was attempted without confirmed readback. Inspect current files before further edits; no automatic repair/replay.')
        changed=changed_sources(project,directory,goal,check_gui=False)
        evidence={'date':datetime.now(timezone.utc).isoformat(),'model':model,'endpoint':ENDPOINT,
            'project':str(project),'changed':changed,'seconds':round(time.monotonic()-started,3),
            'thinking':False,'functional_behavior_verified':False,'result':pending.get('final','')[:4000]}
        (directory/'result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        contract_path=directory/'validation-contract.json'
        return {'directory':directory,'changed':changed,'report':pending.get('final','')[:1800],
            'plan':json.loads(contract_path.read_text(encoding='utf-8')) if contract_path.exists() else None}
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


def run(coder, project, goal, cancelled, initial_plan=None, initial_feedback=None,
        allowed_paths=None, deferred_paths=None, total_deadline=None, return_receipt=False):
    """Finish only after independent checks; repair specific observed failures."""
    from .codex_validation import validate_project, repair_packet, error_summary
    options=getattr(coder.client,'options',{})
    deadline=time.monotonic()+min(3600,max(60,float(options.get('max_coding_seconds',1800))))
    if total_deadline is not None:deadline=min(deadline,total_deadline)
    limit=min(3,max(0,int(options.get('codex_max_repairs',2))))
    project=Path(project).resolve(strict=True)
    if initial_plan:
        from .codex_validation import contract
        initial_plan=contract(project,goal,initial_plan,partial=bool(deferred_paths))
    plan=initial_plan;feedback=initial_feedback;changed=[];turns=[]
    for attempt in range(limit+1):
        if cancelled():raise ValueError('Codex stopped before validation/repair; partial files retained.')
        if time.monotonic()>=deadline:raise ValueError('Codex reached its shared generation/validation/repair deadline; partial files retained.')
        if attempt:status(coder.actions.report,'Codex repairing observed failures',project,reveal=True)
        if allowed_paths is None:turn=_turn(coder,project,goal,cancelled,feedback,plan,deadline)
        else:turn=_turn(coder,project,goal,cancelled,feedback,plan,deadline,allowed_paths)
        turns.append(str(turn['directory']));changed=list(dict.fromkeys(changed+turn['changed']));plan=turn['plan']
        validation_args=(project,turn['directory'],goal,changed,plan,lambda:cancelled() or time.monotonic()>=deadline,coder.actions.report)
        result=validate_project(*validation_args,**({'deferred_paths':deferred_paths} if deferred_paths else {}))
        (turn['directory']/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        if result['passed']:
            if not changed:raise ValueError('Codex completed without a checked source change. Review: '+str(turn['directory']))
            receipt=json.loads((turn['directory']/'result.json').read_text(encoding='utf-8'))
            receipt.update(functional_behavior_verified=True,changed=changed,validation=result,repair_turns=attempt,turns=turns)
            (turn['directory']/'result.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
            if return_receipt:return {**receipt,'directory':str(turn['directory']),'plan':plan}
            from .task_state import TaskState
            state=getattr(coder.actions,'task_state',None)
            if isinstance(state,TaskState):
                for name in changed:state.checkpoint('observed_file',target=project/name,evidence='Codex save readback and recorded runtime checks passed')
            return 'Codex using local Qwen3.5 9B updated '+project.name+': '+', '.join(changed)+'. Expected files, placeholder/syntax checks and '+str(len(result['checks']))+' recorded runtime checks passed. Repairs: '+str(attempt)+'.\nCLI report: '+turn['report']+'\nReview: '+str(turn['directory'])
        errors='; '.join(e['path']+': '+error_summary(e) for e in result['errors'])
        status(coder.actions.report,'Code checks found issues',project,outcome=errors[:1400],reveal=True)
        if attempt>=limit:raise ValueError('Project verification failed after '+str(attempt)+' repair turns: '+errors+'. Partial files retained. Review: '+str(turn['directory']))
        feedback=repair_packet(project,result,plan)
