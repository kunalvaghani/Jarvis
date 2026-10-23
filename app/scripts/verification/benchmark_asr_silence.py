"""Compare installed ASR settings on public fixtures and generated noise only."""
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from jarvis.audio import ASR_PROMPT
from jarvis.whisper_backend import load_model, settings


def main():
    config=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    model=load_model(BASE/config['model_path'],settings(config['whisper']))
    rate,audio=wavfile.read(BASE/'artifacts/realtime-voice/public-fixture.wav')
    if audio.dtype.kind in 'iu':audio=audio.astype(np.float32)/np.iinfo(audio.dtype).max
    if audio.ndim>1:audio=audio.mean(axis=1)
    if rate!=16000:audio=resample_poly(audio,16000,rate).astype(np.float32)
    rng=np.random.default_rng(42)
    fixtures={'silence':np.zeros(48000,dtype=np.float32),
        'low_white_noise':rng.normal(0,.002,48000).astype(np.float32),
        'white_noise':rng.normal(0,.02,48000).astype(np.float32),
        'public_speech':audio,
        'public_speech_padded':np.concatenate([np.zeros(16000),audio,np.zeros(48000)]).astype(np.float32)}
    rows=[]
    for policy in ['baseline','filtered']:
        for name,signal in fixtures.items():
            start=time.monotonic()
            options={'initial_prompt':ASR_PROMPT,'vad_filter':False,'beam_size':5,'temperature':0,
                'condition_on_previous_text':False,'word_timestamps':True} if policy=='baseline' else {
                'initial_prompt':None,'vad_filter':True,'vad_parameters':{'threshold':.5,'min_speech_duration_ms':100,
                    'min_silence_duration_ms':200,'speech_pad_ms':100},'hallucination_silence_threshold':1.,
                'condition_on_previous_text':False,'word_timestamps':True}
            segments,_=model.transcribe(signal,language='en',beam_size=5,temperature=0,
                **{k:v for k,v in options.items() if k not in {'beam_size','temperature'}})
            segments=list(segments)
            row={'policy':policy,'fixture':name,'seconds':time.monotonic()-start,
                'text':' '.join(s.text.strip() for s in segments),
                'segments':[{'no_speech_prob':s.no_speech_prob,'avg_logprob':s.avg_logprob} for s in segments]}
            rows.append(row);print(json.dumps(row),flush=True)
    target=BASE/'artifacts/task-queue/asr-silence-comparison.json'
    target.write_text(json.dumps({'date':'2026-10-23','scope':'Existing installed English model; generated noise and existing public TTS fixture only. No microphone recording. Not a physical accuracy certificate.','results':rows},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
