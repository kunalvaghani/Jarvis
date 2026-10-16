"""Equivalent bounded next-job selection A/B; no learning/network/model execution."""
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
from types import SimpleNamespace

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
from jarvis.self_evolution import SelfEvolution


def main():
    spec=importlib.util.spec_from_file_location('jarvis._evolution_before',BASE/'.jarvis-runtime/jarvis-audit/module20-pre/jarvis__self_evolution.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    backlog=[{'signature':str(i),'status':'pending' if i%3 else 'learned','score':(i*17)%101,'created':str(i%19),'attempts':0} for i in range(1000)]
    rows=[];expected=None
    with tempfile.TemporaryDirectory() as tmp:
        for label,cls in [('before',old.SelfEvolution),('after',SelfEvolution)]:
            warm=cls(SimpleNamespace(base=tmp),{'max_backlog':1000});warm.backlog=backlog
            for i in range(25):
                obj=cls(SimpleNamespace(base=tmp),{'max_backlog':1000}) if i<5 else warm
                obj.backlog=backlog
                tracemalloc.start();start=time.perf_counter_ns();result=obj.next_job();ms=(time.perf_counter_ns()-start)/1e6
                _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                if expected is None:expected=result['signature']
                assert result['signature']==expected
                rows.append({'version':label,'mode':'cold' if i<5 else 'warm','sample':i,'ms':ms,'python_peak_bytes':peak})
    out=BASE/'artifacts/jarvis-audit/modules/20-self-evolution'
    with (out/'benchmarks.csv').open('w',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    summary={'equivalent':True,'samples_per_version':25,'items':1000,'external_effects':0,
      'scope':'Same eligible1000-item backlog; exact chosen signature/tie order.5 newly constructed instances/20 warm selections per implementation; construction/imports/I/O excluded from timed section. No network, inference, audio, GPU or native energy/throughput claim.'}
    for label in ('before','after'):
        summary[label]={}
        for mode in ('cold','warm'):
            selected=[r for r in rows if r['version']==label and r['mode']==mode];values=sorted(r['ms'] for r in selected)
            summary[label][mode]={'p50_ms':statistics.median(values),'p95_ms':values[math.ceil(.95*len(values))-1],
                                  'python_peak_bytes':max(r['python_peak_bytes'] for r in selected)}
    (out/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
