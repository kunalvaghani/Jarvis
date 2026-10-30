"""Shadow-decision log (flag telemetry.shadow_log, default off).

A new decider in shadow mode proposes, the existing path decides, and this log keeps both so the user can see
how often they agree before approving the next mode. Recording never changes the decision that was taken and
never raises. Text is passed through the trace redactor; each decider's file is size-bounded with one rotation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any, Dict, Optional

from .. import flags

APP = Path(__file__).resolve().parents[2]
MAX_BYTES = 5_000_000
MAX_FIELD = 2000
NAME = re.compile(r'^[a-z][a-z0-9_]{0,39}$')
_lock = threading.Lock()


def path(decider: str, base: Optional[Path] = None) -> Path:
    if not NAME.match(decider):
        raise ValueError(f'Invalid decider name {decider!r}')
    return (Path(base) if base is not None else APP) / '.jarvis-runtime' / 'logs' / 'shadow' / f'{decider}.jsonl'


def _text(value: Any) -> str:
    try:
        text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        text = str(value)
    from ..tools import redact
    return str(redact(text))[:MAX_FIELD]


def record(config: Any, decider: str, proposed: Any, actual: Any, task_id: Optional[str] = None,
           latency_ms: Optional[float] = None, base: Optional[Path] = None) -> bool:
    """Log one shadow proposal next to the real decision. Returns whether a row was written."""
    if not flags.enabled(config, 'telemetry', 'shadow_log'):
        return False
    try:
        target = path(decider, base)
        proposed_text, actual_text = _text(proposed), _text(actual)
        row = {'at': datetime.now(timezone.utc).isoformat(timespec='milliseconds'), 'task': task_id,
               'proposed': proposed_text, 'actual': actual_text, 'agree': proposed_text == actual_text,
               'latency_ms': None if latency_ms is None else round(float(latency_ms), 2)}
        line = json.dumps(row) + '\n'
        with _lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size + len(line) > MAX_BYTES:
                target.replace(target.with_suffix('.jsonl.1'))
            with target.open('a', encoding='utf-8') as out:
                out.write(line)
        return True
    except Exception:
        return False  # Shadow mode must never affect the task.


def agreement(decider: str, base: Optional[Path] = None) -> Dict[str, Any]:
    """How often the shadow proposal matched the real decision (current file only)."""
    total = agreed = 0
    try:
        with path(decider, base).open(encoding='utf-8') as rows:
            for line in rows:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                total += 1
                agreed += row.get('agree') is True
    except OSError:
        pass
    return {'decider': decider, 'total': total, 'agreed': agreed, 'rate': round(agreed / total, 4) if total else None}
