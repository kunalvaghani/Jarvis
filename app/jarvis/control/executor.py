"""The interface each of the four routes implements."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .types import Action, ActionResult, Expectation, Observation, Route


@dataclass(frozen=True)
class Health:
    ok: bool
    detail: str = ''
    capabilities: Mapping[str, Any] = field(default_factory=dict)


class RouteExecutor(ABC):
    route: Route

    @abstractmethod
    def observe(self, scope: Optional[str] = None, **options: Any) -> Observation:
        """Read-only snapshot with refs and transform metadata."""

    @abstractmethod
    def act(self, action: Action) -> ActionResult:
        """Dispatch exactly once. Never retries internally after input may have been sent."""

    @abstractmethod
    def probe(self, what: str, **params: Any) -> Any:
        """Read one fresh value for verification (url, value, state, signature, ...)."""

    def verify(self, expectation: Expectation) -> 'tuple[bool, str]':
        from .verify import default_verifier
        return default_verifier.check(expectation, self.probe)

    @abstractmethod
    def cancel(self) -> None:
        """Abort in-flight waits; never sends further input."""

    @abstractmethod
    def health_check(self) -> Health: ...

    @abstractmethod
    def close(self) -> None: ...
