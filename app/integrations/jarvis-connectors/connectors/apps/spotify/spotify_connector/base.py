"""Compatibility names bound to Jarvis's single production connector contract."""
from dataclasses import dataclass
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from jarvis_connector import BaseConnector, ToolError
ConnectorError = ToolError
class UnsupportedAction(ToolError):
    """The selected Spotify mode cannot safely perform this action."""
@dataclass(frozen=True)
class ConnectorInfo:
    name: str
    version: str
    namespace: str
    capabilities: tuple[str, ...]
