"""Reusable base for Jarvis connector implementations."""
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


