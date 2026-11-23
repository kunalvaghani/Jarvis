"""Phase E bounded local acceptance runner, real final-text -> Actions -> brain.

Explicit --run-local only. Uses the live harness' intake/independent-oracle pattern
without its full Actions constructor (which owns shared services/user memory).
No model calls, credential reads, remote writes, downloads, UI or service startup.
One-shot markers retain uncertain stages; never rerun them automatically.
"""
from __future__ import annotations
import argparse,json,os,subprocess,sys,time
from pathlib import Path

APP=Path(__file__).resolve().parents[2]
ROOT=APP.parent
sys.path.insert(0,str(APP))
HOME=APP/'.jarvis-runtime/lab-validation/e-local-2026-11-04'
ON={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':False}}


def write(path,value):
    with path.open('x',encoding='utf-8') as handle:json.dump(value,handle,indent=2,allow_nan=False)


def guard(event,args):
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        path=Path(os.fsdecode(args[0])).resolve()
        if any(path.is_relative_to(root) for root in (APP/'secrets',APP/'.jarvis-runtime/gmail-api')):
            raise PermissionError('local E proof refuses credentials')
    if event in ('socket.connect','socket.sendto'):
        raise PermissionError('local E proof refuses network/model traffic')


def worker(stage):
    from jarvis.neural.service import BrainService
    from jarvis.actions import Actions
    from jarvis.engine import Engine
    from jarvis.discovery.acceptance import trace
    from jarvis.discovery.model.optimization import Studies
    from jarvis.task_store import TaskStore
    from jarvis.task_scheduler import ScheduledQueue
    from jarvis.task_state import TaskState
    write(HOME/(stage+'-started.json'),{'state':'consumed-before-dispatch','stage':stage})
    sys.addaudithook(guard)
    service=BrainService(ON,HOME/'brain.sqlite3');store=TaskStore(HOME/'queue.sqlite3')
    queue=ScheduledQueue(store,observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True})
    actions=Actions.__new__(Actions)
    actions.config,actions.base,actions._neural_service,actions.allowed_tools=ON,HOME,service,None
    actions.queue,actions.generation,actions.task_state=queue,1,TaskState(HOME/'task-owner')
    actions.report=lambda *args:None;actions.approvals_waiting=0;denials=[]
    def decline(kind,detail,cancelled):denials.append({'kind':kind,'detail':detail});return False
    actions.approval_handler=decline
    def execute(command,expected='verified'):
        commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate();engine.feed(command,final=True,raw=command)
        if len(commands)!=1:raise ValueError('one real intake command required')
        before={r['goal_id'] for r in service.journal.rows('SELECT goal_id FROM goals')}
        try:actions.execute(commands[0])
        except ValueError:
            if expected=='verified':raise
        fresh=[r for r in service.journal.rows('SELECT goal_id,state FROM goals') if r['goal_id'] not in before]
        if len(fresh)!=1 or fresh[0]['state']!=expected:raise ValueError('actual brain outcome differs: '+str(fresh))
        return fresh[0]['goal_id']
    studies=Studies(service.journal)
    try:
        if stage=='local':
            clocks=[]
            for index,beta in enumerate((0,.6,.8)):
                name='clock-'+str(index)+'.json';write(HOME/name,{'coordinate_time_s':100,'beta':beta})
                clocks.append(execute('lab theory dilation "'+name+'"'))
            circuit=[execute('lab simulate divider 5 V 1000 ohm 1000 ohm'),execute('lab simulate divider 9 V 1000 ohm 1000 ohm')]
            write(HOME/'local.json',{'clock_goals':clocks,'circuit_goals':circuit})
        elif stage=='first':
            raw=json.loads((APP/'examples/discovery/pendulum-study.json').read_text())
            raw['baseline']['project_id']='phase-e-pendulum';write(HOME/'study.json',raw)
            goal=execute('lab optimize "study.json"')
            identity=trace(service.journal,goal,'discovery.optimization.advance@v1','discovery.verify.optimization@v1')['report']['result']['study_id']
            queued=execute('lab jobs queue "'+identity+'"')
            result=trace(service.journal,queued,'discovery.jobs.queue@v1','discovery.verify.d2@v1')['report']['result']['result']
            task_ids=[r['task_id'] for r in service.journal.rows('SELECT task_id FROM discovery_job_tasks WHERE study=?',(identity,))]
            if len(task_ids)!=3:raise ValueError('three actual queued tasks required')
            actions.task_state.start('Phase E bounded local study','task')
            _,command,_=queue.get(lane='legacy')
            first=execute(command.value);queue.outcome('COMPLETED','actual independent brain verification');queue.task_done()
            report=trace(service.journal,first,'discovery.optimization.advance@v1','discovery.verify.optimization@v1')['report']['result']
            write(HOME/'first.json',{'study_id':identity,'task_ids':task_ids,'first_goal':first,'first_ref':report['trials'][0]['run_ref']})
            # Crash only this owned qualification worker, after committed checkpoint.
            os._exit(23)
        elif stage=='resume':
            saved=json.loads((HOME/'first.json').read_text());identity=saved['study_id'];queue.restore(2)
            actions.task_state.start('Phase E fresh-process resume','task')
            execute('lab jobs pause "'+identity+'"');execute('lab jobs resume "'+identity+'"')
            goals=[]
            for _ in range(2):
                _,command,_=queue.get(lane='legacy');goals.append(execute(command.value))
                queue.outcome('COMPLETED','actual resumed independent brain verification');queue.task_done()
            states=[store.get(task)['state'] for task in saved['task_ids']]
            raw=json.loads((HOME/'study.json').read_text());raw['cpu_budget_s']=0;write(HOME/'zero.json',raw)
            create=execute('lab optimize "zero.json"')
            zero_id=trace(service.journal,create,'discovery.optimization.advance@v1','discovery.verify.optimization@v1')['report']['result']['study_id']
            zero=execute('lab optimize step "'+zero_id+'"')
            limited=trace(service.journal,zero,'discovery.optimization.advance@v1','discovery.verify.optimization@v1')['report']['result']
            if limited['state']!='BUDGET_STOP':raise ValueError('budget did not stop')
            report=studies.describe(identity)
            from jarvis.discovery.contracts import RunArtifact
            from jarvis.discovery.memory import LabMemory
            from jarvis.discovery.acceptance import sha
            memory=LabMemory(service.journal);ref=service.journal.put(report,data_type='Report')
            memory.put(RunArtifact(id='phase-e-study-report',locator=ref,sha256=sha(service.journal.get(ref).encode()),
                source_ids=(identity+'-input',),evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',media_type='application/json',
                justification='Actual bounded ideal-pendulum report; not full Phase E or physical acceptance.'))
            # Prepared destinations only: the parent is the earlier explicitly read My Drive root.
            # These two gates deliberately deny creation. New external writes need a fresh grant.
            parent='0AMVTcmM1XWY0Uk9PVA'
            write(HOME/'report-request.json',{'title':'Jarvis Phase E partial qualification 2026-11-04','parent_id':parent,'artifact_id':'phase-e-study-report'})
            write(HOME/'table-request.json',{'title':'Jarvis Phase E conditional study 2026-11-04','parent_id':parent,
                'experiment_ids':[identity+'-trial-'+str(n)+'-experiment' for n in range(3)]})
            declined=[execute('lab export '+kind+' "'+kind+'-request.json"',expected='denied') for kind in ('report','table')]
            rows=service.journal.rows('SELECT id,state,remote_id,payload_ref FROM discovery_deliveries')
            if len(rows)!=2 or any(r['state']!='PREPARED' or r['remote_id'] for r in rows) or len(denials)!=2:
                raise ValueError('denial did not preserve zero writes')
            write(HOME/'resume.json',{'last_goal':goals[-1],'resumed_goals':goals,'queue_states':states,'budget_goal':zero,
                'budget_state':limited['state'],'denied_goals':declined,'denials':denials,'deliveries':rows,
                'checkpoint_present':actions.task_state.snapshot() is not None})
        else:raise ValueError('unknown worker stage')
    finally:queue.close();store.db.close();service.journal.close()


def assess(persist=False):
    from jarvis.neural.journal import Journal
    from jarvis.discovery import acceptance as oracle
    from jarvis.discovery.memory import LabMemory
    from jarvis.discovery.contracts import RunArtifact
    journal=Journal(HOME/'brain.sqlite3')
    try:
        local=json.loads((HOME/'local.json').read_text());first=json.loads((HOME/'first.json').read_text());resumed=json.loads((HOME/'resume.json').read_text())
        proof={'D':oracle.clocks(journal,local['clock_goals'],HOME),'E':oracle.circuit(journal,local['circuit_goals']),
               'F':oracle.optimization(journal,resumed['last_goal'],first['first_ref'],23,resumed['queue_states'])}
        result={**oracle.catalogue(proof),'date_local':'2026-11-04 Asia/Calcutta','operator_assisted':True,'microphone_used':False,
            'paid_calls':0,'model_calls':0,'external_writes':0,'installs_downloads':0,'services_started':0,
            'owned_child_exit':23,'fresh_process_resume':resumed,'harness_sha256':oracle.sha(Path(__file__).read_bytes()),
            'oracle_sha256':oracle.sha(Path(oracle.__file__).read_bytes()),'reproduce':'app/.venv/Scripts/python.exe -B app/benchmarks/live/discovery_lab.py --inspect'}
        if persist:
            ref=journal.put(result,data_type='Report');memory=LabMemory(journal)
            memory.put(RunArtifact(id='phase-e-local-acceptance',locator=ref,sha256=oracle.sha(journal.get(ref).encode()),
                media_type='application/json',justification='Partial actual acceptance audit; mandatory G/H and full A1-H remain unmet.'))
            result['audit_artifact_ref']=ref
        # Diagnostic points come from the actual outputs, never from visual animation.
        for case in ('D','E','F'):
            output=HOME/(case+'-evidence.json')
            if persist and not output.exists():write(output,proof[case])
        prepared={'date_local':result['date_local'],'max_creates':2,'folder_id':'0AMVTcmM1XWY0Uk9PVA',
            'scope':'PREPARED ONLY; Phase E implementation is not consent to external writes',
            'deliveries':[{'id':r['id'],'payload':oracle.artifact(journal,r['payload_ref'])} for r in resumed['deliveries']]}
        return result,prepared
    finally:journal.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-local',action='store_true');parser.add_argument('--inspect',action='store_true')
    parser.add_argument('--worker',choices=('local','first','resume'));args=parser.parse_args()
    if args.worker:worker(args.worker);return
    if args.run_local:
        HOME.mkdir(parents=True,exist_ok=True)
        write(HOME/'started.json',{'scope':'existing free-local50 caps; two ngspice/three SciPy; no remote writes or models','state':'one-shot'})
        for stage in ('local','first','resume'):
            run=subprocess.run([sys.executable,'-B',__file__,'--worker',stage],timeout=120,capture_output=True)
            if run.returncode!=(23 if stage=='first' else 0):
                write(HOME/(stage+'-failure.json'),{'exit':run.returncode,'state':'UNMET; no automatic replay'})
                # Only source stack/error type diagnostics, kept private (not public evidence).
                with (HOME/(stage+'-private-stderr.txt')).open('xb') as handle:handle.write(run.stderr[-12000:])
                raise RuntimeError('local stage failed; inspect retained state, never rerun uncertain stage: '+stage)
    elif not args.inspect:parser.error('choose --run-local (one shot) or --inspect (read-only current evidence)')
    result,prepared=assess(persist=not args.inspect)
    if args.inspect:
        print(json.dumps({'cases':[(r['case'],r['status']) for r in result['cases']],'full_acceptance_passed':False}));return
    write(HOME/'assessment.json',result)
    write(ROOT/'docs/lab/evidence/e-local-acceptance.json',result)
    write(ROOT/'docs/lab/evidence/e-export-prepared.json',prepared)
    print(json.dumps({'state':'PARTIAL','passed_subchecks':['D conditional clocks','E ideal DC','F bounded study'],
                      'full_acceptance_passed':False,'mandatory_gates':result['mandatory_gates']}))

if __name__=='__main__':main()
