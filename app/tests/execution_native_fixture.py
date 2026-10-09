"""Owned Win32 fixture. No user applications, files, network or clipboard."""
import json
from pathlib import Path
import sys
import win32api
import win32con
import win32gui


def main():
    path = Path(sys.argv[1])
    handles, clicks = {}, 0
    def publish():
        if not handles:
            return
        state = {'handles': handles, 'clicks': clicks,
                 'text': win32gui.GetWindowText(handles['edit']),
                 'checked': win32gui.SendMessage(handles['check'], 0x00F0, 0, 0)}
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state), encoding='utf-8')
        temporary.replace(path)
    def procedure(hwnd, message, wparam, lparam):
        nonlocal clicks
        if message == win32con.WM_COMMAND and win32api.LOWORD(wparam) == 102:
            clicks += 1
            win32gui.SetWindowText(handles['button'], 'Applied ' + str(clicks))
            publish()
        elif message == win32con.WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            return 0
        elif message == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        elif message == win32con.WM_TIMER:
            publish()
            return 0
        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)
    module = win32api.GetModuleHandle(None)
    definition = win32gui.WNDCLASS()
    definition.hInstance, definition.lpszClassName = module, 'JarvisExecutionFixture'
    definition.lpfnWndProc = procedure
    definition.hbrBackground = win32con.COLOR_WINDOW + 1
    win32gui.RegisterClass(definition)
    root = win32gui.CreateWindow(definition.lpszClassName, 'Jarvis execution verification fixture',
                                win32con.WS_OVERLAPPEDWINDOW, 80, 80, 520, 240, 0, 0, module, None)
    child = win32con.WS_CHILD | win32con.WS_VISIBLE
    win32gui.CreateWindow('STATIC', 'Search', child, 20, 20, 100, 25, root, 100, module, None)
    edit = win32gui.CreateWindow('EDIT', '', child | win32con.WS_BORDER | win32con.WS_TABSTOP,
                                130, 20, 320, 25, root, 101, module, None)
    button = win32gui.CreateWindow('BUTTON', 'Apply', child | win32con.WS_TABSTOP,
                                  20, 70, 180, 30, root, 102, module, None)
    check = win32gui.CreateWindow('BUTTON', 'Enabled', child | win32con.WS_TABSTOP | win32con.BS_AUTOCHECKBOX,
                                 240, 70, 180, 30, root, 103, module, None)
    handles.update(root=root, edit=edit, button=button, check=check)
    win32gui.ShowWindow(root, win32con.SW_SHOWNORMAL)
    import ctypes
    ctypes.windll.user32.SetTimer(root, 1, 50, None)
    publish()
    win32gui.PumpMessages()


if __name__ == '__main__':
    main()
