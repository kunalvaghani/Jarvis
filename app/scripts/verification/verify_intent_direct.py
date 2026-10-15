"""Pair captured/current deterministic parsers without altering the checkout."""
import csv
import importlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from types import ModuleType
import psutil

BASE = Path(__file__).resolve().parents[2]
OUT = BASE/'artifacts/jarvis-audit/modules/03-intent-direct'
PRE = BASE/'.jarvis-runtime/jarvis-audit/module03-pre'
PHRASES = ('open Chrome', 'pause', 'volume up', 'Could you bring up Chrome for me?',
    'Please do not open Chrome', 'Open the Chrome downloads folder', 'Open my latest spreadsheet',
    'Turn the sound down a notch', "Pause what's playing", 'I said close the tab, not the browser',
    'open VS Code', 'Set volume to 150 percent')


def parser(mode):
    name = 'audit03_' + mode
    package = ModuleType(name)
    package.__path__ = ([str(PRE)] if mode == 'before' else []) + [str(BASE/'jarvis')]
    sys.modules[name] = package
    return importlib.import_module(name+'.commands').parse


def batch(parse):
    result = []
    started = time.perf_counter()
    for phrase in PHRASES:
        try:
            result.append(vars(parse(phrase)))
        except ValueError:
            result.append({'kind': 'rejected'})
    assert len(result) == len(PHRASES)
    assert result[0]['kind'] == 'open' and result[1]['kind'] == 'click_control'
    assert result[4]['kind'] == 'rejected'  # negation
    return (time.perf_counter()-started)*1000/len(PHRASES), result


def main():
    if len(sys.argv) > 1:
        started = time.perf_counter()
        latency, result = batch(parser(sys.argv[1]))
        print(json.dumps({'milliseconds': (time.perf_counter()-started)*1000,
            'rss_bytes': psutil.Process().memory_info().rss, 'routes': result}))
        return
    parsers = {mode: parser(mode) for mode in ('before','after')}
    routes = {}
    for mode, parse in parsers.items():
        _, routes[mode] = batch(parse)
    rows = []
    for sample in range(20):
        for mode in (('before','after') if sample%2==0 else ('after','before')):
            milliseconds, _ = batch(parsers[mode])
            rows.append(dict(mode=mode, kind='warm_per_phrase', sample=sample,
                milliseconds=milliseconds, rss_bytes=psutil.Process().memory_info().rss))
    for sample in range(5):
        for mode in ('before','after'):
            process = subprocess.run([sys.executable, __file__, mode], cwd=BASE,
                text=True, capture_output=True, check=True, timeout=30)
            result = json.loads(process.stdout)
            rows.append(dict(mode=mode, kind='cold_import_and_batch', sample=sample,
                milliseconds=result['milliseconds'], rss_bytes=result['rss_bytes']))
    with (OUT/'benchmarks.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    summary = {'date':'2026-10-15 IST', 'scope':'12 fixed parser-only phrases, 20 alternating warm batches and 5 fresh subprocess imports/batches per build. No launches, models, network requests or GPU allocations. RSS sampled; not peak. TTFT/audio N/A.', 'routes':routes}
    for mode in parsers:
        for kind in ('warm_per_phrase','cold_import_and_batch'):
            values = sorted(r['milliseconds'] for r in rows if r['mode']==mode and r['kind']==kind)
            summary[mode+'_'+kind] = dict(p50_ms=statistics.median(values), p95_ms=values[int(.95*(len(values)-1))])
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key:value for key,value in summary.items() if key!='routes'}, indent=2))


if __name__ == '__main__':
    main()
