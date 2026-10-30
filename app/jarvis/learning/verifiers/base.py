"""Verifier contract: a skill's outcome is judged from the state it left, not from what Jarvis said.

Each verifier declares what it reads. One that reads only the answer or a tool message is "weak": a skill
checked that way could pass by printing "success". An AI-judge verdict is always low confidence and marks the
skill for re-verification on its next run. A verifier that cannot look (missing app, unreadable file) returns
UNVERIFIABLE, which never counts as a pass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, FrozenSet, Tuple

PASSED, FAILED, UNVERIFIABLE = 'passed', 'failed', 'unverifiable'
PROGRAMMATIC, AI_JUDGE = 'programmatic', 'ai_judge'
STATE_READS: FrozenSet[str] = frozenset({'file', 'process', 'window', 'page'})
MESSAGE_READS: FrozenSet[str] = frozenset({'answer', 'message'})


@dataclass(frozen=True)
class Verdict:
    status: str
    problems: Tuple[str, ...] = ()
    evidence: Dict[str, Any] = field(default_factory=dict)
    kind: str = PROGRAMMATIC
    confidence: str = 'high'
    reverify: bool = False

    def __post_init__(self) -> None:
        if self.status not in (PASSED, FAILED, UNVERIFIABLE):
            raise ValueError(f'Unknown verdict status {self.status!r}')
        if self.kind not in (PROGRAMMATIC, AI_JUDGE):
            raise ValueError(f'Unknown verdict kind {self.kind!r}')
        if self.kind == AI_JUDGE:  # A model's opinion is never high confidence.
            object.__setattr__(self, 'confidence', 'low')
            object.__setattr__(self, 'reverify', True)
        if self.status == PASSED and self.problems:
            raise ValueError('A passed verdict cannot list problems')

    @property
    def passed(self) -> bool:
        return self.status == PASSED


def judged(problems: Any, evidence: Dict[str, Any]) -> Verdict:
    items = tuple(str(p) for p in problems)
    return Verdict(FAILED if items else PASSED, items, evidence)


def unverifiable(reason: str, evidence: Dict[str, Any] | None = None) -> Verdict:
    return Verdict(UNVERIFIABLE, (reason,), evidence or {})


class Verifier:
    NAME: ClassVar[str] = ''
    READS: ClassVar[FrozenSet[str]] = frozenset()

    def check(self, *args: Any, **params: Any) -> Verdict:  # Subclasses take keyword parameters.
        raise NotImplementedError


def weak(verifier: type[Verifier] | Verifier) -> bool:
    """True when the verifier never looks at real state (it could be satisfied by a "success" message)."""
    reads = frozenset(getattr(verifier, 'READS', frozenset()))
    return not (reads & STATE_READS)
