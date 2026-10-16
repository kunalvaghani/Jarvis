"""Equivalent warm selection fixture A/B; no player, network or global query cache."""
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
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
MOD=BASE/'artifacts/jarvis-audit/modules/25-media'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module25-pre'


def main():
    from jarvis import media_player as after
    spec=importlib.util.spec_from_file_location('jarvis._media_before', PRE/'jarvis__media_player.py')
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    rows=[dict(title='Background Recording '+str(n), artists='Other Singer',kind='Song') for n in range(30)]
    rows.insert(5,dict(title='Nadaan Parinde',artists='A.R. Rahman',kind='Song'))
    samples=[]
    for version,module in [('before',before),('after',after)]:
        for n in range(25):
            tracemalloc.start();start=time.perf_counter_ns()
            selected=module.choose_spotify('nadan parinde', rows)
            elapsed=(time.perf_counter_ns()-start)/1e6
            _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            assert selected is rows[5]
            samples.append(dict(version=version,sample=n,phase='initial' if n<5 else 'warm',milliseconds=elapsed,
                                python_peak_bytes=peak,external_actions=0))
    with (MOD/'benchmarks.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
    summary={}
    for version in ('before','after'):
        warm=[r for r in samples if r['version']==version and r['phase']=='warm']
        values=sorted(r['milliseconds'] for r in warm)
        summary[version]=dict(p50_ms=statistics.median(values),p95_ms=values[18],peak_python_bytes=max(r['python_peak_bytes'] for r in warm))
    summary.update(equivalent=True,real_external_actions=0,scope='31-row unambiguous selection;20warm+5initial/version, not cold-process/GUI/RSS/VRAM')
    (MOD/'benchmark-summary.json').write_text(json.dumps(summary,indent=2))
    import psutil
    env=dict(date='2026-10-16 IST',python=sys.version,platform=platform.platform(),ram_bytes=psutil.virtual_memory().total,
             packages={n:metadata.version(n) for n in ('winrt-Windows.Media.Control','winrt-runtime','pycaw','comtypes','playwright','pytest')})
    (MOD/'environment.json').write_text(json.dumps(env,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
