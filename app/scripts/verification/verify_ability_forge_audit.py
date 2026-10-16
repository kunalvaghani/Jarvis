"""Bounded before/after static rejection benchmark; no generated code execution."""
import csv
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from jarvis import repo_abilities
from tests.test_repo_abilities import GOOD, SPEC


def main():
    spec = importlib.util.spec_from_file_location('jarvis._forge_before', BASE/'.jarvis-runtime/jarvis-audit/module19-pre/jarvis__repo_abilities.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    payload = '#'+'x'*400000+'\n'+GOOD
    expected = old.check_code(payload, SPEC)
    assert expected == repo_abilities.check_code(payload, SPEC)
    assert old.check_code(GOOD, SPEC) == repo_abilities.check_code(GOOD, SPEC) == []
    rows = []
    for label, module in [('before', old), ('after', repo_abilities)]:
        for i in range(25):
            tracemalloc.start()
            start = time.perf_counter_ns()
            value = module.check_code(payload, SPEC)
            ms = (time.perf_counter_ns()-start)/1e6
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            assert value == expected
            rows.append({'version': label, 'mode': 'cold' if i<5 else 'warm', 'sample': i,
                         'ms': ms, 'python_peak_bytes': peak})
    out = BASE/'artifacts/jarvis-audit/modules/19-ability-forge'
    with (out/'benchmarks.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    summary = {'equivalent': True, 'samples_per_version': 25, 'external_effects': 0,
               'scope': 'Static rejection of identical 400 KB comment plus valid owned utility. Five initial cold calls and20 subsequent warm calls/version, not fresh Python processes; imports and fixture allocation excluded. Same rejection and valid-source acceptance. No inference/audio/GPU/build throughput claim; TTFT/TTFA/VRAM not applicable.'}
    for label in ('before', 'after'):
        summary[label] = {}
        for mode in ('cold', 'warm'):
            selected = [r for r in rows if r['version']==label and r['mode']==mode]
            values = sorted(r['ms'] for r in selected)
            summary[label][mode] = {'p50_ms': statistics.median(values), 'p95_ms': values[math.ceil(.95*len(values))-1],
                                    'python_peak_bytes': max(r['python_peak_bytes'] for r in selected)}
    (out/'benchmark-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
