"""One-shot offline speech-file inference, bounded by its owning command job."""
import json
import os
import sys


def main():
    request=json.loads(sys.stdin.buffer.read(10000))
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'
    import av
    with av.open(request['source']) as media:
        if media.duration is None or media.duration/av.time_base>120:
            raise ValueError('Transcription requires an audio duration of at most 120 seconds.')
    from faster_whisper import WhisperModel
    model=WhisperModel(request['model'],device='cpu',compute_type='int8',local_files_only=True,cpu_threads=2)
    segments,info=model.transcribe(request['source'],beam_size=1,vad_filter=True)
    rows=[]
    for segment in segments:
        if len(rows)>=1000:raise ValueError('Audio exceeds the segment budget.')
        rows.append({'start':segment.start,'end':segment.end,'text':segment.text.strip()})
    return {'segments':rows,'language':info.language,'device':'cpu','local_only':True}


if __name__=='__main__':
    try:response={'ok':True,'value':main()}
    except Exception as error:response={'ok':False,'error':type(error).__name__+': '+str(error)}
    print(json.dumps(response),flush=True)
