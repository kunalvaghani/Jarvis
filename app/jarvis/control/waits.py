"""Condition waits (flag control.event_waits, default off): end a wait as soon as the app shows the expected
state, never later than the fixed wait it replaces. A probe that raises ControlError counts as "not yet"."""
from __future__ import annotations

import time
from typing import Callable

from ..telemetry.ledger import pause
from .types import ControlError

POLL = .05


def until(done: Callable[[], bool], timeout: float, interval: float = POLL,
          clock: Callable[[], float] = time.perf_counter, sleep: Callable[[float], None] = pause) -> bool:
    """True once done() holds; False when the timeout passes first. Waits at most `timeout` (+ one probe)."""
    deadline = clock() + timeout
    while True:
        try:
            if done():
                return True
        except ControlError:
            pass
        left = deadline - clock()
        if left <= 0:
            return False
        sleep(min(interval, left))
