"""Literal-spec free media creation; no API, host execution or account writes."""
import json
import math
from pathlib import Path

from .deerflow_sandbox import SandboxJob

KINDS = {'chart', 'poster', 'pdf', 'slides', 'video', 'music', 'narration'}


def verify_artifacts(job,kind,artifacts):
    """Check the expected file from disk; filenames/model prose are not format evidence."""
    import wave
    import zipfile
    expected={'chart':'chart.png','poster':'poster.png','pdf':'report.pdf','slides':'slides.pptx',
              'video':'video.mp4','music':'melody.wav','narration':'narration.wav'}[kind]
    rel='outputs/'+expected
    row=next((r for r in artifacts if r['path']==rel),None)
    if row is None:raise ValueError('Renderer did not produce the expected output file.')
    path=job.path('/mnt/user-data/'+rel)
    size=path.stat().st_size
    if not 0<size<=64*1024*1024:raise ValueError('Rendered output exceeds the verification budget.')
    try:
        if expected.endswith('.png'):
            from PIL import Image
            with Image.open(path) as im:
                if im.format!='PNG' or not 1<=im.width<=4096 or not 1<=im.height<=4096:raise ValueError('Invalid PNG dimensions/format')
                dimensions=list(im.size);im.verify()
            proof={'format':'PNG','dimensions':dimensions,'verification':'Pillow structure verification'}
        elif expected.endswith('.wav'):
            with wave.open(str(path),'rb') as sound:
                frames,rate=sound.getnframes(),sound.getframerate()
                if not frames or not 8000<=rate<=192000 or sound.getnchannels() not in (1,2) or frames/rate>300:raise ValueError('Invalid WAV parameters')
                if len(sound.readframes(frames))!=frames*sound.getnchannels()*sound.getsampwidth():raise ValueError('Truncated WAV')
                proof={'format':'WAV','frames':frames,'sample_rate':rate,'verification':'wave PCM readback'}
        elif expected.endswith('.pptx'):
            with zipfile.ZipFile(path) as archive:
                entries=archive.infolist()
                if len(entries)>1000 or sum(r.file_size for r in entries)>64*1024*1024 or not {'[Content_Types].xml','ppt/presentation.xml'}<=set(archive.namelist()):raise ValueError('Invalid PPTX package')
                if archive.testzip() is not None:raise ValueError('Corrupt PPTX entry')
            proof={'format':'PPTX','verification':'bounded ZIP CRC and required package members; no visual/layout proof'}
        else:
            with path.open('rb') as stream:
                head=stream.read(16)
                stream.seek(max(0,size-1024));tail=stream.read(1024)
            if expected.endswith('.pdf'):
                if not head.startswith(b'%PDF-') or b'%%EOF' not in tail:raise ValueError('Invalid PDF envelope')
                proof={'format':'PDF','verification':'header/EOF only; no page rendering or semantic proof'}
            else:
                if len(head)<12 or head[4:8]!=b'ftyp':raise ValueError('Invalid MP4 envelope')
                proof={'format':'MP4','verification':'ftyp envelope only; no codec/duration/frame decoding proof'}
    except (OSError,EOFError,zipfile.BadZipFile,wave.Error,ValueError) as exc:
        raise ValueError('Renderer output failed format verification: '+type(exc).__name__) from None
    return {**row,'bytes':size,**proof}


def validate(kind, spec):
    if kind not in KINDS or not isinstance(spec, dict) or set(spec) - {'title', 'text', 'labels', 'values', 'slides', 'duration', 'voice'}:
        raise ValueError('Use one documented free-media recipe and literal JSON fields.')
    if any(not isinstance(spec.get(k, ''), str) or len(spec.get(k, '')) > limit for k, limit in [('title', 120), ('text', 2000)]):
        raise ValueError('Use a title up to 120 and text up to 2000 characters.')
    if kind in {'video', 'music'} and (type(spec.get('duration', 6)) is not int or not 1 <= spec.get('duration', 6) <= 30):
        raise ValueError('Free short media duration must be 1–30 seconds.')
    if kind in {'poster', 'video'} and len(spec.get('text', '')) > 500:
        raise ValueError('Use at most 500 characters for the short poster/video card.')
    if kind == 'chart':
        labels, values = spec.get('labels'), spec.get('values')
        if not isinstance(labels, list) or not isinstance(values, list) or not 1 <= len(labels) <= 20 or len(labels) != len(values):
            raise ValueError('A chart needs 1–20 matched labels and values.')
        if any(not isinstance(label, str) or len(label) > 80 for label in labels) or any(type(v) not in {int, float} or not math.isfinite(v) for v in values):
            raise ValueError('Use bounded labels and finite numeric chart values.')
    if kind == 'slides':
        slides = spec.get('slides')
        if not isinstance(slides, list) or not 1 <= len(slides) <= 10 or any(not isinstance(s, dict) or set(s) != {'title', 'text'} or
                not isinstance(s['title'], str) or len(s['title']) > 100 or not isinstance(s['text'], str) or len(s['text']) > 500 for s in slides):
            raise ValueError('Use 1–10 slides with bounded title/text.')
    if kind == 'narration' and (not spec.get('text') or spec.get('voice', 'am_michael') not in {'am_michael', 'af_heart', 'bf_emma'}):
        raise ValueError('Narration needs text and an installed stock voice.')
    return {'kind': kind, **spec}


def execute(actions, step, cancelled):
    spec = validate(step['value'], json.loads(step.get('content') or '{}'))
    if cancelled():
        raise ValueError('Free media cancelled before dispatch.')
    with SandboxJob(actions.base) as job:
        job.observe('sandbox_write', 'spec.json', json.dumps(spec))
        job.observe('sandbox_write', 'render.py', Path(__file__).with_name('deerflow_media_runner.py').read_text())
        job.execute('python render.py', timeout=90, cancelled=cancelled)
        artifacts = [r for r in job.inventory() if r['path'].startswith('outputs/') and r['bytes'] > 0]
        if not artifacts:
            raise ValueError('Free renderer produced no artifact; no automatic replay.')
        verified=verify_artifacts(job,spec['kind'],artifacts)
        return json.dumps({'recipe': spec['kind'], 'job_id': job.identifier,
            'artifact_directory': str(job.root), 'artifacts': artifacts, 'verification':verified,
            'provider': 'Offline local libraries; no API key or account'}, ensure_ascii=False)
