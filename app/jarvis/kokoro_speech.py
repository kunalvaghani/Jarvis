"""Free local Kokoro speech: natural phrasing played through one continuous stream.

The serving worker keeps a single audio output stream open. A synthesis thread
renders each phrase ahead of playback (with planned pauses and soft breaths from
natural_voice.py) into a buffer the stream plays gaplessly, so long replies never
stall between sentences and are never cut off by a total time limit. Requests can
be appended while earlier speech plays (answers spoken while still being written).
A "stop" line clears everything at once without restarting the model.

Protocol (JSON lines): request {"id", "text", "voice", "speed", "natural", "breaths"}
or {"stop": true}. Replies: {"ready"}, {"id", "progress"}, {"id", "started"},
{"id", "done", "audio_seconds"}, {"id", "error"}, {"stopped"}.
"""
import collections
import json
import math
import queue
import random
import sys
import threading
import time
from pathlib import Path


def speed(value):
    try:
        value = float(value)
        return min(1.2, max(.85, value)) if math.isfinite(value) else 1.0
    except (TypeError, ValueError):
        return 1.0


def synthesize(voice, text, options):
    """One phrase (or a whole short text) as audio; used directly and by the streaming worker."""
    from .natural_voice import voice_style, language_for
    selected = options.get("voice", "am_michael")
    style = voice_style(voice, selected)
    pacing = speed(options.get("speed", 1))
    adapter = getattr(voice, "_jarvis_speed_session", None)
    if adapter is not None:
        adapter.pacing = pacing
    audio, rate = voice.create(text, voice=style, speed=pacing, lang=language_for(selected))
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


def load_voice(model_path, voices_path, threads=4):
    import onnxruntime as ort
    from kokoro_onnx import Kokoro
    settings = ort.SessionOptions()
    settings.intra_op_num_threads = threads
    settings.inter_op_num_threads = 1
    native = ort.InferenceSession(str(model_path), sess_options=settings, providers=["CPUExecutionProvider"])
    session = SpeedSession(native)
    voice = Kokoro.from_session(session, str(voices_path))
    voice._jarvis_speed_session = session
    return voice


def render(voice, request, stop, emit_progress=lambda index: None, rng=None):
    """Yield (audio, rate) pieces for one request: breath, phrase, pause ... in speaking order."""
    import numpy as np
    from .natural_voice import plan, trim, finish, breath
    rng = rng or random.Random()
    natural = request.get("natural", True)
    phrases = plan(request["text"], speed(request.get("speed", 1)), rng, request.get("breaths", True)) if natural else None
    if not phrases:
        audio, rate = synthesize(voice, request["text"], request)
        yield np.asarray(audio, dtype=np.float32), rate
        return
    for index, phrase in enumerate(phrases):
        if stop.is_set():
            return
        audio, rate = synthesize(voice, phrase.text, {**request, "speed": phrase.speed})
        emit_progress(index)
        spoken = finish(trim(np.asarray(audio, dtype=np.float32), rate), rate, phrase.gain)
        parts = []
        if phrase.breath_before:
            parts += [breath(rate, rng, level=float(request.get("breath_level", .012))), np.zeros(int(rate * .06), np.float32)]
        parts += [spoken, np.zeros(int(rate * phrase.pause_after), np.float32)]
        yield np.concatenate(parts), rate


class Player:
    """One open output stream fed from a queue of audio pieces tagged with request ids."""
    def __init__(self, rate, events):
        import numpy as np
        import sounddevice as sd
        self.np, self.rate, self.events = np, rate, events
        self.pieces = collections.deque()
        self.lock = threading.Lock()
        self.current = None  # [id, audio, position]
        self.stream = sd.OutputStream(samplerate=rate, channels=1, dtype="float32", callback=self.callback,
                                      blocksize=int(rate * .04), latency="low")
        self.stream.start()

    def add(self, request_id, audio):
        with self.lock:
            self.pieces.append([request_id, audio, 0])

    def finish(self, request_id, seconds):
        with self.lock:
            self.pieces.append([request_id, None, seconds])  # End marker: report when reached.

    def clear(self):
        with self.lock:
            self.pieces.clear()
            self.current = None

    def callback(self, out, frames, timing, status):
        out.fill(0)
        filled = 0
        with self.lock:
            while filled < frames:
                if self.current is None:
                    if not self.pieces:
                        return
                    self.current = self.pieces.popleft()
                    request_id, audio, position = self.current
                    if audio is None:
                        self.events.put({"id": request_id, "done": True, "audio_seconds": round(position, 2)})
                        self.current = None
                        continue
                    if position == 0 and getattr(self, "started_id", None) != request_id:
                        self.started_id = request_id
                        self.events.put({"id": request_id, "started": True})
                request_id, audio, position = self.current
                take = min(frames - filled, len(audio) - position)
                out[filled:filled + take, 0] = audio[position:position + take]
                filled += take
                position += take
                self.current[2] = position
                if position >= len(audio):
                    self.current = None

    def close(self):
        self.stream.stop()
        self.stream.close()


def main():
    import numpy as np
    import sounddevice as sd
    request = json.load(sys.stdin)
    voice = load_voice(request["model"], request["voices"])
    audio, rate = synthesize(voice, request["text"], request)
    sd.play(np.asarray(audio, dtype=np.float32), rate, blocking=True)


def raise_priority():
    """Speech must not stutter when the planner keeps the CPU busy."""
    try:
        import ctypes
        kernel = ctypes.WinDLL("kernel32")
        kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x8000)  # ABOVE_NORMAL_PRIORITY_CLASS
    except (OSError, AttributeError):
        pass


def serve():
    import contextlib
    protocol = sys.stdout
    base = Path(__file__).resolve().parent.parent
    events = queue.Queue()
    requests = queue.Queue()
    epoch = [0]  # Incremented by "stop"; work from an older epoch is discarded.

    class Stale:
        """Event-like view: true once the request's epoch is no longer current."""
        def __init__(self, request):
            self.request = request

        def is_set(self):
            return self.request["_epoch"] != epoch[0]

    def writer():
        while True:
            row = events.get()
            if row is None:
                return
            protocol.write(json.dumps(row) + "\n")
            protocol.flush()
    threading.Thread(target=writer, daemon=True).start()
    try:
        raise_priority()
        with contextlib.redirect_stdout(sys.stderr):
            voice = load_voice(base / "models/voices/kokoro/kokoro-v1.0.onnx", base / "models/voices/kokoro/voices-v1.0.bin")
        player = Player(24000, events) if "--no-playback" not in sys.argv else None
        events.put({"ready": True})

        def synthesis():
            while True:
                request = requests.get()
                if request is None:
                    return
                stale = Stale(request)
                if stale.is_set():
                    continue
                total = 0.0
                try:
                    started = time.monotonic()
                    with contextlib.redirect_stdout(sys.stderr):
                        for audio, rate in render(voice, request, stale,
                                                  lambda index: events.put({"id": request["id"], "progress": index})):
                            if stale.is_set():
                                break
                            total += len(audio) / rate
                            if player is not None:
                                player.add(request["id"], audio)
                    if stale.is_set():
                        continue
                    if player is not None:
                        player.finish(request["id"], total)
                    else:
                        events.put({"id": request["id"], "done": True, "audio_seconds": round(total, 2),
                                    "synthesis_seconds": round(time.monotonic() - started, 3)})
                except Exception as exc:
                    events.put({"id": request.get("id"), "error": "Local voice failed: " + str(exc)})
        worker = threading.Thread(target=synthesis, daemon=True)
        worker.start()
        for line in sys.stdin:
            try:
                request = json.loads(line)
            except ValueError:
                continue
            if request.get("stop"):
                epoch[0] += 1
                while True:
                    try:
                        requests.get_nowait()
                    except queue.Empty:
                        break
                if player is not None:
                    player.clear()
                events.put({"stopped": True})
                continue
            request["_epoch"] = epoch[0]
            requests.put(request)
        requests.put(None)
    except Exception as exc:
        events.put({"error": "Local voice initialization failed: " + str(exc)})
    finally:
        events.put(None)
        time.sleep(.2)


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else main()
