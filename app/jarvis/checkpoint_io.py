"""Commit unchanged Jarvis-owned metadata after known Windows sharing failures."""
import hashlib
from pathlib import Path
import time


def replace_checkpoint(source, target, root, *, wait=time.sleep, report=None):
    """Never repeats an external action or a rename with an uncertain outcome."""
    source, target, root = Path(source), Path(target), Path(root).resolve()
    if not all(path.resolve().is_relative_to(root) for path in (source, target)):
        raise ValueError('Checkpoint rename escaped its owned root.')

    def status(message):
        runtime = next((path for path in (root, *root.parents) if path.name == '.jarvis-runtime'), None)
        if runtime is not None:
            try:
                from .recovery import record
                record(runtime.parent, message)
            except OSError:
                pass  # Optional diagnosis never repeats or invalidates a committed effect.
        if callable(report):
            try:
                report('repair', message)
            except Exception:
                pass

    def signature(path, depth=0, budget=None):
        budget = [0, 0] if budget is None else budget
        if not path.exists():
            return None
        stat = path.stat()
        budget[0] += 1
        if (depth > 32 or budget[0] > 5000 or not path.resolve().is_relative_to(root)
                or path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Unsupported linked, deep or oversized owned checkpoint.')
        if path.is_dir():
            content = tuple((child.name, signature(child, depth + 1, budget)) for child in sorted(path.iterdir()))
        else:
            budget[1] += stat.st_size
            if stat.st_size > 32 * 1024 * 1024 or budget[1] > 64 * 1024 * 1024:
                raise ValueError('Owned checkpoint exceeds metadata budget.')
            content = hashlib.sha256(path.read_bytes()).hexdigest()
        return stat.st_ino, stat.st_size, stat.st_mtime_ns, content

    before_source, before_target = signature(source), signature(target)
    for attempt in range(4):
        if attempt and (signature(source) != before_source or signature(target) != before_target):
            status('Owned checkpoint changed during backoff; automatic commit refused.')
            raise ValueError('Owned checkpoint changed during backoff; inspect pending metadata.')
        try:
            source.replace(target)
            if attempt:
                status('Owned checkpoint commit recovered; no external action replayed.')
            return
        except PermissionError as exc:
            if (getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == 3
                    or before_source is None or signature(source) != before_source
                    or signature(target) != before_target):
                status('Owned checkpoint commit blocked; pending metadata retained for inspection.')
                raise
            if attempt == 0:
                status('Owned checkpoint sharing failure; retrying unchanged metadata only.')
            if wait(.05 * (attempt + 1)):
                status('Owned checkpoint commit stopped; pending metadata retained for inspection.')
                raise InterruptedError('Checkpoint commit stopped; pending owned metadata preserved.')
