"""Shared, metadata-only contracts for execution outcomes (upgrade phases 2-4).

Outcome rows extend the existing agent lifecycle log (agent_events.py); they are
not a second registry or event bus. Every field is categorical or bounded, so a
row never carries arguments, responses, file contents or credentials. A row
describes what independent verification observed; it never grants approval,
selects a tool or authorizes a retry.
"""
import json
import math
import re
from pathlib import Path

# API/code first -> structured automation (DOM/UIA) -> GUI coordinates last.
METHOD_TIERS = ('api', 'structured', 'gui')
# read_only and idempotent effects may be retried by policy; the others never replay.
IDEMPOTENCY = ('read_only', 'idempotent', 'non_idempotent', 'unknown')
# verified: an independent postcondition matched. observed_change: state changed,
# goal not established. unverified: dispatched, no evidence. failed: refuted.
VERIFICATION = ('verified', 'observed_change', 'unverified', 'failed')
REPLAYABLE = frozenset({'read_only', 'idempotent'})

_ADAPTER = re.compile(r'[a-z][a-z0-9_.-]{0,39}')
_SKILL_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}')
_MAX_LATENCY_MS = 3_600_000
OUTCOME_FIELDS = frozenset({'method_tier', 'adapter', 'idempotency', 'verification', 'latency_ms', 'attempts', 'skill_id'})


def outcome_metadata(metadata):
    """Keep only well-formed outcome fields; malformed values are dropped, not coerced."""
    result = {}
    for name, allowed in (('method_tier', METHOD_TIERS), ('idempotency', IDEMPOTENCY), ('verification', VERIFICATION)):
        value = metadata.get(name)
        if isinstance(value, str) and value in allowed:
            result[name] = value
    adapter = metadata.get('adapter')
    if isinstance(adapter, str) and _ADAPTER.fullmatch(adapter):
        result['adapter'] = adapter
    skill = metadata.get('skill_id')
    if isinstance(skill, str) and _SKILL_ID.fullmatch(skill):
        result['skill_id'] = skill
    latency = metadata.get('latency_ms')
    if type(latency) in {int, float} and math.isfinite(latency) and 0 <= latency <= _MAX_LATENCY_MS:
        result['latency_ms'] = round(float(latency), 3)
    attempts = metadata.get('attempts')
    if type(attempts) is int and 0 <= attempts <= 10:
        result['attempts'] = attempts
    return result


def may_replay(idempotency):
    """Only read-only or declared-idempotent effects are eligible for automatic retry."""
    return idempotency in REPLAYABLE


def record_outcome(actions, tool, call_id, **metadata):
    """Append one outcome row correlated with an existing tool lifecycle call_id."""
    from .agent_events import event
    if not isinstance(call_id, str) or not re.fullmatch(r'[0-9a-f]{32}', call_id):
        raise ValueError('An outcome must correlate with an existing tool call_id.')
    if metadata.get('verification') not in VERIFICATION or metadata.get('method_tier') not in METHOD_TIERS:
        raise ValueError('An outcome needs a known method tier and verification state.')
    return event(actions, 'tool.outcome', tool, call_id, **metadata)


def read_outcomes(base, limit=500, max_bytes=2_000_000):
    """Bounded tail of verified-outcome rows for ranking/telemetry consumers.

    Malformed or foreign lines are skipped; a consumer must never trust a row
    beyond its categorical fields.
    """
    path = Path(base) / '.jarvis-runtime' / 'agent-events.jsonl'
    if type(limit) is not int or not 1 <= limit <= 5000:
        raise ValueError('Outcome reads are bounded to 1-5000 rows.')
    if not path.is_file() or path.is_symlink():
        return []
    with path.open('rb') as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes))
        data = handle.read().decode('utf-8', errors='replace')
    rows = []
    for line in data.splitlines()[-limit * 4:]:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get('event') == 'tool.outcome' and row.get('version') == 1:
            rows.append(row)
    return rows[-limit:]
