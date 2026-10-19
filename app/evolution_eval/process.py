"""Bounded child processes for evaluation: wall-time, memory and cancellation limits.

Every candidate test or benchmark runs in its own process tree at below-normal priority with a
minimal environment (no credentials). The tree is killed when it exceeds its wall-time or
resident-memory budget or when the caller cancels; output goes to files to avoid pipe stalls.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import time

SAFE_ENV = {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT', 'LOCALAPPDATA', 'APPDATA',
            'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE',
            'USERNAME', 'COMPUTERNAME'}  # identity names are needed by the privacy rules under test; not secrets


def minimal_env(extra=None):
    env = {k: v for k, v in os.environ.items() if k.upper() in SAFE_ENV}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', JARVIS_EVOLUTION_CANDIDATE='1')
    env.update(extra or {})
    return env


def _tree_rss(process):
    try:
        total = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                total += child.memory_info().rss
            except Exception:
                pass
        return total
    except Exception:
        return 0


def _kill_tree(process):
    try:
        children = process.children(recursive=True)
    except Exception:
        children = []
    for item in [*children, process]:
        try:
            item.kill()
        except Exception:
            pass


def run_bounded(command, cwd, timeout, max_rss_mb, cancelled=lambda: False, stdin_text=None, env=None):
    import psutil
    flags = 0
    if os.name == 'nt':
        flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
    with tempfile.TemporaryDirectory() as folder:
        out_path, err_path = Path(folder) / 'out.txt', Path(folder) / 'err.txt'
        with open(out_path, 'wb') as out, open(err_path, 'wb') as err:
            started = time.monotonic()
            child = subprocess.Popen(command, cwd=cwd, env=env or minimal_env(), stdout=out, stderr=err,
                                     stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                                     creationflags=flags)
            if stdin_text is not None:
                try:
                    child.stdin.write(stdin_text.encode('utf-8'))
                    child.stdin.close()
                except OSError:
                    pass
            process = psutil.Process(child.pid)
            status, peak = 'completed', 0
            while child.poll() is None:
                peak = max(peak, _tree_rss(process))
                if time.monotonic() - started > timeout:
                    status = 'timeout'
                elif peak > max_rss_mb * 2 ** 20:
                    status = 'resource_exhausted'
                elif cancelled():
                    status = 'cancelled'
                if status != 'completed':
                    _kill_tree(process)
                    try:
                        child.wait(10)
                    except subprocess.TimeoutExpired:
                        pass
                    break
                time.sleep(.05)
            seconds = time.monotonic() - started
        stdout = out_path.read_text(encoding='utf-8', errors='replace')
        stderr = err_path.read_text(encoding='utf-8', errors='replace')
    return {'status': status, 'returncode': child.returncode, 'stdout': stdout, 'stderr': stderr,
            'seconds': round(seconds, 3), 'peak_rss_mb': round(peak / 2 ** 20, 1)}
