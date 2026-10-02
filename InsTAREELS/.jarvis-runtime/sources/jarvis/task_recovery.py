"""Explicit task failures; uncertain external effects must never be retried."""
from .names import common


class TaskFailure(ValueError):
    def __init__(self, reason, attempted=False):
        super().__init__(reason)
        self.attempted = attempted


def action_key(step):
    action = step.get("action", "")
    from .toolkits import TOOLS
    if action in TOOLS:
        folder = step.get("folder", "") if TOOLS[action][0] in {"files", "resource", "knowledge", "agent"} else ""
        return (action, str(step.get("value", "")), "", str(folder), str(step.get("content", "")), "", "")
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
