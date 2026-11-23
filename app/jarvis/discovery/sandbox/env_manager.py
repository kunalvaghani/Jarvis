"""Inspect the approved per-tool environment without installing or executing plugins.

Dependency isolation does not provide host security. Only the owned Pint worker
is executable in foundations; untrusted/generated tools still require Jarvis's
existing sandbox and explicit installation approval.
"""
from __future__ import annotations

import importlib.metadata
from pathlib import Path

APP = Path(__file__).resolve().parents[3]
EXPECTED = {'pint': '0.25.2', 'flexcache': '0.3', 'flexparser': '0.4',
            'platformdirs': '4.14.3', 'typing-extensions': '4.16.0'}


def units_environment():
    env = APP / '.venv-discovery-units'
    if env.is_symlink():
        raise ValueError('linked tool environments are not accepted')
    versions = {(d.metadata.get('Name') or '').lower().replace('_', '-'): d.version
                for d in importlib.metadata.distributions(path=[str(env / 'Lib/site-packages'),
                                                                str(env / 'lib/python3.11/site-packages')])}
    valid = all(versions.get(name) == version for name, version in EXPECTED.items())
    return {'environment': str(env), 'versions': {name: versions.get(name) for name in EXPECTED},
            'pins_match': valid, 'network_allowed': False, 'gpu_required': False,
            'network_isolation': 'owned worker CPython audit hook; not an OS sandbox',
            'sandbox_for_untrusted_code': False}
