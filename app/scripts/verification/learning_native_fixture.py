"""Owned native app fixture: one real button creates an SVG in its fixture folder."""
import json
from pathlib import Path
import sys
import win32api
import win32con
import win32gui

def main():
    root = Path(sys.argv[1])
    state = root/'state.json'
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="120"><circle cx="100" cy="60" r="40" fill="steelblue"/></svg>'
    def publish(created):
        state.write_text(json.dumps({'root': handle, 'created': created}), encoding='utf-8')
    def procedure(hwnd, message, wparam, lparam):
        if message == win32con.WM_COMMAND and win32api.LOWORD(wparam) == 200:
            (root/'diagram.svg').write_text(svg, encoding='utf-8')
            win32gui.SetWindowText(button, 'Diagram created')
            publish(True)
            return 0
        if message == win32con.WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            return 0
        if message == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)
    module = win32api.GetModuleHandle(None)
    definition = win32gui.WNDCLASS()
    definition.hInstance, definition.lpszClassName = module, 'JarvisLearningFixture'
    definition.lpfnWndProc, definition.hbrBackground = procedure, win32con.COLOR_WINDOW+1
    win32gui.RegisterClass(definition)
    handle = win32gui.CreateWindow(definition.lpszClassName, 'Learning Fixture', win32con.WS_OVERLAPPEDWINDOW,
        80,80,360,180,0,0,module,None)
    button = win32gui.CreateWindow('BUTTON','Create diagram',win32con.WS_CHILD|win32con.WS_VISIBLE|win32con.WS_TABSTOP,
        40,40,220,40,handle,200,module,None)
    publish(False)
    win32gui.ShowWindow(handle, win32con.SW_SHOWNORMAL)
    win32gui.PumpMessages()

if __name__ == '__main__':
    main()
