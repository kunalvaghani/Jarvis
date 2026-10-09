"""Validated UIA operations shared by direct commands and planned steps."""
import re
SHORTCUTS = {
    "tab": "{TAB}", "shift+tab": "+{TAB}", "escape": "{ESC}", "esc": "{ESC}",
    "ctrl+a": "^a", "ctrl+f": "^f", "ctrl+l": "^l", "ctrl+s": "^s",
    "ctrl+shift+s": "^+s", "ctrl+c": "^c", "ctrl+v": "^v", "ctrl+z": "^z",
    "ctrl+y": "^y", "alt+left": "%{LEFT}", "alt+right": "%{RIGHT}",
    "alt+f": "%f", "alt+e": "%e", "up": "{UP}", "down": "{DOWN}",
    "left": "{LEFT}", "right": "{RIGHT}", "home": "{HOME}", "end": "{END}",
    "pageup": "{PGUP}", "pagedown": "{PGDN}", "f5": "{F5}",
}
CONTROL_ACTIONS = {"select", "fill_text", "open_menu", "handle_dialog"}


def shortcut_key(value):
    key = value.strip().casefold().replace("control", "ctrl").replace(" plus ", "+")
    key = re.sub(r"\b(ctrl|alt|shift)\s+", r"\1+", key).replace(" ", "")
    if key not in SHORTCUTS:
        raise ValueError("Unsupported shortcut. Use a named visible button for dialog confirmation or submission.")
    return key


def validate_desktop_step(step):
    action = step["action"]
    if action == "fill_text" and (not isinstance(step.get("content"), str) or len(step["content"]) > 10000):
        raise ValueError("Text field entry requires exact text up to 10,000 characters.")
    if action == "shortcut":
        shortcut_key(step["value"])
    if action == "scroll" and step["value"].casefold() not in {"up", "down", "left", "right"}:
        raise ValueError("Scroll direction must be up, down, left or right.")


def explicit_desktop_plan(goal):
    text = goal.strip()
    if re.search(r"\s+(?:and(?: then)?|then)\s+(?:open|click|select|press|scroll|fill|choose|save)\b", text, re.I):
        return None  # Keep compound workflows for the planner; don't type their remaining steps.
    match = re.fullmatch(r"fill (?:the )?(.+?)(?: text)? field with (.+)", text, re.I)
    if match:
        return {"steps": [{"action": "fill_text", "value": match[1], "content": match[2], "expected": "Requested text is present in the field"}]}
    text = text.rstrip(".!?")
    match = re.fullmatch(r"scroll (up|down|left|right)(?: one page)?", text, re.I)
    if match:
        return {"steps": [{"action": "scroll", "value": match[1].lower(), "expected": "The visible page has scrolled " + match[1].lower()}]}
    match = re.fullmatch(r"(?:press|use shortcut) (.+)", text, re.I)
    if match:
        return {"steps": [{"action": "shortcut", "value": shortcut_key(match[1]), "expected": "The requested shortcut took effect"}]}
    match = re.fullmatch(r"open (?:the )?(.+?) (?:menu|dropdown)", text, re.I)
    if match:
        return {"steps": [{"action": "open_menu", "value": match[1], "expected": "Menu options are visible"}]}
    match = re.fullmatch(r"(?:choose|click|select) (?:the )?(.+?) (?:in|on) (?:the )?dialog", text, re.I)
    if match:
        return {"steps": [{"action": "handle_dialog", "value": match[1], "expected": "The dialog choice took effect"}]}
    match = re.fullmatch(r'(?:click|select|choose) (?:the )?(.+)', text, re.I)
    if match:
        return {'steps': [{'action': 'select', 'value': match[1], 'expected': 'The requested visible control activated'}]}
    return None


def apply_control(element, control, operation, content=""):
    """Call exactly one supported pattern; failures are never retried as clicks."""
    if operation == "fill_text":
        if control["role"] != "Edit" or control.get("password"):
            raise ValueError("Choose a named non-password text field.")
        interface = element.iface_value
        if interface.CurrentIsReadOnly:
            raise ValueError("The selected text field is read-only.")
        if len(content) > 10000:
            raise ValueError("Text entry is too long.")
        interface.SetValue(content)
        if interface.CurrentValue != content:
            raise ValueError("Text entry was attempted, but the field value could not be verified. Check the field before repeating it.")
        return "Filled " + control["name"] + "; exact field value verified"
    if operation == "scroll":
        interface = element.iface_scroll
        # UIA ScrollAmount: LargeDecrement=0, SmallDecrement=1,
        # NoAmount=2, LargeIncrement=3, SmallIncrement=4.
        horizontal, vertical = {"up": (2, 0), "down": (2, 3), "left": (0, 2), "right": (3, 2)}[content]
        interface.Scroll(horizontal, vertical)
        return "Scrolled " + content
    if operation == "open_menu":
        try:
            interface = element.iface_expand_collapse
        except Exception as exc:
            from pywinauto.uia_defines import NoPatternInterfaceError
            if not isinstance(exc, NoPatternInterfaceError):
                raise
            interface = element.iface_invoke
            interface.Invoke()
        else:
            interface.Expand()
        return "Opened menu " + control["name"]
    raise ValueError("Unsupported desktop operation.")
