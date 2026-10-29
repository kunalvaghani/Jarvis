"""Real installed-model capacity probe; no target implementation or saved policy change."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from unittest.mock import patch
from uuid import uuid4

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))


def main():
    from jarvis.campaign_pause import assert_allowed
    assert_allowed(whole_campaign=True)
    parser=argparse.ArgumentParser();parser.add_argument('--context',type=int,default=8192)
    parser.add_argument('--role',choices=['coding','background'],default='coding');args=parser.parse_args()
    from jarvis.gpu_scheduler import configured,memory,runtime_environment
    from jarvis.knowledge_worker import session,chat
    from jarvis.ollama_models import coding_model
    import psutil
    import requests
    root=BASE/'.jarvis-runtime/context-probes'/uuid4().hex;root.mkdir(parents=True)
    record={'date':datetime.now(timezone.utc).isoformat(),'status':'FAIL','model':'qwen3.5:9b',
        'scope':'Real long-input capacity/whole-device-memory observation. Temporary policy injection only; not software generation acceptance.',
        'requested_context':args.context,'role':args.role,'saved_config_changed':False,'root':str(root)}
    policy=configured();tested={**policy,'context_limit':args.context};record['policy_tested']=tested
    samples=[];finished=threading.Event();responses=[];completion={}
    def sample():
        while not finished.is_set():
            samples.append({'at':time.time(),'gpu':memory(),'available_ram_mb':round(psutil.virtual_memory().available/1048576)})
            finished.wait(1)
    sampler=None
    try:
        with requests.Session() as observation:
            observation.trust_env=False
            try:observation.get('http://127.0.0.1:11434/api/version',timeout=3).raise_for_status()
            except requests.ConnectionError:
                executable=shutil.which('ollama') or str(Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Ollama/ollama.exe')
                if not Path(executable).is_file():raise ValueError('Installed Ollama executable not found; no installation attempted.')
                environment=runtime_environment();environment['OLLAMA_HOST']='127.0.0.1:11434'
                log=(root/'owned-server.log').open('ab')
                try:process=subprocess.Popen([executable,'serve'],env=environment,stdout=log,stderr=log,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                finally:log.close()
                record['started_server']={'pid':process.pid,'birth':psutil.Process(process.pid).create_time(),'executable':executable}
                for _ in range(30):
                    try:observation.get('http://127.0.0.1:11434/api/version',timeout=2).raise_for_status();break
                    except requests.RequestException:time.sleep(.5)
                else:raise ValueError('Owned verification server did not become ready.')
            tags=observation.get('http://127.0.0.1:11434/api/tags',timeout=5).json()
            if not any(r.get('name')=='qwen3.5:9b' for r in tags.get('models',[])):
                raise ValueError('Required model is not installed; no model download attempted.')
            model=observation.post('http://127.0.0.1:11434/api/show',json={'model':'qwen3.5:9b'},timeout=10).json()
            record['model_metadata']={k:v for k,v in model.get('model_info',{}).items() if k.endswith(('architecture','context_length','block_count','head_count_kv','key_length','value_length'))}
        sampler=threading.Thread(target=sample,daemon=True);sampler.start();started=time.monotonic()
        with patch('jarvis.gpu_scheduler.configured',return_value=tested),session() as client:
            client.gpu_role=args.role;client.gpu_wait_seconds=180
            coding_model(client,'qwen3.5:9b')
            original=client.post
            def capture(*a,**kw):
                response=original(*a,**kw);responses.append(response);return response
            client.post=capture
            prompt='Capacity test only. Read the padding, then return {"ok":true}.\n'+(' context'*4600)+'\nReturn {"ok":true} now.'
            answer=chat(client,{'model':'qwen3.5:9b','stream':True,'num_ctx':args.context,'num_predict':32,
                'temperature':0,'think':False,'timeout_seconds':150,'on_complete':completion.update,
                'format_schema':{'type':'object','additionalProperties':False,'required':['ok'],
                    'properties':{'ok':{'type':'boolean','enum':[True]}}}},[{'role':'user','content':prompt}],structured=True)
            record.update(answer=json.loads(answer),completion=completion,seconds=round(time.monotonic()-started,3),
                admission=next((getattr(r,'jarvis_gpu') for r in reversed(responses) if getattr(r,'jarvis_gpu',None)),None))
            if record['answer']!={'ok':True} or completion.get('done_reason')!='stop' or completion.get('prompt_eval_count',0)<=4096:
                raise ValueError('Long-input completion did not prove more than 4096 prompt tokens.')
        record['status']='PASS'
    except Exception as error:record.update(error_type=type(error).__name__,error=str(error),completion=completion)
    finally:
        finished.set()
        if sampler:sampler.join(4)
        gpu=[r['gpu']['used_mb'] for r in samples if r['gpu']]
        record.update(samples=samples,whole_device_peak_used_mb=max(gpu) if gpu else None,
            minimum_available_ram_mb=min((r['available_ram_mb'] for r in samples),default=None),
            finished_at=datetime.now(timezone.utc).isoformat())
        if gpu and max(gpu)>tested['vram_ceiling_mb']:
            record.update(status='FAIL',error='Observed whole-device GPU usage exceeded the configured ceiling.')
        target=root/'result.json';target.write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({k:record.get(k) for k in ('status','error','root','seconds','admission','completion','whole_device_peak_used_mb','minimum_available_ram_mb')}))
    return 0 if record['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
