"""Paired baseline/candidate microbenchmarks; no inference, GUI or user data."""
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
OUT = BASE / 'artifacts/jarvis-audit/codex-independent-review'
PIN = '36fbf3ce925080f7f54afa87eaf1d9b88414142d'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def describe(values):
    ordered = sorted(values)
    return {'n': len(values), 'median_ms': statistics.median(values),
            'p95_ms': ordered[int(.95 * (len(values) - 1))],
            'min_ms': ordered[0], 'max_ms': ordered[-1], 'stdev_ms': statistics.stdev(values)}


def main():
    result = {'date': '2026-10-19 IST', 'baseline_commit': PIN,
              'scope': 'Paired synthetic microbenchmarks, warm imports; no end-user latency claim.', 'measurements': {}}
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        modules = {}
        for label in ('baseline', 'candidate'):
            modules[label] = {}
            for key, relative in [('state', 'jarvis/demonstration.py'), ('lease', 'scripts/training/train_azr_lora.py')]:
                path = root / (label + key + '.py')
                raw = (subprocess.run(['git', 'show', PIN + ':app/' + relative], cwd=BASE, capture_output=True,
                                      check=True).stdout if label == 'baseline' else (BASE / relative).read_bytes())
                path.write_bytes(raw)
                modules[label][key] = load(label + key, path)
                modules[label][key].BASE = root
        children = [SimpleNamespace(element_info=SimpleNamespace(control_type='Text', name='Public status',
                                  element=SimpleNamespace(CurrentIsPassword=False))) for _ in range(200)]
        window = SimpleNamespace(descendants=lambda: children, window_text=lambda: 'Synthetic fixture')
        state_path = root / '.jarvis-runtime/gpu/state.json'
        state_path.parent.mkdir(parents=True)
        state_path.write_text('{"active":null,"pending":[]}', encoding='utf-8')
        for scenario in ('state_200_public_elements', 'empty_lease_read'):
            values = {'baseline': [], 'candidate': []}
            for index in range(501):
                # Alternate execution order to reduce ordering bias. First pair is cold-call evidence.
                for label in (('baseline', 'candidate') if index % 2 else ('candidate', 'baseline')):
                    function = (lambda: modules[label]['state'].window_state(window)) if scenario.startswith('state') else modules[label]['lease'].foreground_gpu_busy
                    started = time.perf_counter()
                    function()
                    elapsed = (time.perf_counter() - started) * 1000
                    if index == 0:
                        result.setdefault('first_call_ms', {}).setdefault(scenario, {})[label] = elapsed
                    else:
                        values[label].append(elapsed)
            summaries = {label: describe(v) for label, v in values.items()}
            delta = summaries['candidate']['median_ms'] - summaries['baseline']['median_ms']
            result['measurements'][scenario] = {**summaries, 'absolute_delta_ms': delta,
                'relative_delta_percent': 100 * delta / summaries['baseline']['median_ms']}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'paired-benchmarks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
