"""Controller for the Jarvis-owned browser; shared browsers are never closed."""
from .ui_transport import UITransport
from .browser import browser_args


class BrowserAutomation:
    def __init__(self, apps, base=None):
        self.transport = UITransport(base, timeout=35, module="jarvis.browser_worker")
        self.settings = {"executable": browser_args(apps, "chrome")[0]}
        self.touched = False
        self.user_closed = False
        self.last_url = ""

    def request(self, operation, cancelled=lambda: False, **args):
        if self.user_closed and operation != "reset" and not args.get("new_task"):
            raise ValueError("Jarvis browser was closed; explicitly open Jarvis browser to start another session.")
        try:
            result = self.transport.request({"operation": operation, "settings": self.settings, **args}, cancelled)
        except ValueError as exc:
            if "closed deliberately" in str(exc):
                self.user_closed = True
            raise
        self.touched = True
        self.last_url = result.get("url", self.last_url)
        if operation == "reset" or args.get("new_task"):
            self.user_closed = False
        return result

    def owns_handle(self, handle):
        if not self.touched or not handle or self.user_closed:
            return False
        try:
            import psutil
            import win32process
            profile = str(self.transport.base / ".jarvis-runtime" / "browser-profile").casefold()
            process = psutil.Process(win32process.GetWindowThreadProcessId(handle)[1])
            return any(profile in " ".join(p.cmdline()).casefold() for p in [process, *process.parents()[:6]])
        except (OSError, psutil.Error):
            return False

    def healthy(self):
        return self.transport.healthy()

    def repair(self):
        return not self.user_closed and self.transport.repair()

    def close(self):
        self.transport.close()
