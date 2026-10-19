"""Phase 1 repairs and shared execution-outcome contracts.

Real ToolRegistry, Cognition, launcher loop and event log on temporary
directories. No model, network, desktop or account action runs.
"""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from jarvis import execution_contracts as contracts
from jarvis.agent_events import event
from jarvis.cognition import Cognition
from jarvis.tools import ToolArgumentError, ToolRegistry

BASE = Path(__file__).resolve().parents[1]


def registry(tmp_path):
    actions = SimpleNamespace(base=tmp_path, config={}, allowed_tools=None, report=Mock(), execute=Mock())
    return actions, ToolRegistry(actions)


@pytest.mark.parametrize('step', [None, 42, 'task_id', ['task_id'], ('action', 'open')])
def test_P01_D1_non_object_proposal_is_a_typed_contract_error(tmp_path, step):
    actions, tools = registry(tmp_path)
    with pytest.raises(ToolArgumentError, match='must be an object'):
        tools.execute(step, lambda: False)
    actions.execute.assert_not_called()
    # Rejected before any lifecycle row: nothing was started.
    assert not (tmp_path / '.jarvis-runtime/agent-events.jsonl').exists()


def test_P01_D1_object_with_task_id_still_requires_identity(tmp_path):
    actions, tools = registry(tmp_path)
    with pytest.raises(ValueError, match='Task identity is unavailable'):
        tools.execute({'task_id': 'x', 'action': 'open', 'value': 'notepad'}, lambda: False)
    actions.execute.assert_not_called()


def test_P01_D2_launcher_closes_docker_handle_when_loop_exits(tmp_path):
    from jarvis import launcher
    handle = Mock()
    lock = Mock()
    with patch.object(launcher, 'RUNTIME', tmp_path), patch.object(launcher, 'singleton', return_value=lock), \
            patch.object(launcher, 'preflight', return_value={}), \
            patch('jarvis.docker_runtime.start_background', return_value=handle), \
            patch.object(launcher, 'prepare_runtime', side_effect=InterruptedError):
        launcher.run()
    handle.close.assert_called_once_with()
    lock.close.assert_called_once_with()


def test_P01_D2_launcher_without_docker_handle_exits_cleanly(tmp_path):
    from jarvis import launcher
    lock = Mock()
    with patch.object(launcher, 'RUNTIME', tmp_path), patch.object(launcher, 'singleton', return_value=lock), \
            patch.object(launcher, 'preflight', side_effect=InterruptedError):
        launcher.run()  # Previously relied on locals() introspection; must not raise NameError.
    lock.close.assert_called_once_with()


def cognition(tmp_path, **extra):
    actions = SimpleNamespace(base=tmp_path, whatsapp_prompts=[], current_item=None, pending_tasks=[],
                              approvals_waiting=0, session_style={}, memory=Mock(), **extra)
    return Cognition(actions)


def test_P01_D4_failed_memory_sources_are_counted_not_silent(tmp_path):
    curator = SimpleNamespace(enabled=True, relevant=Mock(side_effect=OSError('vault offline')), conversations=Mock())
    skills = SimpleNamespace(context=Mock(side_effect=KeyError('broken')))
    mind = cognition(tmp_path, curator=curator, skills=skills)
    try:
        found = mind.recall('open my notes', 3)
        mind.recall('open my notes', 3)
    finally:
        mind.close()
    # Recall still degrades gracefully: missing sources are absent, not fabricated.
    assert 'declarative' not in found and 'procedural_skills' not in found
    errors = mind.snapshot()['memory_source_errors']
    assert errors == {'curator': {'count': 2, 'last_error': 'OSError'},
                      'skills': {'count': 2, 'last_error': 'KeyError'}}


def test_P01_D4_healthy_recall_reports_no_errors(tmp_path):
    mind = cognition(tmp_path)
    try:
        mind.recall('weather today', 2)
        assert mind.snapshot()['memory_source_errors'] == {}
    finally:
        mind.close()


def test_P01_D3_hierarchical_planner_initializes_validation_feedback():
    source = (BASE / 'jarvis/hierarchical.py').read_text(encoding='utf-8')
    assert source.index("error = ''") < source.index("validation_error=error if attempt else ''")


def test_P01_D5_web_audit_test_does_not_overwrite_dated_evidence():
    source = (BASE / 'tests/test_web_development_audit.py').read_text(encoding='utf-8')
    body = source.split('def test_JRV_22_001_real_authored_build_and_owned_preview', 1)[1].split('\ndef ', 1)[0]
    assert "JARVIS_CAPTURE_AUDIT_EVIDENCE" in body and 'evidence_dir/' in body
    assert "BASE/'artifacts/jarvis-audit/modules/22-web-development/build-checks.json'" not in body


def test_P01_contract_outcome_round_trip_correlates_with_lifecycle(tmp_path):
    actions = SimpleNamespace(base=tmp_path)
    call = event(actions, 'tool.started', 'read_file')
    contracts.record_outcome(actions, 'read_file', call, method_tier='api', adapter='native_files',
                             idempotency='read_only', verification='verified', latency_ms=12.5, attempts=1,
                             skill_id='file-operations')
    rows = contracts.read_outcomes(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row['call_id'] == call and row['tool'] == 'read_file'
    assert {k: row[k] for k in ('method_tier', 'adapter', 'idempotency', 'verification', 'latency_ms', 'attempts', 'skill_id')} == {
        'method_tier': 'api', 'adapter': 'native_files', 'idempotency': 'read_only', 'verification': 'verified',
        'latency_ms': 12.5, 'attempts': 1, 'skill_id': 'file-operations'}
    assert 'discarded_metadata_fields' not in row


def test_P01_contract_outcome_rejects_payloads_and_malformed_values(tmp_path):
    actions = SimpleNamespace(base=tmp_path)
    call = event(actions, 'tool.started', 'read_file')
    contracts.record_outcome(actions, 'read_file', call, method_tier='gui', verification='unverified',
                             adapter='Bad Adapter!', latency_ms=float('nan'), attempts=99, skill_id='../../etc',
                             content='FAKE_PRIVATE', api_key='FAKE_TOKEN', idempotency='sometimes')
    row = contracts.read_outcomes(tmp_path)[0]
    assert 'FAKE_' not in json.dumps(row) and '../' not in json.dumps(row)
    assert set(row) == {'version', 'at', 'event', 'call_id', 'tool', 'method_tier', 'verification',
                        'discarded_metadata_fields', 'clock_id', 'monotonic_ns'}
    assert row['discarded_metadata_fields'] == 7


def test_P01_contract_outcome_requires_correlation_and_known_states(tmp_path):
    actions = SimpleNamespace(base=tmp_path)
    with pytest.raises(ValueError, match='call_id'):
        contracts.record_outcome(actions, 'read_file', 'not-a-call', method_tier='api', verification='verified')
    call = event(actions, 'tool.started', 'read_file')
    with pytest.raises(ValueError, match='method tier'):
        contracts.record_outcome(actions, 'read_file', call, method_tier='magic', verification='verified')


def test_P01_lifecycle_events_still_drop_outcome_fields(tmp_path):
    actions = SimpleNamespace(base=tmp_path)
    event(actions, 'tool.completed', 'read_file', method_tier='api', verification='verified', backend='files')
    row = json.loads((tmp_path / '.jarvis-runtime/agent-events.jsonl').read_text())
    assert 'method_tier' not in row and row['backend'] == 'files' and row['discarded_metadata_fields'] == 2


def test_P01_contract_replay_policy_matches_no_replay_rule():
    assert [name for name in contracts.IDEMPOTENCY if contracts.may_replay(name)] == ['read_only', 'idempotent']
    assert contracts.METHOD_TIERS == ('api', 'structured', 'gui')


def test_P01_read_outcomes_is_bounded_and_skips_foreign_lines(tmp_path):
    path = tmp_path / '.jarvis-runtime/agent-events.jsonl'
    path.parent.mkdir(parents=True)
    path.write_text('not json\n' + json.dumps({'version': 1, 'event': 'tool.started'}) + '\n'
                    + json.dumps({'version': 1, 'event': 'tool.outcome', 'tool': 'open'}) + '\n', encoding='utf-8')
    assert [r['tool'] for r in contracts.read_outcomes(tmp_path)] == ['open']
    with pytest.raises(ValueError):
        contracts.read_outcomes(tmp_path, limit=0)


def test_P01_baseline_script_measures_without_failed_sections(tmp_path):
    out = tmp_path / 'metrics.json'
    result = subprocess.run([sys.executable, str(BASE / 'scripts/verification/phase_baseline.py'), '--label', 'test',
                             '--out', str(out)], cwd=BASE, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr[-2000:]
    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['schema_version'] == 1
    assert all(section['status'] == 'MEASURED' for section in data['sections'].values())
    registry_section = data['sections']['tool_registry']
    assert registry_section['malformed_dispatched'] == 0 and registry_section['contract_error_rate'] == 0
    assert data['sections']['privacy_routing']['private_marked_public'] == 0
    # Preserved measurements are never silently overwritten.
    again = subprocess.run([sys.executable, str(BASE / 'scripts/verification/phase_baseline.py'), '--label', 'test',
                            '--out', str(out)], cwd=BASE, capture_output=True, text=True, timeout=300)
    assert again.returncode != 0 and 'Refusing to overwrite' in again.stderr
