"""Independent ideal-circuit oracle tests; fixtures are never solver proof."""
import math

import pytest
from jarvis.discovery.adapters.divider import DividerInput, DividerVectors, netlist, verify


@pytest.mark.parametrize('voltage,upper,lower,out,current', [
    (10.0, 1000.0, 1000.0, 5.0, -0.005),
    (12.0, 2000.0, 1000.0, 4.0, -0.004),
    (-6.0, 1000.0, 2000.0, -4.0, 0.002),
    (0.0, 1000.0, 1000.0, 0.0, 0.0),
])
def test_independent_dc_oracle_and_explicit_source_sign(voltage, upper, lower, out, current):
    request = DividerInput(supply_v=voltage, upper_ohm=upper, lower_ohm=lower)
    checked = verify(request, DividerVectors(input_v=voltage, output_v=out, supply_current_a=current))
    assert checked.passed and not checked.problems
    assert checked.evidence_status == 'MODEL_CONSISTENT'
    assert len(checked.netlist_sha256) == 64


def test_wrong_sign_wrong_voltage_and_nonconservation_are_rejected():
    request = DividerInput(supply_v=10.0, upper_ohm=1000.0, lower_ohm=1000.0)
    result = verify(request, DividerVectors(input_v=9.0, output_v=6.0, supply_current_a=0.005))
    assert not result.passed
    assert len(result.problems) == 4


@pytest.mark.parametrize('change', [
    {'supply_v': math.inf}, {'supply_v': math.nan}, {'upper_ohm': 0.0},
    {'lower_ohm': -1.0}, {'supply_v': 101.0}, {'upper_ohm': 1e10},
    {'supply_v': '1\n.control\nshell unsafe'}, {'netlist': '.include unknown.lib'},
])
def test_invalid_physics_bounds_and_arbitrary_spice_are_rejected(change):
    values = dict(supply_v=5.0, upper_ohm=1000.0, lower_ohm=2000.0)
    with pytest.raises(ValueError):
        DividerInput(**(values | change))


def test_netlist_is_fixed_topology_and_missing_vectors_have_no_analytic_fallback():
    request = DividerInput(supply_v=5.0, upper_ohm=1000.0, lower_ohm=2000.0)
    assert netlist(request).splitlines() == [
        'Jarvis ideal DC divider', 'V1 vin 0 DC 5', 'R1 vin vout 1000', 'R2 vout 0 2000', '.op', '.end']
    with pytest.raises(ValueError):
        DividerVectors(input_v=5.0, output_v=10.0/3.0)
    with pytest.raises(TypeError):
        verify(request, None)


def test_proof_slots_survive_restarts_and_never_refund_uncertain_execution(tmp_path, monkeypatch):
    from jarvis.discovery.adapters import ngspice
    monkeypatch.setattr(ngspice, 'RUNTIME', tmp_path)
    monkeypatch.setattr(ngspice, '_proof_limit', lambda: 20)
    assert [ngspice._reserve_slot('request-ref') for _ in range(20)] == list(range(20))
    with pytest.raises(PermissionError, match='exhausted'):
        ngspice._reserve_slot('another-journal')
    assert len(list(tmp_path.glob('proof-slot-*.json'))) == 20


def test_missing_environment_and_cancel_never_execute_a_host_solver(tmp_path, monkeypatch):
    from jarvis.discovery.adapters import ngspice
    from jarvis.neural.journal import Journal
    monkeypatch.setattr(ngspice, 'RUNTIME', tmp_path)
    request = DividerInput(supply_v=5.0, upper_ohm=1000.0, lower_ohm=1000.0)
    journal = Journal(tmp_path / 'journal.sqlite3')
    try:
        with pytest.raises(RuntimeError, match='unavailable'):
            ngspice.solve(request, journal=journal)
        with pytest.raises(ValueError, match='cancelled'):
            ngspice.solve(request, journal=journal, cancelled=lambda: True)
    finally:
        journal.close()
    assert not list(tmp_path.glob('proof-slot-*.json'))


def test_fabricated_numerical_receipt_cannot_pass_brain_verifier(tmp_path):
    import json
    from jarvis.neural.service import BrainService
    from jarvis.neural.dispatcher import Env
    from jarvis.neural.contracts import digest
    config = {'neural': {'mode': 'act'}, 'lab': {'enabled': True, 'sim': True}}
    service = BrainService(config, tmp_path / 'brain.sqlite3')
    try:
        request = {'supply_v': 10.0, 'upper_ohm': 1000.0, 'lower_ohm': 1000.0}
        fabricated = {'input': request, 'vectors': {'input_v': 10.0, 'output_v': 5.0, 'supply_current_a': -0.005},
                      'evidence_status': 'SIMULATION_PASSED_WITH_ASSUMPTIONS'}
        ref = service.journal.put(fabricated, data_type='Report')
        report = {**fabricated, 'solver_ref': ref, 'request_digest': digest(request)}
        verifier = service.dispatcher.adapters['discovery.verify.divider@v1']
        result = verifier(None, {'request': request, 'report': report}, Env(config=config))
        assert result['verdict']['passed'] is False
    finally:
        service.journal.close()


def test_divider_intent_is_bounded_and_flags_off_never_compiles(tmp_path):
    from jarvis.neural.journal import Journal
    from jarvis.discovery.integration import compile_goal
    journal = Journal(tmp_path / 'brain.sqlite3')
    try:
        goal = 'lab simulate divider 10 V 1000 ohm 1000 ohm'
        assert compile_goal(goal, journal, {}) is None
        plan = compile_goal(goal, journal, {'lab': {'enabled': True, 'sim': True}})
        assert plan.steps[0].neuron == 'discovery.electronics.divider@v1'
        invalid = compile_goal('lab simulate divider 10 V 0 ohm 1000 ohm', journal,
                               {'lab': {'enabled': True, 'sim': True}})
        assert invalid is not None  # Typed adapter refuses; never fall back to LLM.
    finally:
        journal.close()


def test_wrong_library_size_is_rejected_before_reading_or_loading(tmp_path, monkeypatch):
    from jarvis.discovery.adapters import ngspice
    monkeypatch.setattr(ngspice, 'RUNTIME', tmp_path)
    for relative in ngspice.LIBRARIES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'changed-library')
    state = ngspice.environment()
    assert not state['ready']
    assert sum('reviewed library' in p for p in state['problems']) == 2


def test_invalid_supported_request_stops_in_brain_before_solver_or_legacy(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from jarvis.neural.service import BrainService, act
    from jarvis.discovery.adapters import ngspice
    config = {'neural': {'mode': 'act'}, 'lab': {'enabled': True, 'sim': True}}
    service = BrainService(config, tmp_path/'brain.sqlite3')
    monkeypatch.setattr(ngspice, 'solve', lambda *args, **kwargs: pytest.fail('invalid request reached solver'))
    try:
        actions = SimpleNamespace(config=config, _neural_service=service, allowed_tools=None)
        with pytest.raises(ValueError, match='brain stopped'):
            act(actions, 'lab simulate divider 10 V 0 ohm 1000 ohm', lambda: False)
        assert service.journal.rows('SELECT state FROM goals ORDER BY rowid DESC LIMIT 1')[0]['state'] != 'verified'
    finally:
        service.journal.close()


def test_unapproved_or_mismatched_proof_extension_is_rejected(tmp_path, monkeypatch):
    import json
    from jarvis.discovery.adapters import ngspice
    monkeypatch.setattr(ngspice, 'RUNTIME', tmp_path)
    path = tmp_path/'proof-authorization.json'
    path.write_text(json.dumps({'approved': True, 'max_invocations': 24, 'image_id': ngspice.IMAGE,
                               'scope': 'user-approved-linux-divider-proof-2026-11-04'}))
    with pytest.raises(ValueError):
        ngspice._proof_limit()
    path.write_text('[]')
    with pytest.raises(ValueError):
        ngspice._proof_limit()


def test_explicit_free_local_fifty_limit_retains_old_usage_and_enforces_cap(tmp_path, monkeypatch):
    import json
    from jarvis.discovery.adapters import ngspice
    monkeypatch.setattr(ngspice, 'RUNTIME', tmp_path)
    (tmp_path/'proof-authorization.json').write_text(json.dumps({'approved':True,'max_invocations':50,
        'image_id':ngspice.IMAGE,'scope':'user-approved-free-local-divider-proof-50-2026-11-04'}))
    for i in range(24):
        (tmp_path/f'proof-slot-{i:02}.json').write_text('{}')
    assert ngspice._proof_limit()==50
    assert [ngspice._reserve_slot('fixture-no-dispatch') for _ in range(26)]==list(range(24,50))
    with pytest.raises(PermissionError,match='exhausted'):
        ngspice._reserve_slot('attempt-51')
