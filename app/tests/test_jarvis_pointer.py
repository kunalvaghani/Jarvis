"""Jarvis's own physical pointer, and cancelling a specific queued task by description."""
import ctypes
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jarvis.commands import Command, parse


class FakeUser:
    """user32 stand-in recording touch taps and pointer moves."""
    def __init__(self, positions=None, held=False):
        self.positions = list(positions or [(500, 400)])
        self.held = held
        self.calls = []

    def GetCursorPos(self, point):
        x, y = self.positions[0] if len(self.positions) == 1 else self.positions.pop(0)
        point._obj.x, point._obj.y = x, y
        return 1

    def GetAsyncKeyState(self, key):
        return 0x8000 if self.held else 0

    def InitializeTouchInjection(self, count, mode):
        self.calls.append(('init', count, mode)); return 1

    def InjectTouchInput(self, count, info):
        info = info._obj
        self.calls.append(('touch', info.pointerInfo.pointerFlags, info.pointerInfo.ptPixelLocation.x,
                           info.pointerInfo.ptPixelLocation.y, info.pressure)); return 1

    def SetCursorPos(self, x, y):
        self.calls.append(('restore', x, y)); return 1

    def mouse_event(self, *args):
        self.calls.append(('nudge',) + args[:2])

    def SetThreadDpiAwarenessContext(self, value):
        return 1


class PointerTests(unittest.TestCase):
    def setUp(self):
        import jarvis.jarvis_pointer as pointer
        pointer._initialized[0] = False

    def test_tap_is_one_touch_down_and_up_then_the_mouse_returns(self):
        from jarvis.jarvis_pointer import tap, FLAG_DOWN, FLAG_UP
        user = FakeUser()
        self.assertTrue(tap(120, 340, user=user, sleep=lambda s: None))
        touches = [call for call in user.calls if call[0] == 'touch']
        self.assertEqual(touches, [('touch', FLAG_DOWN, 120, 340, 512), ('touch', FLAG_UP, 120, 340, 512)])
        self.assertEqual(user.calls[-1], ('restore', 500, 400))  # The user's pointer is back where it was.
        self.assertIn(('nudge', 1, 1), user.calls)  # Keeps it visible after touch input hid it.

    def test_no_click_while_the_user_holds_a_mouse_button(self):
        from jarvis.jarvis_pointer import tap
        user = FakeUser(held=True)
        clock = iter(i * .1 for i in range(1000))
        with self.assertRaisesRegex(ValueError, 'using the mouse'):
            tap(10, 10, user=user, sleep=lambda s: None, clock=lambda: next(clock))
        self.assertFalse([call for call in user.calls if call[0] == 'touch'])

    def test_pointer_is_first_and_falls_back_before_any_input(self):
        from jarvis.execution_adapters import PRIORITY, JarvisPointer, Unsupported
        self.assertEqual(PRIORITY[0], 'jarvis-pointer')
        provider = JarvisPointer()
        with patch('jarvis.jarvis_pointer.enabled', return_value=True):
            with self.assertRaises(Unsupported):  # Not a live control: accessibility providers take over.
                provider.prepare(Mock(), {'role': 'Button'}, {'operation': 'activate'}, Mock())
            with self.assertRaises(Unsupported):  # Password fields are never tapped.
                provider.prepare(Mock(), {'role': 'Edit', 'password': True}, {'operation': 'activate'}, Mock())
            with self.assertRaises(Unsupported):
                provider.prepare(Mock(), {'role': 'Edit'}, {'operation': 'fill_text'}, Mock())
        with patch('jarvis.jarvis_pointer.enabled', return_value=False):
            with self.assertRaises(Unsupported):
                provider.prepare(Mock(), {'role': 'Button'}, {'operation': 'activate'}, Mock())

    def test_setting_turns_physical_clicks_off(self):
        from jarvis.jarvis_pointer import enabled
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'config').mkdir()
            (Path(tmp) / 'config/config.json').write_text(json.dumps({'cursor': {'physical_clicks': False}}))
            self.assertFalse(enabled(tmp))
            (Path(tmp) / 'config/config.json').write_text('{}')
            self.assertTrue(enabled(tmp))


class CancelParsingTests(unittest.TestCase):
    def test_specific_task_phrases(self):
        cases = {'stop the email task': 'email', 'cancel the youtube one': 'youtube',
                 'never mind the wikipedia search': 'wikipedia search', "don't do the email anymore": 'email',
                 'remove the music request from the queue': 'music', 'remove the second task': 'second',
                 'cancel number 2': '2', 'cancel the last one': 'last', 'never mind': 'last', 'scratch that': 'last',
                 'forget about the video': 'video'}
        for text, value in cases.items():
            self.assertEqual(parse(text), Command('cancel_task', value), text)
        self.assertEqual(parse('cancel everything except the email'), Command('cancel_task', 'email', 'except'))
        self.assertEqual(parse('remove all previous tasks').kind, 'cancel_all')
        self.assertEqual(parse('cancel this task').kind, 'cancel_current')

    def test_real_commands_and_negations_are_untouched(self):
        self.assertEqual(parse('delete the latest email').kind, 'task')
        self.assertEqual(parse('delete file notes.txt').kind, 'delete')
        for text in ("don't open notepad", 'never delete file notes'):
            with self.assertRaisesRegex(ValueError, 'negated'):
                parse(text)


class CancelMatchingTests(unittest.TestCase):
    def setUp(self):
        self.current = Command('task', 'go to wikipedia and open the article about black holes')
        self.pending = [Command('compose_text', 'a short email to the team'), Command('play_media', 'lofi', 'spotify'),
                        Command('task', 'open youtube and search for cats')]

    def test_description_position_and_synonyms(self):
        from jarvis.task_queue import match
        self.assertEqual(match('email', self.current, self.pending), ('one', 1))
        self.assertEqual(match('music', self.current, self.pending), ('one', 2))  # music ~ spotify/play
        self.assertEqual(match('black holes article', self.current, self.pending), ('one', 0))
        self.assertEqual(match('video', self.current, self.pending), ('one', 3))  # video ~ youtube
        self.assertEqual(match('second', self.current, self.pending), ('one', 2))  # Waiting list numbering.
        self.assertEqual(match('2', self.current, self.pending), ('one', 2))
        self.assertEqual(match('last', self.current, self.pending), ('one', 3))
        self.assertEqual(match('current', self.current, self.pending), ('one', 0))

    def test_ties_and_paraphrases(self):
        from jarvis.task_queue import match
        pending = [Command('task', 'search google for cheap flights'), Command('task', 'search google for hotels')]
        self.assertEqual(match('google search', None, pending)[0], 'ambiguous')  # Never guessed.
        self.assertEqual(match('the thing about holidays', None, pending, choose=lambda d, labels: 1), ('one', 1))
        self.assertEqual(match('unrelated', None, pending, choose=lambda d, labels: None), ('none', []))

    def test_actions_remove_only_the_described_task(self):
        from jarvis.actions import Actions
        with tempfile.TemporaryDirectory() as tmp:
            actions = Actions({'files_root': 'files', 'apps': {}}, tmp, lambda *a: None)
            try:
                running = threading.Event()
                actions.current_item = (running, self.current)
                tokens = [threading.Event() for _ in self.pending]
                actions.pending_tasks = list(zip(tokens, self.pending))
                with patch('jarvis.task_queue.model_choice', return_value=lambda d, l: None):
                    self.assertEqual(actions._cancel_task(Command('cancel_task', 'email')),
                                     'Removed a short email to the team from the queue.')
                    self.assertTrue(tokens[0].is_set()); self.assertFalse(running.is_set())
                    self.assertEqual([c for _, c in actions.pending_tasks], self.pending[1:])
                    self.assertIn('Stopped go to wikipedia', actions._cancel_task(Command('cancel_task', 'wikipedia')))
                    self.assertTrue(running.is_set())
                    message = actions._cancel_task(Command('cancel_task', 'cats video', 'except'))
                    self.assertIn('everything except open youtube', message)
                    self.assertEqual([c for _, c in actions.pending_tasks], [self.pending[2]])
                    self.assertTrue(tokens[1].is_set()); self.assertFalse(tokens[2].is_set())
            finally:
                actions.close()

    def test_queue_status_is_numbered_for_spoken_removal(self):
        from jarvis.actions import Actions
        with tempfile.TemporaryDirectory() as tmp:
            actions = Actions({'files_root': 'files', 'apps': {}}, tmp, lambda *a: None)
            try:
                actions.current_item = (threading.Event(), self.current)
                actions.pending_tasks = [(threading.Event(), c) for c in self.pending]
                status = actions._queue_control('queue_status')
                self.assertIn('Waiting: 1, a short email to the team; 2, lofi; 3, open youtube', status)
            finally:
                actions.close()


if __name__ == '__main__':
    unittest.main()
