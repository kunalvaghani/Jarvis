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


def choose_window(preferred=0):
    import win32gui
    import win32process

    def usable(hwnd, require_title=False):
        if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return False
        if win32process.GetWindowThreadProcessId(hwnd)[1] == os.getppid():
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


def capture(handle=0):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
    import win32gui
    from PIL import ImageGrab

    hwnd = choose_window(handle)
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
    if Path(executable).is_file():
        try:
            result = subprocess.run([str(executable), "stdin", "stdout", "-l", "eng+hin"],
                                    input=encoded.getvalue(), capture_output=True, timeout=12,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode == 0:
                ocr = result.stdout.decode("utf-8", errors="replace")[:6000]
        except (OSError, subprocess.TimeoutExpired):
            # Vision can still use the valid screenshot if optional OCR is unavailable.
            pass
    return {"title": title[:250],
            "ocr": ocr, "image": base64.b64encode(encoded.getvalue()).decode("ascii")}


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        result = capture(int(request.get("handle") or 0))
    except Exception as exc:
        result = {"error": str(exc)}
    print(json.dumps(result, ensure_ascii=True))
