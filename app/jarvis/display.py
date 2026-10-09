"""Native Windows DPI setup before Tk creates any windows."""
import ctypes
import os


def enable_high_dpi():
    if os.name != 'nt':
        return False
    try:
        user = ctypes.WinDLL('user32', use_last_error=True)
        setter = user.SetProcessDpiAwarenessContext
        setter.argtypes = (ctypes.c_void_p,)
        setter.restype = ctypes.c_bool
        if setter(ctypes.c_void_p(-4)):  # Per Monitor V2
            return True
        if ctypes.get_last_error() == 5:  # Manifest/another library already set awareness.
            return False
    except (AttributeError, OSError):
        pass
    try:
        return bool(ctypes.WinDLL('user32').SetProcessDPIAware())
    except (AttributeError, OSError):
        return False


def window_scale(root):
    try:
        handle = root.winfo_id()
        if not isinstance(handle, int):
            return 1.
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.GetDpiForWindow.argtypes = (ctypes.c_void_p,)
        user.GetDpiForWindow.restype = ctypes.c_uint
        dpi = user.GetDpiForWindow(handle)
        return min(3., max(1., dpi / 96.)) if dpi else 1.
    except (AttributeError, OSError, TypeError, ctypes.ArgumentError):
        return 1.
