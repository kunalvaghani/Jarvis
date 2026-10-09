"""Create parent directories for nested application-layout fixtures."""
from pathlib import Path

def fixture_path(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
