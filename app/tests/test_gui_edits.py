import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis import gui_contract
from jarvis.brain import BrainClient
from jarvis.brain_worker import Models
from jarvis.code_stream import CodeDraft
from jarvis.coder import Coder, calculator_template
from jarvis.inference_limits import coding_limits
from jarvis.task_state import TaskState
from tests.test_coder import UI_SOURCE


class GuiEditTests(unittest.TestCase):
    def test_console_and_uncalled_placeholder_are_rejected(self):
        for source in ('print("UI")', 'def launch_ui():\n    pass\n',
                       UI_SOURCE.split('if __name__')[0], 'if False:\n' + '\n'.join('    ' + line for line in UI_SOURCE.splitlines())):
            with self.subTest(source=source[:40]), self.assertRaisesRegex(ValueError, 'graphical UI'):
                gui_contract.check(source, 'add UI again')
        gui_contract.check(UI_SOURCE, 'add UI')
        gui_contract.check(UI_SOURCE.replace('import tkinter as tk', 'from tkinter import *').replace('tk.', ''), 'add UI')
        gui_contract.check('''import tkinter as tk
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        button = tk.Button(self, text="Go")
        button['command'] = lambda: tk.Label(self, text="Done").pack()
        button.pack()
if __name__ == "__main__":
    App().mainloop()
''', 'add UI')
        with self.assertRaises(ValueError):
            gui_contract.check(UI_SOURCE.replace('command=lambda: tk.Label(root, text="Done").pack()', 'command=lambda: None'), 'add UI')
        gui_contract.check('print("console")', 'add terminal UI')
        self.assertIsNone(calculator_template('create calculator with UI', 'calculator.py'))
        self.assertTrue(gui_contract.requested('there was no UI in calculator.py rebuild the plan and add UI to calculator.py'))
        self.assertFalse(gui_contract.requested('do not add UI to calculator.py'))

    def test_add_ui_skips_plan_rejects_console_repairs_and_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / 'calculator.py'
            original = 'def calculate(a, b):\n    return a + b\n'
            file.write_text(original)
            before = file.read_bytes().decode('utf-8')
            client, actions = Mock(), Mock()
            replies = [original, original + UI_SOURCE]
            def generate(operation, cancelled, **data):
                self.assertEqual(operation, 'code_edit')
                self.assertEqual(data['current'], before)
                self.assertIn('Tkinter', data['gui_requirements'])
                self.assertEqual(file.read_bytes().decode('utf-8'), before)
                data['_on_code'](replies[0])
                return {'content': replies.pop(0)}
            client.request.side_effect = generate
            Coder(actions, client).run(root, 'add UI to calculator .py', selected=True)
            self.assertEqual(client.request.call_count, 2)
            self.assertIn('graphical UI', client.request.call_args.kwargs['validation_error'])
            self.assertIn('root.mainloop()', file.read_text())

    def test_invalid_replies_stop_after_three_and_preserve_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'script.py'
            file.write_bytes(b'value = 1\r\n')
            client = Mock()
            client.request.return_value = {'content': 'value = 2\n'}
            with self.assertRaisesRegex(ValueError, 'graphical UI'):
                Coder(Mock(), client).run(Path(tmp), 'add UI to script.py', selected=True)
            self.assertEqual(file.read_bytes(), b'value = 1\r\n')
            self.assertEqual(client.request.call_count, 3)

    def test_followup_uses_recent_project_target_and_asks_if_ambiguous(self):
        from jarvis.clarification import TaskClarification
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('one.py', 'two.py'):
                (root / name).write_text('value = 1\n')
            actions, client = Mock(), Mock()
            client.request.return_value = {'content': 'value = 1\n' + UI_SOURCE}
            with self.assertRaises(TaskClarification):
                Coder(actions, client).run(root, 'add UI again', selected=True)
            client.request.assert_not_called()
            state = actions.task_state = TaskState(root)
            state.start('modify one.py', 'task', root)
            state.checkpoint('wrote_file', target=root / 'one.py')
            state.finish('completed', 'saved')
            state.start('add UI again', 'task', root)
            Coder(actions, client).run(root, 'add UI again', selected=True)
            self.assertEqual(client.request.call_args.kwargs['path'], 'one.py')
            self.assertEqual((root / 'two.py').read_text(), 'value = 1\n')

    def test_locked_preview_does_not_abort_generation_or_replay_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / 'script.py'
            file.write_text('value = 1\n')
            report = Mock()
            draft = CodeDraft(root, file, file.read_bytes(), False, '# draft\n', lambda: False, report)
            with patch('jarvis.code_stream.os.link', side_effect=PermissionError('fixture lock')) as write:
                draft.write('value = 2\n')
                draft.write('value = 3\n')
                write.assert_called_once()
            self.assertTrue(draft.preview_only)
            self.assertEqual(file.read_text(), 'value = 1\n')
            self.assertTrue(any(call.args[0] == 'warning' for call in report.call_args_list))

    def test_external_script_edit_while_generating_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'script.py'
            file.write_text('value = 1\n')
            client = Mock()
            def generate(*args, **kwargs):
                file.write_text('value = 99\n')
                return {'content': 'value = 1\n' + UI_SOURCE}
            client.request.side_effect = generate
            with self.assertRaisesRegex(ValueError, 'changed while'):
                Coder(Mock(), client).run(file.parent, 'add UI to script.py', selected=True)
            self.assertEqual(file.read_text(), 'value = 99\n')

    def test_coding_deadlines_bound_silence_and_total_and_reject_nonfinite(self):
        self.assertEqual(coding_limits({}), (900, 1800))
        self.assertEqual(coding_limits({'coding_timeout_seconds': 20, 'max_coding_seconds': 100}), (20, 100))
        for value in (True, None, 'never', float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                coding_limits({'max_coding_seconds': value})

    def test_silent_model_times_out_and_shutdown_cancels_without_writes(self):
        client = BrainClient(Path('.'), {'coding_timeout_seconds': 5})
        client.process = SimpleNamespace(poll=lambda: None, stdin=Mock())
        client.close = Mock()
        client.responses = queue.Queue()
        with patch('jarvis.brain.time.monotonic', side_effect=[0, 0, 36]):
            with self.assertRaisesRegex(ValueError, 'coding time limit'):
                client._request_once('code_edit', lambda: False, _on_code=Mock())
        client.close.assert_called_once()
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'script.py'
            file.write_text('value = 1\n')
            draft = CodeDraft(Path(tmp), file, file.read_bytes(), False, '# draft\n', lambda: True, Mock())
            draft.preview_only = True
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                draft.write('value = 2\n')
            self.assertEqual(file.read_text(), 'value = 1\n')

    def test_final_script_lock_stops_without_replaying_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'script.py'
            file.write_text('value = 1\n')
            client = Mock()
            client.request.return_value = {'content': 'value = 1\n' + UI_SOURCE}
            with patch('jarvis.coder.os.replace', side_effect=PermissionError('script locked')) as replace:
                with self.assertRaises(PermissionError):
                    Coder(Mock(), client).run(file.parent, 'add UI to script.py', selected=True)
                replace.assert_called_once()
            self.assertEqual(file.read_text(), 'value = 1\n')

    def test_activity_extends_idle_budget_but_not_total(self):
        for hard_cap, fail in ((300, False), (90, True)):
            client = BrainClient(Path('.'), {'coding_timeout_seconds': 5, 'max_coding_seconds': hard_cap})
            client.process = SimpleNamespace(poll=lambda: None, stdin=Mock())
            client.close = Mock()
            client.responses = queue.Queue()
            for event in ({'coding_activity': 'Thinking'}, {'progress': {'content': 'value = 1'}},
                          {'result': {'content': 'value = 1'}}):
                client.responses.put(json.dumps(event))
            clock = iter([0, 0, 30, 30, 60, 60, 95])
            with patch('jarvis.brain.time.monotonic', side_effect=lambda: next(clock)):
                if fail:
                    with self.assertRaisesRegex(ValueError, 'coding time limit'):
                        client._request_once('code_edit', lambda: False, _on_code=Mock())
                else:
                    self.assertEqual(client._request_once('code_edit', lambda: False, _on_code=Mock())['content'], 'value = 1')
            if fail:
                client.close.assert_called_once()

    def test_worker_passes_exact_current_gui_requirements_and_configured_qwen(self):
        model = Models()
        model.client = Mock()
        original = 'value = 1\r\n'
        request = {'operation': 'code_edit', 'options': {'coder': 'qwen3.5:9b', 'trained_coder_checkpoint': 'fixture'},
                   'path': 'script.py', 'current': original, 'goal': 'add UI', 'use_configured_coder': True,
                   'gui_requirements': gui_contract.instructions('add UI')}
        with patch('jarvis.brain_worker.ensure_server', return_value={'models': [{'name': 'qwen3.5:9b'}]}), \
             patch('jarvis.brain_worker.chat', return_value=json.dumps({'content': UI_SOURCE})) as chat:
            result = model.predict(request)
        payload = json.loads(chat.call_args.args[2][1]['content'].split('\n', 1)[1])
        self.assertEqual(payload['current'], original)
        self.assertEqual(payload['gui_requirements'], request['gui_requirements'])
        self.assertEqual(result['model_used'], 'qwen3.5:9b')
