"""Shadow mode for the web backend: the legacy Playwright route acts; agent-browser only reads.

After each legacy page read on the *test* profile, agent-browser opens the same public URL in its own isolated,
headless session (no profile, no cookies) and snapshots it. The log records how many of legacy's named controls
it also found, and for each legacy ref action whether it found the same target. Pages read on the user's personal
profile are skipped: a logged-out copy would not match and is not worth a second request.

``ReadOnlyBrowserRunner`` refuses every command except opening and reading pages, so shadow mode cannot click,
type or submit anything. The log holds no URLs, names or values: only counts, matches and timings.
"""
from __future__ import annotations

from pathlib import Path
import re
import time
from typing import Any, Dict, Optional, Sequence, Tuple

from ..executor import Health, RouteExecutor
from ..pc.shadow import _write
from ..types import Action, ActionResult, ControlError, ErrorCategory, Observation, Route
from .agent_browser_backend import AgentBrowserExecutor, BrowserRunner, Reply

APP = Path(__file__).resolve().parents[3]
LOG = APP / '.jarvis-runtime' / 'logs' / 'control-shadow' / 'web.jsonl'
READ_COMMANDS = frozenset({'open', 'snapshot', 'get', 'read', 'close'})
ROW = re.compile(r'^\s*([\w-]+) "([^"]*)"[^\[\n]*\[([\w-]+)\]')


class ReadOnlyBrowserRunner(BrowserRunner):
    def __call__(self, args: Sequence[str], timeout_s: float = 60.0) -> Reply:
        command = str(args[0]) if args else ''
        if command not in READ_COMMANDS or (command == 'get' and len(args) > 1 and args[1] not in ('url', 'title', 'text')):
            raise ControlError(f'web shadow never acts (refused {command!r})', ErrorCategory.POLICY_DENIED)
        return super().__call__(args, timeout_s)


def controls(text: str) -> Dict[str, Tuple[str, str]]:
    out = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            out[m.group(3)] = (m.group(1).lower(), m.group(2))
    return out


class WebShadowExecutor(RouteExecutor):
    def __init__(self, legacy: RouteExecutor, candidate: AgentBrowserExecutor, personal: bool, log: Path = LOG) -> None:
        self.legacy, self.candidate, self.personal, self.log = legacy, candidate, personal, log
        self.route = Route.BROWSER
        self.legacy_seen: Dict[str, Tuple[str, str]] = {}
        self.mine: Dict[str, Tuple[str, str]] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.legacy, name)

    def start(self) -> None:
        getattr(self.legacy, "start", lambda: None)()

    def health_check(self) -> Health:
        return self.legacy.health_check()

    def cancel(self) -> None:
        self.legacy.cancel()

    def close(self) -> None:
        self.legacy.close()
        self.candidate.close()

    def probe(self, what: str, **params: Any) -> Any:
        return self.legacy.probe(what, **params)

    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        return self.legacy.observe(scope, **options)

    def _compare(self, legacy_text: str) -> None:
        self.legacy_seen = controls(legacy_text)
        if self.personal:
            _write({'event': 'observe_skipped', 'reason': 'personal profile'}, self.log)
            return
        try:
            url = str(self.legacy.probe('url'))
        except Exception:
            return
        if not url.startswith(('http:', 'https:')):
            return
        started = time.perf_counter()
        try:
            self.candidate.run(['open', url], 60)
            obs = self.candidate.read_page('all')
        except Exception as error:
            _write({'event': 'observe_failed', 'error': type(error).__name__}, self.log)
            return
        ms = (time.perf_counter() - started) * 1000
        self.mine = controls(obs.text)
        mine = {(r, n.casefold()) for r, n in self.mine.values()}
        named = [(r, n.casefold()) for r, n in self.legacy_seen.values() if n]
        _write({'event': 'observe', 'legacy_controls': len(self.legacy_seen), 'candidate_controls': len(self.mine),
                'named_matched': sum(v in mine for v in named), 'named_total': len(named),
                'candidate_ms': round(ms, 1)}, self.log)

    def act(self, action: Action) -> ActionResult:
        result = self.legacy.act(action)
        try:
            if action.name == 'read_page' and result.ok and not action.params.get('ref'):
                self._compare(result.text)
            elif action.params.get('ref'):
                target = self.legacy_seen.get(str(action.params['ref']))
                mine = {(r, n.casefold()) for r, n in self.mine.values()}
                found = target is not None and (target[0], target[1].casefold()) in mine
                _write({'event': 'act', 'op': action.name, 'legacy_ok': result.ok,
                        'candidate_found_same_target': found, 'personal': self.personal}, self.log)
        except Exception:
            pass  # Shadow must never affect the task.
        return result
