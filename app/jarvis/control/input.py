"""The one real-input path for routes 3 and 4 (replaces the five legacy injectors, audit section 3).

Keyboard uses SendInput (Unicode for text, scan codes for keys, so games and apps that ignore
virtual-key-only input still react). A single left click prefers Jarvis's touch pointer
(jarvis_pointer.tap), which never moves the user's mouse; other clicks use SendInput. Every call
holds exclusive foreground-input ownership and stops on the emergency stop. Nothing is retried:
partially accepted input releases held keys and raises as uncertain.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import time
from typing import Any, Callable, List, Optional, Sequence, Tuple

from .locks import LockManager
from .types import CancelToken, ControlError, ErrorCategory

KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, KEYEVENTF_SCANCODE = 0x1, 0x2, 0x4, 0x8
MOUSE_FLAGS = {'left': (0x2, 0x4), 'right': (0x8, 0x10), 'middle': (0x20, 0x40)}
MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_VIRTUALDESK, MOUSEEVENTF_WHEEL = 0x1, 0x8000, 0x4000, 0x800
VK = {'ctrl': 0x11, 'control': 0x11, 'shift': 0x10, 'alt': 0x12, 'win': 0x5B, 'super': 0x5B, 'meta': 0x5B,
      'enter': 0x0D, 'return': 0x0D, 'tab': 0x09, 'esc': 0x1B, 'escape': 0x1B, 'space': 0x20, 'backspace': 0x08,
      'delete': 0x2E, 'del': 0x2E, 'insert': 0x2D, 'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22,
      'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27, 'capslock': 0x14, 'printscreen': 0x2C,
      **{f'f{i}': 0x6F + i for i in range(1, 25)}}
EXTENDED = {0x2E, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x26, 0x28, 0x25, 0x27, 0x5B}
MODIFIERS = (0x10, 0x11, 0x12, 0x5B, 0x5C)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class _UNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('u', _UNION)]


def parse_chord(chord: str) -> List[int]:
    codes = []
    for part in chord.lower().split('+'):
        part = part.strip()
        if part in VK:
            codes.append(VK[part])
        elif len(part) == 1 and part.isalnum():
            codes.append(ord(part.upper()))
        else:
            raise ControlError(f'Unknown key {part!r}.', ErrorCategory.INVALID_ARGUMENTS)
    return codes


class Input:
    def __init__(self, locks: LockManager, owner: str = 'jarvis', user32: Optional[Any] = None,
                 tap: Optional[Callable[[int, int], Any]] = None, use_pointer: bool = True) -> None:
        self.locks, self.owner = locks, owner
        self.user32 = user32 if user32 is not None else ctypes.WinDLL('user32', use_last_error=True)
        self.tap = tap
        self.use_pointer = use_pointer

    # Low level ----------------------------------------------------------------
    def _send(self, rows: Sequence[INPUT]) -> None:
        if not rows:
            return
        array = (INPUT * len(rows))(*rows)
        accepted = int(self.user32.SendInput(len(rows), array, ctypes.sizeof(INPUT)))
        if accepted != len(rows):
            held = [r for r in rows[:accepted] if r.type == 1 and not r.u.ki.dwFlags & KEYEVENTF_KEYUP]
            released = [r for r in rows[:accepted] if r.type == 1 and r.u.ki.dwFlags & KEYEVENTF_KEYUP]
            pending = [r for r in held if not any(u.u.ki.wVk == r.u.ki.wVk and u.u.ki.wScan == r.u.ki.wScan
                                                  for u in released)]
            ups = [INPUT(1, _UNION(ki=KEYBDINPUT(r.u.ki.wVk, r.u.ki.wScan, r.u.ki.dwFlags | KEYEVENTF_KEYUP, 0, 0)))
                   for r in reversed(pending)]
            if ups:
                self.user32.SendInput(len(ups), (INPUT * len(ups))(*ups), ctypes.sizeof(INPUT))
            raise ControlError('Windows accepted only part of the input (UIPI, secure desktop or a blocking app); '
                               'inspect the result before doing anything else.', ErrorCategory.UNCERTAIN, executed=accepted > 0)

    def _key_rows(self, codes: Sequence[int]) -> List[INPUT]:
        def row(vk: int, up: bool) -> INPUT:
            scan = int(self.user32.MapVirtualKeyW(vk, 0))
            flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED else 0)
            return INPUT(1, _UNION(ki=KEYBDINPUT(vk if not scan else 0, scan, flags if scan else flags & ~KEYEVENTF_SCANCODE, 0, 0)))
        return [row(vk, False) for vk in codes] + [row(vk, True) for vk in reversed(codes)]

    def _guard(self, cancel: Optional[CancelToken]) -> None:
        if cancel is not None:
            cancel.raise_if_cancelled()
        if self.locks.stopped:
            raise ControlError('Emergency stop is active: ' + self.locks.stop_reason, ErrorCategory.CANCELLED)
        if any(int(self.user32.GetAsyncKeyState(k)) & 0x8000 for k in MODIFIERS):
            raise ControlError('A modifier key is held down on the physical keyboard; no input was sent.',
                               ErrorCategory.FOCUS_LOST)

    # Public ---------------------------------------------------------------
    def keys(self, text: str, repeat: int = 1, cancel: Optional[CancelToken] = None) -> None:
        if not text.strip() or not 1 <= repeat <= 100:
            raise ControlError('keys needs text and repeat 1-100.', ErrorCategory.INVALID_ARGUMENTS)
        chords = [parse_chord(chord) for chord in text.split()]
        with self.locks.foreground_input(self.owner, cancel=cancel):
            for _ in range(repeat):
                for codes in chords:
                    self._guard(cancel)
                    self._send(self._key_rows(codes))

    def text(self, text: str, cancel: Optional[CancelToken] = None, chunk: int = 64) -> None:
        if len(text) > 20_000:
            raise ControlError('Typed text is limited to 20,000 characters.', ErrorCategory.INVALID_ARGUMENTS)
        units = text.replace('\r\n', '\n').encode('utf-16-le')
        with self.locks.foreground_input(self.owner, cancel=cancel):
            for start in range(0, len(units), chunk * 2):
                self._guard(cancel)
                rows = []
                for offset in range(start, min(len(units), start + chunk * 2), 2):
                    code = int.from_bytes(units[offset:offset + 2], 'little')
                    if code == 10:  # Newline as a real Enter key: editors ignore a Unicode LF.
                        rows += self._key_rows([VK['enter']])
                        continue
                    rows += [INPUT(1, _UNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | up, 0, 0))) for up in (0, KEYEVENTF_KEYUP)]
                self._send(rows)

    def _absolute(self, x: int, y: int) -> Tuple[int, int]:
        left, top = int(self.user32.GetSystemMetrics(76)), int(self.user32.GetSystemMetrics(77))
        width, height = int(self.user32.GetSystemMetrics(78)), int(self.user32.GetSystemMetrics(79))
        if not (left <= x < left + width and top <= y < top + height):
            raise ControlError(f'Point ({x}, {y}) is outside the virtual desktop.', ErrorCategory.INVALID_ARGUMENTS)
        return round((x - left) * 65535 / max(1, width - 1)), round((y - top) * 65535 / max(1, height - 1))

    def click(self, x: int, y: int, button: str = 'left', count: int = 1, cancel: Optional[CancelToken] = None) -> str:
        """Physical screen pixels. Returns the method used ('pointer' or 'sendinput')."""
        if button not in MOUSE_FLAGS or not 1 <= count <= 3:
            raise ControlError('click needs left/right/middle and 1-3 clicks.', ErrorCategory.INVALID_ARGUMENTS)
        with self.locks.foreground_input(self.owner, cancel=cancel):
            self._guard(cancel)
            if self.use_pointer and button == 'left' and count == 1 and self.tap is not None:
                self.tap(int(x), int(y))
                return 'pointer'
            dx, dy = self._absolute(int(x), int(y))
            move = INPUT(0, _UNION(mi=MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, 0, 0)))
            self._send([move])
            # Windows (UIPI) can drop injected input silently; a pointer that did not arrive means nothing happened.
            where = wintypes.POINT()
            self.user32.GetCursorPos(ctypes.byref(where))
            if abs(where.x - int(x)) > 2 or abs(where.y - int(y)) > 2:
                raise ControlError('Windows ignored Jarvis\'s pointer (a protected window is in front or input is '
                                   'blocked); no click was sent.', ErrorCategory.ELEVATED_TARGET)
            down, up = MOUSE_FLAGS[button]
            rows = []
            for _ in range(count):
                rows += [INPUT(0, _UNION(mi=MOUSEINPUT(0, 0, 0, down, 0, 0))), INPUT(0, _UNION(mi=MOUSEINPUT(0, 0, 0, up, 0, 0)))]
            self._send(rows)
            return 'sendinput'

    def wheel(self, x: int, y: int, notches: int, cancel: Optional[CancelToken] = None) -> None:
        if not -20 <= notches <= 20 or notches == 0:
            raise ControlError('wheel needs 1-20 notches up or down.', ErrorCategory.INVALID_ARGUMENTS)
        with self.locks.foreground_input(self.owner, cancel=cancel):
            self._guard(cancel)
            dx, dy = self._absolute(int(x), int(y))
            self._send([INPUT(0, _UNION(mi=MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, 0, 0))),
                        INPUT(0, _UNION(mi=MOUSEINPUT(0, 0, ctypes.c_uint32(-120 * notches).value, MOUSEEVENTF_WHEEL, 0, 0)))])
            time.sleep(.02)
