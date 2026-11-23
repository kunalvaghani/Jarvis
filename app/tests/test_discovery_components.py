"""C1: graph integrity, bounded units, license vetoes, inert cache and real brain routing."""
import hashlib
import json
from pathlib import Path

import pytest
from jarvis.discovery.contracts import Quantity
from jarvis.discovery.model.component_graph import Project, ComponentGraph, fingerprint
from jarvis.discovery.model.parameter_registry import Change, plan
from jarvis.discovery.adapters.assets import AssetCandidate, assess, inspect_local, cache_local
from jarvis.discovery.sandbox.env_manager import units_environment

NEEDS_UNITS = pytest.mark.skipif(not units_environment()['pins_match'], reason='approved Pint environment absent')
ON = {'neural': {'mode': 'act', 'learning': 'shadow'}, 'lab': {'enabled': True, 'sim': True}}


def project_data():
    return {'id': 'wing-study', 'components': [
        {'id': 'chassis', 'name': 'chassis', 'reality_class': 'R2'},
        {'id': 'wing', 'name': 'front wing', 'parent_id': 'chassis', 'reality_class': 'R2',
         'missing': ['unmeasured internal geometry']}],
        'parameters': [{'component_id': 'wing', 'path': 'geometry.flap_angle', 'mutable': True,
                        'parameter': {'id': 'wing.angle', 'name': 'flap angle', 'lower': 0.0, 'upper': 20.0,
                                      'quantity': {'value': 10.0, 'unit': 'degree', 'origin': 'source', 'source_ref': 'user-study'}}}],
        'computations': [{'id': n, 'component_id': c, 'kind': k} for n, c, k in (
            ('wing.geometry', 'wing', 'geometry'), ('wing.mesh', 'wing', 'mesh'),
            ('wing.aero', 'wing', 'aero'), ('car.handling', 'chassis', 'mechanics'),
            ('chassis.thermal', 'chassis', 'thermal'))],
        'dependencies': [{'source': a, 'target': b} for a, b in (
            ('wing.angle', 'wing.geometry'), ('wing.geometry', 'wing.mesh'),
            ('wing.mesh', 'wing.aero'), ('wing.aero', 'car.handling'))],
        'scenario': {'id': 'dry-track', 'name': 'fixed dry reference', 'seed': 7,
                     'parameters': [{'id': 'world.gravity', 'name': 'gravity',
                                     'quantity': {'value': 9.81, 'unit': 'm/s^2', 'origin': 'source', 'source_ref': 'test-definition'}}]}}


def project():
    return Project.model_validate_json(json.dumps(project_data()))


def asset_data(body=b'visual shape only'):
    identity = {'manufacturer': 'McLaren', 'model': 'MCL39', 'year': 2025, 'rule_set': 'F1-2025'}
    return {'identity': identity, 'target': identity.copy(), 'representation': 'concept', 'relative_file': 'model.glb',
            'source': {'id': 'source-model', 'locator': 'https://example.org/artist-model', 'author': 'fixture creator',
                       'sha256': hashlib.sha256(body).hexdigest(), 'license': 'CC0-1.0'}, 'license_confirmed': True}


def test_only_downstream_work_is_invalidated_and_unknowns_remain_unknown():
    p = project()
    assert ComponentGraph(p).affected('wing.angle') == ('wing.geometry', 'wing.mesh', 'wing.aero', 'car.handling')
    assert p.components[1].mass.value is None
    assert 'chassis.thermal' not in ComponentGraph(p).affected('wing.angle')
    assert p.components[1].missing == ('unmeasured internal geometry',)


@pytest.mark.parametrize('mutation', ['cycle', 'parent-cycle', 'dangling', 'duplicate-id', 'duplicate-path', 'scenario-collision', 'overwrite-input'])
def test_invalid_assembly_and_dependency_graphs_are_rejected(mutation):
    data = project_data()
    if mutation == 'cycle': data['dependencies'].append({'source': 'car.handling', 'target': 'wing.geometry'})
    if mutation == 'parent-cycle': data['components'][0]['parent_id'] = 'wing'
    if mutation == 'dangling': data['dependencies'][0]['target'] = 'missing'
    if mutation == 'duplicate-id': data['computations'][0]['id'] = 'wing.angle'
    if mutation == 'duplicate-path': data['parameters'].append(data['parameters'][0].copy())
    if mutation == 'scenario-collision': data['scenario']['id'] = 'wing'
    if mutation == 'overwrite-input': data['dependencies'].append({'source': 'wing.mesh', 'target': 'wing.angle'})
    with pytest.raises(ValueError): Project.model_validate_json(json.dumps(data))


@NEEDS_UNITS
def test_change_plan_converts_units_preserves_scenario_and_never_runs_solver():
    p = project();original = fingerprint(p)
    change = Change(parameter_id='wing.angle', operation='delta',
                    quantity=Quantity(value=0.05235987755982989, unit='radian', origin='source', source_ref='user-command'))
    candidate, result = plan(p, change)
    assert result.after.quantity.value == pytest.approx(13.0)
    assert fingerprint(p) == original
    assert candidate.scenario == p.scenario
    assert result.scenario_sha256 == fingerprint(p.scenario)
    assert result.disposition == 'PLANNED_NOT_EXECUTED'
    assert result.after.revision == result.before.revision+1


@NEEDS_UNITS
@pytest.mark.parametrize('identity,value,unit', [('wing.angle', 30.0, 'degree'), ('wing.angle', 1.0, 'kg'), ('world.gravity', 2.0, 'm/s^2')])
def test_unsupported_change_cannot_cheat_units_bounds_or_scenario(identity, value, unit):
    with pytest.raises((ValueError, PermissionError)):
        plan(project(), Change(parameter_id=identity, operation='set',
             quantity=Quantity(value=value, unit=unit, origin='source', source_ref='user-command')))


def test_project_snapshots_reuse_journal_and_reject_rewriting_a_revision(tmp_path):
    from jarvis.neural.journal import Journal
    from jarvis.discovery.memory import LabMemory
    from jarvis.discovery.model.project_store import save, load
    j=Journal(tmp_path/'brain.sqlite3');memory=LabMemory(j);memory.migrate()
    try:
        p=project();ref=save(memory,p)
        assert save(memory,p)==ref and load(memory,p.id)==p
        data=project_data();data['components'][1]['name']='different wing'
        with pytest.raises(ValueError):save(memory,Project.model_validate_json(json.dumps(data)))
        assert load(memory,p.id)==p
    finally:j.close()


def test_concept_and_regulation_mismatch_are_never_exact():
    data=asset_data();data['target']['year']=2026;data['target']['rule_set']='F1-2026'
    result=assess(AssetCandidate.model_validate_json(json.dumps(data)))
    assert result['asset_state']=='FOUND_VISUAL_ONLY'
    assert 'identity mismatch: year' in result['gaps']
    assert 'identity mismatch: rule_set' in result['gaps']
    assert result['substitution_requires_approval']


@pytest.mark.parametrize('mutation', ['license', 'missing-license', 'credit', 'author', 'blank-credit', 'blank-author'])
def test_license_and_provenance_are_hard_rejects_even_with_other_good_fields(mutation):
    data=asset_data();data.update(dimensions_checked=True,functional_separation_checked=True,suitable_size=True)
    if mutation=='license':data['source']['license']='PROPRIETARY-NO-REUSE'
    if mutation=='missing-license':data['license_confirmed']=False
    if mutation=='credit':data['source']['license']='CC-BY-4.0'
    if mutation=='author':data['source']['author']=None
    if mutation=='blank-credit':data['source']['license']='CC-BY-4.0';data['attribution']='   '
    if mutation=='blank-author':data['source']['author']='   '
    result=assess(AssetCandidate.model_validate_json(json.dumps(data)))
    assert result['asset_state']=='REJECTED' and result['score'] is None and result['hard_rejects']


def test_asset_cache_keeps_bytes_license_attribution_and_hash_in_same_journal(tmp_path):
    from jarvis.neural.journal import Journal
    from jarvis.discovery.memory import LabMemory
    body=b'visual shape only';(tmp_path/'model.glb').write_bytes(body)
    data=asset_data(body);data['source']['license']='CC-BY-4.0';data['attribution']='fixture creator'
    candidate=AssetCandidate.model_validate_json(json.dumps(data))
    j=Journal(tmp_path/'brain.sqlite3');memory=LabMemory(j);memory.migrate()
    try:
        ref=cache_local(tmp_path,candidate,memory=memory)
        artifact_count=j.rows('SELECT COUNT(*) AS n FROM artifacts')[0]['n']
        assert cache_local(tmp_path,candidate,memory=memory)==ref
        assert j.rows('SELECT COUNT(*) AS n FROM artifacts')[0]['n']==artifact_count
        cached=json.loads(j.get(ref))
        assert cached['source']['license']=='CC-BY-4.0' and cached['attribution']=='fixture creator'
        assert cached['sha256']==hashlib.sha256(body).hexdigest()
        assert len(memory.list('RunArtifact'))==1
        (tmp_path/'model.glb').write_bytes(b'different bytes')
        with pytest.raises(ValueError):inspect_local(tmp_path,candidate)
    finally:j.close()


def test_rejected_asset_is_not_read_and_out_of_scope_path_is_refused(tmp_path):
    data=asset_data();data['license_confirmed']=False
    assert inspect_local(tmp_path,AssetCandidate.model_validate_json(json.dumps(data)))['asset_state']=='REJECTED'
    data=asset_data();data['relative_file']='../model.glb'
    with pytest.raises(ValueError):inspect_local(tmp_path,AssetCandidate.model_validate_json(json.dumps(data)))


@NEEDS_UNITS
def test_c1_text_requests_fire_through_actual_actions_brain_and_independent_verifier(tmp_path):
    from jarvis.neural.service import BrainService
    from jarvis.engine import Engine
    from jarvis.actions import Actions
    from jarvis.discovery.memory import LabMemory
    (tmp_path/'study.json').write_text(json.dumps(project_data()))
    service=BrainService(ON,tmp_path/'brain.sqlite3');actions=Actions.__new__(Actions)
    actions.config,actions.base,actions._neural_service,actions.allowed_tools=ON,tmp_path,service,None
    try:
        for goal in ('lab inspect project "study.json"','lab plan parameter "study.json" wing.angle delta 3 degree'):
            commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate();engine.feed(goal,final=True,raw=goal)
            assert commands
            answer=actions.execute(commands[0])
            assert answer
            last=service.journal.rows('SELECT goal_id,state FROM goals ORDER BY rowid DESC LIMIT 1')[0]
            assert last['state']=='verified'
            assert any(s['type']=='verification.passed' for s in service.journal.signals(last['goal_id']))
        assert len(LabMemory(service.journal).list('Component'))==2
        assert json.loads((tmp_path/'study.json').read_text())==project_data()
        commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate()
        invalid='lab plan parameter "study.json" wing.angle set 100 degree'
        engine.feed(invalid,final=True,raw=invalid)
        assert commands
        with pytest.raises(ValueError,match='brain stopped'):
            actions.execute(commands[0])
    finally:service.journal.close()


def test_c1_registration_is_default_off_and_explicit_when_enabled():
    from jarvis.discovery.c1 import neurons
    assert not neurons({})
    assert len(neurons(ON))==4
    assert all(n.contract=='explicit' and n.side_effect_class=='read_only' for n in neurons(ON))


def test_drive_source_adapter_only_reuses_existing_reads_and_labels_excerpt_hash():
    from unittest.mock import Mock
    from jarvis.discovery.adapters import drive_sources
    files=Mock();files.search.return_value=[{'id':'abcdef123456'}]
    files.read.return_value={'id':'abcdef123456','text':'abcdef','mimeType':'text/plain'}
    assert drive_sources.search(files,'wing')==[{'id':'abcdef123456'}]
    result=drive_sources.read(files,'abcdef123456',limit=3)
    files.read.assert_called_once_with('abcdef123456',limit=4)
    assert result['text']=='abc' and result['possibly_truncated']
    assert result['source']['sha256']==hashlib.sha256(b'abc').hexdigest()
    assert result['source']['license'] is None and result['content_is_untrusted']
    assert not files.create_text_file.called and not files.create_doc.called
    with pytest.raises(ValueError):drive_sources.read(files,'not/a/file')


def test_unknown_baseline_and_immutable_parameter_stop_before_unit_worker(monkeypatch):
    from jarvis.discovery.model import parameter_registry
    data=project_data();data['parameters'][0]['parameter']['quantity']={'value':None,'unit':'degree'}
    p=Project.model_validate_json(json.dumps(data))
    monkeypatch.setattr(parameter_registry,'convert',lambda *a,**k:pytest.fail('refused change reached worker'))
    change=Change(parameter_id='wing.angle',operation='delta',quantity=Quantity(value=1.0,unit='degree',origin='source',source_ref='user'))
    with pytest.raises(ValueError,match='unknown baseline'):plan(p,change)
    data=project_data();data['parameters'][0]['mutable']=False
    with pytest.raises(PermissionError):plan(Project.model_validate_json(json.dumps(data)),change)


@NEEDS_UNITS
def test_affine_unit_delta_does_not_add_absolute_temperature_offset():
    data=project_data();p=data['parameters'][0]['parameter'];p['quantity'].update(value=300.0,unit='kelvin');p['upper']=400.0
    data['parameters'][0]['path']='physical.temperature'
    _,result=plan(Project.model_validate_json(json.dumps(data)),Change(parameter_id='wing.angle',operation='delta',
             quantity=Quantity(value=3.0,unit='degC',origin='source',source_ref='user-command')))
    assert result.after.quantity.value==pytest.approx(303.0)
