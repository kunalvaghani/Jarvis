"""Identical synthetic geographic projection A/B, without feeds or model loads."""
import csv
import hashlib
import importlib.util
import json
from importlib import metadata
from pathlib import Path
import platform
import random
import statistics
import sys
import time
import tracemalloc
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/27-gods-eye'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module27-pre'


def main():
    from jarvis import gods_eye as after
    spec=importlib.util.spec_from_file_location('jarvis._eye_before',PRE/'jarvis__gods_eye.py')
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    rng=random.Random(27)
    points=[(rng.uniform(-85,85),rng.uniform(-180,180)) for _ in range(5000)]+[(.01*i,.01*i) for i in range(10)]
    def old():
        result=[]
        for lat,lon in points:
            km=before.distance(0,0,lat,lon)
            if km<=40:result.append((lat,lon,km))
        return result
    def new():
        result=[]
        for lat,lon in points:
            km=after.nearby_distance(0,0,lat,lon,40)
            if km is not None:result.append((lat,lon,km))
        return result
    expected=old();assert new()==expected
    rows=[]
    for sample in range(25):
        for version,call in (('before',old),('after',new)):
            tracemalloc.start();start=time.perf_counter_ns();result=call()
            elapsed=(time.perf_counter_ns()-start)/1e6;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            assert result==expected
            rows.append(dict(version=version,sample=sample,phase='initial' if sample<5 else 'warm',milliseconds=elapsed,
                peak_python_bytes=peak,network_calls=0,notifications=0))
    with (OUT/'benchmarks.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={}
    for version in ('before','after'):
        warm=[r for r in rows if r['version']==version and r['phase']=='warm'];values=sorted(r['milliseconds'] for r in warm)
        summary[version]=dict(p50_ms=statistics.median(values),p95_ms=values[18],peak_python_bytes=max(r['peak_python_bytes'] for r in warm))
    summary.update(equivalent=True,real_external_actions=0,points=len(points),scope='Exact 40km projection;20 warm+5 initial per version, not cold processes, browser, HTTP, audio, RSS or VRAM')
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary,indent=2))
    import psutil
    env=dict(date='2026-10-16 IST',python=sys.version,platform=platform.platform(),ram_bytes=psutil.virtual_memory().total,
        packages={p:metadata.version(p) for p in ('requests','pytest','psutil')},node='v24.14.0')
    root=BASE/'integrations/gods-eye-view-src/gods-eye-view-main'
    env['bundled']=json.loads((root/'jarvis-gods-eye.json').read_text())
    env['frontend']={p:json.loads((root/'node_modules'/p/'package.json').read_text())['version'] for p in ('cesium','vite')}
    (OUT/'environment.json').write_text(json.dumps(env,indent=2))
    print(json.dumps(summary))


if __name__=='__main__':main()
