"""Paired capture-only timings and PCM-duration oracle; no microphone/model/GPU."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock
import psutil
from tests.test_voice_stt_audit import capture_fixture

BASE=Path(__file__).resolve().parents[2]
OUT=BASE/'artifacts/jarvis-audit/modules/04-voice-stt'


def cls(mode):
    if mode=='after':
        from jarvis.audio import Listener
        return Listener
    name='jarvis.audit_audio_pre'
    spec=importlib.util.spec_from_file_location(name,BASE/'.jarvis-runtime/jarvis-audit/module04-pre/audio.py')
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module.Listener


def request(listener_class):
    push=SimpleNamespace(active=threading.Event(),session=7);push.active.set()
    listener=listener_class('owned fixture',None,Mock(),Mock(),push_to_write=push)
    started=time.perf_counter();jobs,_=capture_fixture(listener)
    duration=(time.perf_counter()-started)*1000
    assert len(jobs)==1 and jobs[0].final and jobs[0].write
    return duration,len(jobs[0].audio)


def main():
    if len(sys.argv)>1:
        started=time.perf_counter();duration,samples=request(cls(sys.argv[1]))
        print(json.dumps({'milliseconds':(time.perf_counter()-started)*1000,'pcm_samples':samples,
            'rss_bytes':psutil.Process().memory_info().rss}));return
    classes={mode:cls(mode) for mode in ('before','after')}
    for value in classes.values():request(value)
    rows=[];pcm={}
    for number in range(20):
        for mode in (('before','after') if number%2==0 else ('after','before')):
            duration,pcm[mode]=request(classes[mode])
            rows.append(dict(mode=mode,kind='warm_capture',sample=number,milliseconds=duration,rss_bytes=psutil.Process().memory_info().rss))
    for number in range(5):
        for mode in classes:
            result=subprocess.run([sys.executable,'-m','scripts.verification.verify_voice_stt_audit',mode],cwd=BASE,text=True,capture_output=True,check=True,timeout=40)
            value=json.loads(result.stdout)
            rows.append(dict(mode=mode,kind='cold_fixture_startup',sample=number,milliseconds=value['milliseconds'],rss_bytes=value['rss_bytes']))
    assert pcm=={'before':6400,'after':3200}
    with (OUT/'benchmarks.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    result={'date':'2026-10-15 IST','scope':'Two owned 100 ms/48 kHz blocks, push-to-write release, fake capture/VAD/model; 20 alternating warm and 5 cold processes/build. No real audio capture, GPU, inference, typing or WER. RSS sampled, not peak.',
        'pcm_samples':pcm,'expected_samples_at_16khz':3200,'wer':'BLOCKED: dedicated GPU headroom and labeled acoustic corpora required'}
    for mode in classes:
        for kind in ('warm_capture','cold_fixture_startup'):
            values=sorted(row['milliseconds'] for row in rows if row['mode']==mode and row['kind']==kind)
            result[mode+'_'+kind]={'p50_ms':statistics.median(values),'p95_ms':values[int(.95*(len(values)-1))]}
    (OUT/'benchmark-summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
