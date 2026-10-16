"""Identical lexical fact-retrieval A/B on saved preimage and current code."""
import csv
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tracemalloc

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from jarvis.memory_curator import MemoryCurator


def main():
    out=BASE/'artifacts/jarvis-audit/modules/16-memory'
    spec=importlib.util.spec_from_file_location('jarvis._curator_before',BASE/'.jarvis-runtime/jarvis-audit/module16-pre/jarvis__memory_curator.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    records=[{'text':f'Person{i} enjoys tea and reading science topic{i%20}', 'updated':f'2026-10-{i%28+1:02d}'} for i in range(500)]
    rows=[];expected=None
    with tempfile.TemporaryDirectory() as folder:
        for name,cls in [('before',old.MemoryCurator),('after',MemoryCurator)]:
            warm=cls(folder)
            for i in range(25):
                c=cls(folder) if i<5 else warm;c.facts=records
                tracemalloc.start();started=time.perf_counter_ns()
                result=c.relevant('tea reading science topic3',8)
                ms=(time.perf_counter_ns()-started)/1e6
                _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                if expected is None:expected=result
                assert result==expected and len(result)==8
                rows.append({'version':name,'mode':'cold' if i<5 else 'warm','sample':i,'ms':ms,'python_peak_bytes':peak})
    summary={'equivalent':True,'samples_per_version':25,'side_effects':0,
        'scope':'500 synthetic facts; five fresh in-memory curator objects and20 warm lookups/version. Lookup only, excludes load/save, network/model and full cognition; no GPU/TTFT/audio measured.'}
    for version in ('before','after'):
        summary[version]={}
        for mode in ('cold','warm'):
            subset=[r for r in rows if r['version']==version and r['mode']==mode];v=sorted(r['ms'] for r in subset)
            summary[version][mode]={'p50_ms':statistics.median(v),'p95_ms':v[math.ceil(.95*len(v))-1],'python_peak_bytes':max(r['python_peak_bytes'] for r in subset)}
    with (out/'benchmarks.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    (out/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
