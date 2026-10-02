"""One bounded Windows input request; no generated code, retries or alternate targets."""
import base64
import ctypes
from ctypes import wintypes
import io
import json
import math
import os
import sys
import time


def image_difference(first, second, normalized=None):
    from PIL import Image, ImageChops, ImageStat
    a = Image.open(io.BytesIO(base64.b64decode(first, validate=True))).convert('RGB')
    b = Image.open(io.BytesIO(base64.b64decode(second, validate=True))).convert('RGB')
    if a.size != b.size:
        return 1.0
    if normalized is not None:
        x, y = (round(normalized[i] * a.size[i]) for i in (0, 1))
        region = (max(0, x-24), max(0, y-24), min(a.width, x+25), min(a.height, y+25))
        a, b = a.crop(region), b.crop(region)
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / (3 * 255)


def unchanged(first, second, normalized=None):
    return (image_difference(first, second) <= .015 and
            (normalized is None or image_difference(first, second, normalized) <= .03))


def point(frame, normalized):
    if (not isinstance(normalized, (list, tuple)) or len(normalized) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v < 1 for v in normalized)):
        raise ValueError('Visual coordinates must be finite and strictly inside the selected image.')
    left, top, right, bottom = frame['rect']
    x, y = round(left + normalized[0] * (right-left)), round(top + normalized[1] * (bottom-top))
    if not (left+6 <= x < right-6 and top+6 <= y < bottom-6):
        raise ValueError('Visual point is too close to a window edge.')
    return x, y


class WindowsInput:
    def __init__(self):
        import win32gui
        import win32process
        self.gui, self.process = win32gui, win32process
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.user.WindowFromPoint.argtypes = [wintypes.POINT]
        self.user.WindowFromPoint.restype = wintypes.HWND
        self.user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user.GetAncestor.restype = wintypes.HWND

    def state(self, handle):
        if not self.gui.IsWindow(handle) or not self.gui.IsWindowVisible(handle) or self.gui.IsIconic(handle):
            raise ValueError('The visual target is closed, hidden or minimized.')
        return {'handle': handle, 'pid': self.process.GetWindowThreadProcessId(handle)[1],
                'rect': list(self.gui.GetWindowRect(handle)), 'title': self.gui.GetWindowText(handle).strip() or 'Active window'}

    def foreground(self):
        handle = self.gui.GetForegroundWindow()
        return handle, self.process.GetWindowThreadProcessId(handle)[1] if handle else 0

    def focus(self, handle):
        self.gui.SetForegroundWindow(handle)

    def held_modifiers(self):
        return any(self.user.GetAsyncKeyState(k) & 0x8000 for k in (0x10, 0x11, 0x12, 0x5B, 0x5C))

    def screenshot(self, frame):
        from PIL import ImageGrab
        image = ImageGrab.grab(bbox=tuple(frame['rect']), all_screens=True).convert('RGB')
        image.thumbnail((1600, 1200))
        encoded = io.BytesIO()
        image.save(encoded, format='JPEG', quality=78, optimize=True)
        return base64.b64encode(encoded.getvalue()).decode('ascii')

    def hit(self, x, y):
        child = self.user.WindowFromPoint(wintypes.POINT(x, y))
        return self.user.GetAncestor(child, 2) if child else 0  # GA_ROOT

    def inputs(self, keys=None, text=None, click=False):
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                        ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                        ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
        class UNION(ctypes.Union):
            _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]
        class INPUT(ctypes.Structure):
            _fields_ = [('type', wintypes.DWORD), ('u', UNION)]
        rows = []
        if click:
            rows = [INPUT(0, UNION(mi=MOUSEINPUT(0, 0, 0, flag, 0, 0))) for flag in (2, 4)]
        elif keys:
            codes = {'ctrl': 0x11, 'shift': 0x10, 'a': 0x41, 's': 0x53}
            rows = [INPUT(1, UNION(ki=KEYBDINPUT(codes[k], 0, 0, 0, 0))) for k in keys]
            rows += [INPUT(1, UNION(ki=KEYBDINPUT(codes[k], 0, 2, 0, 0))) for k in reversed(keys)]
        else:
            encoded = text.encode('utf-16-le')
            for offset in range(0, len(encoded), 2):
                code = int.from_bytes(encoded[offset:offset+2], 'little')
                rows.extend(INPUT(1, UNION(ki=KEYBDINPUT(0, code, flag, 0, 0))) for flag in (4, 6))
        events = (INPUT * len(rows))(*rows)
        accepted = self.user.SendInput(len(rows), events, ctypes.sizeof(INPUT))
        if accepted != len(rows):
            # Release only downs accepted from this batch. Never replay a click,
            # shortcut or text, and never send speculative downs during cleanup.
            held = {}
            for row in rows[:max(0, min(accepted, len(rows)))]:
                if row.type == 1:
                    key = ('key', row.u.ki.wVk, row.u.ki.wScan, row.u.ki.dwFlags & 4)
                    if row.u.ki.dwFlags & 2:
                        held.pop(key, None)
                    else:
                        held[key] = INPUT(1, UNION(ki=KEYBDINPUT(row.u.ki.wVk, row.u.ki.wScan,
                                                            row.u.ki.dwFlags | 2, 0, 0)))
                elif row.u.mi.dwFlags == 2:
                    held['left'] = INPUT(0, UNION(mi=MOUSEINPUT(0,0,0,4,0,0)))
                elif row.u.mi.dwFlags == 4:
                    held.pop('left', None)
            if held:
                releases = list(reversed(list(held.values())))
                self.user.SendInput(len(releases), (INPUT * len(releases))(*releases), ctypes.sizeof(INPUT))
            raise OSError('Windows blocked or partially accepted visual input; inspect the result, do not retry.')

    def click(self, x, y):
        if not self.user.SetCursorPos(x, y):
            raise OSError('Windows did not allow positioning the pointer.')
        self.inputs(click=True)

    def shortcut(self, name):
        self.inputs(keys=name.split('+'))  # Tokens are a list: never split a key into characters.

    def type(self, text):
        self.inputs(text=text)


def perform(request, backend=None, cancelled=lambda: False):
    """Return attempted=False only when no input call was entered."""
    attempted = False
    try:
        operation = request.get('operation')
        if operation not in {'click', 'fill', 'shortcut'}:
            raise ValueError('Unsupported visual input operation.')
        frame = request['frame']
        if (not isinstance(frame, dict) or not all(k in frame for k in
                ('handle', 'pid', 'rect', 'title', 'captured_at', 'image'))
                or len(frame['image']) > 6_000_000 or len(frame['rect']) != 4
                or any(type(n) is not int for n in frame['rect'])
                or not 0 <= time.time()-frame['captured_at'] <= 5):
            raise ValueError('Visual input requires a fresh bounded capture of one selected window.')
        if frame['pid'] == request['owner_pid']:
            raise ValueError('Visual input cannot target Jarvis itself.')
        if operation == 'shortcut' and request.get('value') not in {'ctrl+shift+s', 'ctrl+s', 'ctrl+a'}:
            raise ValueError('Visual keyboard input is restricted to tested Save/text-field shortcuts.')
        text = request.get('content', '')
        if operation == 'fill' and (not isinstance(text, str) or not 0 < len(text) <= 2000
                or any(ord(c) < 32 for c in text)):
            raise ValueError('Visual text entry needs bounded single-line literal content.')
        normalized = request.get('point')
        xy = point(frame, normalized) if operation in {'click', 'fill'} else None
        backend = backend or WindowsInput()
        current = backend.state(frame['handle'])
        if any(current[k] != frame[k] for k in ('handle', 'pid', 'rect', 'title')):
            raise ValueError('Visual window identity or geometry changed before input.')
        foreground, pid = backend.foreground()
        if foreground != frame['handle']:
            if pid != request['owner_pid']:
                raise ValueError('Focus changed to another app; visual input cancelled.')
            backend.focus(frame['handle'])
        if backend.foreground()[0] != frame['handle'] or backend.held_modifiers():
            raise ValueError('The selected app lacks focus or a physical modifier is held.')
        if not unchanged(frame['image'], backend.screenshot(frame), normalized):
            raise ValueError('The selected image changed before input; obtain a new grounding.')
        if xy and backend.hit(*xy) != frame['handle']:
            raise ValueError('Another window covers the visual target point.')
        if (backend.foreground()[0] != frame['handle'] or backend.state(frame['handle']) != current
                or backend.held_modifiers()):
            raise ValueError('The selected target changed immediately before visual dispatch.')
        if cancelled():
            raise ValueError('Visual input cancelled before dispatch.')
        # No action retry: a short/failed SendInput result may already have effects.
        attempted = True
        if operation == 'click':
            backend.click(*xy)
        elif operation == 'shortcut':
            backend.shortcut(request['value'])
        else:
            backend.shortcut('ctrl+a')
            if backend.foreground()[0] != frame['handle'] or cancelled():
                raise ValueError('Visual text entry stopped after selecting field contents.')
            backend.type(text)
        return {'attempted': True, 'message': 'Visual input dispatched once; fresh outcome verification required.'}
    except Exception as exc:
        return {'attempted': attempted, 'error': str(exc)}


if __name__ == '__main__':
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
        result = perform(json.load(sys.stdin))
    except Exception as exc:
        result = {'attempted': False, 'error': str(exc)}
    print(json.dumps(result))
