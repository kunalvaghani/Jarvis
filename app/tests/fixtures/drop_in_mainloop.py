"""A drop arriving while Tk's event loop runs, as in Jarvis (run in its own process by test_documents).

Before the 2026-10-12 fix this aborted with "Fatal Python error: PyEval_RestoreThread".
"""
import ctypes
import struct
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from jarvis import file_drop as fd

root = tk.Tk()
canvas = tk.Canvas(root, width=200, height=50)
canvas.pack()
root.update()
got = []
target = fd.DropTarget(root, [canvas], got.extend)
hwnd = canvas.winfo_id()
path = str(Path(sys.argv[2]))


def drop():
    time.sleep(1.0)
    data = struct.pack("<IiiII", 20, 0, 0, 0, 1) + (path + "\0\0").encode("utf-16-le")
    kernel = ctypes.windll.kernel32
    kernel.GlobalAlloc.restype = ctypes.c_void_p
    kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalLock.argtypes = kernel.GlobalUnlock.argtypes = [ctypes.c_void_p]
    handle = kernel.GlobalAlloc(0x0042, len(data))
    ctypes.memmove(kernel.GlobalLock(handle), data, len(data))
    kernel.GlobalUnlock(handle)
    user = ctypes.windll.user32
    user.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    user.PostMessageW(hwnd, fd.WM_DROPFILES, handle, None)  # Delivered inside Tk's own event loop, like a real drop.


def poll():
    if hasattr(target, "poll"):
        target.poll()
    if got:
        print("RECEIVED", got, flush=True)
        root.after(300, root.destroy)
        return
    root.after(50, poll)


def keepalive():
    root.after(20, keepalive)  # Tk's after/callback traffic, like Jarvis's island animation.


threading.Thread(target=drop, daemon=True).start()
root.after(50, poll)
root.after(20, keepalive)
root.after(8000, lambda: (print("TIMEOUT", flush=True), root.destroy()))
root.mainloop()
target.close()
print("CLEAN EXIT", flush=True)
