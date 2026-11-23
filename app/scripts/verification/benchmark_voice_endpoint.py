"""End of speech -> command dispatched, through the real capture loop, Silero VAD, endpointing and Whisper.

A recording is fed to Listener.run in real time by a stand-in microphone stream (no capture device, no playback),
followed by silence. The time from the last spoken sample to Engine dispatch is what the user waits for before
Jarvis can act. Run from app/:

    .venv/Scripts/python scripts/verification/benchmark_voice_endpoint.py
"""
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
FIXTURES = BASE / 'artifacts/realtime-voice'


def speech_end(audio, rate=16000, threshold=.02):
    import numpy as np
    loud = np.flatnonzero(np.abs(audio) > threshold)
    return (loud[-1] + 1) / rate if len(loud) else len(audio) / rate


def run(model_dir, clip, options, repeats=3):
    import numpy as np
    from faster_whisper.audio import decode_audio
    from jarvis.audio import Listener
    from jarvis.engine import Engine
    from jarvis.whisper_backend import settings
    from jarvis.commands import parse
    parse('open notepad')  # the running app has its modules imported and warm before anyone speaks
    audio = decode_audio(str(FIXTURES / clip), sampling_rate=16000).astype(np.float32)
    ended = speech_end(audio)
    padded = np.concatenate([np.zeros(8000, np.float32), audio, np.zeros(16000 * 3, np.float32)])
    results = []
    for _ in range(repeats):
        submitted, marks = [], {}

        def submit(command):
            marks.setdefault('dispatched', time.monotonic())
            submitted.append(command)

        engine = Engine(submit, lambda *a: None, 0)
        feed_original = engine.feed

        def feed(text, final=False, now=None, raw=None):
            if final:
                marks.setdefault('final_text', time.monotonic())
            return feed_original(text, final=final, now=now, raw=raw)
        engine.feed = feed
        listener = Listener(BASE / 'models' / model_dir, None, engine, lambda *a: None, settings(options),
                            activate_on_start=True)
        block = int(16000 * options.get('frame_ms', 100) / 1000)

        class Stream:
            def __init__(self, samplerate, blocksize, device, dtype, channels, callback):
                self.callback = callback

            def __enter__(self):
                def feed():
                    start = time.monotonic()
                    for index in range(0, len(padded), block):
                        target = start + index / 16000
                        while time.monotonic() < target:
                            time.sleep(.001)
                        if index <= (0.5 + ended) * 16000 < index + block:
                            marks['spoken'] = start + 0.5 + ended
                        self.callback(padded[index:index + block].reshape(-1, 1), block, None, None)
                        if listener.stop_event.is_set():
                            return
                threading.Thread(target=feed, daemon=True).start()
                return self

            def __exit__(self, *exc):
                return False

        fake = SimpleNamespace(query_devices=lambda *a, **k: {'default_samplerate': 16000, 'name': 'recording'},
                               InputStream=Stream)
        # Only the microphone module is swapped (patch.dict would also drop every module imported meanwhile,
        # so each run re-imported Jarvis, which the running app never does).
        real = sys.modules.get('sounddevice')
        sys.modules['sounddevice'] = fake
        try:
            listener.start()
            deadline = time.monotonic() + 30
            while not submitted and time.monotonic() < deadline:
                time.sleep(.005)
            listener.stop()
            listener.thread.join(10)
        finally:
            if real is None:
                sys.modules.pop('sounddevice', None)
            else:
                sys.modules['sounddevice'] = real
        metrics = list(listener.decode_metrics)
        results.append({'speech_end_to_dispatch_ms': round((marks['dispatched'] - marks['spoken']) * 1000)
                        if 'dispatched' in marks and 'spoken' in marks else None,
                        'command': [submitted[0].kind, submitted[0].value] if submitted else None,
                        'final_text_ms': round((marks['final_text'] - marks['spoken']) * 1000)
                        if 'final_text' in marks and 'spoken' in marks else None,
                        'reused_early_decode': any(m.get('reused') for m in metrics if m.get('final')),
                        'jobs': [{'kind': 'early' if m.get('speculative') else 'final' if m.get('final') else 'partial',
                                  'queued_ms': round((m['queued'] - marks['spoken']) * 1000) if 'spoken' in marks else None,
                                  'wait_ms': round(m['queue_seconds'] * 1000), 'decode_ms': round(m['decode_seconds'] * 1000)}
                                 for m in metrics if 'queued' in m][-4:]})
    return results


def main():
    english, hindi = 'public-fixture.wav', 'mixed-en-hi.wav'
    base = {'device': 'cuda', 'compute_type': 'int8_float16', 'frame_ms': 100}
    cases = [
        ('before: medium.en, 0.8 s endpoint', 'faster-whisper-medium.en', english,
         {**base, 'language': 'en', 'speculative_final': False}),
        ('medium.en, 0.8 s endpoint, early decode', 'faster-whisper-medium.en', english,
         {**base, 'language': 'en'}),
        ('turbo auto, 0.8 s endpoint, no early decode', 'faster-whisper-large-v3-turbo', english,
         {**base, 'language': 'auto', 'speculative_final': False}),
        ('now: turbo auto, conversation endpoint, early decode', 'faster-whisper-large-v3-turbo', english,
         {**base, 'language': 'auto', 'adaptive_endpointing': True, 'endpoint_mode': 'conversation'}),
        ('now, Hindi: turbo auto, conversation endpoint, early decode', 'faster-whisper-large-v3-turbo',
         'public-hindi-fixture.wav', {**base, 'language': 'auto', 'adaptive_endpointing': True,
                                      'endpoint_mode': 'conversation'}),
        ('English-only option: medium.en, conversation endpoint, early decode', 'faster-whisper-medium.en', english,
         {**base, 'language': 'en', 'adaptive_endpointing': True, 'endpoint_mode': 'conversation'}),
    ]
    only = sys.argv[1:]
    report = {}
    for label, model, clip, options in cases:
        if only and not any(word in label for word in only):
            continue
        report[label] = run(model, clip, options)
        print(label, json.dumps(report[label], ensure_ascii=False), flush=True)
    return report


if __name__ == '__main__':
    main()
