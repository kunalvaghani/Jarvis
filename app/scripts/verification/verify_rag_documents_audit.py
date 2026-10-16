"""Identical BM25 A/B: old immutable source versus postings candidate lookup."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
from jarvis.documents import Document


def main():
    spec=importlib.util.spec_from_file_location('jarvis._documents_before',BASE/'.jarvis-runtime/jarvis-audit/module17-pre/jarvis__documents.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    chunks=[{'id':i,'page':i%400+1,'text':f'Section unique{i} contains routine background explanation. '+('The deadline budget prototype is 14 November.' if i%100==0 else 'Other engineering reference material.')} for i in range(1500)]
    data={'id':'a'*16,'name':'synthetic.pdf','path':'synthetic.pdf','mode':'light','mode_reason':'fixture','created_at':'2026-10-16',
        'chunks':chunks,'graph':{'entities':{},'relations':[]},'graph_chunks_done':[],'questions':[]}
    rows=[];expected=None
    for version,cls in [('before',old.Document),('after',Document)]:
        warm=cls(data)
        for i in range(25):
            doc=cls(data) if i<5 else warm
            tracemalloc.start();start=time.perf_counter_ns();result=doc.search('deadline budget prototype',5)
            elapsed=(time.perf_counter_ns()-start)/1e6;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            projected=[(round(score,10),c['id'],c['page'],c['text']) for score,c in result]
            if expected is None:expected=projected
            assert projected==expected
            rows.append({'version':version,'mode':'cold' if i<5 else 'warm','sample':i,'ms':elapsed,'python_peak_bytes':peak})
    out=BASE/'artifacts/jarvis-audit/modules/17-rag-documents'
    summary={'equivalent':True,'samples_per_version':25,'chunks':len(chunks),'side_effects':0,
        'scope':'BM25 lookup only; five fresh prepared indexes and20 warm lookups/version, top5 IDs/page/text identical, scores equal after rounding to10 decimal places. Index construction, hashing, parsing, graph building, model/network/audio and GPU excluded.'}
    for version in ('before','after'):
        summary[version]={}
        for mode in ('cold','warm'):
            selected=[r for r in rows if r['version']==version and r['mode']==mode];v=sorted(r['ms'] for r in selected)
            summary[version][mode]={'p50_ms':statistics.median(v),'p95_ms':v[__import__('math').ceil(.95*len(v))-1],'python_peak_bytes':max(r['python_peak_bytes'] for r in selected)}
    with (out/'benchmarks.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    (out/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
