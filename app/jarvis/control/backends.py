"""Which PC and web control backend runs. Default legacy everywhere; one-line rollback.

    JARVIS_PC_BACKEND  / control.pc_backend  = legacy | shadow | agent_desktop
    JARVIS_WEB_BACKEND / control.web_backend = legacy | shadow | agent_browser

The environment variable wins over config/config.json. Anything unrecognised reads as legacy.
Per-category routing (Phase 4 of docs/control/ADAPTER_PLAN.md) may later name categories in
``control.pc_backend_by_app`` ({"spotify.exe": "agent_desktop", ...}); unset means the global value.
"""
from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Tuple

PC = ('legacy', 'shadow', 'agent_desktop')
WEB = ('legacy', 'shadow', 'agent_browser')


def _pick(env_name: str, key: str, allowed: Tuple[str, ...], config: Any, environ: Optional[Mapping[str, str]]) -> str:
    value = (environ if environ is not None else os.environ).get(env_name, '').strip().lower()
    if value in allowed:
        return value
    section = config.get('control', {}) if isinstance(config, Mapping) else {}
    value = str((section or {}).get(key, 'legacy')).strip().lower() if isinstance(section, Mapping) else 'legacy'
    return value if value in allowed else 'legacy'


def pc_backend(config: Any = None, environ: Optional[Mapping[str, str]] = None) -> str:
    return _pick('JARVIS_PC_BACKEND', 'pc_backend', PC, config, environ)


def web_backend(config: Any = None, environ: Optional[Mapping[str, str]] = None) -> str:
    return _pick('JARVIS_WEB_BACKEND', 'web_backend', WEB, config, environ)
