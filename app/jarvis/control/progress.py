"""Live progress from the control routes, for the Dynamic Island (UI metadata only, never execution authority).

Every route action reports where it is: observing -> locating -> acting -> verifying -> done, or
refused / failed / blocked. A sink receives ProgressEvent values; the island bridge turns them into
animated cards. A failing sink never affects the action (display is best effort).
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Optional

from .executor import Health, RouteExecutor
from .types import Action, ActionResult, ErrorCategory, Expectation, Observation, Route

PHASES = ('checking', 'observing', 'locating', 'acting', 'verifying', 'waiting_approval', 'done', 'refused', 'failed',
          'blocked')
WORKING = frozenset({'checking', 'observing', 'locating', 'acting', 'verifying'})
# Outcomes that mean "Jarvis stopped safely": nothing happened, or the user must act.
REFUSALS = frozenset({ErrorCategory.TARGET_NOT_FOUND, ErrorCategory.STALE_REF, ErrorCategory.NOT_ACTIONABLE,
                      ErrorCategory.POLICY_DENIED, ErrorCategory.APPROVAL_DENIED, ErrorCategory.CANCELLED,
                      ErrorCategory.INVALID_ARGUMENTS, ErrorCategory.UNSUPPORTED, ErrorCategory.NOT_EXECUTED})
BLOCKERS = frozenset({ErrorCategory.ELEVATED_TARGET, ErrorCategory.SECURE_DESKTOP, ErrorCategory.FOCUS_LOST})
LABELS = {'navigate': 'Opening page', 'read_page': 'Reading the page', 'find': 'Searching the page',
          'form_input': 'Filling a field', 'left_click': 'Clicking', 'click': 'Clicking', 'double_click': 'Double-clicking',
          'right_click': 'Right-clicking', 'type': 'Typing', 'key': 'Pressing keys', 'scroll': 'Scrolling',
          'set_value': 'Entering text', 'launch': 'Opening app', 'read_window': 'Reading the window',
          'locate': 'Finding it on screen', 'screenshot': 'Looking at the screen', 'invoke': 'Pressing',
          'toggle': 'Toggling', 'select': 'Selecting', 'expand': 'Expanding', 'close_window': 'Closing window'}


@dataclass(frozen=True)
class ProgressEvent:
    route: Route
    phase: str
    title: str
    subtitle: str = ''
    detail: str = ''
    step: int = 0       # 1-based step inside a task; 0 when unknown.
    steps: int = 0
    at: float = 0.0


Sink = Callable[[ProgressEvent], None]


def emit(sink: Optional[Sink], event: ProgressEvent) -> None:
    if sink is None:
        return
    try:
        sink(event if event.at else ProgressEvent(event.route, event.phase, event.title, event.subtitle, event.detail,
                                                  event.step, event.steps, time.time()))
    except Exception:
        pass  # Display is best effort; it never changes an action's outcome.


def label(action: Action) -> str:
    name = action.name.split('.', 1)[-1]
    target = action.params.get('target') or action.params.get('label') or action.params.get('url') or action.params.get('app')
    base = LABELS.get(name, name.replace('_', ' ').capitalize())
    return f'{base} "{str(target)[:50]}"' if target else base


def outcome(result: ActionResult) -> str:
    if result.ok:
        return 'done'
    if result.error_category in BLOCKERS:
        return 'blocked'
    return 'refused' if result.error_category in REFUSALS and not result.executed else 'failed'


class Reporting(RouteExecutor):
    """Wraps any route executor and reports each observe/act to a progress sink. Behaviour is unchanged."""

    def __init__(self, inner: RouteExecutor, sink: Optional[Sink], subtitle: str = '') -> None:
        self.inner, self.sink, self.subtitle = inner, sink, subtitle
        self.route = inner.route
        self.step, self.steps = 0, 0
        self.last_act = 0.0

    def plan(self, steps: int) -> None:
        """Announce how many steps the current task expects (drives the determinate step bar)."""
        self.step, self.steps = 0, max(0, int(steps))
        self.last_act = time.monotonic()  # A fresh plan is not a stale task.

    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        emit(self.sink, ProgressEvent(self.route, 'observing', LABELS['read_page' if self.route is Route.BROWSER else
                                                                      'read_window' if self.route is Route.UIA else
                                                                      'screenshot'], self.subtitle))
        return self.inner.observe(scope, **options)

    def act(self, action: Action) -> ActionResult:
        if time.monotonic() - self.last_act > 60:
            self.step, self.steps = 0, 0  # A pause this long starts a new task's count.
        self.last_act = time.monotonic()
        self.step += 1
        steps = max(self.steps, self.step) if self.steps else 0
        title = label(action)
        emit(self.sink, ProgressEvent(self.route, 'acting', title, self.subtitle, '', self.step, steps))
        result = self.inner.act(action)
        state = outcome(result)
        detail = 'Checked: ' + result.evidence[:60] if result.ok and result.verified else result.text[:80]
        emit(self.sink, ProgressEvent(self.route, state, title, self.subtitle, detail, self.step, steps))
        return result

    def probe(self, what: str, **params: Any) -> Any:
        return self.inner.probe(what, **params)

    def verify(self, expectation: Expectation) -> 'tuple[bool, str]':
        emit(self.sink, ProgressEvent(self.route, 'verifying', 'Checking the result', self.subtitle))
        return self.inner.verify(expectation)

    def cancel(self) -> None:
        self.inner.cancel()

    def health_check(self) -> Health:
        return self.inner.health_check()

    def close(self) -> None:
        self.inner.close()
