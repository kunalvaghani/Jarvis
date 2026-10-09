"""Continuous capture, Silero speech detection, and independent CUDA decoding.

Whisper is chunk based. Rolling hypotheses update once a second; superseded
partials are coalesced while final segments and window boundaries are ordered.
"""
from collections import deque
from dataclasses import dataclass
import math
from pathlib import Path
import queue
import re
import threading
import time

ASR_PROMPT = "Jarvis, Spotify, YouTube, Notepad, Calculator, File Explorer, Python."


@dataclass
class DecodeJob:
    utterance: int
    offset: float
    audio: object
    final: bool = False
    rollover: bool = False
    playback: bool = False
    references: tuple = ()


class DecodeQueue:
    def __init__(self, limit=12):
        self.items = deque()
        self.lock = threading.Condition()
        self.limit = limit

    def put(self, job):
        with self.lock:
            if self.items:
                last = self.items[-1]
                if (last.utterance == job.utterance and last.offset == job.offset
                        and not last.final and not last.rollover):
                    self.items.pop()
            if len(self.items) >= self.limit:
                raise RuntimeError("Whisper cannot keep up; listening stopped instead of executing stale commands.")
            self.items.append(job)
            self.lock.notify()

    def get(self):
        with self.lock:
            if not self.items:
                self.lock.wait(0.2)
            return self.items.popleft() if self.items else None


def command_text(text):
    # Whisper adds casing and punctuation. Preserve extension dots inside words.
    text = text.replace("’", "'")
    text = re.sub(r"\b([a-z0-9_-]+)\.\s+(?=(?:text|txt|py|js|jsx|ts|tsx|json|html|css|md|yaml|yml|toml)\b)",
                  r"\1.", text, flags=re.I)
    text = re.sub(r"[.,!?;:]+(?=\s|$)", " ", text)
    return " ".join(text.lower().split())


class TranscriptAssembler:
    def __init__(self):
        self.utterance = None
        self.prefix = []
        self.cutoff = -1.0

    def merge(self, job, words):
        if job.utterance != self.utterance:
            self.utterance = job.utterance
            self.prefix = []
            self.cutoff = -1.0
        remaining = [(job.offset + end, word) for end, word in words
                     if job.offset + end > self.cutoff + 0.05]
        text = " ".join(self.prefix + [word.strip() for _, word in remaining])
        if job.rollover:
            # Next window begins at +16s. Commit through +18s, retaining two
            # seconds of shared context before the first uncommitted word.
            committed = [(end, word) for end, word in remaining if end <= job.offset + 18.0]
            self.prefix.extend(word.strip() for _, word in committed)
            if committed:
                self.cutoff = committed[-1][0]
        return text


class Listener:
    def __init__(self, model_path, device, engine, report, options=None, activate_on_start=False, muted=None,
                 playback=None, input_filter=None, references=None, command_cleanup=None):
        self.model_path, self.device = Path(model_path), device
        self.engine, self.report = engine, report
        self.options = options or {}
        self.activate_on_start = activate_on_start
        self.muted = muted or (lambda: False)
        self.playback = playback or (lambda: False)
        self.input_filter = input_filter
        self.command_cleanup = command_cleanup
        self.references = references or (lambda: ())
        self.stop_event = threading.Event()
        self.audio = queue.Queue(maxsize=100)
        self.overflow = threading.Event()
        self.jobs = DecodeQueue()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.decoder = None
        self.capture_started = False
        self.last_audio = time.monotonic()
        self.decode_started = None

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _decode(self, model):
        assembler = TranscriptAssembler()
        try:
            while not self.stop_event.is_set():
                job = self.jobs.get()
                if job is None:
                    continue
                self.decode_started = time.monotonic()
                language = self.options.get("language", "en")
                segments, _ = model.transcribe(
                    job.audio, language=None if language == "auto" else language,
                    beam_size=5 if job.final else 3, temperature=0,
                    condition_on_previous_text=False, word_timestamps=True,
                    vad_filter=False, no_speech_threshold=0.6,
                    log_prob_threshold=-1.0, compression_ratio_threshold=2.4,
                    initial_prompt=ASR_PROMPT)
                words = []
                for segment in segments:
                    # Whisper treats high no_speech_prob as silence only when
                    # the transcript itself also has low log probability.
                    if segment.avg_logprob < -1.0:
                        continue
                    words.extend((word.end, word.word) for word in segment.words or [])
                self.decode_started = None
                if self.stop_event.is_set():
                    break
                if self.muted():
                    continue
                text = assembler.merge(job, words)
                accepted = self.input_filter(text, job.playback, job.references) if self.input_filter else command_text(text)
                if accepted is None:
                    continue
                self.report("final" if job.final else "partial", accepted if job.playback else text)
                if job.final and self.command_cleanup:
                    accepted = self.command_cleanup.clean(accepted, self.engine,
                        lambda: self.stop_event.is_set() or self.muted())
                if self.stop_event.is_set():
                    break
                if self.muted():
                    continue
                self.engine.feed(accepted, final=job.final)
        except Exception as exc:
            self.report("fatal", f"Whisper GPU decoding failed: {exc}")
            self.stop_event.set()

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
            from scipy.signal import resample_poly
            from .whisper_backend import load_model
            self.report("state", "Loading Whisper on GPU…")
            model = load_model(self.model_path, self.options)
            from faster_whisper.vad import get_vad_model
            if self.stop_event.is_set():
                return
            # Inference exposes missing CUDA DLLs before microphone capture.
            warmup, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language="en", beam_size=1)
            list(warmup)
            if self.stop_event.is_set():
                return
            vad = get_vad_model()
            self.decoder = threading.Thread(target=self._decode, args=(model,), daemon=True)
            self.decoder.start()
            device = sd.query_devices(self.device, "input")
            rate = int(device["default_samplerate"])
            divisor = math.gcd(rate, 16000)

            def callback(data, frames, timing, status):
                self.last_audio = time.monotonic()
                if status:
                    self.overflow.set()
                if self.muted():
                    return
                try:
                    self.audio.put_nowait((data[:, 0].copy(), bool(self.playback()), self.references()))
                except queue.Full:
                    self.overflow.set()

            utterance, offset, silent, next_partial = 0, 0.0, 0.0, 0.0
            active = False
            active_playback = False
            active_references = ()
            captured = np.empty(0, dtype=np.float32)
            history = np.empty(0, dtype=np.float32)
            interval = float(self.options.get("partial_interval_seconds", 1.0))
            silence = float(self.options.get("silence_seconds", 0.8))
            threshold = float(self.options.get("vad_threshold", 0.45))
            with sd.InputStream(samplerate=rate, blocksize=int(rate * 0.1), device=self.device,
                                dtype="float32", channels=1, callback=callback):
                self.capture_started = True
                self.last_audio = time.monotonic()
                self.report("backend", f"Whisper {self.options.get('model', 'small')} · {model.model.device} · {model.model.compute_type} · {device['name']}")
                if self.activate_on_start:
                    self.engine.activate()
                else:
                    self.report("state", "Listening for Jarvis · Whisper GPU")
                while not self.stop_event.is_set():
                    if self.overflow.is_set():
                        raise RuntimeError("Microphone overflow; listening stopped. Select another input device and restart.")
                    try:
                        block, block_playback, block_references = self.audio.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    self.last_audio = time.monotonic()
                    if self.muted():
                        active = False
                        captured = np.empty(0, dtype=np.float32)
                        history = np.empty(0, dtype=np.float32)
                        continue
                    self.report("level", min(100.0, float(np.sqrt(np.mean(block ** 2))) * 500))
                    if rate != 16000:
                        block = resample_poly(block, 16000 // divisor, rate // divisor).astype(np.float32)
                    history = np.concatenate((history, block))[-16384:]
                    padded = np.pad(history, (0, (-len(history)) % 512))
                    probabilities = np.asarray(vad(padded.copy())).reshape(-1)
                    speech = bool(np.max(probabilities[-4:]) >= threshold)
                    if not active:
                        if not speech:
                            continue
                        active = True
                        active_playback = block_playback
                        active_references = tuple(block_references)
                        utterance += 1
                        captured = history.copy()
                        offset, silent, next_partial = 0.0, 0.0, interval
                    else:
                        captured = np.concatenate((captured, block))
                        active_playback = active_playback or block_playback
                        active_references = tuple(dict.fromkeys(active_references + tuple(block_references)))[-8:]
                    silent = 0.0 if speech else silent + len(block) / 16000
                    duration = len(captured) / 16000
                    if silent >= silence:
                        self.jobs.put(DecodeJob(utterance, offset, captured.copy(), final=True, playback=active_playback, references=active_references))
                        active = False
                        captured = np.empty(0, dtype=np.float32)
                        history = np.empty(0, dtype=np.float32)
                    elif duration >= 20.0:
                        self.jobs.put(DecodeJob(utterance, offset, captured.copy(), rollover=True, playback=active_playback, references=active_references))
                        captured = captured[16 * 16000:]
                        offset += 16.0
                        next_partial = len(captured) / 16000 + interval
                    elif duration >= next_partial:
                        self.jobs.put(DecodeJob(utterance, offset, captured.copy(), playback=active_playback, references=active_references))
                        next_partial = duration + interval
        except Exception as exc:
            self.report("fatal", str(exc))
        finally:
            self.stop_event.set()
            if self.decoder:
                self.decoder.join()
            self.report("listener_stopped", "Microphone off")
