"""Single-instance hidden supervisor. Reobserves saved goals after crashes; never blindly replays actions."""
import argparse
import ast
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


class OwnedApplication:
    """Hold the actual interpreter handle, not merely the Windows venv redirector."""
    def __init__(self, child):
        self.child, self.handle = child, None

    def attach(self, pid):
        if self.handle or pid == self.child.pid or os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.TerminateProcess.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.OpenProcess(0x00100001, False, pid)
        if not self.handle:
            raise OSError("Could not track the owned Jarvis interpreter")

    def terminate(self):
        if self.handle:
            self.kernel.TerminateProcess(self.handle, 1)
        if self.child.poll() is None:
            self.child.terminate()

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def session_heartbeat(state, session):
    return state.get("session") == session and type(state.get("pid")) is int and state["pid"] > 0

from .recovery import record

BASE = Path(__file__).resolve().parent.parent
RUNTIME = BASE / ".jarvis-runtime"


def source_snapshot(source, saved):
    """Keep a valid owned backup until a complete new copy can replace it."""
    saved = Path(saved)
    saved.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=saved.parent, prefix='.jarvis-snapshot-', delete=False) as output:
        temporary = Path(output.name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, saved)
    finally:
        temporary.unlink(missing_ok=True)


def preflight(base=BASE, repair=True):
    base = Path(base)
    runtime = base / ".jarvis-runtime"
    runtime.mkdir(exist_ok=True)
    config_path = base / "config.json"
    backup = runtime / "config.last-good.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config.get("apps"), dict) or not isinstance(config.get("whisper"), dict) or not config.get("model_path"):
            raise ValueError("Invalid config")
        if not isinstance(config.get("brain", {}).get("adaptive_planning", False), bool):
            raise ValueError("brain.adaptive_planning must be a boolean")
        if not isinstance(config.get("brain", {}).get("task_recovery", False), bool):
            raise ValueError("brain.task_recovery must be a boolean")
        visual = config.get('brain', {}).get('visual_fallback', {})
        if (not isinstance(visual, dict) or not isinstance(visual.get('enabled', False), bool)
                or type(visual.get('minimum_confidence', .95)) not in (int, float)
                or not math.isfinite(visual.get('minimum_confidence', .95))
                or not .95 <= visual.get('minimum_confidence', .95) <= 1):
            raise ValueError('brain.visual_fallback requires a boolean enabled and minimum_confidence between 0.95 and 1')
    except (ValueError, OSError):
        if not repair or not backup.is_file():
            raise ValueError("config.json is invalid and no last-good configuration is available.")
        if config_path.exists():
            shutil.copy2(config_path, runtime / ("config.damaged." + str(time.time_ns()) + ".json"))
        shutil.copy2(backup, config_path)
        record(base, "Invalid Jarvis configuration restored from its last-good copy; damaged copy preserved.")
        return preflight(base, repair=False)
    sources = [base / "main.py", *sorted((base / "jarvis").rglob("*.py"))]
    if (base / "jarvis_bootstrap.py").is_file():
        sources.append(base / "jarvis_bootstrap.py")
    for source in sources:
        relative = source.relative_to(base)
        saved = runtime / "sources" / relative
        try:
            ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except (SyntaxError, UnicodeError, OSError):
            if not repair or not saved.is_file():
                raise ValueError("Invalid Jarvis source: " + str(relative)) from None
            ast.parse(saved.read_text(encoding="utf-8"))
            damaged = runtime / "damaged" / (str(time.time_ns()) + "-" + source.name)
            damaged.parent.mkdir(exist_ok=True)
            shutil.copy2(source, damaged)
            shutil.copy2(saved, source)
            record(base, "Restored invalid Jarvis source " + str(relative) + " from its startup snapshot; damaged copy preserved.")
    source_snapshot(config_path, backup)
    for source in sources:
        saved = runtime / "sources" / source.relative_to(base)
        saved.parent.mkdir(parents=True, exist_ok=True)
        source_snapshot(source, saved)
    return config


def singleton(path):
    import msvcrt
    path.parent.mkdir(exist_ok=True)
    handle = path.open("a+b")
    if path.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def heartbeat_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def supervised_restart(exit_code, stopped):
    return not stopped and exit_code != 0


def runtime_command(args, log, timeout=1800):
    """Wait for an owned setup process while remaining responsive to Stop."""
    if (RUNTIME / "stop").exists():
        raise InterruptedError("Jarvis stopped")
    child = subprocess.Popen(args, cwd=BASE, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.monotonic() + timeout
    try:
        while child.poll() is None:
            if (RUNTIME / "stop").exists():
                raise InterruptedError("Jarvis stopped")
            if time.monotonic() >= deadline:
                raise TimeoutError("Runtime repair timed out")
            time.sleep(.25)
        return child.returncode
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def prepare_runtime(config):
    """Repair only the project's declared environments and model assets."""
    RUNTIME.mkdir(exist_ok=True)
    manifest = json.loads((BASE / "runtime_manifest.json").read_text(encoding="utf-8"))
    def imports_for(key):
        values = manifest[key]
        if not values or not all(isinstance(value, str) and re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", value) for value in values):
            raise ValueError("Invalid dependency manifest")
        return "import " + ",".join(values)
    with (RUNTIME / "setup.log").open("a", encoding="utf-8") as log:
        def command(args, timeout=1800):
            if runtime_command(args, log, timeout):
                raise ValueError("Declared runtime repair failed; see .jarvis-runtime/setup.log.")
        python = BASE / ".venv" / "Scripts" / "python.exe"
        if not python.is_file():
            record(BASE, "Jarvis Python environment missing; rebuilding it from declared requirements.")
            command([sys.executable, "-m", "venv", str(BASE / ".venv")])
        imports = imports_for("main_imports")
        if runtime_command([str(python), "-c", imports], log, timeout=60):
            record(BASE, "Declared Jarvis dependencies missing; repairing the local environment.")
            command([str(python), "-m", "pip", "--isolated", "install", "-r", "requirements.txt"])
            command([str(python), "-c", imports], timeout=60)
            record(BASE, "Declared Jarvis dependencies repaired.")
        if not (BASE / config["model_path"] / "model.bin").is_file():
            record(BASE, "Whisper model missing; resuming its declared model download.")
            command([str(python), "download_model.py", "--parallel", "4"])
            record(BASE, "Whisper model download repaired.")
        if config.get("speech", {}).get("enabled", True) and config.get("speech", {}).get("engine") == "kokoro":
            if any(not (BASE / path).is_file() for path in manifest.get("voice_assets", [])):
                record(BASE, "Kokoro voice assets missing; restoring pinned local voice files.")
                command([str(python), "setup_voice.py"])
        if config.get("brain", {}).get("enabled"):
            brain = BASE / ".venv-brain" / "Scripts" / "python.exe"
            if not brain.is_file():
                command([str(python), "-m", "venv", str(BASE / ".venv-brain")])
            if runtime_command([str(brain), "-c", imports_for("brain_imports")], log, timeout=60):
                record(BASE, "Brain runtime dependencies missing; restoring declared dependencies.")
                command([str(brain), "-m", "pip", "--isolated", "install", "torch==2.6.0", "--index-url", "https://download.pytorch.org/whl/cpu"])
                command([str(brain), "-m", "pip", "--isolated", "install", "-r", "requirements-brain.txt"])
                command([str(brain), "-c", imports_for("brain_imports")], timeout=60)
            if not (BASE / "models/laya/model.safetensors").is_file():
                record(BASE, "Selector model missing; restoring its pinned checkpoint.")
                command([str(brain), "setup_brain.py", "--laya-only"])
    return BASE / ".venv" / "Scripts" / "pythonw.exe"


def run():
    lock = singleton(RUNTIME / "launcher.lock")
    if lock is None:
        return
    stop = RUNTIME / "stop"
    stop.unlink(missing_ok=True)
    crashes = 0
    resume_after_crash = False
    listen = True
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        while not stop.exists():
            try:
                config = preflight()
                python = prepare_runtime(config)
                session = uuid.uuid4().hex
                beat = RUNTIME / ("heartbeat-" + session + ".json")
                env = dict(os.environ, JARVIS_SUPERVISED="1", JARVIS_SESSION_ID=session,
                           JARVIS_RESUME_TASK="1" if resume_after_crash else "0", JARVIS_AUTOLISTEN="1" if listen else "0")
                with (RUNTIME / "startup.log").open("a", encoding="utf-8") as output:
                    child = subprocess.Popen([str(python), str(BASE / "main.py")], cwd=BASE, env=env,
                        stdout=output, stderr=subprocess.STDOUT, creationflags=flags)
                    started = time.time()
                    owned = OwnedApplication(child)
                    try:
                        while child.poll() is None and not stop.exists():
                            state = heartbeat_state(beat)
                            if session_heartbeat(state, session):
                                owned.attach(state["pid"])
                                listen = state.get("listening_requested", listen)
                                limit = 120 if state.get("status") == "starting" else 90
                                if time.time() - state.get("at", started) > limit:
                                    record(BASE, "Jarvis interface stopped responding; restarting its owned process. Task checkpoints retained.")
                                    owned.terminate()
                                    break
                            elif time.time() - started > 120:
                                record(BASE, "Jarvis startup did not become responsive; restarting its owned process.")
                                owned.terminate()
                                break
                            time.sleep(2)
                        if stop.exists() and child.poll() is None:
                            try:
                                child.wait(timeout=20)
                            except subprocess.TimeoutExpired:
                                owned.terminate()
                        try:
                            code = child.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            owned.terminate()
                            child.kill()
                            code = child.wait(timeout=5)
                    finally:
                        try:
                            if child.poll() is None:
                                owned.terminate()
                                child.wait(timeout=10)
                        finally:
                            owned.close()
                            beat.unlink(missing_ok=True)
                if not supervised_restart(code, stop.exists()):
                    break
                resume_after_crash = True
                crashes = 0 if time.time() - started > 300 else crashes + 1
                record(BASE, "Jarvis stopped unexpectedly; background restart scheduled. No task actions will be replayed.")
            except InterruptedError:
                break
            except Exception as exc:
                crashes += 1
                record(BASE, "Startup repair could not complete: " + str(exc))
            delay = min(300, 2 ** min(crashes, 8))
            for _ in range(delay):
                if stop.exists():
                    break
                time.sleep(1)
    finally:
        lock.close()


def runtime_status(config):
    manifest = json.loads((BASE / "runtime_manifest.json").read_text(encoding="utf-8"))
    missing = []
    for folder, key in ((".venv", "main_imports"), (".venv-brain", "brain_imports")):
        if folder == ".venv-brain" and not config.get("brain", {}).get("enabled"):
            continue
        python = BASE / folder / "Scripts/python.exe"
        modules = manifest[key]
        if not all(re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", name) for name in modules):
            raise ValueError("Invalid dependency manifest")
        if not python.is_file():
            missing.append(folder)
            continue
        result = subprocess.run([str(python), "-c", "import " + ",".join(modules)],
            cwd=BASE, capture_output=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            missing.append(key + ": " + result.stderr.decode(errors="replace").strip().splitlines()[-1])
    if not (BASE / config["model_path"] / "model.bin").is_file():
        missing.append("Whisper checkpoint")
    if config.get("speech", {}).get("enabled", True) and config.get("speech", {}).get("engine") == "kokoro":
        missing.extend(path for path in manifest.get("voice_assets", []) if not (BASE / path).is_file())
    if config.get("brain", {}).get("enabled") and not (BASE / "models/laya/model.safetensors").is_file():
        missing.append("Laya checkpoint")
    hermes_enabled = config.get("brain", {}).get("hermes", {}).get("enabled", False)
    harness_enabled = config.get("brain", {}).get("harness", {}).get("enabled", False)
    if harness_enabled:
        from .harness import readiness
        issue = readiness(BASE)
        if issue:
            missing.append(issue)
        else:
            try:
                check = subprocess.run([str(BASE / '.venv-harness/Scripts/python.exe'),
                    '-m', 'jarvis.harness_worker', '--check'], cwd=BASE, capture_output=True,
                    timeout=45, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if check.returncode:
                    missing.append('Harness runtime/profile check failed; run Setup Jarvis Harness.cmd')
            except (OSError, subprocess.TimeoutExpired):
                missing.append('Harness readiness check failed')
    if hermes_enabled:
        from .hermes import readiness
        issue = readiness(BASE)
        if issue:
            missing.append(issue)
        else:
            try:
                check = subprocess.run([str(BASE / ".venv-hermes/Scripts/python.exe"),
                    "-m", "jarvis.hermes_worker", "--check"], cwd=BASE, capture_output=True,
                    timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if check.returncode:
                    missing.append("Hermes import/tool isolation check failed; run Setup Jarvis Hermes.cmd")
            except (OSError, subprocess.TimeoutExpired):
                missing.append("Hermes readiness check failed")
    visual_enabled = config.get('brain', {}).get('visual_fallback', {}).get('enabled', False)
    if visual_enabled:
        from .visual_fallback import readiness
        issue = readiness(BASE)
        if issue:
            missing.append(issue)
    return {"status": "ready" if not missing else "repair_required", "missing": missing,
            "adaptive_planning": config.get("brain", {}).get("adaptive_planning", False),
            "task_recovery": config.get("brain", {}).get("task_recovery", False),
            "planner": config.get("brain", {}).get("planner"),
            "planning_backend": "deepseek-harness" if harness_enabled else "hermes" if hermes_enabled else "qwen",
            "screen_model": config.get("brain", {}).get("screen_model"),
            "visual_fallback": "ui-tars-parser" if visual_enabled else "disabled"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    if args.stop:
        RUNTIME.mkdir(exist_ok=True)
        (RUNTIME / "stop").touch()
    elif args.check:
        config = preflight(repair=False)
        status = runtime_status(config)
        print(json.dumps(status))
        sys.exit(0 if status["status"] == "ready" else 1)
    else:
        run()
