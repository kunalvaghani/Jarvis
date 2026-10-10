"""Writing without a dictation mode: open-and-write, exact text, composed text."""
import json
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
        self.user = None

    def capture(self, expected=None):
        if self.refuse_capture:
            raise ValueError("No text destination")
        self.target = self.foreground

    def type(self, text, cancelled):
        if not cancelled():
            self.typed.append((self.target, text))


def write(kind, value, target=''):
    return Command(kind, value, json.dumps({'target': target, 'tail': ''}))


class OpenWriteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.desktop = FakeDesktop()
        self.actions = Actions({"files_root": "files", "apps": {"notepad": ["notepad.exe"]}},
                               self.folder.name, lambda *args: None, self.desktop)
        patch('jarvis.writing.safe_text', side_effect=lambda text, hwnd: text).start()
        self.addCleanup(patch.stopall)

    def test_full_whisper_to_action_queue_open_and_write_exactly(self):
        self.actions.start()
        try:
            engine = Engine(self.actions.submit, lambda *args: None)
            engine.activate()
            raw = "Open Notepad and write exactly My name is Kunal."
            with patch("jarvis.actions.subprocess.Popen") as launch, patch("jarvis.actions.time.sleep"), \
                    patch("jarvis.window_focus.focus_app", return_value="notepad"):
                engine.feed(command_text(raw), final=True, raw=raw)
                self.actions.queue.join()
                launch.assert_called_once_with(["notepad.exe"], shell=False)
            self.assertEqual(self.desktop.typed, [("notepad", "My name is Kunal.")])
        finally:
            self.actions.close()
            self.actions.thread.join(2)

    def test_exact_text_goes_to_the_current_app(self):
        self.desktop.target = "old app"
        self.desktop.foreground = "new app"
        self.actions.execute(write("write_text", "hello"))
        self.assertEqual(self.desktop.typed, [("new app", "hello")])

    def test_failed_open_cannot_type_into_unrelated_app(self):
        self.desktop.foreground = "unrelated app"
        with patch("jarvis.window_focus.focus_app", return_value=None), patch("jarvis.actions.subprocess.Popen"), \
                patch("jarvis.actions.time.sleep"):
            with self.assertRaisesRegex(ValueError, "nothing was typed"):
                self.actions.execute(write("write_text", "hello", "notepad"))
        self.assertEqual(self.desktop.typed, [])

    def test_unknown_in_phrase_stays_part_of_the_text(self):
        self.actions.execute(Command("write_text", "a trip", json.dumps({"target": "paris", "tail": " in paris"})))
        self.assertEqual(self.desktop.typed, [("notepad", "a trip in paris")])

    def test_failed_capture_types_nothing(self):
        self.desktop.refuse_capture = True
        with self.assertRaises(ValueError):
            self.actions.execute(write("write_text", "hello"))
        self.assertEqual(self.desktop.typed, [])

    def test_composed_text_is_typed_as_it_streams(self):
        from jarvis import writing
        def chat(client, options, messages):
            for piece in ("Dear team,", " the meeting", " moved to Friday.", "\nThanks"):
                options['on_chunk'](piece)
        result = writing.compose(self.actions, write("compose_text", "a short note that the meeting moved"),
                                 lambda: False, chat=chat, client=object())
        self.assertEqual("".join(text for _, text in self.desktop.typed), "Dear team, the meeting moved to Friday.\nThanks")
        self.assertGreater(len(self.desktop.typed), 1)  # Typed while generating, not only at the end.
        self.assertIn("Wrote 8 words", result)

    def test_the_write_target_is_captured_when_asked(self):
        class User:
            def GetForegroundWindow(self):
                return 4321
            def GetWindowThreadProcessId(self, hwnd, pid):
                pid._obj.value = 1
        self.desktop.user = User()
        command = self.actions._with_write_target(write("compose_text", "a note"))
        self.assertEqual(json.loads(command.extra)["hwnd"], 4321)

    def test_terminals_never_receive_line_breaks(self):
        from jarvis import writing
        patch.stopall()
        with patch("jarvis.writing.process_name", return_value="powershell.exe"):
            self.assertEqual(writing.safe_text("echo hi\nrm -r x", 1), "echo hi rm -r x")
        with patch("jarvis.writing.process_name", return_value="notepad.exe"):
            self.assertEqual(writing.safe_text("line one\r\nline two", 1), "line one\nline two")


if __name__ == "__main__":
    unittest.main()
