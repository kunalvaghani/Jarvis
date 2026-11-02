"""JARVIS neural brain (BNEG): typed capability graph, durable signals, guarded routing, verified learning.

Architecture: docs/brain/ARCHITECTURE.md. Progress: docs/brain/PROGRESS.md. The package is named ``neural``
because ``jarvis/brain.py`` (today's planner) already owns the name ``brain``; docs and the UI say "brain".

Phase 0 (2026-11-02): only the mode switch exists. Nothing reads it yet, so Jarvis behaves exactly as before.
"""
from __future__ import annotations

import os
from typing import Any, Mapping, Optional

BRAIN_MODES = ('off', 'shadow', 'on')
ENVIRONMENT = 'JARVIS_BRAIN_MODE'


def brain_mode(config: Any, environ: Optional[Mapping[str, str]] = None) -> str:
    """'off' (legacy only), 'shadow' (legacy acts, the brain only plans and logs) or 'on' (the brain acts).

    The environment variable JARVIS_BRAIN_MODE overrides the config when it holds one of the three values, so
    ``JARVIS_BRAIN_MODE=off`` is a one-step rollback. Anything malformed falls back to the config, whose own
    malformed values read as off (jarvis.flags). The config mode 'act' means on; 'suggest' means shadow.
    """
    from .. import flags
    value = (environ if environ is not None else os.environ).get(ENVIRONMENT, '').strip().lower()
    if value in BRAIN_MODES:
        return value
    return {'off': 'off', 'shadow': 'shadow', 'suggest': 'shadow', 'act': 'on'}[flags.mode(config, 'neural', 'mode')]
