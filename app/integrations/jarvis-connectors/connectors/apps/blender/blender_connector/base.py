from dataclasses import dataclass
class ConnectorError(Exception): pass
@dataclass(frozen=True)
class ConnectorInfo:
    name: str
    version: str
    namespace: str
    capabilities: tuple
