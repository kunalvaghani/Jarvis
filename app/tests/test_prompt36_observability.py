"""Observable, synthetic telemetry contracts; no real cloud, UI or model workload."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jarvis.skill_store import SkillStore
from jarvis.skill_evolution import finish_outcomes
from jarvis.tools import ToolRegistry, ToolResult
from jarvis.task_state import TaskState
from tests.test_phase05_escalation_demonstration import GENERIC, FAILURES, architect

CANARY = 'syntheticPrivateFixture9471'


def store_fixture(tmp_path):
    store = SkillStore(tmp_path)
    row = {'origin': 'Custom', 'provenance': {'relative_path': 'fixture', 'sha256': 'a'*64},
           'name': 'fixture', 'description': 'Synthetic fixture guidance', 'body': 'Synthetic fixture.'}
    ident = store.register(row)
    return store, ident


def test_JRV_36_024_skill_telemetry_stores_metadata_not_raw_evidence(tmp_path):
    store, skill = store_fixture(tmp_path)
    store.event(skill, 'completed_verified', 'task', {'evidence': [CANARY], 'raw': CANARY, 'token': CANARY})
    store.failure(skill, 'task', 'other', 'token: ' + CANARY)
    with store.connect() as db:
        events = str([dict(r) for r in db.execute('SELECT evidence_json FROM skill_events')])
        failures = str([dict(r) for r in db.execute('SELECT detail FROM skill_failures')])
    assert CANARY not in events + failures
    assert store.metrics(skill)['last_verified_evidence'] == {'evidence_count': 1}


def test_JRV_36_024_large_skill_evidence_remains_valid_json(tmp_path):
    store, skill = store_fixture(tmp_path)
    store.event(skill, 'failed', 'task', {'cause': 'other', 'raw': 'x' * 8000})
    assert store.metrics(skill)['failed_count'] == 1


def test_JRV_36_023_legacy_malformed_evidence_does_not_break_metrics(tmp_path):
    store, skill = store_fixture(tmp_path)
    store.event(skill, 'failed', 'task', {'cause': 'other'})
    with store.connect() as db:
        db.execute("UPDATE skill_events SET evidence_json='not json'")
    assert store.metrics(skill)['failure_causes'] == {'other': 1}
    assert store.metrics(skill)['invalid_evidence_count'] == 1


def test_JRV_36_014_refuted_bound_step_cannot_earn_verified_skill_credit(tmp_path):
    store, skill = store_fixture(tmp_path)
    store.event(skill, 'selected', 'task')
    catalog = [{'skill_id': skill, 'tools': ['office_xlsx']}]
    task = {'task_id': 'task', 'status': 'completed', 'failures': [],
            'plan': {'completed': [{'action': 'office_xlsx', 'verified': False}]},
            'checkpoints': [{'stage': 'goal_verified', 'evidence': 'tool claimed success'}]}
    finish_outcomes(store, catalog, task)
    assert store.metrics(skill)['completed_verified_count'] == 0
    assert store.metrics(skill)['failed_count'] == 1


def test_JRV_36_013_015_selection_only_and_restart_are_not_execution(tmp_path):
    store, skill = store_fixture(tmp_path)
    store.event(skill, 'selected', 'task')
    reopened = SkillStore(tmp_path)
    assert reopened.event(skill, 'selected', 'task') is False
    finish_outcomes(reopened, [{'skill_id': skill, 'tools': ['office_xlsx']}], {'task_id': 'task', 'status': 'completed'})
    metrics = reopened.metrics(skill)
    assert metrics['selected_count'] == 1 and metrics['applied_count'] == metrics['completed_verified_count'] == 0
    assert metrics['fallback_count'] == 0


def test_JRV_36_003_008_five_calls_correlate_to_task_and_monotonic_clock(tmp_path):
    state = TaskState(tmp_path)
    task = state.start('Synthetic read-only five-call fixture', 'task')
    actions = SimpleNamespace(base=tmp_path, task_state=state, allowed_tools={'read_file'})
    registry = ToolRegistry(actions)
    registry._execute = Mock(return_value=ToolResult('read_file', 'files', 'fixture read'))
    for _ in range(5):
        registry.execute({'action': 'read_file', 'value': 'fixture', 'folder': str(tmp_path)}, lambda: False)
    rows = [json.loads(s) for s in (tmp_path / '.jarvis-runtime/agent-events.jsonl').read_text().splitlines()]
    assert len({r['call_id'] for r in rows if r['event'] == 'tool.started'}) == 5
    assert {r['task_id'] for r in rows} == {task}
    assert len({r['clock_id'] for r in rows}) == 1
    assert all(type(r['monotonic_ns']) is int for r in rows)
    assert [r['monotonic_ns'] for r in rows] == sorted(r['monotonic_ns'] for r in rows)


def test_JRV_36_011_logging_unavailable_does_not_replay_or_block_tool(tmp_path, monkeypatch):
    actions = SimpleNamespace(base=tmp_path, allowed_tools={'read_file'})
    registry = ToolRegistry(actions)
    registry._execute = Mock(return_value=ToolResult('read_file', 'files', 'fixture read'))
    real_open = Path.open
    def no_journal(path, *args, **kwargs):
        if path.name == 'agent-events.jsonl':
            raise PermissionError('synthetic locked log')
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', no_journal)
    assert registry.execute({'action': 'read_file', 'value': 'fixture', 'folder': str(tmp_path)}, lambda: False).evidence == 'fixture read'
    registry._execute.assert_called_once()
    assert actions.telemetry_status == 'unavailable'


def test_JRV_36_020_privacy_block_records_categorical_reason_without_payload(tmp_path):
    agent, adapter = architect(tmp_path)
    agent.consult(CANARY, {**GENERIC, 'statement': 'Private screenshot: token=' + CANARY}, FAILURES, 3, 'r1')
    assert adapter.sent == []
    rows = [json.loads(s) for s in agent.log.read_text().splitlines()]
    assert rows[-1]['decision'] == 'privacy_blocked'
    assert CANARY not in json.dumps(rows) and 'screenshot' not in json.dumps(rows)


def test_JRV_36_024_cloud_logs_never_copy_sent_problem_payload(tmp_path):
    agent, adapter = architect(tmp_path)
    agent.consult('fixture', GENERIC, FAILURES, 3, 'r1')
    assert len(adapter.sent) == 1  # local recording fake only
    rows = [json.loads(s) for s in agent.log.read_text().splitlines()]
    assert all('sent' not in r for r in rows)
    assert GENERIC['statement'] not in json.dumps(rows)
    assert rows[0]['decision'] == 'sent' and rows[0]['payload_bytes'] > 0


def test_JRV_36_011_journal_cap_preserves_evidence_without_replay(tmp_path, monkeypatch):
    from jarvis import agent_events
    path = tmp_path / '.jarvis-runtime/agent-events.jsonl'
    path.parent.mkdir(); path.write_text('preserved evidence\n')
    monkeypatch.setattr(agent_events, 'MAX_JOURNAL_BYTES', 1)
    actions = SimpleNamespace(base=tmp_path, allowed_tools={'read_file'})
    registry = ToolRegistry(actions)
    registry._execute = Mock(return_value=ToolResult('read_file', 'files', 'fixture'))
    registry.execute({'action': 'read_file', 'value': 'fixture', 'folder': str(tmp_path)}, lambda: False)
    registry._execute.assert_called_once()
    assert actions.telemetry_status == 'limited' and path.read_text() == 'preserved evidence\n'


def test_JRV_36_011_unavailable_telemetry_cannot_override_deny_policy(tmp_path):
    policy = tmp_path / '.jarvis/policy.json'
    policy.parent.mkdir(); policy.write_text(json.dumps({'deny_tools': ['read_file']}))
    actions = SimpleNamespace(base=tmp_path, telemetry_status='unavailable', allowed_tools={'read_file'})
    registry = ToolRegistry(actions); registry._execute = Mock()
    with pytest.raises(ValueError, match='denied'):
        registry.execute({'action': 'read_file', 'value': 'fixture', 'folder': str(tmp_path)}, lambda: False)
    registry._execute.assert_not_called()


def test_JRV_36_011_cloud_logging_failure_does_not_repeat_consultation(tmp_path, monkeypatch):
    agent, adapter = architect(tmp_path)
    real_open = Path.open
    def no_cloud_log(path, *args, **kwargs):
        if path.name == 'architect-log.jsonl': raise PermissionError('synthetic locked log')
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', no_cloud_log)
    assert agent.consult('fixture', GENERIC, FAILURES, 3, 'r1')['status'] == 'advice_only'
    assert agent.consult('fixture', GENERIC, FAILURES, 3, 'r1')['status'] == 'local'
    assert len(adapter.sent) == 1 and agent.telemetry_status == 'unavailable'
