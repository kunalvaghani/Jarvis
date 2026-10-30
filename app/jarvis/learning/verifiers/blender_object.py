"""Blender object saved: headless Blender opens the .blend and measures the named object."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional, Sequence

from .base import Verdict, Verifier, judged, unverifiable

BLENDER = Path(r'D:\blender.exe')
SCRIPT = r'''
import bpy, json, sys
o = bpy.data.objects.get(sys.argv[sys.argv.index("--") + 1])
row = {"found": o is not None}
if o is not None:
    row.update(type=o.type, dims=[round(v, 4) for v in o.dimensions], loc=[round(v, 4) for v in o.matrix_world.translation],
               verts=len(o.data.vertices) if o.type == "MESH" else 0)
print("ORACLE" + json.dumps(row))
'''
Run = Callable[..., Any]


def measure(path: Path, name: str, blender: Path, run: Run = subprocess.run, timeout: float = 180) -> Optional[Dict[str, Any]]:
    """The object's type, dimensions and world location as headless Blender reports them; None if unreadable."""
    with tempfile.TemporaryDirectory() as folder:
        script = Path(folder) / 'measure.py'
        script.write_text(SCRIPT, encoding='utf-8')
        out = run([str(blender), '-b', str(path), '--python', str(script), '--', name],
                  capture_output=True, text=True, timeout=timeout)
    match = re.search(r'ORACLE(\{.*\})', str(getattr(out, 'stdout', '') or ''))
    if not match:
        return None
    row = json.loads(match.group(1))
    return row if isinstance(row, dict) else None


class BlenderObject(Verifier):
    NAME = 'blender_object'
    READS = frozenset({'file', 'process'})

    def check(self, *, path: str | Path, name: str, object_type: str = 'MESH', dims: Optional[Sequence[float]] = None,
              location: Optional[Sequence[float]] = (0.0, 0.0, 0.0), tolerance: float = 0.01,
              blender: str | Path = BLENDER, run: Run = subprocess.run, **_: Any) -> Verdict:
        target, executable = Path(path), Path(blender)
        evidence: Dict[str, Any] = {'path': str(target), 'object': name}
        if not target.is_file():
            return judged([f'{target} was not saved'], evidence)
        if not executable.is_file():
            return unverifiable(f'Blender is not available at {executable}', evidence)
        try:
            row = measure(target, name, executable, run)
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            return unverifiable(f'headless Blender failed: {type(error).__name__}', evidence)
        if row is None:
            return unverifiable('headless Blender could not read the file', evidence)
        evidence['measured'] = row
        problems: List[str] = []
        if not row.get('found') or row.get('type') != object_type:
            problems.append(f'no {object_type.lower()} named {name} ({row})')
        else:
            if dims is not None and (len(row['dims']) != len(dims) or
                                     any(abs(a - b) > tolerance for a, b in zip(row['dims'], dims))):
                problems.append(f'size wrong: dims {row["dims"]}, expected {list(dims)}')
            if location is not None and any(abs(a - b) > tolerance for a, b in zip(row['loc'], location)):
                problems.append(f'position wrong: location {row["loc"]}, expected {list(location)}')
        return judged(problems, evidence)


def check(**params: Any) -> Verdict:
    return BlenderObject().check(**params)
