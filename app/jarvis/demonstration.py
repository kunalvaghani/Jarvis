"""Show Me Once: learn one identifiable UI action from an explicit, consented user demonstration.

Flow: Jarvis asks (spoken through F5) for a single demonstration in a selected window;
recording starts only after explicit consent, scoped to that window's process; a
low-level mouse hook observes clicks. Injected input -- including Jarvis's own cyan
cursor, which uses Windows touch injection -- is never treated as the user's.
For each user click inside the scoped window the recorder captures the UI Automation
element (control type, AutomationId, accessible name, class, ancestry) and the
observed before/after state; relative coordinates are kept only as a last-resort
fallback. Transient RuntimeIds, keyboard input, field values and anything inside a
password field are never stored.

A demonstration becomes a minimal provisional skill only after Jarvis replays the
selector through the structured UIA path in a safe context and observes the same
postcondition. Trust then follows the Phase 3 lifecycle (independent verified use).
"""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import threading
import time
import uuid

WH_MOUSE_LL, WM_LBUTTONDOWN, WM_QUIT = 14, 0x0201, 0x0012
LLMHF_INJECTED, LLMHF_LOWER_IL_INJECTED = 0x01, 0x02
MAX_STEPS = 10
STATE_ROLES = {'Text', 'Edit', 'CheckBox', 'RadioButton', 'ComboBox', 'TabItem', 'ListItem'}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [('pt', wintypes.POINT), ('mouseData', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


def classify_input(flags):
    """Physical user input has no injection flag; SendInput/touch injection (Jarvis's pointer) does."""
    return 'injected' if flags & (LLMHF_INJECTED | LLMHF_LOWER_IL_INJECTED) else 'user'


class HookProcess:
    """In-process WH_MOUSE_LL with a message pump (used inside the dedicated hook process only)."""

    def __init__(self, emit):
        self.emit = emit

    def run(self):
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t

        def callback(code, wparam, lparam):
            if code == 0:
                data = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                self.emit(data.pt.x, data.pt.y, int(wparam), int(data.flags))
            return user32.CallNextHookEx(None, code, wparam, lparam)

        self._callback = callback_type(callback)
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        handle = user32.SetWindowsHookExW(WH_MOUSE_LL, self._callback, None, 0)
        if not handle:
            raise OSError('SetWindowsHookExW failed (' + str(ctypes.get_last_error()) + ')')
        self.emit(0, 0, 0, -1)  # ready marker
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        user32.UnhookWindowsHookEx(handle)


class MouseHook:
    """Low-level mouse hook in a dedicated, owned process that loads only ctypes.

    Windows silently removes a low-level hook whose callback exceeds LowLevelHooksTimeout,
    and a callback inside the busy Jarvis process would compete for the GIL with planning,
    speech and UI work; a tiny dedicated process keeps system input responsive and the
    hook alive. Events arrive as (x, y, message, flags). Note: Windows (UIPI) does not
    deliver injected input while an elevated/system window has the foreground.
    """

    def __init__(self, events):
        self.events, self.process, self.reader = events, None, None
        self.ready = threading.Event()

    def start(self):
        import subprocess
        import sys
        self.process = subprocess.Popen([sys.executable, '-m', 'jarvis.demonstration', '--hook'],
                                        cwd=str(Path(__file__).resolve().parents[1]), stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.reader = threading.Thread(target=self._read, name='jarvis-demonstration-hook', daemon=True)
        self.reader.start()
        if not self.ready.wait(10):
            self.stop()
            raise ValueError('Mouse hook process did not become ready; nothing is recorded.')

    def _read(self):
        for line in self.process.stdout:
            try:
                x, y, message, flags = (int(part) for part in line.split())
            except ValueError:
                continue
            if flags == -1:
                self.ready.set()
                continue
            try:
                self.events.put_nowait((x, y, message, flags, time.monotonic()))
            except queue.Full:
                pass

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(3)
            except Exception:  # Stuck hook process: force it; it owns nothing else.
                self.process.kill()
        self.process = None


def describe(element, depth=6):
    """Stable selector features only; RuntimeId is deliberately excluded."""
    info = element.element_info
    selector = {'control_type': info.control_type or '', 'automation_id': info.automation_id or '',
                'name': (info.name or '')[:120], 'class_name': (info.class_name or '')[:80]}
    ancestry, parent = [], element.parent()
    while parent is not None and len(ancestry) < depth:
        pinfo = parent.element_info
        ancestry.append({'control_type': pinfo.control_type or '', 'automation_id': pinfo.automation_id or '',
                         'name': (pinfo.name or '')[:80]})
        try:
            parent = parent.parent()
        except Exception:  # Reached the desktop root.
            break
    selector['ancestry'] = ancestry
    return selector


def is_password(element):
    try:
        return bool(element.element_info.element.CurrentIsPassword)
    except Exception:  # Unknown means treat as private.
        return True


def window_state(window):
    """Observed state that a click can change: title and non-editable texts/toggles (no field values)."""
    texts = []
    for child in window.descendants()[:200]:
        info = child.element_info
        if info.control_type == 'Text' and info.name:
            texts.append(info.name[:120])
        elif info.control_type in {'CheckBox', 'RadioButton'}:
            try:
                texts.append(info.name[:60] + '=' + str(child.get_toggle_state()))
            except Exception:  # Control without toggle support; state not observed.
                pass
    return {'title': window.window_text()[:200], 'texts': texts[:50]}


class DemonstrationSession:
    def __init__(self, base, approve, speak=lambda text: None, hook_factory=MouseHook):
        self.base = Path(base)
        self.approve, self.speak, self.hook_factory = approve, speak, hook_factory
        self.identifier = uuid.uuid4().hex[:16]
        self.path = self.base / '.jarvis-runtime' / 'demonstrations' / (self.identifier + '.json')
        self.state = {'id': self.identifier, 'status': 'created', 'steps': [], 'discarded': []}
        self.events = queue.Queue(maxsize=256)
        self.hook = None
        self.window = None
        self.last_state = None

    @classmethod
    def resume(cls, base, identifier, approve, speak=lambda text: None):
        """Restart recovery: recorded steps survive; recording itself needs fresh consent."""
        session = cls(base, approve, speak)
        session.identifier = identifier
        session.path = session.base / '.jarvis-runtime' / 'demonstrations' / (identifier + '.json')
        session.state = json.loads(session.path.read_text(encoding='utf-8'))
        if session.state['status'] == 'recording':
            session.state['status'] = 'interrupted'
        session._save()
        return session

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name('.' + self.path.name + '.' + uuid.uuid4().hex[:6])
        temporary.write_text(json.dumps(self.state, indent=1), encoding='utf-8')
        temporary.replace(self.path)

    def request(self, action_name, window_handle, cancelled=lambda: False):
        """Ask by voice, then require explicit consent scoped to one window. No consent: nothing is installed."""
        import win32gui
        import win32process
        import psutil
        from pywinauto import Desktop
        if not win32gui.IsWindow(window_handle):
            raise ValueError('The selected window no longer exists.')
        pid = win32process.GetWindowThreadProcessId(window_handle)[1]
        process = psutil.Process(pid).name()
        title = win32gui.GetWindowText(window_handle)[:120]
        self.speak(f"I can't reliably find the {action_name} button. Could you click it once while demonstration "
                   'recording is enabled?')
        detail = {'purpose': 'Show Me Once demonstration', 'action': action_name, 'application': process,
                  'window': title, 'records': 'mouse clicks in this window only; no keyboard, no field values, no passwords',
                  'max_steps': MAX_STEPS}
        self.approve('demonstration_recording', json.dumps(detail), cancelled)  # raises when declined
        self.window = Desktop(backend='uia').window(handle=window_handle).wrapper_object()
        self.state.update(status='recording', action=action_name, application=process, window_title=title,
                          window_class=win32gui.GetClassName(window_handle), consent_at=now())
        self.handle, self.pid = window_handle, pid
        self.last_state = window_state(self.window)
        self._save()

    def start_hook(self):
        if self.state['status'] != 'recording':
            raise ValueError('Recording requires fresh consent.')
        self.hook = self.hook_factory(self.events)
        self.hook.start()

    def stop(self, status='stopped'):
        if self.hook:
            self.hook.stop()
            self.hook = None
        self.state['status'] = status
        self._save()

    def process(self, x, y, message, flags):
        """One mouse event. Returns the recorded step, or None when it was ignored."""
        import win32gui
        from pywinauto import Desktop
        if self.state['status'] != 'recording' or message != WM_LBUTTONDOWN:
            return None
        if classify_input(flags) != 'user':
            self.state['discarded'].append({'reason': 'injected input (Jarvis cursor or automation)', 'at': now()})
            return None
        target = win32gui.WindowFromPoint((x, y))
        if not target or win32gui.GetAncestor(target, 2) != self.handle:
            self.state['discarded'].append({'reason': 'outside the selected window', 'at': now()})
            return None
        element = Desktop(backend='uia').from_point(x, y)
        if is_password(element):
            self.state['discarded'].append({'reason': 'password or private field', 'at': now()})
            self._save()
            return None
        before = self.last_state or window_state(self.window)
        rect, window_rect = element.rectangle(), self.window.rectangle()
        time.sleep(.4)  # let the application react before observing the postcondition
        after = window_state(self.window)
        self.last_state = after
        step = {'selector': describe(element),
                'fallback_relative_point': [round((x - window_rect.left) / max(1, window_rect.width()), 4),
                                            round((y - window_rect.top) / max(1, window_rect.height()), 4)],
                'element_size': [rect.width(), rect.height()],
                'before': before, 'after': after,
                'postcondition': sorted(set(after['texts']) - set(before['texts']))[:10]
                                 + ([] if after['title'] == before['title'] else ['title:' + after['title']]),
                'at': now()}
        self.state['steps'].append(step)
        if len(self.state['steps']) >= MAX_STEPS:
            self.stop('complete')
        self._save()
        return step

    def pump(self, timeout=60, until=lambda steps: len(steps) >= 1, cancelled=lambda: False):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not cancelled() and self.state['status'] == 'recording':
            try:
                x, y, message, flags, _ = self.events.get(timeout=.1)
            except queue.Empty:
                continue
            self.process(x, y, message, flags)
            if until(self.state['steps']):
                break
        self.stop('cancelled' if cancelled() else 'complete' if self.state['steps'] else 'timed_out')
        return self.state['steps']

    # ---- replay and skill candidate -------------------------------------------------------------------------------
    def replay(self, window_handle, step):
        """Structured replay in a safe context: locate by stable selector, activate via UIA, verify postcondition."""
        from pywinauto import Desktop
        from .execution_router import execute
        window = Desktop(backend='uia').window(handle=window_handle).wrapper_object()
        selector = step['selector']
        matches = [c for c in window.descendants()
                   if c.element_info.control_type == selector['control_type']
                   and ((selector['automation_id'] and c.element_info.automation_id == selector['automation_id'])
                        or (not selector['automation_id'] and c.element_info.name == selector['name']))]
        if len(matches) != 1:
            raise ValueError('Selector is not unique or not found in the replay context; no input issued.')
        element = matches[0]
        before = window_state(window)
        receipt = execute({'operation': 'activate'}, element,
                          {'role': selector['control_type'], 'name': selector['name'],
                           'id': list(element.element_info.runtime_id)},  # live id for this replay only, never stored
                          type('Window', (), {'handle': window_handle})(), lambda: None,
                          observe=lambda: window_state(window))
        after = window_state(window)
        expected = [p for p in step['postcondition'] if not p.startswith('title:')]
        observed = sorted(set(after['texts']) - set(before['texts']))
        verified = bool(expected) and all(p in observed for p in expected)
        return {'provider': receipt.get('provider'), 'verified': verified, 'expected': expected, 'observed': observed}

    def skill_body(self, name):
        steps = self.state['steps']
        lines = []
        for number, step in enumerate(steps, 1):
            s = step['selector']
            chain = ' > '.join(a['control_type'] + (':' + a['automation_id'] if a['automation_id'] else '')
                               for a in reversed(s['ancestry'][:3]))
            lines.append(f"{number}. In {self.state['application']}, select the {s['control_type']} named "
                         f"\"{s['name']}\"" + (f" (AutomationId {s['automation_id']})" if s['automation_id'] else '') +
                         f" under {chain or 'the window'}. Expect: {', '.join(step['postcondition']) or 'a visible change'}.")
        return (f"---\nname: {name}\ndescription: Demonstrated UI action in {self.state['application']} learned with consent "
                f"from one user click.\ntools: [select]\n---\n\n# Demonstrated action (provisional)\n\n"
                f"Preconditions: application {self.state['application']} with a window of class "
                f"{self.state['window_class']} is open and focused.\n\n## Steps\n\n" + '\n'.join(lines) +
                '\n\nUse the structured selector first; the recorded relative point is a last resort only. '
                'Verify the expected change after every step.\n')


def promote(skills, session, replay, name):
    """Pillar A hand-off: only a verified replay becomes a provisional CAPTURED skill (never trusted here)."""
    if not replay.get('verified'):
        raise ValueError('Demonstration replay was not verified; no skill created.')
    from .skill_evolution import SkillEvolution, _write_skill, validate_skill
    body = session.skill_body(name)
    validate_skill(body, name)
    provenance = {'origin': 'captured', 'source': 'show_me_once', 'demonstration_id': session.identifier,
                  'steps': len(session.state['steps']), 'replay': {k: replay[k] for k in ('provider', 'verified', 'expected')},
                  'at': now()}
    folder = _write_skill(skills.memory.base, name, body, provenance)
    return SkillEvolution(skills, registry=None)._register(folder, 'captured', [], 0, 'Captured from a consented demonstration',
                                                            None, provenance)


def _hook_main():
    import sys

    def emit(x, y, message, flags):
        print(x, y, message, flags, flush=True)
        sys.stdout.flush()
    HookProcess(emit).run()


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--hook']:
        _hook_main()
