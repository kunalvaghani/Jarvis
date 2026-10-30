"""Connection check for every control route: what works, what is blocked, and the one step that fixes it.

    python -m jarvis.control.health            # JSON report
Read-only apart from one temporary file of its own in the approved folder (removed again) and a
headless Chrome start on the empty test profile. Progress streams to an optional island sink.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Callable, List, Optional, Sequence, Tuple
import urllib.request

from .progress import ProgressEvent, Sink, emit
from .settings import ControlSettings, load
from .types import Route

OK, WARN, FAIL = 'ok', 'warn', 'fail'


@dataclass(frozen=True)
class Check:
    name: str
    route: str
    status: str
    detail: str
    fix: str = ''
    ms: float = 0.0


Probe = Callable[[ControlSettings], Tuple[str, str, str]]


def dpi(settings: ControlSettings) -> Tuple[str, str, str]:
    from .coords import ensure_per_monitor_dpi
    ensure_per_monitor_dpi()
    return OK, 'per-monitor DPI aware: screen pixels and clicks agree', ''


def monitors(settings: ControlSettings) -> Tuple[str, str, str]:
    from .coords import system_layout
    layout = system_layout()
    rows = ', '.join(f'{m.physical.width}x{m.physical.height}@{m.scale:g}' for m in layout.monitors)
    return OK, f'{len(layout.monitors)} monitor(s): {rows}', ''


def capture(settings: ControlSettings) -> Tuple[str, str, str]:
    from .coords import system_layout
    from .routes.vision import mss_capture
    monitor = system_layout().monitors[0].physical
    image = mss_capture(monitor)
    if image.size != (monitor.width, monitor.height):
        return FAIL, f'capture {image.size} does not match monitor {monitor.width}x{monitor.height}', 'Restart Jarvis.'
    return OK, f'screen capture {image.width}x{image.height} (stays on this PC)', ''


def vision_models(settings: ControlSettings) -> Tuple[str, str, str]:
    from .routes.vision import OllamaGrounder
    OllamaGrounder(settings.vision_models[0], settings.ollama_url)  # Refuses a non-loopback server.
    try:
        with urllib.request.urlopen(settings.ollama_url.rstrip('/') + '/api/tags', timeout=5) as response:
            names = {row['name'] for row in json.loads(response.read())['models']}
    except (OSError, ValueError, KeyError) as error:
        return FAIL, f'Ollama is not answering ({type(error).__name__})', 'Start Ollama (Start Jarvis.cmd starts it).'
    missing = [m for m in settings.vision_models if m not in names and m + ':latest' not in names]
    if missing:
        return FAIL, 'missing vision model(s): ' + ', '.join(missing), 'ollama pull ' + missing[0]
    return OK, 'local vision models ready: ' + ' -> '.join(settings.vision_models), ''


def uia(settings: ControlSettings) -> Tuple[str, str, str]:
    from .routes.uia import top_windows
    windows = top_windows()
    return OK, f'Windows UI Automation reads {len(windows)} top-level windows', ''


def input_path(settings: ControlSettings) -> Tuple[str, str, str]:
    from .input import Input
    from .locks import LockManager
    from .policy import Policy
    from .routes.uia import UIAExecutor, own_process_elevated, secure_desktop_active
    if secure_desktop_active():
        return FAIL, 'a UAC or lock-screen prompt is showing', 'Answer it yourself; Jarvis never touches it.'
    executor = UIAExecutor(Policy(), Input(LockManager(), 'health', use_pointer=False))
    try:
        blocker = executor.protected_foreground()
    finally:
        executor.close()
    if blocker:
        return WARN, f'a protected window ({blocker}) is in front, so Windows would drop keys and clicks', \
            'Click your desktop or taskbar once.'
    return OK, 'keyboard and mouse input can reach normal apps' + (' (Jarvis runs elevated)' if own_process_elevated() else ''), ''


def browser(settings: ControlSettings) -> Tuple[str, str, str]:
    from .policy import Policy
    from .routes.browser import BrowserExecutor
    settings.test_profile.mkdir(parents=True, exist_ok=True)
    executor = BrowserExecutor(settings.test_profile, Policy(allowed_roots=settings.allowed_roots),
                               settings.downloads, headless=True)
    try:
        executor.start()
        health = executor.health_check()
    except Exception as error:
        text = str(error).splitlines()[0][:120]
        if 'user data directory is already in use' in str(error).lower() or 'processsingleton' in str(error).lower():
            return WARN, 'the test browser profile is open in another Jarvis window', 'Close that browser window.'
        return FAIL, f'Chrome did not start: {text}', 'Install Google Chrome, or update it and retry.'
    finally:
        executor.close()
    return (OK if health.ok else FAIL), 'Chrome starts on the clean Jarvis test profile' if health.ok else health.detail, ''


def personal_profile(settings: ControlSettings) -> Tuple[str, str, str]:
    path = settings.personal_profile / 'Default'
    if not path.is_dir():
        return WARN, 'no personal Jarvis browser profile', 'Optional: copy your Chrome profile (see README).'
    return WARN, 'personal profile present; website sign-ins need one Chrome sign-in inside it', \
        'Open it once and sign in to Chrome (cookies cannot be copied).'


def folder(settings: ControlSettings) -> Tuple[str, str, str]:
    root = settings.allowed_roots[0]
    if not root.is_dir():
        return FAIL, f'approved folder {root} is missing', f'Create {root} or set control.allowed_roots.'
    handle, name = tempfile.mkstemp(prefix='.jarvis-health-', dir=str(root))
    os.close(handle)
    os.unlink(name)  # Only the check's own temporary file.
    return OK, f'file work confined to {root}', ''


def gmail(settings: ControlSettings) -> Tuple[str, str, str]:
    from .. import gmail_api
    state = gmail_api.status()
    if state == 'connected':
        return OK, 'Gmail API connected locally (sends always ask first)', ''
    return WARN, gmail_api.unavailable().split(': ', 1)[-1].split('. ')[0], 'Run launchers/Connect Jarvis Gmail API.cmd.'


CHECKS: Sequence[Tuple[str, Route, Probe]] = (
    ('Screen scaling', Route.VISION, dpi),
    ('Monitors', Route.VISION, monitors),
    ('Screen capture', Route.VISION, capture),
    ('Local vision models', Route.VISION, vision_models),
    ('Windows apps', Route.UIA, uia),
    ('Keyboard and mouse', Route.UIA, input_path),
    ('Chrome (test profile)', Route.BROWSER, browser),
    ('Personal browser profile', Route.BROWSER, personal_profile),
    ('Approved folder', Route.API, folder),
    ('Gmail', Route.API, gmail),
)


def run(settings: Optional[ControlSettings] = None, sink: Optional[Sink] = None,
        checks: Sequence[Tuple[str, Route, Probe]] = CHECKS) -> List[Check]:
    settings = settings or load()
    results: List[Check] = []
    for index, (name, route, probe) in enumerate(checks, 1):
        emit(sink, ProgressEvent(route, 'checking', name, 'Connection check', 'Checking…', index, len(checks)))
        started = time.perf_counter()
        try:
            status, detail, fix = probe(settings)
        except Exception as error:  # A broken dependency is a finding, not a crash.
            status, detail, fix = FAIL, f'{type(error).__name__}: {str(error)[:160]}', 'See the detail.'
        check = Check(name, route.value, status, detail, fix, round((time.perf_counter() - started) * 1000, 1))
        results.append(check)
        emit(sink, ProgressEvent(route, {OK: 'done', WARN: 'blocked', FAIL: 'failed'}[status], name,
                                 'Connection check', detail[:80], index, len(checks)))
    return results


def summary(results: Sequence[Check]) -> str:
    failed = [r for r in results if r.status == FAIL]
    warned = [r for r in results if r.status == WARN]
    head = (f'{len(results) - len(failed) - len(warned)} of {len(results)} control connections are ready'
            + (f', {len(warned)} need attention' if warned else '') + (f', {len(failed)} failed' if failed else '') + '.')
    lines = [head] + [f'{r.name}: {r.detail}' + (f' Fix: {r.fix}' if r.fix else '') for r in failed + warned]
    return '\n'.join(lines)


def main(argv: Sequence[str] = ()) -> int:
    results = run()
    print(json.dumps({'summary': summary(results), 'checks': [asdict(r) for r in results]}, indent=1))
    return 1 if any(r.status == FAIL for r in results) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
