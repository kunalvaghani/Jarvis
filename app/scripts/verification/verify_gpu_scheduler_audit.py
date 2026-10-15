"""Same-state write benchmark; optional sequential cached native GPU probes."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/08-gpu-scheduler'


def benchmark():
    from jarvis import gpu_scheduler as after
    path=BASE/'.jarvis-runtime/jarvis-audit/module08-pre/gpu_scheduler.py'
    spec=importlib.util.spec_from_file_location('jarvis._gpu_audit_before',path)
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    records=[]
    with tempfile.TemporaryDirectory() as folder:
        for version,module in [('before',before),('after',after)]:
            registry=module.Registry(Path(folder)/version)
            with registry.state():pass
            for mode,count in [('cold_read',5),('warm_read',20)]:
                for index in range(count):
                    if mode=='cold_read':registry=module.Registry(Path(folder)/version)
                    tracemalloc.start();start=time.perf_counter()
                    with patch.object(module,'replace_state',wraps=module.replace_state) as replace:
                        with registry.state() as state:
                            assert state['active'] is None and state['pending']==[]
                    elapsed=(time.perf_counter()-start)*1000;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                    records.append(dict(version=version,mode=mode,sample=index,latency_ms=elapsed,
                        atomic_promotions=replace.call_count,peak_python_bytes=peak,external_writes=0,gpu_calls=0))
    with (OUT/'benchmarks.csv').open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    summary={}
    for version in ('before','after'):
        for mode in ('cold_read','warm_read'):
            rows=[r for r in records if r['version']==version and r['mode']==mode]
            times=sorted(r['latency_ms'] for r in rows)
            summary[version+'_'+mode]=dict(samples=len(times),p50_ms=statistics.median(times),
                p95_ms=times[min(len(times)-1,int(len(times)*.95))],atomic_promotions=sum(r['atomic_promotions'] for r in rows),
                peak_python_bytes=max(r['peak_python_bytes'] for r in rows))
    assert summary['after_warm_read']['atomic_promotions']==0 and summary['before_warm_read']['atomic_promotions']==20
    (OUT/'benchmark-summary.json').write_text(json.dumps({'scope':'Identical empty registry polls, same OS lock/path semantics; cold recreates Python Registry only, not disk cache/process/model.',
        'results':summary},indent=2),encoding='utf-8');print(summary)


def native():
    import psutil
    import requests
    from jarvis import gpu_scheduler as gpu
    from jarvis.knowledge_worker import chat
    client=gpu.install(requests.Session());client.trust_env=False
    version=client.get('http://127.0.0.1:11434/api/version',timeout=3).json()['version']
    models=client.get('http://127.0.0.1:11434/api/tags',timeout=3).json()['models']
    assert any(m['name']=='qwen3.5:9b' for m in models),'Cached model required; never download'
    before=client.get('http://127.0.0.1:11434/api/ps',timeout=3).json()['models']
    if any(m.get('name')!='qwen3.5:9b' and m.get('size_vram',0)>0 for m in before):
        raise ValueError('Other GPU model is resident; defer native probes without unloading it.')
    captured=[];original=client.post
    def observed(*args,**kwargs):
        response=original(*args,**kwargs)
        if hasattr(response,'jarvis_gpu'):
            event={'allocation':response.jarvis_gpu};captured.append(event)
            lines=response.iter_lines
            def read(*args,**kwargs):
                for line in lines(*args,**kwargs):
                    if line:
                        data=json.loads(line)
                        if data.get('done'):
                            event['metrics']={key:data.get(key) for key in ('load_duration','total_duration','eval_count','eval_duration','prompt_eval_count','prompt_eval_duration')}
                    yield line
            response.iter_lines=read
        return response
    client.post=observed
    samples=[];stop=threading.Event();observations=[]
    def observe():
        while not stop.is_set():
            observations.append({'hardware':gpu.memory(),'observer_rss_bytes':psutil.Process().memory_info().rss})
            stop.wait(.2)
    observer=threading.Thread(target=observe,daemon=True);observer.start()
    try:
        for label in ('initial','warm1','warm2'):
            chunks=[];start=time.monotonic()
            text=chat(client,{'model':'qwen3.5:9b','think':False,'stream':True,'num_ctx':16384,
                'num_predict':32,'temperature':0,'timeout_seconds':60,
                'on_chunk':lambda text:chunks.append(time.monotonic()-start)},
                [{'role':'user','content':'What is two plus two? Reply with only the number.'}])
            assert '4' in text or 'four' in text.lower(),text
            samples.append({'phase':label,'answer':text,'ttft_seconds':chunks[0],
                'seconds':time.monotonic()-start,**captured[-1]})
    finally:
        stop.set();observer.join(3);client.close()
    state=json.loads(gpu.Registry().path.read_text())
    assert state['active'] is None and state['pending']==[]
    physical=[r['hardware']['used_mb'] for r in observations if r['hardware']]
    assert physical and max(physical)<=4096
    report={'status':'PASS','ollama':version,'model':'qwen3.5:9b',
        'initial_gpu_cold':not any(m.get('name')=='qwen3.5:9b' and m.get('size_vram',0)>0 for m in before),
        'prior_resident_names':[m['name'] for m in before], 'samples':samples,
        'sampled_peak_gpu_used_mb':max(physical),'initial_sampled_gpu_used_mb':physical[0],
        'observer_peak_rss_bytes':max(r['observer_rss_bytes'] for r in observations),
        'scope':'Sequential synthetic loopback inference only; sampled physical GPU peak and observer RSS, not instantaneous/Ollama RSS peaks. No cache forcibly unloaded, no voice/GUI, no new model/download.',
        'external_writes':0,'lease_readback':{'active':state['active'],'pending':len(state['pending'])}}
    (OUT/'native-local.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print({'native':report['status'],'gpu_cold':report['initial_gpu_cold'],'sampled_peak_gpu_mb':max(physical),
           'ttft':[s['ttft_seconds'] for s in samples]})


if __name__=='__main__':
    benchmark()
    if '--native' in sys.argv:native()
