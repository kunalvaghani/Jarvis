"""Independent, cancellable question worker; never dispatches desktop actions."""
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from .question_client import QuestionClient
from .quick_answers import QuickAnswers


SCREEN_QUERY = re.compile(
    r"\b(?:screen|screenshot|this page|this window|what(?:'s| is) this|what do you see|"
    r"what am i looking at|on display|yahan|yeh kya|screen pe|screen par|"
    r"(?:this|that) (?:error|message|image|picture|button|app|website|page))\b|"
    r"(?:स्क्रीन|यहाँ|यह क्या|ये क्या|इस पेज|इस विंडो)", re.I)


def wants_screen(question):
    return bool(SCREEN_QUERY.search(question))


class Knowledge:
    def __init__(self, options, report):
        self.options, self.report = options, report
        self.queue = queue.Queue(maxsize=4)
        self.generation = 0
        self.history = []
        self.closed = threading.Event()
        self.screen_handle = lambda: 0
        self.client = QuestionClient(Path(__file__).resolve().parent.parent, report)
        self.quick = QuickAnswers()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def cancel(self):
        self.generation += 1

    def forget(self):
        self.cancel()
        self.history = []

    def close(self):
        self.cancel()
        self.closed.set()
        if self.thread.is_alive():
            self.thread.join(timeout=3)
        if not self.thread.is_alive():
            self.client.close()

    def submit(self, question, web=False, screen=False):
        try:
            memory = getattr(self, "memory", None)
            if memory is not None:
                memory.record("Jarvis question", question)
            handle = self.screen_handle() if screen or wants_screen(question) else 0
            self.queue.put_nowait((self.generation, question, web, bool(screen or wants_screen(question)), handle))
        except queue.Full:
            self.report("warning", "Question queue full. Wait for an answer or press Stop all tasks.")

    def _run(self):
        while not self.closed.is_set():
            try:
                generation, question, web, use_screen, handle = self.queue.get(timeout=.2)
            except queue.Empty:
                continue
            process = None
            capture_hidden = False
            cancelled = lambda: self.closed.is_set() or generation != self.generation
            try:
                if cancelled():
                    continue
                direct = None if web or use_screen else self.quick.answer(question)
                if direct is not None:
                    result = {"answer": direct}
                else:
                    self.report("thinking", f"Thinking locally: {question}")
                screen = None
                if use_screen:
                    self.report("screen_capture", "")
                    capture_hidden = True
                    time.sleep(.3)  # Let the overlay disappear before taking the screenshot.
                    if cancelled():
                        continue
                    process = subprocess.Popen([sys.executable, "-m", "jarvis.screen_worker"],
                        cwd=Path(__file__).resolve().parent.parent, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    payload = json.dumps({"handle": handle})
                    deadline = time.monotonic() + 20
                    first = True
                    while True:
                        if cancelled():
                            break
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Screen capture timed out.")
                        try:
                            output, error = process.communicate(input=payload if first else None, timeout=.2)
                            break
                        except subprocess.TimeoutExpired:
                            first = False
                    if cancelled():
                        continue
                    if process.returncode:
                        raise RuntimeError(error[-500:] or "Screen capture failed.")
                    screen = json.loads(output)
                    if screen.get("error"):
                        raise ValueError(screen["error"])
                    self.report("screen_capture_done", "")
                    capture_hidden = False
                    self.report("screen", f"Reading visible window: {screen['title']}")
                if direct is None:
                    result = self.client.request({"question": question, "web": web, "options": self.options,
                                                  "history": self.history, "screen": screen}, cancelled)
                if cancelled():
                    continue
                answer = result["answer"]
                if cancelled():
                    continue
                self.history = (self.history + [{"role": "user", "content": question[:2000]},
                    {"role": "assistant", "content": answer[:3000]}])[-6:]
                self.report("answer", answer)
            except Exception as exc:
                if not cancelled():
                    self.report("answer", f"Could not answer: {exc}")
            finally:
                if capture_hidden:
                    self.report("screen_capture_done", "")
                if process and process.poll() is None:
                    process.kill()
                    process.communicate()
                self.queue.task_done()
        self.client.close()
