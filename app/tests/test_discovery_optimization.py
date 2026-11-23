"""Real CPU numerical optimization and persistent restart/stop integrity; no paid/native app fixtures."""
import json,threading
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from jarvis.discovery.model import optimization as opt
from jarvis.discovery.model.pendulum import Pendulum
from jarvis.neural.journal import Journal

ON={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True}}

def spec(**changes):
    return {'baseline':Pendulum(length_m=.5).model_dump(mode='json'),'lower_length_m':.5,'upper_length_m':1.5,
            'grid_points':3,'max_trials':3,'target_period_s':2.0,'tolerance_s':.02,'max_gravity_moment_nm':2.5,'cpu_budget_s':20.0,**changes}

@pytest.fixture
def study(tmp_path,monkeypatch):
    monkeypatch.setattr(opt,'reserve',lambda *a:0)
    file=tmp_path/'study.json';file.write_text(json.dumps(spec()))
    j=Journal(tmp_path/'brain.sqlite3');s=opt.Studies(j);identity=s.create(tmp_path,'study.json')['study_id']
    yield s,identity,tmp_path
    j.close()

def test_numerical_objective_improves_without_relaxing_scenario_and_failures_retained(study):
    s,i,base=study;before=s.describe(i)['scenario_sha256'];state=Mock()
    for _ in range(3):r=s.advance(i,base,task_state=state)
    assert r['state']=='COMPLETED' and r['objective_met']
    assert r['best']['length_m']==1 and r['best']['error_s']<r['baseline_error_s']
    assert r['trials'][1]['decision']=='REJECTED_CONSTRAINT' and not r['trials'][1]['feasible']
    assert len(r['trials'])==3 and r['scenario_sha256']==before
    assert state.checkpoint.call_count==3
    assert len(s.memory.list('Experiment'))==3
    assert s.advance(i,base)==r

def test_fresh_journal_reopen_resumes_next_trial_without_replaying_completed(study):
    s,i,base=study;s.advance(i,base);j=Journal(s.j.path)
    try:
        resumed=opt.Studies(j);assert len(resumed.describe(i)['trials'])==1
        r=resumed.advance(i,base)
        assert [x['number'] for x in r['trials']]==[0,1]
        assert r['trials'][0]['run_ref']==s.describe(i)['trials'][0]['run_ref']
    finally:j.close()

def test_crash_unknown_trial_stays_charged_and_is_not_repeated(study):
    s,i,base=study;s.advance(i,base)
    # Simulate an interruption before an input's outcome was recorded.
    with s.j.tx() as db:
        db.execute("UPDATE discovery_optimization_trials SET state='RUNNING',run_ref=NULL WHERE study=? AND number=0",(i,))
        db.execute("UPDATE discovery_studies SET state='RUNNING',owner='dead-fixture',lease_until=0 WHERE id=?",(i,))
    r=s.advance(i,base)
    assert r['trials'][0]['state']=='UNCERTAIN' and r['trials'][1]['length_m']==1.5

def test_pause_cancel_and_active_lease_never_silently_resume(study):
    s,i,base=study
    assert s.control(i,'pause')['state']=='PAUSED'
    assert not s.advance(i,base)['trials']
    s.control(i,'resume')
    with s.j.tx() as db:db.execute("UPDATE discovery_studies SET owner='active',lease_until=? WHERE id=?",(__import__('time').time()+100,i))
    with pytest.raises(ValueError,match='active trial'):s.advance(i,base)
    s.control(i,'cancel');assert s.advance(i,base)['state']=='CANCELLED'
    with pytest.raises(ValueError):s.control(i,'resume')

def test_budget_stop_needs_explicit_new_scope_not_resume(tmp_path,monkeypatch):
    monkeypatch.setattr(opt,'reserve',lambda *a:pytest.fail('budget-blocked solver dispatched'))
    (tmp_path/'zero.json').write_text(json.dumps(spec(cpu_budget_s=0.0)))
    j=Journal(tmp_path/'brain.sqlite3')
    try:
        s=opt.Studies(j);i=s.create(tmp_path,'zero.json')['study_id'];r=s.advance(i,tmp_path)
        assert r['state']=='BUDGET_STOP' and r['trials'][0]['state']=='BLOCKED' and r['best'] is None
        with pytest.raises(ValueError):s.control(i,'resume')
    finally:j.close()

def test_changed_source_and_fabricated_physics_are_refused(study):
    s,i,base=study;s.advance(i,base)
    trial=s.j.rows('SELECT run_ref FROM discovery_optimization_trials WHERE study=?',(i,))[0]
    run=json.loads(s.j.get(trial['run_ref']));run['model']['gravity_m_s2']=12.0
    forged=s.j.put(run,data_type='Report')
    with s.j.tx() as db:db.execute('UPDATE discovery_optimization_trials SET run_ref=? WHERE study=?',(forged,i))
    with pytest.raises(ValueError):s.describe(i)
    (base/'study.json').write_text(json.dumps(spec(target_period_s=3.0)))
    with pytest.raises(ValueError,match='source changed'):s.advance(i,base)

def test_existing_scheduler_dependencies_and_restore(study):
    from jarvis.task_store import TaskStore
    from jarvis.task_scheduler import ScheduledQueue
    s,i,base=study;store=TaskStore(base/'queue.sqlite3');observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True}
    q=ScheduledQueue(store,observe=observe)
    try:
        first=opt.enqueue(q,ON,i,1,threading.Event());second=opt.enqueue(q,ON,i,1,threading.Event(),[first])
        gen,command,token=q.get(lane='legacy');assert token.task_id==first
        s.advance(i,base);q.outcome('COMPLETED','real numerical trial');q.task_done()
        restored=ScheduledQueue(store,observe=observe);restored.restore(2)
        gen,command,token=restored.get(lane='legacy');assert gen==2 and restored.local.identity==second
        s.advance(i,base);restored.outcome('COMPLETED','real resumed trial');restored.task_done();restored.close()
    finally:q.close();store.db.close()

def test_real_brain_ingress_and_disabled_flags_cannot_fall_back(tmp_path,monkeypatch):
    from jarvis.actions import Actions
    from jarvis.commands import Command
    from jarvis.engine import Engine
    from jarvis.neural.service import BrainService
    monkeypatch.setattr(opt,'reserve',lambda *a:0)
    (tmp_path/'study.json').write_text(json.dumps(spec()));service=BrainService(ON,tmp_path/'brain.sqlite3')
    a=Actions.__new__(Actions);a.config,a.base,a._neural_service,a.allowed_tools=ON,tmp_path,service,None
    try:
        commands=[];e=Engine(commands.append,lambda *a:None);e.activate();e.feed('lab optimize "study.json"',final=True,raw='lab optimize "study.json"')
        a.execute(commands[0]);i=service.journal.rows('SELECT id FROM discovery_studies')[0]['id']
        for _ in range(3):a.execute(Command('task','lab optimize step "'+i+'"'))
        assert opt.Studies(service.journal).describe(i)['objective_met']
        assert service.journal.rows('SELECT state FROM goals ORDER BY rowid DESC LIMIT 1')[0]['state']=='verified'
        a.config={}
        with pytest.raises(ValueError,match='disabled'):a.execute(Command('task','lab optimize step "'+i+'"'))
    finally:service.journal.close()

def test_compact_c3_direct_schema_and_program_bound_provenance(monkeypatch):
    from jarvis.brain_worker import Models
    from jarvis.discovery.model.proposal_payload import expand
    import jarvis.brain_worker as worker
    m=Models.__new__(Models);m.client=Mock()
    reply={'alternatives':[{'statement':'Relative motion changes elapsed proper time.','prediction':'Matched clocks diverge when relative motion changes.'},
                           {'statement':'Gravitational potential changes the clock comparison.','prediction':'Matched motion leaves a height dependent clock offset.'}]}
    chat=Mock(return_value=json.dumps(reply));monkeypatch.setattr(worker,'chat',chat)
    output=m.generate('fixture-model','short',{'discovery_proposals':True,'context':'untrusted source'},'tool_text')
    settings=chat.call_args.args[1];assert settings['num_predict']==320 and settings['num_ctx']==2048
    assert 'alternatives' in settings['format_schema']['properties']
    assert len(chat.call_args.args[2][0]['content'])<500
    r={'question':'clocks','citations':[{'id':'paper-fixture','retraction_status':'not_checked','paper':{'title':'Fixture'}}]}
    tournament=expand(r,output);assert len(tournament.hypotheses)==3 and tournament.hypotheses[0].is_null
    assert all(h.citation_ids==('paper-fixture',) for h in tournament.hypotheses)
    bad=__import__('copy').deepcopy(reply);bad['alternatives'][0]['prediction']='It is proven to improve results by 50 percent.'
    with pytest.raises(ValueError):expand(r,bad)


def test_queue_remaining_is_idempotent_dependency_chain(study):
    from jarvis.task_store import TaskStore
    from jarvis.task_scheduler import ScheduledQueue
    s,i,base=study;store=TaskStore(base/'chain.sqlite3')
    q=ScheduledQueue(store,observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True})
    try:
        ids=opt.enqueue_remaining(s,q,ON,i,1)
        assert len(ids)==3 and len(set(ids))==3
        assert opt.enqueue_remaining(s,q,ON,i,1)==ids
        for identity in ids:
            q.get(lane='legacy');assert q.local.identity==identity
            s.advance(i,base);q.outcome('COMPLETED','verified numerical trial');q.task_done()
        assert opt.enqueue_remaining(s,q,ON,i,1)==[]
        assert s.describe(i)['objective_met']
    finally:q.close();store.db.close()


def test_explicit_queue_after_pause_drain_preserves_old_tasks_and_runs_remaining(study):
    from jarvis.task_store import TaskStore
    from jarvis.task_scheduler import ScheduledQueue
    s,i,base=study;store=TaskStore(base/'pause-chain.sqlite3')
    q=ScheduledQueue(store,observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True})
    try:
        old=opt.enqueue_remaining(s,q,ON,i,1);s.control(i,'pause')
        for _ in old:
            q.get(lane='legacy');assert s.advance(i,base)['state']=='PAUSED'
            q.outcome('COMPLETED','paused study, no numeric dispatch');q.task_done()
        s.control(i,'resume');new=opt.enqueue_remaining(s,q,ON,i,2)
        assert len(new)==3 and not set(new)&set(old)
        assert all(store.get(identity)['state']=='COMPLETED' for identity in old)
        assert opt.enqueue_remaining(s,q,ON,i,2)==new
        for _ in new:
            q.get(lane='legacy');s.advance(i,base);q.outcome('COMPLETED','verified trial');q.task_done()
        assert s.describe(i)['objective_met']
    finally:q.close();store.db.close()
