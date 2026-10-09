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
            try:
                item['focused'] = bool(info.element.CurrentHasKeyboardFocus)
            except Exception:
                pass
            if info.control_type == 'TabItem':
                try:
                    item['selected'] = bool(element.iface_selection_item.CurrentIsSelected)
                except Exception:
                    pass
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


def routed(request, window, element, control, hwnd):
    """Admit live targets for every provider; no wrapper survives a request."""
    import win32gui
    import win32process
    from pywinauto.uia_defines import NoPatternInterfaceError
    from .execution_router import execute, UncertainAction
    target_pid = win32process.GetWindowThreadProcessId(hwnd)[1]

    def guard():
        if (not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1] != target_pid
                or win32gui.GetForegroundWindow() != hwnd):
            raise ValueError('The destination or focus changed; no further input issued.')
        if not element.is_visible() or not element.is_enabled():
            raise ValueError('The chosen control is hidden or disabled; no further input issued.')
        if control.get('id'):
            info = element.element_info
            rect = element.rectangle()
            name = element.window_text().strip() or str(getattr(info, 'automation_id', '') or '').strip()
            if (list(info.runtime_id) != control['id'] or info.control_type != control['role']
                    or [rect.left, rect.top, rect.right, rect.bottom] != control['rect']
                    or name != control['name']):
                raise ValueError('The selected accessible control changed; no further input issued.')
            if request['operation'] == 'fill_text':
                if bool(getattr(info, 'is_password', False)):
                    raise ValueError('Password field entry is not supported.')
                try:
                    value = element.iface_value
                except NoPatternInterfaceError:
                    pass
                else:
                    if value.CurrentIsReadOnly:
                        raise ValueError('The selected field is read-only; no input issued.')

    def observe():
        # Read-only after dispatch; a closed window is evidence only, never replay.
        if not win32gui.IsWindow(hwnd):
            return 'closed'
        return collect(window)[2]

    def record(receipt):
        # Metadata only: never write typed text, window titles or screenshots here.
        try:
            from datetime import datetime, timezone
            path = Path(__file__).resolve().parents[1] / '.jarvis-runtime/execution-receipts.jsonl'
            path.parent.mkdir(exist_ok=True)
            attempts = receipt.get('attempts', [])
            dispatch_failed = 'dispatch_error' in receipt
            receipt = {key: value for key, value in receipt.items() if key not in {'message', 'dispatch_error', 'attempts'}}
            # Arbitrary provider exception strings could contain field contents.
            # Retain only fixed state metadata, never those strings on disk.
            receipt['attempts'] = [{'provider': row['provider'], 'state': row['state'],
                                    'error_type': row.get('error_type', 'Unsupported')}
                                   for row in attempts]
            receipt['dispatch_failed'] = dispatch_failed
            with path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'date': datetime.now(timezone.utc).isoformat(), **receipt}) + '\n')
        except OSError:
            pass  # Receipt I/O cannot make an external action retriable.
    try:
        from .independent_cursor import CursorCue
        cue = (lambda chosen: CursorCue(chosen['rect'],hwnd)) if request['operation'] in {'activate','open_menu'} else None
        result = execute(request, element, control, window, guard, observe, cue=cue)
    except UncertainAction as exc:
        record(exc.receipt)
        raise
    record({key: value for key, value in result.items() if key != 'message'})
    return result


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
        if win32gui.GetForegroundWindow()!=hwnd:window.set_focus()
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError("The target app did not take focus.")
    controls, wrappers, signature = collect(window)
    if request['operation'] == 'windows_commands':
        from .windows_command_desktop import perform as windows_perform
        return windows_perform(request, window, signature)
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
            return routed(request, window, window, {'name': key, 'role': 'Pane'}, hwnd)
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
            return routed(request, window, target, {'name': request['value'], 'role': 'Pane'}, hwnd)
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
                'target_pid': win32process.GetWindowThreadProcessId(hwnd)[1],
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
            button = buttons[0]
            rect = button.rectangle()
            chosen = {'name':button.window_text().strip(),'role':'Button',
                      'id':list(button.element_info.runtime_id),
                      'rect':[rect.left,rect.top,rect.right,rect.bottom]}
            routed(request,window,button,chosen,hwnd)
        else:
            raise ValueError('This Spotify row exposes no accessible Play button. Jarvis kept your pointer untouched; choose a visible Play control.')
        return {'message': 'Requested playback of the selected Spotify track; playback state is not yet verified.'}
    if request["operation"] in {"fill_text", "open_menu"}:
        from .desktop_actions import apply_control
        if win32gui.GetForegroundWindow() != hwnd:
            raise ValueError("Focus changed before desktop action.")
        return routed(request, window, element, control, hwnd)
    return routed(request, window, element, control, hwnd)


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
