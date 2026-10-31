"""One Save-dialog recipe for both save tools (flag control.shared_save, default off).

`app_act save_as` already saves through the app's own Save As dialog with UI Automation: it refuses to
overwrite and proves the file on disk (`ControlService._save_as`). With the flag on, the older `save_file` tool
uses that same recipe for a new file in the app window Jarvis is working in. Everything else stays on the
existing visual Save path, decided **before** any key is sent:

- the target already exists (that path asks the user before replacing it);
- no app window is known (the task did not open or read one through the control tools).

After the recipe has sent its shortcut there is no fallback: input may have reached the app, so a failure is
reported and nothing is repeated.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional


def target(actions: Any, step: Dict[str, Any], cancelled: Callable[[], bool]) -> Path:
    """The requested file in the requested folder, resolved like the visual Save path (no links)."""
    from ..commands import filename
    from ..skill_memory import linked
    name = filename(step['value'])
    selected = Path(actions._task_folder(step['folder'], cancelled))
    if any(linked(p) for p in (selected, *selected.parents)):
        raise ValueError('The Save destination contains a linked path.')
    folder = selected.resolve(strict=True)
    path = folder / str(name)
    if any(linked(p) for p in [path, folder, *folder.parents]):
        raise ValueError('The Save destination contains a linked path.')
    return path


def save_file_step(actions: Any, step: Dict[str, Any], cancelled: Callable[[], bool]) -> Optional[str]:
    """Evidence after a save through the shared recipe, or None to use the visual path (nothing was sent)."""
    path = target(actions, step, cancelled)
    if path.exists():
        return None
    control = actions.control()
    scope = str(getattr(control, 'app_scope', '') or '')
    if not scope.startswith('win-') or not scope[4:].isdigit():
        return None
    from .types import ControlError
    try:
        report = control.app_act('save_as', {'text': str(path), 'window': scope[4:]}, cancelled)
    except ControlError as error:
        raise ValueError(str(error)) from None
    head = json.loads(report.split('\n', 1)[0])
    if head.get('ok') is not True or not path.is_file():
        raise ValueError('Save As did not produce ' + str(path) + '; the shortcut was not repeated. ' +
                         str(head.get('result') or head.get('evidence') or '')[:200])
    return f'Saved {path} through the Save As dialog; file verified on disk ({path.stat().st_size} bytes).'
