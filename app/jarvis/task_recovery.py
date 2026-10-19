"""Explicit task failures; uncertain external effects must never be retried."""
from .names import common
import time

# Read-retry backoff: a bounded evolution surface (jarvis/evolution_surfaces.py). The 1-5 attempt
# budget and the read-only requirement are policy and are not part of the surface.
BACKOFF = {'base_seconds': 0.1, 'max_seconds': 1.0}


def retry_read(operation, *, read_only, cancelled=lambda:False, attempts=5, wait=None):
    """Only explicitly admitted observations/inference may be retried, max five."""
    if read_only is not True or type(attempts) is not int or not 1<=attempts<=5:
        raise ValueError('Retries require a read-only operation and a 1–5 attempt budget.')
    for number in range(attempts):
        if cancelled():raise InterruptedError('Read retry cancelled.')
        try:return operation()
        except (OSError,TimeoutError):
            if number+1==attempts:raise
            delay=min(BACKOFF['base_seconds']*2**number,BACKOFF['max_seconds'])
            if wait:wait(delay)
            else:
                deadline=time.monotonic()+delay
                while time.monotonic()<deadline:
                    if cancelled():raise InterruptedError('Read retry cancelled during backoff.')
                    time.sleep(min(.025,max(0,deadline-time.monotonic())))


class TaskFailure(ValueError):
    def __init__(self, reason, attempted=False):
        super().__init__(reason)
        self.attempted = attempted


def action_key(step):
    action = step.get("action", "")
    from .toolkits import TOOLS
    if action in TOOLS:
        folder = step.get("folder", "") if TOOLS[action][0] in {"files", "resource", "knowledge", "agent"} else ""
        # file_tool's read branch does not consume content. A dummy read field
        # cannot turn a completed/failed read into a different action.
        content = '' if action == 'read_file' else str(step.get('content', ''))
        return (action, str(step.get("value", "")), "", str(folder), content, "", "")
    # Ignore fields that dispatch does not use; changing dummy fields is no new approach.
    browser = step.get("browser", "chrome") if action in {"browse", "browser_search"} else ""
    if action == "media_search" and step.get("platform") != "spotify":
        browser = step.get("browser", "chrome")
    folder = step.get("folder", "") if action in {"create_file", "modify_file", "delete_file"} else ""
    content = step.get("content", "") if action in {"create_file", "modify_file", "fill_text"} else ""
    find = step.get("find", "") if action == "modify_file" else ""
    platform = step.get("platform", "") if action in {"media_search", "media_control"} else ""
    return (common(action), common(str(step.get("value", ""))), common(browser),
            common(folder), content, find, common(platform))
