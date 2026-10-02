"""Isolated UIA provider calls; never use guessed screen coordinates."""
import hashlib
import json
import sys
from pathlib import Path

ROLES = {"Button", "SplitButton", "Hyperlink", "MenuItem", "TabItem", "ListItem",
         "TreeItem", "RadioButton", "CheckBox", "ComboBox", "Edit", "Document", "Pane", "Slider", "DataItem"}


def collect(window):
    controls, wrappers = [], {}
    for element in window.descendants(cache_enable=True):
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
                if not item["password"] and name.casefold() in {"search", "search youtube", "search query", "what do you want to play?", "search for songs, artists, or podcasts"}:
                    try:
                        item["value"] = str(element.iface_value.CurrentValue)[:300]
                    except Exception:
                        try:
                            item["value"] = element.iface_text.DocumentRange.GetText(300)
                        except Exception:
                            pass
            if info.control_type == "Hyperlink":
                try:
                    href = element.iface_legacy_iaccessible.CurrentValue
                    if isinstance(href, str) and href.startswith(("https://", "http://")):
                        item["href"] = href[:2000]
                except Exception:
                    pass
            if info.control_type in {"Button", "CheckBox", "RadioButton"}:
                try:
                    item['toggle_state'] = int(element.iface_toggle.CurrentToggleState)
                except Exception:
                    pass
            try:
                parent = element.parent()
                if parent:
                    parent_name = parent.window_text().strip()
                    if parent_name and parent_name != name:
                        item["context"] = parent_name[:150]
            except Exception:
                pass
            if info.control_type == "DataItem" and item.get("context", "").casefold() == "search results":
                # Spotify's root result row omits the artist in its own label.
                # Read child metadata from this fresh row, never from the library.
                try:
                    metadata = [child.window_text().strip() for child in element.descendants(control_type="DataItem", cache_enable=True)]
                    item["metadata"] = next((text[:300] for text in metadata if text.startswith("Song ") and "More options" not in text), "")
                except Exception:
                    pass
            controls.append(item)
            wrappers[tuple(identity)] = element
        except Exception:
            continue
    signature = hashlib.sha256(json.dumps(controls, sort_keys=True).encode()).hexdigest()
    return controls, wrappers, signature


def perform(request):
    # COM initialization stays on this isolated worker's single thread.
    if request.get("operation") == "ping":
        return {"ready": True}
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
    media_platform = request.get('media_platform') or (request.get('platform') if request['operation'].startswith('media_') else None)
    if media_platform:
        import win32api
        from .media_ui import platform_of
        process = win32api.OpenProcess(0x0410, False, win32process.GetWindowThreadProcessId(hwnd)[1])
        try:
            executable = win32process.GetModuleFileNameEx(process, 0)
        finally:
            process.Close()
        if platform_of({'title': window.window_text(), 'context': json.dumps([executable])}) != media_platform:
            raise ValueError('The media destination changed; no action taken.')
    if request["operation"] in {"activate", "fill_text", "scroll", "shortcut", "open_menu", "media_key", "media_range", "media_search_field"}:
        current = win32gui.GetForegroundWindow()
        current_pid = win32process.GetWindowThreadProcessId(current)[1] if current else 0
        if current not in (hwnd,) and current_pid != request["owner_pid"] and not (media_platform and current == request.get('foreground_handle')):
            raise ValueError("Focus changed to another app; selection cancelled.")
        window.set_focus()
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError("The target app did not take focus.")
    controls, wrappers, signature = collect(window)
    if request['operation'] in {'media_key', 'media_range', 'media_search_field'}:
        import win32api
        from .media_ui import platform_of, key_for, fill_search, set_range
        process = win32api.OpenProcess(0x0410, False, win32process.GetWindowThreadProcessId(hwnd)[1])
        try:
            executable = win32process.GetModuleFileNameEx(process, 0)
        finally:
            process.Close()
        snapshot = {'title': window.window_text(), 'context': json.dumps([executable])}
        if platform_of(snapshot) != request.get('platform'):
            raise ValueError('The media app changed before the action; no action taken.')
        target = request.get('control')
        if target is not None and target not in controls:
            raise ValueError('The media control changed before the action; no action taken.')
        element = wrappers[tuple(target['id'])] if target else None
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError('Focus changed before the media action.')
        if request['operation'] == 'media_search_field':
            return {'message': fill_search(element, target, request['content'], hwnd)}
        if request['operation'] == 'media_range':
            return {'message': set_range(element, target, request['value'])}
        key = key_for(request['platform'], request['value'])
        if key is None or (request['platform'] == 'youtube' and element is None):
            raise ValueError('Unsupported media shortcut or missing player focus target.')
        if element is not None:
            element.set_focus()
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError('Focus changed before the media shortcut.')
        window.type_keys(key, set_foreground=False, pause=.02)
        return {'message': 'Sent ' + request['platform'] + ' ' + request['value'] + '; updated media state is not yet verified.'}
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
        thumbnails = {}
        from .media_ui import platform_of
        if platform_of({'context':context,'title':window.window_text()})=='spotify':
            try:
                from .island_artwork import row_artwork
                thumbnails = row_artwork(window,controls,hwnd)
            except Exception:
                pass  # Missing artwork never invalidates accessible controls.
        return {"controls": controls, "signature": signature, "context": context, "is_dialog": modal,
                'thumbnails':thumbnails,
                "foreground_handle": win32gui.GetForegroundWindow(),
                "title": window.window_text()}
    # Video time/progress and ads can change unrelated controls every second.
    # Revalidate the exact chosen element rather than the whole page signature.
    if request["control"] not in controls:
        raise ValueError("The chosen control changed before selection. Please repeat the command.")
    control = request["control"]
    element = wrappers[tuple(control["id"])]
    role = control["role"]
    if request.get('verb') == 'play' and media_platform == 'spotify' and role in {'ListItem', 'DataItem'}:
        buttons = [child for child in element.descendants(control_type='Button')
                   if child.is_enabled() and child.is_visible() and child.window_text().strip().casefold().startswith('play')]
        if len(buttons) > 1:
            raise ValueError('The requested track has multiple Play buttons; no action taken.')
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError('Focus changed before playing the selected track.')
        if buttons:
            interface = buttons[0].iface_invoke
            interface.Invoke()
        else:
            # Spotify rows use native double-click playback when no Play pattern
            # is exposed. Coordinates come from this freshly verified UIA row.
            rect = element.rectangle()
            if [rect.left, rect.top, rect.right, rect.bottom] != control['rect'] or rect.width() <= 0 or rect.height() <= 0:
                raise ValueError('Track geometry changed; no action taken.')
            element.double_click_input()
        return {'message': 'Requested playback of the selected Spotify track; playback state is not yet verified.'}
    if request["operation"] in {"fill_text", "open_menu"}:
        from .desktop_actions import apply_control
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError("Focus changed before desktop action.")
        return {"message": apply_control(element, control, request["operation"], request.get("content", ""))}
    # Resolve a supported pattern BEFORE invoking it. Never retry a failed action
    # with a second click: the original action may already have taken effect.
    patterns = ("iface_selection_item", "iface_invoke") if role in {"TabItem", "ListItem", "DataItem", "TreeItem", "RadioButton"} else ("iface_invoke", "iface_selection_item")
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


def serve():
    # Each request observes fresh wrappers; no cached targets survive a call.
    for line in sys.stdin:
        ident = None
        try:
            envelope = json.loads(line)
            ident = envelope["id"]
            if envelope["request"].get("operation") == "shutdown":
                break
            result = {"id": ident, "result": perform(envelope["request"])}
        except Exception as exc:
            result = {"id": ident, "error": str(exc)}
        print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__" and "--serve" in sys.argv:
    serve()
elif __name__ == "__main__":
    try:
        result = perform(json.loads(sys.argv[1]))
    except Exception as exc:
        result = {"error": str(exc)}
    print(json.dumps(result, ensure_ascii=True))
