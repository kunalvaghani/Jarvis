"""Recovery controller: bounded, loop-aware, never blindly repeats uncertain input (prompt section 8)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Hashable, Optional

from .types import Action, ActionResult, ErrorCategory, Risk


class Decision(str, Enum):
    DONE = 'done'
    REOBSERVE = 'reobserve'          # read fresh state, then retry the same route
    REFRESH_REFS = 'refresh_refs'    # re-read the tree/page, re-resolve the target
    RETRY = 'retry'                  # same action, same route, fresh target
    SWITCH_ROUTE = 'switch_route'
    ESCALATE_MODEL = 'escalate_model'
    ASK_USER = 'ask_user'
    STOP = 'stop'


@dataclass(frozen=True)
class Plan:
    decision: Decision
    reason: str


TERMINAL = {
    ErrorCategory.CANCELLED: (Decision.STOP, 'The action was cancelled.'),
    ErrorCategory.APPROVAL_DENIED: (Decision.STOP, 'Permission was not granted.'),
    ErrorCategory.POLICY_DENIED: (Decision.STOP, 'Policy blocked the action.'),
    ErrorCategory.INVALID_ARGUMENTS: (Decision.STOP, 'The action is malformed.'),
    ErrorCategory.NOT_EXECUTED: (Decision.STOP, 'An earlier action failed.'),
    ErrorCategory.ELEVATED_TARGET: (Decision.ASK_USER, 'The target runs as administrator; the user must act.'),
    ErrorCategory.SECURE_DESKTOP: (Decision.ASK_USER, 'A secure-desktop prompt needs the user.'),
}
LOCAL_RETRY = {ErrorCategory.STALE_REF, ErrorCategory.TARGET_NOT_FOUND, ErrorCategory.NOT_ACTIONABLE,
               ErrorCategory.FOCUS_LOST, ErrorCategory.TIMEOUT}


class LoopDetector:
    """The same action against the same observed state, again and again, is a loop."""

    def __init__(self, limit: int = 2) -> None:
        self.limit = limit
        self.seen: Counter[Hashable] = Counter()

    def record(self, signature: Hashable) -> bool:
        self.seen[signature] += 1
        return self.seen[signature] > self.limit


class RecoveryController:
    def __init__(self, max_attempts: int = 3, loop_limit: int = 2) -> None:
        self.max_attempts = max_attempts
        self.loops = LoopDetector(loop_limit)
        self.escalated = False

    def decide(self, action: Action, result: ActionResult, attempt: int, *,
               already_happened: Optional[bool] = None, alternatives: bool = False,
               state_signature: Hashable = None) -> Plan:
        """Recovery order: classify, check whether it already happened, re-observe, refresh refs,
        bounded retry, switch route, escalate model reasoning, ask the user."""
        if result.ok and (result.verified or action.expectation is None):
            return Plan(Decision.DONE, 'Verified.' if result.verified else 'Completed; no post-condition declared.')
        if state_signature is not None and self.loops.record((action.name, str(action.target), state_signature)):
            return Plan(Decision.STOP, 'Loop detected: the same action keeps meeting the same state.')
        category = result.error_category
        if category in TERMINAL:
            decision, reason = TERMINAL[category]
            return Plan(decision, reason)
        if result.executed or category in (ErrorCategory.UNCERTAIN, ErrorCategory.VERIFICATION_FAILED):
            # Input may have reached the target. Never repeat it without evidence it did not happen.
            if already_happened:
                return Plan(Decision.DONE, 'Fresh state shows the action already took effect.')
            if action.risk is Risk.CONSEQUENTIAL:
                return Plan(Decision.ASK_USER, 'A consequential action has an uncertain outcome; not repeating it.')
            if already_happened is None and not action.idempotent:
                return Plan(Decision.ASK_USER, 'Outcome is uncertain and the action is not safe to repeat.')
            if attempt >= min(self.max_attempts, action.max_retries + 1):
                return self._escalate(alternatives, 'Retries exhausted after verified non-effect.')
            return Plan(Decision.REOBSERVE, 'Verified not applied; re-observe and retry once.')
        if attempt >= self.max_attempts:
            return self._escalate(alternatives, 'Retries exhausted on this route.')
        if category is ErrorCategory.STALE_REF:
            return Plan(Decision.REFRESH_REFS, 'Reference went stale; re-read and re-resolve the target.')
        if category in LOCAL_RETRY:
            return Plan(Decision.REOBSERVE, f'{category.value}: re-observe before a bounded retry.')
        return self._escalate(alternatives, f'{category.value}: this route cannot do it.')

    def _escalate(self, alternatives: bool, reason: str) -> Plan:
        if alternatives:
            return Plan(Decision.SWITCH_ROUTE, reason + ' Trying the next route.')
        if not self.escalated:
            self.escalated = True
            return Plan(Decision.ESCALATE_MODEL, reason + ' Asking a stronger planner once.')
        return Plan(Decision.ASK_USER, reason + ' No route left.')
