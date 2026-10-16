"""Equivalent before/after preview health parsing without network or project execution."""
import csv
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
from types import SimpleNamespace
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))

def main():
    from jarvis.development_tools import DevelopmentTools
    spec=importlib.util.spec_from_file_location('jarvis._development_before',BASE/'.jarvis-runtime/jarvis-audit/module22-pre/jarvis__development_tools.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    rows=[]
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*a):pass
    with patch('urllib.request.OpenerDirector.open',return_value=Response()):
        for label,klass in [('before',old.DevelopmentTools),('after',DevelopmentTools)]:
            tools=klass(BASE);tools.preview={'desired':True,'process':SimpleNamespace(poll=lambda:None),'url':'http://127.0.0.1:12345'}
            for i in range(25):
                tracemalloc.start();start=time.perf_counter_ns();result=tools.healthy();ms=(time.perf_counter_ns()-start)/1e6
                _,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert result is True
                rows.append({'version':label,'mode':'initial' if i<5 else 'warm','sample':i,'ms':ms,'python_peak_bytes':peak})
            tools.preview['process'].poll=lambda:1;assert tools.healthy() is False
            tools.preview=None;tools.close();assert tools.healthy() is True
    out=BASE/'artifacts/jarvis-audit/modules/22-web-development'
    with (out/'benchmarks.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    summary={'equivalent':True,'external_effects':0,'samples_per_version':25,
      'scope':'Same fake200 health response, active/dead/closed state assertions; real proxy-free opener construction, mocked network open. Five first calls/twenty warm calls per version in one process. Construction/imports/network/Chrome/build/GPU excluded. Cached opener adds retained per-instance memory and construction work; lock still serializes network.'}
    for label in ('before','after'):
        summary[label]={}
        for mode in ('initial','warm'):
            selected=[r for r in rows if r['version']==label and r['mode']==mode];values=sorted(r['ms'] for r in selected)
            summary[label][mode]={'p50_ms':statistics.median(values),'p95_ms':values[math.ceil(.95*len(values))-1],'python_peak_bytes':max(r['python_peak_bytes'] for r in selected)}
    (out/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
