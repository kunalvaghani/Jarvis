"""Equivalent original/current Gmail draft update on identical in-memory MIME state."""
import base64
import csv
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))

def main():
    from jarvis import gmail_api
    from tests.test_gmail_api import MailFixture
    spec=importlib.util.spec_from_file_location('jarvis._gmail_before',BASE/'.jarvis-runtime/jarvis-audit/module23-pre/jarvis__gmail_api.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    initial=base64.urlsafe_b64encode(b'Subject: Original\r\nTo: a@example.test\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p><b>Keep formatting</b></p>').decode()
    info=old.decode(initial);args={'subject':'Changed','to':'a@example.test','body':info['body'],'expected_sha256':info['sha256']}
    rows=[];outcomes=[]
    for label,module in [('before',old),('after',gmail_api)]:
        api=MailFixture()
        for i in range(25):
            api.raw=initial;api.writes=[]
            tracemalloc.start();start=time.perf_counter_ns();result=module.run(api,'gmail_api_update_draft','draft123',args)
            ms=(time.perf_counter_ns()-start)/1e6;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            assert result['subject_verified'] and result['body_verified'] and not result['sent'] and api.writes==[('PUT','drafts/draft123')]
            outcomes.append((api.raw,result))
            rows.append({'version':label,'mode':'initial' if i<5 else 'warm','sample':i,'ms':ms,'python_peak_bytes':peak})
    assert all(x==outcomes[0] for x in outcomes)
    out=BASE/'artifacts/jarvis-audit/modules/23-gmail'
    with (out/'benchmarks.csv').open('w',newline='') as handle:
        w=csv.DictWriter(handle,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    summary={'equivalent':True,'samples_per_version':25,'real_mailbox_writes':0,'external_effects':0,
      'scope':'Same HTML MIME, expected hash, recipient and result/readback. One fake PUT per sample; byte-identical result MIME. Five initial/twenty warm calls per version in one imported process; no fresh-process cold start, OAuth, network, GUI, RSS/VRAM or full user-journey timing. Current update adds one GET after approval; real HTTP latency may increase despite avoiding repeated MIME parsing.'}
    for label in ('before','after'):
        summary[label]={}
        for mode in ('initial','warm'):
            r=[x for x in rows if x['version']==label and x['mode']==mode];v=sorted(x['ms'] for x in r)
            summary[label][mode]={'p50_ms':statistics.median(v),'p95_ms':v[math.ceil(.95*len(v))-1],'python_peak_bytes':max(x['python_peak_bytes'] for x in r)}
    (out/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
