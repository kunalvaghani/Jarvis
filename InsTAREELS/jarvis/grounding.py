"""Local decisions for explicitly named unique controls; no success inference."""
import re
from .ui_controls import label_key, UNSAFE_INFERRED


def direct_decision(step, goal, matching):
    if len(matching) != 1 or step["action"] not in {"select", "fill_text", "open_menu"}:
        return None
    chosen = matching[0]
    value = label_key(step["value"])
    if (UNSAFE_INFERRED.search(chosen["name"]) or chosen.get("password")
            or value != label_key(chosen["name"]) or not value
            or not re.search(r"(?:^|\s)" + re.escape(value) + r"(?:\s|$)", label_key(goal))):
        return None
    if step["action"] == "fill_text" and (not step.get("content") or step["content"].casefold() not in goal.casefold()):
        return None
    return {"approved": True, "choice": "c0", "reason": "Explicit named target is unique in fresh accessibility state"}
