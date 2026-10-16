"""Safe local normalization A/B, environment census and source freeze. No UI calls."""
import csv
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
OUT = BASE / 'artifacts/jarvis-audit/modules/24-whatsapp'
PRE = BASE / '.jarvis-runtime/jarvis-audit/module24-pre'


def freeze():
    paths = sorted(list((BASE/'jarvis').glob('*.py')) + list((BASE/'tests').glob('test_*.py')))
    data = {p.relative_to(BASE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (OUT/'full-start-source-hashes.json').write_text(json.dumps(data, indent=2))
    print('Frozen', len(data), 'source/test files')


def benchmark():
    from jarvis import whatsapp as after
    spec = importlib.util.spec_from_file_location('jarvis._whatsapp_before', PRE/'jarvis__whatsapp.py')
    before = importlib.util.module_from_spec(spec); spec.loader.exec_module(before)
    texts = [' नमस्ते\tગુજરાતી  français 😀 "quoted"\n' + str(i) for i in range(1000)]
    expected = [before.normalized(s) for s in texts]
    rows = []
    for version, module in [('before', before), ('after', after)]:
        for sample in range(25):
            tracemalloc.start(); start = time.perf_counter_ns()
            result = [module.normalized(s) for s in texts]
            elapsed = (time.perf_counter_ns() - start) / 1e6
            _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
            assert result == expected
            rows.append(dict(version=version, sample=sample, phase='initial' if sample < 5 else 'warm',
                             batch=1000, milliseconds=elapsed, python_peak_bytes=peak, external_actions=0))
    with (OUT/'benchmarks.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary = {}
    for version in ('before', 'after'):
        warm = [r for r in rows if r['version'] == version and r['phase'] == 'warm']
        samples = sorted(r['milliseconds'] for r in warm)
        summary[version] = dict(p50_ms=statistics.median(samples), p95_ms=samples[18],
                               peak_python_bytes=max(r['python_peak_bytes'] for r in warm))
    summary.update(equivalent=True, real_external_actions=0,
                   limitation='Normalization only; initial5 are not cold process starts. No model/GUI/RSS/VRAM latency claim.')
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary, indent=2))
    env = dict(date='2026-10-16 IST', python=sys.version, platform=platform.platform(),
               packages={n: metadata.version(n) for n in ('comtypes', 'pytest', 'requests', 'psutil')})
    import psutil
    env['ram_bytes'] = psutil.virtual_memory().total
    (OUT/'environment.json').write_text(json.dumps(env, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    freeze() if '--freeze' in sys.argv else benchmark()
