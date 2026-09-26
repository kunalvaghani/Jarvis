"""Isolated UIA provider calls; never use guessed screen coordinates."""
import hashlib
import json
import sys
from pathlib import Path

ROLES = {"Button", "SplitButton", "Hyperlink", "MenuItem", "TabItem", "ListItem",
         "TreeItem", "RadioButton", "CheckBox", "ComboBox", "Edit", "Document", "Pane"}


def collect(window):
    controls, wrappers = [], {}
    for element in window.descendants():
        try:
            info = element.element_info
            if info.control_type not in ROLES or not element.is_visible() or not element.is_enabled():
                continue
            name = element.window_text().strip()
            if not name and info.control_type == "Edit":
                name = str(getattr(info, "automation_id", "") or "").strip()
            if not name:
                continue
            if info.control_type in {"Pane", "Document"}:
                try:
                    element.iface_scroll
                except Exception:
                    continue
            identity = list(info.runtime_id)
            rect = element.rectangle()
            item = {"name": name, "role": info.control_type, "id": identity,
                    "rect": [rect.left, rect.top, rect.right, rect.bottom]}
            if info.control_type == "Edit":
                item["password"] = bool(getattr(info, "is_password", False))
            try:
                parent = element.parent()
                if parent:
                    parent_name = parent.window_text().strip()
                    if parent_name and parent_name != name:
                        item["context"] = parent_name[:150]
            except Exception:
                pass
            controls.append(item)
            wrappers[tuple(identity)] = element
        except Exception:
            continue
    signature = hashlib.sha256(json.dumps(controls, sort_keys=True).encode()).hexdigest()
    return controls, wrappers, signature


def perform(request):
    # COM initialization is owned by this short-lived process, never the audio thread.
    from pywinauto import Desktop
    from pywinauto.uia_defines import NoPatternInterfaceError
    import win32gui
    import win32process
    hwnd = request["handle"]
    if not win32gui.IsWindow(hwnd):
        raise ValueError("The destination window was closed.")
    if win32process.GetWindowThreadProcessId(hwnd)[1] == request["owner_pid"]:
        raise ValueError("Switch to the destination app before selecting its controls.")
    if request["operation"] == "folder":
        import pythoncom
        import win32com.client
        import win32api
        process = win32api.OpenProcess(0x0410, False, win32process.GetWindowThreadProcessId(hwnd)[1])
        try:
            if not win32process.GetModuleFileNameEx(process, 0).casefold().endswith("\\explorer.exe"):
                raise ValueError("Select a File Explorer folder first, or name the folder.")
        finally:
            process.Close()
        pythoncom.CoInitialize()
        try:
            for shell_window in win32com.client.Dispatch("Shell.Application").Windows():
                if int(shell_window.HWND) == hwnd:
                    path = shell_window.Document.Folder.Self.Path
                    if Path(path).is_dir():
                        return {"folder": path}
        finally:
            pythoncom.CoUninitialize()
        raise ValueError("This File Explorer window does not show a normal filesystem folder.")
    window = Desktop(backend="uia").window(handle=hwnd).wrapper_object()
    if request["operation"] in {"activate", "fill_text", "scroll", "shortcut", "open_menu"}:
        current = win32gui.GetForegroundWindow()
        current_pid = win32process.GetWindowThreadProcessId(current)[1] if current else 0
        if current not in (hwnd,) and current_pid != request["owner_pid"]:
            raise ValueError("Focus changed to another app; selection cancelled.")
        window.set_focus()
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError("The target app did not take focus.")
    controls, wrappers, signature = collect(window)
    if request["operation"] in {"shortcut", "scroll"}:
        from .desktop_actions import SHORTCUTS, shortcut_key, apply_control
        if request.get("signature") != signature:
            raise ValueError("The destination controls changed; action cancelled.")
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError("Focus changed before desktop action.")
        if request["operation"] == "shortcut":
            key = shortcut_key(request["value"])
            window.type_keys(SHORTCUTS[key], set_foreground=False, pause=.02)
            return {"message": "Pressed " + key}
        # Resolve the scroll pattern before calling it, never retry after Scroll.
        targets = [window] + [wrappers[tuple(c["id"])] for c in controls if c["role"] in {"Pane", "Document", "ListItem"}]
        for target in targets:
            try:
                interface = target.iface_scroll
            except NoPatternInterfaceError:
                continue
            direction = request["value"].casefold()
            if direction in {"up", "down"} and not interface.CurrentVerticallyScrollable:
                continue
            if direction in {"left", "right"} and not interface.CurrentHorizontallyScrollable:
                continue
            return {"message": apply_control(target, {"name": "window", "role": "Pane"}, "scroll", request["value"].casefold())}
        raise ValueError("This window has no accessible scroll container.")
    if request["operation"] == "list":
        import win32api
        context = None
        try:
            process = win32api.OpenProcess(0x0410, False, win32process.GetWindowThreadProcessId(hwnd)[1])
            try:
                executable = win32process.GetModuleFileNameEx(process, 0)
            finally:
                process.Close()
            context = json.dumps([executable.casefold(), window.window_text().casefold()])
        except Exception:
            pass  # A protected process can still expose usable UI controls.
        modal = window.class_name() == "#32770"
        try:
            modal = modal or bool(window.iface_window.CurrentIsModal)
        except NoPatternInterfaceError:
            pass
        return {"controls": controls, "signature": signature, "context": context, "is_dialog": modal,
                "title": window.window_text()}
    # Video time/progress and ads can change unrelated controls every second.
    # Revalidate the exact chosen element rather than the whole page signature.
    if request["control"] not in controls:
        raise ValueError("The chosen control changed before selection. Please repeat the command.")
    control = request["control"]
    element = wrappers[tuple(control["id"])]
    role = control["role"]
    if request["operation"] in {"fill_text", "open_menu"}:
        from .desktop_actions import apply_control
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError("Focus changed before desktop action.")
        return {"message": apply_control(element, control, request["operation"], request.get("content", ""))}
    # Resolve a supported pattern BEFORE invoking it. Never retry a failed action
    # with a second click: the original action may already have taken effect.
    patterns = ("iface_selection_item", "iface_invoke") if role in {"TabItem", "ListItem", "TreeItem", "RadioButton"} else ("iface_invoke", "iface_selection_item")
    if role == "ComboBox":
        patterns = ("iface_expand_collapse",)
    elif role == "CheckBox":
        patterns = ("iface_toggle",)
    pattern, interface = None, None
    for candidate in patterns:
        try:
            interface = getattr(element, candidate)
            pattern = candidate
            break
        except NoPatternInterfaceError:
            continue
    if pattern is None:
        raise ValueError("This control has no supported selection/click pattern. Use the mouse for this control.")
    if win32gui.GetForegroundWindow() != hwnd:
        raise ValueError("Focus changed before selection; command cancelled.")
    if pattern == "iface_invoke":
        interface.Invoke()
    elif pattern == "iface_selection_item":
        interface.Select()
    elif pattern == "iface_expand_collapse":
        interface.Expand()
    elif request.get("verb") != "select" or interface.CurrentToggleState != 1:
        interface.Toggle()
    return {"message": f"Activated {control['name']} ({role})"}


if __name__ == "__main__":
    try:
        result = perform(json.loads(sys.argv[1]))
    except Exception as exc:
        result = {"error": str(exc)}
    print(json.dumps(result, ensure_ascii=True))
