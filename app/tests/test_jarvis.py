from pathlib import Path
import tempfile
import threading
import unittest

from jarvis.commands import Command, filename, parse
from jarvis.engine import Engine
from jarvis.actions import Actions, Desktop

NOTEPAD = '{"target": "notepad", "tail": ""}'
NONE = '{"target": "", "tail": ""}'


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.sent, self.events = [], []
        self.engine = Engine(self.sent.append, lambda *event: self.events.append(event))

    def feed(self, text, final=False, now=10):
        self.engine.feed(text, final, now)

    def test_requires_wake_word(self):
        self.feed("open notepad", True)
        self.assertEqual(self.sent, [])
        self.feed("hey jarvis open notepad", True)
        self.assertEqual(self.sent, [Command("open", "notepad")])

    def test_manual_activation_accepts_plain_open_notepad(self):
        self.engine.activate(now=10)
        self.feed("open notepad", True, now=11)
        self.assertEqual(self.sent, [Command("open", "notepad")])

    def test_sleep_after_manual_activation_requires_wake_word(self):
        self.engine.activate(now=10)
        self.feed("go to sleep", True, now=11)
        self.feed("open notepad", True, now=12)
        self.assertEqual(self.sent, [Command("end_conversation")])  # Ends listening; queued tasks continue.
        self.assertTrue(any(kind == "ignored" for kind, _ in self.events))
        self.feed("jarvis open notepad", True, now=13)
        self.assertEqual(self.sent[-1], Command("open", "notepad"))

    def test_manual_activation_expires_and_explains_ignored_command(self):
        self.engine.activate(now=10)
        self.feed("open notepad", True, now=101)
        self.assertEqual(self.sent, [])
        self.assertTrue(any(kind == "ignored" for kind, _ in self.events))

    def test_mid_speech_and_no_duplicates(self):
        self.feed("jarvis open notepad then open")
        self.feed("jarvis open notepad then open calculator")
        self.assertEqual(self.sent, [Command("open", "notepad")])
        self.feed("jarvis open notepad then open calculator", True)
        self.assertEqual(self.sent, [Command("open", "notepad"), Command("open", "calculator")])

    def test_repeated_command_in_new_segment_runs(self):
        self.feed("jarvis open notepad", True)
        self.feed("open notepad", True)
        self.assertEqual(len(self.sent), 2)

    def test_deletion_waits_for_final_and_preserves_order(self):
        self.feed("jarvis delete file old dot txt then open paint then open calculator")
        self.assertEqual(self.sent, [])
        self.feed("jarvis delete file old dot txt then open paint then open calculator", True)
        self.assertEqual([c.kind for c in self.sent], ["delete", "open", "open"])

    def test_corrected_partial_delete_is_not_executed(self):
        self.feed("jarvis delete file notes then open paint")
        self.feed("jarvis do not delete file notes then open paint", True)
        self.assertNotIn("delete", [c.kind for c in self.sent])

    def test_no_partial_open_without_boundary(self):
        self.feed("jarvis open notepad")
        self.assertEqual(self.sent, [])

    def test_write_waits_for_final_speech_and_never_starts_dictation(self):
        self.feed("jarvis write one two three four five")
        self.feed("jarvis write one two three four five six")
        self.assertEqual(self.sent, [])  # Nothing is typed from a revisable partial.
        self.feed("jarvis write one two three four five six", True)
        self.assertEqual(self.sent, [Command("compose_text", "one two three four five six", NONE)])
        self.feed("seven eight", True)  # Plain speech afterwards is not typed.
        self.assertEqual(self.sent[-1], Command("task", "seven eight", "unparsed"))

    def test_dictation_phrases_explain_push_to_write(self):
        self.feed("jarvis start dictation", True)
        self.feed("stop dictation", True)
        self.assertEqual(self.sent, [Command("write_help"), Command("write_help")])

    def test_exact_write_keeps_then_inside_the_text(self):
        self.feed("jarvis write exactly hello then open paint", True)
        self.assertEqual(self.sent, [Command("write_text", "hello then open paint", NONE)])

    def test_open_and_write_in_one_sentence(self):
        self.feed("jarvis open notepad and write exactly my name is kunal", True)
        self.assertEqual(self.sent, [Command("open", "notepad"), Command("write_text", "my name is kunal", NOTEPAD)])

    def test_partial_and_write_does_not_repeat_open_or_write(self):
        self.feed("jarvis open notepad and write my name")
        self.feed("jarvis open notepad and write my name is kunal")
        self.feed("jarvis open notepad and write my name is kunal", True)
        self.assertEqual(sum(c.kind == "open" for c in self.sent), 1)
        self.assertEqual([c for c in self.sent if c.kind == "compose_text"],
                         [Command("compose_text", "my name is kunal", NOTEPAD)])

    def test_and_write_inside_prose_remains_literal(self):
        self.feed("jarvis write exactly i read and write every day", True)
        self.assertEqual(self.sent[-1], Command("write_text", "i read and write every day", NONE))

    def test_and_write_across_recognizer_endpoints(self):
        self.feed("jarvis open notepad", True)
        self.feed("and write exactly my name is kunal", True)
        self.assertEqual(self.sent, [Command("open", "notepad"), Command("write_text", "my name is kunal", NOTEPAD)])

    def test_original_case_and_punctuation_reach_exact_writes(self):
        raw = "Jarvis, write exactly Hello, World! See you at 5 PM."
        self.engine.feed("jarvis write exactly hello world see you at 5 pm", final=True, raw=raw)
        self.assertEqual(self.sent[-1].value, "Hello, World! See you at 5 PM.")

    def test_sleep_suppresses_remainder(self):
        self.feed("jarvis go to sleep then open paint", True)
        self.assertEqual(self.sent, [Command("end_conversation")])  # Ends listening; queued tasks continue.
        self.feed("open paint", True)
        self.assertEqual(len(self.sent), 1)

    def test_timeout(self):
        self.feed("jarvis", True, now=10)
        self.feed("open paint", True, now=101)
        self.assertEqual(self.sent, [])

    def test_changed_already_sent_clause_suppresses_followup(self):
        self.feed("jarvis open notepad then open")
        self.feed("jarvis open paint then open calculator", True)
        self.assertEqual(self.sent, [Command("open", "notepad")])


class CommandTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse("please create a file called notes dot txt containing hello there"), Command("create", "notes.txt", "hello there"))
        self.assertEqual(parse("rename file notes to ideas"), Command("rename", "notes.txt", "ideas.txt"))

    def test_no_implied_or_negated_deletion(self):
        for text in ["do not delete file notes", "don't delete file notes", "maybe delete file notes", "I talked about delete file notes", "remove everything", "delete all files"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse(text)

    def test_reject_paths(self):
        for name in ["../outside", "C:\\secret", "notes/../../secret", "*", "CON.txt", "notes:secret", ".hidden"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                filename(name)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.recycled = []
        self.actions = Actions({"files_root": "files", "apps": {}}, self.temp.name, lambda *x: None, recycler=self.recycled.append)

    def test_create_rename_recycle(self):
        self.actions.execute(Command("create", "notes.txt", "hello"))
        self.assertEqual((self.actions.root / "notes.txt").read_text(), "hello")
        self.actions.execute(Command("rename", "notes.txt", "ideas.txt"))
        self.assertFalse((self.actions.root / "notes.txt").exists())
        self.actions.approval_handler = lambda kind, detail, cancelled: kind == "delete" and detail.endswith("ideas.txt")
        self.actions.execute(Command("delete", "ideas.txt"))
        self.assertEqual(self.recycled, [str(self.actions.root / "ideas.txt")])

    def test_command_parsing_for_jarvis_console_and_file_edit(self):
        self.assertEqual(parse("open Jarvis command prompt"), Command("show_command_prompt"))
        self.assertEqual(parse("run command dir"), Command("run_command", "dir"))
        self.assertEqual(parse("modify file notes dot txt replace old with new"),
            Command("modify", "notes.txt", '{"find": "old", "content": "new"}'))
        self.assertEqual(parse("create a file called notes .txt"), Command("create", "notes.txt", ""))
        for utterance in ("delete file old.txt in Downloads", "Modify file notes.txt in Documents: replace old with new",
                          "Overwrite file notes.txt in Documents with content Hello."):
            self.assertEqual(parse(utterance), Command("task", utterance))

    def test_delete_requires_approval(self):
        self.actions.execute(Command("create", "keep.txt", "important"))
        with self.assertRaisesRegex(ValueError, "approve"):
            self.actions.execute(Command("delete", "keep.txt"))
        self.actions.approval_handler = lambda *_: False
        with self.assertRaisesRegex(ValueError, "approval was not given"):
            self.actions.execute(Command("delete", "keep.txt"))
        self.assertEqual((self.actions.root / "keep.txt").read_text(), "important")
        self.assertEqual(self.recycled, [])

    def test_modify_replaces_only_one_exact_match(self):
        self.actions.execute(Command("create", "notes.txt", "old line\nkeep line"))
        payload = '{"find":"old line","content":"new line"}'
        self.actions.execute(Command("modify", "notes.txt", payload))
        self.assertEqual((self.actions.root / "notes.txt").read_text(), "new line\nkeep line")
        with self.assertRaisesRegex(ValueError, "exactly once"):
            self.actions.execute(Command("modify", "notes.txt", payload))
        self.assertEqual((self.actions.root / "notes.txt").read_text(), "new line\nkeep line")

    def test_modify_preserves_windows_line_endings(self):
        path = self.actions.root / "windows.txt"
        path.write_bytes(b"first\r\nold\r\nlast\r\n")
        self.actions.execute(Command("modify", "windows.txt", '{"find":"old","content":"new"}'))
        self.assertEqual(path.read_bytes(), b"first\r\nnew\r\nlast\r\n")

    def test_command_prompt_needs_separate_approval_and_returns_output(self):
        events = []
        self.actions.report = lambda kind, message: events.append((kind, message))
        with self.assertRaisesRegex(ValueError, "approve"):
            self.actions.execute(Command("run_command", "echo hello"))
        self.actions.approval_handler = lambda kind, detail, cancelled: kind == "command" and detail == "echo hello"
        result = self.actions.execute(Command("run_command", "echo hello"))
        self.assertIn("exit code 0", result)
        self.assertTrue(any(kind == "command_output" and "hello" in message for kind, message in events))

    def test_no_overwrite(self):
        self.actions.execute(Command("create", "a.txt", "original"))
        with self.assertRaises(FileExistsError):
            self.actions.execute(Command("create", "a.txt", "replacement"))
        self.actions.execute(Command("create", "b.txt"))
        with self.assertRaises(ValueError):
            self.actions.execute(Command("rename", "a.txt", "b.txt"))
        self.assertEqual((self.actions.root / "a.txt").read_text(), "original")

    def test_executor_rejects_escape_and_directories(self):
        with self.assertRaises(ValueError):
            self.actions.execute(Command("create", "../escape.txt"))
        (self.actions.root / "folder.txt").mkdir()
        with self.assertRaises(ValueError):
            self.actions.execute(Command("delete", "folder.txt"))

    def test_cancellation_discards_queued_work(self):
        self.actions.submit(Command("create", "a.txt"))
        self.actions.cancel()
        self.actions.start()
        self.actions.queue.join()
        self.actions.close()
        self.actions.thread.join(2)
        self.assertFalse((self.actions.root / "a.txt").exists())

    def test_action_worker_does_not_block_input(self):
        entered, release = threading.Event(), threading.Event()
        original = self.actions.execute
        def slow(command, cancelled):
            entered.set()
            release.wait(2)
            return original(command, cancelled)
        self.actions.execute = slow
        self.actions.start()
        engine = Engine(self.actions.submit, lambda *args: None)
        engine.feed("jarvis create file a", True)
        self.assertTrue(entered.wait(1))
        engine.feed("create file b", True)
        self.assertEqual(self.actions.queue.qsize(), 1)
        release.set()
        self.actions.queue.join()
        self.actions.close()
        self.actions.thread.join(2)
        self.assertTrue((self.actions.root / "b.txt").exists())


class TypingTests(unittest.TestCase):
    class FakeUser:
        def __init__(self):
            self.focus = 42
            self.sent = 0
            self.result = 2
            self.corner = False

        def GetForegroundWindow(self):
            return self.focus

        def GetCursorPos(self, point):
            point._obj.x = point._obj.y = 0 if self.corner else 100
            return True

        def GetSystemMetrics(self, index):
            return 1000

        def SendInput(self, count, inputs, size):
            self.sent += count
            return self.result

    def setUp(self):
        self.desktop = object.__new__(Desktop)
        self.desktop.user = self.FakeUser()
        self.desktop.target = 42

    def test_unicode_typing_uses_down_up_pairs(self):
        self.desktop.type("a\u0915", lambda: False)
        self.assertEqual(self.desktop.user.sent, 4)

    def test_changed_window_stops_typing(self):
        self.desktop.user.focus = 43
        with self.assertRaises(ValueError):
            self.desktop.type("hello", lambda: False)
        self.assertEqual(self.desktop.user.sent, 0)

    def test_cancelled_typing_sends_nothing(self):
        self.desktop.type("hello", lambda: True)
        self.assertEqual(self.desktop.user.sent, 0)

    def test_pointer_corner_stops_typing(self):
        self.desktop.user.corner = True
        with self.assertRaises(ValueError):
            self.desktop.type("hello", lambda: False)
        self.assertEqual(self.desktop.user.sent, 0)

    def test_windows_rejection_is_reported(self):
        self.desktop.user.result = 0
        with self.assertRaises(RuntimeError):
            self.desktop.type("hello", lambda: False)


if __name__ == "__main__":
    unittest.main()
