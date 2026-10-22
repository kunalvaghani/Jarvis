"""Continuous capture, Silero speech detection, and independent CUDA decoding.

Whisper is chunk based. Rolling hypotheses update once a second; superseded
partials are coalesced while final segments and window boundaries are ordered.
"""
from collections import deque
from dataclasses import dataclass, field
import math
from pathlib import Path
import queue
import re
import threading
import time
import uuid
from .whisper_backend import settings


def workers_alive(listener):
    """A stopped capture thread may still own a stuck native CUDA decoder."""
    return bool(listener and any(worker is not None and worker.is_alive()
        for worker in (getattr(listener, 'thread', None), getattr(listener, 'decoder', None))))

ASR_PROMPT = "Jarvis, Spotify, YouTube, Notepad, Calculator, File Explorer, Python."
# Ends hands-free writing; matched alone or at the end of a phrase ("... see you tomorrow. Stop writing.").
STOP_WRITING = re.compile(r"(?:^|[\s,.!?]+)(?:(?:hey |ok |okay )?jarvis[, ]+)?(?:stop|end|finish|quit) (?:writing|dictating|dictation|typing)"
                          r"(?: now| please| jarvis)?[.!?]*$|^(?:that'?s all|i'?m done|done writing)[.!?]*$", re.I)


@dataclass
class DecodeJob:
    utterance: int
    offset: float
    audio: object
    final: bool = False
    rollover: bool = False
    playback: bool = False
    references: tuple = ()
    write: bool = False  # Spoken while the push-to-write keys were held: typed, not a command.
    session: int = 0
    queued_at: float = field(default_factory=time.monotonic)


class DecodeQueue:
    def __init__(self, limit=12):
        if type(limit) is not int or not 1<=limit<=128:
            raise ValueError('Whisper decode queue limit must be between 1 and 128')
        self.items = deque()
        self.lock = threading.Condition()
        self.limit = limit

    def put(self, job):
        if (not isinstance(job, DecodeJob) or type(job.utterance) is not int or not 0<=job.utterance<2**63
                or type(job.session) is not int or not 0<=job.session<2**63
                or type(job.offset) not in (int,float) or not math.isfinite(job.offset) or job.offset<0
                or type(job.queued_at) not in (int,float) or not math.isfinite(job.queued_at) or job.queued_at < 0
                or any(type(value) is not bool for value in (job.final,job.rollover,job.playback,job.write))):
            raise ValueError('Invalid Whisper decode job metadata')
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
                 playback=None, input_filter=None, references=None, command_cleanup=None,
                 push_to_write=None, writer=None, input_update=None):
        self.model_path, self.device = Path(model_path), device
        self.engine, self.report = engine, report
        self.options = settings(options)
        self.activate_on_start = activate_on_start
        self.muted = muted or (lambda: False)
        self.playback = playback or (lambda: False)
        self.input_update = input_update
        self.latest_transcript = None
        self.language = "en"
        self.input_filter = input_filter
        self.command_cleanup = command_cleanup
        self.push_to_write, self.writer = push_to_write, writer
        self.references = references or (lambda: ())
        self.stop_event = threading.Event()
        from .pcm_ring import CaptureQueue
        self.audio = CaptureQueue()
        self.overflow = threading.Event()
        self.jobs = DecodeQueue()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.decoder = None
        self.capture_started = False
        self.last_audio = time.monotonic()
        self.decode_started = None
        self.error = None
        self.error_type = None
        self.duplicate_jobs = 0
        self.trace_id = uuid.uuid4().hex
        self.decode_metrics = deque(maxlen=128)  # Timing metadata only; no transcript/audio retention.

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        with self.jobs.lock:
            self.jobs.items.clear()
            self.jobs.lock.notify_all()
        while True:
            try:self.audio.get_nowait()
            except queue.Empty:break

    def _fail(self, code, exc=None):
        codes = {'capture_failure','decode_failure','decoder_stalled','model_missing',
            'cuda_unavailable','cuda_libraries_missing'}
        self.error = code if code in codes else 'capture_failure'
        self.error_type = type(exc).__name__ if exc is not None and type(exc).__module__ == 'builtins' else None
        self.report('fatal', 'Voice input unavailable ('+self.error+'); microphone off. Typed input remains available.')

    def health(self):
        return {'trace_id':self.trace_id,'error':self.error,'error_type':self.error_type,'capture_started':self.capture_started,
            'capture_alive':self.thread.is_alive(), 'decoder_alive':bool(self.decoder and self.decoder.is_alive()),
            'stopping':self.stop_event.is_set(), 'audio_backlog':self.audio.qsize(),
            'decode_backlog':len(self.jobs.items), 'duplicate_jobs':self.duplicate_jobs,
            'last_decode': self.decode_metrics[-1] if self.decode_metrics else None}

    def _decode(self, model):
        from .voice_runtime import Stabilizer, LanguageTracker, repetitive_hypothesis
        stabilizer = Stabilizer()
        languages = LanguageTracker(self.options["language_confidence"], self.options["language_confirmations"])
        assembler = TranscriptAssembler()
        finalized = -1  # Capture emits monotonically increasing utterance IDs.
        try:
            while not self.stop_event.is_set():
                job = self.jobs.get()
                if job is None:
                    continue
                if job.utterance <= finalized:
                    self.duplicate_jobs += 1
                    continue
                if job.final:
                    finalized = job.utterance  # Final/late-partial retransmissions cannot replay an effect.
                self.decode_started = time.monotonic()
                started = self.decode_started
                language = self.options.get("language", "en")
                segments, info = model.transcribe(
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
                self.decode_metrics.append({'session_id': self.trace_id, 'utterance_id': job.utterance,
                    'final': job.final, 'decode_seconds': time.monotonic() - started,
                    'queue_seconds': max(0., started - job.queued_at), 'audio_offset': job.offset})
                if self.stop_event.is_set():
                    break
                if self.muted():
                    continue
                text = assembler.merge(job, words)
                if repetitive_hypothesis(text):
                    if job.final:
                        self.report('warning', 'Speech recognition repeated itself; no command was sent. Please repeat.')
                    continue
                if job.write:
                    discarded = getattr(self.push_to_write, 'discarded', ())
                    if job.final and text.strip() and self.writer and job.session not in discarded:
                        text = text.strip()
                        if getattr(self.push_to_write, 'latched', False):
                            # Hands-free writing: "stop writing" (alone or at the end) ends it and isn't typed.
                            stop = STOP_WRITING.search(text)
                            if stop:
                                text = text[:stop.start()].rstrip(' ,')
                            self.push_to_write.last_write = time.monotonic()
                            if text:
                                self.report("final", text)
                                self.writer(text, job.session)
                            if stop:
                                self.push_to_write.latch(False)
                            continue
                        self.report("final", text)
                        self.writer(text, job.session)
                    continue
                accepted = (self.input_update(text, job.final, job.utterance, job.playback,
                    job.references, len(job.audio) / 16000 if job.audio is not None else 0)
                    if self.input_update else
                    self.input_filter(text, job.playback, job.references) if self.input_filter else command_text(text))
                if accepted is None:
                    continue
                self.language = languages.update(text, getattr(info, 'language', None),
                    getattr(info, 'language_probability', 0))
                event = stabilizer.update(self.trace_id, job.utterance, text, job.final, self.language)
                self.latest_transcript = event
                self.report('voice_transcript', event)
                if event['stable'] and not job.final:
                    # Local category preparation only: no model, network or tool calls.
                    from .commands import parse
                    try:
                        category = parse(command_text(event['stable'])).kind
                    except ValueError:
                        category = 'conversation'
                    self.report('voice_prepared', {'session_id': self.trace_id,
                        'utterance_id': job.utterance, 'category': category})
                self.report("final" if job.final else "partial", accepted if job.playback else text)
                if job.final and self.command_cleanup:
                    accepted = self.command_cleanup.clean(accepted, self.engine,
                        lambda: self.stop_event.is_set() or self.muted())
                if self.stop_event.is_set():
                    break
                if self.muted():
                    continue
                self.engine.feed(accepted, final=job.final, raw=text)
        except Exception as exc:
            self._fail('decode_failure', exc)
            self.stop_event.set()
        finally:
            self.decode_started = None

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
            from scipy.signal import resample_poly
            from .whisper_backend import load_model
            self.report("state", "Loading local Whisper…")
            model = load_model(self.model_path, self.options)
            from .whisper_backend import CoordinatedWhisper
            if isinstance(model, CoordinatedWhisper):
                model.cancelled = self.stop_event.is_set
            from faster_whisper.vad import get_vad_model
            if self.stop_event.is_set():
                return
            # Inference exposes missing CUDA DLLs before microphone capture.
            warmup, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language="en", beam_size=1)
            list(warmup)
            if self.stop_event.is_set():
                return
            if not getattr(getattr(model, 'model', None), 'is_multilingual', True) and self.options['language'] != 'en':
                self.report('warning', 'Installed Whisper is English-only; multilingual ASR needs an approved local multilingual model.')
                self.options['language'] = 'en'
            vad = get_vad_model()
            self.decoder = threading.Thread(target=self._decode, args=(model,), daemon=True)
            self.decoder.start()
            device = sd.query_devices(self.device, "input")
            rate = int(device["default_samplerate"])
            divisor = math.gcd(rate, 16000)
            self.audio.configure(rate)

            def callback(data, frames, timing, status):
                if self.stop_event.is_set():
                    return
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
            writing, was_held, session = False, False, 0
            active_playback = False
            active_references = ()
            captured = np.empty(0, dtype=np.float32)
            history = np.empty(0, dtype=np.float32)
            interval = float(self.options.get("partial_interval_seconds", 1.0))
            silence = float(self.options.get("silence_seconds", 0.8))
            threshold = float(self.options.get("vad_threshold", 0.45))
            vad_elapsed, speech = .1, False
            with sd.InputStream(samplerate=rate, blocksize=int(rate * self.options["frame_ms"] / 1000), device=self.device,
                                dtype="float32", channels=1, callback=callback):
                self.capture_started = True
                self.last_audio = time.monotonic()
                self.report("backend", f"Whisper {self.options.get('model', 'small')} · {model.model.device} · {model.model.compute_type} · {device['name']}")
                if self.activate_on_start:
                    self.engine.activate()
                else:
                    self.report("state", "Listening for Jarvis · local Whisper")
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
                    held = bool(self.push_to_write is not None and self.push_to_write.active.is_set())
                    if held:
                        session = self.push_to_write.session
                    if was_held and not held and active and writing:
                        # Keys released mid-sentence: type what was said so far right away.
                        self.jobs.put(DecodeJob(utterance, offset, np.concatenate((captured, block)), final=True,
                                                write=True, session=session))
                        active = writing = False
                        captured = np.empty(0, dtype=np.float32)
                        history = np.empty(0, dtype=np.float32)
                        was_held = held
                        continue
                    was_held = held
                    history = np.concatenate((history, block))[-16384:]
                    # Keep the original ~10 Hz VAD cost while capture uses 32 ms frames.
                    # The installed VAD wrapper recomputes its recurrent history per call.
                    vad_elapsed += len(block) / 16000
                    if vad_elapsed >= .096:
                        padded = np.pad(history, (0, (-len(history)) % 512))
                        probabilities = np.asarray(vad(padded)).reshape(-1)
                        speech = bool(np.max(probabilities[-4:]) >= threshold)
                        vad_elapsed = 0.
                    if not active:
                        if not speech:
                            continue
                        active = True
                        writing = held
                        active_playback = block_playback
                        active_references = tuple(block_references)
                        utterance += 1
                        captured = history.copy()
                        offset, silent, next_partial = 0.0, 0.0, interval
                    else:
                        captured = np.concatenate((captured, block))
                        writing = writing or held
                        active_playback = active_playback or block_playback
                        active_references = tuple(dict.fromkeys(active_references + tuple(block_references)))[-8:]
                    silent = 0.0 if speech else silent + len(block) / 16000
                    duration = len(captured) / 16000
                    latest = self.latest_transcript
                    endpoint = silence
                    if self.options['adaptive_endpointing']:
                        from .voice_runtime import endpoint_delay
                        current = latest if latest and latest['utterance_id'] == utterance else {}
                        endpoint = endpoint_delay(self.options['endpoint_mode'], current.get('text', ''),
                            bool(current.get('stable')), writing, silence)
                    if offset + duration >= self.options['max_utterance_seconds']:
                        raise RuntimeError('Utterance duration limit exceeded; no command committed.')
                    if silent >= endpoint:
                        self.jobs.put(DecodeJob(utterance, offset, captured.copy(), final=True, playback=active_playback,
                                                references=active_references, write=writing, session=session))
                        active = writing = False
                        captured = np.empty(0, dtype=np.float32)
                        history = np.empty(0, dtype=np.float32)
                    elif duration >= 20.0:
                        self.jobs.put(DecodeJob(utterance, offset, captured.copy(), rollover=True, playback=active_playback,
                                                references=active_references, write=writing, session=session))
                        captured = captured[16 * 16000:]
                        offset += 16.0
                        next_partial = len(captured) / 16000 + interval
                    elif duration >= next_partial and not writing and self.options['streaming_enabled']:
                        # No partial decoding while writing: only finished phrases are typed.
                        self.jobs.put(DecodeJob(utterance, offset, captured.copy(), playback=active_playback, references=active_references))
                        next_partial = duration + interval
        except Exception as exc:
            self._fail(getattr(exc,'code','capture_failure'), exc)
        finally:
            self.stop_event.set()
            if self.decoder:
                self.decoder.join(timeout=2.)
                if self.decoder.is_alive():
                    self._fail('decoder_stalled')
            if hasattr(self.audio, 'close'):
                self.audio.close()
            self.report("listener_stopped", "Microphone off")
