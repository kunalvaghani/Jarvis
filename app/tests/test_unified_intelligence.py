"""Offline integration/safety checks; no live model, connector or desktop proof."""
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from jarvis.actions import Actions
from jarvis.capabilities import (PREREQUISITES, RANKING, ROUTES, _tool_index,
                                 intents, rank_tools, tokens)
from jarvis.capability_model import CapabilityModel
from jarvis.commands import Command
from jarvis.deliberation import execution_path
from jarvis.tools import SPECS, ToolRegistry, ToolSpec


def legacy_rank(specs, query, allowed=None, limit=12):
    """Original exhaustive algorithm as an independent ranking oracle (no skills)."""
    from jarvis.toolkits import TOOLS, available
    words, boosts, ranked = tokens(query), {}, []
    import re
    for intent in intents(query):
        for i, name in enumerate(ROUTES[intent][1]):
            boosts[name] = max(boosts.get(name, 0), RANKING['route_boost'] - min(i, RANKING['route_step_cap']) * RANKING['route_step'])
    for spec in specs.values():
        if isinstance(allowed, (set, frozenset)) and spec.name not in allowed:
            continue
        if spec.name in TOOLS and not available(spec.name):
            continue
        score = len(words & tokens(spec.name.replace('_', ' ') + ' ' + spec.description)) + boosts.get(spec.name, 0)
        if re.search(r'(?<!\w)' + re.escape(spec.name) + r'(?!\w)', query.casefold()):
            score += RANKING['exact_name_bonus']
        if score:
            ranked.append((score, spec.name))
    selected = [name for _, name in sorted(ranked, key=lambda x: (-x[0], x[1]))[:max(0, min(limit, 30))]]
    for name in list(selected):
        for dependency in PREREQUISITES.get(name, ()):
            if dependency in specs and dependency not in selected and (
                    not isinstance(allowed, (set, frozenset)) or dependency in allowed) and (
                    dependency not in TOOLS or available(dependency)) and len(selected) < 30:
                selected.append(dependency)
    return selected


@pytest.mark.parametrize('query', ['Python code', 'browser_click', 'read_file then modify_file',
    'research sources', 'Blender model', 'Unreal scene', 'play YouTube', 'spreadsheets cells',
    'files folders directory', 'tool_search!', 'ébrowser_click', '_browser_click',
    'browser_click2', 'unknownnothing', '', 'runtime capabilities'])
@pytest.mark.parametrize('limit', [0, 1, 12, 30])
def test_index_matches_exhaustive_oracle(query, limit):
    specs = {s.name: s for s in SPECS}
    with patch('jarvis.toolkits.available', return_value=True):
        assert rank_tools(specs, query, limit=limit) == legacy_rank(specs, query, limit=limit)


def test_index_invalidates_on_replacement_and_removal():
    specs = {'custom': ToolSpec('custom', 'toolkit', 'zebra')}
    assert rank_tools(specs, 'zebra') == ['custom']
    specs['custom'] = ToolSpec('custom', 'toolkit', 'giraffe')
    assert rank_tools(specs, 'zebra') == []
    assert rank_tools(specs, 'giraffe') == ['custom']
    specs.clear()
    assert rank_tools(specs, 'giraffe') == []


def test_cached_discovery_rechecks_scope_and_availability():
    specs = {s.name: s for s in SPECS}
    with patch('jarvis.toolkits.available', return_value=True):
        assert 'read_email' in rank_tools(specs, 'read_email')
    with patch('jarvis.toolkits.available', return_value=False):
        assert 'read_email' not in rank_tools(specs, 'read_email')
    assert rank_tools(specs, 'read_file', allowed=set()) == []


def test_manifest_reconciles_disk_without_trusting_saved_tools(tmp_path):
    specs = {'read_file': next(s for s in SPECS if s.name == 'read_file')}
    model = CapabilityModel(tmp_path)
    assert model.refresh(specs)
    path = tmp_path / '.jarvis-runtime/capabilities.json'
    original = json.loads(path.read_text())
    stamp = path.stat().st_mtime_ns
    assert model.refresh(specs)
    assert path.stat().st_mtime_ns == stamp
    original['capabilities']['fake_shell'] = {'approval': 'none'}
    original['capabilities']['read_file']['approval'] = 'forged'
    path.write_text(json.dumps(original))
    restarted = CapabilityModel(tmp_path)
    restarted.refresh(specs)
    saved = json.loads(path.read_text())['capabilities']
    assert set(saved) == {'read_file'}
    assert saved['read_file']['approval'] == specs['read_file'].approval
    specs.clear()
    restarted.refresh(specs)
    assert restarted.records == {}


def test_manifest_scope_health_and_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'private-token-should-never-persist')
    actions = SimpleNamespace(base=tmp_path, allowed_tools={'read_file'})
    registry = ToolRegistry(actions)
    result = registry.self_model(['read_file', 'run_command', 'fake_shell'])
    assert [r['name'] for r in result['capabilities']] == ['read_file']
    assert result['capabilities'][0]['connection_health'] == 'not_probed'
    assert 'private-token-should-never-persist' not in (tmp_path / '.jarvis-runtime/capabilities.json').read_text()
    actions.allowed_tools = set()
    assert registry.self_model(['read_file'])['capabilities'] == []


def test_manifest_interrupt_does_not_commit_partial_index(tmp_path):
    model = CapabilityModel(tmp_path)
    assert not model.refresh({s.name: s for s in SPECS}, lambda: True)
    assert not (tmp_path / '.jarvis-runtime/capabilities.json').exists()


def test_manifest_storage_failure_preserves_runtime_view(tmp_path):
    model = CapabilityModel(tmp_path)
    with patch('jarvis.skill_memory.atomic', side_effect=PermissionError):
        assert model.refresh({s.name: s for s in SPECS})
    assert model.status == 'memory_only'
    assert 'read_file' in model.records


def test_self_model_results_cannot_mutate_later_metadata(tmp_path):
    model = CapabilityModel(tmp_path)
    specs = {s.name: s for s in SPECS}
    first = model.describe(specs, ['read_file'])
    first['capabilities'][0]['arguments']['required'].clear()
    assert 'action' in model.describe(specs, ['read_file'])['capabilities'][0]['arguments']['required']


def test_self_model_uses_existing_advisory_metrics(tmp_path):
    from jarvis.execution_contracts import record_outcome
    actions = SimpleNamespace(base=tmp_path)
    record_outcome(actions, 'read_file', 'a' * 32, method_tier='api', adapter='files',
                   idempotency='read_only', verification='verified', latency_ms=12.5)
    row = ToolRegistry(actions).self_model(['read_file'])['capabilities'][0]
    assert row['performance']['observed_calls'] == 1
    assert row['performance']['reported_verified'] == 1
    assert row['performance']['latency_p95_ms'] == 12.5


def test_generated_registry_recovers_only_unchanged_metadata(tmp_path):
    from pathlib import Path
    from jarvis.mcp_synthesis import save_registry, load_registry
    actual, calls = Path.replace, []
    def replace(path, destination):
        if destination.name == 'registry.json':
            calls.append(True)
            if len(calls) == 1:
                error = PermissionError('Injected Windows sharing conflict')
                error.winerror = 5
                raise error
        return actual(path, destination)
    data = {'version': 1, 'servers': {}, 'history': []}
    with patch.object(Path, 'replace', replace):
        save_registry(tmp_path, data)
    assert load_registry(tmp_path) == data
    assert len(calls) == 2
    journal = tmp_path / '.jarvis-runtime/repairs.jsonl'
    assert journal.is_file() and 'unchanged metadata' in journal.read_text()


@pytest.mark.parametrize('outcome', ['verified', 'not_dispatched', 'uncertain'])
def test_actions_try_exact_executor_before_opinion_and_do_not_replay(tmp_path, outcome):
    from jarvis.task_state import TaskState
    actions = Actions.__new__(Actions)
    actions.config = {'agent_runtime': {'direct_execution': True}}
    actions.apps, actions.pending_question, actions.resume_source = {}, None, None
    actions.deliberation = SimpleNamespace(enabled=True)
    actions.projects, actions.ui_controls = SimpleNamespace(pending=None), None
    actions.report = Mock()
    actions.task_state = TaskState(tmp_path)
    actions.brain = SimpleNamespace(run=Mock(return_value='Task paused: synthetic planner needs fresh state'))
    actions._form_task_opinion = Mock(side_effect=AssertionError('unnecessary model opinion'))
    actions._suggest_recovery = lambda goal, result, cancelled: result
    def direct(*args):
        if outcome == 'uncertain':
            raise ValueError('Task paused: input outcome uncertain')
        if outcome == 'not_dispatched':
            return None
        actions.task_state.checkpoint('goal_verified', source='explicit_desktop_native_postconditions',
                                      evidence='Synthetic native-state oracle matched')
        return 'Finished synthetic direct workflow'
    with patch('jarvis.blender_host.route', return_value=(False, None)), \
            patch('jarvis.spotify_host.route', return_value=(False, None)), \
            patch('jarvis.direct_execution.run', side_effect=direct) as executor:
        if outcome == 'uncertain':
            with pytest.raises(ValueError, match='uncertain'):
                actions._execute(Command('task', 'scroll down then scroll up'))
        else:
            actions._execute(Command('task', 'scroll down then scroll up'))
    assert executor.call_count == 1
    actions._form_task_opinion.assert_not_called()
    assert actions.brain.run.call_count == (1 if outcome == 'not_dispatched' else 0)


@pytest.mark.parametrize('text,expected', [
    ('click Save', 'REFLEX'), ('fill Search field with "hello"', 'REFLEX'),
    ('scroll down then scroll up', 'REFLEX'), ('research architecture improvements', 'DEEP'),
    ('delete all files', 'DEEP'), ('maybe click Save', 'DEEP'),
    ('click Save then invent a model', 'DEEP'), ('list files', 'FAST')])
def test_executive_uses_complete_grammar_only(text, expected):
    assert execution_path(Command('task', text), {'direct_execution': True})['path'] == expected


def test_routing_never_runs_tools_or_models_and_respects_flags():
    assert execution_path(Command('task', 'click Save button'), {})['path'] == 'DEEP'
    assert execution_path(Command('task', 'click Save'), {'direct_execution': True}, resuming=True)['path'] == 'DEEP'
    assert execution_path(Command('ask', 'what is recursion'))['path'] == 'FAST'
    assert execution_path(Command('code_task', 'fix code'))['path'] == 'DEEP'
    assert execution_path(Command('open', 'chrome'))['path'] == 'REFLEX'
    fake = SimpleNamespace(config={'agent_runtime': {'direct_execution': True}}, apps={})
    assert not Actions._should_deliberate(fake, 'click Save')
    assert Actions._should_deliberate(fake, 'delete all files')


def test_idle_preparation_respects_foreground_and_shutdown(tmp_path):
    from jarvis.self_evolution import SelfEvolution
    actions = SimpleNamespace(base=tmp_path)
    evolution = SelfEvolution(actions, {'enabled': True}, busy=lambda: True)
    with patch.object(evolution, '_resources_ok', return_value=True):
        assert not evolution.capability_maintenance()
        evolution.busy = lambda: False
        evolution.last_activity -= 1000
        assert evolution.capability_maintenance()
        stamp = (tmp_path / '.jarvis-runtime/capabilities.json').stat().st_mtime_ns
        evolution.note_activity()
        assert not evolution.capability_maintenance()
        assert (tmp_path / '.jarvis-runtime/capabilities.json').stat().st_mtime_ns == stamp
        evolution.close()
        assert not evolution.capability_maintenance()


def release(tag):
    return {'draft': False, 'prerelease': False, 'tag_name': tag, 'published_at': '2026-10-21T00:00:00Z'}


def test_technology_watch_disabled_and_unknown_sources_never_fetch(tmp_path):
    from jarvis.technology_watch import TechnologyWatch
    fetch = Mock(side_effect=AssertionError('unexpected fetch'))
    assert TechnologyWatch(tmp_path).tick(fetch=fetch) is None
    assert not (tmp_path / '.jarvis-runtime/technology-watch.json').exists()
    fetch.assert_not_called()
    with pytest.raises(ValueError):
        TechnologyWatch(tmp_path, {'enabled': True, 'sources': ['evil/source']})


def test_release_changes_are_deduplicated_and_survive_restart(tmp_path):
    from jarvis.technology_watch import TechnologyWatch
    now = [10_000.]
    opts = {'enabled': True, 'sources': ['ollama'], 'interval_seconds': 3600}
    watcher = TechnologyWatch(tmp_path, opts, lambda: now[0])
    first = Mock(return_value=release('v1.0'))
    assert watcher.tick(fetch=first) is None
    assert watcher.tick(fetch=first) is None
    assert first.call_count == 1
    now[0] += 3601
    finding = watcher.tick(fetch=lambda *args: release('v1.1'))
    assert finding['compatibility'] == 'not_tested'
    assert finding['url'] == 'https://github.com/ollama/ollama/releases/tag/v1.1'
    restarted = TechnologyWatch(tmp_path, opts, lambda: now[0])
    assert len(restarted.findings) == 1
    now[0] += 3601
    assert restarted.tick(fetch=lambda *args: release('v1.1')) is None
    assert len(restarted.findings) == 1


def test_watch_failures_back_off_and_cancellation_does_not_commit(tmp_path):
    from jarvis.technology_watch import TechnologyWatch
    watcher = TechnologyWatch(tmp_path, {'enabled': True, 'sources': ['mcp']}, lambda: 10_000.)
    fetch = Mock(side_effect=TimeoutError)
    assert watcher.tick(fetch=fetch) is None
    assert watcher.status == 'deferred'
    watcher.tick(fetch=fetch)
    assert fetch.call_count == 1
    watcher.state.clear()
    before = (tmp_path / '.jarvis-runtime/technology-watch.json').read_bytes()
    cancel = [False]
    def interrupted(*args):
        cancel[0] = True
        return release('v2.0')
    assert watcher.tick(lambda: cancel[0], interrupted) is None
    assert (tmp_path / '.jarvis-runtime/technology-watch.json').read_bytes() == before


def test_recent_failure_blocks_an_older_verified_navigation_recipe(tmp_path):
    from jarvis.obsidian_memory import ObsidianMemory
    from jarvis.skill_memory import SkillMemory
    from jarvis.step_planning import WorkflowMemory, fingerprint, replay
    memory = ObsidianMemory(tmp_path, {'enabled': True, 'vault': 'vault'})
    skills = SkillMemory(memory)
    goal = 'Show Settings'
    before = {'title': 'Editor', 'context': '["notepad.exe"]',
              'controls': [{'name': 'Settings', 'role': 'TabItem', 'context': '', 'selected': False}]}
    after = {**before, 'controls': [{**before['controls'][0], 'selected': True}]}
    workflows = WorkflowMemory(tmp_path)
    session = SimpleNamespace(goal_verified=True, learnable=True, trace=[{
        'action': 'select', 'value': 'Settings', 'expected': 'Settings selected',
        'role': 'TabItem', 'context': '', 'before': fingerprint(before), 'after': fingerprint(after)}])
    assert workflows.remember(goal, session)
    assert workflows.proposal(goal, before) is not None
    # Real persisted negative experience, rather than a model-written workflow.
    skills.experiences.record({'goal': goal, 'kind': 'task', 'status': 'failed',
                              'conditions': {'surface': 'Editor'}, 'checkpoints': [],
                              'result': 'Requested settings did not appear'})
    actions = SimpleNamespace(skills=skills, resume_source=None)
    brain = SimpleNamespace(actions=actions, workflows=workflows,
                            observe=Mock(return_value=(7, before)), dispatch=Mock())
    assert replay(brain, goal, lambda: False) is None
    brain.dispatch.assert_not_called()
    skills.close()


@pytest.mark.parametrize('data', [release('../../run'), {'draft': True}, release('v1') | {'published_at': 'bad'}])
def test_untrusted_release_records_cannot_create_findings(tmp_path, data):
    from jarvis.technology_watch import TechnologyWatch
    watcher = TechnologyWatch(tmp_path, {'enabled': True, 'sources': ['ollama']})
    assert watcher.tick(fetch=lambda *args: data) is None
    assert not watcher.findings
