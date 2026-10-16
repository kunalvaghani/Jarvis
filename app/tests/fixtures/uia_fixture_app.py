"""Disposable Win32 test application for structured UIA execution tests.

python uia_fixture_app.py <title>
One Edit, one "Apply" button and a status label ("Applied: <edit text>" after a
click). Shown without activation so it does not take keyboard focus; exits on
close or after 60 seconds. Owned by the test process; no user data.
"""
import sys
import time

import win32api
import win32con
import win32gui

EDIT, BUTTON, LABEL = 1001, 1002, 1003


def main(title):
    instance = win32api.GetModuleHandle(None)
    controls = {}

    def procedure(handle, message, wparam, lparam):
        if message == win32con.WM_COMMAND and win32api.LOWORD(wparam) == BUTTON:
            text = win32gui.GetWindowText(controls['edit'])
            win32gui.SetWindowText(controls['label'], 'Applied: ' + text)
            return 0
        if message == win32con.WM_CLOSE:
            win32gui.DestroyWindow(handle)
            return 0
        if message == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(handle, message, wparam, lparam)

    klass = win32gui.WNDCLASS()
    klass.hInstance = instance
    klass.lpszClassName = 'JarvisUiaFixture'
    klass.lpfnWndProc = procedure
    klass.hbrBackground = win32con.COLOR_WINDOW + 1
    win32gui.RegisterClass(klass)
    window = win32gui.CreateWindow('JarvisUiaFixture', title, win32con.WS_OVERLAPPEDWINDOW, 40, 40, 420, 200,
                                   0, 0, instance, None)
    child = win32con.WS_CHILD | win32con.WS_VISIBLE
    controls['edit'] = win32gui.CreateWindow('EDIT', '', child | win32con.WS_BORDER | win32con.ES_AUTOHSCROLL,
                                             10, 10, 380, 24, window, EDIT, instance, None)
    win32gui.CreateWindow('BUTTON', 'Apply', child | win32con.BS_PUSHBUTTON, 10, 44, 100, 30, window, BUTTON, instance, None)
    controls['label'] = win32gui.CreateWindow('STATIC', 'Not applied', child, 10, 84, 380, 24, window, LABEL, instance, None)
    win32gui.ShowWindow(window, win32con.SW_SHOWNOACTIVATE)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if not win32gui.IsWindow(window):
            return
        win32gui.PumpWaitingMessages()
        time.sleep(.01)
    if win32gui.IsWindow(window):
        win32gui.DestroyWindow(window)


if __name__ == '__main__':
    main(sys.argv[1])
