"""Identical saved-memory relevance A/B, immutable before-source, no repository/network/model execution."""
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
from jarvis.repo_learning import RepoLearner


def main():
    spec=importlib.util.spec_from_file_location('jarvis._repo_before',BASE/'.jarvis-runtime/jarvis-audit/module18-pre/jarvis__repo_learning.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    index={f'fixture/repo{i}':{'keywords':[f'term{j}' for j in range(77)]+(['markdown','parser','python'] if i%10==0 else ['other','game','canvas'])} for i in range(500)}
    rows=[];expected=None
    with tempfile.TemporaryDirectory() as tmp:
        actions=SimpleNamespace(base=tmp,memory=SimpleNamespace(vault=Path(tmp)/'vault'))
        for version,cls in [('before',old.RepoLearner),('after',RepoLearner)]:
            warm=cls(actions);warm.index=index;warm.relevant('markdown parser python')
            for i in range(25):
                obj=cls(actions) if i<5 else warm;obj.index=index
                tracemalloc.start();start=time.perf_counter_ns();result=obj.relevant('markdown parser python',3)
                ms=(time.perf_counter_ns()-start)/1e6;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                projection=[(s,n) for s,n,r in result]
                if expected is None:expected=projection
                assert projection==expected
                rows.append({'version':version,'mode':'cold' if i<5 else 'warm','sample':i,'ms':ms,'python_peak_bytes':peak})
            warm.http.close()
    out=BASE/'artifacts/jarvis-audit/modules/18-repo-learning'
    summary={'equivalent':True,'samples_per_version':25,'repositories':500,'keywords_each':80,'external_effects':0,
             'scope':'Saved-memory keyword relevance only: five cold caches,20 warm queries/version; identical scores/top3 names. Construction, disk, source parsing, Git/HTTP/model/audio/GPU excluded. Cold peak includes building derived keyword cache; warm excludes its retained memory.'}
    for version in ('before','after'):
        summary[version]={}
        for mode in ('cold','warm'):
            selected=[r for r in rows if r['version']==version and r['mode']==mode];values=sorted(r['ms'] for r in selected)
            summary[version][mode]={'p50_ms':statistics.median(values),'p95_ms':values[__import__('math').ceil(.95*len(values))-1],'python_peak_bytes':max(r['python_peak_bytes'] for r in selected)}
    with (out/'benchmarks.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    (out/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
