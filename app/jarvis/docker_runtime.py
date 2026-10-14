"""Hidden Docker availability recovery; never owns or stops the shared engine."""
import json
import shutil
import subprocess
import threading
import time
import os
from pathlib import Path
from contextlib import contextmanager

from .repo_acquisition import command, environment

HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'


def desktop_environment():
    """Trusted Desktop needs Windows profile paths, unlike confined job CLIs."""
    env=environment()
    allowed={'LOCALAPPDATA','APPDATA','USERPROFILE','HOMEDRIVE','HOMEPATH',
        'USERNAME','USERDOMAIN','PROGRAMDATA','ALLUSERSPROFILE'}
    env.update({k:v for k,v in os.environ.items() if k.upper() in allowed})
    if os.name=='nt' and any(not env.get(k) for k in ('LOCALAPPDATA','APPDATA','USERPROFILE')):
        raise ValueError('Windows profile paths unavailable; Desktop launch withheld.')
    return env


@contextmanager
def desktop_start_lock(base):
    """One startup across the supervisor and UI process; never locks the engine."""
    path=Path(base)/'.jarvis-runtime/docker-start.lock'
    path.parent.mkdir(parents=True,exist_ok=True)
    handle=path.open('a+b')
    try:
        handle.seek(0,2)
        if not handle.tell(): handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        handle.close()  # OS releases the lock, also after owner-process death.


def settings(value=None):
    value = value or {}
    if (not isinstance(value, dict) or set(value) - {'enabled', 'recovery', 'leave_shared_engine_running_on_quit'} or
            type(value.get('enabled', False)) is not bool or value.get('recovery', 'start_only') != 'start_only' or
            value.get('leave_shared_engine_running_on_quit', True) is not True):
        raise ValueError('Docker recovery supports boolean enabled, start_only and preserving the shared engine.')
    return value


def engine_status():
    binary = shutil.which('docker')
    if not binary:
        return {'status': 'unavailable', 'error_type': 'DockerCLIMissing'}
    try:
        data = json.loads(command([binary, '--host', HOST, 'info', '--format', '{{json .}}'], timeout=4, limit=200000))
        return {'status': 'available' if data.get('OSType') == 'linux' else 'unavailable',
                'version': data.get('ServerVersion'), 'os': data.get('OSType')}
    except (ValueError, OSError):
        return {'status': 'unavailable', 'error_type': 'DockerEngineUnavailable'}


class DockerService:
    def __init__(self, base, report=None, stopped=lambda: False):
        self.base, self.report, self.stopped = base, report, stopped
        self.closed = threading.Event()
        self.lock = threading.Lock()
        self.thread = None
        self.next_start = 0
        self.attempts = 0
        self.last_orphan_check = 0
        self.orphan_thread = None

    def disabled(self):
        return self.closed.is_set() or self.stopped()

    def healthy(self):
        if self.disabled():
            return True
        available = engine_status()['status'] == 'available'
        if available and time.monotonic() - self.last_orphan_check > 60 and not (self.orphan_thread and self.orphan_thread.is_alive()):
            self.last_orphan_check = time.monotonic()
            self.orphan_thread = threading.Thread(target=self._reap, name='jarvis-sandbox-cleanup', daemon=True)
            self.orphan_thread.start()
        return available

    def _reap(self):
        from .deerflow_sandbox import reap_orphans
        from .recovery import record
        if self.disabled():
            return
        count = reap_orphans(self.base)
        if count:
            record(self.base, 'Closed ' + str(count) + ' abandoned owned sandbox containers; outputs preserved, no task replay.')

    def repair(self):
        if self.disabled():
            return True
        with self.lock:
            if self.thread and self.thread.is_alive():
                return None
            if time.monotonic() < self.next_start:
                return False
            self.thread = threading.Thread(target=self._start, name='jarvis-docker-start', daemon=True)
            self.thread.start()
        return None

    def _start(self):
        from .recovery import record
        if self.disabled():
            return
        binary = shutil.which('docker')
        if not binary:
            self.attempts += 1
            self.next_start = time.monotonic() + 300
            record(self.base, 'Docker CLI missing; sandbox remains unavailable.')
            return
        try:
            if engine_status()['status'] == 'available' or self.disabled():
                self.attempts = 0
                return
            with desktop_start_lock(self.base) as acquired:
                if not acquired:
                    self.next_start=time.monotonic()+5
                    return  # Another process starts Desktop; only reobserve later.
                if self.disabled() or engine_status()['status']=='available': return
                # Desktop is shared. Never attach it to a kill-on-Quit job.
                result=subprocess.run([binary, 'desktop', 'start', '--detach'], env=desktop_environment(),
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if result.returncode: raise ValueError('Desktop start failed')
                deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    if self.disabled(): return
                    if engine_status()['status'] == 'available':
                        self.attempts = 0
                        record(self.base, 'Docker Linux engine available; no interrupted command was replayed.')
                        return
                    if self.closed.wait(1): return
                raise ValueError('Docker readiness deadline')
        except (OSError, ValueError, subprocess.TimeoutExpired):
            self.attempts += 1
            self.next_start = time.monotonic() + min(300, 10 * 2 ** min(self.attempts, 5))
            record(self.base, 'Docker background start did not become ready; bounded backoff, no task replay.')

    def close(self):
        self.closed.set()


def start_background(base, config, stopped=lambda: False):
    if not config.get('docker_runtime', {}).get('enabled', False):
        return None
    service = DockerService(base, stopped=stopped)
    service.repair()
    return service
