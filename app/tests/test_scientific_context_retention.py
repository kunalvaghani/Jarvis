"""Verified source references survive native continuations and repair feedback."""
from unittest.mock import Mock
from types import SimpleNamespace
import pytest
from jarvis.native_tools import step_update
from jarvis.toolkits import virtual_scope_error,validate_step
from jarvis.brain import Brain


@pytest.mark.parametrize('feedback',[None,'invalid request field'])
def test_continuation_repeats_real_source_ids_without_case_parameters(feedback):
    sources={'source_refs':['actual-retained-source-id'],'content_is_untrusted':True,'metadata_candidates':[]}
    data={'goal':'original goal','capability_context':{'current_scientific_sources':sources}}
    if feedback:data['plan_validation_error']=feedback
    result=step_update(data,'discovery_call')
    assert result['scientific_sources']==sources
    assert result['goal']=='original goal'
    assert 'physical_parameters' not in result


def test_skill_namespace_is_rejected_as_file_scope_but_not_skill_scope():
    step={'action':'search_files','value':'model','folder':'@jarvis'}
    assert virtual_scope_error(step)
    with pytest.raises(ValueError,match='skill_list/skill_read'):validate_step(step)
    assert not virtual_scope_error({'action':'skill_read','folder':'@jarvis','value':'vehicle-comparison'})
    assert not virtual_scope_error({'action':'read_file','folder':'D:/selected-folder','value':'model.json'})


def test_bad_scope_correction_happens_before_file_dispatch():
    actions=SimpleNamespace(config={},task_state=None,report=Mock(),acquisition=None)
    brain=Brain.__new__(Brain);brain.actions=actions;brain.options={'max_actions':10};brain.adaptive_controller=None
    brain.client=Mock();brain.checkpoint=Mock()
    bad={'done':False,'steps':[{'action':'search_files','value':'model','folder':'@jarvis'}]}
    good={'done':False,'steps':[{'action':'skill_read','value':'vehicle-comparison','folder':'@jarvis'}]}
    brain.client.request.side_effect=[bad,good]
    assert brain.propose_plan('plan',lambda:False,goal='Find a model',completed=[])==good
    assert brain.client.request.call_count==2
    assert 'No file operation was executed' in brain.client.request.call_args.kwargs['plan_validation_error']


def test_continuous_goal_check_reports_missing_evidence_without_inference_or_replay():
    actions=SimpleNamespace(config={'lab':{'enabled':True,'sim':True}},task_state=None,report=Mock())
    brain=Brain.__new__(Brain);brain.actions=actions;brain.client=Mock();brain.checkpoint=Mock()
    brain.current_scientific_context={'source_refs':['retained-source']}
    goal='Simulate a 2025 McLaren F1 model with real vehicle dynamics.'
    brain.scientific_progress(goal)
    progress=brain.current_scientific_context['whole_goal_evidence']
    assert progress['passed'] is False and '2025: controlled_solver' in progress['missing']
    assert brain.current_scientific_context['source_refs']==['retained-source']
    assert '0/5' in actions.report.call_args.args[1]  # 2025 active aero is inapplicable, not verified evidence.
    assert brain.checkpoint.call_args.args==('scientific_progress',)
    brain.scientific_progress(goal)
    assert actions.report.call_count==1 and brain.checkpoint.call_count==1
    assert not brain.client.mock_calls  # Pure Journal audit; no planning or tool execution.
    continuation=step_update({'goal':goal,'capability_context':{
        'current_scientific_sources':brain.current_scientific_context}},'discovery_call')
    assert continuation['scientific_sources']['whole_goal_evidence']==progress


def test_continuous_goal_check_does_not_probe_disabled_or_unrelated_lab(monkeypatch):
    from jarvis.discovery import vehicle_assurance
    audit=Mock(side_effect=AssertionError('disabled Lab must not audit'))
    monkeypatch.setattr(vehicle_assurance,'audit',audit)
    brain=Brain.__new__(Brain);brain.actions=SimpleNamespace(config={},report=Mock());brain.checkpoint=Mock()
    brain.scientific_progress('Simulate a 2025 F1 car.')
    audit.assert_not_called()
    assert not brain.checkpoint.mock_calls
