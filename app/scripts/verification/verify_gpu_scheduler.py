"""Actual inference-phase GPU handoff beside live Whisper; no desktop actions."""
from datetime import datetime,timezone
import json
from pathlib import Path
import threading
import time

import requests
from jarvis.gpu_scheduler import memory,Registry,configured
from jarvis.knowledge_worker import session,chat
from jarvis.native_tools import plan
from jarvis.command_cleanup import stream_json

BASE=Path(__file__).resolve().parents[2]


def health():
    rows=[]
    for path in (BASE/'.jarvis-runtime').glob('heartbeat-*.json'):
        try:
            r=json.loads(path.read_text())
            if time.time()-r.get('at',0)<10:rows.append(r)
        except (OSError,ValueError):pass
    if not rows:return {'healthy_microphone':False}
    r=max(rows,key=lambda x:x['at']);a=r.get('health',{}).get('audio',{})
    return {'healthy_microphone':r.get('status')=='running' and a.get('phase')=='listening'
        and a.get('capture_alive') and a.get('decoder_alive'),
        'last_audio_age_seconds':a.get('last_block_age_seconds')}


def verify():
    result={'date':datetime.now(timezone.utc).isoformat(),
        'scope':'Actual native planning proposal, execution/question inference, local Codex Responses GPU turn and helper stream. Synthetic inputs only; no desktop action/file write is dispatched. CLI coding is tested separately.',
        'helper_gpu':configured()['helper_gpu'],
        'before':health(),'phases':[]}
    stop=threading.Event();seen=[];gpu=[]
    def monitor():
        with requests.Session() as observer:
            observer.trust_env=False;last_gpu=0
            while not stop.wait(.08):
                try:
                    rows=observer.get('http://127.0.0.1:11434/api/ps',timeout=.5).json().get('models',[])
                    seen.extend({'at':time.time(),**{k:r.get(k) for k in ('name','size_vram','context_length')}} for r in rows)
                    if time.monotonic()-last_gpu>.5:
                        value=memory()
                        if value:gpu.append(value)
                        last_gpu=time.monotonic()
                except requests.RequestException:pass
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try:
        assert result['before']['healthy_microphone'],'Whisper listener must be loaded for this test'
        with session() as client:
            client.gpu_role='planner';started=time.monotonic()
            proposal=plan(client,'qwen3.5:9b','Plan only the one requested read. Never execute a tool.',
                {'goal':'Read fixture.txt once.','tools':[{'action':'read_file','description':'Read the named fixture file.'}]},
                {'timeout_seconds':180})
            assert len(proposal['steps'])==1 and proposal['steps'][0]['action']=='read_file'
            result['phases'].append({'role':'planner','seconds':round(time.monotonic()-started,3),'proposal_only':True,'valid':True,'microphone':health()})
            for role in ('execution','question'):
                client.gpu_role=role;started=time.monotonic()
                text=chat(client,{'model':'qwen3.5:9b','num_ctx':8192,'num_predict':32,'think':False,
                    'format_schema':{'type':'object','required':['result'],'additionalProperties':False,'properties':{'result':{'type':'integer','const':4}}}},
                    [{'role':'user','content':'Return only JSON with result equal to two plus two.'}],structured=True)
                assert json.loads(text)=={'result':4}
                result['phases'].append({'role':role,'seconds':round(time.monotonic()-started,3),'valid':True,'microphone':health()})
            client.gpu_role='coding';started=time.monotonic();text=''
            with client.post('http://127.0.0.1:11434/v1/responses',json={'model':'jarvis-codex-qwen3.5:9b',
                'input':'Return only the number 4.','think':False,'max_output_tokens':32,'stream':True},stream=True,timeout=(3,180)) as response:
                response.raise_for_status();done=False
                for line in response.iter_lines(chunk_size=1):
                    if not line.startswith(b'data:') or line[5:].strip()==b'[DONE]':continue
                    event=json.loads(line[5:])
                    if event.get('type')=='response.output_text.delta':text+=event['delta']
                    if event.get('type')=='response.completed':done=True
                assert done and text.strip()=='4',repr(text)
            result['phases'].append({'role':'coding','seconds':round(time.monotonic()-started,3),'valid':True,'microphone':health()})
        # Let the identified coding cache expire before the idle helper GPU check.
        expiry=time.monotonic()+35
        with requests.Session() as observer:
            observer.trust_env=False
            while time.monotonic()<expiry and observer.get('http://127.0.0.1:11434/api/ps',timeout=3).json().get('models'):
                time.sleep(.25)
        started=time.monotonic()
        answer=stream_json({'model':'qwen3.5:0.8b','messages':[{'role':'user','content':'Return {"result":4} only.'}],
            'stream':True,'think':False,'format':{'type':'object','required':['result'],'additionalProperties':False,'properties':{'result':{'type':'integer','const':4}}},
            'options':{'num_ctx':2048,'num_predict':32}},90,role='context')
        assert answer=={'result':4}
        result['phases'].append({'role':'context','seconds':round(time.monotonic()-started,3),'valid':True,'microphone':health()})
        result['after']=health()
        result['max_observed_gpu_used_mb']=max((r['used_mb'] for r in gpu),default=None)
        result['gpu_total_mb']=gpu[-1]['total_mb'] if gpu else None
        result['resident_models']=[{'model':name,'max_size_vram':max(r['size_vram'] or 0 for r in seen if r['name']==name),
            'contexts':sorted({r['context_length'] for r in seen if r['name']==name and r['context_length']})} for name in sorted({r['name'] for r in seen})]
        events=[json.loads(x) for x in (Registry().root/'events.jsonl').read_text().splitlines()]
        result['scheduler_events']=[r for r in events if r['at']>=datetime.fromisoformat(result['date']).timestamp()]
        result['passed']=all(r['microphone']['healthy_microphone'] for r in result['phases']) and result['after']['healthy_microphone'] and all(
            any(r['model']==name and r['max_size_vram']>0 for r in result['resident_models'])
            for name in (('qwen3.5:9b','jarvis-codex-qwen3.5:9b','qwen3.5:0.8b') if result['helper_gpu'] else ('qwen3.5:9b','jarvis-codex-qwen3.5:9b')))
    except Exception as exc:result.update(passed=False,error_type=type(exc).__name__,error=str(exc)[:500])
    finally:
        stop.set();thread.join(3)
        result['after']=health()
        result['max_observed_gpu_used_mb']=max((r['used_mb'] for r in gpu),default=None)
        result['gpu_total_mb']=gpu[-1]['total_mb'] if gpu else None
        result['resident_models']=[{'model':name,'max_size_vram':max(r['size_vram'] or 0 for r in seen if r['name']==name),
            'contexts':sorted({r['context_length'] for r in seen if r['name']==name and r['context_length']})} for name in sorted({r['name'] for r in seen})]
    path=BASE/'artifacts/reports/gpu-live-check.json'
    if path.exists():
        history=path.with_name('gpu-live-history.json')
        rows=json.loads(history.read_text()) if history.exists() else []
        rows.append(json.loads(path.read_text()));history.write_text(json.dumps(rows,indent=2)+'\n')
    path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return result['passed']


if __name__=='__main__':raise SystemExit(0 if verify() else 1)
