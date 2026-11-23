"""Controlled integration checks; these are not autonomous A–H acceptance."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jarvis.discovery.planner_access import execute, _payload
from jarvis.neural.service import BrainService
from jarvis.task_state import TaskState
from jarvis.tools import ToolRegistry

ON = {'neural': {'mode':'act','learning':'shadow'},
      'lab': {'enabled':True,'sim':True,'research':True,'learning':False}}


@pytest.fixture
def actions(tmp_path):
    service = BrainService(ON, tmp_path/'brain.sqlite3')
    state = TaskState(tmp_path)
    state.start('Investigate a scientific question','task')
    value = SimpleNamespace(config=ON,base=tmp_path,task_state=state,_neural_service=service,
                            _approve=Mock(side_effect=ValueError('No fixture approval')))
    yield value
    service.journal.close()


def test_disabled_is_hidden_and_execution_fails_before_import_or_service(tmp_path):
    value=SimpleNamespace(config={},base=tmp_path)
    registry=ToolRegistry(value)
    assert 'discovery_call' not in {r['action'] for r in registry.catalog('science')}
    assert 'discovery_call' not in {r['action'] for r in registry.search('science')}
    with pytest.raises(ValueError,match='disabled'):
        execute(value,'lab status','',lambda:False)
    assert not list(tmp_path.iterdir())


def test_planner_gets_real_native_schema_and_help(actions):
    from jarvis.native_tools import functions,parse
    rows=ToolRegistry(actions).catalog('Investigate scientific questions')
    definition=next(r for r in functions(rows) if r['function']['name']=='discovery_call')
    assert {'operation','expected'} <= set(definition['function']['parameters']['required'])
    proposal=parse({'tool_calls':[{'function':{'name':'discovery_call','arguments':
        {'operation':'help','topic':'mechanics','expected':'Inspect supported scientific workflows'}}}]},rows)
    assert proposal['steps'][0]['action']=='discovery_call'
    assert proposal['steps'][0]['value']=='help mechanics'
    report=json.loads(execute(actions,'help','',lambda:False))
    assert 'pendulum' in report['schema_names'] and 'dilation' in report['schema_names']
    assert json.loads(execute(actions,'help mechanics','',lambda:False))['schema']['properties']['units']['const']=='SI'
    assert not actions._approve.called


def test_child_uses_real_dispatcher_and_reuses_same_task_receipt(actions,monkeypatch):
    service=actions._neural_service
    original=service.dispatcher.run
    calls=[]
    def observe(*a,**kw):
        calls.append(a[0].goal_id)
        return original(*a,**kw)
    monkeypatch.setattr(service.dispatcher,'run',observe)
    first=json.loads(execute(actions,'lab status','',lambda:False))
    second=json.loads(execute(actions,'lab status','',lambda:False))
    assert first==second and len(calls)==1
    assert first['verified'] and not first['physical_validation']
    assert first['autonomous_task_id']==actions.task_state.identity()
    assert service.journal.goal(first['goal_id'])['state']=='verified'


@pytest.mark.parametrize('content',['[]','{"x":NaN}','{"approved":true}','{"nested":{"authorization":"yes"}}'])
def test_proposals_cannot_supply_nonfinite_or_approval_values(content):
    with pytest.raises(ValueError):_payload(content)


@pytest.mark.parametrize('command,content',[
    ('open calculator',''),('lab nonexistent',''),('lab status','{}'),
    ('lab theory dilation {request}','{}'),('lab status\nopen calculator','')])
def test_unknown_or_invalid_commands_never_reach_adapter(actions,command,content,monkeypatch):
    monkeypatch.setattr(actions._neural_service.dispatcher,'run',lambda *a:pytest.fail('invalid dispatch'))
    with pytest.raises(ValueError):execute(actions,command,content,lambda:False)


def test_uncertain_child_is_not_replayed(actions,monkeypatch):
    calls=[]
    def fail(*a,**kw):
        calls.append(1)
        raise OSError('fixture interruption after dispatch')
    monkeypatch.setattr(actions._neural_service.dispatcher,'run',fail)
    with pytest.raises(OSError):execute(actions,'lab status','',lambda:False)
    with pytest.raises(ValueError,match='Prior Lab call'):
        execute(actions,'lab status','',lambda:False)
    assert calls==[1]


def test_request_artifact_retains_unverified_provenance_even_on_failure(actions,monkeypatch):
    from jarvis.discovery.memory import LabMemory
    from jarvis.neural.dispatcher import Outcome
    def refuse(plan,*a,**kw):return Outcome(plan.goal_id,'blocked','synthetic unavailable solver')
    monkeypatch.setattr(actions._neural_service.dispatcher,'run',refuse)
    with pytest.raises(ValueError,match='blocked'):
        execute(actions,'lab simulate pendulum "{request}"','{"length_m":0.7}',lambda:False)
    files=list((actions.base/'.jarvis-runtime/discovery/requests').glob('*.json'))
    assert len(files)==1 and json.loads(files[0].read_text(encoding='utf-8'))=={'length_m':0.7}
    sources=LabMemory(actions._neural_service.journal).list('Source')
    source=next(s for s in sources if s.id.startswith('proposal-'))
    assert source.evidence_status=='INSUFFICIENT_EVIDENCE' and 'unverified' in source.justification
    assert not actions._approve.called


def test_delegated_work_is_not_automatically_replanned():
    from jarvis.brain import replannable
    assert not replannable({'action':'discovery_call'},ToolRegistry(SimpleNamespace()).specs)


def test_real_conditional_clock_workflow_materializes_its_own_proposal(actions):
    # Canonical controlled integration check, not the autonomous time-travel case.
    result=json.loads(execute(actions,'lab theory dilation "{request}"',
        '{"coordinate_time_s":10.0,"beta":0.6}',lambda:False))
    assert result['verified'] and result['input_origin']=='model_proposed_unverified'
    assert not result['physical_validation']
    assert actions._neural_service.journal.goal(result['goal_id'])['state']=='verified'
    assert len(list((actions.base/'.jarvis-runtime/discovery/requests').glob('*.json')))==1


def test_ordinary_planner_reads_actual_lab_result_without_desktop_verification(actions):
    # Synthetic model proposals exercise the real loop/registry/child dispatcher.
    # This is a controlled integration fixture, never an autonomous case pass.
    from jarvis.brain import Brain
    actor=Mock()
    actor.config,actor.base,actor._neural_service=actions.config,actions.base,actions._neural_service
    actor.task_state,actor.allowed_tools,actor.apps=actions.task_state,None,{}
    actor.pending_open=None
    actor.last_created=actor.last_modified=actor.last_deleted=actor.last_command=None
    brain=Brain(actor,actions.base,{'enabled':True,'planner':'qwen3.5:9b','decision':'qwen3.5:9b'})
    actor.brain=brain
    brain.client=Mock()
    brain.observe=Mock(return_value=(0,{'title':'Desktop','controls':[]}))
    brain.observe_after_action=Mock(side_effect=AssertionError('A Lab result is not a desktop change'))
    step={'action':'discovery_call','value':'lab status','content':'','folder':'','expected':'Read actual Lab status'}
    def inference(operation,cancelled,**data):
        if operation=='plan':return {'steps':[step]}
        if operation=='decide':return {'approved':True}
        # The whole-goal verifier receives tool output as data, not trusted instructions.
        evidence=(json.dumps(data['screen'].get('tool_results',[])) if data['step']['action']=='goal'
                  else ' '.join(data['screen']['trusted_evidence']))
        assert 'Lab foundations' in evidence and 'physical_validation' in evidence
        return {'verified':True}
    brain.client.request.side_effect=inference
    assert 'Finished' in brain.run('Show scientific lab capabilities',lambda:False)
    brain.observe_after_action.assert_not_called()
