"""Owned Win32 twenty-stage execution fixture; no user apps or network."""
import json
from pathlib import Path
import sys
import win32api
import win32con
import win32gui


def main():
    path = Path(sys.argv[1])
    completed, buttons = [], []
    def publish():
        raw = {'root': root, 'completed': completed}
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(raw), encoding='utf-8')
        temporary.replace(path)
    def procedure(hwnd, message, wparam, lparam):
        if message == win32con.WM_COMMAND:
            index = win32api.LOWORD(wparam)-200
            if 0 <= index < 20:
                completed.append(index+1)
                win32gui.SetWindowText(buttons[index], f'Stage {index+1:02d} done')
                win32gui.SetWindowText(hwnd, f'Jarvis fixture: {len(completed)} stages verified')
                publish()
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
    definition.hInstance, definition.lpszClassName = module, 'JarvisPlanExecutionFixture'
    definition.lpfnWndProc = procedure
    definition.hbrBackground = win32con.COLOR_WINDOW+1
    win32gui.RegisterClass(definition)
    root = win32gui.CreateWindow(definition.lpszClassName, 'Jarvis fixture: 0 stages verified',
                                win32con.WS_OVERLAPPEDWINDOW, 80, 80, 600, 400, 0, 0, module, None)
    for index in range(20):
        button = win32gui.CreateWindow('BUTTON', f'Stage {index+1:02d}',
            win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.WS_TABSTOP,
            20+(index%4)*135, 20+(index//4)*60, 125, 40, root, 200+index, module, None)
        buttons.append(button)
    win32gui.ShowWindow(root, win32con.SW_SHOWNORMAL)
    publish()
    win32gui.PumpMessages()


if __name__ == '__main__':
    main()
