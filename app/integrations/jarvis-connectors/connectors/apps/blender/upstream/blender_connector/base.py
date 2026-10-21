"""Reusable base for Jarvis connector implementations."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class ConnectorError(RuntimeError):
    """A connector operation failed; never represent it as successful."""


class UnsupportedAction(ConnectorError):
    """The selected application cannot safely perform the requested action."""


@dataclass(frozen=True)
class ConnectorInfo:
    name: str
    version: str
    namespace: str
    capabilities: tuple[str, ...]


class BaseConnector(ABC):
    """Minimal parent interface; replace/adapt to your existing Jarvis base."""

    @property
    @abstractmethod
    def info(self) -> ConnectorInfo:
        raise NotImplementedError

    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        raise NotImplementedError

    def require_text(self, value: str, label: str, limit: int = 200) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ConnectorError(f"{label} must be a nonempty string")
        value = value.strip()
        if len(value) > limit:
            raise ConnectorError(f"{label} too long (maximum {limit} characters)")
        return value
