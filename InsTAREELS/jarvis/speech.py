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


def spoken_text(answer):
    """Turn transcript formatting into prose while retaining words and pauses."""
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
        self.next_id = 0
        self.last_progress = time.monotonic()
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
        content = spoken_text(answer)
        with self.lock:
            streamed, self.streamed = self.streamed, None
        if streamed is not None:
            if streamed and content.startswith(streamed):
                content = content[len(streamed):].strip()
            elif streamed:
                # The final answer differs from what was spoken (for example after online
                # verification): stop the draft and speak the verified answer in full.
                self.cancel()
        if content:
            self._enqueue(content)

    def stream(self, text, active=True):
        """Speak complete sentences of an answer while it is still being generated."""
        if (self.closed.is_set() or not self.options.get("enabled", True)
                or not self.options.get("stream_answers", True)):
            return
        content = spoken_text(text or "")
        with self.lock:
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
                if self.options.get("engine") == "kokoro" and self.process.stdin:
                    try:
                        # Stop playback and pending synthesis; the warm model stays loaded.
                        self.process.stdin.write(json.dumps({"stop": True}) + "\n")
                        self.process.stdin.flush()
                    except (OSError, ValueError):
                        self.process.kill()
                else:
                    self.process.kill()
            self.outstanding.clear()
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
            if self.speaking.is_set() or self.outstanding:
                self.cancel()

    def output_recent(self):
        # Capture callback must not wait for voice process disposal/synthesis locks.
        return self.speaking.is_set() or time.monotonic() < self.output_until

    def output_references(self):
        return tuple(self.reference_texts)  # Replaced as a whole under the writer lock.

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
            self.outstanding.clear()
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

    def _ensure_kokoro(self, generation):
        with self.lock:
            if self.closed.is_set() or generation != self.generation:
                return False
            if self.process and self.process.poll() is None:
                return True
            self._dispose_voice()
            base = Path(__file__).resolve().parent.parent
            directory = base / ".jarvis-runtime"
            directory.mkdir(exist_ok=True)
            self.voice_log = (directory / "speech.log").open("a", encoding="utf-8")
            self.process = subprocess.Popen([sys.executable, "-u", "-m", "jarvis.kokoro_speech", "--serve"],
                cwd=base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.voice_log,
                encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            responses = self.responses = queue.Queue()
            process = self.process
            def read():
                try:
                    for line in process.stdout:
                        responses.put(line)
                        self._event(line)
                except (OSError, ValueError):
                    pass
                finally:
                    responses.put(None)
            threading.Thread(target=read, daemon=True).start()
            return True

    def _event(self, line):
        """Worker progress: keeps the speaking state exact and feeds the stall watchdog."""
        try:
            row = json.loads(line)
        except ValueError:
            return
        with self.lock:
            self.last_progress = time.monotonic()
            request = row.get("id")
            if row.get("error"):
                if request in self.outstanding and self.outstanding[request] == self.generation and not self.closed.is_set():
                    self.report("warning", "Voice playback failed: " + str(row["error"])[:300])
                self.outstanding.pop(request, None)
            elif row.get("done"):
                self.outstanding.pop(request, None)
            if not self.outstanding:
                self._end_output()

    def _watchdog(self):
        while not self.closed.is_set():
            time.sleep(1)
            with self.lock:
                stuck = self.outstanding and time.monotonic() - self.last_progress > self.STALL_SECONDS
            if stuck:
                self.report("repair", "Voice worker stopped making progress and was restarted; the answer remains in the transcript.")
                self._dispose_voice()
                self._end_output()

    def _kokoro_send(self, generation, payload, content):
        if not self._ensure_kokoro(generation):
            return False
        with self.lock:
            if self.closed.is_set() or generation != self.generation:
                return False
            self.next_id += 1
            request = self.next_id
            payload = {**payload, "id": request}
            self.outstanding[request] = generation
            self.last_progress = time.monotonic()
            self._begin_output(content)
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        return True

    def _serve_queue(self):
        # Warm the selected local model in a hidden owned child, without speaking.
        if self.options.get("engine") == "kokoro" and self.options.get("enabled", True):
            try:
                self._ensure_kokoro(self.generation)
            except Exception:
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
                name = "hi_IN-rohan-medium" if language == "hi" else "en_GB-alan-medium"
                base = Path(__file__).resolve().parent.parent
                kokoro = language == "en" and self.options.get("engine") == "kokoro"
                voice_model = base / "models" / "voices" / ("kokoro/kokoro-v1.0.onnx" if kokoro else name + ".onnx")
                voices = base / "models/voices/kokoro/voices-v1.0.bin"
                if not voice_model.is_file() or (kokoro and not voices.is_file()):
                    self.report("warning", f"{language.upper()} voice model is missing. Run scripts/setup/setup.ps1 to install it.")
                    continue
                if kokoro:
                    # Sent without waiting: the worker plays it right after what is already queued.
                    self._kokoro_send(generation, {
                        "text": content, "voice": self.options.get("voice", "am_michael:60,am_fenrir:40"),
                        "speed": self.options.get("speed", 1.0), "natural": self.options.get("natural", True),
                        "breaths": self.options.get("breaths", True),
                        "breath_level": self.options.get("breath_level", .012)}, content)
                    continue
                command = [sys.executable, "-m", "jarvis.piper_speech"]
                payload = json.dumps({"text": content, "model": str(voice_model), **speech_parameters(self.options)},
                                     ensure_ascii=False)
                with self.lock:
                    if generation != self.generation or self.closed.is_set():
                        continue
                    self._dispose_voice()
                    self._begin_output(content)
                    self.process = subprocess.Popen(
                        command, cwd=Path(__file__).resolve().parent.parent,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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
                    self.report("warning", "Voice playback failed: " + error.strip()[-300:])
            except Exception as exc:
                if generation == self.generation and not self.closed.is_set():
                    self.report("warning", f"Voice playback failed: {exc}")
            finally:
                self.queue.task_done()
