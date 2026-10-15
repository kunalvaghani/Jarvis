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
        from .pcm_ring import PCMBuffer
        self.pcm = PCMBuffer(rate * 60)
        self.pieces = collections.deque()
        self.lock = threading.Lock()
        self.current = None  # [id, audio, position]
        try:
            self.stream = sd.OutputStream(samplerate=rate, channels=1, dtype="float32", callback=self.callback,
                                          blocksize=int(rate * .02), latency="low")
            self.stream.start()
        except BaseException:
            self.pcm.close()
            raise

    def add(self, request_id, audio, stop=None):
        if (not isinstance(audio,self.np.ndarray) or audio.ndim!=1 or not audio.size
                or audio.size>self.rate*30 or not self.np.isfinite(audio).all()):
            raise ValueError('Invalid or oversized local voice audio')
        with self.lock:
            if stop is not None and stop.is_set():return False
            if getattr(self,'stream',None) is not None and not self.stream.active:
                raise OSError('Audio output unavailable')
            if len(self.pieces)>=128:raise BufferError('Local voice playback buffer full')
            self.pieces.append([request_id, self.pcm.put(audio) if hasattr(self,'pcm') else audio, 0])
            return True

    def finish(self, request_id, seconds, stop=None):
        with self.lock:
            if stop is not None and stop.is_set():return
            if len(self.pieces)>=128:raise BufferError('Local voice playback buffer full')
            self.pieces.append([request_id, None, seconds])  # End marker: report when reached.

    def clear(self):
        with self.lock:
            if hasattr(self, 'pcm'):
                for row in list(self.pieces) + ([self.current] if self.current else []):
                    if row[1] is not None:self.pcm.release(row[1])
            self.pieces.clear()
            self.current = None

    def discard(self, request_ids):
        with self.lock:
            if hasattr(self, 'pcm'):
                for row in list(self.pieces) + ([self.current] if self.current else []):
                    if row[0] in request_ids and row[1] is not None:self.pcm.release(row[1])
            self.pieces=collections.deque(row for row in self.pieces if row[0] not in request_ids)
            if self.current is not None and self.current[0] in request_ids:self.current=None

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
                        self.played_samples = 0
                        self.events.put({"id": request_id, "started": True})
                request_id, audio, position = self.current
                size = self.pcm.size(audio) if hasattr(self,'pcm') else len(audio)
                take = min(frames - filled, size - position)
                out[filled:filled + take, 0] = self.pcm.read(audio,position,take) if hasattr(self,'pcm') else audio[position:position + take]
                filled += take
                position += take
                self.current[2] = position
                self.played_samples=getattr(self,'played_samples',0)+take
                if self.played_samples>=self.rate:
                    self.played_samples%=self.rate
                    self.events.put({'id':request_id,'playback':True})
                if position >= size:
                    if hasattr(self,'pcm'):self.pcm.release(audio)
                    self.current = None

    def close(self):
        self.stream.stop()
        self.stream.close()
        self.clear()
        self.pcm.close()


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


def queued_batch(request, requests):
    """Join available text in order; retain the first excluded row, including EOF."""
    batch = [request]
    combined = str(request.get('text', ''))
    held, has_held = None, False
    while len(batch) < 8:
        try:
            candidate = requests.get_nowait()
        except queue.Empty:
            break
        if (candidate is None or candidate['_epoch'] != request['_epoch']
                or len(combined)+len(candidate.get('text', ''))+1 > 1000):
            held, has_held = candidate, True
            break
        batch.append(candidate)
        combined += ' ' + candidate.get('text', '')
    return {**request, 'text': combined}, batch, held, has_held


def serve(loader=None, renderer=None, coalesce=False):
    import contextlib
    protocol = sys.stdout
    base = Path(__file__).resolve().parent.parent
    events = queue.Queue()
    requests = queue.Queue(maxsize=64)
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
    writer_thread=threading.Thread(target=writer, daemon=True)
    writer_thread.start()
    player=None
    worker=None
    try:
        raise_priority()
        with contextlib.redirect_stdout(sys.stderr):
            voice = loader() if loader else load_voice(base / "models/voices/kokoro/kokoro-v1.0.onnx", base / "models/voices/kokoro/voices-v1.0.bin")
        player = Player(24000, events) if "--no-playback" not in sys.argv else None
        events.put({"ready": True})

        def synthesis():
            empty = object()
            held = empty
            while True:
                request = requests.get() if held is empty else held
                held = empty
                if request is None:
                    return
                stale = Stale(request)
                if stale.is_set():
                    continue
                batch = [request]
                if coalesce:
                    request, batch, candidate, has_held = queued_batch(request, requests)
                    held = candidate if has_held else empty
                total = 0.0
                committed = False
                try:
                    started = time.monotonic()
                    with contextlib.redirect_stdout(sys.stderr):
                        for audio, rate in (renderer or render)(voice, request, stale,
                                                  lambda index: events.put({"id": request["id"], "progress": index})):
                            if stale.is_set():
                                break
                            total += len(audio) / rate
                            if player is not None:
                                player.add(request["id"], audio, stale)
                                committed = True
                            events.put({'id': request['id'], 'audio_ready': True,
                                        'synthesis_seconds': round(time.monotonic()-started, 3)})
                    if stale.is_set():
                        continue
                    if player is not None:
                        for index, row in enumerate(batch):
                            player.finish(row['id'], total if index == 0 else 0., stale)
                    else:
                        for index, row in enumerate(batch):
                            events.put({"id": row['id'], "done": True, "audio_seconds": round(total, 2) if index == 0 else 0.,
                                        "synthesis_seconds": round(time.monotonic() - started, 3),
                                        "coalesced_ids": [part['id'] for part in batch]})
                except Exception as exc:
                    if player is not None:player.discard({row['id'] for row in batch})
                    for row in batch:
                        events.put({"id": row.get("id"), "error": "synthesis_or_output_failure",
                                    "safe_to_retry": not committed})
        worker = threading.Thread(target=synthesis, daemon=True)
        worker.start()
        last_id=0
        for line in sys.stdin:
            try:
                if len(line)>65536:continue
                request = json.loads(line)
            except (ValueError,RecursionError):
                continue
            if not isinstance(request,dict):continue
            if request.get("stop") is True:
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
            request_id=request.get('id')
            if type(request_id) is not int or not 0<request_id<2**63:continue
            if request_id<=last_id:
                continue  # A retransmitted request id cannot replay audio.
            text=request.get('text')
            if not isinstance(text,str) or len(text)>20000:
                events.put({'id':request_id,'error':'invalid_request'});continue
            last_id=request_id
            if not text.strip():
                events.put({'id':request_id,'done':True,'audio_seconds':0.});continue
            request["_epoch"] = epoch[0]
            try:requests.put_nowait(request)
            except queue.Full:events.put({'id':request_id,'error':'request_queue_full'})
        # EOF must not discard output from an already accepted quick request.
        # Long/stuck synthesis remains bounded and is cancelled, never replayed.
        try:requests.put(None,timeout=.2)
        except queue.Full:epoch[0]+=1
        worker.join(timeout=5.)
        if worker.is_alive():epoch[0]+=1
    except Exception as exc:
        events.put({"error": "initialization_failure"})
    finally:
        epoch[0]+=1
        if player is not None:
            player.clear()
            try:player.close()
            except Exception:pass
        events.put(None)
        writer_thread.join(timeout=1.)


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else main()
