"""Capture one visible window for a user-initiated screen question."""
import base64
import ctypes
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def choose_window(preferred=0, owner_pid=None):
    import win32gui
    import win32process

    if owner_pid is not None and (type(owner_pid) is not int or owner_pid <= 0):
        raise ValueError('Screen capture owner must be a positive process ID.')
    excluded = {os.getpid(), os.getppid(), owner_pid}

    def usable(hwnd, require_title=False):
        if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return False
        if win32process.GetWindowThreadProcessId(hwnd)[1] in excluded:
            return False
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return (right - left >= 250 and bottom - top >= 150
                and (not require_title or bool(win32gui.GetWindowText(hwnd).strip())))

    if usable(preferred):
        return preferred
    foreground = win32gui.GetForegroundWindow()
    if usable(foreground):
        return foreground
    candidates = []
    win32gui.EnumWindows(lambda hwnd, _: candidates.append(hwnd) if usable(hwnd, require_title=True) else None, None)
    return candidates[0] if candidates else 0


def capture(handle=0, strict=False, skip_ocr=False, owner_pid=None):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
    import win32gui
    from PIL import ImageGrab

    captured_at = time.time()
    hwnd = choose_window(handle, owner_pid=owner_pid)
    if strict and (not handle or hwnd != handle):
        raise ValueError('The selected visual target is unavailable; no substitute window was captured.')
    if hwnd:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True).convert("RGB")
        title = win32gui.GetWindowText(hwnd).strip() or "Active window"
    else:
        image = ImageGrab.grab(all_screens=True).convert("RGB")
        title = "Desktop"
    image.thumbnail((1600, 1200))
    encoded = io.BytesIO()
    image.save(encoded, format="JPEG", quality=78, optimize=True)
    ocr = ""
    executable = shutil.which("tesseract") or Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if not strict and not skip_ocr and Path(executable).is_file():
        try:
            result = subprocess.run([str(executable), "stdin", "stdout", "-l", "eng+hin"],
                                    input=encoded.getvalue(), capture_output=True, timeout=12,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode == 0:
                ocr = result.stdout.decode("utf-8", errors="replace")[:6000]
        except (OSError, subprocess.TimeoutExpired):
            # Vision can still use the valid screenshot if optional OCR is unavailable.
            pass
    result = {"title": title[:250],
              "ocr": ocr, "image": base64.b64encode(encoded.getvalue()).decode("ascii")}
    if hwnd:
        import win32process
        result.update(handle=hwnd, pid=win32process.GetWindowThreadProcessId(hwnd)[1],
                      rect=[left, top, right, bottom], image_size=list(image.size),
                      captured_at=captured_at)
    return result


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        result = capture(int(request.get("handle") or 0), strict=request.get('strict') is True,
                         skip_ocr=request.get('skip_ocr') is True, owner_pid=request.get('owner_pid'))
    except Exception as exc:
        result = {"error": str(exc)}
    print(json.dumps(result, ensure_ascii=True))
