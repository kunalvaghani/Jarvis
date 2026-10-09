"""On-demand launcher for Bilawal Sidhu's local God's Eye View console."""
from pathlib import Path
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen


URL = "http://127.0.0.1:4173/"
SOURCE = Path(__file__).resolve().parent.parent / "integrations" / "gods-eye-view-src" / "gods-eye-view-main"


def ready():
    try:
        with urlopen(URL, timeout=1) as response:
            page = response.read(32000).decode("utf-8", errors="replace")
        return "God's Eye View" in page or "gods-eye-view" in page
    except (OSError, URLError):
        return False


class GodsEyeView:
    def __init__(self, source=SOURCE):
        self.source = Path(source)
        self.process = None
        self.log = None

    def start(self, cancelled=lambda: False):
        if ready():
            return URL
        vite = self.source / "node_modules" / "vite" / "bin" / "vite.js"
        if not vite.is_file():
            raise ValueError("God's Eye View is not installed. Complete its local npm setup first.")
        if cancelled():
            raise ValueError("God's Eye View launch cancelled.")
        self.log = (self.source / "jarvis-launch.log").open("a", encoding="utf-8")
        try:
            self.process = subprocess.Popen(["node", str(vite), "--host", "127.0.0.1", "--port", "4173", "--strictPort"],
                                            cwd=self.source, stdout=self.log, stderr=subprocess.STDOUT,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError:
            self.close()
            raise ValueError("Node.js could not start God's Eye View. Check that Node 24 is installed.") from None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if cancelled():
                self.close()
                raise ValueError("God's Eye View launch cancelled.")
            if self.process.poll() is not None:
                self.close()
                raise ValueError("God's Eye View did not start; see jarvis-launch.log in its folder.")
            if ready():
                return URL
            time.sleep(.2)
        self.close()
        raise ValueError("God's Eye View startup timed out; see jarvis-launch.log in its folder.")

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None
        if self.log:
            self.log.close()
            self.log = None
