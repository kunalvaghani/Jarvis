"""Measure before/after source fingerprint work on identical files and hardware."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/10-dag-planning'


def main():
    import jarvis.hierarchical as after
    from tests.test_hierarchical import tools
    spec=importlib.util.spec_from_file_location('jarvis._dag_before',BASE/'.jarvis-runtime/jarvis-audit/module10-pre/hierarchical.py')
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    # Both algorithms hash the identical current production files; saved code is the baseline algorithm.
    before.__file__=after.__file__
    rows=[];summary={}
    for version,module in [('before',before),('after',after)]:
        for mode,count in [('cold',5),('warm',20)]:
            for index in range(count):
                if mode=='cold' and hasattr(module,'_CODE_HASHES'):module._CODE_HASHES.clear()
                tracemalloc.start();start=time.perf_counter()
                signature=module.fingerprint(tools(),{}, {'files_root':'fixture'})
                elapsed=(time.perf_counter()-start)*1000;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                assert len(signature)==64
                rows.append({'version':version,'mode':mode,'index':index,'ms':elapsed,'peak_python_bytes':peak,'external_side_effects':0})
    for version in ('before','after'):
        for mode in ('cold','warm'):
            sample=[r for r in rows if r['version']==version and r['mode']==mode];values=sorted(r['ms'] for r in sample)
            summary[version+'_'+mode]={'samples':len(values),'p50_ms':statistics.median(values),'p95_ms':values[-1 if len(values)==5 else 18],
                'peak_python_bytes':max(r['peak_python_bytes'] for r in sample)}
    with (OUT/'benchmarks.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/'benchmark-summary.json').write_text(json.dumps({'date':'2026-10-15 IST','scope':'Same-process source-fingerprint component;5 cleared digest-cache (not OS/model cold),20 warm samples/version. Before6 source digests;after8 plus planner labels and metadata invalidation. Both algorithms hash current same files. No tool/network/model dispatch;TTFT/audio/VRAM not applicable;tracemalloc is not whole-host RAM.','results':summary},indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
