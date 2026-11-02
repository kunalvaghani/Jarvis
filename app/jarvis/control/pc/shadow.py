"""Shadow mode for the PC backend: legacy UI Automation acts; agent-desktop only observes and resolves targets.

For every legacy window read, agent-desktop snapshots the same window and the log records how many of legacy's
controls it also found and how long its observe took. For every legacy ref action, it records whether
agent-desktop found an element with the same role and name, i.e. the ref it would have acted on.

agent-desktop runs through ``ReadOnlyRunner``, which refuses every command that could change anything, so
shadow mode cannot act even by mistake. The log holds no names or values: only counts, matches and timings.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, Optional, Sequence, Tuple

from ..executor import Health, RouteExecutor
from ..types import Action, ActionResult, ControlError, ErrorCategory, Observation, Route
from .runner import Envelope, Runner

APP = Path(__file__).resolve().parents[3]
LOG = APP / '.jarvis-runtime' / 'logs' / 'control-shadow' / 'pc.jsonl'
READ_COMMANDS = frozenset({'snapshot', 'find', 'get', 'is', 'list-windows', 'list-apps', 'status', 'list-surfaces',
                           'version', 'permissions'})
ROW = re.compile(r'^\s*(\w[\w ]*?) "([^"]*)"(?: [^\[\n]*?)? \[([\w-]+)\]')
MAX_BYTES = 5_000_000
_lock = threading.Lock()


class ReadOnlyRunner(Runner):
    """A runner that can only look. Any command outside READ_COMMANDS is refused before a process starts."""

    def __call__(self, args: Sequence[str], headed: bool = False, timeout_s: float = 30.0) -> Envelope:
        command = str(args[0]) if args else ''
        if headed or command not in READ_COMMANDS:
            raise ControlError(f'shadow mode never acts (refused {command!r})', ErrorCategory.POLICY_DENIED)
        return super().__call__(args, False, timeout_s)


def _write(row: Dict[str, Any], path: Path = LOG) -> None:
    row = {'at': datetime.now(timezone.utc).isoformat(timespec='milliseconds'), **row}
    line = json.dumps(row) + '\n'
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size + len(line) > MAX_BYTES:
            path.replace(path.with_suffix('.jsonl.1'))
        with path.open('a', encoding='utf-8') as out:
            out.write(line)


def controls(text: str) -> Dict[str, Tuple[str, str]]:
    found = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            found[m.group(3)] = (m.group(1), m.group(2))
    return found


class ShadowExecutor(RouteExecutor):
    """Legacy acts; the candidate observes. Every legacy result is returned unchanged."""

    def __init__(self, legacy: RouteExecutor, candidate: Any, log: Path = LOG) -> None:
        self.legacy, self.candidate, self.log = legacy, candidate, log
        self.route = getattr(legacy, 'route', Route.UIA)
        self.last: Dict[str, Dict[str, Tuple[str, str]]] = {}   # scope -> candidate controls (ref -> (kind, name))
        self.legacy_seen: Dict[str, Dict[str, Tuple[str, str]]] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.legacy, name)  # launch/windows/... stay legacy

    def health_check(self) -> Health:
        return self.legacy.health_check()

    def cancel(self) -> None:
        self.legacy.cancel()

    def close(self) -> None:
        self.legacy.close()

    def probe(self, what: str, **params: Any) -> Any:
        return self.legacy.probe(what, **params)

    def _observe_candidate(self, scope: str) -> Optional[float]:
        if not scope.startswith('win-'):
            return None
        started = time.perf_counter()
        try:
            obs = self.candidate.read_window(int(scope[4:]), 'all')
        except Exception as error:
            _write({'event': 'observe_failed', 'scope_kind': 'window', 'error': type(error).__name__,
                    'category': getattr(getattr(error, 'category', None), 'value', '')}, self.log)
            return None
        self.last[scope] = controls(obs.text)
        return (time.perf_counter() - started) * 1000

    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        obs = self.legacy.observe(scope, **options)
        self._compare(obs.scope, obs.text)
        return obs

    def _compare(self, scope: str, legacy_text: str) -> None:
        legacy = controls(legacy_text)
        self.legacy_seen[scope] = legacy
        ms = self._observe_candidate(scope)
        if ms is None:
            return
        mine = {v for v in self.last.get(scope, {}).values()}
        theirs = [v for v in legacy.values() if v[1]]
        matched = sum(v in mine for v in theirs)
        _write({'event': 'observe', 'legacy_controls': len(legacy), 'candidate_controls': len(self.last.get(scope, {})),
                'named_matched': matched, 'named_total': len(theirs), 'candidate_ms': round(ms, 1)}, self.log)

    def act(self, action: Action) -> ActionResult:
        result = self.legacy.act(action)
        try:
            self._shadow_act(action, result)
        except Exception:
            pass  # Shadow must never affect the task.
        return result

    def _shadow_act(self, action: Action, result: ActionResult) -> None:
        if action.name == 'read_window' and result.ok:
            self._compare(str(result.state.get('scope', '')), result.text)
            return
        scope, ref = str(action.params.get('scope', '')), str(action.params.get('ref', ''))
        if not scope or not ref:
            _write({'event': 'act', 'op': action.name, 'targeted': False, 'legacy_ok': result.ok}, self.log)
            return
        target = self.legacy_seen.get(scope, {}).get(ref)
        mine = self.last.get(scope, {})
        found = target is not None and target in mine.values()
        _write({'event': 'act', 'op': action.name, 'targeted': True, 'legacy_ok': result.ok,
                'legacy_verified': result.verified, 'candidate_found_same_target': found,
                'would_run': {'click': 'click', 'invoke': 'click', 'set_value': 'set-value',
                              'toggle': 'toggle'}.get(action.name, action.name)}, self.log)


def summary(path: Path = LOG) -> Dict[str, Any]:
    observes = acts = found = matched = total = 0
    ms = []
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row.get('event') == 'observe':
                observes += 1
                matched += row['named_matched']
                total += row['named_total']
                ms.append(row['candidate_ms'])
            elif row.get('event') == 'act' and row.get('targeted'):
                acts += 1
                found += bool(row.get('candidate_found_same_target'))
    except (OSError, ValueError, KeyError):
        pass
    ms.sort()
    return {'observes': observes, 'named_controls_found': f'{matched}/{total}', 'targeted_acts': acts,
            'same_target_found': f'{found}/{acts}', 'observe_ms_p50': ms[len(ms) // 2] if ms else None}
