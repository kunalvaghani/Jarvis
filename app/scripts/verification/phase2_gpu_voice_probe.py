"""Bounded synthetic local probes. No microphone/private transcript/cloud requests.

python -m scripts.verification.phase2_gpu_voice_probe
Samples nvidia-smi throughout owned workers; stores categorical metadata only.
Never terminates a pre-existing Ollama, and never downloads missing weights.
"""
import argparse
import contextlib
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

BASE=Path(__file__).resolve().parents[2]
ART=BASE/'artifacts'
FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)


def worker(kind):
    config=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    started=time.perf_counter()
    if kind=='laya':
        from jarvis.brain_worker import Models
        models=Models()
        cases=[
            ('Save the current file without changing its name','Save', [('a','Save','Current document'),('b','Save As','Create a named copy'),('c','Save All','Every open document')]),
            ('Close only the current tab','Close tab',[('a','Close window','All tabs'),('b','Close tab','Current tab'),('c','Close project','Whole project')]),
            ('Keep editing and dismiss the exit question','Cancel',[('a','Discard','Lose changes and exit'),('b','Save','Save and exit'),('c','Cancel','Return to editing')]),
            ('Preview the draft without sending it','Preview',[('a','Send','Deliver immediately'),('b','Preview','Review current draft'),('c','Delete','Remove draft')]),
            ('Pause this playing song','Pause',[('a','Stop','End playback'),('b','Next','Skip track'),('c','Pause','Pause current playback')])]
        rows=[]
        for variant in ('Please','Can you','I want you to','Now','For this task'):
            for goal,target,choices in cases:
                expected=next(key for key,name,_ in choices if name==target)
                request={'operation':'choose','options':{},'goal':variant+' '+goal,
                    'target':goal,'screen':{'title':'Synthetic acceptance application'},
                    'candidates':[{'key':key,'name':name,'context':context,'role':'button'} for key,name,context in choices]}
                result=models.predict(request)
                selected=result.get('choice') if isinstance(result,dict) else result
                rows.append({'expected':expected,'selected':selected,'correct':selected==expected,
                             'confidence':result.get('confidence') if isinstance(result,dict) else None})
        return {'completed':True,'correct':sum(r['correct'] for r in rows),'total':25,'rows':rows,'seconds':time.perf_counter()-started}
    if kind=='lora':
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_TF='0',USE_FLAX='0')
        import torch
        from transformers import AutoTokenizer,AutoModelForCausalLM
        from peft import PeftModel
        checkpoint=(BASE/config['brain']['trained_pc_checkpoint']).resolve()
        tokenizer=AutoTokenizer.from_pretrained(checkpoint,local_files_only=True)
        model=AutoModelForCausalLM.from_pretrained(BASE/'models/qwen-jarvis-base',torch_dtype=torch.float32,local_files_only=True)
        model=PeftModel.from_pretrained(model,checkpoint,local_files_only=True).eval()
        with torch.no_grad():
            inputs=tokenizer('Resolve the project named Aurora.',return_tensors='pt')
            result=model.generate(**inputs,max_new_tokens=2,do_sample=False,pad_token_id=tokenizer.eos_token_id)
        return {'completed':True,'generated_tokens':int(result.shape[-1]-inputs.input_ids.shape[-1]),'seconds':time.perf_counter()-started}
    if kind=='whisper':
        import numpy as np
        from jarvis.whisper_backend import load_model
        model=load_model(BASE/config['model_path'],config['whisper'])
        # Synthetic PCM: this is decode/load pressure, not recognition accuracy.
        durations=[]
        for _ in range(5):
            at=time.perf_counter()
            segments,_=model.transcribe(np.zeros(16000,dtype=np.float32),language='en',beam_size=1)
            list(segments);durations.append(time.perf_counter()-at)
        return {'completed':True,'decode_seconds':durations,'seconds':time.perf_counter()-started,'input':'synthetic silence; no acoustic accuracy claim'}
    if kind=='f5':
        from jarvis.f5_speech import load_voice,render
        voice=load_voice();latencies=[];seconds=[]
        for _ in range(2):
            at=time.perf_counter();first=None;audio_seconds=0
            for audio,rate in render(voice,{'text':'The system is ready for a short voice test.'},threading.Event()):
                if first is None:first=time.perf_counter()-at
                audio_seconds+=len(audio)/rate
            latencies.append(first);seconds.append(audio_seconds)
        return {'completed':True,'first_pcm_seconds':latencies,'audio_seconds':seconds,'seconds':time.perf_counter()-started,
            'scope':'warm synthesis only; no microphone or speaker loopback'}
    if kind in {'kokoro','piper'}:
        import numpy as np
        if kind=='kokoro':
            from jarvis.kokoro_speech import load_voice,render
            voice=load_voice(BASE/'models/voices/kokoro/kokoro-v1.0.onnx',BASE/'models/voices/kokoro/voices-v1.0.bin')
            generate=lambda:render(voice,{'text':'This is a safe fallback voice test.','voice':'am_michael:60,am_fenrir:40'},threading.Event())
        else:
            from piper import PiperVoice
            voice=PiperVoice.load(str(BASE/'models/voices/en_GB-alan-medium.onnx'))
            generate=lambda:((chunk.audio_float_array,chunk.sample_rate) for chunk in voice.synthesize('This is a safe fallback voice test.'))
        at=time.perf_counter();first=None;seconds=0
        for audio,rate in generate():
            if first is None:first=time.perf_counter()-at
            if not np.isfinite(audio).all():raise ValueError('Invalid fallback PCM')
            seconds+=len(audio)/rate
        return {'completed':seconds>0,'first_pcm_seconds':first,'audio_seconds':seconds,'seconds':time.perf_counter()-started}
    if kind in {'cleanup','context','planner','legacy'}:
        import requests
        from jarvis.gpu_scheduler import install
        role={'cleanup':'cleanup','context':'context','planner':'planner','legacy':'coding'}[kind]
        model={'cleanup':'qwen2.5:0.5b','context':'qwen3.5:0.8b','planner':'qwen3.5:9b','legacy':'jarvis-codex-qwen3.5:9b'}[kind]
        client=install(requests.Session(),role);client.trust_env=False
        try:
            result=client.post('http://127.0.0.1:11434/api/generate',json={'model':model,'prompt':'Reply with the word ready.',
                'stream':False,'options':{'num_ctx':4096,'num_predict':8}},timeout=(3,90))
            try:
                result.raise_for_status();data=result.json()
                return {'completed':bool(data.get('done')),'seconds':time.perf_counter()-started,
                    'tokens':data.get('eval_count'),'model':model,'policy':getattr(result,'jarvis_gpu',{})}
            finally:result.close()
        finally:client.close()
    raise ValueError('Unknown probe')


def run_probe(kind,env,timeout=120):
    executable=BASE/env/'Scripts/python.exe'
    try:
        result=subprocess.run([str(executable),'-m','scripts.verification.phase2_gpu_voice_probe','--worker',kind],
            cwd=BASE,env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'},capture_output=True,text=True,
            encoding='utf-8',timeout=timeout,creationflags=FLAGS)
        rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        return rows[-1] if rows else {'completed':False,'error_type':'WorkerExit','returncode':result.returncode}
    except (OSError,subprocess.TimeoutExpired,ValueError) as error:
        return {'completed':False,'error_type':type(error).__name__}


def main():
    ART.mkdir(exist_ok=True)
    stop=threading.Event();trace=[];probes={};owned=None
    def sample():
        while not stop.is_set():
            try:
                r=subprocess.run(['nvidia-smi','--query-gpu=memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits'],
                    capture_output=True,text=True,timeout=2,creationflags=FLAGS,check=True)
                total,used,util=(int(x.strip()) for x in r.stdout.strip().split(','))
                trace.append({'elapsed_seconds':round(time.monotonic()-began,3),'total_mb':total,'used_mb':used,'utilization_percent':util})
            except (OSError,ValueError,subprocess.SubprocessError):pass
            stop.wait(.2)
    began=time.monotonic();sampler=threading.Thread(target=sample);sampler.start()
    try:
        import requests
        client=requests.Session();client.trust_env=False
        try:
            client.get('http://127.0.0.1:11434/api/tags',timeout=2).raise_for_status()
        except requests.RequestException:
            from jarvis.gpu_scheduler import runtime_environment
            env=runtime_environment();env['OLLAMA_HOST']='127.0.0.1:11434'
            # Preserve the server's normal model store. Do not choose a different
            # manifest cache, pull weights, repair aliases or prune user blobs.
            env.update(OLLAMA_NO_CLOUD='1',OLLAMA_NOPRUNE='1')
            executable=shutil.which('ollama')
            if executable:
                server_log=BASE/'.jarvis-runtime/phase2-ollama.log'
                server_log.parent.mkdir(exist_ok=True)
                with server_log.open('w',encoding='utf-8') as output:
                    owned=subprocess.Popen([executable,'serve'],cwd=BASE,env=env,stdout=output,stderr=output,creationflags=FLAGS)
                for _ in range(20):
                    try:
                        client.get('http://127.0.0.1:11434/api/tags',timeout=1).raise_for_status();break
                    except requests.RequestException:time.sleep(.25)
                probes['server_start']={'returncode':owned.poll(),'owned':True}
        from concurrent.futures import ThreadPoolExecutor
        # Simultaneous submissions; scheduler serializes admitted CUDA turns.
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures={kind:pool.submit(run_probe,kind,env) for kind,env in
                [('whisper','.venv'),('f5','.venv-f5'),('cleanup','.venv'),('context','.venv'),('planner','.venv')]}
            for kind,future in futures.items():
                probes[kind]=future.result();print(json.dumps({'probe':kind,**probes[kind]}),flush=True)
        for kind,env in [('laya','.venv-brain'),('lora','.venv-training'),('legacy','.venv'),('kokoro','.venv'),('piper','.venv')]:
            probes[kind]=run_probe(kind,env,120)
            print(json.dumps({'probe':kind,**probes[kind]}),flush=True)
    finally:
        stop.set();sampler.join(3)
        if owned is not None:
            owned.terminate()
            try:owned.wait(timeout=5)
            except subprocess.TimeoutExpired:owned.kill();owned.wait(timeout=5)
    peak=max((row['used_mb'] for row in trace),default=None)
    gates={}
    def blocked(reason):return {'status':'blocked','reason':reason}
    required=('whisper','f5','cleanup','context','planner')
    complete=all(probes.get(k,{}).get('completed') for k in required)
    gates['simultaneous_cuda']=({'status':'pass' if peak is not None and peak<=3850 else 'fail','peak_mb':peak,
        'scope':'simultaneous submissions, synthetic decode and generation; sampled VRAM is not allocator peak proof'} if complete else blocked('One or more CUDA/model workers did not complete; see probe metadata.'))
    for gate,kind in [('lora_load','lora'),('legacy_alias','legacy')]:
        row=probes.get(kind,{})
        gates[gate]={'status':'pass'} if row.get('completed') else blocked(row.get('error_type','Worker incomplete'))
    laya=probes.get('laya',{})
    gates['laya_25']=({'status':'pass' if laya.get('correct',0)>=20 else 'fail','correct':laya.get('correct'),'total':25,'threshold':20} if laya.get('completed') else blocked(laya.get('error_type','Laya incomplete')))
    pcm=probes.get('f5',{}).get('first_pcm_seconds',[])
    gates['ttfa']=({'status':'fail','target_seconds':.5,'first_pcm_seconds':pcm,
        'reason':'First PCM already exceeds audible TTFA target; speaker callback/loopback was not measured.'}
        if pcm and min(pcm)>=.5 else blocked('Audible TTFA needs a speaker callback/loopback measurement.'))
    gates['live_hotkeys']=blocked('No interactive Notepad/VS Code key injection performed; fixture key-state results are separate.')
    gates['live_mind_dag']=blocked('No live Tk Mind/DAG session captured; state and rendering fixtures are separate.')
    evidence={'date':'2026-10-15 IST','elapsed_seconds':time.monotonic()-began,'probes':probes,'gates':gates,
        'vram_peak_sampled_mb':peak,'sample_count':len(trace),'oom_count':None,
        'oom_scope':'No global CUDA allocator/log interception; zero OOM is not certified by sampling.'}
    (ART/'phase2-live-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    with (ART/'phase2-vram-trace.csv').open('w',newline='',encoding='utf-8') as out:
        writer=csv.DictWriter(out,fieldnames=['elapsed_seconds','total_mb','used_mb','utilization_percent']);writer.writeheader();writer.writerows(trace)
    print(json.dumps({'evidence':'artifacts/phase2-live-evidence.json','gates':gates}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker');args=parser.parse_args()
    if args.worker:
        try:
            with contextlib.redirect_stdout(sys.stderr):result=worker(args.worker)
        except Exception as error:result={'completed':False,'error_type':type(error).__name__}
        print(json.dumps(result),flush=True)
    else:main()
