"""Bounded Windows tasks that require an actual named window or folder."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import os
import tempfile
import time

from .commands import filename
from .names import common, rank


def _process_path(desktop, hwnd):
    pid = wintypes.DWORD()
    desktop.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value or pid.value == os.getpid():
        raise ValueError("Select the application to close first.")
    process = desktop.kernel.OpenProcess(0x1000, False, pid.value)
    if not process:
        raise ValueError("Windows did not allow checking the target application.")
    try:
        length = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(length.value)
        if not desktop.kernel.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
            raise ValueError("Windows did not allow checking the target application.")
        return Path(path.value)
    finally:
        desktop.kernel.CloseHandle(process)


def close_app(desktop, apps, requested="", cancelled=lambda: False, observed=None):
    uniquely_identified = False
    hwnd = desktop.user.GetForegroundWindow()
    pid = wintypes.DWORD()
    desktop.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == os.getpid():
        hwnd = desktop.target
    if pid.value == os.getpid() and requested and requested.casefold() not in {"this app", "this window", "current app", "current window", "the app", "the window"}:
        aliases = rank(requested, apps)
        expected = {Path(apps[alias][0]).name.casefold() for alias in aliases
                    if isinstance(apps[alias], list) and apps[alias]}
        expected.update(Path(apps[alias]["executable"]).name.casefold() for alias in aliases
                        if isinstance(apps[alias], dict) and apps[alias].get("executable"))
        found = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def inspect(window, _):
            if desktop.user.IsWindowVisible(window):
                try:
                    if _process_path(desktop, window).name.casefold() in expected:
                        found.append(window)
                except ValueError:
                    pass
            return True
        callback = callback_type(inspect)
        desktop.user.EnumWindows(callback, 0)
        if len(found) == 1:
            hwnd = found[0]
            uniquely_identified = True
        elif len(found) > 1:
            raise ValueError(f"Multiple {requested} windows are open. Select the one to close, then say close {requested}.")
    if not hwnd or not desktop.user.IsWindow(hwnd):
        raise ValueError("Select the application window you want to close first.")
    actual = _process_path(desktop, hwnd)
    if requested and requested.casefold() not in {"this app", "this window", "current app", "current window", "the app", "the window"}:
        aliases = rank(requested, apps)
        expected = set()
        for alias in aliases:
            entry = apps[alias]
            if isinstance(entry, list) and entry:
                expected.add(Path(entry[0]).name.casefold())
            elif isinstance(entry, dict) and entry.get("executable"):
                expected.add(Path(entry["executable"]).name.casefold())
        title = ctypes.create_unicode_buffer(512)
        desktop.user.GetWindowTextW(hwnd, title, len(title))
        packaged_name_matches = not expected and bool(rank(requested, apps)) and common(requested) in common(title.value)
        if not expected and not packaged_name_matches:
            raise ValueError(f"I cannot identify '{requested}' in the selected window. Select it and say close this app.")
        if expected and actual.name.casefold() not in expected:
            raise ValueError(f"The selected window is {actual.name}, not {requested}; nothing was closed.")
    if cancelled():
        return "Closing cancelled"
    foreground = desktop.user.GetForegroundWindow()
    if foreground not in {hwnd}:
        foreground_pid = wintypes.DWORD()
        desktop.user.GetWindowThreadProcessId(foreground, ctypes.byref(foreground_pid))
        if foreground_pid.value != os.getpid() or (desktop.target != hwnd and not uniquely_identified):
            raise ValueError("The selected window changed; nothing was closed.")
    from .experience_memory import observe_conditions
    from types import SimpleNamespace
    known = observe_conditions(SimpleNamespace(desktop=desktop), handle=hwnd, tools=[])
    if not desktop.user.PostMessageW(hwnd, 0x0010, 0, 0):  # WM_CLOSE; lets apps show Save prompts.
        raise ValueError('Windows did not accept the close request; inspect the current app state.')
    def report_outcome(state, evidence, verified):
        if observed is not None:
            observed({'state': state, 'app_name': actual.name.casefold(),
                      'source': 'window_state', 'evidence': evidence, 'verified': verified,
                      'conditions': known})
    for _ in range(15):
        if not desktop.user.IsWindow(hwnd):
            if desktop.target == hwnd:
                desktop.target = None
            evidence = f'{actual.name} window no longer exists; process exit is not established.'
            report_outcome('window_destroyed', evidence, True)
            return f"Closed {actual.name} window; process exit is not established."
        if not desktop.user.IsWindowVisible(hwnd):
            evidence = f'{actual.name} window is hidden after Close; tray presence and process exit are not established.'
            report_outcome('window_hidden', evidence, True)
            return f'Closed visible {actual.name} window: it became hidden; process exit is not established.'
        if cancelled():
            report_outcome('close_pending', f'{actual.name} Close was requested; observation stopped before a result was established.', False)
            return "Close requested; check the app for a Save prompt."
        time.sleep(.1)
    report_outcome('window_still_visible', f'{actual.name} window remained visible after Close; completion is not verified. Check for a Save prompt.', False)
    return f"Close requested for {actual.name}; check the app for a Save prompt."


def write_new_file(folder, name, content, cancelled=lambda: False):
    folder = Path(folder).resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("The selected folder no longer exists.")
    name = filename(name)
    path = folder / name
    if path.is_symlink() or path.resolve().parent != folder:
        raise ValueError("The file must be directly inside the selected folder.")
    if cancelled():
        return None
    with path.open("x", encoding="utf-8") as file:
        file.write(content)
    return path


def modify_text_file(folder, name, find, replacement, cancelled=lambda: False):
    """Replace one exact snippet, or the full text when find is empty."""
    folder = Path(folder).resolve(strict=True)
    path = folder / filename(name)
    if path.is_symlink() or path.resolve().parent != folder or not path.is_file():
        raise ValueError("Choose an existing regular file directly inside the named folder.")
    if path.stat().st_size > 2_000_000:
        raise ValueError("The file is too large for Jarvis text editing.")
    def read_exact():
        with path.open("r", encoding="utf-8", newline="") as source:
            return source.read()

    try:
        original = read_exact()
    except UnicodeDecodeError as exc:
        raise ValueError("Jarvis can modify UTF-8 text files only.") from exc
    if find:
        if original.count(find) != 1:
            raise ValueError("The text to replace must occur exactly once; the file was not changed.")
        updated = original.replace(find, replacement, 1)
    else:
        updated = replacement
    if cancelled():
        return None
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=folder,
                prefix=".jarvis-edit-", delete=False) as output:
            temporary = Path(output.name)
            output.write(updated)
        if cancelled():
            return None
        if read_exact() != original:
            raise ValueError("The file changed while Jarvis was editing it; no update was applied.")
        os.replace(temporary, path)
        temporary = None
        return path
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
