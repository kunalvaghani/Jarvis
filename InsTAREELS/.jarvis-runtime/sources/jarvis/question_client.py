"""Reusable, cancellable question-only process; no desktop actions or answer cache."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time


class QuestionClient:
    def __init__(self, base, report, timeout=180):
        self.base, self.report, self.timeout = Path(base), report, timeout
        self.process = self.responses = self.log = None

    def close(self):
        process, self.process = self.process, None
        if process:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()
        if self.log:
            self.log.close()
            self.log = None

    def _start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.close()
        self.log = (self.base / "question-worker.log").open("a", encoding="utf-8")
        self.process = subprocess.Popen([sys.executable, "-u", "-m", "jarvis.knowledge_worker", "--serve"],
            cwd=self.base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
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

    def request(self, request, cancelled):
        import re
        if re.search(r'\b(?:my (?:pc|computer|projects?|files?|folders?)|downloads|documents|project.*(?:path|location)|where.*(?:project|folder|file))\b',request.get('question',''),re.I):
            from .pc_context import context
            try:
                request={**request,'pc_context':context(self.base,request['question'])}
            except (OSError,ValueError):
                pass
        for attempt in range(2):
            if cancelled():
                raise ValueError("Question cancelled.")
            try:
                self._start()
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()
                deadline = time.monotonic() + self.timeout
                while True:
                    if cancelled():
                        raise ValueError("Question cancelled.")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("The local LLM took too long. Try a shorter question.")
                    try:
                        line = self.responses.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if line is None:
                        raise BrokenPipeError("Question worker stopped.")
                    result = json.loads(line)
                    if result.get("error"):
                        raise ValueError(result["error"])
                    if not isinstance(result.get("answer"), str) or not result["answer"].strip():
                        raise ValueError("Question worker returned no answer.")
                    return result
            except Exception as exc:
                self.close()
                # Only a stopped worker permits one read-only inference retry.
                if not isinstance(exc, (BrokenPipeError, OSError)) or isinstance(exc, TimeoutError) or attempt or cancelled():
                    raise
                from .recovery import record
                message = "Question worker stopped; retrying read-only inference after backoff."
                record(self.base, message)
                self.report("repair", message)
                deadline = time.monotonic() + .5
                while time.monotonic() < deadline:
                    if cancelled():
                        raise ValueError("Question cancelled during recovery.")
                    time.sleep(.05)
