"""Nonblocking restoration of declared Ollama models, owned by Jarvis."""
from pathlib import Path
import subprocess
import threading
import time


class ModelRecovery:
    def __init__(self, base, config, report, closing):
        from .knowledge_worker import session
        self.base, self.config, self.report, self.closing = Path(base), config, report, closing
        self.client = session()
        self.process = None
        self.thread = None
        self.lock = threading.Lock()
        self.next_attempt = 0
        self.last_check = 0
        self.cached = True
        self.missing = []

    def healthy(self):
        if self.closing():
            return True
        if time.monotonic() - self.last_check < 30:
            return self.cached
        self.last_check = time.monotonic()
        try:
            response = self.client.get("http://127.0.0.1:11434/api/tags", timeout=2)
            response.raise_for_status()
            installed = {item["name"] for item in response.json().get("models", [])}
            from .model_selection import required_models
            required = required_models(self.config)
            self.missing = sorted(required - installed)
            self.cached = required <= installed
        except Exception:
            self.cached = True  # Ollama service recovery owns server outages.
        return self.cached

    def repair(self):
        with self.lock:
            if self.closing():
                return False
            if (self.thread and self.thread.is_alive()) or time.monotonic() < self.next_attempt:
                return None
            self.next_attempt = time.monotonic() + 300
            self.thread = threading.Thread(target=self.download, name="jarvis-model-repair", daemon=True)
            self.thread.start()
        self.report("repair", "Missing local models: " + ", ".join(self.missing) + ". Background restoration started; unrelated tasks can continue.")
        return None

    def download(self):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            with (self.base / ".jarvis-runtime" / "models.log").open("a", encoding="utf-8") as log:
                with self.lock:
                    if self.closing():
                        return
                    self.process = subprocess.Popen([str(self.base / ".venv/Scripts/python.exe"),
                        "setup_brain.py", "--ollama-only"], cwd=self.base,
                        stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
                deadline = time.monotonic() + 1800
                while self.process.poll() is None:
                    if self.closing() or time.monotonic() > deadline:
                        self.process.terminate()
                        break
                    time.sleep(.5)
                self.process.wait(timeout=10)
                self.last_check = 0
                if not self.closing() and self.process.returncode == 0:
                    self.report("repair", "Declared Ollama models restored. Preferred models are available again.")
                elif not self.closing():
                    self.report("repair", "Model restoration failed for " + ", ".join(self.missing) + ". See .jarvis-runtime/models.log; next attempt in 300 seconds. A task needing a missing model pauses at its checkpoint.")
        except Exception:
            if not self.closing():
                self.report("repair", "Model restoration is incomplete; partial downloads retained for a later retry.")
        finally:
            with self.lock:
                if self.process and self.process.poll() is None:
                    self.process.kill()
                self.process = None
                self.next_attempt = time.monotonic() + 300

    def close(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
