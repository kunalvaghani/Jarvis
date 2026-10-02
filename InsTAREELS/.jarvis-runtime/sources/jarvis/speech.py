"""Cancellable, local Windows speech for question answers."""
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
    answer = re.sub(r"\n+", ". ", answer)
    answer = re.sub(r"([.!?।])\s*\.", r"\1", answer)
    answer = re.sub(r"\s+([,.!?।])", r"\1", answer)
    answer = " ".join(answer.split())
    if len(answer) > 2500:
        boundary = max(answer.rfind(mark, 0, 2500) for mark in ".!?।")
        answer = answer[:boundary + 1] if boundary >= 1500 else answer[:2500].rsplit(" ", 1)[0] + "."
    return answer


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
    def __init__(self, options, report):
        self.options, self.report = options, report
        self.queue = queue.Queue(maxsize=4)
        self.generation = 0
        self.process = None
        self.closed = threading.Event()
        self.speaking = threading.Event()
        self.lock = threading.RLock()
        self.reference_texts = []
        self.output_until = 0.
        self.responses = None
        self.voice_log = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def say(self, answer):
        if self.closed.is_set() or not self.options.get("enabled", True):
            return
        content = spoken_text(answer)
        if content:
            try:
                self.queue.put_nowait((self.generation, content))
            except queue.Full:
                self.report("warning", "Voice queue is full. The answer remains in the transcript.")

    def cancel(self):
        with self.lock:
            self.generation += 1
            if self.process and self.process.poll() is None:
                self.process.kill()
            self._end_output()
            while True:
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except queue.Empty:
                    break

    def interrupt(self):
        with self.lock:
            if self.speaking.is_set():
                self.cancel()

    def output_recent(self):
        # Capture callback must not wait for voice process disposal/synthesis locks.
        return self.speaking.is_set() or time.monotonic() < self.output_until

    def output_references(self):
        return tuple(self.reference_texts)  # Replaced as a whole under the writer lock.

    def _begin_output(self, content):
        with self.lock:
            self.reference_texts = (self.reference_texts + [content])[-2:]
            self.speaking.set()

    def _end_output(self):
        if self.speaking.is_set():
            self.output_until = time.monotonic() + 1.2
            self.speaking.clear()

    def close(self):
        self.closed.set()
        self.cancel()
        if self.thread.is_alive():
            self.thread.join(timeout=3)

    def _run(self):
        try:
            self._serve_queue()
        finally:
            self._dispose_voice()

    def _dispose_voice(self):
        with self.lock:
            process, self.process = self.process, None
            if process:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                if process.stdin:
                    process.stdin.close()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
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
                except (OSError, ValueError):
                    pass
                finally:
                    responses.put(None)
            threading.Thread(target=read, daemon=True).start()
            return True

    def _kokoro_reply(self, generation, payload, content):
        if not self._ensure_kokoro(generation):
            return False
        with self.lock:
            if self.closed.is_set() or generation != self.generation:
                return False
            self._begin_output(content)
            self.process.stdin.write(payload + "\n")
            self.process.stdin.flush()
        deadline = time.monotonic() + playback_timeout(content)
        while not self.closed.is_set() and generation == self.generation:
            if time.monotonic() > deadline:
                raise ValueError("Voice worker timed out; this reply will not be replayed.")
            try:
                line = self.responses.get(timeout=.1)
            except queue.Empty:
                continue
            if line is None:
                raise ValueError("Voice worker stopped. See .jarvis-runtime/speech.log.")
            result = json.loads(line)
            if result.get("error"):
                raise ValueError(result["error"])
            if result.get("done"):
                return True
        return False

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
            keep = False
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
                    self.report("warning", f"{language.upper()} voice model is missing. Run setup.ps1 to install it.")
                    continue
                command = [sys.executable, "-m", "jarvis.kokoro_speech" if kokoro else "jarvis.piper_speech"]
                payload = json.dumps({"text": content, "model": str(voice_model), "voices": str(voices),
                                      "voice": self.options.get("voice", "af_heart"), "speed": self.options.get("speed", 1.0),
                                      **speech_parameters(self.options)}, ensure_ascii=False)
                if kokoro:
                    keep = self._kokoro_reply(generation, payload, content)
                    continue
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
                if self.process.returncode and generation == self.generation and not self.closed.is_set():
                    self.report("warning", "Voice playback failed: " + error.strip()[-300:])
            except Exception as exc:
                if generation == self.generation and not self.closed.is_set():
                    self.report("warning", f"Voice playback failed: {exc}")
            finally:
                with self.lock:
                    if not keep:
                        self._dispose_voice()
                    self._end_output()
                self.queue.task_done()
