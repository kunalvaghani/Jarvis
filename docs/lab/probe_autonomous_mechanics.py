"""One natural-language mechanics smoke probe, not autonomous A–H acceptance.

No prepared case JSON, solution, direct adapter call, model patch or solver patch
is supplied. Jarvis must choose a workflow and materialize its own request.
Only the post-run oracle knows the analytic reference. Run after regressions.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'app'
HOME=APP/'.jarvis-runtime/lab-validation/ah-autonomous-mechanics-v5'
GOAL=('Run a conditional mechanical simulation of one uniform sphere of mass 0.4 kg and radius 0.05 m, '
      'released from rest with its centre at (0, 0, 2) metres. Use gravity (0, 0, -9.81) m/s^2, '
      'no contact and no air drag. Simulate 0.2 seconds and report its final position and the model limitations.')
sys.path.insert(0,str(APP))


def save(name,data):
    with (HOME/name).open('x',encoding='utf-8') as stream:json.dump(data,stream,indent=2,allow_nan=False)


def worker():
    from jarvis.actions import Actions,Desktop
    from jarvis.brain import BrainClient
    from jarvis.engine import Engine
    from jarvis.audio import command_text
    from jarvis.commands import Command
    from jarvis.conversation_intent import quick_kind,model_kind,needs_page
    from jarvis.task_state import TaskState
    from jarvis.telemetry.ledger import task_scope
    from jarvis.discovery.acceptance import artifact
    config=json.loads((APP/'config/config.json').read_text(encoding='utf-8'))
    config['_ui_verification']=True  # Does not interrupt the real task or start background services.
    for provider in ('groq','gemini'):
        config[provider]={**config.get(provider,{}),'enabled':False}
    config['memory']={**config.get('memory',{}),'enabled':False}
    config['knowledge_acquisition']={**config.get('knowledge_acquisition',{}),'enabled':False}
    config['lab']={'enabled':True,'sim':True,'research':False,'learning':False}
    config['neural']={**config.get('neural',{}),'mode':'act','learning':'shadow',
        'journal':(HOME/'brain.sqlite3').relative_to(APP).as_posix()}
    config['telemetry']={**config.get('telemetry',{}),'timing_ledger':True}
    os.environ['JARVIS_BRAIN_MODE']='on'  # This worker only; no shipped configuration change.
    events=[]
    def report(kind,value):events.append({'kind':kind,'value':value})
    actions=Actions(config,APP,report,Desktop())
    actions.task_state=TaskState(HOME/'task-owner')
    actions.skills.task_id_provider=actions.task_state.running_identity
    approvals=[]
    def decline(kind,detail,cancelled):
        approvals.append({'kind':kind,'answer':'denied'})
        return False
    actions.approval_handler=decline
    assert type(actions.brain.client) is BrainClient
    started=time.monotonic();ledger=None;answer='';error=None
    def cancelled():
        return time.monotonic()-started>450 or (ledger is not None and ledger.counts['model_calls']>=9)
    try:
        with task_scope(config,'autonomous_mechanics_probe',HOME) as ledger:
            commands=[];engine=Engine(commands.append,lambda *a:None);engine.activate()
            engine.feed(command_text(GOAL),final=True,raw=GOAL)
            if len(commands)!=1:raise ValueError('exactly one ordinary intake command required')
            command=commands[0]
            if command.kind=='task' and command.extra=='unparsed':
                kind=quick_kind(command.value) or model_kind(command.value,{
                    'model':config.get('context_selector',{}).get('model','qwen3.5:0.8b'),
                    'timeout_seconds':3.0},cancelled)
                command=Command('ask' if kind=='chat' else 'task',command.value)
            if command.kind=='ask' and needs_page(command.value):command=Command('task',command.value)
            if command.kind!='task':raise ValueError('Jarvis routed the request to conversation, not a task')
            answer=str(actions.execute(command,cancelled))
    except Exception as exc:error=type(exc).__name__+': '+str(exc)[:2000]
    finally:
        service=getattr(actions,'_neural_service',None)
        result={'scope':'one autonomous primitive-mechanics smoke; not A-H acceptance',
            'goal':GOAL,'seconds':time.monotonic()-started,'answer':answer,'error':error,
            'model_calls':ledger.counts['model_calls'] if ledger else 0,'approvals':approvals,
            'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'no_prepared_case_json':True,'model_or_solver_patches':False,'physical_validation':False}
        checks=[]
        try:
            if error or result['model_calls']<1 or service is None:raise ValueError('ordinary live planning did not finish')
            calls=service.journal.rows("SELECT * FROM discovery_planner_calls WHERE state='done'")
            for call in calls:
                proposal=artifact(service.journal,call['proposal_ref'])
                if proposal['proposal']['command']!='lab simulate mechanics "{request}"':continue
                body=proposal['proposal']['request']
                if body['units']!='SI' or len(body['bodies'])!=1:raise ValueError('requested assembly changed')
                sphere=body['bodies'][0]
                expected={'shape':'sphere','joint':'free','mass_kg':.4,'size_m':[.05],
                          'position_m':[0,0,2],'shape_center_m':[0,0,0]}
                if any(sphere.get(k)!=v for k,v in expected.items()):raise ValueError('physical input differs from the question')
                if body['gravity_m_s2']!=[0,0,-9.81] or body['duration_s']!=.2:raise ValueError('scenario changed')
                child=artifact(service.journal,call['result_ref'])
                if child['verified'] is not True or not child['autonomous_task_id']:raise ValueError('actual child verification required')
                outputs=service.journal.rows('SELECT state,result_ref FROM outbox WHERE goal_id=? AND node_id=?',
                    (child['goal_id'],'discovery.mechanics.primitive@v1'))
                if len(outputs)!=1 or outputs[0]['state']!='done':raise ValueError('actual producer outbox required')
                packet=artifact(service.journal,outputs[0]['result_ref'])
                produced=artifact(service.journal,packet['report'])
                run_ref=produced['run_ref']
                if not service.journal.rows('SELECT ref FROM discovery_primitive_runs WHERE ref=?',(run_ref,)):
                    raise ValueError('no actual matching MuJoCo invocation receipt')
                actual=artifact(service.journal,run_ref)
                z=actual['samples'][-1]['positions_m'][sphere['id']][2]
                target=2-9.81*.2**2/2
                if not math.isclose(z,target,abs_tol=1e-8):raise ValueError('independent free-fall reference mismatch')
                checks.append({'goal_id':child['goal_id'],'actual_final_z_m':z,
                    'analytic_reference_z_m':target,'run_ref':run_ref})
            if not checks:raise ValueError('Jarvis did not prepare and execute its own matching mechanics request')
            result['probe_passed']=True
        except Exception as exc:
            result.update(probe_passed=False,oracle_error=type(exc).__name__+': '+str(exc)[:1000])
        result['checks']=checks
        save('result.json',result);save('events-private.json',events)
        actions.close()
        if service:service.journal.close()
        print(json.dumps({k:result[k] for k in ('probe_passed','model_calls','seconds','error')}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true');parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    if args.worker:return worker()
    if not args.run:
        print(json.dumps({'result_exists':(HOME/'result.json').is_file(),'live_run_performed':False}));return
    HOME.mkdir(parents=True,exist_ok=True)
    save('started.json',{'scope':'one bounded live native-planner smoke','max_seconds':480,
        'max_instrumented_model_calls':9,'C3_proposer_calls':0,'paid_usage':False,'user_account_writes':False})
    from jarvis.repo_acquisition import command
    raw=command([sys.executable,'-B',str(Path(__file__).resolve()),'--worker'],timeout=480,limit=10000)
    print(raw.decode('utf-8',errors='replace'))


if __name__=='__main__':main()
