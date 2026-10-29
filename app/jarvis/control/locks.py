"""Tab/window locks, exclusive real-desktop input ownership and the emergency stop."""
from __future__ import annotations

from contextlib import contextmanager
import threading
import time
from typing import Callable, ContextManager, Dict, Iterator, List, Optional, Tuple

from .types import CancelToken, ControlError, ErrorCategory

FOREGROUND = ('input', 'foreground')


class LockManager:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._cv = threading.Condition()
        self._owners: Dict[Tuple[str, str], str] = {}
        self._tokens: List[CancelToken] = []
        self.stopped = False
        self.stop_reason = ''

    # Emergency stop -----------------------------------------------------
    def emergency_stop(self, reason: str = 'stop requested by the user') -> int:
        """Cancel every running action and refuse new ones until reset()."""
        with self._cv:
            self.stopped, self.stop_reason = True, reason
            tokens, self._tokens = self._tokens, []
            self._cv.notify_all()
        for token in tokens:
            token.cancel(reason)
        return len(tokens)

    def reset(self) -> None:
        with self._cv:
            self.stopped, self.stop_reason = False, ''

    def track(self, token: CancelToken) -> CancelToken:
        with self._cv:
            if self.stopped:
                token.cancel(self.stop_reason)
            else:
                self._tokens = [t for t in self._tokens if not t.cancelled] + [token]
        return token

    # Locks --------------------------------------------------------------
    def acquire(self, kind: str, key: str, owner: str, timeout_s: float = 5.0,
                cancel: Optional[CancelToken] = None) -> None:
        deadline = self.clock() + timeout_s
        name = (kind, key)
        with self._cv:
            while True:
                if self.stopped:
                    raise ControlError('Emergency stop is active: ' + self.stop_reason, ErrorCategory.CANCELLED)
                if cancel is not None and cancel.cancelled:
                    raise ControlError('Cancelled while waiting for ' + kind, ErrorCategory.CANCELLED)
                holder = self._owners.get(name)
                if holder is None or holder == owner:
                    self._owners[name] = owner
                    return
                remaining = deadline - self.clock()
                if remaining <= 0:
                    raise ControlError(f'{kind} {key} is busy with task {holder}.', ErrorCategory.TIMEOUT)
                self._cv.wait(min(remaining, .05))

    def release(self, kind: str, key: str, owner: str) -> None:
        with self._cv:
            if self._owners.get((kind, key)) == owner:
                del self._owners[(kind, key)]
                self._cv.notify_all()

    def owner(self, kind: str, key: str) -> Optional[str]:
        with self._cv:
            return self._owners.get((kind, key))

    @contextmanager
    def hold(self, kind: str, key: str, owner: str, timeout_s: float = 5.0,
             cancel: Optional[CancelToken] = None) -> Iterator[None]:
        self.acquire(kind, key, owner, timeout_s, cancel)
        try:
            yield
        finally:
            self.release(kind, key, owner)

    def foreground_input(self, owner: str, timeout_s: float = 5.0,
                         cancel: Optional[CancelToken] = None) -> ContextManager[None]:
        """Real mouse/keyboard on the user's desktop: one owner at a time."""
        return self.hold(*FOREGROUND, owner, timeout_s, cancel)
