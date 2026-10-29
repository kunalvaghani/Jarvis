"""Sequential batch runner (doc section 2.3 item 5, prompt section 8)."""
from __future__ import annotations

from typing import Callable, List, Sequence

from .policy import ApprovalGate
from .types import Action, ActionResult, ControlError, ErrorCategory, Risk

HALT_TEXT = 'Not executed: an earlier action in this turn failed.'


def _skipped(action: Action, text: str = HALT_TEXT) -> ActionResult:
    return ActionResult(action.action_id, False, action.route, text=text, error_category=ErrorCategory.NOT_EXECUTED)


def run_batch(actions: Sequence[Action], execute: Callable[[Action], ActionResult],
              gate: ApprovalGate) -> List[ActionResult]:
    """Run in order, stop at the first failure, answer every later action with HALT_TEXT.

    Approval is asked immediately before each consequential action, never once per batch, and a
    consequential action never runs past an earlier action that succeeded without verification.
    """
    results: List[ActionResult] = []
    halted = False
    for action in actions:
        if halted:
            results.append(_skipped(action))
            continue
        try:
            action.cancel.raise_if_cancelled()
            if action.risk is Risk.CONSEQUENTIAL and any(r.executed and not r.verified for r in results):
                raise ControlError('An earlier step in this batch is unverified; the consequential step was '
                                   'not run.', ErrorCategory.VERIFICATION_FAILED)
            gate.require(action)
            result = execute(action)
        except ControlError as error:
            result = ActionResult.failure(action, error)
        except Exception as error:  # An executor bug is uncertain, not a clean failure.
            result = ActionResult(action.action_id, False, action.route, text=f'{type(error).__name__}: {error}',
                                  executed=True, error_category=ErrorCategory.UNCERTAIN)
        results.append(result)
        halted = not result.ok
    return results
