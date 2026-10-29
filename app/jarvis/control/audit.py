"""Append-only JSONL audit of every control action.

Typed text, field contents, screenshots and page text never reach disk: free text is stored as
its length and a short SHA-256 prefix. Remaining strings pass through Jarvis's existing secret
redaction. A sink can forward records to the existing observability (agent events).
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Callable, Dict, Mapping, Optional

from .types import Action, ActionResult

SENSITIVE_PARAMS = frozenset({'text', 'content', 'value', 'query', 'password', 'body', 'script', 'code', 'paths'})
Sink = Callable[[Dict[str, Any]], None]


def fingerprint(value: Any) -> Dict[str, Any]:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return {'len': len(text), 'sha256': hashlib.sha256(text.encode('utf-8', 'replace')).hexdigest()[:12]}


def _redact(text: str) -> str:
    from ..tools import redact  # Reuse the existing Jarvis secret scrubber.
    return str(redact(text))


def scrub(params: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in params.items():
        if key.lower() in SENSITIVE_PARAMS:
            out[key] = fingerprint(value)
        elif isinstance(value, str):
            out[key] = _redact(value)[:500]
        elif isinstance(value, (int, float, bool)) or value is None:
            out[key] = value
        else:
            out[key] = fingerprint(value)
    return out


class AuditLog:
    def __init__(self, path: Path, sink: Optional[Sink] = None) -> None:
        self.path = Path(path)
        self.sink = sink
        self._lock = threading.Lock()

    def write(self, event: str, **fields: Any) -> Dict[str, Any]:
        record = {'date': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}
        line = json.dumps(record, ensure_ascii=True, default=str)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(line + '\n')
        if self.sink is not None:
            try:
                self.sink(record)
            except Exception:
                pass  # Observability must never turn a completed action into a failure.
        return record

    def action(self, action: Action, result: ActionResult) -> Dict[str, Any]:
        return self.write(
            'control.action', action_id=action.action_id, task_id=action.task_id, step_id=action.step_id,
            name=action.name, route=result.route.value, risk=int(action.risk), params=scrub(action.params),
            target=(getattr(action.target, 'id', None) or type(action.target).__name__),
            app=action.context.app, window=action.context.window, tab=action.context.tab,
            ok=result.ok, executed=result.executed, verified=result.verified,
            error_category=result.error_category.value, evidence=_redact(result.evidence)[:500],
            timings_ms=dict(result.timings_ms))
