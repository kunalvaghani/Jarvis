"""Paired CPU-only authorization microbenchmark; no downloads, installs or GPU work."""
import csv
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace

out=Path(__file__).resolve().parent
app=Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-v2-mutants-e5af0e7/app')
sys.path.insert(0,str(app))
from jarvis import repair_authorization as current
raw=subprocess.check_output(['git','show','e5af0e700517bac5fb48dcebc8f6cc9c9df9a369:app/jarvis/repair_authorization.py'],cwd=app)
old=ModuleType('jarvis._p99_old_authorization')
sys.modules[old.__name__]=old
exec(compile(raw,'<pinned-authorization>','exec'),old.__dict__)
now=time.time()
parameters=dict(model='qwen3.5:27b',revision='sha256:'+'b'*64,source='ollama',max_bytes=1000,
    ram_bytes=0,vram_bytes=0,network_allowed=True,expires=now+60,approval_id='owned-benchmark')
versions={'pinned':(old,old.ModelDownload(**parameters)),'candidate':(current,current.ModelDownload(**parameters))}
args=dict(environment={},now=now,disk_usage=lambda path:SimpleNamespace(free=1<<40),ram_total=1<<40)
rows=[]
rng=random.Random(99)
for pair in range(201):
    order=list(versions);rng.shuffle(order)
    for name in order:
        module,approval=versions[name]
        start=time.perf_counter_ns()
        module.check_model_download(approval,['qwen3.5:27b'],app,**args)
        elapsed=time.perf_counter_ns()-start
        rows.append({'pair':pair,'revision':name,'elapsed_ns':elapsed,'phase':'first_call' if pair==0 else 'warm'})
with (out/'guard-benchmarks.csv').open('w',newline='',encoding='utf-8') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
summary={}
for name in versions:
    values=sorted(row['elapsed_ns'] for row in rows if row['revision']==name and row['phase']=='warm')
    summary[name]={'n':len(values),'p50_ns':statistics.median(values),'p95_ns':values[189],
        'sample_variance_ns2':statistics.variance(values),'first_call_ns':next(r['elapsed_ns'] for r in rows if r['revision']==name)}
deltas=[next(r['elapsed_ns'] for r in rows if r['pair']==i and r['revision']=='candidate')-
        next(r['elapsed_ns'] for r in rows if r['pair']==i and r['revision']=='pinned') for i in range(1,201)]
bootstrap=sorted(statistics.mean(rng.choices(deltas,k=len(deltas))) for _ in range(2000))
summary.update({'paired_mean_delta_ns':statistics.mean(deltas),'bootstrap_95pct_mean_delta_ns':[bootstrap[49],bootstrap[1949]],
    'pinned_source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_source_sha256':hashlib.sha256((app/'jarvis/repair_authorization.py').read_bytes()).hexdigest(),
    'scope':'valid authorization preflight CPU-only, fixed fake disk/RAM, seed99, randomized 200 warm pairs; no task/model/GPU/voice performance claim',
    'cold_model_and_foreground_latency':'NOT RUN','regression_threshold':'candidate p95 <= pinned p95 + 1ms; security invariant takes precedence',
    'threshold_pass':summary['candidate']['p95_ns']<=summary['pinned']['p95_ns']+1000000})
(out/'guard-benchmark-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary))
