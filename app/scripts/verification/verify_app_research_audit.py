"""Identical bounded AppKnowledge lookups before/after; no providers or UI."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tracemalloc

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from jarvis.app_knowledge import AppKnowledge


def main():
    out=BASE/'artifacts/jarvis-audit/modules/15-app-research'
    old=BASE/'.jarvis-runtime/jarvis-audit/module15-pre/jarvis__app_knowledge.py'
    spec=importlib.util.spec_from_file_location('jarvis._app_knowledge_before',old)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    now=time.time()
    records={str(i):{'identity':'fixture','feature':'diagram'+str(i),'version':'1.0',
        'status':'environment_confirmed','interface_signature':'same',
        'controls':[{'name':'button'+str(n),'role':'Button'} for n in range(20)],
        'sources':[{'url':'https://example.org/help','excerpt':'Synthetic reference. '*90}]*3,
        'verification':[],'executions':0,'seen_at':now-i} for i in range(24)}
    rows=[]; answers=[]
    with tempfile.TemporaryDirectory() as folder:
        for name,cls in [('before',module.AppKnowledge),('after',AppKnowledge)]:
            warm=cls(folder)
            for i in range(25):
                store=cls(folder) if i<5 else warm
                store.learned={'capability:fixture':{'capabilities':records}}
                tracemalloc.start();start=time.perf_counter_ns()
                answer=store.capabilities('fixture',version='1.0',signature='same')
                ms=(time.perf_counter_ns()-start)/1e6
                _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                assert answer==sorted(records.values(),key=lambda x:x['seen_at'],reverse=True)[:3]
                answer[0]['controls'][0]['name']='mutated copy'
                assert records['0']['controls'][0]['name']=='button0'
                rows.append({'version':name,'mode':'cold' if i<5 else 'warm','index':i,'ms':ms,'python_peak_bytes':peak})
    summary={'samples_per_version':25,'equivalent':True,'side_effects':0,
        'scope':'24 records/target, 20 controls and 3 clipped synthetic sources each. Lookup only; cold is a fresh in-memory store. No disk startup, network, model, TTFT/audio or GPU workload.',
        'vram':'N/A: no GPU allocation'}
    for name in ('before','after'):
        summary[name]={}
        for mode in ('cold','warm'):
            selected=[r for r in rows if r['version']==name and r['mode']==mode]
            values=sorted(r['ms'] for r in selected)
            summary[name][mode]={'p50_ms':statistics.median(values),'p95_ms':values[max(0,__import__('math').ceil(.95*len(values))-1)],'python_peak_bytes':max(r['python_peak_bytes'] for r in selected)}
    with (out/'benchmarks.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    (out/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
