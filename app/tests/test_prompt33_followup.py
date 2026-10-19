"""Claude follow-up verification for Codex's 2c4ea56 handoff: P33-004 identity, P33-002/003 contract edges,
MCP dependent-skill invalidation and retrieval, and registry concurrency. Every provider call is intercepted."""
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from jarvis.task_state import TaskState  # noqa: E402
from jarvis.tools import ToolRegistry  # noqa: E402

EVENT = {'action': 'calendar_create', 'value': 'primary',
         'content': json.dumps({'summary': 'SYNTHETIC', 'start': {'date': '2026-10-20'}, 'end': {'date': '2026-10-21'}})}


def host(tmp_path, approve):
    state = TaskState(tmp_path)
    state.start('Synthetic provider identity case', 'task')
    return SimpleNamespace(base=tmp_path, config={}, skills=None, allowed_tools=None, task_state=state, report=Mock(),
                           _approve=approve)


def run_create(tmp_path, start_env, during_approval):
    ledger, cards = [], []
    def approve(kind, detail, cancelled):
        cards.append(json.loads(detail))
        os.environ.update(during_approval)  # simulated change while the card is pending
    def api(client, method, url, cancelled, **kwargs):
        ledger.append({'method': method, 'auth': kwargs['headers']['Authorization']})
        return json.dumps({'id': 'SYNTHETIC_EVENT'})
    actions = host(tmp_path, approve)
    with patch.dict(os.environ, start_env, clear=True), patch('jarvis.toolkits.api', side_effect=api):
        try:
            ToolRegistry(actions).execute(dict(EVENT), lambda: False)
            outcome = 'sent'
        except ValueError as exc:
            outcome = str(exc)
    return outcome, ledger, cards, actions


# ---- P33-004 -----------------------------------------------------------------------------------------------------------
def test_verified_account_switch_while_approval_pending_writes_nothing(tmp_path):
    outcome, ledger, cards, _ = run_create(
        tmp_path, {'JARVIS_GOOGLE_ACCOUNT': 'account-a@example.test', 'JARVIS_GOOGLE_ACCESS_TOKEN': 'SYNTHETIC_TOKEN_A_0001'},
        {'JARVIS_GOOGLE_ACCOUNT': 'account-b@example.test', 'JARVIS_GOOGLE_ACCESS_TOKEN': 'SYNTHETIC_TOKEN_B_0002'})
    assert 'account changed' in outcome and ledger == []  # zero writes to B (or anywhere)
    assert cards[0]['account'] == 'account-a@example.test' and cards[0]['identity_verified'] is True
    assert cards[0]['provider'] == 'calendar' and cards[0]['target'] == 'primary'


def test_token_rotation_for_the_same_verified_account_proceeds_and_is_recorded(tmp_path):
    outcome, ledger, cards, actions = run_create(
        tmp_path, {'JARVIS_GOOGLE_ACCOUNT': 'account-a@example.test', 'JARVIS_GOOGLE_ACCESS_TOKEN': 'SYNTHETIC_TOKEN_A_0001'},
        {'JARVIS_GOOGLE_ACCESS_TOKEN': 'SYNTHETIC_TOKEN_A_ROTATED'})
    assert outcome == 'sent' and ledger == [{'method': 'POST', 'auth': 'Bearer SYNTHETIC_TOKEN_A_ROTATED'}]
    evidence = json.dumps(actions.task_state.snapshot())
    assert 'credential rotated for the same verified account' in evidence and 'SYNTHETIC_TOKEN' not in evidence


def test_unverified_credential_change_is_refused_and_tokens_never_reach_the_card(tmp_path):
    outcome, ledger, cards, _ = run_create(tmp_path, {'JARVIS_GOOGLE_ACCESS_TOKEN': 'SYNTHETIC_TOKEN_A_0001'},
                                           {'JARVIS_GOOGLE_ACCESS_TOKEN': 'SYNTHETIC_TOKEN_A_ROTATED'})
    assert 'cannot be confirmed' in outcome and ledger == []
    assert cards[0]['identity_verified'] is False and 'SYNTHETIC_TOKEN' not in json.dumps(cards)


def test_unchanged_context_dispatches_with_the_approved_credential(tmp_path):
    outcome, ledger, cards, _ = run_create(
        tmp_path, {'JARVIS_GOOGLE_ACCOUNT': 'account-a@example.test', 'JARVIS_GOOGLE_ACCESS_TOKEN': 'SYNTHETIC_TOKEN_A_0001'}, {})
    assert outcome == 'sent' and ledger == [{'method': 'POST', 'auth': 'Bearer SYNTHETIC_TOKEN_A_0001'}]


def test_jira_identity_is_url_and_user_not_the_token():
    from jarvis.provider_identity import AccountDrift, ProviderContext
    env = {'JARVIS_JIRA_URL': 'https://a.example.test', 'JARVIS_JIRA_USER': 'alice', 'JARVIS_JIRA_TOKEN': 'SYNTHETIC_JIRA_1'}
    context = ProviderContext('jira', env)
    assert context.verified and context.account == 'https://a.example.test / alice'
    assert context.recheck({**env, 'JARVIS_JIRA_TOKEN': 'SYNTHETIC_JIRA_2'}).rotated is True
    with pytest.raises(AccountDrift):
        context.recheck({**env, 'JARVIS_JIRA_USER': 'bob'})
    with pytest.raises(AccountDrift):
        context.recheck({**env, 'JARVIS_JIRA_URL': 'https://b.example.test'})


# ---- P33-002 / P33-003 ------------------------------------------------------------------------------------------------
def test_over_budget_values_are_rejected_whole_and_json_equality_is_type_aware():
    from jarvis.mcp_contract import MAX_ITEMS, ContractError, json_equal, validate_schema_value
    with pytest.raises(ContractError, match='rejected as a whole'):
        validate_schema_value({'type': 'array'}, [0] * (MAX_ITEMS + 1))
    with pytest.raises(ContractError, match='budget'):
        validate_schema_value({'type': 'array', 'items': {'type': 'array'}}, [[0] * 9000] * 12)
    assert validate_schema_value({'type': 'array', 'items': {'type': 'integer'}}, list(range(MAX_ITEMS)))
    assert json_equal(1, 1.0) and json_equal([1, {'a': True}], [1.0, {'a': True}])
    assert not json_equal(False, 0) and not json_equal(True, 1) and not json_equal([0], [False])
    assert validate_schema_value({'enum': [1, 'x']}, 1.0) and validate_schema_value({'const': [True]}, [True])


@pytest.mark.parametrize('block,ok', [
    ({'type': 'resource', 'resource': {'uri': 'mem://a', 'text': 'x', 'mimeType': 'text/plain'}}, True),
    ({'type': 'resource', 'resource': {'uri': 'mem://a', 'blob': 'eA=='}}, True),
    ({'type': 'resource', 'resource': {'uri': 'mem://a', 'text': 'x', 'blob': 'eA=='}}, False),
    ({'type': 'resource', 'resource': {'uri': '', 'text': 'x'}}, False),
    ({'type': 'resource', 'resource': {'uri': 'mem://a', 'text': 5}}, False),
    ({'type': 'resource', 'resource': {'uri': 'mem://a', 'text': 'x', 'surprise': 1}}, False),
    ({'type': 'resource_link', 'uri': 'mem://a', 'name': 'a', 'size': 3}, True),
    ({'type': 'resource_link', 'uri': 'mem://a', 'name': 'a', 'size': True}, False),
    ({'type': 'text', 'text': 'x', 'annotations': {'audience': ['user']}}, True),
    ({'type': 'text', 'text': 'x', 'extra': 1}, False),
])
def test_content_blocks_follow_the_supported_contract(block, ok):
    from jarvis.mcp_contract import ContractError, validate_result
    if ok:
        assert validate_result({'content': [block]})
    else:
        with pytest.raises(ContractError):
            validate_result({'content': [block]})


def test_malformed_result_keeps_the_uncertain_write_checkpoint(tmp_path):
    original = __import__('runpy').run_path(str(BASE / 'tests' / 'test_prompt33_mcp_boundaries.py'))
    actions, _ = original['fixture'](tmp_path, 'malformed')
    with pytest.raises(ValueError):
        ToolRegistry(actions).execute(original['step'](count=1), lambda: False)
    assert 'not verified' in actions.task_state.resume_blocker(actions.task_state.snapshot())


# ---- dependent-skill invalidation, retrieval and concurrency ---------------------------------------------------------
def skills_with_dependent(tmp_path):
    from jarvis.skill_memory import SkillMemory
    source = tmp_path / 'skills'
    for name, body in (('fingerprint-text', 'Call mcp_call on gen-x to fingerprint text.'),
                       ('unrelated-notes', 'Write notes with create_file.')):
        folder = source / name
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Fingerprint text with the generated sha tool\n'
                                         f'tools: []\n---\n\n{body}\n', encoding='utf-8')
    memory = SimpleNamespace(vault=tmp_path / 'vault', base=tmp_path, enabled=True, hermes_skills_enabled=False)
    (tmp_path / 'vault').mkdir()
    return SkillMemory(memory, source)


def test_drift_disables_dependent_skills_they_are_not_retrieved_and_health_restores_them(tmp_path):
    from jarvis import mcp_synthesis
    skills = skills_with_dependent(tmp_path)
    names = lambda: [row['name'] for row in skills.context('fingerprint text with the generated sha tool')['skills']]
    assert 'fingerprint-text' in names()
    assert mcp_synthesis.invalidate_dependent_skills(skills, 'gen-x') == ['fingerprint-text']
    assert 'fingerprint-text' not in names() and 'unrelated-notes' in [r['name'] for r in skills.catalog if r['enabled']]
    record = skills.store.record(next(r['skill_id'] for r in skills.catalog if r['name'] == 'fingerprint-text'))
    assert record['enabled'] == 0 and json.loads(record['compatibility_json'])['server'] == 'gen-x'
    assert mcp_synthesis.restore_dependent_skills(skills, 'gen-x') == ['fingerprint-text']
    assert 'fingerprint-text' in names()


def test_execution_drift_through_the_bridge_path_invalidates_dependents(tmp_path):
    from jarvis import mcp_synthesis
    skills = skills_with_dependent(tmp_path)
    folder = tmp_path / 'gen' / 'gen-x' / 'abc'
    folder.mkdir(parents=True)
    (folder / 'server.py').write_text('print(1)\n', encoding='utf-8')
    (folder / 'spec.json').write_text('{}', encoding='utf-8')
    image = 'sha256:' + 'a' * 64
    mcp_synthesis.save_registry(tmp_path, {'version': 1, 'history': [], 'servers': {'gen-x': {
        'command': 'docker', 'args': ['type=bind,src=' + str(folder / 'server.py') + ',dst=/server.py,readonly', image],
        'trusted': True, 'enabled': True, 'allow_tools': ['x'], 'timeout_seconds': 5, 'status': 'provisional',
        'code_sha256': hashlib.sha256(b'print(2)\n').hexdigest(),  # does not match: drift
        'spec_sha256': hashlib.sha256(b'{}').hexdigest(), 'schema_sha256': 's' * 64, 'image_id': image}}})
    config = mcp_synthesis.configurations(tmp_path)['gen-x']
    with patch.object(mcp_synthesis, 'image_status', return_value={'available': True, 'image_id': image}):
        with pytest.raises(ValueError, match='revalidation'):
            mcp_synthesis.verified_execution_config(tmp_path, 'gen-x', config, skills=skills)
    assert not next(r for r in skills.catalog if r['name'] == 'fingerprint-text')['enabled']


def test_concurrent_registry_updates_stay_consistent(tmp_path):
    from jarvis import mcp_synthesis
    servers = {f'gen-s{i}': {'command': 'docker', 'args': [], 'enabled': True, 'status': 'provisional'} for i in range(16)}
    mcp_synthesis.save_registry(tmp_path, {'version': 1, 'servers': servers, 'history': []})
    errors = []
    def drift(name):
        try:
            mcp_synthesis.mark_drifted(tmp_path, name, 'concurrency check')
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(repr(exc))
    threads = [threading.Thread(target=drift, args=(name,)) for name in servers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    registry = mcp_synthesis.load_registry(tmp_path)
    assert errors == [] and all(row['status'] == 'drifted' for row in registry['servers'].values())
    assert len(registry['history']) == 16 and mcp_synthesis.configurations(tmp_path) == {}
