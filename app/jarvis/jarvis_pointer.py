"""Jarvis's own physical pointer: real taps that never use your mouse buttons.

Clicks are delivered with Windows touch injection, a separate input pointer, so
buttons that ignore accessibility "invoke" (custom app controls, canvases, web
pages in your own browser) still receive a genuine click. Windows moves its
hidden mouse position to the tap for older mouse-only apps; Jarvis puts your
pointer back where it was and keeps it visible. If you are moving the mouse or
holding a button, Jarvis waits briefly and refuses rather than interfere.
"""
import ctypes
from ctypes import wintypes
import threading
import time


class POINTER_INFO(ctypes.Structure):
    _fields_ = [('pointerType', ctypes.c_uint32), ('pointerId', ctypes.c_uint32), ('frameId', ctypes.c_uint32),
                ('pointerFlags', ctypes.c_uint32), ('sourceDevice', wintypes.HANDLE), ('hwndTarget', wintypes.HWND),
                ('ptPixelLocation', wintypes.POINT), ('ptHimetricLocation', wintypes.POINT),
                ('ptPixelLocationRaw', wintypes.POINT), ('ptHimetricLocationRaw', wintypes.POINT),
                ('dwTime', wintypes.DWORD), ('historyCount', ctypes.c_uint32), ('InputData', ctypes.c_int32),
                ('dwKeyStates', wintypes.DWORD), ('PerformanceCount', ctypes.c_uint64), ('ButtonChangeType', ctypes.c_int)]


class POINTER_TOUCH_INFO(ctypes.Structure):
    _fields_ = [('pointerInfo', POINTER_INFO), ('touchFlags', ctypes.c_uint32), ('touchMask', ctypes.c_uint32),
                ('rcContact', wintypes.RECT), ('rcContactRaw', wintypes.RECT), ('orientation', ctypes.c_uint32),
                ('pressure', ctypes.c_uint32)]


PT_TOUCH = 2
FLAG_DOWN = 0x2 | 0x4 | 0x10000  # INRANGE | INCONTACT | DOWN
FLAG_UP = 0x40000
TOUCH_MASK = 0x1 | 0x2 | 0x4  # contact area, orientation, pressure
MOUSE_MOVE = 0x0001
_lock = threading.Lock()
_initialized = [False]


def user32():
    return ctypes.WinDLL('user32', use_last_error=True)


def wait_for_idle_mouse(user, clock=time.monotonic, sleep=time.sleep, quiet=.15, limit=1.5):
    """Wait until the user's mouse is still and no button is held; False if that never happens."""
    started = clock()
    last = wintypes.POINT()
    user.GetCursorPos(ctypes.byref(last))
    still_since = clock()
    while clock() - started < limit:
        point = wintypes.POINT()
        user.GetCursorPos(ctypes.byref(point))
        held = any(user.GetAsyncKeyState(key) & 0x8000 for key in (0x01, 0x02, 0x04))
        if (point.x, point.y) != (last.x, last.y) or held:
            last, still_since = point, clock()
        elif clock() - still_since >= quiet:
            return True
        sleep(.02)
    return False


def tap(x, y, user=None, sleep=time.sleep, clock=time.monotonic):
    """One physical tap at screen pixel (x, y). Never retried; raises before any input if unsafe."""
    user = user or user32()
    with _lock:
        try:
            user.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))  # Physical pixels (per-monitor v2).
        except (AttributeError, OSError):
            pass
        if not wait_for_idle_mouse(user, clock, sleep):
            raise ValueError("You are using the mouse, so Jarvis did not click. It will not retry on its own.")
        if not _initialized[0]:
            if not user.InitializeTouchInjection(1, 0x3):  # One contact, no touch feedback ripple.
                raise ValueError("Windows refused Jarvis's pointer (touch injection unavailable); no click was sent.")
            _initialized[0] = True
        before = wintypes.POINT()
        user.GetCursorPos(ctypes.byref(before))
        info = POINTER_TOUCH_INFO()
        info.pointerInfo.pointerType = PT_TOUCH
        info.pointerInfo.ptPixelLocation = wintypes.POINT(int(x), int(y))
        info.touchMask = TOUCH_MASK
        info.rcContact = wintypes.RECT(int(x) - 2, int(y) - 2, int(x) + 2, int(y) + 2)
        info.orientation = 90
        info.pressure = 512
        info.pointerInfo.pointerFlags = FLAG_DOWN
        if not user.InjectTouchInput(1, ctypes.byref(info)):
            raise ValueError("Windows refused Jarvis's tap (error %d); no click was sent." % ctypes.get_last_error())
        try:
            sleep(.04)
        finally:
            # Always lift the contact once it went down, so no touch stays pressed.
            info.pointerInfo.pointerFlags = FLAG_UP
            lifted = user.InjectTouchInput(1, ctypes.byref(info))
            # Put the user's pointer back and keep it visible (touch input hides it).
            sleep(.03)
            user.SetCursorPos(before.x, before.y)
            user.mouse_event(MOUSE_MOVE, 1, 0, 0, 0)
            user.mouse_event(MOUSE_MOVE, -1, 0, 0, 0)
            sleep(.01)
            user.SetCursorPos(before.x, before.y)
        if not lifted:
            raise ValueError("Jarvis's tap may not have completed; inspect the screen before repeating.")
        return True


def enabled(base=None):
    """cursor.physical_clicks in config.json (default on)."""
    import json
    from pathlib import Path
    path = Path(base or Path(__file__).resolve().parents[1]) / 'config/config.json'
    try:
        return bool(json.loads(path.read_text(encoding='utf-8')).get('cursor', {}).get('physical_clicks', True))
    except (OSError, ValueError):
        return True
