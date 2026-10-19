"""Nonblocking diagnosis of declared Ollama models; downloads only with explicit bounded approval (P34-002).

A missing configured model is diagnosed with a read-only ``/api/tags`` lookup, and the installed compatible fallback
that model selection will use is reported. Nothing is pulled, deleted or recreated, and no other provider is
substituted. A configured tag is not download consent. A download starts only from an authorization naming the exact
model, revision, source, byte/RAM/VRAM budgets and network permission (see ``jarvis.repair_authorization``).
``download`` is the final executor and checks every bound immediately before it launches anything. Partial
downloads are left in place for a later approved run.
"""
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
        self.installed = None
        self.approval = None

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
            self.installed = installed
            self.missing = sorted(required - installed)
            self.cached = required <= installed
        except Exception:
            self.cached = True  # Ollama service recovery owns server outages.
        return self.cached

    def approve_download(self, approval):
        """Queue one explicitly approved download; it is re-validated by ``download`` before launch."""
        with self.lock:
            self.approval = approval
            self.next_attempt = 0

    def repair(self):
        with self.lock:
            if self.closing():
                return False
            if (self.thread and self.thread.is_alive()) or time.monotonic() < self.next_attempt:
                return None
            self.next_attempt = time.monotonic() + 300
            self.thread = threading.Thread(target=self.recover, name="jarvis-model-diagnosis", daemon=True)
            self.thread.start()
        return None

    def fallbacks(self):
        """Installed compatible model per missing one (read-only), as model selection would choose it."""
        from .model_selection import installed_model
        screens = {self.config.get(section, {}).get("screen_model") for section in ("brain", "knowledge")}
        chosen = {}
        for model in self.missing:
            try:
                chosen[model] = installed_model(model, self.installed or set(), vision=model in screens)
            except ValueError:
                chosen[model] = None
        return chosen

    def recover(self):
        try:
            from .repair_authorization import RepairRefused, take_model_download
            approval = self.approval
            self.approval = None
            if approval is None:
                try:
                    approval = take_model_download(self.base / ".jarvis-runtime")
                except RepairRefused as error:
                    self.report("repair", str(error))
            if approval is not None:
                self.download(approval)
                return
            if self.closing():
                return
            parts = []
            for model, fallback in self.fallbacks().items():
                parts.append(model + (" -> using installed " + fallback if fallback else " (no installed compatible model)"))
            self.report("repair", "Missing local models: " + "; ".join(parts) + ". Nothing was downloaded. To restore one, "
                        "approve its exact revision, source and byte/RAM/VRAM budget (python -m jarvis.repair_authorization "
                        "model ...) or run launchers/Setup Jarvis Brain.cmd yourself.")
        except Exception:
            if not self.closing():
                self.report("repair", "Model diagnosis is incomplete; nothing was downloaded.")

    def download(self, approval=None):
        """Final executor: launch exactly one approved model pull, or refuse before anything starts."""
        from .repair_authorization import RepairRefused, check_model_download, model_store
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            with self.lock:
                if self.closing():
                    return
                try:
                    check_model_download(approval, self.missing, model_store())
                except RepairRefused as error:
                    self.report("repair", str(error) + " Configured models stay missing; installed fallbacks remain in use.")
                    return
            with (self.base / ".jarvis-runtime" / "models.log").open("a", encoding="utf-8") as log:
                with self.lock:
                    if self.closing():
                        return
                    self.process = subprocess.Popen([str(self.base / ".venv/Scripts/python.exe"),
                        '-m', 'scripts.setup.setup_brain', "--ollama-only", "--model", approval.model,
                        "--revision", approval.revision, "--max-bytes", str(approval.max_bytes)], cwd=self.base,
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
                    self.report("repair", "Approved model " + approval.model + " restored at the approved revision.")
                elif not self.closing():
                    self.report("repair", "Approved restoration of " + approval.model + " did not finish. See "
                                ".jarvis-runtime/models.log; partial downloads are kept. It is not retried "
                                "automatically; approve it again to resume. A task needing a missing model pauses at "
                                "its checkpoint; next model check in 300 seconds.")
        except Exception:
            if not self.closing():
                self.report("repair", "Model restoration is incomplete; partial downloads retained for a later approved retry.")
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
