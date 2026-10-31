"""Upgrade v2 feature flags (docs/adr/0005-upgrade-v2-flags-ledger-verifiers.md).

Every v2 capability is off unless config/config.json turns it on. A missing, malformed or unknown value reads
as off, so a damaged configuration can only switch features off, never on. Deciders move through the modes
off -> shadow (log only) -> suggest (an island card) -> act; only the user raises a mode, by editing the config.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

MODES: Tuple[str, ...] = ('off', 'shadow', 'suggest', 'act')

# (section, key) -> False for an on/off flag, 'off' for a decider mode. These are also the shipped values.
FLAGS: Dict[Tuple[str, str], Any] = {
    ('telemetry', 'timing_ledger'): False,
    ('telemetry', 'shadow_log'): False,
    ('speed', 'cache_order'): False,
    ('control', 'event_waits'): False,
    ('control', 'compact_reads'): False,
    ('control', 'form_fill'): False,
    ('control', 'shared_save'): False,
    ('control', 'api_routes'): False,
    ('vision', 'tight_escalation'): False,
    ('recipes', 'replay'): 'off',
    # Not in "brain": that section is sent to the brain worker with every request, which a flag must not change.
    ('fast_path', 'system1'): 'off',
    ('fast_path', 'plan_cache'): 'off',
    ('learning', 'mode'): 'off',
    ('learning', 'cloud_research'): False,
    ('learning', 'sleep_time'): False,
    ('memory_v2', 'facade'): False,
    ('memory_v2', 'ingest'): False,
    ('memory_v2', 'context_pack'): False,
    ('memory_v2', 'resolver'): 'off',
    ('proactive', 'enabled'): False,
}
SECTIONS: Tuple[str, ...] = tuple(sorted({section for section, _ in FLAGS}))


def _value(config: Any, section: str, key: str) -> Any:
    if (section, key) not in FLAGS:
        raise KeyError(f'Unknown v2 flag {section}.{key}')
    part = config.get(section) if isinstance(config, Mapping) else None
    return part.get(key) if isinstance(part, Mapping) else None


def enabled(config: Any, section: str, key: str) -> bool:
    """An on/off flag: on only for a literal JSON true."""
    if isinstance(FLAGS[(section, key)], str):
        raise KeyError(f'{section}.{key} is a mode; use mode()')
    return _value(config, section, key) is True


def mode(config: Any, section: str, key: str) -> str:
    """A decider's mode; anything but one of MODES reads as off."""
    if not isinstance(FLAGS[(section, key)], str):
        raise KeyError(f'{section}.{key} is on/off; use enabled()')
    value = _value(config, section, key)
    return value if isinstance(value, str) and value in MODES else 'off'


def at_least(config: Any, section: str, key: str, level: str) -> bool:
    if level not in MODES:
        raise ValueError(f'Unknown mode {level!r}')
    return MODES.index(mode(config, section, key)) >= MODES.index(level)


def defaults() -> Dict[str, Dict[str, Any]]:
    """The shipped config sections: every flag off."""
    out: Dict[str, Dict[str, Any]] = {}
    for (section, key), value in FLAGS.items():
        out.setdefault(section, {})[key] = value
    return out


def summary(config: Any) -> Dict[str, Any]:
    """Every flag's effective value, for the launcher check and reports."""
    return {f'{s}.{k}': (mode(config, s, k) if isinstance(v, str) else enabled(config, s, k)) for (s, k), v in FLAGS.items()}
