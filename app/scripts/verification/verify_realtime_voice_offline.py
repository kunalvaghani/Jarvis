"""Run generated public audio through the actual Listener decoder and Engine.

No microphone/playback or external action: Engine submits to an in-memory list.
Windows are supplied serially, so timings measure decode, not live capture latency.
"""
import json
from pathlib import Path
import threading
import time

BASE = Path(__file__).resolve().parents[2]


def main():
    from scipy.io import wavfile
    from jarvis.audio import Listener, DecodeJob
    from jarvis.engine import Engine
    from jarvis.whisper_backend import load_model
    out = BASE / 'artifacts/realtime-voice'
    config = json.loads((BASE / 'config/config.json').read_text(encoding='utf-8'))
    rate, audio = wavfile.read(out / 'public-fixture.wav')
    assert rate == 16000
    submitted, events = [], []
    listener = Listener(BASE / config['model_path'], None,
        Engine(submitted.append, lambda *a: None), lambda *a: events.append(a), config['whisper'])
    model = load_model(listener.model_path, listener.options)
    worker = threading.Thread(target=listener._decode, args=(model,), daemon=True)
    worker.start()
    steps = []
    try:
        for index, end in enumerate((.9, 1.6, len(audio)/16000)):
            final = index == 2
            before = len(listener.decode_metrics)
            listener.jobs.put(DecodeJob(1, 0, audio[:round(end*16000)], final=final))
            deadline = time.monotonic() + 60
            while len(listener.decode_metrics) == before and time.monotonic() < deadline:
                time.sleep(.01)
            if len(listener.decode_metrics) == before:
                raise TimeoutError('Offline decode timed out')
            # Metrics precede the transcript event and final dispatch by a few instructions.
            deadline = time.monotonic() + 2
            while not any(k == 'voice_transcript' and v['revision'] == index+1 for k,v in events) and time.monotonic() < deadline:
                time.sleep(.01)
            steps.append({'audio_seconds': end, 'final': final,
                'decode_seconds': listener.decode_metrics[-1]['decode_seconds'],
                'submitted_count': len(submitted)})
            if not final:
                assert not submitted
        deadline = time.monotonic() + 2
        while not submitted and time.monotonic() < deadline:
            time.sleep(.01)
        passed = len(submitted) == 1 and submitted[0].kind == 'open' and submitted[0].value == 'calculator'
        steps[-1]['submitted_count'] = len(submitted)
        report = {'date': '2026-10-23 IST', 'passed': passed,
            'scope': 'Actual local Listener decoder and Engine; serial growing windows of one generated public English fixture. No live capture, speaker, external actions or native streaming claim.',
            'steps': steps, 'transcripts': [v for k,v in events if k == 'voice_transcript'],
            'commands': [{'kind': c.kind, 'value': c.value} for c in submitted]}
        (out / 'offline-listener.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, indent=2))
        if not passed:
            raise SystemExit(1)
    finally:
        listener.stop()
        worker.join(3)


if __name__ == '__main__':
    main()
