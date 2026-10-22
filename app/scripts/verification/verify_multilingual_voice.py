"""Offline evaluation of an already-installed approved model and local public fixtures.

No downloads, capture, playback, package installation or external tool execution.
Model-download authorization and fixture provenance are separate receipts.
"""
from pathlib import Path
import hashlib
import json
import time
import unicodedata
import numpy as np
from faster_whisper.audio import decode_audio
import sys

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
OUT = BASE / 'artifacts/realtime-voice'


def normalized(text):
    return ''.join(' ' if unicodedata.category(c).startswith('P') else c for c in unicodedata.normalize('NFKC',text).lower()).split()


def distance(a,b):
    previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        current=[i]
        for j,y in enumerate(b,1):
            current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(x!=y)))
        previous=current
    return previous[-1]


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path', default='models/faster-whisper-large-v3-turbo')
    parser.add_argument('--language', default='auto', choices=['auto','en','hi','gu','fr'])
    parser.add_argument('--output', default='turbo-multilingual-asr.json')
    args=parser.parse_args()
    if Path(args.output).name != args.output:
        raise ValueError('Output must be a report filename')
    fixtures=json.loads((OUT/'multilingual-fixtures.json').read_text(encoding='utf-8'))['fixtures']
    mixed=OUT/'mixed-fixtures.json'
    if mixed.is_file():fixtures += json.loads(mixed.read_text(encoding='utf-8'))['fixtures']
    from jarvis.whisper_backend import load_model
    from jarvis.audio import ASR_PROMPT
    model=load_model(BASE/args.model_path,{'device':'cuda','compute_type':'int8_float16','language':'auto'})
    rows=[]
    for fixture in fixtures:
        audio=decode_audio(str(OUT/fixture['path']),sampling_rate=16000)
        import psutil
        process=psutil.Process(); cpu_before=process.cpu_times()
        started=time.perf_counter()
        segments,info=model.transcribe(audio,language=None if args.language=='auto' else args.language,beam_size=5,temperature=0,
            condition_on_previous_text=False,word_timestamps=True,vad_filter=False,
            no_speech_threshold=.6,log_prob_threshold=-1.,compression_ratio_threshold=2.4,initial_prompt=ASR_PROMPT)
        text=' '.join(s.text for s in segments)
        seconds=time.perf_counter()-started
        reference=normalized(fixture['reference']);actual=normalized(text)
        cpu_after=process.cpu_times()
        rows.append({'rss_bytes_sampled':process.memory_info().rss, 'cpu_seconds':cpu_after.user+cpu_after.system-cpu_before.user-cpu_before.system, 'fixture':fixture['path'],'expected_language':fixture['language'],
            'detected_language':info.language,'language_probability':info.language_probability,
            'reference':fixture['reference'],'hypothesis':text,'word_errors':distance(reference,actual),
            'reference_words':len(reference),'wer':distance(reference,actual)/max(1,len(reference)),
            'decode_seconds':seconds,'audio_seconds':len(audio)/16000})
        print(fixture['path']+': '+info.language+' WER='+str(round(rows[-1]['wer'],3)),flush=True)
        report={'date':'2026-10-23 IST','model':args.model_path, 'language_mode':args.language,
            'scope':'Offline public FLEURS test rows plus synthesized public fixtures; production final decode settings and automatic language detection. Tiny diagnostic sample, no physical microphone, no broad accuracy claim.',
            'supported_languages':{k:k in model.supported_languages for k in ('en','hi','gu','fr')},'results':rows}
        (OUT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
