"""Matched offline benchmarks and optional fake-cloud to real-local journey."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tracemalloc
from unittest.mock import Mock, patch

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/07-model-routing'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module07-pre'


def load_before(name):
    spec=importlib.util.spec_from_file_location('jarvis._audit_pre_'+name,PRE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def benchmark():
    from jarvis import hybrid_inference,cloud_policy
    options=cloud_policy.settings(dict(enabled=True,account_plan='free',free_tier_confirmed=True,dedicated_quota_confirmed=True),environ={})
    records=[]
    with tempfile.TemporaryDirectory() as folder:
        for version,module in [('before',load_before('hybrid_inference')),('after',hybrid_inference)]:
            for mode,count in [('cold_gateway',5),('warm_gateway',20)]:
                gateway=None
                for i in range(count):
                    adapter=Mock();adapter.ready.side_effect=lambda **_: (time.sleep(.02) or True)
                    guard=Mock();guard.snapshot.return_value={'state':'EXHAUSTED'}
                    tracemalloc.start();start=time.perf_counter()
                    if mode=='cold_gateway' or gateway is None:
                        gateway=module.HybridGateway(Path(folder)/version,options,adapter=adapter,guardian=guard)
                    route=gateway.decide({'question':'Explain quantum computing'})
                    elapsed=(time.perf_counter()-start)*1000
                    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                    assert route['provider']=='local' and route['reason']=='quota_unavailable'
                    records.append(dict(version=version,mode=mode,sample=i,latency_ms=elapsed,
                        peak_python_bytes=peak,metadata_wait_calls=gateway.adapter.ready.call_count,
                        cloud_inference_calls=gateway.adapter.complete.call_count,external_writes=0,gpu_allocations=0))
        # Identical benign/public/private classification workload; no model/router downloaded.
        fixtures=['Explain quantum computing','Explain my bank statement','Explain api_key=SYNTHETIC',
                  'Click the button','Explain quantum computing हिन्दी 😀']
        classification={}
        for version,module in [('before',load_before('cloud_policy')),('after',cloud_policy)]:
            times=[]
            for _ in range(100):
                start=time.perf_counter()
                results=[module.classify({'question':q}) for q in fixtures]
                times.append((time.perf_counter()-start)*1000/len(fixtures))
                assert [r['privacy'] for r in results]==['PUBLIC','INTERNAL','SENSITIVE','INTERNAL','PUBLIC']
            classification[version]={'p50_ms_per_request':statistics.median(times),'p95_ms_per_request':sorted(times)[94]}
    with (OUT/'benchmarks.csv').open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    summary={}
    for version in ('before','after'):
        for mode in ('cold_gateway','warm_gateway'):
            selected=[r for r in records if r['version']==version and r['mode']==mode]
            times=sorted(r['latency_ms'] for r in selected)
            summary[version+'_'+mode]={'samples':len(times),'p50_ms':statistics.median(times),
                'p95_ms':times[min(len(times)-1,int(len(times)*.95))],
                'peak_python_bytes':max(r['peak_python_bytes'] for r in selected)}
    assert summary['after_warm_gateway']['p95_ms']<summary['before_warm_gateway']['p95_ms']
    (OUT/'benchmark-summary.json').write_text(json.dumps({'scope':'Exhausted quota with identical simulated20ms metadata wait. Cold includes gateway/SQLite feedback initialization; warm reuses gateway. No network/model/first-audio benchmark.',
        'route':summary,'classification':classification},indent=2),encoding='utf-8')
    print(summary)


def journey():
    from jarvis.cloud_policy import settings
    from jarvis.cloud_quota import QuotaGuardian
    from jarvis.groq_adapter import GroqAdapter
    from jarvis.hybrid_inference import HybridGateway
    from jarvis.knowledge_worker import handle_request,session,ensure_server
    from tests.fake_groq import server
    options=settings(dict(enabled=True,account_plan='free',free_tier_confirmed=True,dedicated_quota_confirmed=True),environ={})
    client=session()
    try:
        models=ensure_server(client)
        assert 'qwen3.5:9b' in {m['name'] for m in models['models']}, 'already installed9b required; no download permitted'
        with tempfile.TemporaryDirectory() as folder,server() as (endpoint,state):
            state['mode']='429';state['headers']={'Retry-After':'120'}
            guard=QuotaGuardian(Path(folder)/'quota.db',options)
            adapter=GroqAdapter('gsk_fakeonlytest123',options,guard,endpoint=endpoint,testing=True)
            adapter.refresh();assert adapter.ready()
            gateway=HybridGateway(folder,options,adapter=adapter,guardian=guard)
            request={'question':'Explain quantum computing to a beginner',
                'options':{'model':'missing-audit-model','internet':False,'think':False,'num_gpu':0,
                           'num_predict':240,'num_thread':6,'timeout_seconds':60,'temperature':0}}
            def fake_gateway(request,progress=None):
                request['_hybrid_enabled']=True
                return gateway.answer(request,progress)
            start=time.monotonic()
            with patch('jarvis.hybrid_inference.maybe_answer',side_effect=fake_gateway),patch('jarvis.hybrid_inference.BASE',Path(folder)):
                result=handle_request(request,client)
            elapsed=time.monotonic()-start
            assert 'error' not in result and 'qubit' in result['answer'].lower(),result
            assert state['calls']==1 and guard.snapshot(fresh=True)['state']=='UNKNOWN'
            with guard.connect() as db:
                row=dict(db.execute('SELECT id,tokens,reserved,status FROM calls').fetchone())
            assert row['status']=='uncertain' and row['tokens']==row['reserved']
            adapter.close()
            report={'status':'PASS','scope':'Real handle_request: loopback fakeGroq429 then cached realOllama9b; no real cloud/desktop/speech/account action.',
                'model':'qwen3.5:9b','seconds':elapsed,'answer':result['answer'],'fake_cloud_calls':state['calls'],
                'real_cloud_calls':0,'external_writes':0,'quota_readback':row}
            (OUT/'local-fallback-journey.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print({'journey':report['status'],'seconds':elapsed})
    finally:client.close()


if __name__=='__main__':
    benchmark()
    if '--local-journey' in sys.argv:journey()
