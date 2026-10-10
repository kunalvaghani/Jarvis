"""Bring a just-launched app's window to the foreground so observation targets it.

Windows' focus-stealing prevention often leaves the previous window in front when
a background process launches an app. Without this, Jarvis would observe and verify
the wrong window. Only visible top-level windows of the named executable are used.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import time

SW_MINIMIZE = 6
SW_RESTORE = 9


def _process_name(kernel, pid):
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ''
    try:
        length = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(length.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
            return ''
        return Path(path.value).name.casefold()
    finally:
        kernel.CloseHandle(handle)


def windows(executable, user=None, kernel=None):
    """Visible titled top-level windows of one executable, in Z order (front first)."""
    if os.name != 'nt' or not executable:
        return []
    user = user or ctypes.WinDLL('user32', use_last_error=True)
    kernel = kernel or ctypes.WinDLL('kernel32', use_last_error=True)
    wanted, found = Path(executable).name.casefold(), []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd, _):
        if user.IsWindowVisible(hwnd) and user.GetWindowTextLengthW(hwnd) > 0 and not user.GetWindow(hwnd, 4):
            pid = wintypes.DWORD()
            user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value != os.getpid() and _process_name(kernel, pid.value) == wanted:
                buffer = ctypes.create_unicode_buffer(512)
                user.GetWindowTextW(hwnd, buffer, 512)
                found.append((int(hwnd), buffer.value))
        return True
    user.EnumWindows(callback_type(visit), 0)
    return found


def focus(hwnd, user=None, kernel=None):
    """Restore and raise one window without sending any keystroke.

    An ALT tap would also satisfy Windows' foreground rule, but it switches apps such
    as Notepad and Office into menu-shortcut mode, so typed text becomes commands.
    Attaching to the foreground thread's input queue grants the same permission.
    """
    user = user or ctypes.WinDLL('user32', use_last_error=True)
    kernel = kernel or ctypes.WinDLL('kernel32', use_last_error=True)
    if user.IsIconic(hwnd):
        user.ShowWindow(hwnd, SW_RESTORE)
    foreground = user.GetForegroundWindow()
    if int(foreground or 0) == int(hwnd):
        return True
    current = kernel.GetCurrentThreadId()
    other = user.GetWindowThreadProcessId(foreground, None) if foreground else 0
    attached = bool(other and other != current and user.AttachThreadInput(current, other, True))
    try:
        user.BringWindowToTop(hwnd)
        user.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user.AttachThreadInput(current, other, False)
    if int(user.GetForegroundWindow()) != int(hwnd):
        # Minimise/restore is the documented way an app regains activation.
        user.ShowWindow(hwnd, SW_MINIMIZE)
        user.ShowWindow(hwnd, SW_RESTORE)
        user.SetForegroundWindow(hwnd)
    return int(user.GetForegroundWindow()) == int(hwnd)


def focus_app(executable, title_hint='', timeout=4.0, cancelled=lambda: False, sleep=time.sleep):
    """Wait briefly for the app's window and focus it. Returns the handle, or None."""
    deadline = time.monotonic() + timeout
    hint = title_hint.casefold()
    while time.monotonic() < deadline and not cancelled():
        rows = windows(executable)
        if rows:
            preferred = [row for row in rows if hint and hint in row[1].casefold()]
            hwnd = (preferred or rows)[0][0]
            if focus(hwnd):
                return hwnd
        sleep(.2)
    return None
