"""Cancellable, local Windows speech: natural, continuous Kokoro voice (Piper for Hindi)."""
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import math
import time
import uuid


class VoiceStartupError(RuntimeError):
    """No text has been submitted, so selecting another backend is safe."""


def spoken_text(answer):
    """Turn transcript formatting into prose while retaining words and pauses."""
    from .natural_voice import speech_unicode
    answer = speech_unicode(answer)
    answer = re.split(r"\n\s*Sources:\s*\n", answer, maxsplit=1, flags=re.I)[0]
    answer = re.sub(r"```[\s\S]*?```", " The code is in the transcript. ", answer)
    answer = re.sub(r"!?\[([^\]]+)\]\([^\n)]+\)", r"\1", answer)
    answer = re.sub(r"https?://\S+", "", answer)
    answer = re.sub(r"\[\d+\]", "", answer)
    answer = re.sub(r"(?m)^\s*(?:#{1,6}\s+|>\s*|[-+*]\s+|\d{1,2}[.)]\s+)", "", answer)
    answer = re.sub(r"(?m)^\s*[-=]{3,}\s*$", "", answer)
    answer = re.sub(r"[`*~]", "", answer)
    answer = re.sub(r"(?<!\w)_+|_+(?!\w)", "", answer)
    # Paragraph breaks are kept (they become longer pauses); single line breaks end a phrase.
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", answer):
        paragraph = re.sub(r"\n+", ". ", paragraph)
        paragraph = re.sub(r"([.!?।:])\s*\.", r"\1", paragraph)
        paragraph = re.sub(r"\s+([,.!?।])", r"\1", paragraph)
        paragraph = " ".join(paragraph.split())
        if paragraph:
            paragraphs.append(paragraph)
    answer = "\n\n".join(paragraphs)
    if len(answer) > SPOKEN_LIMIT:
        # A safety bound only; ordinary long answers are spoken in full.
        boundary = max(answer.rfind(mark, 0, SPOKEN_LIMIT) for mark in ".!?।")
        answer = answer[:boundary + 1] if boundary > SPOKEN_LIMIT // 2 else answer[:SPOKEN_LIMIT].rsplit(" ", 1)[0] + "."
    return answer


SPOKEN_LIMIT = 20000


def speech_parameters(options):
    """Bound voice pacing so malformed settings cannot create runaway audio."""
    def number(name, default, low, high):
        try:
            value = float(options.get(name, default))
            return min(high, max(low, value)) if math.isfinite(value) else default
        except (TypeError, ValueError):
            return default
    return {"length_scale": number("length_scale", 1.05, .7, 1.5),
            "noise_scale": number("noise_scale", .667, 0, 1),
            "noise_w_scale": number("noise_w_scale", .8, 0, 1),
            "sentence_silence": number("sentence_silence", .18, 0, .6)}


def playback_timeout(text):
    # Slow speech at about 100 words/minute, plus bounded model startup time.
    return min(240, max(60, len(text.split()) * .6 + 30))


def speech_language(answer, preference="auto"):
    if preference in {"en", "hi"}:
        return preference
    if re.search(r"[\u0900-\u097f]", answer):
        return "hi"
    roman_hindi = re.findall(r"\b(?:hai|hain|kya|kyun|kaise|mujhe|aap|yeh|pani|batao|hota|hoti)\b", answer, re.I)
    return "hi" if len(roman_hindi) >= 2 else "en"


class Speech:
    """Spoken replies. Kokoro (English) runs in one warm worker that plays a continuous
    stream; replies are queued into it without waiting, so consecutive replies and an
    answer spoken while it is being written flow without gaps or time limits."""
    STALL_SECONDS = 60  # No synthesis/playback progress for this long means the worker is stuck.

    def __init__(self, options, report):
        if (not isinstance(options,dict) or not isinstance(options.get('engine','piper'),str)
                or not isinstance(options.get('language','auto'),str)
                or options.get('engine','piper') not in {'f5','kokoro','piper'}
                or options.get('language','auto') not in {'auto','en','hi'}):
            raise ValueError('Invalid speech engine or language configuration')
        self.options, self.report = options, report
        self.queue = queue.Queue(maxsize=64)
        self.generation = 0
        self.process = None
        self.closed = threading.Event()
        self.speaking = threading.Event()
        self.lock = threading.RLock()
        self.reference_texts = []
        self.output_until = 0.
        self.responses = None
        self.voice_log = None
        self.outstanding = {}  # Kokoro request id -> generation
        self.submitted = {}  # Retained only until playback completes or is cancelled.
        self.submitted_at = {}
        self.audio_committed = set()
        self.first_audio_seconds = None
        self.next_id = 0
        self.last_progress = time.monotonic()
        self.worker_engine = None
        self.worker_ready = threading.Event()
        self.worker_init_error = False
        self.failed_backends = set()
        self.restart_required = False
        self.trace_id = uuid.uuid4().hex
        self.streamed = None  # Text of the answer being spoken while it is written.
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()
        threading.Thread(target=self._watchdog, daemon=True).start()

    # --- public API ---
    def say(self, answer):
        """Speak a reply; if it was already being spoken while written, only the rest is added."""
        if self.closed.is_set() or not self.options.get("enabled", True):
            return
        generation = self.generation
        content = spoken_text(answer)
        with self.lock:
            if generation != self.generation or self.closed.is_set():
                return
            streamed, self.streamed = self.streamed, None
            if streamed is not None:
                if streamed and content.startswith(streamed):
                    content = content[len(streamed):].strip()
                elif streamed:
                    self.cancel()
            if content:
                self._enqueue(content)

    def stream(self, text, active=True, phase=None):
        """Speak complete sentences of an answer while it is still being generated."""
        if (self.closed.is_set() or not self.options.get("enabled", True)
                or not self.options.get("stream_answers", True)):
            return
        if not active:
            self.cancel()
            return
        f5 = self.options.get('engine') == 'f5'
        if f5 and phase not in {None, 'Conversing', 'Groq public answer', 'Generating verified answer'}:
            # Keep research drafts on the island until verification selects an answer.
            if not text and self.streamed:
                self.cancel()
            return
        generation = self.generation
        content = spoken_text(text or "")
        with self.lock:
            if generation != self.generation or self.closed.is_set():
                return
            spoken = self.streamed
            if spoken is None:
                if not content:
                    return
                spoken = ""
            if not content.startswith(spoken):
                # The preview was replaced (e.g. a draft discarded); wait for the final answer.
                self.streamed = ""
                self.cancel()
                return
            boundary = max(content.rfind(mark, len(spoken)) for mark in (". ", "! ", "? ", "\n\n"))
            if f5:
                from .speech_normalizer import opening_clause
                # A sentence can finish at the stream edge before another token arrives.
                ends = [match.end() for match in re.finditer(r'[.!?](?=\s|$)', content)
                        if match.end() > len(spoken) and match.end()-len(spoken) >= 24]
                if ends:
                    boundary = ends[0]-1
                if boundary+1-len(spoken) < 24:
                    boundary = -1
                if boundary < 0:
                    clauses = [match.end() for match in re.finditer(r'[,;:](?=\s)', content)
                               if match.end() > len(spoken) and 32 <= match.end()-len(spoken) <= 120]
                    if clauses:
                        boundary = clauses[0]-1
                if not spoken and boundary < 0:
                    head = opening_clause(content)
                    if head is not None:
                        boundary = head - 1
            if boundary < 0 or (boundary + 1 - len(spoken) < 25 and spoken):
                self.streamed = spoken
                return
            piece = content[len(spoken):boundary + 1]
            self.streamed = content[:boundary + 1]
            if piece.strip():
                self._enqueue(piece.strip())

    def cancel(self):
        with self.lock:
            self.generation += 1
            if self.process and self.process.poll() is None:
                if (self.worker_engine or self.options.get("engine")) in {"kokoro", "f5"} and self.process.stdin:
                    try:
                        # Stop playback and pending synthesis; the warm model stays loaded.
                        self.process.stdin.write(json.dumps({"stop": True}) + "\n")
                        self.process.stdin.flush()
                    except (OSError, ValueError):
                        self.process.kill()
                else:
                    self.process.kill()
            self.outstanding.clear()
            self.submitted.clear()
            self.submitted_at.clear()
            self.audio_committed.clear()
            self.streamed = None
            self._end_output()
            while True:
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except queue.Empty:
                    break

    def interrupt(self):
        with self.lock:
            if self.speaking.is_set() or self.outstanding or not self.queue.empty() or self.streamed is not None:
                self.cancel()

    def output_recent(self):
        # Capture callback must not wait for voice process disposal/synthesis locks.
        return self.speaking.is_set() or time.monotonic() < self.output_until

    def output_references(self):
        return tuple(self.reference_texts)  # Replaced as a whole under the writer lock.

    def health(self):
        with self.lock:
            return {'trace_id':self.trace_id,'backend':self.worker_engine,
                'ready':self.worker_ready.is_set() and not self.worker_init_error,
                'fallback':sorted(self.failed_backends),'pending':len(self.outstanding),
                'queue':self.queue.qsize(),'speaking':self.speaking.is_set(),
                'first_audio_seconds':self.first_audio_seconds,
                'closed':self.closed.is_set(),'restart_required':self.restart_required}

    def close(self):
        self.closed.set()
        self.cancel()
        if self.thread.is_alive():
            self.thread.join(timeout=3)

    # --- internals ---
    def _enqueue(self, content):
        try:
            self.queue.put_nowait((self.generation, content))
        except queue.Full:
            self.report("warning", "Voice queue is full. The answer remains in the transcript.")

    def _begin_output(self, content):
        with self.lock:
            self.reference_texts = (self.reference_texts + [content])[-4:]
            self.speaking.set()

    def _end_output(self):
        if self.speaking.is_set():
            self.output_until = time.monotonic() + 1.2
            self.speaking.clear()

    def _run(self):
        try:
            self._serve_queue()
        finally:
            self._dispose_voice()

    def _dispose_voice(self):
        with self.lock:
            process, self.process = self.process, None
            self.worker_engine = None
            self.worker_ready.clear()
            self.outstanding.clear()
            self.submitted.clear()
            self.submitted_at.clear()
            self.audio_committed.clear()
            if process:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream:
                        stream.close()
            if self.voice_log:
                self.voice_log.close()
                self.voice_log = None

    def _ensure_kokoro(self, generation, engine=None):
        engine = engine or self.options.get('engine', 'kokoro')
        if self.worker_engine is not None and self.worker_engine!=engine:
            if not self._drain_output(generation):return False
        with self.lock:
            if self.closed.is_set() or generation != self.generation:
                return False
            if (self.process and self.process.poll() is None and not self.restart_required
                    and (self.worker_engine is None or self.worker_engine == engine)):
                return True
            self._dispose_voice()
            base = Path(__file__).resolve().parent.parent
            f5 = engine == "f5"
            executable = str(base / ".venv-f5/Scripts/python.exe") if f5 else sys.executable
            module = "jarvis.f5_speech" if f5 else "jarvis.kokoro_speech"
            try:
                self.process = subprocess.Popen([executable, "-u", "-m", module, "--serve"],
                    cwd=base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError:
                raise VoiceStartupError('Local voice process could not start') from None
            self.worker_engine = engine
            self.restart_required = False
            self.worker_init_error = False
            responses = self.responses = queue.Queue(maxsize=128)
            process = self.process
            def read():
                try:
                    while True:
                        line=process.stdout.readline(65537)
                        if not line:break
                        if len(line)>65536:
                            self._event('{"error":"invalid_worker_frame"}',process=process)
                            break
                        if responses.full():responses.get_nowait()
                        responses.put_nowait(line)
                        self._event(line, process=process)
                except (OSError, ValueError):
                    pass
                finally:
                    with self.lock:
                        if self.process is process:
                            self.worker_init_error = True
                            self.worker_ready.set()
                            self.restart_required = True
                            if self.outstanding and not self.closed.is_set():
                                self.report('repair','Voice connection closed; pending audio was discarded, not replayed. A new request can restart the owned worker.')
                            self.outstanding.clear()
                            self.submitted.clear()
                            self.submitted_at.clear()
                            self.audio_committed.clear()
                            self._end_output()
            threading.Thread(target=read, daemon=True).start()
        # Do not hold the synthesis/ownership lock while a cold model loads:
        # Stop and Quit must remain responsive. No text is submitted until ready.
        deadline = time.monotonic()+60
        while not self.closed.is_set() and generation == self.generation:
            if self.worker_ready.wait(.05):
                if self.worker_init_error:
                    raise VoiceStartupError('Local voice initialization failed')
                return True
            if process.poll() is not None or time.monotonic() >= deadline:
                raise VoiceStartupError('Local voice startup deadline exceeded')
        return False

    def _drain_output(self,generation):
        """A language/backend change cannot kill the previous reply mid-clause."""
        while not self.closed.is_set() and generation==self.generation:
            with self.lock:
                if not self.outstanding:return True
            self.closed.wait(.05)  # Existing watchdog bounds a stalled worker.
        return False

    def _event(self, line, process=None):
        """Worker progress: keeps the speaking state exact and feeds the stall watchdog."""
        if not isinstance(line,str) or len(line)>65536:
            return
        try:
            row = json.loads(line)
        except (ValueError,RecursionError):
            return
        if not isinstance(row,dict):return
        flags=('ready','done','started','audio_ready','stopped','playback','safe_to_retry')
        if any(key in row and type(row[key]) is not bool for key in flags):return
        if 'progress' in row and (type(row['progress']) is not int or not 0<=row['progress']<1000000):return
        if 'error' in row and not isinstance(row['error'],str):return
        if not (any(row.get(key) is True for key in flags) or 'progress' in row or row.get('error')):return
        request=row.get('id')
        if request is not None and (type(request) is not int or not 0<request<2**63):return
        with self.lock:
            if process is not None and process is not self.process:return
            if request in self.outstanding and any(row.get(flag) is True for flag in ('audio_ready','started','playback')):
                self.audio_committed.add(request)
            if request in self.submitted_at and row.get('started') is True:
                self.first_audio_seconds = round(time.monotonic()-self.submitted_at[request],3)
                self.submitted_at.pop(request,None)
            if row.get('ready') is True:
                self.worker_ready.set()
                self.last_progress = time.monotonic()
                return
            if row.get("error"):
                if request is None:
                    self.worker_init_error = True
                    self.worker_ready.set()
                self.restart_required = True
                if request in self.outstanding and self.outstanding[request] == self.generation and not self.closed.is_set():
                    content = self.submitted.get(request)
                    backend = self.worker_engine
                    if row.get('safe_to_retry') is True and request not in self.audio_committed and content and backend in {'f5','kokoro'}:
                        self.failed_backends.add(backend)
                        try:self.queue.put_nowait((self.generation,content))
                        except queue.Full:self.report('warning','Voice fallback queue full; the answer remains in the transcript.')
                    else:
                        self.report("warning", "Voice playback failed; the answer remains in the transcript. A new request can restart the owned voice worker.")
                self.outstanding.pop(request, None)
                self.submitted.pop(request, None)
                self.submitted_at.pop(request,None)
                self.audio_committed.discard(request)
            elif row.get("done"):
                self.outstanding.pop(request, None)
                self.submitted.pop(request, None)
                self.submitted_at.pop(request,None)
                self.audio_committed.discard(request)
            if request in self.outstanding:self.last_progress = time.monotonic()
            if not self.outstanding:
                self._end_output()

    def _watchdog(self):
        while not self.closed.is_set():
            time.sleep(1)
            with self.lock:
                limit = 600 if (self.worker_engine or self.options.get("engine")) == "f5" else self.STALL_SECONDS
                stuck = self.outstanding and time.monotonic() - self.last_progress > limit
            if stuck:
                self.report("repair", "Voice worker stopped making progress and was restarted; the answer remains in the transcript.")
                self._dispose_voice()
                self._end_output()

    def _kokoro_send(self, generation, payload, content, engine=None):
        ready = self._ensure_kokoro(generation, engine=engine) if engine else self._ensure_kokoro(generation)
        if not ready:
            return False
        with self.lock:
            if self.closed.is_set() or generation != self.generation:
                return False
            self.next_id += 1
            request = self.next_id
            payload = {**payload, "id": request}
            self.outstanding[request] = generation
            self.submitted[request] = content
            self.submitted_at[request] = time.monotonic()
            self.last_progress = time.monotonic()
            self._begin_output(content)
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        return True

    def _serve_queue(self):
        # Warm the selected local model in a hidden owned child, without speaking.
        if self.options.get("engine") in {"kokoro", "f5"} and self.options.get("enabled", True):
            try:
                if self.options.get("engine") != "f5":
                    self._ensure_kokoro(self.generation)
                else:
                    from .f5_speech import readiness
                    if not readiness(self.options.get("f5", {})):
                        self._ensure_kokoro(self.generation)
            except Exception:
                if self.options.get('engine') == 'f5':
                    self.failed_backends.add('f5')
                    self.report('repair','F5 startup unavailable; trying installed CPU speech. Check speech.f5 or scripts/setup/setup_f5.ps1.')
                self._dispose_voice()
        while not self.closed.is_set():
            try:
                generation, content = self.queue.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                if generation != self.generation or self.closed.is_set() or not self.options.get("enabled", True):
                    continue
                language = speech_language(content, self.options.get("language", "auto"))
                if language == "en" and self.options.get("engine") == "f5":
                    from .f5_speech import readiness
                    issue = readiness(self.options.get("f5", {}))
                    if issue or 'f5' in self.failed_backends:
                        if 'f5' not in self.failed_backends:
                            self.report('repair','F5 reference/environment unavailable; trying installed CPU speech. Configure speech.f5; run scripts/setup/setup_f5.ps1 if needed.')
                        self.failed_backends.add('f5')
                    else:
                        try:
                            self._kokoro_send(generation, {"text": content}, content, engine='f5')
                            continue
                        except VoiceStartupError:
                            # _ensure failed before any text was sent: CPU fallback
                            # cannot duplicate audible audio. Runtime failures never replay.
                            self.failed_backends.add('f5')
                            self._dispose_voice()
                            self.report('repair','F5 startup unavailable; trying installed CPU speech. Check speech.f5.')
                name = "hi_IN-rohan-medium" if language == "hi" else "en_GB-alan-medium"
                base = Path(__file__).resolve().parent.parent
                kokoro = language == "en" and (self.options.get("engine") == "kokoro" or 'f5' in self.failed_backends) and 'kokoro' not in self.failed_backends
                voice_model = base / "models" / "voices" / ("kokoro/kokoro-v1.0.onnx" if kokoro else name + ".onnx")
                voices = base / "models/voices/kokoro/voices-v1.0.bin"
                if not voice_model.is_file() or (kokoro and not voices.is_file()):
                    if kokoro:
                        kokoro=False
                        voice_model=base/'models/voices'/(name+'.onnx')
                    if not voice_model.is_file():
                        self.report("warning", f"{language.upper()} voice model is missing. Run scripts/setup/setup.ps1 to install it.")
                        continue
                if kokoro:
                    # Sent without waiting: the worker plays it right after what is already queued.
                    try:
                        self._kokoro_send(generation, {
                            "text": content, "voice": self.options.get("voice", "am_michael:60,am_fenrir:40"),
                            "speed": self.options.get("speed", 1.0), "natural": self.options.get("natural", True),
                            "breaths": self.options.get("breaths", True),
                            "breath_level": self.options.get("breath_level", .012)}, content, engine='kokoro')
                        continue
                    except VoiceStartupError:
                        self.failed_backends.add('kokoro');self._dispose_voice()
                        voice_model=base/'models/voices'/(name+'.onnx')
                        if not voice_model.is_file():raise RuntimeError('Piper fallback unavailable')
                command = [sys.executable, "-m", "jarvis.piper_speech"]
                payload = json.dumps({"text": content, "model": str(voice_model), **speech_parameters(self.options)},
                                     ensure_ascii=False)
                if not self._drain_output(generation):continue
                with self.lock:
                    if generation != self.generation or self.closed.is_set():
                        continue
                    self._dispose_voice()
                    self._begin_output(content)
                    self.process = subprocess.Popen(
                        command, cwd=Path(__file__).resolve().parent.parent,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    self.worker_engine='piper'
                try:
                    _, error = self.process.communicate(payload, timeout=playback_timeout(content))
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.communicate(timeout=5)
                    if generation == self.generation and not self.closed.is_set():
                        self.report("repair", "Voice worker stalled and was reset; the answer remains in the transcript.")
                    continue
                finally:
                    self._end_output()
                if self.process.returncode and generation == self.generation and not self.closed.is_set():
                    self.report("warning", "Voice playback failed; the answer remains in the transcript.")
            except Exception as exc:
                if generation == self.generation and not self.closed.is_set():
                    self.report("warning", "Voice playback failed; the answer remains in the transcript.")
            finally:
                self.queue.task_done()
