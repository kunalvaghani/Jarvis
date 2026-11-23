"""Scientific foundations: immutable evidence, flag isolation, real Pint, and Journal-qualified growth."""
import json
import math
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from jarvis.discovery import contracts as C
from jarvis.discovery.memory import LabMemory
from jarvis.neural.journal import Journal, SecretPayload
from jarvis.discovery.sandbox.env_manager import units_environment

NEEDS_UNITS = pytest.mark.skipif(not units_environment()['pins_match'], reason='approved isolated Pint environment unavailable')

ON = {'neural': {'mode': 'act', 'learning': 'shadow'},
      'lab': {'enabled': True, 'sim': True, 'research': True, 'learning': True}}


@pytest.fixture
def journal(tmp_path):
    j = Journal(tmp_path / 'brain.sqlite3')
    yield j
    j.close()


def number(value=1.0, unit='m'):
    return C.Quantity(value=value, unit=unit, origin='deterministic', source_ref='analytic-reference')


def test_unknowns_bounds_nonfinite_and_llm_provenance():
    component = C.Component(id='wing', name='wing', reality_class='R2')
    assert component.mass.value is None
    for values in ({'value': 1.0, 'unit': 'm'}, {'value': math.nan, 'unit': 'm'},
                   {'value': 1.0, 'unit': 'm', 'origin': 'llm', 'source_ref': 'model'}):
        with pytest.raises(ValueError):
            C.Quantity(**values)
    with pytest.raises(ValueError):
        C.Parameter(id='angle', name='angle', quantity=number(4.0), lower=0.0, upper=3.0)
    with pytest.raises(ValueError):
        C.Component(id='x', name='x', reality_class='R2', fabricated_field=True)


def test_all_scientific_kinds_roundtrip(journal):
    memory = LabMemory(journal); memory.migrate()
    records = [C.Source(id='source', locator='https://example.org/reference'),
               C.Claim(id='claim', text='conditional claim', reality_class='T1'),
               C.Hypothesis(id='hypothesis', statement='null', prediction='no effect', is_null=True),
               C.Parameter(id='parameter', name='length', quantity=C.Quantity(unit='m')),
               C.Component(id='component', name='known part', reality_class='R2'),
               C.Scenario(id='scenario', name='fixed dry track'),
               C.Experiment(id='experiment', design_sha256='a'*64, scenario_sha256='b'*64,
                            solver='not-run-fixture', solver_version='fixture'),
               C.RunArtifact(id='artifact', sha256='c'*64, locator='fixture.json', media_type='application/json'),
               C.Capability(id='capability', neuron_id='discovery.status@v1', intents=('lab status',)),
               C.Tool(id='tool', name='fixture', version='1', environment='isolated-fixture'),
               C.Skill(id='skill', path='fixture/SKILL.md', sha256='d'*64),
               C.LearningEpisode(id='episode', gap='missing solver', tool_id='tool', stage='gap')]
    for record in records:
        ref = memory.put(record)
        assert memory.put(record) == ref
        assert memory.get(record.id) == record
    assert {r.kind for r in records} == {'Source', 'Claim', 'Hypothesis', 'Parameter', 'Component', 'Scenario',
                                         'Experiment', 'RunArtifact', 'Capability', 'Tool', 'Skill', 'LearningEpisode'}


def test_migration_rollback_preserves_history_and_existing_tables(journal):
    before = {r['name'] for r in journal.rows("SELECT name FROM sqlite_master WHERE type='table'")}
    memory = LabMemory(journal); memory.migrate(); memory.migrate()
    original = C.Source(id='s', locator='reference')
    memory.put(original)
    with pytest.raises(ValueError, match='immutable'):
        memory.put(C.Source(id='s', locator='different'))
    memory.put(original.model_copy(update={'revision': 2, 'locator': 'v2'}))
    assert len(memory.list('Source')) == 1
    memory.deactivate()
    with pytest.raises(ValueError, match='inactive'):
        memory.put(C.Source(id='new', locator='blocked'))
    assert memory.get('s', 1) == original
    memory.migrate()
    assert memory.get('s').revision == 2
    assert before <= {r['name'] for r in journal.rows("SELECT name FROM sqlite_master WHERE type='table'")}


def test_secrets_and_dangling_relations_are_rejected(journal):
    memory = LabMemory(journal); memory.migrate()
    with pytest.raises(SecretPayload):
        memory.put(C.Source(id='secret', locator='token=sk-this-is-a-private-test-key-1234567890'))
    assert memory.get('secret') is None
    memory.put(C.Source(id='source', locator='reference'))
    with pytest.raises(ValueError, match='dangling'):
        memory.link(C.Edge(source='source', target='absent', relation='supports', source_ref='reference'))
    memory.put(C.Claim(id='claim', text='a conditional statement', reality_class='T1'))
    edge = C.Edge(source='source', target='claim', relation='supports', source_ref='reference')
    assert memory.link(edge) == memory.link(edge)


def test_reference_index_uses_existing_reasoning_bank_without_personal_facts(journal, tmp_path):
    from jarvis.reasoning_bank import ReasoningBank
    memory = LabMemory(journal); memory.migrate()
    bank = ReasoningBank(tmp_path, embedder=lambda text: [1.0, 0.0])
    memory.put(C.Claim(id='c', text='simulation result', reality_class='T1'))
    memory.index_reference(bank, 'c', 1)
    assert bank.items() == []  # Scientific text never becomes a personal fact or reasoning strategy.
    with bank.connect() as db:
        assert db.execute('SELECT kind FROM discovery_references').fetchone()[0] == 'Claim'


@NEEDS_UNITS
def test_pint_known_answers_unknowns_and_dimension_rejection():
    from jarvis.discovery.model.units import convert
    assert convert(number(1.0, 'km'), 'm').value == 1000.0
    assert convert(number(0.0, 'degC'), 'kelvin').value == pytest.approx(273.15)
    assert convert(C.Quantity(unit='kg'), 'g').value is None
    with pytest.raises(ValueError):
        convert(number(1.0, 'kg'), 'second')
    with pytest.raises(ValueError):
        convert(number(1.0, 'm^99^99'), 'm')
    from jarvis.discovery.golden import run
    assert run('pint_si_and_temperature')[0].passed
    assert not run('an-unreviewed-evaluator')[0].passed


def test_default_off_does_not_import_or_construct_lab_state(tmp_path):
    from jarvis.neural.service import BrainService
    service = BrainService({'neural': {'mode': 'act'}}, tmp_path / 'off.sqlite3')
    try:
        assert not any(n.startswith('discovery.') for n in service.registry.nodes)
        assert service.journal.rows("SELECT name FROM sqlite_master WHERE name LIKE 'discovery_%'") == []
        from jarvis.neural.compiler import compile_goal
        assert compile_goal('lab convert 1 km to m', service.journal, {}) is None
    finally:
        service.journal.close()


@NEEDS_UNITS
def test_brain_routes_real_unit_conversion_and_query_from_same_memory(tmp_path):
    from jarvis.neural.service import BrainService, act
    service = BrainService(ON, tmp_path / 'on.sqlite3')
    actions = SimpleNamespace(config=ON, _neural_service=service, allowed_tools=None)
    try:
        answer = act(actions, 'lab convert 1 km to m', lambda: False)
        assert '1000.0' in answer and 'MODEL_CONSISTENT' in answer
        assert service.journal.rows("SELECT state FROM goals")[-1]['state'] == 'verified'
        assert 'discovery.units.convert@v1' in act(actions, 'what can you do in the lab?', lambda: False)
        assert len(LabMemory(service.journal).list('Capability', limit=200)) == sum(
            identity.startswith('discovery.') for identity in service.graph.neurons)
        from jarvis.neural.policy import Context, eligibility
        for node in service.registry.nodes.values():
            if node.node_id.startswith('discovery.'):
                assert not eligibility(node, Context(config={})).eligible
    finally:
        service.journal.close()


@NEEDS_UNITS
def test_wrong_target_unit_cannot_pass_roundtrip_only_verifier(tmp_path):
    from jarvis.neural.service import BrainService
    from jarvis.neural.dispatcher import Env
    from jarvis.neural.contracts import digest
    service = BrainService(ON, tmp_path / 'j.sqlite3')
    try:
        request = {'quantity': number(1.0, 'km').model_dump(mode='json'), 'target': 'm'}
        report = {'quantity': number(1.0, 'km').model_dump(mode='json'), 'request_digest': digest(request),
                  'evidence_status': 'MODEL_CONSISTENT'}
        verifier = service.dispatcher.adapters['discovery.verify.units@v1']
        assert not verifier(None, {'request': request, 'report': report}, Env(config=ON))['verdict']['passed']
    finally:
        service.journal.close()


def test_research_scouts_are_scoped_and_sim_requires_master_flag():
    from jarvis.discovery.catalog import research_config, enabled
    scoped = research_config(ON)
    assert scoped['control']['web_scouts'] is True
    assert 'control' not in ON
    assert not enabled({'lab': {'sim': True}}, 'sim')


def test_budget_restart_uncertain_reservations_and_no_paid_gpu_bypass(journal):
    from jarvis.discovery.sandbox.budget import Budget, BudgetExceeded
    budget = Budget(journal, cpu_s=5.0, disk_bytes=1000)
    budget.reserve('a', cpu_s=4.0)
    budget.settle('a', uncertain=True)
    reopened = Budget(journal, cpu_s=5.0, disk_bytes=1000)
    with pytest.raises(BudgetExceeded):
        reopened.reserve('b', cpu_s=2.0)
    for args in ({'money': 0.01}, {'vram_mb': 1}):
        with pytest.raises(BudgetExceeded):
            reopened.reserve('new', cpu_s=0.0, **args)
    for value in (True, -1.0, math.inf):
        with pytest.raises(ValueError):
            reopened.reserve('bad', cpu_s=value)


@NEEDS_UNITS
def test_golden_gate_rejects_false_goals_and_duplicate_use_counts(tmp_path):
    from jarvis.neural.service import BrainService, act
    from jarvis.discovery.learning import LearningGate
    from jarvis.discovery.sandbox.env_manager import units_environment
    service = BrainService(ON, tmp_path / 'j.sqlite3')
    actions = SimpleNamespace(config=ON, _neural_service=service, allowed_tools=None)
    try:
        memory = LabMemory(service.journal)
        gate = LearningGate(memory, service.registry, ON)
        source = C.Source(id='pypi-pint', locator='https://pypi.org/project/Pint/0.25.2/', license='BSD-3-Clause')
        tool = C.Tool(id='pint', name='Pint', version='0.25.2', environment=units_environment()['environment'], license='BSD-3-Clause')
        episode, candidate = gate.qualify(tool, source, 'discovery.units.convert@v1')
        assert candidate.status == 'proposed'
        with pytest.raises(ValueError):
            gate.observe_use(episode.id, candidate.node_id, 'invented-goal')
        for i in (1, 2, 3):
            act(actions, f'lab convert {i} km to m', lambda: False)
            goal_id = service.journal.rows('SELECT goal_id FROM goals ORDER BY rowid DESC LIMIT 1')[0]['goal_id']
            capability = gate.observe_use(episode.id, candidate.node_id, goal_id)
            gate.observe_use(episode.id, candidate.node_id, goal_id)
            assert len(memory.get(episode.id).successful_goal_ids) == i
            assert capability.verification == ('VERIFIED' if i == 3 else 'LEARNED_UNVERIFIED')
        assert service.registry.get(candidate.node_id).status == 'active'
        service.rebuild()
        act(actions, 'lab convert 4 km to m', lambda: False)
        goal_id = service.journal.rows('SELECT goal_id FROM goals ORDER BY rowid DESC LIMIT 1')[0]['goal_id']
        assert any(e.get('target_node') == candidate.node_id and e['type'] == 'neuron.fired'
                   for e in service.journal.signals(goal_id))
        with patch('jarvis.discovery.learning.run', return_value=(SimpleNamespace(passed=False, details=('failed',)), 'fixture-ref')):
            failed, absent = gate.qualify(tool, source, 'discovery.units.convert@v1')
            assert failed.stage == 'golden_failed' and absent is None
    finally:
        service.journal.close()


def test_scientific_source_hash_uses_existing_path_scope(tmp_path):
    from jarvis.discovery.model.provenance import local_source
    (tmp_path / 'reference.txt').write_text('published dimensions', encoding='utf-8')
    assert len(local_source(tmp_path, 'reference.txt').sha256) == 64
    with pytest.raises(ValueError):
        local_source(tmp_path, '../outside.txt')


def test_google_read_contracts_never_downgrade_writes():
    from jarvis.google_contracts import CONTRACTS, READ_TOOLS
    from jarvis.neural.registry import Registry
    from jarvis.hierarchical import READ_TOOLS as DAG_READS
    registry = Registry().refresh()
    assert READ_TOOLS <= DAG_READS
    for name, contract in CONTRACTS.items():
        node = registry.by_tool(name)
        assert node.contract == 'explicit'
        assert node.privacy == 'local_private'
        if name in READ_TOOLS:
            assert node.side_effect_class == 'read_only'
        else:
            assert node.side_effect_class == 'external_write' and node.gated and name not in DAG_READS


def test_jobs_use_the_existing_queue_and_checkpoint_owner(journal):
    from jarvis.discovery.jobs import submit, checkpoint
    from unittest.mock import Mock
    queue, token = Mock(), SimpleNamespace()
    submit(queue, ON, 'lab convert 1 km to m', 7, token)
    generation, command, same_token = queue.put_nowait.call_args.args[0]
    assert generation == 7 and command.kind == 'task' and same_token is token
    with pytest.raises(PermissionError):
        submit(queue, {}, 'lab convert 1 km to m', 7, token)
    memory = LabMemory(journal); memory.migrate()
    experiment = C.Experiment(id='exp', design_sha256='a'*64, scenario_sha256='b'*64,
                              solver='fixture-only', solver_version='1')
    state = Mock()
    ref = checkpoint(memory, state, experiment)
    state.checkpoint.assert_called_once_with('discovery.experiment', evidence=ref, source='brain_journal')


@NEEDS_UNITS
def test_text_ingress_and_actions_execute_route_the_lab_without_a_model(tmp_path):
    from jarvis.engine import Engine
    from jarvis.actions import Actions
    from jarvis.neural.service import BrainService
    commands = []
    engine = Engine(commands.append, lambda *args: None)
    engine.activate()
    engine.feed('lab convert 2 km to m', final=True, raw='lab convert 2 km to m')
    assert commands
    service = BrainService(ON, tmp_path / 'j.sqlite3')
    # Use actual Actions.execute without starting the UI, microphone, connectors or workers.
    actions = Actions.__new__(Actions)
    actions.config, actions.base, actions._neural_service = ON, tmp_path, service
    actions.allowed_tools = None
    try:
        assert '2000.0' in actions.execute(commands[0])
        from jarvis.commands import parse
        assert 'Lab foundations:' in actions.execute(parse('what can you do in the lab?'))
    finally:
        service.journal.close()


def test_nested_discovery_guides_use_existing_skill_loader_only_when_enabled(tmp_path):
    from jarvis.skill_memory import SkillMemory
    root = tmp_path / 'jarvis/skills/discovery/lab-fixture'
    root.mkdir(parents=True)
    (root / 'SKILL.md').write_text('---\nname: lab-fixture\ndescription: Owned fixture\ntools: []\n---\nEvidence only.\n', encoding='utf-8')
    memory = SimpleNamespace(base=tmp_path, vault=tmp_path/'vault', enabled=False, experience_options={})
    off = SkillMemory(memory, source=tmp_path / 'builtins')
    on = SkillMemory(memory, source=tmp_path / 'builtins', discovery=True)
    try:
        assert not any(r['name'] == 'lab-fixture' for r in off.catalog)
        assert any(r['name'] == 'lab-fixture' and r['origin'] == 'Discovery' for r in on.catalog)
        assert not (root / '.skill_id').exists()  # The namespaced source is read-only guidance.
    finally:
        off.close(); on.close()


def test_caller_fabricated_pass_artifact_cannot_promote(journal):
    from jarvis.discovery.golden import GoldenReceipt, implementation_hash, load
    import platform
    forged = GoldenReceipt(case='foundation_status', passed=True, implementation_sha256=implementation_hash(),
                            python=platform.python_version(), seconds=0.0, details=('caller asserted success',))
    ref = journal.put(forged.model_dump(mode='json'), 'Report')
    with pytest.raises(ValueError):
        load(journal, ref, 'foundation_status')
