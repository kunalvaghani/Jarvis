"""Local source hashing through the existing approved-project path resolver."""
from pathlib import Path
import hashlib
from ..contracts import Source


def local_source(root: Path, relative: str, *, license: str | None = None) -> Source:
    from ...agent_context import scoped
    from ...obsidian_memory import SENSITIVE
    path = scoped(Path(root), relative)
    if not path.is_file() or path.is_symlink() or SENSITIVE.search(path.name):
        raise ValueError('source must be a permitted regular nonsecret project file')
    if path.stat().st_size > 64_000_000:
        raise ValueError('source exceeds the local hash byte budget')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        remaining = 64_000_001
        while remaining:
            block = stream.read(min(1_000_000, remaining))
            if not block:
                break
            h.update(block); remaining -= len(block)
        if not remaining:
            raise ValueError('source changed beyond its byte budget')
    return Source(id='source-' + h.hexdigest(), locator=str(path), sha256=h.hexdigest(), license=license)
