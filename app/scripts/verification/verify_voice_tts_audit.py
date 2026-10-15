"""Paired header/chunk CPU timings, or one offline GPU worker protocol run."""
import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path
import queue
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import wave
import psutil

BASE=Path(__file__).resolve().parents[2]
OUT=BASE/'artifacts/jarvis-audit/modules/05-voice-tts'


def module(mode):
    path=BASE/'jarvis/f5_speech.py' if mode=='after' else BASE/'.jarvis-runtime/jarvis-audit/module05-pre/f5_speech.py'
    name='jarvis.audit_f5_'+mode
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value)
    return value


def exercise(adapter,path,rounds):
    options={'reference_audio':str(path),'reference_text':'A clean synthetic reference has exact words.','auto_emotion':False}
    text='A complete first sentence. Another complete sentence preserves all of its words. '*8
    started=time.perf_counter()
    for _ in range(rounds):
        ref,transcript,style=adapter.reference(options,text)
        chunks=adapter.chunks(text,ref,transcript,1.)
        assert ' '.join(chunks)==text.strip() and style=='neutral'
    return (time.perf_counter()-started)*1000/rounds


def benchmark(child=None):
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'reference.wav'
        with wave.open(str(path),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(24000)
            stream.writeframes(b'\0'*(24000*2*4))
        if child:
            started=time.perf_counter();adapter=module(child);exercise(adapter,path,1)
            print(json.dumps({'milliseconds':(time.perf_counter()-started)*1000,'rss_bytes':psutil.Process().memory_info().rss}));return
        adapters={mode:module(mode) for mode in ('before','after')}
        for adapter in adapters.values():exercise(adapter,path,1)
        rows=[]
        for sample in range(20):
            for mode in (('before','after') if sample%2==0 else ('after','before')):
                rows.append({'mode':mode,'kind':'warm_reference_and_chunks','sample':sample,'milliseconds':exercise(adapters[mode],path,40),'rss_bytes':psutil.Process().memory_info().rss})
        for sample in range(5):
            for mode in adapters:
                result=subprocess.run([sys.executable,'-m','scripts.verification.verify_voice_tts_audit','--child',mode],cwd=BASE,capture_output=True,text=True,timeout=40,check=True)
                value=json.loads(result.stdout)
                rows.append({'mode':mode,'kind':'cold_adapter_import','sample':sample,**value})
    with (OUT/'benchmarks.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={'date':'2026-10-15 IST','scope':'Owned four-second zero-PCM reference metadata and fixed text chunk boundaries; no inference, speaker, network or GPU. 20 alternating warm batches of40 requests and5 cold subprocess samples/build. RSS sampled, not peak.'}
    for mode in adapters:
        for kind in {row['kind'] for row in rows}:
            values=sorted(row['milliseconds'] for row in rows if row['mode']==mode and row['kind']==kind)
            summary[mode+'_'+kind]={'p50_ms':statistics.median(values),'p95_ms':values[int(.95*(len(values)-1))]}
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary))


def live():
    """No downloads: current cached F5, one GPU process, no audio output stream."""
    child='''import json,sys,time
from jarvis.f5_speech import load_voice,render
from jarvis.kokoro_speech import serve
protocol=sys.stdout
loads=0
def loader():
    global loads
    loads+=1
    voice=load_voice()
    import torch
    torch.cuda.reset_peak_memory_stats()
    return voice
def renderer(voice,request,stop,progress):
    import torch
    yield from render(voice,request,stop,progress)
    protocol.write(json.dumps({'id':request['id'],'audit_metrics':{'loads':loads,'peak_allocated_mb':round(torch.cuda.max_memory_allocated()/1048576,2),'peak_reserved_mb':round(torch.cuda.max_memory_reserved()/1048576,2)}})+'\\n');protocol.flush()
serve(loader,renderer,coalesce=True)
'''
    env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1'}
    private=BASE/'.jarvis-runtime/jarvis-audit/module05-pre'
    events=queue.Queue();rows=[];started=time.monotonic()
    with (private/'live-worker.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(BASE/'.venv-f5/Scripts/python.exe'),'-u','-c',child,'--no-playback'],cwd=BASE,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        def read():
            for line in process.stdout:
                try:row=json.loads(line)
                except ValueError:continue
                events.put({'at_seconds':round(time.monotonic()-started,4),**row})
            events.put({'error':'worker_exit'})
        thread=threading.Thread(target=read,daemon=True);thread.start()
        def until(predicate,seconds=120):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                row=events.get(timeout=max(.01,deadline-time.monotonic()));rows.append(row)
                if row.get('error'):raise RuntimeError('Live owned voice protocol failed; inspect private log')
                if predicate(row):return row
            raise TimeoutError('Live owned voice deadline')
        def send(row):process.stdin.write(json.dumps(row)+'\n');process.stdin.flush()
        try:
            ready=until(lambda r:r.get('ready'))
            sent1=time.monotonic()-started
            send({'id':1,'text':'Your project is ready. I can help with the next step.'})
            first=until(lambda r:r.get('id')==1 and r.get('audio_ready'))
            until(lambda r:r.get('id')==1 and r.get('done'))
            send({'id':2,'text':'This long answer keeps the steps in order. First we review the existing tests, then inspect the evidence. Each change has a clear purpose and a way to check the result. We can continue with the next part when you are ready. The final result remains available in your transcript.'})
            until(lambda r:r.get('id')==2 and r.get('done'))
            send({'id':3,'text':'This cancelled reply must never be replayed.'})
            stop_at=time.monotonic();send({'stop':True})
            until(lambda r:r.get('stopped'),5)
            stop_ack=time.monotonic()-stop_at
            send({'id':4,'text':'The earlier reply was stopped. This is a new request.'})
            until(lambda r:r.get('id')==4 and r.get('done'))
            assert [r['id'] for r in rows if r.get('done')]==[1,2,4]
            assert not any(r.get('id')==3 and (r.get('audio_ready') or r.get('done')) for r in rows)
            metrics=[r['audit_metrics'] for r in rows if 'audit_metrics' in r]
            assert metrics and all(r['loads']==1 for r in metrics)
            result={'date':'2026-10-15 IST','status':'PASS','scope':'Actual cached F5 CUDA inference and owned protocol, one model load, offline/no speaker playback; no acoustic quality or STT/Qwen contention claim','ready_seconds':ready['at_seconds'],'first_request_audio_seconds':round(first['at_seconds']-sent1,4),'stop_ack_seconds':round(stop_ack,4),'peak_allocated_mb':max(r['peak_allocated_mb'] for r in metrics),'peak_reserved_mb':max(r['peak_reserved_mb'] for r in metrics),'events':rows}
            (OUT/'live-worker.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='events'}))
        finally:
            process.stdin.close()
            try:process.wait(timeout=6)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            process.stdout.close();thread.join(timeout=1)


def live_cpu():
    """Real fallback via Speech, forcing an absent reference; speakers stay off."""
    from unittest.mock import patch
    import numpy as np
    from jarvis.speech import Speech
    from piper import PiperVoice
    launched=[];reports=[];events=[]
    native_launch=subprocess.Popen
    def launch(argv,**kwargs):
        if 'jarvis.kokoro_speech' not in argv:
            raise RuntimeError('This audit permits only a no-playback Kokoro child')
        launched.append(list(argv))
        kwargs['env']={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
        return native_launch([*argv,'--no-playback'],**kwargs)
    speech=Speech({'engine':'f5','language':'en','f5':{'reference_audio':'models/voices/f5/audit-deliberately-absent.wav','reference_text':'Missing reference fixture.'}},lambda kind,text:reports.append(kind))
    event=speech._event
    def observed(line,process=None):
        try:events.append(json.loads(line))
        except ValueError:pass
        event(line,process=process)
    speech._event=observed
    started=time.monotonic()
    with patch('jarvis.speech.subprocess.Popen',side_effect=launch):
        try:
            speech.start()
            for index,text in enumerate(('An installed local fallback is ready.','A second reply reuses the warm voice.'),1):
                speech.say(text);deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    if any(row.get('id')==index and row.get('done') for row in events):break
                    if any(row.get('error') for row in events):raise RuntimeError('CPU fallback protocol failed')
                    time.sleep(.02)
                else:raise TimeoutError('CPU fallback deadline')
            assert len(launched)==1 and 'f5' in speech.failed_backends
            assert [row['id'] for row in events if row.get('done')]==[1,2]
            assert speech.worker_engine=='kokoro' and not speech.outstanding
        finally:speech.close()
    # Piper component synthesis is local PCM only: never call play_reply/sounddevice.
    voice=PiperVoice.load(str(BASE/'models/voices/en_GB-alan-medium.onnx'))
    samples=0
    for chunk in voice.synthesize('The installed Piper fallback also produces valid speech.'):
        audio=np.asarray(chunk.audio_float_array)
        assert audio.size and np.isfinite(audio).all();samples+=audio.size
    assert samples>0
    result={'date':'2026-10-15 IST','status':'PASS','scope':'Actual Speech F5-missing-reference to installed warm Kokoro child with --no-playback, two requests/one launch; separate installed Piper component PCM synthesis, no output stream or download','kokoro_requests':2,'kokoro_process_launches':1,'piper_pcm_samples':samples,'seconds':round(time.monotonic()-started,3),'events':events,'report_categories':reports}
    (OUT/'live-cpu-fallback.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='events'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--child',choices=['before','after']);parser.add_argument('--live',action='store_true');parser.add_argument('--live-cpu',action='store_true');args=parser.parse_args()
    if args.live:live()
    elif args.live_cpu:live_cpu()
    else:benchmark(args.child)
