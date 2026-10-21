"""Controller invariants and production execution with owned filesystem tools."""
import copy
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from jarvis.adaptive_planning import AdaptivePlanningController, STATES, literal_requirement
from jarvis.brain import Brain
from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.task_state import TaskState
from jarvis.repo_abilities import AbilityForge
from scripts.verification.verify_adaptive_planning import measure
from scripts.verification.verify_plan_execution import FixtureClient, fixture, scenario


def step(value='notes.txt', **extra):
    return {'action': 'read_file', 'value': value, 'folder': 'this folder',
            'expected': 'Requested content read', **extra}


def test_progress_and_acceptance_are_durable_task_owned_and_never_replayed(tmp_path):
    state = TaskState(tmp_path)
    task = state.start('1. Read notes.txt\n2. Verify its content', 'task')
    controller = AdaptivePlanningController(state.snapshot()['goal'],
        lambda payload: state.update_adaptive(payload, task_id=task))
    controller.progress([step()], [])
    controller.transition('EXECUTE', 'Dispatch only through existing tool policy')
    restarted = TaskState(tmp_path)
    assert restarted.snapshot()['status'] == 'interrupted'
    assert restarted.snapshot()['adaptive']['state'] == 'BLOCKED'
    assert restarted.snapshot()['adaptive']['interrupted_state'] == 'EXECUTE'
    assert len(restarted.snapshot()['adaptive']['acceptance']) == 3
    state.start('Another task', 'task')
    with pytest.raises(ValueError, match='identity changed'):
        controller.transition('OBSERVE', 'Late old worker')
    assert 'adaptive' not in state.snapshot()


def test_repeated_prompt_needs_new_evidence_but_productive_reasoning_has_no_cutoff():
    controller = AdaptivePlanningController('Investigate unfamiliar application')
    for index in range(500):
        assert controller.admit('replan', {'screen': {'new_dependency': index}})
    assert not controller.admit('replan', {'screen': {'new_dependency': 499}})
    assert controller.ledger['planning_cycles'] == 500
    assert controller.ledger['repeated_decisions'] == 1
    assert len(controller.ledger['decisions']) <= 40
    assert controller.admit('replan', {'screen': {'new_dependency': 500}})


def test_semantic_plan_oscillation_ignores_wording_and_unused_fields():
    controller = AdaptivePlanningController('Investigate alternatives')
    for target in ('first', 'second', 'first'):
        controller.proposal({'reason': target, 'steps': [step(target, unused='changed')]}, .1)
    assert controller.ledger['plan_oscillations'] == 1
    assert controller.ledger['model_seconds'] == pytest.approx(.3)


def test_cosmetic_plan_edits_are_not_new_evidence():
    controller = AdaptivePlanningController('Read notes')
    assert controller.admit('plan', {'remaining': [step(expected='Read it')]})
    assert not controller.admit('replan', {'remaining': [step(expected='Read it carefully', browser='edge')]})


@pytest.mark.parametrize('pending', [step(verified=True), step(action='select'),
    step(action='mcp_call'), step(action='modify_file', find=''), step(folder=''), step(expected='')])
def test_ready_rule_refuses_repeated_unknown_or_unresolved_actions(pending):
    controller = AdaptivePlanningController('Read file')
    assert not controller.ready([pending], [step(verified=True)], [])


def test_verified_subtask_can_start_without_perfect_global_plan():
    controller = AdaptivePlanningController('Read files')
    complete = step('first.txt', verified=True)
    assert controller.ready([step('second.txt')], [complete], [])
    assert not controller.ready([step('second.txt')], [complete], [step('second.txt')])
    assert not controller.ready([step('second.txt')], [{**complete, 'confirmed': False}], [])


def test_partial_work_and_tool_success_never_satisfy_completion(tmp_path):
    state = TaskState(tmp_path)
    task = state.start('Read and validate two files', 'task')
    controller = AdaptivePlanningController(state.snapshot()['goal'],
        lambda value: state.update_adaptive(value, task_id=task))
    controller.progress([step('second.txt')], [step(verified=True)])
    assert not controller.verify_goal('Tool claimed success')
    state.finish('completed', 'Finished', task_id=task)
    assert state.snapshot()['status'] == 'paused'
    assert not any(row['verified'] for row in state.snapshot()['adaptive']['acceptance'])


def test_final_evidence_required_then_complete_with_no_remaining_steps(tmp_path):
    state = TaskState(tmp_path)
    task = state.start('Read notes', 'task')
    controller = AdaptivePlanningController('Read notes',
        lambda value: state.update_adaptive(value, task_id=task))
    controller.progress([], [step(verified=True)])
    with pytest.raises(ValueError, match='evidence'):
        controller.verify_goal('')
    assert controller.verify_goal('Fresh independent content readback')
    state.finish('completed', 'Finished', task_id=task)
    assert state.snapshot()['status'] == 'completed'


def test_omitted_literal_acceptance_cannot_be_overruled_by_model_done():
    controller = AdaptivePlanningController('1. Read first.txt\n2. Read second.txt')
    controller.progress([], [step('first.txt', verified=True)])
    assert not controller.verify_goal('Model says done')
    assert 'criterion' in controller.ledger['blockers'][0]
    controller.progress([], [step('first.txt', verified=True), step('second.txt', verified=True)])
    assert controller.verify_goal('Fresh full-goal readback')


def test_literal_acceptance_defers_ambiguous_names_and_accepts_sentence_punctuation():
    assert literal_requirement('Read report.txt.') == {'action': 'read_file', 'value': 'report.txt'}
    assert literal_requirement('Read chapter-one') is None
    assert literal_requirement('Read example.org') is None
    assert literal_requirement('Read "quarterly report.txt"') is None


def test_uncertain_write_overrules_controller_completion(tmp_path):
    state = TaskState(tmp_path)
    task = state.start('Read notes', 'task')
    controller = AdaptivePlanningController('Read notes',
        lambda value: state.update_adaptive(value, task_id=task))
    state.checkpoint('uncertain_external_write', action='mock_write', target='fixture')
    assert controller.verify_goal('Verifier missed an uncertain write')
    state.finish('completed', 'Finished', task_id=task)
    assert state.snapshot()['status'] == 'paused'
    assert state.snapshot()['adaptive']['state'] == 'BLOCKED'


def test_planner_done_cannot_override_failed_independent_verification(tmp_path):
    original = FixtureClient.request
    def request(self, operation, cancelled, **data):
        if operation == 'verify' and data['step']['action'] == 'goal':
            return {'verified': False, 'reason': 'Missing requested quality requirement'}
        return original(self, operation, cancelled, **data)
    with patch.object(FixtureClient, 'request', request):
        result = fixture(tmp_path, scenario(0, 2), incremental=True)
    assert result['state_status'] == 'paused'
    assert result['dispatched_actions'] == 2
    assert not result['passed']


def test_model_success_cannot_hide_an_omitted_literal_operation_in_real_executor(tmp_path):
    original = FixtureClient.request
    def request(self, operation, cancelled, **data):
        if operation == 'plan':
            return {'steps': self.case['steps'][:1], 'question': ''}
        if operation == 'verify':
            return {'verified': True, 'reason': 'Overconfident simulated verifier'}
        return original(self, operation, cancelled, **data)
    with patch.object(FixtureClient, 'request', request):
        result = fixture(tmp_path, scenario(0, 2))
    assert result['state_status'] == 'paused'
    assert result['dispatched_actions'] == result['completed_actions'] == 1
    assert 'criterion' in result['error']


@pytest.mark.parametrize('incremental', [False, True])
def test_uncertain_real_write_preserves_checkpoint_and_never_replays(tmp_path, incremental):
    result = fixture(tmp_path, scenario(0, 5), incremental=incremental, fault_after=2)
    assert result['dispatched_actions'] == 2
    assert result['completed_actions'] == 1
    assert result['state_status'] != 'completed'
    assert result['resume_blocker']
    assert (tmp_path/'notes'/'notes1.txt').read_text() == 'reviewed'


def test_ui_snapshot_exposes_only_bounded_progress_metadata(tmp_path):
    state = TaskState(tmp_path)
    task = state.start('Private objective', 'task')
    controller = AdaptivePlanningController('Private objective',
        lambda value: state.update_adaptive(value, task_id=task))
    controller.progress([step('private-file.txt')], [])
    snapshot = state.ui_snapshot()
    assert snapshot['adaptive']['remaining'] == 1
    assert 'Private' not in str(snapshot) and 'private-file' not in str(snapshot)


def test_queued_partial_result_is_not_displayed_as_done(tmp_path):
    actions = Actions({'files_root': 'files', 'apps': {}, '_ui_verification': True,
                       'memory': {'enabled': False}}, tmp_path, lambda *_: None)
    actions.brain.run = lambda *_: 'Task paused: essential dependency unavailable'
    try:
        actions.start()
        actions.submit(Command('task', 'Read the two requested files'))
        actions.queue.join()
        assert actions.task_state.snapshot()['status'] == 'paused'
        assert actions.task_history[-1]['status'] == 'paused'
    finally:
        actions.close()


def test_real_file_chains_keep_quality_and_remove_redundant_replans():
    result = measure()
    assert result['verified_successes'] == 4, result
    assert result['quality_exact_order']
    assert result['planner_calls'] == 7  # Four initial + three completion proposals; action-limit case goes to final verifier.


def test_same_worker_rejects_concurrent_task_before_mutating_session(tmp_path):
    brain = Brain(Mock(), tmp_path, {})
    entered, release = threading.Event(), threading.Event()
    def run(*args):
        entered.set()
        assert release.wait(5)
        return 'Task paused'
    brain._run_owned = run
    thread = threading.Thread(target=lambda: brain.run('First', lambda: False))
    thread.start()
    assert entered.wait(5)
    try:
        with pytest.raises(ValueError, match='already owns'):
            brain.run('Second', lambda: False)
    finally:
        release.set()
        thread.join(5)
    assert not brain._run_lock.locked()


def test_repeated_model_context_observes_without_calling_model_again(tmp_path):
    brain = Brain(Mock(), tmp_path, {})
    brain.client = Mock()
    brain.client.request.return_value = {'steps': [step()]}
    brain.adaptive_controller = AdaptivePlanningController('Read notes')
    screen = {'title': 'Same', 'is_dialog': False, 'fields': [], 'controls': []}
    brain.observe = Mock(return_value=(None, screen))
    brain.propose_plan('plan', lambda: False, goal='Read notes', screen=screen)
    with pytest.raises(ValueError, match='unchanged'):
        brain.propose_plan('replan', lambda: False, goal='Read notes', screen=copy.deepcopy(screen))
    assert brain.client.request.call_count == 1
    brain.observe.assert_called_once()
    assert brain.adaptive_controller.ledger['state'] == 'BLOCKED'
    assert brain.adaptive_controller.ledger['state'] in STATES


@pytest.mark.parametrize('directory', [False, True])
def test_known_failed_owned_metadata_rename_retries_without_replaying_effect(tmp_path, directory):
    forge = AbilityForge.__new__(AbilityForge)
    forge.root, forge.stop = tmp_path, threading.Event()
    source, target = tmp_path/'pending', tmp_path/'checkpoint'
    source.mkdir() if directory else source.write_text('metadata')
    actual = Path.replace
    calls = []
    def replace(path, destination):
        calls.append(str(path))
        if len(calls) == 1:
            error = PermissionError('Injected Windows reader lock')
            error.winerror = 5
            raise error
        return actual(path, destination)
    with patch.object(Path, 'replace', replace):
        forge._replace_checkpoint(source, target)
    assert len(calls) == 2 and target.exists() and not source.exists()


@pytest.mark.parametrize('fault', ['target_changed', 'uncertain_move', 'shutdown', 'directory_child_changed'])
def test_owned_metadata_commit_refuses_uncertainty_or_shutdown(tmp_path, fault):
    forge = AbilityForge.__new__(AbilityForge)
    forge.root, forge.stop = tmp_path, threading.Event()
    source, target = tmp_path/'pending', tmp_path/'checkpoint'
    if fault == 'directory_child_changed':
        source.mkdir()
        (source/'ability.py').write_text('old')
    else:
        source.write_text('metadata')
    actual = Path.replace
    calls = []
    def replace(path, destination):
        calls.append(str(path))
        if fault == 'target_changed':
            target.write_text('Another writer')
        elif fault == 'uncertain_move':
            actual(path, destination)
        elif fault == 'directory_child_changed':
            (source/'ability.py').write_text('new')
        else:
            forge.stop.set()
        error = PermissionError('Injected uncertain commit')
        error.winerror = 5
        raise error
    with patch.object(Path, 'replace', replace), pytest.raises((PermissionError, InterruptedError)):
        forge._replace_checkpoint(source, target)
    assert len(calls) == 1


def test_gmail_ack_checkpoint_retry_never_resends_fake_message(tmp_path):
    from jarvis.gmail_api import execute
    from tests.test_gmail_audit import box
    api = box()
    actions = SimpleNamespace(base=tmp_path, _approve=Mock())
    actual = Path.replace
    injected = []
    def replace(path, target):
        if path.suffix == '.tmp' and not injected and json.loads(path.read_text()).get('message_id'):
            injected.append(True)
            error = PermissionError('Injected acknowledgement checkpoint lock')
            error.winerror = 32
            raise error
        return actual(path, target)
    with patch('jarvis.gmail_api.configured', return_value=True), patch('jarvis.gmail_api.API', return_value=api), patch.object(Path, 'replace', replace):
        result = json.loads(execute(actions, {'action': 'gmail_api_send', 'value': 'new',
            'content': json.dumps({'to': 'a@example.test', 'subject': 'Owned fixture', 'body': 'owned'})}, lambda: False))
    assert injected and result['sent']
    assert api.writes() == [('POST', 'messages/send')]


def test_checkpoint_cannot_rename_outside_its_owned_root(tmp_path):
    from jarvis.checkpoint_io import replace_checkpoint
    owned = tmp_path/'owned'
    owned.mkdir()
    source = owned/'pending'
    source.write_text('metadata')
    with pytest.raises(ValueError, match='escaped'):
        replace_checkpoint(source, tmp_path/'outside', owned)
    assert source.read_text() == 'metadata' and not (tmp_path/'outside').exists()


def test_checkpoint_repair_is_silent_and_journaled_without_contents(tmp_path):
    from jarvis.checkpoint_io import replace_checkpoint
    owned = tmp_path/'.jarvis-runtime'/'owned'
    owned.mkdir(parents=True)
    source, target = owned/'pending', owned/'checkpoint'
    source.write_text('PRIVATE_CONTENT_SENTINEL')
    actual, calls, events = Path.replace, [], []
    def replace(path, destination):
        calls.append(True)
        if len(calls) == 1:
            error = PermissionError('Injected reader lock')
            error.winerror = 5
            raise error
        return actual(path, destination)
    with patch.object(Path, 'replace', replace):
        replace_checkpoint(source, target, owned, wait=lambda _: None,
                           report=lambda *event: events.append(event))
    log = (tmp_path/'.jarvis-runtime'/'repairs.jsonl').read_text()
    assert len(log.splitlines()) == 2 and 'PRIVATE_CONTENT_SENTINEL' not in log
    assert len(events) == 2 and all(event[0] == 'repair' for event in events)


def test_checkpoint_revalidates_source_after_backoff(tmp_path):
    from jarvis.checkpoint_io import replace_checkpoint
    source, target = tmp_path/'pending', tmp_path/'checkpoint'
    source.write_text('old')
    error = PermissionError('Injected reader lock')
    error.winerror = 5
    with patch.object(Path, 'replace', side_effect=error) as commit, pytest.raises(ValueError, match='backoff'):
        replace_checkpoint(source, target, tmp_path, wait=lambda _: source.write_text('new') and None)
    commit.assert_called_once()
    assert source.read_text() == 'new' and not target.exists()
