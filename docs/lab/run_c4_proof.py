"""Operator-assisted actual queue/process restart and bounded numeric fault proof; no native apps."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'app';sys.path.insert(0,str(BASE))
from jarvis.discovery.model import optimization as opt
from jarvis.neural.service import BrainService
from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.task_store import TaskStore
from jarvis.task_scheduler import ScheduledQueue
from jarvis.task_state import TaskState
ON={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True}}
HOME=BASE/'.jarvis-runtime/lab-validation/c4-proof-final';HOME.mkdir(exist_ok=True)

def worker(phase):
    s=BrainService(ON,HOME/'brain.sqlite3');store=TaskStore(HOME/'queue.sqlite3')
    q=ScheduledQueue(store,observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True})
    a=Actions.__new__(Actions);a.config,a.base,a._neural_service,a.allowed_tools=ON,HOME,s,None
    a.queue=q;a.generation=1;a.task_state=TaskState(HOME/'task-owner');studies=opt.Studies(s.journal)
    try:
        if phase=='first':
            original=json.loads((BASE/'examples/discovery/pendulum-study.json').read_text())
            (HOME/'study.json').write_text(json.dumps(original),encoding='utf-8')
            a.execute(Command('task','lab optimize "study.json"'));identity=studies.create(HOME,'study.json')['study_id']
            a.execute(Command('task','lab optimize queue "'+identity+'"'))
            ids=opt.enqueue_remaining(studies,q,ON,identity,1)
            assert len(ids)==3
            a.task_state.start('bounded C4 proof','task')
            q.get(lane='legacy');a.execute(Command('task','lab optimize step "'+identity+'"'))
            q.outcome('COMPLETED','actual brain verified numeric trial');q.task_done()
            result=studies.describe(identity)
            (HOME/'identity.json').write_text(json.dumps({'id':identity,'task_ids':ids,'first_ref':result['trials'][0]['run_ref']}))
        elif phase=='resume':
            saved=json.loads((HOME/'identity.json').read_text());identity=saved['id'];q.restore(2)
            a.task_state.start('resumed bounded C4 proof','task')
            for _ in range(2):
                _,command,_=q.get(lane='legacy');a.execute(command)
                q.outcome('COMPLETED','actual resumed brain verified numeric trial');q.task_done()
            result=studies.describe(identity)
            assert result['objective_met'] and result['trials'][0]['run_ref']==saved['first_ref']
            assert result['trials'][1]['decision']=='REJECTED_CONSTRAINT'
            result['queue_states']=[store.get(i)['state'] for i in saved['task_ids']]
            result['checkpoint_present']=a.task_state.snapshot() is not None
        elif phase=='crash':
            raw=json.loads((HOME/'study.json').read_text());raw['target_period_s']=2.1
            (HOME/'crash.json').write_text(json.dumps(raw));identity=studies.create(HOME,'crash.json')['study_id']
            (HOME/'crash-id.json').write_text(json.dumps(identity))
            opt.solve=lambda *args,**kwargs:os._exit(23)
            studies.advance(identity,HOME)
            raise AssertionError('fault injection did not exit')
        else:
            identity=json.loads((HOME/'crash-id.json').read_text());row=studies.row(identity)
            if row['lease_until']>time.time():raise ValueError('wait for the real lease; do not alter timestamps')
            result=studies.advance(identity,HOME)
            assert result['trials'][0]['state']=='UNCERTAIN' and result['trials'][0]['run_ref'] is None
            assert result['trials'][1]['number']==1
            raw=json.loads((HOME/'study.json').read_text());raw['cpu_budget_s']=0
            (HOME/'zero.json').write_text(json.dumps(raw));zero=studies.create(HOME,'zero.json')['study_id']
            result['budget_stop']=studies.advance(zero,HOME)['state'];assert result['budget_stop']=='BUDGET_STOP'
            studies.control(identity,'pause');assert studies.advance(identity,HOME)['state']=='PAUSED'
            studies.control(identity,'resume');studies.control(identity,'cancel')
            result['control_final']=studies.describe(identity)['state']
        (HOME/(phase+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    finally:q.close();store.db.close();s.journal.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['first','resume','crash','recover']);args=p.parse_args()
    if args.phase:worker(args.phase);return
    marker=HOME/'started.json'
    with marker.open('x') as f:json.dump({'scope':'free local 50-attempt grant; five SciPy admissions; no installs/model/GPU'},f)
    for phase in ('first','resume','crash'):
        r=subprocess.run([sys.executable,'-B',__file__,'--phase',phase],timeout=90,capture_output=True)
        if r.returncode!=(23 if phase=='crash' else 0):
            print(r.stderr.decode(errors='replace')[-2500:]);raise RuntimeError('proof phase failed: '+phase)
    time.sleep(21)
    r=subprocess.run([sys.executable,'-B',__file__,'--phase','recover'],timeout=90,capture_output=True)
    if r.returncode:print(r.stderr.decode(errors='replace')[-2500:]);raise RuntimeError('recovery proof failed')
    result={'date_local':'2026-11-04 Asia/Calcutta','operator_assisted':True,'physical_validation':False,
        'fresh_process_resume':True,'owned_child_crash_exit':23,'real_lease_wait_s':21,'new_installs':0,'paid_calls':0,
        **{phase:json.loads((HOME/(phase+'.json')).read_text()) for phase in ('first','resume','recover')}}
    (ROOT/'docs/lab/evidence/c4-brain-proof.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'state':'passed','best':result['resume']['best'],'recovery':result['recover']['control_final']}))
if __name__=='__main__':main()
