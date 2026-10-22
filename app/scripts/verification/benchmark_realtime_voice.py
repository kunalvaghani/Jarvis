"""Offline pilot: generated public speech, existing local ASR only, no playback/capture.

Run as a module. CPU/GPU configurations are isolated in sequential child processes.
The report contains timing/resource metadata and exact-match flags, never recordings.
"""
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / 'artifacts/realtime-voice'
TEXT = 'Jarvis open calculator.'


def child(device):
    import psutil
    import numpy as np
    from scipy.io import wavfile
    from jarvis.whisper_backend import load_model
    from jarvis.audio import command_text, ASR_PROMPT
    config = json.loads((BASE / 'config/config.json').read_text(encoding='utf-8'))
    rate, audio = wavfile.read(OUT / 'public-fixture.wav')
    assert rate == 16000 and audio.ndim == 1
    process = psutil.Process()
    options = dict(config['whisper'], device=device,
        compute_type='int8' if device == 'cpu' else 'int8_float16')
    start = time.perf_counter()
    model = load_model(BASE / config['model_path'], options)
    load_seconds = time.perf_counter() - start
    rows = []
    for _ in range(3):
        started = time.perf_counter()
        cpu = process.cpu_times()
        segments, info = model.transcribe(audio, language='en', beam_size=5, temperature=0,
            condition_on_previous_text=False, word_timestamps=True, vad_filter=False,
            no_speech_threshold=.6, log_prob_threshold=-1., compression_ratio_threshold=2.4,
            initial_prompt=ASR_PROMPT)
        text = ' '.join(s.text for s in segments)
        after = process.cpu_times()
        rows.append({'seconds': time.perf_counter()-started,
            'cpu_seconds': after.user+after.system-cpu.user-cpu.system,
            'exact_match': command_text(text) == command_text(TEXT),
            'public_fixture_hypothesis': text,
            'input_scope': 'Known synthesized public fixture only',
            'rss_bytes_sampled': process.memory_info().rss})
    values = sorted(row['seconds'] for row in rows)
    return {'device': device, 'precision': options['compute_type'],
        'decode_options': 'Production final decode options including ASR_PROMPT',
        'model': config['model_path'], 'audio_seconds': len(audio)/16000,
        'load_seconds': load_seconds, 'samples': rows,
        'p50_seconds': statistics.median(values), 'worst_seconds': max(values),
        'p95_seconds': None, 'note': 'Three-sample pilot; insufficient for a reliable p95. RSS sampled, not peak.'}


def main():
    if len(sys.argv) > 1:
        try:
            result = child(sys.argv[1])
        except Exception as exc:
            result = {'device': sys.argv[1], 'error_type': type(exc).__name__, 'passed': False}
        print(json.dumps(result))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    from scipy.signal import resample_poly
    from scipy.io import wavfile
    import numpy as np
    from jarvis.kokoro_speech import load_voice, synthesize
    voices = BASE / 'models/voices/kokoro'
    voice = load_voice(voices / 'kokoro-v1.0.onnx', voices / 'voices-v1.0.bin')
    audio, rate = synthesize(voice, TEXT, {'voice': 'am_michael'})
    wavfile.write(OUT / 'public-fixture.wav', 16000, resample_poly(audio, 16000, rate).astype(np.float32))
    del voice

    report = {'date': '2026-10-23 IST', 'scope': 'Generated public English sentence; no microphone/playback or multilingual corpus. Application regression suite may run concurrently; this is not an isolated contention benchmark.', 'configurations': []}
    for device in ('cpu', 'cuda'):
        result = subprocess.run([sys.executable, '-m', 'scripts.verification.benchmark_realtime_voice', device],
            cwd=BASE, capture_output=True, text=True, timeout=300,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            report['configurations'].append(json.loads(result.stdout.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            report['configurations'].append({'device': device, 'error': 'child_failed', 'exit_code': result.returncode})
        (OUT / 'asr-pilot.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
