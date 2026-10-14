"""Read-only adapter to existing app configuration and Windows UI transport."""
from pathlib import Path
import os
import psutil

def matches(entry, actual):
    """Only exact configured paths, including explicitly configured GUI binaries."""
    paths = [entry.get('executable', '')] if isinstance(entry, dict) else [str(entry)]
    if isinstance(entry, dict) and isinstance(entry.get('observation_executables'), list):
        paths += [p for p in entry['observation_executables'] if isinstance(p, str)]
    return any(p and Path(p).resolve() == actual.resolve() for p in paths)

def foreground(actions):
    ui = actions._ui()
    handle = ui._handle()
    import win32process
    actual = Path(psutil.Process(win32process.GetWindowThreadProcessId(handle)[1]).exe())
    return ui, handle, actual

def inspect(actions, name, cancelled):
    apps = getattr(actions, 'apps', {})
    observed = None
    if name.casefold() == 'current':
        if cancelled():
            raise InterruptedError('Cancelled before current application discovery.')
        observed = foreground(actions)
        name = next((key for key, entry in apps.items() if matches(entry, observed[2])), '')
    key = next((key for key in apps if key.casefold() == name.casefold()), None)
    if key is None:
        raise ValueError('Application is not configured; no guessed executable was launched.')
    entry = apps[key]
    executable = entry.get('executable', '') if isinstance(entry, dict) else str(entry)
    path = Path(executable) if executable else None
    version = 'unknown'
    if path and path.is_file():
        try:
            import win32api
            info = win32api.GetFileVersionInfo(str(path), '\\')
            version = '{}.{}.{}.{}'.format(info['FileVersionMS'] >> 16, info['FileVersionMS'] & 65535,
                info['FileVersionLS'] >> 16, info['FileVersionLS'] & 65535)
        except Exception:
            pass
    controls = []
    if not cancelled():
        try:
            ui, handle, actual = observed or foreground(actions)
            # Read the live process identity, never infer it from a window title.
            if matches(entry, actual):
                snapshot = ui.runner({'operation': 'list', 'handle': handle, 'owner_pid': os.getpid()}, cancelled)
                from .knowledge_acquisition import safe_controls
                controls = safe_controls(snapshot.get('controls', []))
        except (ValueError, OSError, AttributeError, psutil.Error):
            pass
    return {'identity': key.casefold(), 'configured': True, 'installed': bool(path and path.is_file()),
            'version': version, 'controls': controls, 'scope': 'Names/roles only; no fields, screenshots, coordinates or actions.'}
