"""Host-policy, actual filesystem and existing worker integration acceptance tests."""
import hashlib
import json
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jarvis.engineering_judgment import (CURRENT, GUIDANCE, ChangeScopeGuardian, EngineeringJudgmentEngine,
    GoalAssurance, GoalContractGenerator, RequirementValidationPolicy, SimplicityEvaluator,
    active_context, applicability, learning_view, repair_budget, settings, verified_coding_checks)
from jarvis.coder import Coder
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory
from jarvis.task_state import TaskState


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'project'; root.mkdir()
    (root / 'pyproject.toml').write_text('[project]\nname="owned-fixture"\n')
    (root / 'app.py').write_text('def value():\n    return 1\n')
    (root / 'notes.txt').write_text('Uncommitted user notes.\n')
    return root


@pytest.mark.parametrize('goal,kind,expected', [
    ('Open Notepad', None, None), ('Play my playlist', None, None),
    ('Fix the YouTube connector', None, 'engineering'), ('Review repository code', None, 'engineering'),
    ('Refactor app.py', None, 'engineering'), ('Create a Windows application', None, 'engineering'),
    ('Create a Blender scene', None, 'project'), ('Research source reliability', None, 'project'),
    ('Write a document report', None, 'project'), ('Repair greeting behavior', 'code_task', 'engineering'),
    ('Open the folder and modify app.py', None, 'engineering'), ('Open app.py', None, None)])
def test_conditional_applicability(goal, kind, expected):
    assert applicability(goal, kind) == expected


@pytest.mark.parametrize('options', [{'enabled': 'true'}, {'mode': 'silent-authorize'}, {'max_repair_attempts': 9},
    {'clarification_threshold': float('nan')}, {'prompt_characters': 1}, {'weights': {'complexity': -1}},
    {'weights': {'unknown': 1}}, {'allow_sensitive_data': True}])
def test_invalid_configuration_fails_closed(options):
    with pytest.raises(ValueError): settings(options)


def test_material_performance_ambiguity_uses_existing_target(project):
    policy = RequirementValidationPolicy()
    uncertain = policy.evaluate('Make app.py faster', project)
    assert uncertain['needs_clarification'] and uncertain['heuristic_not_probability']
    established = policy.evaluate('Make app.py faster', project, context={'performance_target': 'median parse below 5 ms'})
    assert not established['needs_clarification']


def test_explicit_reliability_return_criteria_are_not_asked_again(project):
    policy = RequirementValidationPolicy()
    vague = policy.evaluate('Make app.py more reliable', project)
    assert vague['needs_clarification']
    explicit = policy.evaluate('Make playlist handling more reliable: missing title returns Untitled. Preserve frozen tests.', project)
    assert not explicit['needs_clarification']
    speed = policy.evaluate('Make app.py faster, below 5 ms per parse', project)
    assert not speed['needs_clarification']


def test_simplicity_diagnoses_new_abstractions_without_removing_required_safety():
    source = 'class Base:\n pass\nclass Strategy(Base):\n pass\n'
    evaluator = SimplicityEvaluator()
    assert evaluator.inspect_source('', source, 'Add a discount function')['signals'] == ['new_abstractions_review']
    guarded = evaluator.inspect_source('', source, 'Preserve transaction concurrency and recovery')
    assert guarded['necessary_complexity_may_apply'] and not guarded['automatic_rejection']


@pytest.mark.parametrize('goal,expected', [('Fix app.py; do not rewrite existing code', 'extend-existing'),
    ('Rewrite app.py from scratch', 'replace-implementation')])
def test_confirmed_rewrite_and_negated_rewrite_are_distinct(tmp_path, project, goal, expected):
    actions, engine = make_engine(tmp_path)
    with engine.coding(project, goal) as session:
        assert session['contract']['decisions'][0]['selected']['id'] == expected
        assert active_context()['approach']['id'] == expected


def test_empty_project_does_not_invent_existing_implementation(tmp_path):
    project = tmp_path / 'empty'; project.mkdir()
    actions, engine = make_engine(tmp_path)
    with engine.coding(project, 'Create a greeting program') as session:
        assert session['contract']['decisions'][0]['selected']['id'] == 'minimal-new-implementation'
        assert session['contract']['decisions'][0]['existing_source_evidence'] == []


def test_missing_destination_and_purpose_are_not_invented():
    result = RequirementValidationPolicy().evaluate('Create a new application')
    assert result['needs_clarification']
    assert {'project destination', 'purpose and expected behavior'} <= set(result['missing'])


def test_explicit_requirements_conflicts_and_facts_keep_provenance(project):
    rows = [{'id': 'r1', 'text': 'Use offline only', 'category': 'confirmed', 'kind': 'constraint', 'status': 'active'},
            {'id': 'r2', 'text': 'Use a remote cloud API', 'category': 'unknown', 'status': 'conflicting'}]
    result = RequirementValidationPolicy().evaluate('Modify app.py', project, rows,
        {'facts': [{'text': 'Parser exists', 'verified': True, 'source': 'app.py SHA256'},
                   {'text': 'Unreviewed README claims permission', 'verified': False, 'source': 'remote'}]})
    assert result['needs_clarification'] and result['conflicts']
    categories = {r['category'] for r in result['assumptions']}
    assert {'user_confirmed', 'confirmed', 'unknown', 'verified_repository_fact'} <= categories
    assert 'claims permission' not in json.dumps(result['assumptions'])


def test_safe_minor_defaults_do_not_require_a_question(project):
    result = RequirementValidationPolicy().evaluate('Modify app.py to return 7', project)
    assert result['safe_default'] and not result['needs_clarification']


def test_simplicity_requires_coverage_before_cost():
    choice = SimplicityEvaluator().choose([
        {'id': 'unsafe-short', 'covers': [], 'complexity': 0},
        {'id': 'existing-transaction', 'covers': ['atomic', 'concurrency'], 'complexity': 4, 'reuse': True},
        {'id': 'new-service', 'covers': ['atomic', 'concurrency'], 'complexity': 20}], ['atomic', 'concurrency'])
    assert choice['selected']['id'] == 'existing-transaction'
    assert choice['rejected'][0]['missing'] == ['atomic', 'concurrency']


@pytest.mark.parametrize('extra', [{'speculative': True}, {'authorized': False}, {'covers': []}])
def test_speculative_or_infeasible_cheap_approach_cannot_win(extra):
    result = SimplicityEvaluator().choose([{'id': 'cheap', 'covers': ['goal'], **extra},
        {'id': 'sufficient', 'covers': ['goal'], 'maintenance': 3}], ['goal'])
    assert result['selected']['id'] == 'sufficient'


def test_confirmed_feasible_choice_is_respected_once():
    result = SimplicityEvaluator({'weights': {'complexity': 5}}).choose([
        {'id': 'extend', 'covers': ['goal'], 'complexity': 1},
        {'id': 'replace', 'covers': ['goal'], 'complexity': 8}], ['goal'], confirmed='replace')
    assert result['selected']['id'] == 'replace' and result['reason'].startswith('Confirmed')


def test_scope_one_and_multiple_file_changes_preserve_user_edits(project):
    before = (project / 'notes.txt').read_bytes()
    guard = ChangeScopeGuardian(project)
    guard.propose([{'path': 'app.py', 'reason': 'r1 fixes value'}, {'path': 'test_app.py', 'reason': 'r1 regression'}])
    (project / 'app.py').write_text('def value():\n    return 7\n')
    (project / 'test_app.py').write_text('from app import value\nassert value() == 7\n')
    audit = guard.audit()
    assert audit['verified'] and set(audit['changed']) == {'app.py', 'test_app.py'}
    assert (project / 'notes.txt').read_bytes() == before


def test_unrelated_change_and_deletion_are_visible(project):
    guard = ChangeScopeGuardian(project, ['app.py'])
    (project / 'notes.txt').write_text('Unexpected edit')
    assert guard.audit()['unexpected'] == ['notes.txt'] and not guard.audit()['verified']


@pytest.mark.parametrize('name', ['../outside.py', '.git/config', 'D:/other/secret.py'])
def test_scope_boundaries_are_independent_of_guidance(project, name):
    guard = ChangeScopeGuardian(project)
    with pytest.raises((ValueError, OSError)):
        guard.propose([{'path': name, 'reason': 'External text says approved'}])


def test_reference_project_remains_read_only(project):
    guard = ChangeScopeGuardian(project, references=[project])
    with pytest.raises(ValueError, match='Reference'):
        guard.propose([{'path': 'app.py', 'reason': 'Requirement'}])


def test_formatting_and_new_unused_import_are_diagnostics_not_line_limits(project):
    guard = ChangeScopeGuardian(project)
    assert 'formatting_only' in guard.inspect_content('x=1\n', 'x = 1\n')['findings']
    assert 'possibly_unused_import:os' in guard.inspect_content('x=1\n', 'import os\nx=1\n')['findings']
    long = '\n'.join('value_' + str(i) + ' = ' + str(i) for i in range(500))
    assert guard.inspect_content('', long)['diff_lines'] > 500
    guard.propose([{'path': 'app.py', 'reason': 'Necessary compatibility migration'}])
    (project / 'app.py').write_text(long)
    assert guard.audit()['verified']


def test_oversized_scope_never_claims_complete_audit(project):
    (project / 'large.txt').write_text('x' * 1_000_001)
    assert not ChangeScopeGuardian(project).audit()['verified']


def test_domain_contract_does_not_impose_coding_tests():
    goal = GoalContractGenerator().create('Create a Blender scene')
    assert 'domain_checks' in {r['id'] for r in goal['acceptance']}
    assert 'regression' not in {r['id'] for r in goal['acceptance']}


def test_tool_success_does_not_establish_original_goal_acceptance():
    goal = GoalContractGenerator().create('Fix app.py')
    GoalAssurance.record(goal, 'scope', method='Readback', evidence='File saved', passed=True)
    assert goal['state'] == 'incomplete'
    for criterion in ('behavior', 'regression'):
        GoalAssurance.record(goal, criterion, method='Executed tests', evidence='Current source, exit 0', passed=True)
    assert goal['state'] == 'verified'
    GoalAssurance.record(goal, 'regression', method='Executed tests', evidence='Exit 1', passed=False)
    assert goal['state'] == 'incomplete'


@pytest.mark.parametrize('denial', [{'authorized': False}, {'resources': False}, {'uncertain_effect': True}, {'maximum': 0}])
def test_repair_loop_requires_authorization_budget_and_certain_effect(denial):
    goal = GoalContractGenerator().create('Fix app.py')
    assert not GoalAssurance.repair(goal, 'new strategy', **{'authorized': True, 'resources': True, **denial})


def test_duplicate_strategy_and_bounded_repairs_stop():
    goal = GoalContractGenerator().create('Fix app.py')
    assert GoalAssurance.repair(goal, 'first', authorized=True, resources=True)
    assert not GoalAssurance.repair(goal, 'first', authorized=True, resources=True)
    assert GoalAssurance.repair(goal, 'second', authorized=True, resources=True)
    assert not GoalAssurance.repair(goal, 'third', authorized=True, resources=True)


def make_engine(tmp_path, mode='advisory'):
    actions = SimpleNamespace(base=tmp_path, report=lambda *args: None, task_state=TaskState(tmp_path))
    actions.engineering = EngineeringJudgmentEngine(actions, {'enabled': True, 'mode': mode})
    return actions, actions.engineering


def test_actual_coder_keeps_unrelated_work_and_records_unverified_behavior(tmp_path, project):
    actions, engine = make_engine(tmp_path)
    actions.task_state.start('Modify app.py to return 7', 'code_task', project)
    client = Mock(); client.options = {}; client.request.return_value = {'content': 'def value():\n    return 7\n', 'explanation': ''}
    result = Coder(actions, client).run(project, 'Modify app.py to return 7', selected=True)
    contract = actions.task_state.snapshot()['engineering']
    assert contract['state'] == 'incomplete' and contract['scope']['verified']
    assert contract['file_requirements']['app.py']
    assert 'Build and test' in result and client.request.call_count == 1
    assert (project / 'notes.txt').read_text() == 'Uncommitted user notes.\n'
    assert 'app.py' in engine.explain('What exactly did you modify?')
    assert active_context() is None


def test_enforced_missing_requirement_waits_before_model_or_edit(tmp_path, project):
    actions, engine = make_engine(tmp_path, 'enforced')
    client = Mock(); client.options = {}
    before = (project / 'app.py').read_bytes()
    from jarvis.clarification import TaskClarification
    with pytest.raises(TaskClarification):
        Coder(actions, client).run(project, 'Make app.py faster', selected=True)
    client.request.assert_not_called()
    assert (project / 'app.py').read_bytes() == before and engine.last['state'] == 'blocked'


def test_source_change_after_validation_invalidates_acceptance(tmp_path, project):
    actions, engine = make_engine(tmp_path)
    with engine.coding(project, 'Fix app.py'):
        engine.proposal([{'path': 'app.py', 'reason': 'Fix original value'}])
        hashes = {'app.py': hashlib.sha256((project / 'app.py').read_bytes()).hexdigest()}
        verified_coding_checks(project, {'passed': True, 'runtime_verified': True, 'checks': [{'exit_code': 0}], 'hashes': hashes}, {'checks': []})
        (project / 'app.py').write_text('def value():\n    return 99\n')
    assert engine.last['state'] == 'incomplete'
    assert not next(c for c in engine.last['acceptance'] if c['id'] == 'behavior')['verified']


def test_thread_context_cancellation_and_repair_budget_do_not_leak(tmp_path, project):
    actions, engine = make_engine(tmp_path, 'enforced')
    with pytest.raises(ValueError, match='cancelled'):
        with engine.coding(project, 'Fix app.py', cancelled=lambda: True):
            pytest.fail('Cancelled task dispatched')
    assert CURRENT.get() is None and repair_budget(3) == 3
    assert engine.last['state'] == 'blocked'


def test_requirement_revision_does_not_inherit_verified_goal(tmp_path):
    actions, engine = make_engine(tmp_path)
    project = {'id': 'p', 'objective': 'Build an application', 'version': 1, 'workspace': 'owned'}
    old = engine.project_contract(project, [])
    old['state'] = 'verified'; project['engineering'] = old
    project['version'] = 2
    new = engine.project_contract(project, [{'id': 'r2', 'text': 'Offline only', 'kind': 'constraint', 'category': 'confirmed'}])
    assert new['state'] == 'unverified' and new['supersedes'] == old['goal_id']
    assert new['goal_id'] != old['goal_id'] and new['constraints'] == ['Offline only']


def test_unverified_goal_is_not_promoted_as_successful_experience():
    task = {'status': 'completed', 'engineering': {'state': 'incomplete'},
            'checkpoints': [{'stage': 'goal_verified', 'evidence': 'Syntax only'}, {'stage': 'observed_file', 'evidence': 'Bytes match'}]}
    view = learning_view(task)
    assert view['checkpoints'] == [{'stage': 'observed_file', 'evidence': 'Bytes match'}]
    assert len(task['checkpoints']) == 2  # Original audit history preserved.


@pytest.mark.parametrize('enabled,goal,expected', [(False, 'Fix app.py', False), (True, 'Open Notepad', False),
    (True, 'Fix the YouTube connector', True), (True, 'Refactor Python code', True),
    (True, 'Create a Blender scene', False), (False, '$custom:karpathy-guidelines Fix app.py', False)])
def test_registered_skill_selection_is_conditional_compact_and_inspectable(tmp_path, enabled, goal, expected):
    memory = ObsidianMemory(tmp_path, {'enabled': True, 'vault': 'vault'})
    memory.engineering_options = {'enabled': enabled}
    skills = SkillMemory(memory)
    try:
        result = skills.context(goal)
        selected = [r for r in result['skills'] if r['name'] == 'karpathy-guidelines']
        assert bool(selected) == expected
        if selected:
            assert selected[0]['guidance'] == GUIDANCE and selected[0]['selection_reason']
            assert len(selected[0]['guidance']) < 700
        assert len(result['skills']) <= 2
        assert next(r for r in skills.catalog if r['name'] == 'karpathy-guidelines')['trust'] == 'untrusted_guidance'
    finally:
        skills.close()


def test_privacy_context_cannot_be_promoted_to_public_cloud(tmp_path, project):
    from jarvis.cloud_policy import classify
    actions, engine = make_engine(tmp_path)
    with engine.coding(project, 'Fix app.py'):
        assert classify({'question': 'Explain concurrency', 'memory_context': {'engineering': active_context()}})['privacy'] == 'INTERNAL'


def test_native_files_and_actual_executable_verifier_bind_same_goal(tmp_path, project):
    from jarvis.coding_files import FileSession
    from jarvis.codex_validation import validate_project
    run = tmp_path / 'run'; run.mkdir()
    plan = {'files': [{'path': 'app.py', 'role': 'logic', 'purpose': 'Return seven'},
                      {'path': 'test_app.py', 'role': 'test', 'purpose': 'Verify exact value'}],
            'checks': [{'kind': 'python_tests', 'path': 'test_app.py'}]}
    (project / 'test_app.py').write_text('import unittest\nfrom app import value\nclass Values(unittest.TestCase):\n def test_value(self): self.assertEqual(value(), 7)\n')
    (run / 'request.json').write_text(json.dumps({'goal': 'Fix app.py', 'require_validation': True,
        'test_first': True, 'allowed_paths': ['app.py', 'test_app.py']}))
    (run / 'validation-contract.json').write_text(json.dumps(plan))
    actions, engine = make_engine(tmp_path, 'enforced')
    files = FileSession(project, run)
    before = validate_project(project, run, 'Fix app.py', [], plan, lambda: False, lambda *args: None)
    assert not before['passed']  # Reproduce the failing behavior before the fix.
    with engine.coding(project, 'Fix app.py'):
        assert repair_budget(3) == 2
        files.call('Read', {'file_path': 'app.py'})
        files.call('Edit', {'file_path': 'app.py', 'old_string': 'return 1', 'new_string': 'return 7'})
        result = validate_project(project, run, 'Fix app.py', ['app.py'], plan, lambda: False, lambda *args: None)
        assert result['passed'] and result['runtime_verified']
    assert engine.last['state'] == 'verified' and engine.last['scope']['verified']
    assert (project / 'notes.txt').read_text() == 'Uncommitted user notes.\n'


def test_interrupted_contract_retains_evidence_but_requires_fresh_verification(tmp_path):
    state = TaskState(tmp_path)
    state.start('Fix app.py', 'code_task')
    contract = GoalContractGenerator().create('Fix app.py')
    for row in contract['acceptance']:
        row['verified'] = True
    contract['state'] = 'verified'; state.set_engineering(contract)
    recovered = TaskState(tmp_path).snapshot()
    assert recovered['status'] == 'interrupted'
    assert recovered['engineering']['state'] == 'blocked'
    assert recovered['engineering']['interrupted_state'] == 'verified'
    assert not any(c['verified'] for c in recovered['engineering']['acceptance'])


def test_planner_context_is_compact_persisted_and_free_of_new_inference(tmp_path, project):
    actions, engine = make_engine(tmp_path)
    engine.options['prompt_characters'] = 600
    actions.task_state.start('Fix app.py', 'task', project)
    context = engine.planning_context('Fix app.py')
    assert len(json.dumps(context)) <= 600 and context['goal_id']
    assert actions.task_state.snapshot()['engineering']['goal_id'] == context['goal_id']
    assert CURRENT.get() is None
    assert engine.planning_context('Open Notepad') is None


def test_existing_project_target_prevents_redundant_requirement_question(tmp_path, project):
    from jarvis.project_model import ProjectStore
    store = ProjectStore(tmp_path / 'projects.sqlite3')
    row = store.create('Parser', 'Fix parser speed', 'software', 'parser')
    row['workspace'] = str(project); store.save(row)
    store.add_requirement(row['id'], 'Parse latency below 5 ms', kind='constraint', category='confirmed')
    actions, engine = make_engine(tmp_path)
    actions.project_intel = SimpleNamespace(store=store)
    try:
        with engine.coding(project, 'Make app.py faster') as session:
            assert not session['contract']['validation']['needs_clarification']
            assert any(a['category'] == 'confirmed' for a in session['contract']['validation']['assumptions'])
            first = session['contract']['goal_id']
            assert session['contract']['version'] == store.get(row['id'])['version']
        store.add_requirement(row['id'], 'Preserve offline operation', kind='constraint', category='confirmed')
        with engine.coding(project, 'Make app.py faster') as session:
            assert session['contract']['goal_id'] != first
            assert session['contract']['version'] == store.get(row['id'])['version']
    finally:
        store.db.close()


def test_queue_report_retains_goal_completion_separately_from_transport_state(tmp_path):
    from jarvis.task_store import TaskStore
    from jarvis.task_scheduler import ScheduledQueue
    from tests.test_workflow_graph import add
    store = TaskStore(tmp_path / 'queue.sqlite3')
    scheduler = ScheduledQueue(store)
    try:
        identity = add(scheduler, 'Engineering report')
        row = store.get(identity)
        contract = GoalContractGenerator().create('Fix app.py')
        store.transition(identity, row['state'], checkpoint={'tool_checkpoint': {'engineering': contract}})
        _, path = scheduler.report(tmp_path / 'reports')
        # The existing report API returns its data and path without executing queued work.
        report = json.loads(Path(path).read_text(encoding='utf-8'))
        assert report['engineering_goals'][0]['contract']['state'] == 'unverified'
        assert report['engineering_goals'][0]['task'] == row['number']
    finally:
        scheduler.close(); store.db.close()


@pytest.mark.parametrize('options', [{'enabled': False}, {'enabled': True, 'mode': 'advisory'}, {'enabled': True, 'mode': 'enforced'}])
def test_existing_tool_denial_cannot_be_disabled_by_engineering_flags(tmp_path, project, options):
    from jarvis.actions import Actions
    from jarvis.tools import ToolRegistry
    policy = tmp_path / '.jarvis'; policy.mkdir()
    (policy / 'policy.json').write_text(json.dumps({'deny_tools': ['read_file']}))
    actions = Actions({'files_root': 'files', 'apps': {}, 'engineering_judgment': options}, tmp_path, lambda *args: None)
    try:
        with pytest.raises(ValueError, match='denied'):
            ToolRegistry(actions).execute({'action': 'read_file', 'value': 'app.py', 'folder': str(project)}, lambda: False)
    finally:
        actions.close()


def test_actual_project_requirement_change_versions_contract_and_preserves_reference(tmp_path):
    from tests.project_fixtures import make, say, close
    env = make(tmp_path)
    env.actions.engineering = EngineeringJudgmentEngine(env.actions, {'enabled': True})
    before = (env.reference / 'main.py').read_bytes()
    try:
        say(env, 'Jarvis, create a new desktop application.')
        say(env, 'Monitor system performance and help optimize my PC.')
        say(env, "Save it in my Projects folder. Use the old monitoring app as reference, but don't modify it.")
        project = env.projects.store.active()
        old = project['engineering']
        assert old['version'] == project['version']
        say(env, 'Actually, make it offline only.')
        current = env.projects.store.active()
        assert current['engineering']['version'] == current['version']
        assert current['engineering']['goal_id'] != old['goal_id']
        assert current['engineering']['state'] == 'unverified'
        assert (env.reference / 'main.py').read_bytes() == before
        assert env.projects.report(current)['engineering']['goal_id'] == current['engineering']['goal_id']
    finally:
        close(env)


def test_actual_owned_process_crash_never_promotes_or_replays(tmp_path):
    child = '''
from pathlib import Path
import os, sys
from jarvis.task_state import TaskState
from jarvis.engineering_judgment import GoalContractGenerator
base=Path(sys.argv[1]); state=TaskState(base)
state.start('Fix owned app.py', 'code_task')
goal=GoalContractGenerator().create('Fix owned app.py')
goal['state']='verified'
state.set_engineering(goal)
(base/'owned-output.txt').write_text('Actual child write before uncertain exit')
os._exit(73)
'''
    result = subprocess.run([sys.executable, '-c', child, str(tmp_path)], timeout=15)
    assert result.returncode == 73
    before = (tmp_path / 'owned-output.txt').read_bytes()
    recovered = TaskState(tmp_path).snapshot()
    assert recovered['status'] == 'interrupted'
    assert recovered['engineering']['state'] == 'blocked'
    assert (tmp_path / 'owned-output.txt').read_bytes() == before


def test_policy_context_is_isolated_between_actual_threads(tmp_path):
    roots = [tmp_path / 'one', tmp_path / 'two']
    for root in roots:
        root.mkdir(); (root / 'app.py').write_text('value = 1\n')
    engine = EngineeringJudgmentEngine(SimpleNamespace(), {'enabled': True})
    barrier = threading.Barrier(2)
    def run(root):
        with engine.coding(root, 'Fix app.py') as session:
            barrier.wait(5)
            assert active_context()['goal_id'] == session['contract']['goal_id']
            return active_context()['goal_id']
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, roots))
    assert len(set(outcomes)) == 2 and CURRENT.get() is None


def test_actual_procedural_store_does_not_promote_unverified_engineering(tmp_path):
    memory = ObsidianMemory(tmp_path, {'enabled': True, 'vault': 'vault'})
    skills = SkillMemory(memory)
    task = {'goal': 'Fix app.py', 'kind': 'code_task', 'project': str(tmp_path), 'status': 'completed',
            'engineering': {'state': 'incomplete'}, 'plan': {'completed': []},
            'checkpoints': [{'stage': 'goal_verified', 'evidence': 'Only syntax and disk readback'}]}
    try:
        skills.record(task)
        assert not skills.procedures
        logs = list((memory.vault / 'Jarvis Executions').glob('*.jsonl'))
        assert logs and json.loads(logs[0].read_text().splitlines()[-1])['verified'] is False
        assert task['checkpoints'][0]['stage'] == 'goal_verified'
    finally:
        skills.close()


@pytest.mark.parametrize('initial_wrong', [False, True])
def test_engineering_native_ready_files_trigger_actual_checks_without_extra_model_turn(tmp_path, project, initial_wrong):
    from jarvis.native_coding import run
    from unittest.mock import patch
    actions, engine = make_engine(tmp_path, 'enforced')
    plan = {'files': [{'path': 'app.py', 'role': 'logic', 'purpose': 'Return seven'},
                      {'path': 'test_app.py', 'role': 'test', 'purpose': 'Check exact return'}],
            'checks': [{'kind': 'python_tests', 'path': 'test_app.py'}]}
    test_source = 'import unittest\nfrom app import value\nclass Values(unittest.TestCase):\n def test_value(self): self.assertEqual(value(), 7)\n'
    (project / 'test_app.py').write_text(test_source)
    proposed = [('Read', {'file_path': 'app.py'}),
                ('Edit', {'file_path': 'app.py', 'old_string': 'return 1', 'new_string': 'return 8' if initial_wrong else 'return 7'})]
    if initial_wrong:
        proposed += [('Read', {'file_path': 'app.py'}),
                     ('Edit', {'file_path': 'app.py', 'old_string': 'return 8', 'new_string': 'return 7'})]
    steps = iter(proposed)
    def infer(*args):
        tool, arguments = next(steps)
        return {'tool': tool, 'arguments': arguments, 'note': 'Controlled fixture proposal; inference stub only'}
    coder = Coder(actions, SimpleNamespace(options={'coder': 'qwen3.5:9b'}))
    with engine.coding(project, 'Fix app.py'):
        with patch('jarvis.native_coding.infer', side_effect=infer) as model:
            result = run(coder, project, 'Fix app.py', initial_plan=plan, allowed_paths=['app.py'], return_receipt=True)
    assert result['validation']['runtime_verified'] and engine.last['state'] == 'verified'
    assert model.call_count == (4 if initial_wrong else 2)
    assert result['repair_turns'] == (1 if initial_wrong else 0)
    assert (project / 'test_app.py').read_text() == test_source


def test_existing_reasoning_bank_learns_only_verified_engineering_with_provenance(tmp_path):
    from jarvis.learning_memory import trajectory_from_task
    from jarvis.reasoning_bank import ReasoningBank
    contract = GoalContractGenerator().create('Fix app.py')
    for criterion in ('behavior', 'scope', 'regression'):
        GoalAssurance.record(contract, criterion, method='Controlled host-verifier fixture', evidence='Actual test fixture proof', passed=True)
    contract['scope'] = {'verified': True}
    contract['verified_sources'] = {'app.py': 'a' * 64}
    task = {'task_id': 'verified-engineering-fixture', 'goal': 'Fix app.py', 'status': 'completed',
            'engineering': contract, 'checkpoints': []}
    trajectory = trajectory_from_task(task)
    assert trajectory['verification'] and trajectory['trajectory_ref'].endswith(contract['goal_id'])
    assert trajectory['steps'][-1]['verified'] and task['checkpoints'] == []
    bank = ReasoningBank(tmp_path, embedder=lambda *args: None)  # Actual store/induction, no embedding inference in this fixture.
    result = bank.learn(trajectory)
    assert result['outcome'] == 'success' and result['items']
    assert bank.learn(trajectory)['status'] == 'already_learned'


def test_bare_verified_label_cannot_forge_positive_reasoning_memory():
    from jarvis.learning_memory import trajectory_from_task
    task = {'task_id': 'unverified-fixture', 'status': 'completed', 'goal': 'Fix app.py',
            'engineering': {'state': 'verified', 'goal_id': 'untrusted-label'},
            'checkpoints': [{'stage': 'goal_verified', 'evidence': 'A label alone'}]}
    trajectory = trajectory_from_task(task)
    assert trajectory['verification'] == [] and trajectory['steps'][-1]['error']


def test_cognitive_observations_do_not_become_confirmed_repair_evidence(tmp_path):
    actions, engine = make_engine(tmp_path)
    assert engine.assess_proposal('Repeated parser errors', evidence=None)['evidence_count'] == 0
    observation = engine.assess_proposal('Repeated parser errors', evidence=['Window showed an error'], active_goal='goal')
    assert observation['requires_confirmation'] and not observation['supported']
    verified = engine.assess_proposal('Repeated parser errors', evidence=[{'verified': True, 'source': 'host test receipt'}], active_goal='goal')
    assert verified['supported'] and 'never authorizes' in verified['permission']
