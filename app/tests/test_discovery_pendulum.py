"""C2 mechanical credibility, approval boundaries and safe speech units; no native launch."""
import copy
import json
import math
from pathlib import Path

import pytest
from jarvis.discovery.model.pendulum import Pendulum, solve, independent_checks, compare_runs


def test_numerical_pendulum_matches_independent_period_energy_and_refinement():
    spec=Pendulum(initial_angle_rad=0.0001,duration_s=4.0)
    run=solve(spec);refined=solve(spec,max_step=0.01)
    expected=2*math.pi*math.sqrt((spec.length_m**2+0.4*spec.radius_m**2)/(spec.gravity_m_s2*spec.length_m))
    assert run['metrics']['measured_period_s']==pytest.approx(expected,rel=1e-5)
    assert run['metrics']['relative_energy_change']<1e-6
    assert max(abs(a['theta_rad']-b['theta_rad']) for a,b in zip(run['samples'],refined['samples']))<1e-8
    assert run['physical_validation'] is False


@pytest.mark.parametrize('values',[{'length_m':0.0},{'mass_kg':float('nan')},{'radius_m':0.2,'length_m':0.1},
    {'gravity_m_s2':0.0},{'duration_s':10000.0},{'dt_s':0.2},{'temperature_c':40.0},
    {'length_m':0.1,'radius_m':0.005,'gravity_m_s2':20.0,'dt_s':0.1}])
def test_unsupported_or_underresolved_model_is_rejected(values):
    with pytest.raises(ValueError):Pendulum(**values)


def test_frozen_motion_is_not_accepted_as_a_simulation_and_damping_is_passive():
    spec=Pendulum(duration_s=4.0);run=solve(spec);fake=copy.deepcopy(run)
    for row in fake['samples']:
        row.update(theta_rad=spec.initial_angle_rad,omega_rad_s=0.0,x_m=spec.length_m*math.sin(spec.initial_angle_rad),z_m=-spec.length_m*math.cos(spec.initial_angle_rad))
    with pytest.raises(ValueError,match='residual'):independent_checks(spec,fake)
    damped=solve(Pendulum(damping_nm_s=0.1,duration_s=4.0))
    assert abs(damped['samples'][-1]['theta_rad'])<spec.initial_angle_rad


def test_scenario_cannot_be_changed_to_make_a_comparison_pass():
    with pytest.raises(ValueError,match='same scenario'):
        compare_runs({'scenario_sha256':'a'},{'scenario_sha256':'b'})
    with pytest.raises(ValueError,match='cancelled'):
        solve(Pendulum(),cancelled=lambda:True)


def grant(tmp_path,monkeypatch):
    from jarvis.discovery.sandbox import local_trials
    monkeypatch.setattr(local_trials,'APP',tmp_path)
    root=tmp_path/'.jarvis-runtime/discovery/local-trials';root.mkdir(parents=True)
    (root/'authorization.json').write_text(json.dumps({'scope':'user-approved-free-local-c2-2026-11-04',
        'max_per_tool':50,'money':0,'tools':sorted(local_trials.TOOLS)}))
    return local_trials


def test_only_explicit_local_tools_get_fifty_durable_attempts(tmp_path,monkeypatch):
    trials=grant(tmp_path,monkeypatch)
    with pytest.raises(PermissionError):trials.reserve('paid-cloud','x')
    assert [trials.reserve('scipy-pendulum','fixture') for _ in range(50)]==list(range(50))
    with pytest.raises(PermissionError):trials.reserve('scipy-pendulum','fixture')


def test_native_build_requires_real_existing_approval_and_changed_source_is_preserved(tmp_path,monkeypatch):
    from jarvis.neural.service import BrainService
    from jarvis.actions import Actions
    from jarvis.commands import Command
    from jarvis.discovery.adapters import blender_pendulum
    grant(tmp_path,monkeypatch)
    monkeypatch.setattr(blender_pendulum,'native',lambda *a,**k:pytest.fail('unapproved/changed input reached Blender'))
    model=tmp_path/'pendulum.json';model.write_text(Pendulum(duration_s=4.0).model_dump_json())
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True}}
    service=BrainService(config,tmp_path/'brain.sqlite3');a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=config,tmp_path,service,None
    a.approval_handler=None;a.approvals_waiting=0
    try:
        with pytest.raises(ValueError,match='brain stopped'):
            a.execute(Command('task','lab build pendulum "pendulum.json"'))
        assert not (tmp_path/'.jarvis-runtime/discovery/experiments').exists()
        def approve(kind,detail,cancelled):
            assert kind=='brain' and 'discovery.geometry.pendulum' in detail
            model.write_text(Pendulum(length_m=2.0,duration_s=4.0).model_dump_json());return True
        a.approval_handler=approve
        with pytest.raises(ValueError,match='changed while awaiting approval'):
            a.execute(Command('task','lab build pendulum "pendulum.json"'))
        assert json.loads(model.read_text())['length_m']==2.0
        assert not (tmp_path/'.jarvis-runtime/discovery/experiments').exists()
    finally:service.journal.close()


def test_registered_c2_is_off_by_default_and_native_writes_stay_gated():
    from jarvis.discovery.c2 import neurons,NODES
    assert neurons({})==[]
    found={n.node_id:n for n in neurons({'lab':{'enabled':True,'sim':True}})}
    assert len(found)==4
    assert found[NODES['build']].gated and found[NODES['build']].side_effect_class=='local_write'
    assert found[NODES['solve']].side_effect_class=='read_only'


@pytest.mark.parametrize('text', ['Lab simulate divider 10V 1000Ω 1000Ω',
    'lab simulate divider 10 volts 1000 ohms and 1000 ohms'])
def test_actual_spoken_unit_forms_normalize_without_changing_numbers(text):
    from jarvis.commands import Command
    from jarvis.discovery.speech_units import normalize_command
    assert normalize_command(Command('task',text,'unparsed')).value=='lab simulate divider 10 V 1000 ohm 1000 ohm'


def test_speech_normalization_never_partially_accepts_shell_text_or_other_goals():
    from jarvis.commands import Command
    from jarvis.discovery.speech_units import normalize_command
    command=Command('task','open Ω file','unparsed');assert normalize_command(command) is command
    for text in ['lab simulate divider 10V 1000Ω 1000Ω; delete files','lab simulate divider ten volts unknown ohms']:
        with pytest.raises(ValueError,match='not sent to the general planner'):
            normalize_command(Command('task',text,'unparsed'))


def test_mismatched_native_result_never_promotes_components_or_experiment(tmp_path,monkeypatch):
    from jarvis.neural.service import BrainService
    from jarvis.neural.dispatcher import Env
    from jarvis.discovery.c2 import NODES
    from jarvis.discovery.memory import LabMemory
    from jarvis.discovery.adapters import blender_pendulum
    from types import SimpleNamespace
    grant(tmp_path,monkeypatch)
    (tmp_path/'pendulum.json').write_text(Pendulum(duration_s=4.0).model_dump_json())
    config={'neural':{'mode':'act'},'lab':{'enabled':True,'sim':True}}
    service=BrainService(config,tmp_path/'brain.sqlite3');env=Env(actions=SimpleNamespace(base=tmp_path),config=config)
    try:
        report=service.dispatcher.adapters[NODES['solve']](None,{'request':{'relative_file':'pendulum.json'}},env)['report']
        memory=LabMemory(service.journal);before=len(memory.list('RunArtifact'))
        monkeypatch.setattr(blender_pendulum,'native',lambda *a,**k:{'model_sha256':'wrong','trajectory_sha256':'wrong','parts':[]})
        verdict=service.dispatcher.adapters[NODES['native']](None,{'run':report,'native':{
            'directory':str(tmp_path/'no-native-files'),'experiment_id':report['experiment_id'],'component_ids':{}}},env)
        assert verdict['verdict']['passed'] is False
        assert memory.list('Component')==[] and len(memory.list('RunArtifact'))==before
        assert memory.get(report['experiment_id']).revision==1
    finally:service.journal.close()


def test_c2_native_project_reuses_c1_ids_world_and_dependency_plans(tmp_path):
    import uuid
    from jarvis.neural.journal import Journal
    from jarvis.discovery.memory import LabMemory
    from jarvis.discovery.model.pendulum_project import project
    from jarvis.discovery.model.component_graph import ComponentGraph,fingerprint
    j=Journal(tmp_path/'brain.sqlite3');memory=LabMemory(j);memory.migrate()
    try:
        ids={n:str(uuid.uuid5(uuid.NAMESPACE_URL,'demo:'+n)) for n in ('anchor','rod','bob')}
        _,a=project(Pendulum(),'owned-run-ref',ids,tmp_path,memory)
        _,b=project(Pendulum(length_m=1.5),'other-owned-run-ref',ids,tmp_path/'candidate',memory)
        assert fingerprint(a.scenario)==fingerprint(b.scenario)
        length=a.parameters[0].parameter.id
        affected=ComponentGraph(a).affected(length)
        assert ids['rod']+'.geometry' in affected and ids['anchor']+'.mechanics' in affected
        assert ids['bob']+'.geometry' not in affected
        assert {c.id for c in a.components}==set(ids.values())
    finally:j.close()


def test_real_pendulum_parameter_command_reuses_c1_units_and_keeps_source_scenario(tmp_path,monkeypatch):
    from jarvis.neural.service import BrainService
    from jarvis.actions import Actions
    from jarvis.commands import Command
    grant(tmp_path,monkeypatch)
    path=tmp_path/'model.json';original=Pendulum(duration_s=4.0).model_dump_json();path.write_text(original)
    config={'neural':{'mode':'act'},'lab':{'enabled':True,'sim':True}}
    s=BrainService(config,tmp_path/'brain.sqlite3');a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=config,tmp_path,s,None
    try:
        answer=a.execute(Command('task','lab simulate pendulum "model.json" length delta 50 cm'))
        assert '1.5' in answer and path.read_text()==original
        rows=s.journal.rows('SELECT body FROM artifacts WHERE data_type=?',('Report',))
        runs=[]
        for r in rows:
            try:value=json.loads(r['body'])
            except ValueError:continue
            if isinstance(value,dict) and value.get('solver')=='scipy.integrate.solve_ivp' and 'samples' in value:runs.append(value)
        assert runs[-1]['model']['length_m']==1.5 and runs[-1]['model']['gravity_m_s2']==9.81
        assert runs[-1]['requested_parameter_plan']['disposition']=='PLANNED_NOT_EXECUTED'
        with pytest.raises(ValueError,match='brain stopped'):
            a.execute(Command('task','lab simulate pendulum "model.json" length set 100 m'))
        data=json.loads(original);data.pop('mass_kg');path.write_text(json.dumps(data))
        with pytest.raises(ValueError,match='every physical input explicitly'):
            a.execute(Command('task','lab simulate pendulum "model.json"'))
    finally:s.journal.close()
