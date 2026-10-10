"""Owned, input-transparent Windows alpha edge; Tk retains all interactive content.

Only the fractional silhouette pixels are composited here. No desktop sampling,
screenshots, focus changes, shared processes or additional service are involved.
"""
import ctypes
from ctypes import wintypes as w
import os

from PIL import Image


class AnimationTimer:
    """Balanced per-process Windows timer request for short Tk frame intervals."""
    def __init__(self):
        self.timer = None
        if os.name == 'nt':
            try:
                timer = ctypes.WinDLL('winmm')
                timer.timeBeginPeriod.argtypes = timer.timeEndPeriod.argtypes = (w.UINT,)
                timer.timeBeginPeriod.restype = timer.timeEndPeriod.restype = w.UINT
                if timer.timeBeginPeriod(1) == 0:
                    self.timer = timer
            except OSError:
                pass

    def close(self):
        if self.timer:
            self.timer.timeEndPeriod(1)
            self.timer = None


class EdgeSurface:
    def __init__(self, root):
        self.root, self.handle, self.key = root, None, None
        self.dc = self.bitmap = self.original = None
        self.size = None
        self.active = False
        if os.name != 'nt' or not isinstance(root.winfo_id(), int):
            return
        try:
            self.user = ctypes.WinDLL('user32', use_last_error=True)
            self.gdi = ctypes.WinDLL('gdi32', use_last_error=True)
            self._signatures()
            owner = self.user.GetAncestor(root.winfo_id(), 2)
            # STATIC has no custom message loop. The owning root destroys the
            # popup too; TRANSPARENT + NOACTIVATE preserve every Tk input target.
            self.handle = self.user.CreateWindowExW(0x80000 | 0x20 | 0x80 | 0x08000000,
                'STATIC', 'Jarvis smooth edge', 0x80000000, 0, 0, 1, 1, owner, None, None, None)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            self.user.SetWindowDisplayAffinity(self.handle, 0x11)
            self.dc = self.gdi.CreateCompatibleDC(None)
            if not self.dc:
                raise ctypes.WinError(ctypes.get_last_error())
            self.active = True
        except (OSError, AttributeError):
            self.close()

    def _signatures(self):
        for name, args, result in (
            ('GetAncestor', (w.HWND, w.UINT), w.HWND),
            ('CreateWindowExW', (w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID), w.HWND),
            ('SetWindowDisplayAffinity', (w.HWND, w.DWORD), w.BOOL),
            ('ShowWindow', (w.HWND, ctypes.c_int), w.BOOL),
            ('DestroyWindow', (w.HWND,), w.BOOL),
            ('UpdateLayeredWindow', (w.HWND, w.HDC, ctypes.c_void_p, ctypes.c_void_p, w.HDC,
                ctypes.c_void_p, w.DWORD, ctypes.c_void_p, w.DWORD), w.BOOL),
            ('SetWindowPos', (w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT), w.BOOL)):
            function = getattr(self.user, name)
            function.argtypes, function.restype = args, result
        for name, args, result in (
            ('CreateCompatibleDC', (w.HDC,), w.HDC),
            ('CreateDIBSection', (w.HDC, ctypes.c_void_p, w.UINT, ctypes.POINTER(ctypes.c_void_p), w.HANDLE, w.DWORD), w.HBITMAP),
            ('SelectObject', (w.HDC, w.HANDLE), w.HANDLE),
            ('DeleteObject', (w.HANDLE,), w.BOOL), ('DeleteDC', (w.HDC,), w.BOOL)):
            function = getattr(self.gdi, name)
            function.argtypes, function.restype = args, result

    def _release_bitmap(self):
        if self.bitmap:
            self.gdi.SelectObject(self.dc, self.original)
            self.gdi.DeleteObject(self.bitmap)
            self.bitmap = self.original = None

    def present(self, mask, left, top, opacity=1., visible=True):
        if not self.active:
            return
        if not visible:
            self.hide()
            return
        key = (mask.size, id(mask), left, top, opacity)
        if key == self.key:
            return
        try:
            if self.size != mask.size or self.key is None or self.key[1] != id(mask):
                self._release_bitmap()
                width, height = mask.size
                # Top-down 32-bit BI_RGB DIB. Black RGB is already premultiplied.
                header = (ctypes.c_int32 * 11)(40, width, -height, 1 | (32 << 16), 0, width * height * 4, 0, 0, 0, 0, 0)
                bits = ctypes.c_void_p()
                self.bitmap = self.gdi.CreateDIBSection(self.dc, header, 0, ctypes.byref(bits), None, 0)
                if not self.bitmap:
                    raise ctypes.WinError(ctypes.get_last_error())
                self.original = self.gdi.SelectObject(self.dc, self.bitmap)
                image = Image.new('RGBA', mask.size)
                image.putalpha(mask.point(lambda alpha: alpha if alpha < 255 else 0))
                raw = image.tobytes('raw', 'BGRA')
                ctypes.memmove(bits, raw, len(raw))
                self.size = mask.size
            destination, source = w.POINT(left, top), w.POINT(0, 0)
            size = w.SIZE(*mask.size)
            blend = (ctypes.c_ubyte * 4)(0, 0, round(min(1., max(0., opacity)) * 255), 1)
            if not self.user.UpdateLayeredWindow(self.handle, None, ctypes.byref(destination), ctypes.byref(size),
                    self.dc, ctypes.byref(source), 0, blend, 2):
                raise ctypes.WinError(ctypes.get_last_error())
            self.user.SetWindowPos(self.handle, w.HWND(-1), left, top, 0, 0, 0x1 | 0x10 | 0x40)
            self.mask, self.key = mask, key  # Keep the cache object alive, avoiding id reuse.
        except OSError:
            self.close()  # The corrected color-key renderer remains available.

    def hide(self):
        if self.handle:
            self.user.ShowWindow(self.handle, 0)
        self.key = None

    def close(self):
        self.active = False
        self._release_bitmap()
        if self.dc:
            self.gdi.DeleteDC(self.dc)
            self.dc = None
        if self.handle:
            self.user.DestroyWindow(self.handle)
            self.handle = None
        self.key = None
