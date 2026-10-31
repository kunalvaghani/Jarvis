"""App-API routes (flag control.api_routes, default off).

Document tools build files through the app's API (background Blender, Office file formats) and read them back.
When the user's request names the app ("Open Blender, add a cylinder ... save cylinder.blend"), they expect to see
the result there. The planner's follow-up `open cylinder.blend` failed (live H2, 2026-10-30): `open` resolves names
through the file catalog, which does not know a file made seconds ago. `show_document` opens the exact verified
file instead, by its full path in the task folder, with the app Windows associates with it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Dict, Optional

# Document tool -> (file suffix, words that mean the user named the app, app name for the report).
APPS = {
    'blender_task': ('.blend', r'\bblender\b', 'Blender'),
    'office_xlsx': ('.xlsx', r'\bexcel\b', 'Excel'),
    'office_docx': ('.docx', r'\b(?:ms |microsoft )?word\b(?! document)|\bin word\b', 'Word'),
}


def verified_file(actions: Any, step: Dict[str, Any], evidence: str, cancelled: Callable[[], bool]) -> Optional[Path]:
    """The file a document tool reported as verified, inside the task folder, or None."""
    try:
        row = json.loads(evidence)
    except (TypeError, ValueError):
        return None
    if not isinstance(row, dict) or row.get('verification') != 'verified' or not isinstance(row.get('file'), str):
        return None
    folder = Path(actions._task_folder(step.get('folder', ''), cancelled)).resolve(strict=True)
    path = (folder / Path(row['file']).name).resolve()
    return path if path.parent == folder and path.is_file() else None


def show_document(actions: Any, step: Dict[str, Any], evidence: str, goal: str, cancelled: Callable[[], bool],
                  start: Optional[Callable[[str], None]] = None) -> str:
    """Evidence, plus "Opened ... in <app>." when the user named the app and the verified file was opened."""
    name = step.get('action', '')
    if name not in APPS or cancelled():
        return evidence
    suffix, words, app = APPS[name]
    if not re.search(words, goal, re.I):
        return evidence
    try:
        path = verified_file(actions, step, evidence, cancelled)
    except (OSError, ValueError):
        return evidence
    if path is None or path.suffix.lower() != suffix:
        return evidence
    try:
        (start or os.startfile)(str(path))  # Windows: the app associated with the file type.
    except OSError as error:
        return evidence + f'\nThe file is saved, but {app} did not open it: {error}'
    return evidence + f'\nOpened {path} in {app} so the user can see it; do not open it again.'
