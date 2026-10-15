"""Paired, owned-fixture module 02 benchmark; never loads a model or action."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import psutil

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / 'artifacts/jarvis-audit/modules/02-perception-cognition'
PRE = BASE / '.jarvis-runtime/jarvis-audit/module02-pre/cognition.py'


def load(mode):
    path = PRE if mode == 'before' else BASE / 'jarvis/cognition.py'
    spec = importlib.util.spec_from_file_location('fixture_cognition_' + mode, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Cognition


def request(cls, root):
    actions = SimpleNamespace(base=root, current_item=None, whatsapp_prompts=[],
        pending_tasks=[], session_style={}, approvals_waiting=0, memory=None)
    mind = cls(actions)
    for i in range(200):
        mind.perceive('fixture', 'sensor', str(i), ((i * 73) % 101) / 100)
        mind.percepts[-1].at = 1000 + i
    # Identical deterministic ranking oracle; monkeypatch module clock for both builds.
    # Loaded modules are not registered: use method globals instead.
    clock = mind.update_workspace.__func__.__globals__['time']
    original = clock.time
    try:
        clock.time = lambda: 1200.
        start = time.perf_counter()
        for _ in range(100):
            mind.tick()
        milliseconds = (time.perf_counter() - start) * 10  # per tick, ms
        expected = sorted(mind.percepts, key=lambda p: (p.weight(1200.), p.at), reverse=True)[:7]
        assert [p.content for p in mind.attention] == [p.content for p in expected]
    finally:
        clock.time = original
    return milliseconds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cold', choices=['before', 'after'])
    args = parser.parse_args()
    if args.cold:
        started = time.perf_counter()
        cls = load(args.cold)
        with tempfile.TemporaryDirectory() as root:
            value = request(cls, Path(root))
        print(json.dumps({'startup_ms': (time.perf_counter()-started)*1000,
            'tick_ms': value, 'rss_bytes': psutil.Process().memory_info().rss}))
        return
    rows = []
    classes = {mode: load(mode) for mode in ('before', 'after')}
    with tempfile.TemporaryDirectory() as root:
        for mode in classes:
            request(classes[mode], Path(root))  # prime SciPy, same process
        for sample in range(20):
            for mode in (('before', 'after') if sample % 2 == 0 else ('after', 'before')):
                value = request(classes[mode], Path(root))
                rows.append(dict(mode=mode, kind='warm_tick', sample=sample, milliseconds=value,
                    rss_bytes=psutil.Process().memory_info().rss))
    for sample in range(5):
        for mode in ('before', 'after'):
            result = subprocess.run([sys.executable, __file__, '--cold', mode], cwd=BASE,
                capture_output=True, text=True, check=True, timeout=30)
            data = json.loads(result.stdout)
            rows.append(dict(mode=mode, kind='cold_startup', sample=sample,
                milliseconds=data['startup_ms'], rss_bytes=data['rss_bytes']))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT/'benchmarks.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    summary = {'date': '2026-10-15 IST', 'scope': '200 synthetic percepts; 100 ticks per warm sample, periodic workspace refresh; 20 alternating warm samples/build and 5 fresh-process cold samples/build. No model, network, GUI or GPU allocations. TTFT/audio N/A. RSS sampled, not peak.',
        'source_sha256': {mode: hashlib.sha256((PRE if mode=='before' else BASE/'jarvis/cognition.py').read_bytes()).hexdigest() for mode in classes}}
    for mode in classes:
        for kind in ('warm_tick', 'cold_startup'):
            values = sorted(r['milliseconds'] for r in rows if r['mode']==mode and r['kind']==kind)
            summary[mode+'_'+kind] = dict(p50_ms=statistics.median(values), p95_ms=values[int(.95*(len(values)-1))], samples=len(values))
    with tempfile.TemporaryDirectory() as root:
        for mode, cls in classes.items():
            actions = SimpleNamespace(base=Path(root)/mode, current_item=None, whatsapp_prompts=[],
                pending_tasks=[], session_style={}, approvals_waiting=0, memory=None)
            mind = cls(actions)
            samples = []
            tick = mind.tick
            def measured_tick():
                samples.append(time.monotonic())
                tick()
            mind.tick = measured_tick
            mind.write_state = lambda: time.sleep(.18)  # identical disk-delay fault
            mind.start()
            try:
                for i in range(32):
                    mind.perceive('fixture', 'sensor', str(i))
                    time.sleep(.1)
            finally:
                mind.close()
            intervals = sorted((b-a)*1000 for a,b in zip(samples,samples[1:]))
            assert len(intervals) >= 9
            summary[mode+'_schedule'] = dict(samples=len(intervals), p50_ms=statistics.median(intervals),
                p95_ms=intervals[int(.95*(len(intervals)-1))], max_ms=max(intervals))
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
