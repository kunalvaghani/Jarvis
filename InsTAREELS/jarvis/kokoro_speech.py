"""Free local Kokoro speech: whole phrases, one continuous playback buffer."""
import json
import math
import sys
import time
from pathlib import Path


def speed(value):
    try:
        value = float(value)
        return min(1.2, max(.85, value)) if math.isfinite(value) else 1.0
    except (TypeError, ValueError):
        return 1.0


def synthesize(voice, text, options):
    selected = options.get("voice", "af_heart")
    if selected not in voice.voices:
        raise ValueError("Selected Kokoro voice is unavailable: " + str(selected))
    language = "en-gb" if selected.startswith("b") else "en-us"
    pacing = speed(options.get("speed", 1))
    adapter = getattr(voice, "_jarvis_speed_session", None)
    if adapter is not None:
        adapter.pacing = pacing
    # Let Kokoro keep phrase context and split only at its phoneme limit.
    # Concatenate every model chunk before playback, avoiding synthesis gaps.
    audio, rate = voice.create(text, voice=selected, speed=pacing, lang=language)
    if not audio.size:
        raise ValueError("Kokoro produced no audio.")
    return audio, rate


class SpeedSession:
    """Bridge kokoro-onnx 0.4.9's int speed to the v1.1 export's float input."""
    def __init__(self, session):
        self.session = session
        self.pacing = 1.0

    def __getattr__(self, name):
        return getattr(self.session, name)

    def run(self, names, inputs):
        import numpy as np
        inputs = dict(inputs)
        kind = next(item.type for item in self.session.get_inputs() if item.name == "speed")
        if kind != "tensor(float)":
            raise ValueError("Unexpected Kokoro speed input type: " + kind)
        inputs["speed"] = np.array([self.pacing], dtype=np.float32)
        return self.session.run(names, inputs)


def load_voice(model_path, voices_path):
    import onnxruntime as ort
    from kokoro_onnx import Kokoro
    settings = ort.SessionOptions()
    settings.intra_op_num_threads = 4
    settings.inter_op_num_threads = 1
    native = ort.InferenceSession(str(model_path), sess_options=settings, providers=["CPUExecutionProvider"])
    session = SpeedSession(native)
    voice = Kokoro.from_session(session, str(voices_path))
    voice._jarvis_speed_session = session
    return voice


def main():
    import numpy as np
    import sounddevice as sd
    request = json.load(sys.stdin)
    voice = load_voice(request["model"], request["voices"])
    audio, rate = synthesize(voice, request["text"], request)
    sd.play(np.asarray(audio, dtype=np.float32), rate, blocking=True)


def serve():
    import contextlib
    import numpy as np
    import sounddevice as sd
    protocol = sys.stdout
    base = Path(__file__).resolve().parent.parent
    try:
        with contextlib.redirect_stdout(sys.stderr):
            voice = load_voice(base / "models/voices/kokoro/kokoro-v1.0.onnx", base / "models/voices/kokoro/voices-v1.0.bin")
        protocol.write(json.dumps({"ready": True}) + "\n")
        protocol.flush()
        for line in sys.stdin:
            try:
                request = json.loads(line)
                started = time.monotonic()
                with contextlib.redirect_stdout(sys.stderr):
                    audio, rate = synthesize(voice, request["text"], request)
                elapsed = time.monotonic() - started
                if "--no-playback" not in sys.argv:
                    sd.play(np.asarray(audio, dtype=np.float32), rate, blocking=True)
                result = {"done": True, "synthesis_seconds": round(elapsed, 3), "audio_seconds": round(len(audio) / rate, 3)}
            except Exception as exc:
                result = {"error": "Local voice failed: " + str(exc)}
            protocol.write(json.dumps(result) + "\n")
            protocol.flush()
    except Exception as exc:
        protocol.write(json.dumps({"error": "Local voice initialization failed: " + str(exc)}) + "\n")
        protocol.flush()
    finally:
        sd.stop()


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else main()
