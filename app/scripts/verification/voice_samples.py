"""Render Jarvis's natural voice with several male voices; save WAVs and measure them.

Each sample goes through the full natural pipeline (phrasing, pauses, breaths) and is
transcribed by the local Whisper model to compare intelligibility. Listen to the WAVs
in artifacts/media/voice-samples and set speech.voice in config/config.json.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import re
import sys
import threading
import time

import numpy as np

from jarvis.kokoro_speech import load_voice, render
from jarvis.paths import artifact_path

TEXT = ("Oh, nice, that worked on the first try! Honestly, that almost never happens, so let's enjoy it while it lasts. "
        "Here's the plan for today. First we'll tidy up the notes, then we'll look at that flaky login test.\n\n"
        "I'm sorry the build took so long earlier. Anyway, what would you like to tackle next?")
CANDIDATES = ["am_michael", "am_fenrir", "am_puck", "bm_george", "am_michael:60,am_fenrir:40",
              "am_michael:50,am_puck:50", "am_fenrir:50,am_puck:50"]


def words(text):
    return re.sub(r"[^a-z' ]", " ", text.lower()).split()


def error_rate(reference, hypothesis):
    ref, hyp = words(reference), words(hypothesis)
    rows = list(range(len(hyp) + 1))
    for i, word in enumerate(ref, 1):
        previous, rows[0] = rows[0], i
        for j, other in enumerate(hyp, 1):
            previous, rows[j] = rows[j], min(rows[j] + 1, rows[j - 1] + 1, previous + (word != other))
    return rows[-1] / max(1, len(ref))


def main():
    from scipy.io import wavfile
    base = Path(__file__).resolve().parents[2]
    out = base / 'artifacts/media/voice-samples'
    out.mkdir(parents=True, exist_ok=True)
    voice = load_voice(base / 'models/voices/kokoro/kokoro-v1.0.onnx', base / 'models/voices/kokoro/voices-v1.0.bin')
    from jarvis.whisper_backend import load_model
    config = json.loads((base / 'config/config.json').read_text())
    whisper = load_model(base / config['model_path'], config['whisper'])  # Sets up the CUDA libraries.
    rows = []
    for spec in CANDIDATES:
        started = time.monotonic()
        pieces = [audio for audio, rate in render(voice, {'text': TEXT, 'voice': spec, 'speed': 1.0}, threading.Event(),
                                                  rng=random.Random(7))]
        seconds = time.monotonic() - started
        audio = np.concatenate(pieces)
        name = spec.replace(':', '').replace(',', '+')
        path = out / (name + '.wav')
        wavfile.write(path, 24000, (audio * 32767).astype(np.int16))
        segments, _ = whisper.transcribe(audio, language='en', beam_size=5)
        heard = ' '.join(segment.text for segment in segments)
        rows.append({'voice': spec, 'file': str(path.relative_to(base)).replace('\\', '/'),
                     'audio_seconds': round(len(audio) / 24000, 2), 'synthesis_seconds': round(seconds, 2),
                     'real_time_factor': round(seconds / (len(audio) / 24000), 2),
                     'word_error_rate': round(error_rate(TEXT, heard), 3)})
        print(json.dumps(rows[-1]), flush=True)
    report = {'date': datetime.now(timezone.utc).isoformat(), 'text': TEXT, 'samples': rows,
              'note': 'Intelligibility by local Whisper medium.en; naturalness needs a human listener.'}
    artifact_path(base, 'voice-samples.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    sys.exit(main())
