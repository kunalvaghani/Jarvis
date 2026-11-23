"""Optional actor context for guards; never an authorization or output-path fallback."""
import os


def optional_actor_base(actor):
    """Return a real filesystem base when supplied by an Actions-compatible caller.

    Older scoped coding callers supply only their mandatory project path. Missing
    or non-path optional actor metadata must not break that API. The campaign
    guard still checks the actual project; valid explicit runtime paths are also
    checked. No path is invented and no writer receives a fallback directory.
    """
    value=getattr(actor,'base',None)
    try:path=os.fspath(value)
    except TypeError:return None
    return path if isinstance(path,str) and path.strip() else None
