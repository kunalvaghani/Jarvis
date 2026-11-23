"""Phase E independent-oracle adversarial checks; no live native solver/model/provider."""
import json
import pytest
from jarvis.discovery import acceptance as oracle
from jarvis.neural.service import BrainService
from jarvis.actions import Actions
from jarvis.engine import Engine

ON={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':False}}

@pytest.fixture
def clocks(tmp_path):
    service=BrainService(ON,tmp_path/'brain.sqlite3');actions=Actions.__new__(Actions)
    actions.config,actions.base,actions._neural_service,actions.allowed_tools=ON,tmp_path,service,None
    actions.report=lambda *args:None;goals=[]
    for n,beta in enumerate((0,.6,.8)):
        name='clock-'+str(n)+'.json';(tmp_path/name).write_text(json.dumps({'coordinate_time_s':100,'beta':beta}),encoding='utf-8')
        commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate()
        command='lab theory dilation "'+name+'"';engine.feed(command,final=True,raw=command);actions.execute(commands[0])
        goals.append(service.journal.rows('SELECT goal_id FROM goals ORDER BY rowid DESC LIMIT 1')[0]['goal_id'])
    yield service.journal,goals,tmp_path
    service.journal.close()

def test_actual_text_brain_clock_trace_and_independent_oracle(clocks):
    journal,goals,base=clocks;result=oracle.clocks(journal,goals,base)
    assert result['status']=='PASSED_SUBCHECK'
    assert [r['result']['proper_time_s'] for r in result['runs']]==pytest.approx([100,80,60])
    assert all(r['microphone_used'] is False and r['result']['physical_validation'] is False for r in result['runs'])
    report=oracle.catalogue({'D':result})
    assert report['certified_full_acceptance_score']==0 and report['full_acceptance_passed'] is False
    assert report['mandatory_gates']=={'G':'UNMET','H':'UNMET'}

@pytest.mark.parametrize('fault',['unverified','missing_outbox','missing_signal','changed_signal','bad_binding','self_verifier','bad_artifact'])
def test_forged_or_incomplete_goal_cannot_supply_acceptance_evidence(clocks,fault):
    journal,goals,base=clocks;identity=goals[0]
    with journal.tx() as db:
        if fault=='unverified':db.execute("UPDATE goals SET state='failed' WHERE goal_id=?",(identity,))
        elif fault=='missing_outbox':db.execute('DELETE FROM outbox WHERE goal_id=?',(identity,))
        elif fault=='missing_signal':db.execute('DELETE FROM signals WHERE goal_id=? AND type=?',(identity,'neuron.fired'))
        elif fault=='changed_signal':
            row=db.execute("SELECT seq,body FROM signals WHERE goal_id=? AND type='neuron.succeeded' LIMIT 1",(identity,)).fetchone()
            body=json.loads(row[1]);body['payload_ref']='artifact://sha256/'+'0'*64
            db.execute('UPDATE signals SET body=? WHERE seq=?',(json.dumps(body),row[0]))
        elif fault in ('bad_binding','self_verifier'):
            plan=json.loads(journal.goal(identity)['plan'])
            if fault=='bad_binding':plan['steps'][1]['bind']['report']['step']='answer'
            else:plan['steps'][1]['neuron']=plan['steps'][0]['neuron']
            db.execute('UPDATE goals SET plan=? WHERE goal_id=?',(json.dumps(plan),identity))
        else:
            ref=db.execute('SELECT result_ref FROM outbox WHERE goal_id=? LIMIT 1',(identity,)).fetchone()[0]
            db.execute('UPDATE artifacts SET body=? WHERE ref=?',('{"forged":true}',ref))
    with pytest.raises(ValueError):oracle.clocks(journal,goals,base)

def test_changed_source_and_duplicate_runs_fail(clocks):
    journal,goals,base=clocks
    with pytest.raises(ValueError):oracle.clocks(journal,[goals[0]]*3,base)
    (base/'clock-0.json').write_text('{"beta":0.3,"coordinate_time_s":100}',encoding='utf-8')
    with pytest.raises(ValueError,match='source changed'):oracle.clocks(journal,goals,base)

def test_raw_json_is_not_a_journal_content_address(clocks):
    journal,_,_=clocks
    with pytest.raises(ValueError):oracle.artifact(journal,'{"passed":true}')
    with pytest.raises(ValueError):oracle.artifact(journal,'artifact://sha256/'+'f'*64)

def test_all_nine_cases_and_mandatory_gates_remain_visible():
    report=oracle.catalogue({})
    assert [c['case'] for c in report['cases']]==['A1','A2','B','C','D','E','F','G','H']
    assert all(c['status']=='UNMET' and c['reason'] for c in report['cases'])
    assert sum(report['rubric_weights'].values())==100
    with pytest.raises(ValueError):oracle.catalogue({'G':{'status':'PASSED_SUBCHECK'}})
    with pytest.raises(ValueError):oracle.catalogue({'D':{'passed':True}})
    assert oracle.catalogue({'D':{'status':'PASSED_SUBCHECK','full_acceptance_passed':True}})['full_acceptance_passed'] is False

def test_regression_uses_exact_ids_and_never_substitutes_for_live_H():
    current={'source_sha256_before':'a','source_sha256_after':'a','errors':0,'collection_errors':[],
             'reports':[{'test':'old','outcome':'failed'},{'test':'new','outcome':'failed'}],'passed':10,'failed':2,'skipped':1}
    report=oracle.verify_regression(current,{'remaining_failure_ids':['old','resolved']})
    assert report['new_failure_ids']==['new'] and report['resolved_failure_ids']==['resolved']
    assert report['H_passed'] is False
    current['source_sha256_after']='b'
    with pytest.raises(ValueError):oracle.verify_regression(current,{'remaining_failure_ids':[]})

def test_failed_subcheck_is_visible_and_cannot_earn_points():
    report=oracle.catalogue({'F':{'status':'FAILED','reason':'actual solver failed'}})
    assert next(c for c in report['cases'] if c['case']=='F')['status']=='FAILED'
    assert report['certified_full_acceptance_score']==0

def test_actual_numeric_study_oracle_rejects_changed_baseline_and_unobserved_resume(tmp_path,monkeypatch):
    from jarvis.discovery.model import optimization as opt
    from jarvis.commands import Command
    monkeypatch.setattr(opt,'reserve',lambda *args:0)  # Fixture never consumes the user's live50 slots.
    service=BrainService(ON,tmp_path/'brain.sqlite3');a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=ON,tmp_path,service,None;a.report=lambda *args:None
    try:
        source=json.loads((__import__('pathlib').Path(__file__).parents[1]/'examples/discovery/pendulum-study.json').read_text())
        (tmp_path/'study.json').write_text(json.dumps(source),encoding='utf-8')
        a.execute(Command('task','lab optimize "study.json"'))
        study=opt.Studies(service.journal);identity=study.create(tmp_path,'study.json')['study_id']
        for _ in range(3):a.execute(Command('task','lab optimize step "'+identity+'"'))
        goal=service.journal.rows('SELECT goal_id FROM goals ORDER BY rowid DESC LIMIT 1')[0]['goal_id']
        ref=study.describe(identity)['trials'][0]['run_ref']
        assert oracle.optimization(service.journal,goal,ref,23,['COMPLETED']*3)['status']=='PASSED_SUBCHECK'
        with pytest.raises(ValueError):oracle.optimization(service.journal,goal,'wrong-ref',23,['COMPLETED']*3)
        with pytest.raises(ValueError):oracle.optimization(service.journal,goal,ref,0,['COMPLETED']*3)
        with pytest.raises(ValueError):oracle.optimization(service.journal,goal,ref,23,['RUNNING']*3)
    finally:service.journal.close()
