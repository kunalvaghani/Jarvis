"""Route 3: Windows UI Automation executor (doc sections 11.2-11.3, 12.3).

Talks to IUIAutomation directly through comtypes (the `uiautomation` package switches the process
to per-monitor DPI v1 on import, see ADR 0002). One cache request reads a window's whole subtree
in a single cross-process call. Refs are keyed by UIA runtime id inside a window scope. Actions
use control patterns first; real input (input.Input) is the fallback when no pattern applies.
Elevated windows, the secure desktop and Chromium windows with renderer accessibility off are
detected and reported, never failed silently.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ..executor import Health, RouteExecutor
from ..input import Input
from ..policy import Policy
from ..refs import RefRegistry
from ..timing import StageTimer
from ..types import Action, ActionResult, ControlError, ErrorCategory, Observation, Ref, Route

CONTROL_TYPES = {50000: 'Button', 50001: 'Calendar', 50002: 'CheckBox', 50003: 'ComboBox', 50004: 'Edit',
                 50005: 'Hyperlink', 50006: 'Image', 50007: 'ListItem', 50008: 'List', 50009: 'Menu',
                 50010: 'MenuBar', 50011: 'MenuItem', 50012: 'ProgressBar', 50013: 'RadioButton',
                 50014: 'ScrollBar', 50015: 'Slider', 50016: 'Spinner', 50017: 'StatusBar', 50018: 'Tab',
                 50019: 'TabItem', 50020: 'Text', 50021: 'ToolBar', 50022: 'ToolTip', 50023: 'Tree',
                 50024: 'TreeItem', 50025: 'Custom', 50026: 'Group', 50027: 'Thumb', 50028: 'DataGrid',
                 50029: 'DataItem', 50030: 'Document', 50031: 'SplitButton', 50032: 'Window', 50033: 'Pane',
                 50034: 'Header', 50035: 'HeaderItem', 50036: 'Table', 50037: 'TitleBar', 50038: 'Separator',
                 50039: 'SemanticZoom', 50040: 'AppBar'}
INTERACTIVE = frozenset({'Button', 'CheckBox', 'ComboBox', 'Edit', 'Hyperlink', 'ListItem', 'MenuItem', 'RadioButton',
                         'Slider', 'Spinner', 'TabItem', 'TreeItem', 'DataItem', 'SplitButton', 'Document', 'HeaderItem'})
P = {'runtime_id': 30000, 'rect': 30001, 'pid': 30002, 'type': 30003, 'name': 30005, 'focused': 30008,
     'enabled': 30010, 'aid': 30011, 'class': 30012, 'password': 30019, 'offscreen': 30022,
     'can_expand': 30028, 'can_invoke': 30031, 'can_scroll': 30034, 'can_select': 30036, 'can_text': 30040,
     'can_toggle': 30041, 'can_value': 30043, 'value': 30045, 'readonly': 30046, 'expand_state': 30070,
     'selected': 30079, 'toggle_state': 30086}
PATTERN = {'invoke': 10000, 'value': 10002, 'scroll': 10004, 'expand': 10005, 'window': 10009,
           'select': 10010, 'text': 10014, 'toggle': 10015}
APPS = {'notepad': 'notepad.exe', 'calculator': 'calc.exe', 'explorer': 'explorer.exe', 'paint': 'mspaint.exe'}


@dataclass(frozen=True)
class Window:
    handle: int
    title: str
    class_name: str
    pid: int
    executable: str
    elevated: bool


@dataclass
class _Scope:
    window: Window
    elements: Dict[Tuple[int, ...], Any] = field(default_factory=dict)
    seen: Dict[Tuple[int, ...], Tuple[str, str]] = field(default_factory=dict)


def _process_info(pid: int) -> Tuple[str, bool]:
    """Executable path and elevation of a process ('' / True when access is denied)."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return '', True  # Denied to a medium-integrity caller: treat as protected/elevated.
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(1024)
        exe = buffer.value if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)) else ''
        token = wintypes.HANDLE()
        elevated = False
        if advapi.OpenProcessToken(handle, 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
            try:
                value, returned = wintypes.DWORD(), wintypes.DWORD()
                if advapi.GetTokenInformation(token, 20, ctypes.byref(value), 4, ctypes.byref(returned)):
                    elevated = bool(value.value)
            finally:
                kernel.CloseHandle(token)
        return exe, elevated
    finally:
        kernel.CloseHandle(handle)


def own_process_elevated() -> bool:
    return _process_info(os.getpid())[1]


def secure_desktop_active() -> bool:
    """UAC prompts, Ctrl+Alt+Del and the lock screen run on a desktop no app may automate."""
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    desktop = user32.OpenInputDesktop(0, False, 0x0001)  # DESKTOP_READOBJECTS
    if not desktop:
        return True
    try:
        name = ctypes.create_unicode_buffer(256)
        needed = wintypes.DWORD()
        user32.GetUserObjectInformationW(desktop, 2, name, ctypes.sizeof(name), ctypes.byref(needed))
        return name.value.lower() != 'default'
    finally:
        user32.CloseDesktop(desktop)


def top_windows() -> List[Window]:
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    rows: List[Window] = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def collect(hwnd: Any, _: Any) -> bool:
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):  # GW_OWNER: owned popups belong to their app window
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if title.value:
            exe, elevated = _process_info(pid.value)
            rows.append(Window(int(hwnd), title.value, cls.value, pid.value, exe, elevated))
        return True

    user32.EnumWindows(proc(collect), 0)
    return rows


class UIAExecutor(RouteExecutor):
    route = Route.UIA

    def __init__(self, policy: Policy, input: Input, clock: Callable[[], float] = time.monotonic) -> None:
        self.policy, self.input, self.clock = policy, input, clock
        self.refs = RefRegistry(Route.UIA, prefix='u')
        self.scopes: Dict[str, _Scope] = {}
        self._uia: Any = None
        self._mod: Any = None
        self._lock = threading.RLock()
        self._cancelled = threading.Event()
        self.elevated_self = own_process_elevated()
        self.launched: List[int] = []

    # COM -------------------------------------------------------------------
    def _client(self) -> Tuple[Any, Any]:
        if self._uia is None:
            from ..coords import ensure_per_monitor_dpi
            ensure_per_monitor_dpi()
            import comtypes
            import comtypes.client
            comtypes.CoInitialize()
            self._mod = comtypes.client.GetModule('UIAutomationCore.dll')
            self._uia = comtypes.client.CreateObject(self._mod.CUIAutomation, interface=self._mod.IUIAutomation)
        return self._uia, self._mod

    def health_check(self) -> Health:
        try:
            self._client()
            return Health(not secure_desktop_active(), 'secure desktop active' if secure_desktop_active() else 'ok',
                          {'elevated': self.elevated_self})
        except Exception as exc:
            return Health(False, type(exc).__name__)

    def cancel(self) -> None:
        self._cancelled.set()

    def close(self) -> None:
        self.scopes.clear()
        self._uia = None

    # Windows ---------------------------------------------------------------
    def windows(self) -> List[Window]:
        return top_windows()

    def window(self, query: str = '', handle: Optional[int] = None) -> Window:
        rows = self.windows()
        if handle is not None:
            match = [w for w in rows if w.handle == handle]
        else:
            q = query.lower()
            match = [w for w in rows if q in w.title.lower() or q == Path(w.executable).stem.lower()]
        if not match:
            raise ControlError(f'No open window matches {query or handle!r}.', ErrorCategory.TARGET_NOT_FOUND)
        if len(match) > 1 and handle is None:
            exact = [w for w in match if w.title.lower() == query.lower()]
            if len(exact) != 1:
                titles = '; '.join(w.title[:60] for w in match[:5])
                raise ControlError(f'Several windows match {query!r}: {titles}. Be more specific.',
                                   ErrorCategory.TARGET_NOT_FOUND)
            match = exact
        return match[0]

    def _admit(self, window: Window) -> None:
        if secure_desktop_active():
            raise ControlError('A secure-desktop prompt (UAC, lock screen) is showing; only you can answer it.',
                               ErrorCategory.SECURE_DESKTOP)
        if window.elevated and not self.elevated_self:
            raise ControlError(f'"{window.title[:60]}" runs as administrator. Windows blocks Jarvis from controlling '
                               'it (UIPI); please handle it yourself.', ErrorCategory.ELEVATED_TARGET)
        self.policy.check_app(window.executable or 'unknown.exe', window.elevated and not self.elevated_self)

    def launch(self, app: str, argument: str = '', timeout_s: float = 10.0) -> Window:
        """Start an allowlisted app (optionally with a confined file/folder) and wait for its window."""
        exe = APPS.get(app.lower())
        if exe is None:
            raise ControlError(f'{app!r} is not on the launch list ({", ".join(APPS)}).', ErrorCategory.POLICY_DENIED)
        args = [exe]
        expect = ''
        if argument:
            path = self.policy.confine(argument)
            args.append(str(path))
            expect = path.name if path.is_file() or not path.exists() else path.name
        before = {w.handle: w.title for w in self.windows()}
        subprocess.Popen(args, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = self.clock() + timeout_s
        stem = Path(exe).stem.lower()
        while self.clock() < deadline:
            for w in self.windows():
                fresh = w.handle not in before or before[w.handle] != w.title
                if fresh and ((expect and expect.lower() in w.title.lower()) or
                              (not expect and (stem in Path(w.executable).stem.lower() or app.lower() in w.title.lower()))):
                    self.launched.append(w.handle)
                    return w
            time.sleep(.1)
        raise ControlError(f'{app} did not show a window within {timeout_s:.0f} s.', ErrorCategory.TIMEOUT)

    def protected_foreground(self) -> Optional[str]:
        """Class name of a foreground window whose process is elevated/protected while Jarvis is not.

        In that state Windows (UIPI) silently drops every injected key and click, so input must not
        be attempted and the user must be told instead of a silent no-op.
        """
        if self.elevated_self:
            return None
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        handle = user32.GetForegroundWindow()
        if not handle:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if pid.value in (0, os.getpid()) or not _process_info(pid.value)[1]:
            return None
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(handle, name, 256)
        return name.value or 'unknown'

    def focus(self, window: Window) -> None:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        if user32.GetForegroundWindow() == window.handle:
            return
        blocker = self.protected_foreground()
        if blocker is not None:
            raise ControlError(f'A protected or administrator window ({blocker}) is in front, so Windows blocks all of '
                               "Jarvis's keyboard and mouse input. Click once on your desktop or the target app, then retry.",
                               ErrorCategory.ELEVATED_TARGET)
        if user32.IsIconic(window.handle):
            user32.ShowWindow(window.handle, 9)  # SW_RESTORE
        # Windows only lets the foreground owner hand focus over; a released Alt key satisfies that rule.
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(window.handle)
        if self._wait_foreground(window.handle, .5):
            return
        try:  # UI Automation asks the app itself to take focus.
            uia, _ = self._client()
            uia.ElementFromHandle(window.handle).SetFocus()
        except Exception:
            pass
        if self._wait_foreground(window.handle, .5):
            return
        # Last resort, as a user would: one click on plain caption space (never a tab or caption button).
        point = self._caption_point(window.handle)
        if point is not None:
            self.input.click(*point)
            if self._wait_foreground(window.handle, 1.0):
                return
        raise ControlError(f'Windows refused to bring "{window.title[:60]}" to the front.', ErrorCategory.FOCUS_LOST)

    def _wait_foreground(self, handle: int, seconds: float) -> bool:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        deadline = self.clock() + seconds
        while user32.GetForegroundWindow() != handle:
            if self.clock() >= deadline:
                return False
            time.sleep(.02)
        return True

    def _caption_point(self, handle: int) -> Optional[Tuple[int, int]]:
        """A point the window itself reports as HTCAPTION, visible and not covered by another window."""
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                               wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        rect = wintypes.RECT()
        user32.GetWindowRect(handle, ctypes.byref(rect))
        width = rect.right - rect.left
        for fy in (12, 8, 18):
            for fx in (.5, .62, .38, .75, .25):
                x, y = rect.left + int(width * fx), rect.top + fy
                answer = ctypes.c_size_t()
                lparam = (y & 0xFFFF) << 16 | (x & 0xFFFF)
                if not user32.SendMessageTimeoutW(handle, 0x0084, 0, lparam, 0x2, 200, ctypes.byref(answer)):
                    continue  # WM_NCHITTEST timed out: the app is hung
                top = user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(x, y)), 2)
                if answer.value == 2 and top == handle:  # HTCAPTION, and nothing covers it
                    return x, y
        return None

    def title_guard(self, window: Window, expected: str) -> None:
        """Right before keyboard input: the foreground window must be this one and show `expected`.

        Shared windows (Windows 11 Notepad tabs, browser tabs) switch content without changing the
        handle; the title is what proves the user's own document is not the one in front.
        """
        if not expected:
            return
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(window.handle, buffer, 512)
        if user32.GetForegroundWindow() != window.handle or expected.lower() not in buffer.value.lower():
            raise ControlError(f'The window in front shows "{buffer.value[:80]}", not "{expected[:80]}"; no keys were sent.',
                               ErrorCategory.FOCUS_LOST)

    # Observation -----------------------------------------------------------
    def _scope(self, window: Window) -> str:
        scope = f'win-{window.handle}'
        current = self.scopes.get(scope)
        if current is None or current.window.pid != window.pid:
            self.refs.invalidate(scope)
            self.scopes[scope] = _Scope(window)
        else:
            current.window = window
        return scope

    def read_window(self, window: Window, filter: str = 'interactive', depth: int = 25) -> Observation:
        if filter not in ('interactive', 'all'):
            raise ControlError('filter must be interactive or all.', ErrorCategory.INVALID_ARGUMENTS)
        with self._lock:
            uia, _ = self._client()
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            if not user32.IsWindow(window.handle):
                raise ControlError('The window was closed.', ErrorCategory.STALE_REF)
            scope = self._scope(window)
            state = self.scopes[scope]
            request = uia.CreateCacheRequest()
            for pid in P.values():
                request.AddProperty(pid)
            request.TreeScope = 7  # element + descendants
            root = uia.ElementFromHandle(window.handle).BuildUpdatedCache(request)
            lines: List[str] = []
            refs: List[Ref] = []
            live: List[Tuple[int, ...]] = []
            counts = {'elements': 0, 'documents': 0, 'document_children': 0}

            def prop(e: Any, name: str) -> Any:
                try:
                    return e.GetCachedPropertyValue(P[name])
                except Exception:
                    return None

            def visit(e: Any, level: int, indent: int, parent_type: str) -> None:
                if level > depth or len(lines) > 4000:
                    return
                counts['elements'] += 1
                kind = CONTROL_TYPES.get(int(prop(e, 'type') or 0), 'Custom')
                if parent_type == 'Document':
                    counts['document_children'] += 1
                if kind == 'Document':
                    counts['documents'] += 1
                rid = tuple(int(v) for v in (prop(e, 'runtime_id') or ()))
                name = str(prop(e, 'name') or '').strip()
                aid = str(prop(e, 'aid') or '')
                offscreen = bool(prop(e, 'offscreen'))
                actionable = any(prop(e, k) for k in ('can_invoke', 'can_value', 'can_toggle', 'can_select', 'can_expand'))
                keep = rid and not offscreen and (filter == 'all' or kind in INTERACTIVE or actionable)
                shown = indent
                if keep:
                    live.append(rid)
                    ref = self.refs.assign(scope, rid)
                    refs.append(ref)
                    state.elements[rid] = e
                    state.seen[rid] = (kind, name)
                    extras = []
                    if aid:
                        extras.append(f'aid={aid}')
                    if prop(e, 'can_value') and not prop(e, 'password'):
                        value = str(prop(e, 'value') or '')
                        if value:
                            extras.append(f'value={value[:120]!r}')
                    if prop(e, 'can_toggle'):
                        extras.append({0: 'off', 1: 'on', 2: 'mixed'}.get(int(prop(e, 'toggle_state') or 0), ''))
                    if prop(e, 'selected'):
                        extras.append('selected')
                    if prop(e, 'enabled') is False:
                        extras.append('disabled')
                    if prop(e, 'focused'):
                        extras.append('focused')
                    if prop(e, 'password'):
                        extras.append('password')
                    lines.append(f'{"  " * indent}{kind} "{name[:150]}" [{ref.id}]' + (' ' + ' '.join(extras) if extras else ''))
                    shown = indent + 1
                children = e.GetCachedChildren()
                if children:
                    for i in range(children.Length):
                        visit(children.GetElement(i), level + 1, shown, kind)

            visit(root, 0, 0, '')
            self.refs.retain(scope, live)
            warnings = []
            if window.class_name == 'Chrome_WidgetWin_1' and counts['documents'] and not counts['document_children']:
                warnings.append('This Chromium/Electron window exposes no web content to UI Automation '
                                '(renderer accessibility is off); use the browser route or vision.')
            if window.elevated and not self.elevated_self:
                warnings.append('Window is elevated: readable at most, never controllable.')
            return Observation(Route.UIA, scope, '\n'.join(lines), tuple(refs),
                               state={'title': window.title, 'handle': window.handle, 'pid': window.pid,
                                      'executable': window.executable, 'warnings': warnings, **counts})

    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        if scope and scope.startswith('win-'):
            window = self.window(handle=int(scope[4:]))
        else:
            window = self.window(str(options.get('window', '')), options.get('handle'))
        return self.read_window(window, options.get('filter', 'interactive'), options.get('depth', 25))

    # Resolution ---------------------------------------------------------------
    def _element(self, action: Action) -> Tuple[_Scope, Tuple[int, ...], Any]:
        target = action.target
        if not isinstance(target, Ref):
            scope = action.params.get('scope') or (f'win-{action.context.window}' if action.context.window else '')
            if not scope or not action.params.get('ref'):
                raise ControlError('This action needs a ref from a window read.', ErrorCategory.INVALID_ARGUMENTS)
            target = self.refs.lookup(str(scope), str(action.params['ref']))
        rid = self.refs.resolve(target)
        state = self.scopes.get(target.scope)
        if state is None or rid not in state.elements:
            raise ControlError(f'{target.id} is stale or not found. Re-read the window to get fresh references.',
                               ErrorCategory.STALE_REF)
        return state, rid, state.elements[rid]

    def _current(self, element: Any, state: _Scope, rid: Tuple[int, ...]) -> Tuple[str, str, bool]:
        try:
            kind = CONTROL_TYPES.get(int(element.CurrentControlType), 'Custom')
            name = str(element.CurrentName or '').strip()
            enabled = bool(element.CurrentIsEnabled)
            current = tuple(int(v) for v in element.GetRuntimeId())
        except Exception:
            raise ControlError('The control no longer exists. Re-read the window.', ErrorCategory.STALE_REF) from None
        if current != rid:
            raise ControlError('The control was replaced. Re-read the window.', ErrorCategory.STALE_REF)
        seen = state.seen.get(rid)
        if seen is not None and (kind, name) != seen:
            raise ControlError(f'The control changed after it was read (was {seen[0]} "{seen[1][:60]}", now {kind} '
                               f'"{name[:60]}"). Nothing was done; re-read the window.', ErrorCategory.STALE_REF)
        return kind, name, enabled

    def _pattern(self, element: Any, name: str) -> Any:
        _, mod = self._client()
        iface = {'invoke': mod.IUIAutomationInvokePattern, 'value': mod.IUIAutomationValuePattern,
                 'scroll': mod.IUIAutomationScrollPattern, 'expand': mod.IUIAutomationExpandCollapsePattern,
                 'window': mod.IUIAutomationWindowPattern, 'select': mod.IUIAutomationSelectionItemPattern,
                 'text': mod.IUIAutomationTextPattern, 'toggle': mod.IUIAutomationTogglePattern}[name]
        try:
            raw = element.GetCurrentPattern(PATTERN[name])
        except Exception:
            return None
        return raw.QueryInterface(iface) if raw else None

    # Probes ---------------------------------------------------------------------
    def probe(self, what: str, **params: Any) -> Any:
        if what == 'window_title':
            return self.window(handle=int(params['handle'])).title
        if what == 'windows':
            return [w.title for w in self.windows()]
        state = self.scopes.get(str(params.get('scope', '')))
        if state is None:
            raise ControlError('Unknown window scope; read the window first.', ErrorCategory.STALE_REF)
        rid = self.refs.resolve(self.refs.lookup(str(params['scope']), str(params['ref'])))
        element = state.elements[rid]  # type: ignore[index]
        if what == 'value':
            value = self._pattern(element, 'value')
            if value is not None:
                return str(value.CurrentValue)
            text = self._pattern(element, 'text')
            return str(text.DocumentRange.GetText(-1)) if text is not None else None
        if what == 'name':
            return str(element.CurrentName)
        if what == 'toggle':
            toggle = self._pattern(element, 'toggle')
            return int(toggle.CurrentToggleState) if toggle is not None else None
        if what == 'selected':
            sel = self._pattern(element, 'select')
            return bool(sel.CurrentIsSelected) if sel is not None else None
        if what == 'expanded':
            exp = self._pattern(element, 'expand')
            return int(exp.CurrentExpandCollapseState) if exp is not None else None
        raise ControlError(f'Unknown UIA probe {what!r}.', ErrorCategory.UNSUPPORTED)

    # Actions --------------------------------------------------------------------
    def act(self, action: Action) -> ActionResult:
        timer = StageTimer()
        with self._lock:
            try:
                result = self._dispatch(action, timer)
            except ControlError as error:
                return ActionResult.failure(action, error, timings_ms=timer.result())
            except Exception as error:
                return ActionResult(action.action_id, False, Route.UIA, text=f'{type(error).__name__}: {error}'[:300],
                                    executed=True, error_category=ErrorCategory.UNCERTAIN, timings_ms=timer.result())
        verified, evidence = result.verified, result.evidence
        if result.ok and action.expectation is not None:
            from ..verify import default_verifier
            with timer.stage('verify'):
                verified, evidence = default_verifier.wait(action.expectation, self.probe, action.timeout_s, action.cancel)
        ok = result.ok and (verified or action.expectation is None)
        return ActionResult(action.action_id, ok, Route.UIA, text=result.text, state=result.state,
                            executed=result.executed, verified=verified, evidence=evidence,
                            error_category=ErrorCategory.NONE if ok else ErrorCategory.VERIFICATION_FAILED,
                            timings_ms=timer.result())

    def _done(self, action: Action, text: str, executed: bool = True, verified: bool = False, evidence: str = '',
              **state: Any) -> ActionResult:
        return ActionResult(action.action_id, True, Route.UIA, text=text, executed=executed, verified=verified,
                            evidence=evidence, state=state)

    def _dispatch(self, action: Action, timer: StageTimer) -> ActionResult:
        name, p = action.name, action.params
        action.cancel.raise_if_cancelled()
        if name == 'launch':
            window = self.launch(str(p['app']), str(p.get('path', '')), action.timeout_s)
            return self._done(action, f'Opened {window.title}', verified=True, evidence='window appeared',
                              handle=window.handle, title=window.title)
        if name == 'list_windows':
            rows = [f'{w.title[:80]} | {Path(w.executable).name} | handle {w.handle}' + (' | elevated' if w.elevated else '')
                    for w in self.windows()]
            return self._done(action, '\n'.join(rows), executed=False, verified=True)
        if name in ('focus_window', 'read_window', 'type', 'key', 'close_window'):
            window = self.window(str(p.get('window', '')), p.get('handle') or action.context.window)
            self._admit(window)
            if name == 'read_window':
                with timer.stage('tree_read'):
                    obs = self.read_window(window, str(p.get('filter', 'interactive')))
                return self._done(action, obs.text, executed=False, verified=True, scope=obs.scope,
                                  warnings=obs.state['warnings'])
            if name == 'close_window':
                uia, _ = self._client()
                pattern = self._pattern(uia.ElementFromHandle(window.handle), 'window')
                if pattern is None:
                    raise ControlError('This window cannot be closed through UI Automation.', ErrorCategory.UNSUPPORTED)
                pattern.Close()
                return self._done(action, f'Asked "{window.title[:60]}" to close')
            with timer.stage('input'):
                self.focus(window)
                self.title_guard(window, str(p.get('expect_title', '')))
                if name == 'type':
                    self.input.enter(str(p['text']), action.cancel)
                elif name == 'key':
                    self.input.keys(str(p['text']), int(p.get('repeat', 1)), action.cancel)
            return self._done(action, f'{name} sent to "{window.title[:60]}"', executed=name != 'focus_window',
                              verified=name == 'focus_window')
        state, rid, element = self._element(action)
        self._admit(state.window)
        with timer.stage('tree_read'):
            kind, label, enabled = self._current(element, state, rid)
        if not enabled:
            raise ControlError(f'{kind} "{label[:60]}" is disabled.', ErrorCategory.NOT_ACTIONABLE)
        with timer.stage('input'):
            return self._pattern_action(action, element, kind, label, state)

    def _pattern_action(self, action: Action, element: Any, kind: str, label: str, state: _Scope) -> ActionResult:
        name, p = action.name, action.params
        if name in ('click', 'invoke'):
            for pattern_name in ('invoke', 'toggle', 'select', 'expand'):
                pattern = self._pattern(element, pattern_name)
                if pattern is None:
                    continue
                if pattern_name == 'invoke':
                    pattern.Invoke()
                    return self._done(action, f'Invoked {kind} "{label[:80]}"', evidence='InvokePattern')
                if pattern_name == 'toggle':
                    before = int(pattern.CurrentToggleState)
                    pattern.Toggle()
                    after = int(pattern.CurrentToggleState)
                    return self._done(action, f'Toggled "{label[:80]}"', verified=after != before,
                                      evidence=f'toggle state {before} -> {after}')
                if pattern_name == 'select':
                    pattern.Select()
                    return self._done(action, f'Selected "{label[:80]}"', verified=bool(pattern.CurrentIsSelected),
                                      evidence='SelectionItemPattern read back')
                pattern.Expand()
                return self._done(action, f'Expanded "{label[:80]}"', verified=int(pattern.CurrentExpandCollapseState) == 1,
                                  evidence='ExpandCollapsePattern read back')
            return self._mouse(action, element, state, label)
        if name == 'set_value':
            value = str(p['value'])
            if bool(element.GetCurrentPropertyValue(P['password'])):
                raise ControlError('Password fields are never filled automatically.', ErrorCategory.POLICY_DENIED)
            pattern = self._pattern(element, 'value')
            if pattern is not None and not bool(pattern.CurrentIsReadOnly):
                pattern.SetValue(value)
                current = str(pattern.CurrentValue)
                if current != value:
                    raise ControlError('The value did not match after setting it; check the field before repeating.',
                                       ErrorCategory.VERIFICATION_FAILED, executed=True)
                return self._done(action, f'Set "{label[:60]}"', verified=True, evidence='ValuePattern read back')
            if pattern is not None:
                raise ControlError(f'"{label[:60]}" is read-only.', ErrorCategory.NOT_ACTIONABLE)
            # Rich editors (e.g. Windows 11 Notepad) expose TextPattern only: focus, replace by keyboard, read back.
            text = self._pattern(element, 'text')
            if text is None:
                raise ControlError(f'{kind} "{label[:60]}" accepts no text through UI Automation.', ErrorCategory.UNSUPPORTED)
            self.focus(state.window)
            element.SetFocus()
            self.title_guard(state.window, str(p.get('expect_title', '')))
            self.input.keys('ctrl+a', cancel=action.cancel)
            self.input.enter(value, action.cancel)
            deadline = self.clock() + action.timeout_s
            current = ''
            while self.clock() < deadline:
                current = str(text.DocumentRange.GetText(-1)).replace('\r\n', '\n').replace('\r', '\n')
                if current.rstrip('\n') == value.replace('\r\n', '\n').rstrip('\n'):
                    return self._done(action, f'Typed into "{label[:60]}"', verified=True, evidence='TextPattern read back')
                time.sleep(.05)
            raise ControlError('Typed text did not read back as expected; inspect the editor before repeating.',
                               ErrorCategory.VERIFICATION_FAILED, executed=True)
        if name in ('toggle', 'select', 'expand', 'collapse'):
            pattern = self._pattern(element, 'expand' if name == 'collapse' else name)
            if pattern is None:
                raise ControlError(f'{kind} "{label[:60]}" does not support {name}.', ErrorCategory.UNSUPPORTED)
            if name == 'toggle':
                desired = p.get('state')
                before = int(pattern.CurrentToggleState)
                if desired is None or int(desired) != before:
                    pattern.Toggle()
                after = int(pattern.CurrentToggleState)
                return self._done(action, f'Toggle "{label[:60]}" is {after}',
                                  verified=after == int(desired) if desired is not None else after != before)
            if name == 'select':
                pattern.Select()
                return self._done(action, f'Selected "{label[:60]}"', verified=bool(pattern.CurrentIsSelected))
            (pattern.Expand if name == 'expand' else pattern.Collapse)()
            expected = 1 if name == 'expand' else 0
            return self._done(action, f'{name} "{label[:60]}"', verified=int(pattern.CurrentExpandCollapseState) == expected)
        if name == 'scroll':
            pattern = self._pattern(element, 'scroll')
            if pattern is None:
                raise ControlError(f'{kind} "{label[:60]}" is not scrollable.', ErrorCategory.UNSUPPORTED)
            direction = str(p.get('direction', 'down'))
            amounts = {'up': (2, 0), 'down': (2, 3), 'left': (0, 2), 'right': (3, 2)}
            if direction not in amounts:
                raise ControlError('scroll direction must be up, down, left or right.', ErrorCategory.INVALID_ARGUMENTS)
            was = (float(pattern.CurrentHorizontalScrollPercent), float(pattern.CurrentVerticalScrollPercent))
            pattern.Scroll(*amounts[direction])
            now = (float(pattern.CurrentHorizontalScrollPercent), float(pattern.CurrentVerticalScrollPercent))
            return self._done(action, f'Scrolled {direction}', verified=now != was, evidence=f'{was} -> {now}')
        if name == 'focus':
            element.SetFocus()
            return self._done(action, f'Focused "{label[:60]}"', verified=bool(element.CurrentHasKeyboardFocus))
        raise ControlError(f'Unsupported UIA action {name!r}.', ErrorCategory.UNSUPPORTED)

    def _mouse(self, action: Action, element: Any, state: _Scope, label: str) -> ActionResult:
        """No pattern applies: a real click at the control's centre, after a hit test."""
        rect = element.CurrentBoundingRectangle
        if rect.right - rect.left < 2 or rect.bottom - rect.top < 2:
            raise ControlError(f'"{label[:60]}" has no clickable area.', ErrorCategory.NOT_ACTIONABLE)
        x, y = (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
        uia, _ = self._client()
        point = wintypes.POINT(x, y)
        hit = uia.ElementFromPoint(point)
        target = tuple(int(v) for v in element.GetRuntimeId())
        walker = uia.ControlViewWalker
        node, ok = hit, False
        for _ in range(12):
            if node is None:
                break
            try:
                if tuple(int(v) for v in node.GetRuntimeId()) == target:
                    ok = True
                    break
                node = walker.GetParentElement(node)
            except Exception:
                break
        if not ok:
            raise ControlError(f'Something covers "{label[:60]}"; nothing was clicked.', ErrorCategory.NOT_ACTIONABLE)
        self.focus(state.window)
        method = self.input.click(x, y, cancel=action.cancel)
        return self._done(action, f'Clicked "{label[:60]}" ({method})', evidence=f'{method} at ({x}, {y})')


def tool_members() -> Sequence[str]:
    return ('launch', 'list_windows', 'read_window', 'focus_window', 'close_window', 'type', 'key', 'click',
            'invoke', 'set_value', 'toggle', 'select', 'expand', 'collapse', 'scroll', 'focus')


__all__ = ['UIAExecutor', 'Window', 'top_windows', 'secure_desktop_active', 'tool_members', 'Mapping']
