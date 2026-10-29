"""Real production intake campaign. Never authors or replaces target application source."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
import sys
import time
from uuid import uuid4

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
REQUESTS=[
    'Create a new Python calculator application that supports addition, subtraction, multiplication and division. Include input validation and tests. Save it as a new isolated project.',
    'Create a Python desktop calculator with an elegant, modern graphical interface. It must support basic arithmetic, keyboard interaction, clearing input and error handling. Make it visually polished and fully functional.',
    'Create a modern Python desktop to-do application where I can add, edit, delete and complete tasks. Save tasks locally and restore them when the application restarts.',
    'Create a professional responsive portfolio website using HTML, CSS and JavaScript. Include a hero section, navigation, projects, contact section, animations and dark mode. All interactive controls must work.',
    'Create a polished, professional React website with an animated hero section, interactive cards, responsive navigation, smooth transitions and a coherent visual design.',
    'Create a modern React productivity dashboard with projects, tasks, progress charts, filters and local persistence. Use a professional design system and polished interactions.',
    'Create a small full-stack task management website with a frontend, backend API and local database. Users should be able to create, update, view and delete tasks.',
    'Create a desktop PC monitoring dashboard that displays available CPU, RAM and disk information, updates periodically and provides a responsive graphical interface with charts.',
]
LIVE_REQUEST='Create a professional responsive portfolio website using HTML, CSS and JavaScript. Include a hero section, navigation, projects and a contact section. All interactive controls must work.'
RESEARCH_REQUEST='Create a professional responsive portfolio website using HTML, CSS and JavaScript, with a reusable interactive project-card component, navigation, animations and dark mode. All interactive controls must work. Use suitable reusable components when available and retain their provenance.'
LIVE_CHANGES=['Also add dark mode.','Make the navigation animated.','Do not use cloud APIs.']


def source_manifest():
    return {p.relative_to(BASE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((BASE/'jarvis').rglob('*.py'))}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',type=int,choices=range(1,12),required=True)
    parser.add_argument('--seconds',type=int,default=900)
    parser.add_argument('--coding-provider',choices=['local','auto','groq','gemini'],default='local')
    parser.add_argument('--function-statements',choices=['json_nodes','python_source'],default='json_nodes',help='Model proposal representation only; both use the same scoped AST, source/frozen and candidate guards.')
    parser.add_argument('--cloud-targeted-repairs-only',action='store_true',help='Reserve approved cloud calls for source-bound repair proposals; preparation and planning remain local.')
    parser.add_argument('--cloud-budget-task-id',help='Retain the existing logical cloud task budget when restarting a superseded repair trial (32 lowercase hex characters).')
    parser.add_argument('--gemini-task-call-limit',type=int,choices=range(1,17),help='Optional bounded task override; exceeding3 requires explicit priority justification and remaining capacity.')
    parser.add_argument('--gemini-budget-justification',help='Recorded reason for a priority extension of at most two calls beyond the initial allocation, within configured ceiling and remaining capacity; never include credentials.')
    parser.add_argument('--groq-task-call-limit',type=int,choices=range(1,17),help='Optional bounded logical task call ceiling; one justified recovery call beyond the default is allowed.')
    parser.add_argument('--groq-budget-justification',help='Reason for the one-call Groq recovery extension; never include credentials.')
    parser.add_argument('--approve-synthetic-cloud',action='store_true',help='Explicitly approve this synthetic campaign context for free-only cloud coding; requires current zero-token certification.')
    parser.add_argument('--resume-run',type=Path,help='Resume an existing owned campaign through production intake; preserve its previous report.')
    parser.add_argument('--existing-project',type=Path,help='Explicit existing project for a new production coding/verification task; no source supplied by this harness.')
    parser.add_argument('--repair-goal',help='High-level existing-project goal; requires --existing-project.')
    parser.add_argument('--require-repair-progress',action='store_true',
                        help='Existing-project trial only: reject neutral implementation saves against a failed complete unittest baseline.')
    parser.add_argument('--execution-function-repair',action='store_true',
                        help='Scoped repair only: observe actual failed-test owned calls and constrain bounded function repairs; no function bodies supplied.')
    parser.add_argument('--acceptance-observation',action='append',default=[],
                        help='Explicit failed report filename under .jarvis-runtime/acceptance-observations; current source/frozen hashes must match, at most two.')
    parser.add_argument('--diagnostic-observation',action='append',default=[],
                        help='One explicit completed read-only contract probe id; raw response/model/source/frozen bindings required. Untrusted data only.')
    parser.add_argument('--prior-validation',action='append',default=[],
                        help='Explicit old failing validation under this campaign namespace; verified frozen bytes/checks/snapshot only, at most four.')
    parser.add_argument('--workspace-parent',type=Path,help='Existing owned parent for new isolated project roots; useful outside the Jarvis repository instruction hierarchy.')
    args=parser.parse_args()
    from jarvis.campaign_pause import assert_allowed
    assert_allowed(whole_campaign=True)
    if args.groq_task_call_limit and args.groq_task_call_limit>8 and not args.groq_budget_justification:
        parser.error('A Groq task extension requires an explicit justification.')
    if args.gemini_task_call_limit and args.gemini_task_call_limit>3 and not args.gemini_budget_justification:
        parser.error('A Gemini task extension requires an explicit justification.')
    if args.cloud_budget_task_id and (len(args.cloud_budget_task_id)!=32 or any(c not in "0123456789abcdef" for c in args.cloud_budget_task_id)):
        parser.error("Cloud budget task ID must be32 lowercase hex characters.")
    if args.cloud_budget_task_id and not args.approve_synthetic_cloud:
        parser.error("Cloud budget continuation requires explicit synthetic cloud approval.")
    if args.coding_provider!='local' and not args.approve_synthetic_cloud:parser.error('Cloud coding requires explicit synthetic campaign context approval.')
    if args.approve_synthetic_cloud:
        certificate=json.loads((BASE/'artifacts/autonomous-repair/cloud-coding-zero-token.json').read_text(encoding='utf-8'))
        if certificate.get('status')!='PASS' or certificate.get('real_cloud_inference_tokens')!=0:parser.error('Passing zero-token certification is required before live cloud inference.')
        if any(hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=sha for name,sha in certificate['source_sha256'].items()):parser.error('Cloud coding source changed since the zero-token dry run; rerun its tests first.')
    if bool(args.existing_project)!=bool(args.repair_goal) or (args.resume_run and args.existing_project):
        parser.error('Existing-project and repair-goal must be supplied together, without resume-run.')
    if args.case==9 and not args.existing_project:parser.error('Case 9 requires an explicit controlled existing project and repair goal.')
    if args.require_repair_progress and not args.existing_project:
        parser.error('Repair progress policy requires an explicit existing-project trial.')
    if args.execution_function_repair and not (args.existing_project and args.require_repair_progress):
        parser.error('Execution-guided function repair requires an existing project and strict repair progress.')
    if args.function_statements!='json_nodes' and not args.execution_function_repair:
        parser.error('Python statement representation requires execution-guided scoped repair.')
    if args.acceptance_observation and (not args.existing_project or len(args.acceptance_observation)>2):
        parser.error('Select at most two independent failure reports for an explicit existing-project trial.')
    if args.diagnostic_observation and (not args.existing_project or len(args.diagnostic_observation)>1):
        parser.error('Select at most one diagnostic observation for an explicit existing-project trial.')
    if args.prior_validation and (not args.existing_project or len(args.prior_validation)>4):
        parser.error('Select at most four historical validations for an explicit existing-project repair.')
    source_before=source_manifest()
    config_before=hashlib.sha256((BASE/'config/config.json').read_bytes()).hexdigest()
    from jarvis.actions import Actions
    from jarvis.engine import Engine
    campaign_parent=(BASE/'.jarvis-runtime/autonomous-repair').resolve()
    previous=None
    if args.resume_run:
        root=args.resume_run.resolve(strict=True)
        if root.parent!=campaign_parent:
            parser.error('Resume requires a direct child of the owned campaign directory.')
        previous=json.loads((root/'campaign.json').read_text(encoding='utf-8'))
        if previous.get('case')!=args.case:
            parser.error('Resume case must match the existing campaign.')
        workspace=Path(previous['workspace_parent']).resolve(strict=True)
        history=root/'campaign-history'
        history.mkdir(exist_ok=True)
        (history/(uuid4().hex+'.json')).write_bytes((root/'campaign.json').read_bytes())
    else:
        root=campaign_parent/uuid4().hex
        root.mkdir(parents=True)
        workspace=args.existing_project.resolve(strict=True) if args.existing_project else ((args.workspace_parent.resolve(strict=True)/root.name) if args.workspace_parent else root/'projects')
        if not args.existing_project:workspace.mkdir()
    config=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    config['files_root']='files'
    config['project_roots']=[str(workspace)]
    config['memory']={**config.get('memory',{}),'enabled':args.case==11,'vault':str(root/'vault')}
    config['brain']={**config['brain'],'coding_backend':'jarvis','native_max_workers':1,
                     'max_coding_seconds':args.seconds}
    if args.approve_synthetic_cloud:
        config['brain'].update(native_cloud_context={'provenance':'synthetic','restricted':False},
            native_cloud_task_id=args.cloud_budget_task_id or root.name,native_coding_provider=args.coding_provider,
            native_cloud_targeted_repairs_only=args.cloud_targeted_repairs_only,
            native_coding_complexity='complex' if args.case==2 else 'ordinary')
    if args.gemini_task_call_limit:config['brain'].update(native_gemini_task_limit=args.gemini_task_call_limit,native_gemini_budget_reason=args.gemini_budget_justification or '')
    if args.groq_task_call_limit:config['brain'].update(native_groq_task_limit=args.groq_task_call_limit,native_groq_budget_reason=args.groq_budget_justification or '')
    if args.prior_validation:config['brain']['native_prior_validation_paths']=args.prior_validation
    if args.require_repair_progress:config['brain']['native_require_repair_progress']=True
    if args.execution_function_repair:
        config['brain']['native_execution_function_repair']=True
        config['brain']['native_statement_representation']=args.function_statements
    if args.acceptance_observation:config['brain']['native_acceptance_observation_paths']=args.acceptance_observation
    if args.diagnostic_observation:config['brain']['native_diagnostic_observation_ids']=args.diagnostic_observation
    config['project_intelligence']={**config.get('project_intelligence',{}),'enabled':True,
        'default_workspace':str(workspace),'search_roots':[],'search_home':False}
    # Keep production project/queue/coding paths; background sensors are irrelevant
    # to this isolated campaign and must not act on the user's desktop.
    for key in ('anticipation','realtime','self_evolution','cognitive_awareness','screen_awareness'):
        config[key]={**config.get(key,{}),'enabled':False}
    request=args.repair_goal or (LIVE_REQUEST if args.case==10 else RESEARCH_REQUEST if args.case==11 else REQUESTS[args.case-1])
    record={'date':datetime.now(timezone.utc).isoformat(),'case':args.case,'request':request,
        'root':str(root),'workspace_parent':str(workspace),'model':config['brain'].get('coder'),'result':'NOT_RUN',
        'scope':'Production Engine -> Actions -> TaskIngress -> project intelligence/scheduler -> native local Qwen. No target source supplied by supervisor. Isolated memory disabled; reuse is unverified.'}
    record['configuration_sha256']=config_before
    record['requested_coding_provider']=args.coding_provider
    record['cloud_context_approved']=args.approve_synthetic_cloud
    if args.prior_validation:record['selected_prior_validations']=args.prior_validation
    if args.acceptance_observation:record['selected_acceptance_observations']=args.acceptance_observation
    if args.diagnostic_observation:record['selected_diagnostic_observations']=args.diagnostic_observation
    record['coding_policy']={k:config['brain'].get(k) for k in ('native_max_turns','native_max_repairs','native_max_workers','max_coding_seconds','native_require_repair_progress','native_execution_function_repair','native_statement_representation','native_cloud_task_id','native_cloud_targeted_repairs_only','native_gemini_task_limit','native_gemini_budget_reason','native_groq_task_limit','native_groq_budget_reason')}
    from jarvis.gpu_scheduler import configured
    record['gpu_policy']=configured()
    if args.case==11:
        record['scope']='Production intake/coding and configured research, with a new empty isolated memory vault. No personal memory loaded. Overlap, handoff, integration and application acceptance require observed evidence; memory reuse is unverified.'
    if args.case==10:record['live_changes']=[]
    (root/('jarvis-source-before-'+uuid4().hex+'.json')).write_text(json.dumps(source_before,indent=2),encoding='utf-8')
    record['jarvis_source_sha256']=hashlib.sha256(json.dumps(source_before,sort_keys=True).encode()).hexdigest()
    if previous:
        record['resume']={'previous_date':previous['date'],'command':'Resume the project',
                          'supervised_engineering_validation':True,'source_actions_replayed':False}
    if args.existing_project:
        from jarvis.codex_workload import fingerprint
        record.update(request=args.repair_goal,mode='explicit existing-project task',
            source_before=fingerprint(workspace),
            scope='Production Actions -> durable TaskIngress -> Coder -> workload/native Qwen -> executable validation. Explicit existing-project scope; no source supplied by supervisor. No claim of fresh-project intake or memory reuse.')
    def save():
        (root/'campaign.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    def report(kind,value=''):
        with (root/'events.jsonl').open('a',encoding='utf-8') as out:
            out.write(json.dumps({'at':time.time(),'kind':kind,'value':value},ensure_ascii=False,default=str)+'\n')
        if kind=='task_decision' and isinstance(value,dict) and value.get('status')=='PENDING' and actions is not None:
            # Equivalent to displaying the logged choice card. Do not select an
            # option or mint approval; production timeout/reversibility governs.
            actions.ingress.decisions.presented(value['id'])
        if kind in {'spoken_reply','answer','warning','question','repair'}:
            print(kind,str(value)[:1000],flush=True)
    save();print('CAMPAIGN '+str(root),flush=True)
    actions=None
    try:
        actions=Actions(config,root,report)
        # Start only the real admission/scheduler/executor lanes. No sensing,
        # microphone, idle autonomy or user desktop action is needed for intake.
        actions.ingress.start();actions.thread.start()
        engine=Engine(actions.submit,report);engine.activate()
        if args.existing_project:
            from jarvis.commands import Command
            actions.submit(Command('code_task',args.repair_goal,str(workspace)))
        else:
            command='Resume the project' if previous else request
            engine.feed(command,final=True,raw=command)
        started=time.monotonic();last=None;idle_since=None;change_due=0
        while time.monotonic()-started<args.seconds:
            rows=actions.ingress.store.rows()
            projects=actions.project_intel.store.all()
            if args.case==10 and len(record['live_changes'])<len(LIVE_CHANGES) and time.monotonic()>=change_due:
                coding=[r for r in rows if r['state']=='RUNNING' and r.get('command',{}).get('kind')=='code_task']
                confirmed=[]
                for journal in (root/'.jarvis-runtime/native-code').glob('*/file-events.jsonl'):
                    # Read complete journal lines only. Never alter worker state
                    # or infer a save from an attempted/uncertain mutation.
                    for line in journal.read_text(encoding='utf-8').splitlines():
                        try:event=json.loads(line)
                        except json.JSONDecodeError:continue
                        if event.get('stage')=='applied':confirmed.append(str(journal))
                if coding and confirmed:
                    change=LIVE_CHANGES[len(record['live_changes'])]
                    record['live_changes'].append({'at':time.time(),'request':change,
                        'running_task_ids':[r['id'] for r in coding],'project_ids':[p['id'] for p in projects],
                        'confirmed_save_journals':sorted(set(confirmed))})
                    # App.send_input activates a fresh command engine per typed
                    # submission. A long build can exceed the speech wake timeout.
                    # Match typed intake without waking the user's microphone.
                    save();engine.activate();engine.feed(change,final=True,raw=change);change_due=time.monotonic()+2
            snapshot=[(r['id'],r['state']) for r in rows]
            if snapshot!=last:
                record.update(tasks=[{k:r.get(k) for k in ('id','state','command','outcome','checkpoint')} for r in rows],
                              projects=projects,seconds=round(time.monotonic()-started,3))
                save();last=snapshot
                print('TASKS '+str(snapshot),flush=True)
            active=[r for r in rows if r['state'] not in {'COMPLETED','FAILED','CANCELLED','PARTIAL'}]
            failed_dependency_only=(any(r['state']=='FAILED' for r in rows) and active
                and all(r['state'] in {'WAITING_DEPENDENCY','WAITING_CLARIFICATION'} for r in active))
            pending_decisions=any(d['status']=='PENDING' for d in actions.ingress.decisions.rows())
            if (not active or failed_dependency_only) and rows and not pending_decisions:
                idle_since=idle_since or time.monotonic()
                if time.monotonic()-idle_since>12:break
            else:idle_since=None
            time.sleep(.5)
        record.update(result='FAIL',seconds=round(time.monotonic()-started,3),
                      reason='Application acceptance requires independent functional verification; inspect task and workload evidence.',
                      project_reports=[actions.project_intel.report(p) for p in actions.project_intel.store.all()])
        record['decisions']=actions.ingress.decisions.rows()
        if any(p.get('questions') and any(q.get('status')=='open' for q in p['questions']) for p in actions.project_intel.store.all()):
            record.update(result='BLOCKED',reason='Production intake requires a project clarification; exact question is retained in events.')
    except Exception as exc:
        record.update(result='BLOCKED',error_type=type(exc).__name__,reason=str(exc))
    finally:
        if actions is not None:
            actions.close()
            record['tasks_at_limit']=record.get('tasks',[])
            try:
                with sqlite3.connect((root/'.jarvis-runtime/task-queue.sqlite3').as_uri()+'?mode=ro',uri=True,timeout=2) as connection:
                    connection.row_factory=sqlite3.Row
                    record['tasks']=[{k:(json.loads(row[k]) if k in {'command','checkpoint'} else row[k])
                        for k in ('id','state','command','outcome','checkpoint')} for row in connection.execute('SELECT * FROM tasks ORDER BY number')]
                record['task_capture_stage']='After Actions.close; fresh read-only durable queue snapshot'
            except sqlite3.Error as error:record['shutdown_snapshot_error']=str(error)
        if args.existing_project:
            record['source_after']=fingerprint(workspace)
        source_after=source_manifest()
        record['jarvis_source_changed_during_trial']=source_before!=source_after
        record['configuration_changed_during_trial']=hashlib.sha256((BASE/'config/config.json').read_bytes()).hexdigest()!=config_before
        record['finished_at']=datetime.now(timezone.utc).isoformat()
        cloud=[]
        for path in (root/'.jarvis-runtime').rglob('cloud-route-state.json'):
            try:
                state=json.loads(path.read_text(encoding='utf-8'))
                cloud.extend({'state_evidence':str(path.relative_to(root)),**row} for row in state.get('attempts',[]))
            except (OSError,ValueError):pass
        record['cloud_inference']={'attempts':cloud,'real_inference_requests':sum(row.get('sent') is True for row in cloud),
            'reported_tokens':sum(row.get('usage',{}).get('total_tokens',0) for row in cloud),
            'application_acceptance':'Requires separate independent verification'}
        record['record_to_shutdown_seconds']=round((datetime.fromisoformat(record['finished_at'])-datetime.fromisoformat(record['date'])).total_seconds(),3)
        save()
    print(json.dumps(record,indent=2,default=str),flush=True)


if __name__=='__main__':main()
