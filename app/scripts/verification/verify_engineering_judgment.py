"""Real installed-model/native-coder probe on a deliberately buggy owned connector."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis.coder import Coder
from jarvis.commands import Command
from jarvis.engineering_judgment import EngineeringJudgmentEngine
from jarvis.task_scheduler import ScheduledQueue
from jarvis.task_state import TaskState
from jarvis.task_store import TaskStore
from jarvis import native_coding

SOURCE = '''def video_url(video_id):
    return "https://www.youtube.com/watch?v=" + video_id

def normalize_playlist(items):
    return [item["id"] for item in items]

def playlist_title(playlist):
    return playlist["title"]
'''
CORE = '''import unittest
from youtube_connector import normalize_playlist, video_url
class Core(unittest.TestCase):
    def test_existing_url(self):
        self.assertEqual(video_url("v1"), "https://www.youtube.com/watch?v=v1")
    def test_missing_playlist(self):
        self.assertEqual(normalize_playlist(None), [])
    def test_valid_items_preserve_order_without_duplicates(self):
        self.assertEqual(normalize_playlist([{"id":"v1"}, {}, {"id":"v2"}, {"id":"v1"}, {"id":""}, None,
            {"id":None}, {"id":123}, {"id":[]}, {"id":"  "}]), ["v1", "v2"])
'''
PLAYLIST = '''import unittest
from youtube_connector import playlist_title
class Playlist(unittest.TestCase):
    def test_missing_title(self):
        self.assertEqual(playlist_title(None), "Untitled")
        self.assertEqual(playlist_title({}), "Untitled")
        self.assertEqual(playlist_title({"title":""}), "Untitled")
        self.assertEqual(playlist_title({"title":"  "}), "Untitled")
    def test_valid_title(self):
        self.assertEqual(playlist_title({"title":" Mix "}), "Mix")
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--mode', default='enforced', choices=('disabled', 'advisory', 'enforced'))
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    root = out / 'project'; root.mkdir()
    (root / 'youtube_connector.py').write_text(SOURCE)
    (root / 'test_core.py').write_text(CORE)
    (root / 'test_playlist.py').write_text(PLAYLIST)
    (root / 'notes.txt').write_text('Existing user fixture notes; preserve exactly.\n')
    (root / 'pyproject.toml').write_text('[project]\nname="owned-youtube-fixture"\n')
    events = []
    actions = SimpleNamespace(base=out, report=lambda *a: events.append(a), task_state=TaskState(out))
    actions.engineering = EngineeringJudgmentEngine(actions, {'enabled': args.mode != 'disabled',
        'mode': args.mode if args.mode != 'disabled' else 'advisory', 'max_repair_attempts': 2})
    coder = Coder(actions, SimpleNamespace(options={'coder': 'qwen3.5:9b', 'max_coding_seconds': 240,
        'native_max_turns': 18, 'native_max_repairs': 2, 'native_predict': 1600}))
    store = TaskStore(out / 'tasks.sqlite3'); queue = ScheduledQueue(store)
    actions.task_state.on_checkpoint = lambda state: store.transition(queue.local.identity,
        store.get(queue.local.identity)['state'], 'Existing TaskState host checkpoint', checkpoint={
            **store.get(queue.local.identity)['checkpoint'], 'tool_checkpoint': state}) if getattr(queue.local, 'identity', None) else None
    goals = [
        'Fix youtube_connector.py normalize_playlist reliability: None returns an empty list; only nonblank string IDs are valid; ignore missing IDs, non-string IDs, blank/whitespace IDs and None entries; retain valid string IDs in order without duplicates. Preserve video_url and playlist_title. Read the existing frozen test_core.py. No network or accounts. Only edit youtube_connector.py.',
        'Also make playlist handling more reliable in the same youtube_connector.py: playlist_title(None) and missing/empty title return Untitled, strip whitespace from valid titles. Preserve normalize_playlist and video_url and all frozen tests. No network or accounts. Only edit youtube_connector.py.']
    identities = [queue.put_nowait((0, Command('code_task', goal, str(root)), threading.Event())) for goal in goals]
    graph = queue.graph; graph.move(identities[1], graph.node(identities[0])['workflow'])
    graph.set_dependencies(identities[1], [{'upstream': identities[0], 'requires_result': True}])
    graph.relation(identities[1], identities[0], 'CONTINUATION_OF', 'Explicit same-project playlist continuation', 1.)
    allowed = {'Read', 'Write', 'Edit', 'Glob', 'Grep', 'apply_patch', 'read_slice', 'run_checks', 'finish'}
    original_infer = native_coding.infer
    calls = []

    def scoped_inference(*a, **kw):
        result = original_infer(*a, **kw)  # Real installed Ollama model, not canned output.
        calls.append({'tool': result.get('tool'), 'at': time.time()})
        if result.get('tool') not in allowed:
            raise ValueError('Live probe refused an out-of-scope tool before execution.')
        return result

    source_root = Path(__file__).resolve().parents[2]
    frozen = {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [Path(__file__), *source_root.joinpath('jarvis').glob('*.py')]}
    receipt = {'started_at': datetime.now(timezone.utc).isoformat(), 'passed': False, 'mode': args.mode,
        'source_before': frozen,
        'scope': 'Actual ScheduledQueue/SQLite DAG, existing native coding model and independent executable checks on an owned deliberately buggy local connector. Host freezes plans/tests and denies network, accounts, shell, installation and non-source tools. Not real YouTube/account, voice/UI or overnight acceptance.',
        'model': 'qwen3.5:9b', 'microphone_started': False, 'account_effects': False, 'tasks': []}
    try:
        with patch('jarvis.native_coding.infer', scoped_inference):
            for index, goal in enumerate(goals):
                _, command, _ = queue.get(timeout=8)
                if command.value != goal:
                    raise AssertionError('Dependency dispatch order changed')
                inputs = queue.current_inputs()
                actions.task_state.start(goal, 'code_task', root)
                checks = [{'kind': 'python_tests', 'path': 'test_core.py'}]
                files = [{'path': 'youtube_connector.py', 'role': 'logic', 'purpose': 'Implement only requested connector behavior'},
                         {'path': 'test_core.py', 'role': 'test', 'purpose': 'Preserve existing URL and playlist normalization tests'}]
                if index:
                    checks.append({'kind': 'python_tests', 'path': 'test_playlist.py'})
                    files.append({'path': 'test_playlist.py', 'role': 'test', 'purpose': 'Verify new title requirement'})
                plan = {'files': files, 'checks': checks}
                with actions.engineering.coding(root, goal):
                    result = native_coding.run(coder, root, goal, initial_plan=plan,
                        allowed_paths=['youtube_connector.py'], return_receipt=True)
                contract = actions.engineering.last
                assert result['validation']['runtime_verified']
                if args.mode != 'disabled':
                    assert contract['state'] == 'verified'
                assert (root / 'notes.txt').read_text() == 'Existing user fixture notes; preserve exactly.\n'
                assert (root / 'test_core.py').read_text() == CORE and (root / 'test_playlist.py').read_text() == PLAYLIST
                output = {'goal_id': contract['goal_id'] if contract else None, 'checks': result['validation']['checks'],
                          'source_hashes': result['validation']['hashes'], 'scope': contract['scope'] if contract else 'Existing native scope guards; engineering disabled control'}
                queue.publish_output(output, verified=True)
                queue.outcome('COMPLETED', 'Host executable checks and goal scope verified')
                queue.task_done()
                actions.task_state.finish('completed', 'Verified owned connector fixture')
                receipt['tasks'].append({'id': identities[index], 'goal_id': contract['goal_id'] if contract else None, 'contract': contract,
                    'input_versions': [r.get('version') for r in inputs], 'validation': result['validation'],
                    'worker_review': str(Path(result['directory']).relative_to(out))})
                receipt['completed'] = len(receipt['tasks'])
                (out / 'acceptance.json').write_text(json.dumps(receipt, indent=2) + '\n')
        report, path = queue.report(out / 'reports')
        receipt.update(passed=True, calls=calls, graph=graph.snapshot(), report=str(path.relative_to(out)),
                       completed=report['counts'].get('COMPLETED', 0))
    except Exception as exc:
        receipt.update(error_type=type(exc).__name__, error=str(exc)[:1500], calls=calls)
    finally:
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        receipt['source_unchanged'] = all((source_root / name).is_file() and hashlib.sha256((source_root / name).read_bytes()).hexdigest() == digest
                                         for name, digest in frozen.items())
        receipt['passed'] = receipt['passed'] and receipt['source_unchanged']
        (out / 'acceptance.json').write_text(json.dumps(receipt, indent=2) + '\n')
        queue.close(); store.db.close()
    print(json.dumps({'passed': receipt['passed'], 'completed': receipt.get('completed', 0),
                      'calls': len(calls), 'error': receipt.get('error'), 'receipt': str(out / 'acceptance.json')}), flush=True)
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
