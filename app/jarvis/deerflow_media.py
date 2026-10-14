"""Literal-spec free media creation; no API, host execution or account writes."""
import json
import math
from pathlib import Path

from .deerflow_sandbox import SandboxJob

KINDS = {'chart', 'poster', 'pdf', 'slides', 'video', 'music', 'narration'}


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
        return json.dumps({'recipe': spec['kind'], 'job_id': job.identifier,
            'artifact_directory': str(job.root), 'artifacts': artifacts, 'provider': 'Offline local libraries; no API key or account'}, ensure_ascii=False)
