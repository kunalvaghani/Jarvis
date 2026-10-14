"""Offline route constraints and timing; all provider results are simulated."""
import json
from pathlib import Path
import statistics
import tempfile
import time
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock

from jarvis.cloud_policy import classify,settings
from jarvis.cloud_quota import QuotaGuardian
from jarvis.hybrid_inference import HybridGateway

BASE=Path(__file__).resolve().parents[2]


def cases():
    from tests.intent_permutations import scenarios
    expected=json.loads((BASE/'tests/fixtures/intent_testbook_expected.json').read_text(encoding='utf-8'))
    source=[(number,direct) for number,direct,*_ in scenarios() if expected[number]!='ask']
    rows=[{'question':direct,'task_kind':expected[number],'expected':'local','group':'existing independent command corpus'} for number,direct in source[::4]][:150]
    public=['Compare distributed consistency models','Explain quantum entanglement','Derive the complexity of binary search','Design a distributed queue architecture','Compare sorting algorithm tradeoffs','Prove the irrationality of square root two','Describe cryptography tradeoffs','Outline concurrency patterns','Analyze optimization algorithms','Discuss quantum error correction']
    private=['Explain my private PDF','Compare our confidential repository','Explain password=never-upload','Explain C:\\Users\\private\\notes.txt','Explain my account history','Explain my personal memory','Explain that proof','Explain this screenshot','Continue the previous task','अभी मेरे निजी दस्तावेज़ पढ़ो','My bank balance','hello','explica mi contraseña','opyen chrmoe','open Chrome and delete a file','Explain api_key=privatevalue','Explain .env settings','Compare my Unreal project','Summarize my medical record','Fix our project','what about it','Tell me the same thing','Show my downloads','Explain /home/person/.ssh/id_rsa','Compare bank account passwords']
    rows += [{'question':q,'expected':'groq','group':'public complex'} for q in public]
    rows += [{'question':q,'expected':'local','group':'private ambiguous multilingual adversarial'} for q in private]
    for field in ('history','screen','memory_context','pc_context','catalog_context','conversation_context','live_app_context'):
        rows.append({'question':'Explain quantum entanglement',field:True,'expected':'local','group':'typed private provenance'})
    for state in ('EXHAUSTED','UNKNOWN','CRITICAL'):
        for q in public: rows.append({'question':q,'quota_state':state,'expected':'local','group':'quota refusal'})
    for q in public: rows.append({'question':q,'offline':True,'expected':'local','group':'offline preference'})
    return rows


def percentiles(rows):
    values=sorted(rows)
    return {f'p{p}_ms':round(values[min(len(values)-1,int(len(values)*p/100))],4) for p in (50,95,99)}


def main():
    import psutil
    rows=cases(); failures=[]
    options=settings({'enabled':True,'account_plan':'free','free_tier_confirmed':True,'dedicated_quota_confirmed':True},environ={})
    with tempfile.TemporaryDirectory() as root:
        adapter=Mock();adapter.ready.return_value=True
        guardian=Mock();guardian.snapshot.return_value={'state':'NORMAL'}
        before=psutil.Process().memory_info().rss
        gateway=HybridGateway(root,options,adapter=adapter,guardian=guardian)
        after=psutil.Process().memory_info().rss
        for row in rows:
            gateway.options={**options,'routing':'local' if row.get('offline') else 'auto'}
            guardian.snapshot.return_value={'state':row.get('quota_state','NORMAL')}
            route=gateway.decide(row)
            if route['provider']!=row['expected']:failures.append({'case':row,'route':route})
        gateway.options=options
        guardian=QuotaGuardian(Path(root)/'benchmark.db',options)
        gateway.guardian=guardian
        privacy=[];quota=[];routing=[]
        for index in range(1200):
            request=rows[index%len(rows)]
            start=time.perf_counter();classify(request);privacy.append((time.perf_counter()-start)*1000)
            start=time.perf_counter();guardian.snapshot();quota.append((time.perf_counter()-start)*1000)
            start=time.perf_counter();gateway.decide(request);routing.append((time.perf_counter()-start)*1000)
        cold_start=time.perf_counter();cold=QuotaGuardian(Path(root)/'cold.db',options);cold.snapshot();cold_ms=1000*(time.perf_counter()-cold_start)
        now=[time.time()]
        durable=QuotaGuardian(Path(root)/'durable.db',options,clock=lambda:now[0])
        reservation=[]
        for _ in range(120):
            now[0]+=3
            start=time.perf_counter();identifier=durable.reserve(options['model'],100);reservation.append(1000*(time.perf_counter()-start))
            durable.finish(identifier,{'total_tokens':50})
        from tests.fake_groq import server
        from jarvis.groq_adapter import GroqAdapter
        now=[time.time()]
        fake_guard=QuotaGuardian(Path(root)/'fake.db',options,clock=lambda:now[0])
        durations=[];ttft=[]
        with server() as (endpoint,state):
            actual_adapter=GroqAdapter('gsk_fakeonlytest123',options,fake_guard,endpoint=endpoint,testing=True)
            actual_adapter.refresh()
            for _ in range(100):
                now[0]+=3;started=time.perf_counter();first=[]
                def chunk(value):
                    if not first:first.append(1000*(time.perf_counter()-started))
                actual_adapter.complete([{'role':'user','content':'Explain quantum computing'}],on_chunk=chunk)
                durations.append(1000*(time.perf_counter()-started));ttft.append(first[0])
            fake_calls=state['calls'];actual_adapter.close()
    report={'date':datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime('%Y-%m-%d IST'),'cases':len(rows),'passed':len(rows)-len(failures),'failures':failures,
        'dataset_scope':'150 existing independently written action scenarios plus public/privacy/quota/offline cases. Constraint acceptance, not model answer accuracy or general semantic routing accuracy.',
        'samples_per_stage':1200,'privacy':percentiles(privacy),'quota_snapshot':percentiles(quota),'route':percentiles(routing),
        'cold_quota_initialization_ms':round(cold_ms,4),'gateway_init_rss_delta_bytes':after-before,
        'atomic_reservation':percentiles(reservation),'atomic_reservation_samples':120,
        'fake_http_stream_ttft':percentiles(ttft),'fake_http_end_to_end':percentiles(durations),'fake_http_calls':fake_calls,
        'resource_scope':'Current Python process RSS delta after imports; no real cloud call, GPU allocation, model load/unload or tiny classifier added.',
        'live_groq_calls':0,'live_model_switch_ms':None,'live_cloud_ttft_ms':None}
    (BASE/'artifacts/reports/groq-routing-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (BASE/'tests/fixtures/groq-routing-cases.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report))
    if failures: raise SystemExit(1)


if __name__=='__main__':main()
