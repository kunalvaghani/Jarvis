"""Versioned upgrade-phase baseline over real Jarvis components.

Every measurement drives the actual parser, DAG executor, ToolRegistry, skill
loader and cloud privacy classifier with authored synthetic fixtures. No model,
network, account, microphone or desktop action runs. Numbers describe this
machine at run time; they are not live end-user acceptance measurements.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

SCHEMA_VERSION = 1

# Authored privacy oracle: expected cloud eligibility, independent of the classifier.
PRIVACY_CASES = (
    ('What is the capital of France?', True), ('Explain how photosynthesis works.', True),
    ('Who wrote the novel Pride and Prejudice?', True), ('How does a binary search tree work?', True),
    ('What is the boiling point of water at sea level?', True), ('Explain the theory of general relativity.', True),
    ('Read my latest email from my boss', False), ('What is in my Documents folder?', False),
    ('Summarize the file on my desktop', False), ('Send a WhatsApp message to Mom', False),
    ('My password is hunter2, is it strong?', False), ('What did I say to Rahul yesterday?', False),
    ('Open Chrome and play music', False), ('What is my bank balance?', False),
    ('api_key=sk-abcdefghijklmnopqrstuvwx is this valid?', False), ('Delete the report in my downloads', False),
)


def summary(values):
    values = sorted(values)
    if not values:
        return {'n': 0}
    return {'n': len(values), 'p50': round(statistics.median(values), 4),
            'p95': round(values[int((len(values) - 1) * .95)], 4), 'max': round(values[-1], 4)}


def measured(function):
    """Return (result, peak traced bytes) for one section."""
    tracemalloc.start()
    try:
        result = function()
        return result, tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def rss():
    try:
        import psutil
        return psutil.Process().memory_info().rss
    except Exception as exc:  # Recorded, never estimated.
        return 'unavailable: ' + type(exc).__name__


def intent_routing():
    from jarvis.commands import parse
    from tests.intent_permutations import scenarios
    expected = json.loads((BASE / 'tests/fixtures/intent_testbook_expected.json').read_text(encoding='utf-8'))
    counts, latencies = Counter(), []
    for number, *texts in scenarios():
        for text in texts:
            started = time.perf_counter()
            try:
                actual = parse(text).kind
            except ValueError:
                actual = 'unparsed'
            latencies.append((time.perf_counter() - started) * 1000)
            counts['total'] += 1
            counts['correct'] += actual == expected[number]
    return {'scope': 'authored 800-scenario/2400-phrasing deterministic oracle',
            'correct': counts['correct'], 'total': counts['total'],
            'accuracy': round(counts['correct'] / counts['total'], 6),
            'error_rate': round(1 - counts['correct'] / counts['total'], 6), 'routing_ms': summary(latencies)}


def privacy_routing():
    from jarvis.cloud_policy import classify
    latencies, wrong, leaked = [], [], 0
    for question, public in PRIVACY_CASES:
        started = time.perf_counter()
        eligible = classify({'question': question})['privacy'] == 'PUBLIC'
        latencies.append((time.perf_counter() - started) * 1000)
        if eligible != public:
            wrong.append(question)
            leaked += eligible and not public
    return {'scope': 'authored 16-question oracle; classifier only, no cloud call',
            'cases': len(PRIVACY_CASES), 'correct': len(PRIVACY_CASES) - len(wrong),
            'private_marked_public': leaked, 'misclassified': wrong, 'classify_ms': summary(latencies)}


def dag_execution():
    from jarvis.dag_execution import Executor, Tool, validate_plan
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for index in range(8):
            (root / f'input{index}.txt').write_text(f'value {index}\n', encoding='utf-8')
        writes = []
        lock = threading.Lock()

        def read(arguments, cancelled):
            return (root / arguments['path']).read_text(encoding='utf-8')

        def write(arguments, cancelled):
            with lock:
                writes.append(arguments['path'])
                (root / arguments['path']).write_text(arguments['content'], encoding='utf-8')
            return 'written'

        def slow(arguments, cancelled):
            for _ in range(200):
                if cancelled():
                    raise InterruptedError('cancelled')
                time.sleep(.01)
            return 'slow'

        string = {'type': 'string', 'minLength': 1}
        tools = {
            'read': Tool('read', {'type': 'object', 'properties': {'path': string}, 'required': ['path']}, read,
                         lambda a, out: isinstance(out, str) and out.startswith('value')),
            'write': Tool('write', {'type': 'object', 'properties': {'path': string, 'content': string},
                                    'required': ['path', 'content']}, write,
                          lambda a, out: (root / a['path']).read_text(encoding='utf-8') == a['content'], read_only=False),
            'slow': Tool('slow', {'type': 'object', 'properties': {}}, slow, lambda a, out: out == 'slow'),
        }

        def row(identifier, tool, arguments, dependencies=(), read_only=True):
            return {'id': identifier, 'tool': tool, 'arguments': arguments, 'dependencies': list(dependencies),
                    'expected': 'Deterministic fixture readback.', 'permission': 'read' if read_only else 'user',
                    'resources': {'cpu': 1, 'ram_mb': 32, 'gpu_mb': 0},
                    'retry': {'attempts': 2 if read_only else 1, 'backoff_seconds': .01}, 'timeout_seconds': 5}

        graph = {'version': 1, 'steps': [row(f'r{i}', 'read', {'path': f'input{i}.txt'}) for i in range(8)]
                 + [row('w0', 'write', {'path': 'out.txt', 'content': 'merged'}, [f'r{i}' for i in range(8)], False)]}
        runs, checkpoints = [], []
        for _ in range(20):
            writes.clear()
            (root / 'out.txt').unlink(missing_ok=True)
            steps = validate_plan(graph, tools)
            started = time.perf_counter()
            result = Executor(tools, max_concurrency=3, checkpoint=lambda rows: checkpoints.append(1)).run(steps)
            runs.append({'ms': (time.perf_counter() - started) * 1000, 'status': result['status'],
                         'steps': len(result['steps']), 'writes': len(writes)})
        cancel = threading.Event()
        cancel_graph = {'version': 1, 'steps': [row('s0', 'slow', {}), row('s1', 'slow', {}, ['s0'])]}
        timer = threading.Timer(.1, cancel.set)
        timer.start()
        started = time.perf_counter()
        cancelled = Executor(tools).run(validate_plan(cancel_graph, tools), cancel.is_set)
        cancel_ms = (time.perf_counter() - started) * 1000
        timer.cancel()
        return {'scope': '9-step fixture DAG (8 parallel reads + 1 dependent write) x20; one cancellation run',
                'success_rate': sum(r['status'] == 'completed' for r in runs) / len(runs),
                'steps_per_run': runs[0]['steps'], 'effect_dispatches_per_run': sorted({r['writes'] for r in runs}),
                'checkpoints_per_run': len(checkpoints) / len(runs), 'run_ms': summary([r['ms'] for r in runs]),
                'cancellation': {'status': cancelled['status'], 'requested_after_ms': 100,
                                 'returned_after_ms': round(cancel_ms, 3),
                                 'unstarted_step_status': cancelled['steps']['s1']['status']}}


def tool_registry():
    from jarvis.tools import ToolArgumentError, ToolRegistry
    with tempfile.TemporaryDirectory() as folder:
        actions = SimpleNamespace(base=Path(folder), config={}, allowed_tools=None, skills=None)
        dispatched = []
        actions.execute = lambda command, cancelled: dispatched.append(command)
        actions.report = lambda *args: None
        registry = ToolRegistry(actions)
        catalog_ms, search_ms = [], []
        for _ in range(30):
            started = time.perf_counter()
            catalog = registry.catalog('find the latest python file in my project')
            catalog_ms.append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            registry.search('search github repository code for a bug')
            search_ms.append((time.perf_counter() - started) * 1000)
        malformed = [None, 42, 'task_id', ['task_id'], {}, {'action': 'open'}, {'action': 'open', 'value': ''},
                     {'action': 'open', 'value': 7}, {'action': 'nope', 'value': 'x'},
                     {'action': 'create_file', 'value': 'a.txt'}, {'action': 'realtime_query', 'value': 'x', 'content': '['},
                     {'action': 'open', 'value': 'x' * 5000}]
        outcomes = Counter()
        for step in malformed:
            try:
                registry.execute(step, lambda: False)
                outcomes['accepted'] += 1
            except ToolArgumentError:
                outcomes['ToolArgumentError'] += 1
            except ValueError:
                outcomes['ValueError'] += 1
            except Exception as exc:
                outcomes['unexpected:' + type(exc).__name__] += 1
        return {'scope': 'real ToolRegistry, synthetic actions object; malformed proposals never reach a handler',
                'catalog_size': len(catalog), 'catalog_ms': summary(catalog_ms), 'search_ms': summary(search_ms),
                'malformed_cases': len(malformed), 'malformed_outcomes': dict(outcomes),
                'malformed_dispatched': len(dispatched),
                'contract_error_rate': round(sum(v for k, v in outcomes.items() if k.startswith('unexpected')
                                                 or k == 'accepted') / len(malformed), 6)}


def skills():
    from jarvis.skill_memory import SkillMemory
    with tempfile.TemporaryDirectory() as folder:
        memory = SimpleNamespace(vault=Path(folder), base=Path(folder), enabled=True, hermes_skills_enabled=False)
        started = time.perf_counter()
        loaded = SkillMemory(memory, BASE / 'skills')
        load_ms = (time.perf_counter() - started) * 1000
        latencies, selected = [], []
        for goal in ('play a song on spotify', 'fix the failing unit test in my python project',
                     'fill the login form in chrome', 'research the latest rust release notes') * 5:
            started = time.perf_counter()
            selected.append(len(loaded.context(goal).get('skills', [])))
            latencies.append((time.perf_counter() - started) * 1000)
        return {'scope': 'bundled skills/ with an empty temporary vault; Hermes disabled',
                'bundled_skills_loaded': len(loaded.catalog), 'skill_errors': len(loaded.skill_errors),
                'cold_load_ms': round(load_ms, 3), 'context_ms': summary(latencies),
                'goals_with_selected_skill': sum(1 for count in selected if count), 'goals': len(selected)}


def git_revision():
    try:
        sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=BASE, capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = bool(subprocess.run(['git', 'status', '--porcelain', '--', '.'], cwd=BASE, capture_output=True,
                                    text=True, timeout=30).stdout.strip())
        return {'commit': sha, 'worktree_dirty': dirty}
    except (OSError, subprocess.SubprocessError) as exc:
        return {'commit': 'unavailable: ' + type(exc).__name__}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--overwrite', action='store_true')
    options = parser.parse_args(argv)
    path = Path(options.out)
    if path.exists() and not options.overwrite:
        raise SystemExit('Refusing to overwrite preserved measurements: ' + str(path))
    result = {'schema_version': SCHEMA_VERSION, 'label': options.label,
              'measured_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'git': git_revision(),
              'environment': {'python': sys.version.split()[0], 'platform': platform.platform(),
                              'cpu_count': os.cpu_count()},
              'rss_bytes_start': rss(), 'sections': {}}
    for name, function in (('intent_routing', intent_routing), ('privacy_routing', privacy_routing),
                           ('dag_execution', dag_execution), ('tool_registry', tool_registry), ('skills', skills)):
        started = time.perf_counter()
        try:
            data, peak = measured(function)
            data['status'] = 'MEASURED'
        except Exception as exc:  # A failed section is reported, never replaced by an estimate.
            data, peak = {'status': 'FAILED', 'error': type(exc).__name__ + ': ' + str(exc)[:300]}, None
        data['section_seconds'] = round(time.perf_counter() - started, 4)
        data['peak_traced_bytes'] = peak
        result['sections'][name] = data
    result['rss_bytes_end'] = rss()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({name: {k: v for k, v in data.items() if k in {'status', 'accuracy', 'success_rate', 'correct',
                                                                    'contract_error_rate', 'malformed_outcomes', 'error'}}
                      for name, data in result['sections'].items()}, indent=1))


if __name__ == '__main__':
    main()
