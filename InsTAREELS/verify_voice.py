"""Generate a synthetic Heart voice preview without using the speaker or microphone."""
import json
from pathlib import Path
import time
import wave
from datetime import date
import numpy as np
from jarvis.kokoro_speech import synthesize, load_voice

base = Path(__file__).resolve().parent
started = time.monotonic()
voice = load_voice(base / "models/voices/kokoro/kokoro-v1.0.onnx", base / "models/voices/kokoro/voices-v1.0.bin")
loaded = time.monotonic() - started
started = time.monotonic()
text = "Good morning, sir. Your workspace is ready. I can help you find a project, check the weather, or continue your work. Just tell me what you would like to do."
audio, rate = synthesize(voice, text, {"voice": "af_heart", "speed": 1.0})
elapsed = time.monotonic() - started
path = base / "artifacts/jarvis-heart-preview.wav"
with wave.open(str(path), "wb") as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(rate)
    output.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
evidence = {"date": date.today().isoformat(), "voice": "af_heart", "text": text,
    "load_seconds": round(loaded, 3), "synthesis_seconds": round(elapsed, 3),
    "audio_seconds": round(len(audio) / rate, 3), "sample_rate": rate,
    "kind": "Actual local synthesis; synthetic text; no speaker playback or subjective quality rating"}
(base / "artifacts/kokoro-voice-check.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(json.dumps(evidence))
