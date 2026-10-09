"""Owned, warm UIA process with deadlines; external requests are never retried."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time


class UITransport:
    def __init__(self, base=None, timeout=15, factory=subprocess.Popen, clock=time.monotonic, module="jarvis.ui_worker"):
        self.base = Path(base) if base else Path(__file__).resolve().parent.parent
        self.timeout, self.factory, self.clock = timeout, factory, clock
        self.module = module
        self.process = None
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.started = False
        self.serial = 0
        self.retry_at = 0
        self.failures = 0

    def _start(self):
        if self.closed.is_set():
            raise ValueError("UI worker is closed.")
        if self.process and self.process.poll() is None:
            return
        if self.clock() < self.retry_at:
            raise ValueError("UI worker is cooling down; inspect the target before a new request.")
        try:
            self.process = self.factory([sys.executable, "-m", self.module, "--serve"],
                cwd=self.base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                encoding="utf-8", errors="replace", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.responses = queue.Queue()
            responses, process = self.responses, self.process
            def read():
                try:
                    for line in process.stdout:
                        responses.put(json.loads(line))
                except (OSError, ValueError):
                    pass
                finally:
                    responses.put({"transport_error": "UI worker exited or returned invalid output."})
            threading.Thread(target=read, name="jarvis-ui-response", daemon=True).start()
            self.started = True
        except OSError:
            self._backoff()
            raise

    def _backoff(self):
        self.failures += 1
        self.retry_at = self.clock() + min(30, 2 ** min(self.failures, 5))

    def _stop_process(self):
        process, self.process = self.process, None
        if process:
            if process.poll() is None:
                if self.module == "jarvis.browser_worker":
                    import psutil
                    try:
                        children = psutil.Process(process.pid).children(recursive=True)
                    except psutil.Error:
                        children = []
                    for child in reversed(children):
                        try:
                            child.kill()
                        except psutil.Error:
                            pass
                process.kill()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()

    def request(self, request, cancelled=lambda: False):
        deadline = self.clock() + self.timeout
        while not self.lock.acquire(timeout=.05):
            if cancelled() or self.closed.is_set() or self.clock() >= deadline:
                raise ValueError("UI request cancelled before dispatch.")
        sent = False
        try:
            if cancelled() or self.closed.is_set():
                raise ValueError("UI request cancelled before dispatch.")
            self._start()
            self.serial += 1
            payload = {"id": self.serial, "request": request}
            sent = True  # A partial pipe write is also an uncertain dispatch.
            self.process.stdin.write(json.dumps(payload) + "\n")
            self.process.stdin.flush()
            while True:
                if cancelled() or self.closed.is_set():
                    raise RuntimeError("UI request cancelled after dispatch; inspect the app before repeating it.")
                if self.clock() >= deadline:
                    raise RuntimeError("UI request timed out after dispatch; inspect the app before repeating it.")
                try:
                    result = self.responses.get(timeout=.05)
                except queue.Empty:
                    continue
                if result.get("transport_error") or result.get("id") != self.serial:
                    raise RuntimeError("UI worker lost the response; inspect the app before repeating it.")
                self.failures, self.retry_at = 0, 0
                if result.get("error"):
                    raise ValueError(result["error"])
                return result["result"]
        except (RuntimeError, OSError, KeyError, TypeError) as exc:
            if sent:
                self._stop_process()
                self._backoff()
            raise RuntimeError("UI request failed without replay: " + str(exc)) from exc
        finally:
            self.lock.release()

    def healthy(self):
        return self.closed.is_set() or not self.started or bool(self.process and self.process.poll() is None)

    def repair(self):
        if self.closed.is_set() or not self.lock.acquire(blocking=False):
            return False
        try:
            self._start()  # Start an idle worker only; never send an earlier request.
            return True
        except (OSError, ValueError):
            return False
        finally:
            self.lock.release()

    def close(self):
        self.closed.set()
        with self.lock:
            if self.process and self.process.poll() is None:
                try:
                    self.process.stdin.write(json.dumps({"id": -1, "request": {"operation": "shutdown"}}) + "\n")
                    self.process.stdin.flush()
                    self.process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            self._stop_process()
