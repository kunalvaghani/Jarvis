from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.actions import Actions
from jarvis.audio import DecodeJob, Listener
from jarvis.code_stream import CodeDraft
from jarvis.commands import Command
from jarvis.display import window_scale
from jarvis.engine import Engine
from jarvis.island import Activity, render_island
from jarvis.progress import status
from jarvis.speech import Speech
from jarvis.task_state import TaskState
from jarvis.voice_input import VoiceInput


class DuplexDisplayTests(unittest.TestCase):
    def speech(self, content='Your file is ready. I am explaining its result.'):
        speech = Speech({'enabled': True}, Mock())
        speech.process = Mock()
        speech.process.poll.return_value = None
        speech._begin_output(content)
        return speech

    def test_native_resolution_and_transparency_survive_scaling(self):
        image = render_island(580, 64, 'WORKING', detail='Generating alarm.py', scale=2)
        self.assertEqual(image.size, (1160, 128))
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 255))
        self.assertNotEqual(image.getpixel((600, 64)), (255, 0, 255))
        no_detail = render_island(580, 64, 'WORKING', scale=2)
        self.assertEqual(image.crop((1010, 0, 1160, 128)).tobytes(), no_detail.crop((1010, 0, 1160, 128)).tobytes())

    def test_window_dpi_is_used_and_mock_handles_do_not_reach_winapi(self):
        user = Mock()
        user.GetDpiForWindow.return_value = 192
        with patch('jarvis.display.ctypes.WinDLL', return_value=user):
            self.assertEqual(window_scale(SimpleNamespace(winfo_id=lambda: 42)), 2.)
            self.assertEqual(window_scale(Mock()), 1.)
            user.GetDpiForWindow.assert_called_once_with(42)

    def test_activity_shows_file_and_speech_then_expires(self):
        activity = Activity()
        activity.notify('task_status', {'phase': 'Generating code', 'target': r'D:\project\alarm.py'}, now=10)
        self.assertEqual(activity.caption('WORKING', now=20, speaking=True), 'Generating code · alarm.py · Speaking')
        activity.notify('task_status', {'phase': 'Ready', 'active': False}, now=20)
        self.assertEqual(activity.caption('LISTENING', now=21), 'Ready')
        self.assertEqual(activity.caption('LISTENING', now=28), 'Ready for a command')
        self.assertIn('Jarvis', activity.caption('SPEAKING', now=28, listening=True))

    def test_progress_never_stops_a_write_if_display_delivery_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.py'
            events = []
            def report(kind, value):
                if kind == 'task_status':
                    events.append(value)
                    raise RuntimeError('UI unavailable')
            stream = CodeDraft(tmp, path, None, True, '# draft\n', lambda: False, report)
            stream.write('print(1)\n')
            self.assertEqual(path.read_text(), '# draft\nprint(1)\n')
            self.assertEqual(events[0]['phase'], 'Generating code')
            self.assertIn('chars', events[-1]['phase'])
            self.assertEqual(events[-1]['target'], str(path))

    def test_output_echo_and_unaddressed_commands_are_not_executed(self):
        speech = self.speech('You can say Jarvis open notepad when you need an editor.')
        gate = VoiceInput(speech)
        self.assertIsNone(gate.filter('You can say Jarvis open Notepad when you need an editor.'))
        self.assertIsNone(gate.filter('open calculator'))
        speech.process.kill.assert_not_called()

    def test_user_wake_interrupts_voice_and_clears_queued_replies(self):
        speech = self.speech()
        speech.say('Old queued answer')
        gate = VoiceInput(speech)
        self.assertEqual(gate.filter('Previous speaker words. Hey Jarvis, open calculator.'), 'jarvis open calculator')
        speech.process.kill.assert_called_once()
        self.assertFalse(speech.speaking.is_set())
        self.assertTrue(speech.output_recent())
        self.assertTrue(speech.queue.empty())

    def test_capture_before_output_is_not_rejected_when_decoding_during_output(self):
        gate = VoiceInput(self.speech())
        self.assertEqual(gate.filter('open calculator', playback=False), 'open calculator')

    def test_captured_reference_filters_delayed_echo_after_new_answers(self):
        speech = self.speech('A different current reply')
        speech._end_output()
        speech.output_until = 0
        gate = VoiceInput(speech)
        self.assertIsNone(gate.filter('Jarvis open notepad', playback=True,
                                     references=('You can say Jarvis open notepad',)))
        speech.process.kill.assert_not_called()

    def test_partial_barge_in_then_final_dispatches_once_without_stopping_capture(self):
        speech = self.speech('You can say Jarvis open notepad when you need an editor.')
        gate, sent = VoiceInput(speech), []
        engine = Engine(sent.append, Mock())
        listener = Listener('unused', None, engine, Mock(), playback=speech.output_recent,
                            input_filter=gate.filter, references=speech.output_references)
        self.assertFalse(listener.muted())
        references = speech.output_references()
        segments = ['You can say Jarvis open notepad when you need an editor',
                    'Jarvis open calculator', 'Jarvis open calculator']
        class Model:
            def transcribe(self, audio, **kwargs):
                text = segments[audio]
                return iter([SimpleNamespace(avg_logprob=0, words=[SimpleNamespace(end=1, word=text)])]), None
        listener.jobs.put(DecodeJob(1, 0, 0, final=True, playback=True, references=references))
        listener.jobs.put(DecodeJob(2, 0, 1, playback=True, references=references))
        listener.jobs.put(DecodeJob(2, 0, 2, final=True, playback=True, references=references))
        worker = threading.Thread(target=listener._decode, args=(Model(),))
        worker.start()
        deadline = time.monotonic()+2
        while not sent and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertFalse(listener.stop_event.is_set())
        listener.stop()
        worker.join(2)
        self.assertEqual(sent, [Command('open', 'calculator')])
        speech.process.kill.assert_called_once()

    def test_stop_discards_late_decoding_without_interrupt_or_dispatch(self):
        speech = self.speech()
        gate, sent = VoiceInput(speech), []
        listener = Listener('unused', None, Engine(sent.append, Mock()), Mock(), input_filter=gate.filter)
        class Model:
            def transcribe(self, audio, **kwargs):
                listener.stop()
                return iter([SimpleNamespace(avg_logprob=0, words=[SimpleNamespace(end=1, word='Jarvis open calculator')])]), None
        listener.jobs.put(DecodeJob(1, 0, None, final=True, playback=True))
        listener._decode(Model())
        self.assertEqual(sent, [])
        speech.process.kill.assert_not_called()

    def test_question_does_not_supersede_running_task_but_new_task_does(self):
        with tempfile.TemporaryDirectory() as tmp:
            actions = Actions({'files_root': 'files', 'apps': {}}, tmp, Mock())
            actions.task_active = True
            actions.knowledge.submit = Mock()
            try:
                actions.submit(Command('ask', 'what time is it'))
                self.assertEqual(actions.generation, 0)
                self.assertFalse(actions.superseded_generations)
                actions.knowledge.submit.assert_called_once_with('what time is it', False)
                actions.submit(Command('task', 'open calculator'))
                self.assertEqual(actions.generation, 1)
                self.assertIn(0, actions.superseded_generations)
            finally:
                actions.close()

    def test_hidden_ui_verification_cannot_rewrite_running_task_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = TaskState(tmp)
            original.start('A live task', 'task')
            before = original.path.read_bytes()
            check = TaskState(tmp, read_only=True)
            check.start('A UI verification task', 'task')
            check.finish('completed', 'checked')
            self.assertEqual(original.path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
