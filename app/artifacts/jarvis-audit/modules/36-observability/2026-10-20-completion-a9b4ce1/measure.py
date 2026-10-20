"""Raw paired synthetic measurements, corrected pinned probes and owned trace readback."""
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace, ModuleType
from unittest.mock import Mock, patch

import psutil

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
sys.path.insert(0, str(APP))
PIN = '36fbf3ce925080f7f54afa87eaf1d9b88414142d'
BASE = 'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6'

def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def git_source(revision, name):
    return subprocess.check_output(['git', 'show', revision + ':app/' + name], cwd=APP)

def load(name, raw, folder, package=None):
    path = folder / (name.rsplit('.', 1)[-1] + '.py')
    path.write_bytes(raw)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if package: module.__package__ = package
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

dump('host-profile.json', {'date': '2026-10-20', 'python': platform.python_version(), 'python_build': platform.python_build(),
     'os': platform.platform(), 'machine': platform.machine(), 'processor': platform.processor(),
     'logical_cpus': psutil.cpu_count(), 'ram_total_bytes': psutil.virtual_memory().total,
     'available_ram_before_bytes': psutil.virtual_memory().available, 'cpu_percent_before': psutil.cpu_percent(.1),
     'pressure': 'Concurrent regression activity; serial within each randomized pair; one host/session, not independent populations.',
     'seed': 36, 'timing_unit': 'milliseconds from perf_counter_ns', 'private_roots': 'omitted'})

raw_rows, summaries = [], {}
with tempfile.TemporaryDirectory(prefix='jarvis-observability-') as folder:
    root = Path(folder)
    modules = {}
    hashes = {}
    for variant in ['baseline', 'candidate']:
        modules[variant] = {}
        for key, name in [('state', 'jarvis/demonstration.py'), ('lease', 'scripts/training/train_azr_lora.py')]:
            raw = git_source(PIN, name) if variant == 'baseline' else (APP / name).read_bytes()
            hashes[variant + ':' + name] = hashlib.sha256(raw).hexdigest()
            module = load(variant + key, raw, root)
            module.BASE = root
            modules[variant][key] = module
    children = [SimpleNamespace(element_info=SimpleNamespace(control_type='Text', name='Public status',
                      element=SimpleNamespace(CurrentIsPassword=False))) for _ in range(200)]
    window = SimpleNamespace(descendants=lambda: children, window_text=lambda: 'Synthetic fixture')
    state = root / '.jarvis-runtime/gpu/state.json'
    state.parent.mkdir(parents=True)
    state.write_text('{"active":null,"pending":[]}', encoding='utf-8')
    rng = random.Random(36)
    for scenario in ['state_200_public_elements', 'empty_lease_read']:
        paired = []
        values = {'baseline': [], 'candidate': []}
        first = {}
        for index in range(501):
            order = ['baseline', 'candidate']; rng.shuffle(order)
            pair = {}
            for position, variant in enumerate(order):
                function = ((lambda v=variant: modules[v]['state'].window_state(window)) if scenario.startswith('state')
                            else modules[variant]['lease'].foreground_gpu_busy)
                started = time.perf_counter_ns(); result = function(); elapsed = (time.perf_counter_ns() - started) / 1e6
                assert (result['title'] == 'Synthetic fixture') if scenario.startswith('state') else result is False
                raw_rows.append({'scenario': scenario, 'sample': index, 'phase': 'first_call' if index == 0 else 'warm',
                                 'order': position, 'variant': variant, 'revision': PIN if variant == 'baseline' else BASE + '+local patches',
                                 'duration_ms': elapsed, 'outcome': 'PASS', 'real_external_side_effects': 0})
                pair[variant] = elapsed
                if index: values[variant].append(elapsed)
                else: first[variant] = elapsed
            if index: paired.append(pair['candidate'] - pair['baseline'])
        stats = {}
        for variant, samples in values.items():
            ordered = sorted(samples)
            stats[variant] = {'n': len(samples), 'p50_ms': statistics.median(samples), 'p95_ms': ordered[474],
                              'mean_ms': statistics.mean(samples), 'stdev_ms': statistics.stdev(samples),
                              'variance_ms2': statistics.variance(samples), 'min_ms': min(samples), 'max_ms': max(samples)}
        delta = statistics.mean(paired); margin = 1.96 * statistics.stdev(paired) / math.sqrt(len(paired))
        summaries[scenario] = {'statistics': stats, 'first_call_ms': first,
                              'paired_mean_delta_ms': delta, 'paired_mean_ci95_normal_approx_ms': [delta-margin, delta+margin],
                              'limitations': 'Serial correlated synthetic samples. CI approximates paired mean, not median/p95 or real task latency.'}
    dump('benchmark-provenance.json', {'baseline': PIN, 'candidate_base': BASE, 'source_hashes': hashes,
         'pairs_per_scenario': 500, 'first_pair_separate': True, 'order_seed': 36,
         'scope': 'Synthetic UIA objects / empty GPU lease file only; no COM, microphone, model, inference, startup or throughput.',
         'historical_raw_N500': 'NOT FOUND: original script saved aggregates only; fresh raw CSV is not the historical raw samples.'})
    dump('benchmark-summary.json', summaries)

    # Corrected pre-P36 executor probes (valid toolkit folder). Old event source is unchanged from base through P35.
    old_events = load('jarvis.audit_prior_events', git_source(BASE, 'jarvis/agent_events.py'), root, 'jarvis')
    old_tools = load('jarvis.audit_prior_tools', git_source(BASE, 'jarvis/tools.py'), root, 'jarvis')
    with patch.dict(sys.modules, {'jarvis.agent_events': old_events}):
        old_root = root / 'old-trace'
        old_root.mkdir()
        actions = SimpleNamespace(base=old_root, allowed_tools={'read_file'})
        registry = old_tools.ToolRegistry(actions)
        registry._execute = Mock(return_value=old_tools.ToolResult('read_file', 'files', 'fixture'))
        for _ in range(5):
            registry.execute({'action': 'read_file', 'value': 'fixture', 'folder': str(root)}, lambda: False)
        rows = [json.loads(s) for s in (old_root / '.jarvis-runtime/agent-events.jsonl').read_text().splitlines()]
        proof = {'source': BASE, 'valid_folder_argument': True, 'five_calls': len({r['call_id'] for r in rows}),
                 'task_field_present': any('task_id' in r for r in rows), 'monotonic_field_present': any('monotonic_ns' in r for r in rows)}
        actual_open = Path.open
        def no_journal(path, *args, **kwargs):
            if path.name == 'agent-events.jsonl': raise PermissionError('synthetic locked journal')
            return actual_open(path, *args, **kwargs)
        with patch.object(Path, 'open', no_journal):
            before_count = registry._execute.call_count
            try:
                registry.execute({'action': 'read_file', 'value': 'fixture', 'folder': str(root)}, lambda: False)
            except PermissionError:
                proof['logging_error_blocks_dispatch'] = registry._execute.call_count == before_count
            else: proof['logging_error_blocks_dispatch'] = False
        dump('corrected-pinned-boundary-readback.json', proof)

    # Actual current registry + TaskState, with five mocked read-only dispatches; clocks and joins are real.
    from jarvis.task_state import TaskState
    from jarvis.tools import ToolRegistry, ToolResult
    trace_root = root / 'current-trace'
    task = TaskState(trace_root); task_id = task.start('Synthetic trace fixture', 'task')
    actions = SimpleNamespace(base=trace_root, task_state=task, allowed_tools={'read_file'})
    registry = ToolRegistry(actions)
    registry._execute = Mock(return_value=ToolResult('read_file', 'files', 'fixture'))
    for _ in range(5): registry.execute({'action': 'read_file', 'value': 'fixture', 'folder': str(root)}, lambda: False)
    rows = [json.loads(s) for s in (trace_root / '.jarvis-runtime/agent-events.jsonl').read_text().splitlines()]
    assert len({r['call_id'] for r in rows}) == 5 and {r['task_id'] for r in rows} == {task_id}
    (OUT / 'trace-readback.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')

    from jarvis.reasoning_bank import ReasoningBank
    bank = ReasoningBank(root / 'memory', embedder=lambda texts, kind='document': None)
    size_before = bank.path.stat().st_size
    started = time.perf_counter()
    ids = set()
    for index in range(100):
        result = bank.learn({'task_id': 'fixture-' + str(index), 'status': 'failed', 'verification': [],
                            'conditions': {'application': 'fixture'},
                            'steps': [{'action': 'read_file', 'error': 'fixture failure attempt ' + str(1000 + index)}]})
        ids.update(result['items'])
    elapsed = time.perf_counter() - started
    assert len(bank.items()) == len(ids) == 1
    dump('memory-growth-readback.json', {'case': 'JRV-36-018', 'trajectories': 100, 'unique_items': 1,
         'synthetic_near_duplicate_numbers_normalized': True, 'db_bytes_before': size_before,
         'db_bytes_after': bank.path.stat().st_size, 'elapsed_seconds': elapsed,
         'limitation': 'Does not establish general semantic novelty detection or unlimited storage retention.'})

with (OUT / 'raw-samples.csv').open('w', newline='', encoding='utf-8') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(raw_rows[0])); writer.writeheader(); writer.writerows(raw_rows)
with (OUT / 'benchmarks.csv').open('w', newline='', encoding='utf-8') as handle:
    fields = ['scenario', 'variant', 'n', 'p50_ms', 'p95_ms', 'mean_ms', 'stdev_ms', 'variance_ms2', 'min_ms', 'max_ms']
    writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
    for scenario, summary in summaries.items():
        for variant, stats in summary['statistics'].items(): writer.writerow({'scenario': scenario, 'variant': variant, **stats})
print(json.dumps({'raw_samples': len(raw_rows), 'paired_synthetic_scenarios': 2, 'trace_calls': 5, 'memory_unique_items': 1}))
