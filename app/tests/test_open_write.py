import tempfile
import unittest
from unittest.mock import patch

from jarvis.actions import Actions
from jarvis.audio import command_text
from jarvis.commands import Command
from jarvis.engine import Engine


class FakeDesktop:
    def __init__(self):
        self.target = None
        self.foreground = "notepad"
        self.typed = []
        self.refuse_capture = False

    def capture(self, expected=None):
        if self.refuse_capture:
            raise ValueError("No text destination")
        self.target = self.foreground

    def type(self, text, cancelled):
        if not cancelled():
            self.typed.append((self.target, text))


class OpenWriteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.desktop = FakeDesktop()
        self.actions = Actions({"files_root": "files", "apps": {"notepad": ["notepad.exe"]}},
                               self.folder.name, lambda *args: None, self.desktop)

    def test_full_whisper_to_action_queue_open_and_write(self):
        self.actions.start()
        try:
            engine = Engine(self.actions.submit, lambda *args: None)
            engine.activate()
            with patch("jarvis.actions.subprocess.Popen") as launch, patch("jarvis.actions.time.sleep"):
                engine.feed(command_text("Open Notepad and write my name is Kunal."), final=True)
                self.actions.queue.join()
                launch.assert_called_once_with(["notepad.exe"], shell=False)
            self.assertEqual(self.desktop.typed, [("notepad", "my name is kunal ")])
        finally:
            self.actions.close()
            self.actions.thread.join(2)

    def test_new_dictation_rebinds_to_current_app(self):
        self.desktop.target = "old app"
        self.desktop.foreground = "new app"
        self.actions.typing_failed = True
        self.actions.execute(Command("begin_dictation"))
        self.actions.execute(Command("type", "hello "))
        self.assertEqual(self.desktop.typed, [("new app", "hello ")])

    def test_failed_open_cannot_type_into_unrelated_app(self):
        self.actions.open_target_pending = True
        self.actions.typing_failed = True
        with self.assertRaises(ValueError):
            self.actions.execute(Command("begin_dictation"))
        with self.assertRaises(ValueError):
            self.actions.execute(Command("type", "hello "))
        self.assertEqual(self.desktop.typed, [])

    def test_successful_open_keeps_verified_target(self):
        self.actions.open_target_pending = True
        self.desktop.target = "notepad"
        self.desktop.foreground = "another window"
        self.actions.execute(Command("begin_dictation"))
        self.assertEqual(self.desktop.target, "notepad")

    def test_failed_capture_blocks_following_text(self):
        self.desktop.refuse_capture = True
        with self.assertRaises(ValueError):
            self.actions.execute(Command("begin_dictation"))
        with self.assertRaises(ValueError):
            self.actions.execute(Command("type", "hello "))
        self.assertEqual(self.desktop.typed, [])


if __name__ == "__main__":
    unittest.main()
