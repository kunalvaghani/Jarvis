"""Per-stage timers for every action (Part IV measurements)."""
from __future__ import annotations

from contextlib import contextmanager
import time
from typing import Callable, Dict, Iterator

STAGES = ('intent', 'inference', 'routing', 'mcp_dispatch', 'capture', 'tree_read', 'grounding', 'input',
          'app_wait', 'verify', 'recovery', 'total')


class StageTimer:
    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self.clock = clock
        self.started = clock()
        self.stages: Dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        if name not in STAGES or name == 'total':
            raise ValueError(f'Unknown timing stage {name!r}.')
        begun = self.clock()
        try:
            yield
        finally:
            # Repeated stages (e.g. two tree reads) accumulate.
            self.stages[name] = self.stages.get(name, 0.0) + (self.clock() - begun) * 1000

    def add(self, name: str, milliseconds: float) -> None:
        if name not in STAGES or name == 'total' or milliseconds < 0:
            raise ValueError(f'Invalid timing {name!r}={milliseconds}.')
        self.stages[name] = self.stages.get(name, 0.0) + milliseconds

    def result(self) -> Dict[str, float]:
        return {**{k: round(v, 3) for k, v in self.stages.items()},
                'total': round((self.clock() - self.started) * 1000, 3)}
