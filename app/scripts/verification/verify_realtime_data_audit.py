"""Equivalent bounded projection A/B, environment and actual provider inventory."""
import csv
import importlib.util
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
MOD=BASE/'artifacts/jarvis-audit/modules/26-realtime-data'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module26-pre'


def main():
    from jarvis import realtime_sources as after
    from jarvis.realtime_catalog import CATALOG
    spec=importlib.util.spec_from_file_location('jarvis._sources_before',PRE/'jarvis__realtime_sources.py')
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    data={f'field{i}':{'value':i,'text':'café ગુજરાતી "quoted"'} for i in range(5000)}
    expected=before.compact(data);rows=[]
    for version,module in [('before',before),('after',after)]:
        for sample in range(25):
            tracemalloc.start();start=time.perf_counter_ns();result=module.compact(data)
            elapsed=(time.perf_counter_ns()-start)/1e6;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            assert result==expected and len(result)==40 and len(data)==5000
            rows.append(dict(version=version,sample=sample,phase='initial' if sample<5 else 'warm',milliseconds=elapsed,
                             peak_python_bytes=peak,network_calls=0,notifications=0))
    with (MOD/'benchmarks.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={}
    for version in ('before','after'):
        warm=[r for r in rows if r['version']==version and r['phase']=='warm'];values=sorted(r['milliseconds'] for r in warm)
        summary[version]=dict(p50_ms=statistics.median(values),p95_ms=values[18],peak_python_bytes=max(r['peak_python_bytes'] for r in warm))
    summary.update(equivalent=True,real_external_actions=0,scope='5000-key projection, identical first40 fields;20warm+5initial, not cold process/HTTP/model/RSS/VRAM')
    (MOD/'benchmark-summary.json').write_text(json.dumps(summary,indent=2))
    import psutil
    env=dict(date='2026-10-16 IST',python=sys.version,platform=platform.platform(),ram_bytes=psutil.virtual_memory().total,
             packages={n:metadata.version(n) for n in ('requests','websocket-client','psutil','pytest')})
    (MOD/'environment.json').write_text(json.dumps(env,indent=2))
    inventory=[dict(id=p.key,name=p.name,mode=p.mode,setup=p.requirement,cadence_seconds=p.interval,
                    endpoint=p.url,reference=p.docs,proof='registered endpoint constructed with fixture operands; not live availability') for p in CATALOG.values()]
    assert len(inventory)==82
    (MOD/'provider-inventory.json').write_text(json.dumps(inventory,indent=2))
    print(json.dumps(summary))


if __name__=='__main__':main()
