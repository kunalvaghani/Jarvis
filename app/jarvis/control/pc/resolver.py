"""App-name resolver: "open spotify" / "spotfy" / "vs code" -> something ``agent-desktop launch`` can start.

agent-desktop launches an absolute exe path or a bare System32 name, not a display name. Sources, in order:
Jarvis's own short names, Start menu entries (``Get-StartApps``: desktop shortcuts and Store app ids), and the
App Paths registry. Store apps (Spotify, WhatsApp, Notepad, Calculator) have no exe path: they launch through
``explorer.exe shell:AppsFolder\\<AUMID>`` and are then found by ``wait --event window-opened``.

Resolving a name grants nothing: the caller still checks Jarvis's allowed-app policy before launching.
"""
from __future__ import annotations

from dataclasses import dataclass
import difflib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple

APP = Path(__file__).resolve().parents[3]
CACHE = APP / '.jarvis-runtime' / 'state' / 'app-resolver.json'
CACHE_SECONDS = 24 * 3600
# Spoken names and nicknames -> Start menu display names (or System32 names).
ALIASES = {'calculator': 'Calculator', 'calc': 'Calculator', 'notepad': 'Notepad', 'paint': 'mspaint.exe',
           'explorer': 'explorer.exe', 'file explorer': 'explorer.exe', 'files': 'explorer.exe',
           'vs code': 'Visual Studio Code', 'vscode': 'Visual Studio Code', 'code': 'Visual Studio Code',
           'chrome': 'Google Chrome', 'google chrome': 'Google Chrome', 'spotify': 'Spotify',
           'whatsapp': 'WhatsApp', 'discord': 'Discord', 'blender': 'Blender', 'settings': 'Settings',
           'task manager': 'Task Manager', 'word': 'Word', 'excel': 'Excel'}
SYSTEM = {'mspaint.exe', 'explorer.exe', 'notepad.exe', 'calc.exe', 'taskmgr.exe', 'cmd.exe'}
# Process image a launched app shows up as (for wait/snapshot --app and the allowed-app policy).
IMAGES = {'Calculator': 'CalculatorApp.exe', 'Notepad': 'Notepad.exe', 'Spotify': 'Spotify.exe',
          'WhatsApp': 'WhatsApp.exe', 'Visual Studio Code': 'Code.exe', 'Google Chrome': 'chrome.exe',
          'Discord': 'Discord.exe', 'Settings': 'SystemSettings.exe', 'Task Manager': 'Taskmgr.exe',
          'mspaint.exe': 'mspaint.exe', 'explorer.exe': 'explorer.exe'}


@dataclass(frozen=True)
class Launchable:
    name: str            # display name it resolved to
    target: str          # what to pass to `agent-desktop launch`
    args: Tuple[str, ...] = ()  # extra --arg values (Store apps: the shell:AppsFolder id)
    image: str = ''      # expected process image, e.g. Spotify.exe
    store: bool = False
    score: float = 1.0   # 1.0 exact; lower = fuzzy

    def describe(self) -> str:
        return f'{self.name} ({"Store app" if self.store else self.target})'


def start_apps() -> Dict[str, str]:
    """Start menu display name -> AppID (exe path for desktop apps, AUMID for Store apps). Cached for a day."""
    try:
        cached = json.loads(CACHE.read_text(encoding='utf-8'))
        if time.time() - cached.get('at', 0) < CACHE_SECONDS and cached.get('apps'):
            return dict(cached['apps'])
    except (OSError, ValueError):
        pass
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command',
                              'Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress'],
                             capture_output=True, text=True, timeout=20,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
        rows = json.loads(out or '[]')
        rows = rows if isinstance(rows, list) else [rows]
        apps = {str(r['Name']): str(r['AppID']) for r in rows if r.get('Name') and r.get('AppID')}
    except (OSError, ValueError, subprocess.SubprocessError):
        apps = {}
    if apps:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({'at': time.time(), 'apps': apps}), encoding='utf-8')
    return apps


def app_paths(name: str) -> Optional[str]:
    """HKLM/HKCU ...\\App Paths\\<name>.exe default value."""
    try:
        import winreg
    except ImportError:
        return None
    exe = name if name.lower().endswith('.exe') else name + '.exe'
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, rf'Software\Microsoft\Windows\CurrentVersion\App Paths\{exe}') as key:
                value = winreg.QueryValue(key, None)
                if value and Path(value.strip('"')).is_file():
                    return value.strip('"')
        except OSError:
            continue
    return None


def _launchable(name: str, app_id: str, score: float) -> Launchable:
    image = IMAGES.get(name, '')
    if re.match(r'^[A-Za-z]:\\', app_id) and app_id.lower().endswith('.exe'):
        return Launchable(name, app_id, (), image or Path(app_id).name, False, score)
    # A Store/packaged app id (AUMID, or a registered id such as Microsoft.VisualStudioCode).
    return Launchable(name, 'explorer.exe', (f'shell:AppsFolder\\{app_id}',), image, True, score)


def resolve(spoken: str, apps: Optional[Dict[str, str]] = None) -> Optional[Launchable]:
    """Best launch target for a spoken app name, or None. Fuzzy matches report score < 1."""
    query = ' '.join(str(spoken or '').lower().replace('.exe', '').split())
    if not query:
        return None
    target = ALIASES.get(query, '')
    if target.lower() in SYSTEM:
        return Launchable(target, target, (), IMAGES.get(target, target), False, 1.0)
    if query + '.exe' in SYSTEM:
        return Launchable(query + '.exe', query + '.exe', (), query + '.exe', False, 1.0)
    apps = start_apps() if apps is None else apps
    by_lower = {k.lower(): k for k in apps}
    exact = by_lower.get((target or query).lower())
    if exact:
        return _launchable(exact, apps[exact], 1.0)
    starts = [k for k in apps if k.lower().startswith(query)]
    if len(starts) == 1:
        return _launchable(starts[0], apps[starts[0]], 0.95)
    path = app_paths(query)
    if path:
        return Launchable(Path(path).stem, path, (), Path(path).name, False, 0.95)
    candidates = list(by_lower) + list(ALIASES)
    close = difflib.get_close_matches(query, candidates, n=1, cutoff=0.72)
    if close:
        name = ALIASES.get(close[0], by_lower.get(close[0], ''))
        if name.lower() in SYSTEM:
            return Launchable(name, name, (), IMAGES.get(name, name), False, 0.8)
        real = by_lower.get(name.lower())
        if real:
            return _launchable(real, apps[real], 0.8)
    return None


def candidates(spoken: str, apps: Optional[Dict[str, str]] = None, n: int = 3) -> List[str]:
    """For a "did you mean" answer when nothing resolved."""
    apps = start_apps() if apps is None else apps
    return difflib.get_close_matches(str(spoken).lower(), [k.lower() for k in apps], n=n, cutoff=0.5)


def _env_root() -> str:
    return os.environ.get('SystemRoot', r'C:\Windows')
