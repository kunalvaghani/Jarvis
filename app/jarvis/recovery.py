"""Silent, bounded recovery of explicitly registered Jarvis services."""
import json
import os
from pathlib import Path
import queue
import re
import threading
import time
from functools import wraps


def ui_loop(interval):
    """Repair display callbacks only, never re-run user task commands."""
    def decorate(callback):
        @wraps(callback)
        def wrapped(app, *args, **kwargs):
            if getattr(app, "closing", False):
                return
            failures = getattr(app, "ui_failures", {})
            app.ui_failures = failures
            try:
                result = callback(app, *args, **kwargs)
                if failures.get(callback.__name__):
                    record(Path(__file__).resolve().parent.parent, callback.__name__ + " display loop recovered.")
                failures[callback.__name__] = 0
                return result
            except Exception:
                count = failures.get(callback.__name__, 0) + 1
                failures[callback.__name__] = count
                if count in {1, 3}:
                    record(Path(__file__).resolve().parent.parent, callback.__name__ + " display loop failed; background retry scheduled.")
                if not getattr(app, "closing", False):
                    app.root.after(min(30000, interval * 2 ** min(count, 8)), lambda: wrapped(app))
        return wrapped
    return decorate


# Applied to the WHOLE message before truncation, so a secret cannot survive by sitting past the cut.
_REDACTIONS = (
    # Credential schemes first, so "Authorization: Bearer <token>" redacts the token itself.
    (re.compile(r'(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}'), lambda m: m.group(1) + ' [redacted]'),
    (re.compile(r'(?i)\b(api[_-]?key|access[_-]?key|secret|token|password|passwd|pwd|auth|authorization|'
                r'client[_-]?secret|refresh[_-]?token|session[_-]?id|cookie)\b(\s*[:=]\s*|\s+)("[^"]*"|\'[^\']*\'|\S+)'),
     lambda m: m.group(1) + m.group(2) + '[redacted]'),
    (re.compile(r'\b(?:sk|gsk|ghp|gho|ghu|ghs|github_pat|hf|xox[abprs]|AKIA|AIza)[-_A-Za-z0-9]{10,}'), lambda m: '[redacted]'),
    (re.compile(r'(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^@\s/]+@'), lambda m: m.group(1) + '[redacted]@'),
    (re.compile(r'(?i)(\bhttps?://[^\s?#]+)[?#]\S*'), lambda m: m.group(1) + '?[redacted]'),
    (re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+'), lambda m: '[email]'),
    (re.compile(r'(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+'), lambda m: '%USERPROFILE%'),
    (re.compile(r'\b[A-Fa-f0-9]{32,}\b|\b[A-Za-z0-9+/_-]{40,}={0,2}'), lambda m: '[redacted]'),
)


def safe_message(message, limit=300):
    """Privacy-safe one-line repair text: redact credentials, URLs' queries, emails and user paths, then bound it."""
    text = ' '.join(str(message).split())
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text[:limit]


def record(base, message):
    path = Path(base) / ".jarvis-runtime" / "repairs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps({"at": time.time(), "message": safe_message(message)}) + "\n")


def restart_thread(owner, name):
    if owner.closed.is_set() or owner.thread.is_alive():
        return False
    owner.cancel()
    while True:
        try:
            owner.queue.get_nowait()
            owner.queue.task_done()
        except queue.Empty:
            break
    if hasattr(owner, "task_active"):
        owner.task_active = False
        owner.task_state.finish("paused", "Action worker stopped. Last checkpoint preserved; no actions replayed.")
    owner.thread = threading.Thread(target=owner._run, name=name, daemon=True)
    owner.thread.start()
    return True


class Watchdog:
    def __init__(self, report, interval=5, clock=time.monotonic):
        self.report, self.interval, self.clock = report, interval, clock
        self.closed = threading.Event()
        self.services = {}
        self.thread = threading.Thread(target=self.run, name="jarvis-recovery", daemon=True)

    def register(self, name, healthy, repair, enabled=lambda: True):
        self.services[name] = {"healthy": healthy, "repair": repair, "enabled": enabled,
                               "failures": 0, "next": 0, "warned": False}

    def tick(self):
        for name, service in list(self.services.items()):
            if self.closed.is_set():
                return
            try:
                if not service["enabled"]():
                    continue
                if service["healthy"]():
                    if service["warned"]:
                        self.report("repair", name + " was stopped and fixed. No previous actions were replayed.")
                    service.update(failures=0, next=0, warned=False)
                    continue
                if self.clock() < service["next"]:
                    continue
                if not service["warned"]:
                    self.report("repair", name + " stopped responding; attempting background recovery.")
                    service["warned"] = True
                repaired = service["repair"]()
                if self.closed.is_set():
                    return
                if repaired is None:
                    # Asynchronous work is pending, not a failed synchronous repair.
                    service["next"] = self.clock() + self.interval
                    continue
                if repaired and service["healthy"]():
                    self.report("repair", name + " was stopped and fixed. No previous actions were replayed.")
                    service.update(failures=0, next=0, warned=False)
                else:
                    self.failed(name, service)
            except Exception as exc:
                self.failed(name, service)

    def failed(self, name, service):
        service["failures"] += 1
        delay = min(300, 5 * 2 ** min(service["failures"], 6))
        service["next"] = self.clock() + delay
        if service["failures"] in {1, 3}:
            self.report("repair", name + " is not repaired yet; retrying in " + str(delay) + " seconds.")

    def start(self):
        self.thread.start()

    def run(self):
        while not self.closed.is_set():
            self.tick()
            self.closed.wait(self.interval)

    def close(self):
        self.closed.set()


class OllamaService:
    def __init__(self):
        from .knowledge_worker import session
        self.client = session()

    def healthy(self):
        try:
            response = self.client.get("http://127.0.0.1:11434/api/tags", timeout=2)
            return response.status_code == 200 and isinstance(response.json().get("models"), list)
        except Exception:
            return False

    def repair(self):
        from .knowledge_worker import ensure_server
        ensure_server(self.client)
        return self.healthy()
