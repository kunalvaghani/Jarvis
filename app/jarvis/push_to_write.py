"""Push-to-write: hold Left Ctrl + Left Alt and everything you say is typed at the cursor.

A low-level keyboard hook observes the two keys. Nothing is blocked except the final
Alt release, which is re-sent after a harmless unassigned key (0xE8), because a bare
Alt release puts Notepad, Office and similar apps into menu-shortcut mode, where the
next typed letters would run menu commands. Holding the keys alone activates writing;
pressing any other key during the hold (Ctrl+Alt+Del, Ctrl+Alt+T ...) cancels it.
"""
import ctypes
from ctypes import wintypes
import threading
import time

VK_LCONTROL, VK_LMENU, VK_MASK = 0xA2, 0xA4, 0xE8
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP, WM_QUIT = 0x100, 0x101, 0x104, 0x105, 0x12
LLKHF_INJECTED = 0x10
KEYEVENTF_KEYUP = 2


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [('vkCode', wintypes.DWORD), ('scanCode', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class PushToWrite:
    """Key state machine; the Windows hook feeds key(vk, down, injected)."""
    def __init__(self, on_change, hold_seconds=0.2, send=None, clock=time.monotonic):
        self.on_change, self.hold_seconds, self.clock = on_change, hold_seconds, clock
        self.send = send or self._send_mask_and_alt_up
        self.active = threading.Event()
        self.session = 0
        self.discarded = set()  # Holds cancelled by another key: their speech is not typed.
        self.ctrl = self.alt = self.other = self.combo = False
        self.lock = threading.Lock()
        self.thread = None
        self.thread_id = None
        self.closed = threading.Event()

    # --- key state machine (pure; unit-tested without Windows) ---
    def key(self, vk, down, injected=False):
        """Returns True when this real key event must be blocked (only a masked Alt release)."""
        if injected:
            return False  # Jarvis's own typing and the mask key pass through untouched.
        block = False
        with self.lock:
            if vk == VK_LCONTROL:
                self.ctrl = down
            elif vk == VK_LMENU:
                if not down and self.combo and not self.other:
                    self.send()  # Mask key, then the Alt release: no menu-shortcut mode.
                    block = True
                self.alt = down
            elif down:
                self.other = True
            both = self.ctrl and self.alt
            if both and not self.combo:
                self.combo, self.other, started = True, False, self.clock()
                threading.Thread(target=self._arm, args=(started,), daemon=True).start()
            if not self.ctrl and not self.alt:
                self.combo = self.other = False
            stop = self.active.is_set() and (not both or self.other)
        if stop:
            self._set(False, discard=self.other)
        return block

    def _arm(self, started):
        while self.clock() - started < self.hold_seconds:
            if self.closed.is_set():
                return
            time.sleep(.02)
        with self.lock:
            ready = self.ctrl and self.alt and self.combo and not self.other and not self.active.is_set()
        if ready:
            self._set(True)

    def _set(self, value, discard=False):
        if value:
            self.session += 1
            self.active.set()
        else:
            if discard:
                self.discarded.add(self.session)
            self.active.clear()
        try:
            self.on_change(value, discard)
        except Exception:
            pass  # A UI/report failure must never break the keyboard hook.

    @staticmethod
    def _send_mask_and_alt_up():
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.keybd_event(VK_MASK, 0, 0, 0)
        user.keybd_event(VK_MASK, 0, KEYEVENTF_KEYUP, 0)
        user.keybd_event(VK_LMENU, 0, KEYEVENTF_KEYUP, 0)

    # --- Windows hook ---
    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, name='Jarvis push-to-write', daemon=True)
            self.thread.start()

    def stop(self):
        self.closed.set()
        if self.active.is_set():
            self._set(False)
        if self.thread_id:
            ctypes.WinDLL('user32').PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)

    def _run(self):
        user = ctypes.WinDLL('user32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
        user.SetWindowsHookExW.restype = wintypes.HHOOK
        user.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user.CallNextHookEx.restype = LRESULT
        kernel.GetModuleHandleW.restype = wintypes.HMODULE

        def callback(code, wparam, lparam):
            if code == 0 and wparam in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
                info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                try:
                    if self.key(info.vkCode, wparam in (WM_KEYDOWN, WM_SYSKEYDOWN), bool(info.flags & LLKHF_INJECTED)):
                        return 1
                except Exception:
                    pass
            return user.CallNextHookEx(None, code, wparam, lparam)
        self._proc = HOOKPROC(callback)  # Keep a reference for the hook's lifetime.
        self.thread_id = kernel.GetCurrentThreadId()
        hook = user.SetWindowsHookExW(13, self._proc, kernel.GetModuleHandleW(None), 0)
        if not hook:
            return
        try:
            message = wintypes.MSG()
            while not self.closed.is_set() and user.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                user.TranslateMessage(ctypes.byref(message))
                user.DispatchMessageW(ctypes.byref(message))
        finally:
            user.UnhookWindowsHookEx(hook)
