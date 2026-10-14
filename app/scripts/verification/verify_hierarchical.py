"""Repeatable original/upgraded benchmarks; authored plans, real local file tools.

No microphone, user desktop mutation, network search or model quality claim.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import psutil

BASE = Path(__file__).resolve().parents[2]


def inventory():
    rows = []
    for folder in ('jarvis', 'scripts', 'tests'):
        for path in sorted((BASE/folder).rglob('*.py')):
            if '__pycache__' in path.parts:
                continue
            raw = path.read_bytes()
            try:
                tree = ast.parse(raw)
                rows.append({'path': path.relative_to(BASE).as_posix(),
                    'sha256': hashlib.sha256(raw).hexdigest(), 'lines': len(raw.splitlines()),
                    'classes': [n.name for n in tree.body if isinstance(n, ast.ClassDef)],
                    'functions': [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
                    'imports': sorted({n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} |
                                      {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})})
            except (SyntaxError, UnicodeError) as exc:
                rows.append({'path': str(path.relative_to(BASE)), 'parse_error': str(exc)})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['baseline', 'upgraded'], required=True)
    args = parser.parse_args()
    from jarvis.commands import parse
    from jarvis.tools import ToolRegistry
    from scripts.verification.verify_plan_execution import fixture, scenario
    samples = []
    labels = [('open Chrome', 'open_app'), ('open VS Code', 'open_app'),
              ('stop all tasks', 'cancel_tasks'), ('what is my battery level', 'question'),
              ('show CPU usage', 'question'), ('read my notes', 'read_file')]
    def route(text):
        try:
            return parse(text).kind
        except ValueError:
            return 'unparsed'
    classified = []
    for text, _ in labels:
        classified.append({'input': text, 'actual_kind': route(text)})
    for _ in range(100):
        start = time.perf_counter()
        for text, _ in labels:
            route(text)
        samples.append((time.perf_counter()-start)*1000/len(labels))
    started = time.perf_counter()
    startup = subprocess.run([sys.executable, '-c', 'import jarvis.actions,jarvis.brain,jarvis.commands'],
                             cwd=BASE, capture_output=True, timeout=60)
    import_seconds = time.perf_counter()-started
    scratch = BASE/'.jarvis-runtime/hierarchical-benchmark'/str(time.time_ns())
    scratch.mkdir(parents=True)
    workflows = [fixture(scratch/str(i), scenario(0, 5)) for i in range(3)]
    recovery = [fixture(scratch/'fault', scenario(1, 3), fault_after=1),
                fixture(scratch/'cancel', scenario(2, 3), cancel_after=1)]
    from jarvis.actions import Actions
    root = scratch/'reads'
    root.mkdir()
    for i in range(3):
        (root/f'{i}.txt').write_text(f'Fixture {i}: verified local content.', encoding='utf-8')
    actions = Actions({'files_root': 'managed', 'apps': {}, '_ui_verification': True,
        'memory': {'enabled': False}, 'brain': {'enabled': False}}, root, lambda *_: None)
    actions.allowed_tools = {'read_file'}
    actions._task_folder = lambda folder, cancelled: root if folder == 'this folder' else None
    registry = ToolRegistry(actions)
    def read(index):
        time.sleep(.1)  # Explicit controlled I/O delay, not an external-service measurement.
        return registry.execute({'action': 'read_file', 'value': f'{index}.txt',
            'folder': 'this folder', 'expected': 'Read fixture', 'content': ''}, lambda: False).evidence
    parallel = []
    try:
        for trial in range(5):
            start = time.perf_counter()
            if args.mode == 'baseline':
                results = [read(i) for i in range(3)]
            else:
                from jarvis.dag_execution import Executor, Tool, validate_plan
                tools = {'read': Tool('read', {'type': 'object', 'additionalProperties': False,
                    'required': ['index'], 'properties': {'index': {'type': 'integer'}}},
                    lambda arguments, cancelled: {'text': read(arguments['index'])},
                    lambda arguments, result: result['text'] == f"Fixture {arguments['index']}: verified local content.")}
                graph = {'version': 1, 'steps': [{'id': f's{i}', 'tool': 'read', 'arguments': {'index': i},
                    'dependencies': [], 'expected': 'Read fixture', 'permission': 'read',
                    'resources': {'cpu': 1, 'ram_mb': 32, 'gpu_mb': 0},
                    'retry': {'attempts': 1, 'backoff_seconds': .01}, 'timeout_seconds': 2} for i in range(3)]}
                result = Executor(tools, max_concurrency=3).run(validate_plan(graph, tools))
                results = [result['steps'][f's{i}']['result']['text'] for i in range(3)]
            parallel.append({'seconds': time.perf_counter()-start,
                'correct': results == [f'Fixture {i}: verified local content.' for i in range(3)]})
    finally:
        actions.close()
    process = psutil.Process()
    memory = process.memory_info()
    result = {'date': datetime.now(timezone.utc).isoformat(), 'mode': args.mode,
        'scope': 'Process import timing; deterministic parser; authored real-file workflows through Brain; controlled-delay real ToolRegistry reads. Not full UI startup, acoustic latency, live planner reasoning or external actions.',
        'production_source_inventory': inventory(),
        'routing_median_ms': statistics.median(samples), 'routing_p95_ms': sorted(samples)[94],
        'routing_labels': classified, 'process_import_seconds': import_seconds,
        'process_import_exit_code': startup.returncode, 'workflows': workflows, 'recovery': recovery,
        'parallel_trials': parallel, 'parallel_median_seconds': statistics.median(r['seconds'] for r in parallel),
        'rss_mb_at_end': memory.rss/1048576, 'peak_working_set_mb': getattr(memory, 'peak_wset', 0)/1048576,
        'cpu_times': process.cpu_times()._asdict(), 'gpu_utilization': 'Not measured',
        'peak_vram': 'Not measured', 'microphone_to_speaker_latency': 'Not measured',
        'model_first_token': 'Not measured', 'power_impact': 'Not measured'}
    target = BASE/'artifacts/reports'/f'hierarchical-{args.mode}.json'
    if target.exists():
        raise ValueError('Preserve historical baseline/results; choose an explicit archival move before rerunning.')
    target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in {'production_source_inventory', 'workflows', 'recovery'}}, indent=2))


if __name__ == '__main__':
    main()
