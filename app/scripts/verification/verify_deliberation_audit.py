"""Identical ledger fixtures, saved preimage versus current policy implementation."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tracemalloc
from types import SimpleNamespace

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/09-deliberation'


def main():
    from jarvis import deliberation as after
    spec=importlib.util.spec_from_file_location('jarvis._deliberation_before',BASE/'.jarvis-runtime/jarvis-audit/module09-pre/deliberation.py')
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    samples=[];summary={}
    opinion={'goal':'read fixture','recommendation':'read','confidence':.7,'risk':'low','source':'heuristic'}
    with tempfile.TemporaryDirectory() as folder:
        for version,module in [('before',before),('after',after)]:
            actions=SimpleNamespace(base=Path(folder)/version)
            engine=module.Deliberation(actions,{'ledger_max':500})
            engine.ledger_path.parent.mkdir(parents=True)
            seed=json.dumps({'id':'seed','goal':'read fixture','outcome':None})+'\n'
            engine.ledger_path.write_text(seed*500,encoding='utf-8')
            for mode,count in [('cold',5),('warm',20)]:
                for index in range(count):
                    if mode=='cold':engine=module.Deliberation(actions,{'ledger_max':500})
                    tracemalloc.start();start=time.perf_counter()
                    did=engine.record(opinion,{},'read','none')
                    elapsed=(time.perf_counter()-start)*1000
                    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                    rows=engine.decisions(500)
                    assert len(rows)==500 and rows[-1]['id']==did and engine.ledger_path.is_file()
                    samples.append({'version':version,'mode':mode,'index':index,'ms':elapsed,'peak_python_bytes':peak,'side_effects':0})
            # An isolated 100-record soak checks bounded retention, not external writes.
            for _ in range(100):engine.record(opinion,{},'read','none')
            assert len(engine.decisions(1000))==500
            summary[version]={'retained_decisions':500,'in_memory_id_cache':len(getattr(engine,'_by_id',{}))}
    with (OUT/'benchmarks.csv').open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
    for version in ('before','after'):
        for mode in ('cold','warm'):
            rows=[r for r in samples if r['version']==version and r['mode']==mode];values=sorted(r['ms'] for r in rows)
            summary[version+'_'+mode]={'samples':len(values),'p50_ms':statistics.median(values),'p95_ms':values[math_ceil(.95*len(values))-1],
                'peak_python_bytes':max(r['peak_python_bytes'] for r in rows)}
    (OUT/'benchmark-summary.json').write_text(json.dumps({'date':'2026-10-15 IST','scope':'Same machine,500-row isolated rotating ledger; cold means new Deliberation instance, not OS/model cold. No GPU/model/audio work; TTFT/VRAM not applicable. Side effects counts exclude fixture ledger writes.','results':summary},indent=2)+'\n')
    print(json.dumps(summary,indent=2))


def math_ceil(value):
    import math
    return math.ceil(value)


if __name__=='__main__':main()
