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
    # The brain verifies save_file against this record (varied live gate 2026-10-31: without it a correct save was
    # reported as "no longer matches its independent disk readback").
    fallback = getattr(getattr(actions, 'brain', None), 'visual_fallback', None)
    if fallback is not None:
        state = fallback.file_state(path)
        if isinstance(state, dict):
            fallback.last_saved = {'path': path, **state}
    return f'Saved {path} through the Save As dialog; file verified on disk ({path.stat().st_size} bytes).'


NAME_KEYS = ('text', 'filename', 'file_name', 'name', 'file', 'path')


def save_as_args(actions: Any, args: Dict[str, Any], cancelled: Callable[[], bool]) -> Dict[str, Any]:
    """`app_act save_as` with a file name and a folder (as `create_file` takes them) gets the full path.

    Live S3 (2026-10-31): the planner sent {"filename": "shopping.txt", "folder": "Jarvis test"} three runs out of
    three. Anything that does not resolve stays as it was, so save_as reports its own error and sends nothing.
    """
    text = args.get('text')
    if isinstance(text, str) and Path(text.strip().strip('"')).is_absolute():
        return args
    name = next((args[k] for k in NAME_KEYS if isinstance(args.get(k), str) and args[k].strip()), None)
    folder = args.get('folder')
    if name is None or not isinstance(folder, str) or not folder.strip():
        return args
    name = name.strip().strip('"')
    if Path(name).name != name or not Path(name).suffix:
        return args
    try:
        path = target(actions, {'value': name, 'folder': folder}, cancelled)
    except (ValueError, OSError):
        return args
    return {**args, 'text': str(path)}
