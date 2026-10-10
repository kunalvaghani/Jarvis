"""Push-to-write: hold Left Ctrl + Left Alt to type speech at the cursor."""
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis.push_to_write import PushToWrite, VK_LCONTROL, VK_LMENU


def wait(predicate, seconds=1.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not predicate():
        time.sleep(.01)
    return predicate()


class KeyStateTests(unittest.TestCase):
    def setUp(self):
        self.changes, self.sent = [], []
        self.keys = PushToWrite(lambda active, discard: self.changes.append((active, discard)), hold_seconds=.05,
                                send=lambda: self.sent.append('mask+alt-up'))
        self.addCleanup(self.keys.closed.set)

    def test_holding_both_keys_starts_and_releasing_stops_writing(self):
        self.keys.key(VK_LCONTROL, True)
        self.keys.key(VK_LMENU, True)
        self.assertTrue(wait(self.keys.active.is_set))
        session = self.keys.session
        self.assertTrue(self.keys.key(VK_LMENU, False))  # Real Alt release is replaced ...
        self.assertEqual(self.sent, ['mask+alt-up'])  # ... by mask key + Alt release.
        self.assertFalse(self.keys.active.is_set())
        self.keys.key(VK_LCONTROL, False)
        self.assertEqual(self.changes, [(True, False), (False, False)])
        self.keys.key(VK_LCONTROL, True); self.keys.key(VK_LMENU, True)
        self.assertTrue(wait(self.keys.active.is_set))
        self.assertEqual(self.keys.session, session + 1)  # Each hold is a new session.

    def test_shortcut_with_another_key_never_activates(self):
        self.keys.key(VK_LCONTROL, True)
        self.keys.key(VK_LMENU, True)
        self.keys.key(0x2E, True)  # Ctrl+Alt+Delete
        time.sleep(.12)
        self.assertFalse(self.keys.active.is_set())
        self.assertFalse(self.keys.key(VK_LMENU, False))  # Nothing masked or blocked.
        self.assertEqual(self.sent, [])

    def test_other_key_during_writing_cancels_and_discards(self):
        self.keys.key(VK_LCONTROL, True); self.keys.key(VK_LMENU, True)
        self.assertTrue(wait(self.keys.active.is_set))
        self.keys.key(0x56, True)  # Ctrl+Alt+V
        self.assertFalse(self.keys.active.is_set())
        self.assertEqual(self.changes[-1], (False, True))
        self.assertIn(self.keys.session, self.keys.discarded)  # Its half-spoken phrase is dropped.

    def test_quick_tap_does_not_activate_and_injected_keys_are_ignored(self):
        self.keys.key(VK_LCONTROL, True); self.keys.key(VK_LMENU, True)
        self.keys.key(VK_LMENU, False); self.keys.key(VK_LCONTROL, False)
        time.sleep(.12)
        self.assertFalse(self.keys.active.is_set())
        self.assertFalse(self.keys.key(VK_LMENU, False, injected=True))
        self.assertFalse(self.keys.key(0x41, True, injected=True))  # Jarvis's own typing.

    def test_right_alt_altgr_is_not_the_hotkey(self):
        self.keys.key(VK_LCONTROL, True)
        self.keys.key(0xA5, True)  # Right Alt (AltGr sends Left Ctrl + Right Alt)
        time.sleep(.12)
        self.assertFalse(self.keys.active.is_set())


class ListenerRoutingTests(unittest.TestCase):
    def run_jobs(self, jobs):
        from jarvis.audio import Listener, DecodeJob
        engine, written = Mock(), []
        listener = Listener('model', None, engine, lambda *a: None, writer=lambda text, session: written.append((text, session)))
        words = [(0.5, ' Hello,'), (0.9, ' world.')]
        for job in jobs:
            listener.jobs.put(DecodeJob(*job[0], **job[1]))
        class Model:
            def transcribe(self, audio, **kwargs):
                segment = SimpleNamespace(avg_logprob=-0.2, words=[SimpleNamespace(end=end, word=word) for end, word in words])
                if listener.jobs.items == type(listener.jobs.items)():
                    threading.Timer(.05, listener.stop_event.set).start()
                return [segment], None
        listener._decode(Model())
        return engine, written

    def test_held_speech_is_typed_with_case_and_never_reaches_commands(self):
        engine, written = self.run_jobs([((1, 0.0, b''), {'final': True, 'write': True, 'session': 3})])
        self.assertEqual(written, [('Hello, world.', 3)])
        engine.feed.assert_not_called()

    def test_normal_speech_still_goes_to_the_command_engine(self):
        engine, written = self.run_jobs([((1, 0.0, b''), {'final': True})])
        self.assertEqual(written, [])
        engine.feed.assert_called_once()
        self.assertEqual(engine.feed.call_args.kwargs['raw'], 'Hello, world.')


class SpokenWriterTests(unittest.TestCase):
    def test_phrases_follow_the_cursor_with_spacing_and_spoken_new_lines(self):
        from jarvis.writing import SpokenWriter
        typed = []
        class Desktop:
            target = None
            def capture(self):
                self.target = 'editor'
            def type(self, text, cancelled):
                typed.append((self.target, text))
        writer = SpokenWriter(desktop=Desktop())
        self.addCleanup(writer.close)
        from unittest.mock import patch
        with patch('jarvis.writing.safe_text', side_effect=lambda text, hwnd: text):
            writer('Hello there.', 1)
            writer('How are you? New line. Thanks', 1)
            writer('Fresh start', 2)
            self.assertTrue(wait(lambda: len(typed) == 3))
        self.assertEqual(typed, [('editor', 'Hello there.'), ('editor', ' How are you?\nThanks'), ('editor', 'Fresh start')])


if __name__ == '__main__':
    unittest.main()
