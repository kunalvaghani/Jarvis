"""Live Qwen file-task/answer checks in temporary folders; no desktop actions."""
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from jarvis.actions import Actions
from jarvis.brain import BrainClient
from jarvis.commands import Command
from jarvis.engine import Engine

BASE = Path(__file__).resolve().parent


def main():
    options = json.loads((BASE / "config.json").read_text(encoding="utf-8"))["brain"]
    with tempfile.TemporaryDirectory(prefix="jarvis-clarification-") as temporary:
        folder = Path(temporary) / "Downloads"
        folder.mkdir()
        actions = Actions({"files_root": "files", "apps": {}, "folders": {"downloads": str(folder)},
            "brain": {**options, "screen_aware": False, "adaptive_planning": False}}, temporary, lambda *_: None)
        actions.brain.client = BrainClient(BASE, options)
        actions.brain.observe = Mock(return_value=(0, {"title": "Downloads - File Explorer",
            "controls": [{"name": "Downloads", "role": "Pane"}]}))
        try:
            engine = Engine(actions.submit, lambda *_: None)
            engine.feed("Hey Jarvis, open folder downloads, create a file called JarvisTest .txt there and write hello kunal in it.", final=True)
            _, command = actions.queue.get_nowait()
            with patch("jarvis.actions.os.startfile"):
                result = actions.execute(command)
            assert (folder / "JarvisTest.txt").read_text(encoding="utf-8") == "hello kunal", result
            print("Reported voice request: exact file/content verified; Explorer launch stubbed.", flush=True)
            paused = actions.execute(Command("task", "Create a file called answer.txt and write follow-up works"))
            assert actions.pending_question, paused
            actions.submit(Command("ask", "Downloads"))
            _, reply = actions.queue.get_nowait()
            assert reply.kind == "clarified_task", reply
            result = actions.execute(reply)
            assert (folder / "answer.txt").read_text(encoding="utf-8") == "follow-up works", result
            print("Folder reply: continued original task and verified exact file/content.", flush=True)
            print("Live checks passed. Real Qwen inference and temporary file writes; synthetic Explorer observations. No desktop, microphone, or account actions.", flush=True)
        finally:
            actions.brain.client.close()


if __name__ == "__main__":
    main()
