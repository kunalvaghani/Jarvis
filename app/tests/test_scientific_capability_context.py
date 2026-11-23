"""Production tool discovery exposes real eligibility before scientific planning."""
from types import SimpleNamespace
from unittest.mock import patch
from jarvis.capabilities import runtime_context,intents
from jarvis.tools import ToolRegistry


def test_science_intent_prioritizes_registered_adapter_without_case_answers():
    goal='Find a model, simulate vehicle dynamics and compare its suspension.'
    assert 'scientific_lab' in intents(goal)
    a=SimpleNamespace(config={'lab':{'enabled':True,'sim':True,'research':True}})
    row=ToolRegistry(a)._lab_metadata([{'action':'discovery_call','description':'runtime API'}])[0]
    with patch('jarvis.discovery.adapters.chrono.qualification',return_value={'runtime_ready':False,'problems':['not installed']}):
        result=runtime_context(goal,[row])
    assert 'discovery_call' in result['tools']
    assert result['scientific_lab']['vehicle_runtime']['runtime_ready'] is False
    assert result['scientific_lab']['vehicle_workflow']=='lab compare vehicle "{request}"'
    assert 'source_contract' in result['scientific_lab']
    assert 'inputs' not in result['scientific_lab']


def test_absent_lab_tool_exposes_no_unsupported_runtime_or_schema():
    with patch('jarvis.discovery.adapters.chrono.qualification',side_effect=AssertionError('must not inspect runtime')):
        result=runtime_context('Simulate a vehicle',[])
    assert 'scientific_lab' not in result


def test_disabled_solver_schema_does_not_probe_installed_solver():
    a=SimpleNamespace(config={'lab':{'enabled':True,'sim':False,'research':False}})
    row=ToolRegistry(a)._lab_metadata([{'action':'discovery_call'}])[0]
    with patch('jarvis.discovery.adapters.chrono.qualification',side_effect=AssertionError('disabled')):
        result=runtime_context('Research physics',[row])
    assert 'vehicle_runtime' not in result['scientific_lab']


def test_other_scientific_families_do_not_probe_vehicle_runtime():
    a=SimpleNamespace(config={'lab':{'enabled':True,'sim':True,'research':True}})
    row=ToolRegistry(a)._lab_metadata([{'action':'discovery_call'}])[0]
    with patch('jarvis.discovery.adapters.chrono.qualification',side_effect=AssertionError('unrelated vehicle probe')):
        result=runtime_context('Simulate a pendulum',[row])
    assert 'vehicle_runtime' not in result['scientific_lab']
