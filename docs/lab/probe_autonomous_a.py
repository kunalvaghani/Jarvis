"""Natural-language Test A attempt with a read-only live event monitor.

No prepared vehicle JSON, asset, script, solver result or suggested answer is
supplied to Jarvis. These diagnostic attempts cannot certify full acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'app'
sys.path.insert(0, str(APP))
GOALS = {
 'A1': 'Find a legal free downloadable 2025 McLaren F1 model. Verify its license and identity; say if it is only a concept or visual replica. Build an editable simulation-ready vehicle with separated moving components and explicitly marked physical assumptions. Run real Chrono vehicle dynamics, change the front-wing angle, and compare baseline versus candidate under exactly the same track, environment and power-unit model. Save native editable files, solver inputs, raw numerical outputs, provenance and a reproducible report. Do the work through your available tools; do not claim completion if a required capability or permission is unavailable. No paid usage, new installs, arbitrary downloaded/generated host scripts, purchases or account writes are authorized.',
 'A2': 'Find a legal free model for a 2026-regulation F1 car and verify its license and era identity. Build an editable simulation-ready vehicle and run real Chrono vehicle dynamics with front and rear active aero: Corner Mode and Straight Mode coefficient sets, switched by designated track zones. Increase only the Corner Mode front-flap angle by 2 degrees and compare cornering, top speed and energy use, keeping Straight Mode, track, environment and power-unit model fixed. Mark guessed coefficients and unavailable proprietary data. Save native source, separated moving components, mode trace, raw results, source provenance and a reproducible report. Do the work through your available tools; never claim completion without execution evidence. No paid usage, new installs, arbitrary downloaded/generated host scripts, purchases or account writes are authorized.'}


def source_fingerprint():
    sys.path.insert(0,str(Path(__file__).parent))
    from run_checks import source_fingerprint as fingerprint
    return fingerprint()


def goal_for(case,surrogate_scope=False):
    return GOALS[case]+(' If no suitable exact engineering asset is usable, I explicitly permit a clearly labelled regulation-referenced F1-class surrogate; do not call it exact team CAD.' if surrogate_scope else '')


def worker(home, case, max_seconds, max_calls,surrogate_scope=False,approve_owned_project=False):
    from jarvis.actions import Actions, Desktop
    from jarvis.brain import BrainClient
    from jarvis.engine import Engine
    from jarvis.audio import command_text
    from jarvis.commands import Command
    from jarvis.conversation_intent import quick_kind, model_kind, needs_page
    from jarvis.task_state import TaskState
    from jarvis.telemetry.ledger import task_scope
    from jarvis.tools import redact
    config = json.loads((APP/'config/config.json').read_text(encoding='utf-8'))
    config['_ui_verification'] = True
    for provider in ('groq','gemini'):
        config[provider] = {**config.get(provider,{}), 'enabled':False}
    for key in ('memory','knowledge_acquisition'):
        config[key] = {**config.get(key,{}), 'enabled':False}
    config['lab'] = {'enabled':True,'sim':True,'research':True,'learning':False}
    config['neural'] = {**config.get('neural',{}),'mode':'act','learning':'shadow',
                         'journal':(home/'brain.sqlite3').relative_to(APP).as_posix()}
    config['telemetry'] = {**config.get('telemetry',{}),'timing_ledger':True}
    os.environ['JARVIS_BRAIN_MODE'] = 'on'
    def report(kind,value):
        row={'elapsed_s':round(time.monotonic()-started,3),'kind':str(kind),
             'value':redact(str(value))[:16000]}
        with (home/'events-private.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
    started=time.monotonic()
    source_before=source_fingerprint()
    harness_before=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    actions=Actions(config,APP,report,Desktop())
    actions.task_state=TaskState(home/'task-owner')
    actions.skills.task_id_provider=actions.task_state.running_identity
    approvals=[]
    def decline(kind,detail,cancelled):
        if (approve_owned_project and kind=='brain' and str(detail).startswith('discovery.vehicle.scenario. ')
                and not cancelled()):
            approvals.append({'kind':str(kind),'scope':'discovery.vehicle.scenario','answer':'approved',
                'basis':'explicit user instruction to execute and repair full A; bounded public research and owned project work only'})
            report('approval','Approved scoped owned vehicle project under explicit test authorization; other actions remain denied.')
            return True
        approvals.append({'kind':str(kind),'answer':'denied'})
        report('approval','Blocked: '+str(kind))
        return False
    actions.approval_handler=decline
    assert type(actions.brain.client) is BrainClient
    ledger=None
    stop_reason=None
    def cancelled():
        nonlocal stop_reason
        if time.monotonic()-started>max_seconds:stop_reason='harness deadline'
        if ledger is not None and ledger.counts['model_calls']>=max_calls:stop_reason='harness model-call cap'
        return stop_reason is not None
    goal=goal_for(case,surrogate_scope)
    result={'case':case,'goal':goal,'full_acceptance_passed':False,'surrogate_scope_explicit':surrogate_scope,
            'no_prepared_case_json':True,'model_or_solver_patches':False}
    try:
        report('intake',goal)
        with task_scope(config,'autonomous_'+case,home) as ledger:
            commands=[]
            engine=Engine(commands.append,lambda *a:None);engine.activate()
            engine.feed(command_text(goal),final=True,raw=goal)
            if len(commands)!=1:raise ValueError('one ordinary intake required')
            command=commands[0]
            if command.kind=='task' and command.extra=='unparsed':
                kind=quick_kind(command.value) or model_kind(command.value,{
                    'model':config.get('context_selector',{}).get('model','qwen3.5:0.8b'),
                    'timeout_seconds':3.0},cancelled)
                command=Command('ask' if kind=='chat' else 'task',command.value)
            if command.kind=='ask' and needs_page(command.value):command=Command('task',command.value)
            if command.kind!='task':raise ValueError('request routed to conversation')
            result['answer']=str(actions.execute(command,cancelled))
            report('returned_answer',result['answer'])
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)[:2000]
        report('attempt_error',result['error'])
    finally:
        service=getattr(actions,'_neural_service',None)
        result.update(seconds=time.monotonic()-started,model_calls=ledger.counts['model_calls'] if ledger else 0,
                      stop_reason=stop_reason,stopped_by_user=False,
                      source_sha256_before=source_before,source_sha256_after=source_fingerprint(),
                      harness_sha256_before=harness_before,harness_sha256_after=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      approvals=approvals,acceptance_reason='Requires independent complete A source/native-artifact/Chrono/comparison audit; this runner never promotes from prose.')
        result['chrono_slots_after']=len(list((APP/'.jarvis-runtime/discovery/tools/chrono-10.0.0/invocations').glob('slot-*.json')))
        with (home/'result-private.json').open('x',encoding='utf-8') as f:
            json.dump(result,f,indent=2)
        report('terminal','Attempt ended; full acceptance NOT certified. Inspect actual Journal and outputs.')
        actions.close()
        if service:service.journal.close()
        print(json.dumps({k:result.get(k) for k in ('case','seconds','model_calls','error','full_acceptance_passed')}))


def monitor(home,case):
    import tkinter as tk
    from tkinter.scrolledtext import ScrolledText
    root=tk.Tk();root.title('Jarvis Test '+case+' — live diagnostic monitor')
    root.geometry('1040x700')
    tk.Label(root,text='READ-ONLY MONITOR • actual Jarvis events • no acceptance claim',font=('Segoe UI',14)).pack(pady=8)
    view=ScrolledText(root,wrap='word',font=('Consolas',10));view.pack(fill='both',expand=True)
    count=0
    def update():
        nonlocal count
        path=home/'events-private.jsonl'
        rows=path.read_text(encoding='utf-8').splitlines() if path.exists() else []
        for line in rows[count:]:
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            view.configure(state='normal');view.insert('end',f"[{r['elapsed_s']}s] {r['kind']}\n{r['value']}\n\n");view.see('end');view.configure(state='disabled')
        count=len(rows)
        root.after(1000,update)
    update();root.mainloop()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=GOALS,default='A1');p.add_argument('--attempt',type=int,default=1)
    p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--monitor',action='store_true')
    p.add_argument('--max-seconds',type=int,default=600);p.add_argument('--max-model-calls',type=int,default=12)
    p.add_argument('--resume-attempt',type=int)
    p.add_argument('--resume-mode',choices=['history','evidence'],default='history')
    p.add_argument('--surrogate-scope',action='store_true',help='Explicit fallback scope from the 2026-11-06 user assignment; exact-team acceptance remains separate')
    p.add_argument('--approve-owned-project',action='store_true',help='Explicit scoped user grant for the vehicle workflow only; no paid/install/account/hardware approvals')
    a=p.parse_args();home=APP/f'.jarvis-runtime/lab-validation/a-{a.case.lower()}-attempt-{a.attempt}'
    if not 60<=a.max_seconds<=1800 or not 1<=a.max_model_calls<=30:raise ValueError('bounded diagnostic limits required')
    if a.monitor:return monitor(home,a.case)
    if a.worker:return worker(home,a.case,a.max_seconds,a.max_model_calls,a.surrogate_scope,a.approve_owned_project)
    if not a.run:return print('Explicit --run required; no inference performed')
    home.mkdir(parents=True,exist_ok=False)
    if a.resume_attempt is not None:
        import sqlite3,shutil
        if not 0<a.resume_attempt<a.attempt:raise ValueError('resume only an earlier same-case attempt')
        old=home.with_name(f'a-{a.case.lower()}-attempt-{a.resume_attempt}')
        if not (old/'result-private.json').is_file():raise ValueError('earlier attempt must have a terminal receipt')
        # Copy only actual Jarvis history, never hand-authored case inputs or answers.
        # A read-only SQLite backup preserves content-addressed evidence/WAL state.
        with sqlite3.connect((old/'brain.sqlite3').as_uri()+'?mode=ro',uri=True) as src:
            with sqlite3.connect(home/'brain.sqlite3') as dst:src.backup(dst)
        if a.resume_mode=='history' and (old/'task-owner').exists():shutil.copytree(old/'task-owner',home/'task-owner')
        (home/'resume-source.json').write_text(json.dumps({'attempt':a.resume_attempt,
            'source':'actual terminal Jarvis Journal'+(' and TaskState' if a.resume_mode=='history' else '; fresh TaskState; old traces remain in original attempt'),
            'operator_case_inputs':False}))
    (home/'started.json').write_text(json.dumps({'case':a.case,'goal':goal_for(a.case,a.surrogate_scope),
        'max_seconds':a.max_seconds,'max_instrumented_model_calls':a.max_model_calls,'paid_usage':False,'prepared_case':False,
        'owned_project_scope_authorized':a.approve_owned_project,
        'chrono_slots_before':len(list((APP/'.jarvis-runtime/discovery/tools/chrono-10.0.0/invocations').glob('slot-*.json')))}),encoding='utf-8')
    from jarvis.repo_acquisition import command
    raw=command([sys.executable,'-B',str(Path(__file__).resolve()),'--worker','--case',a.case,'--attempt',str(a.attempt),
        '--max-seconds',str(a.max_seconds),'--max-model-calls',str(a.max_model_calls),
        *(['--surrogate-scope'] if a.surrogate_scope else []),
        *(['--approve-owned-project'] if a.approve_owned_project else [])],timeout=a.max_seconds+30,limit=10000)
    print(raw.decode(errors='replace'))


if __name__=='__main__':main()
