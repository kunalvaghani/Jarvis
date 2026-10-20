"""Reusable least-privilege helpers for connectors.

These checks restrict ordinary tool calls; they do not turn the connector
process into a security sandbox. Run connectors with the narrowest folder and
OS access the task needs.
"""
from pathlib import Path

from .base import ToolError


class ConfinedRoot:
    """One approved directory. Only plain files with an allowed suffix, directly inside it, are reachable.

    No subdirectories, no symlinks/junctions, no absolute paths or drive letters,
    and a per-file size cap. Children subclass or instantiate this instead of
    touching the filesystem directly.
    """

    def __init__(self, root, suffixes, max_bytes=64 * 1024):
        if not root:
            raise ToolError('No approved directory is configured.')
        path = Path(root)
        if not path.is_absolute():
            raise ToolError('The approved directory must be an absolute path.')
        if _linked(path):
            raise ToolError('The approved directory must not be a symlink or junction.')
        try:
            self.root = path.resolve(strict=True)
        except OSError as exc:
            raise ToolError('The approved directory does not exist.') from exc
        if not self.root.is_dir():
            raise ToolError('The approved path is not a directory.')
        self.suffixes = {s.lower() for s in suffixes}
        self.max_bytes = max_bytes

    def _candidate(self, filename):
        if (not isinstance(filename, str) or not filename or filename in {'.', '..'}
                or any(c in filename for c in '\\/:\0') or Path(filename).name != filename
                or Path(filename).suffix.lower() not in self.suffixes):
            raise ToolError('Provide a single file name ending in ' + ', '.join(sorted(self.suffixes))
                            + ' (no folders or drive letters).')
        return self.root / filename

    def path_for_new(self, filename):
        """Validated path for a file that must not exist yet (write tools never overwrite through this)."""
        candidate = self._candidate(filename)
        if candidate.exists() or _linked(candidate):
            raise ToolError(filename + ' already exists.')
        return candidate

    def path(self, filename):
        """Resolve one existing approved file by bare name, or raise :class:`ToolError`."""
        candidate = self._candidate(filename)
        if _linked(candidate):
            raise ToolError('Linked files are not allowed.')
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ToolError('File not found: ' + filename) from exc
        if resolved.parent != self.root or not resolved.is_file():
            raise ToolError('That file is outside the approved directory.')
        if resolved.stat().st_size > self.max_bytes:
            raise ToolError('File exceeds the ' + str(self.max_bytes) + '-byte limit.')
        return resolved

    def files(self):
        """Approved file names, case-insensitively sorted; oversized and linked files are skipped."""
        names = []
        for entry in self.root.iterdir():
            if (entry.suffix.lower() in self.suffixes and not _linked(entry) and entry.is_file()
                    and entry.stat().st_size <= self.max_bytes):
                names.append(entry.name)
        return sorted(names, key=str.casefold)

    def read_text(self, filename):
        try:
            return self.path(filename).read_text(encoding='utf-8')
        except UnicodeDecodeError as exc:
            raise ToolError(filename + ' is not UTF-8 text.') from exc


def _linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())
