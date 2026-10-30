"""Sealed programmatic verifiers for learned skills (upgrade v2, Phase 0).

A verifier is written before the skill it judges, and the code that writes skills must not be able to change
it. MANIFEST.json holds the SHA-256 of every verifier file; `load()` refuses a verifier whose file no longer
matches. Only a developer re-seals, with `python -m jarvis.learning.verifiers --seal`, and the change is
reviewed like any other code change.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Dict, List, Type

from .base import Verdict, Verifier, weak

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'MANIFEST.json'
# Verifier name -> (module, class).
REGISTRY: Dict[str, tuple[str, str]] = {
    'text_file_saved': ('text_file', 'TextFileSaved'),
    'blender_object': ('blender_object', 'BlenderObject'),
    'python_project': ('python_project', 'PythonProject'),
}
SEALED = ('__init__.py', 'base.py', *sorted({f'{module}.py' for module, _ in REGISTRY.values()}))


class TamperedVerifier(RuntimeError):
    """A verifier file differs from its sealed hash; it is not used."""


def digest(path: Path) -> str:
    # Line endings normalised: a Git checkout may turn LF into CRLF without changing the code.
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def hashes(folder: Path = HERE) -> Dict[str, str]:
    return {name: digest(folder / name) for name in SEALED}


def tampered(folder: Path = HERE) -> List[str]:
    """Sealed files whose content differs from the manifest (or that are missing)."""
    try:
        sealed = json.loads((folder / 'MANIFEST.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return list(SEALED)
    bad = []
    for name in SEALED:
        try:
            if sealed.get(name) != digest(folder / name):
                bad.append(name)
        except OSError:
            bad.append(name)
    return bad


def load(name: str) -> Verifier:
    if name not in REGISTRY:
        raise KeyError(f'Unknown verifier {name!r}')
    bad = tampered()
    if bad:
        raise TamperedVerifier('Verifier files changed since they were sealed: ' + ', '.join(bad))
    module, cls = REGISTRY[name]
    kind: Type[Verifier] = getattr(importlib.import_module(f'{__name__}.{module}'), cls)
    if weak(kind):
        raise TamperedVerifier(f'{name} reads no real state; it could pass on a success message alone')
    return kind()


def seal() -> Dict[str, str]:
    values = hashes()
    MANIFEST.write_text(json.dumps(values, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return values


__all__ = ['Verdict', 'Verifier', 'TamperedVerifier', 'load', 'seal', 'tampered', 'weak', 'REGISTRY']
