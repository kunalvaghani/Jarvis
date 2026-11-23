"""Whole-goal claims cannot pass from browser screenshots or model assertions."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from jarvis.discovery.vehicle_assurance import applies,audit,completion_error,asset_query_error,search_step_error
from jarvis.brain import Brain

ON={'lab':{'enabled':True,'sim':True}}
GOAL='Simulate a 2025 F1 vehicle and compare the front wing under fixed conditions.'


def test_gate_is_narrow_and_flags_off_do_not_read_journal():
    assert applies(ON,GOAL)
    assert not applies({'lab':{'enabled':False,'sim':True}},GOAL)
    assert not applies(ON,'Find a photo of an F1 car')
    assert not applies(ON,'Simulate a pendulum')
    a=SimpleNamespace(config={'lab':{'enabled':False}},_neural_service=object())
    assert not audit(a,GOAL)['applies']


def test_prose_and_completed_browser_actions_never_satisfy_physical_requirements():
    a=SimpleNamespace(config=ON,task_state=None,_neural_service=None)
    r=audit(a,GOAL+' Also simulate 2026 active aero.')
    assert r['applies'] and not r['passed']
    assert set(r['checks'])=={'2025','2026'}
    assert not r['checks']['2025']['controlled_solver']
    assert not r['checks']['2026']['spatial_active_aero']
    assert 'licensed_asset_identity' in completion_error(a,GOAL)


def test_completion_rejection_uses_existing_bounded_correction_without_actions():
    actions=SimpleNamespace(config=ON,task_state=None,_neural_service=None,report=Mock(),acquisition=None)
    brain=Brain.__new__(Brain);brain.actions=actions;brain.options={'max_actions':10};brain.adaptive_controller=None
    brain.client=Mock();brain.client.request.return_value={'done':True,'steps':[],'reason':'I completed the entire car.'}
    brain.checkpoint=Mock()
    with pytest.raises(ValueError,match='checkpoint retained'):
        brain.propose_plan('plan',lambda:False,goal=GOAL,completed=[])
    assert brain.client.request.call_count==2
    second=brain.client.request.call_args.kwargs
    assert second['goal']==GOAL
    assert 'Independent scientific' in second['plan_validation_error']
    assert brain.checkpoint.call_count==2
    assert actions.report.call_count==2


@pytest.mark.parametrize('query',['McLaren F1 free downloadable model','McLaren free 3D model','1993 McLaren F1 model download'])
def test_whole_car_asset_query_cannot_drop_requested_year(query):
    goal='Find a legal 2025 McLaren F1 model and simulate vehicle dynamics.'
    assert '2025' in asset_query_error(ON,goal,query)
    assert search_step_error(ON,goal,{'action':'web_search','value':query})


@pytest.mark.parametrize('query',['2025 McLaren F1 free downloadable model','McLaren Sketchfab API authentication documentation','battery motor CAD model'])
def test_correct_scope_and_general_documentation_are_not_blocked(query):
    assert asset_query_error(ON,'Find a 2025 McLaren F1 model and simulate dynamics.',query) is None


def test_direct_asset_urls_are_not_rewritten_and_bing_query_is_checked():
    goal='Simulate a 2025 McLaren F1 model.'
    assert search_step_error(ON,goal,{'action':'web_open','value':'https://sketchfab.com/3d-models/model-id'}) is None
    assert search_step_error(ON,goal,{'action':'web_open','value':'https://www.bing.com/search?q=McLaren+F1+free+model'})


def test_catalog_context_preserves_year_even_without_model_keyword_in_query():
    goal='Find a 2025 McLaren F1 model and simulate dynamics.'
    assert search_step_error(ON,goal,{'action':'discovery_call','value':'lab assets search "McLaren F1"'})
    assert asset_query_error(ON,goal,'McLaren F1',catalog_search=True)
    assert search_step_error(ON,goal,{'action':'discovery_call','value':'lab assets search "2025 McLaren F1"'}) is None
    assert asset_query_error(ON,goal,'suspension bearing',catalog_search=True) is None
