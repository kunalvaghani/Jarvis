import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.brain import BrainClient
from jarvis.code_stream import CodeDraft, content_prefix, owned_draft
from jarvis.coder import Coder, single_python_target
from jarvis.knowledge_worker import chat


class CodeStreamTests(unittest.TestCase):
    def test_partial_json_escapes_and_unicode_preserve_source(self):
        source = 'print("hello\\nworld")\n# 😀\n'
        raw = json.dumps({'explanation': 'a content-like \\"content\\" label', 'content': source})
        prefixes = [content_prefix(raw[:i]) for i in range(len(raw) + 1)]
        self.assertEqual(content_prefix(raw), source)
        self.assertTrue(all(source.startswith(p) for p in prefixes if p is not None))
        self.assertEqual(content_prefix('{"content":"x\\'), 'x')
        self.assertEqual(content_prefix('{"content":"x\\n'), 'x\n')

    def test_new_draft_updates_and_external_edits_stop_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base / 'alarm.py'
            path.write_text('# draft\n')
            draft = CodeDraft(base, path, path.read_bytes(), True, '# draft\n', lambda: False, Mock())
            draft.write('import time\n')
            self.assertIn('import time', path.read_text())
            self.assertTrue(owned_draft(base, path))
            path.write_text('# user change\n')
            with self.assertRaisesRegex(ValueError, 'changed outside'):
                draft.write('import time\nprint(1)\n')
            self.assertEqual(path.read_text(), '# user change\n')

    def test_existing_script_unchanged_until_valid_commit_and_sidecar_reusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base / 'alarm.py'
            path.write_text('value = 1\n')
            draft = CodeDraft(base, path, path.read_bytes(), False, '# draft\n', lambda: False, Mock())
            draft.write('value = 2\n')
            self.assertEqual(path.read_text(), 'value = 1\n')
            self.assertIn('value = 2', draft.path.read_text())
            draft.complete()
            again = CodeDraft(base, path, path.read_bytes(), False, '# draft\n', lambda: False, Mock())
            again.write('value = 3\n')
            self.assertIn('value = 3', again.path.read_text())

    def test_cancel_prevents_progress_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'alarm.py'
            draft = CodeDraft(Path(tmp), path, None, True, '# draft\n', lambda: True, Mock())
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                draft.write('import time\n')
            self.assertFalse(path.exists())

    def test_streamed_http_response_must_complete_and_respects_non_thinking_coder(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_lines.return_value = iter([json.dumps({'response': '{"content":"x'}).encode(), json.dumps({'response': ' = 1"}', 'done': True}).encode()])
        client = Mock()
        client.post.return_value = response
        callback = Mock()
        options = {'model': 'Qwen3-Coder:latest', 'prompt_format': 'qwen_chatml', 'stream': True,
            'on_chunk': callback, 'non_thinking_coder': True, 'timeout_seconds': 900}
        result = chat(client, options, [{'role': 'user', 'content': 'Generate source'}], structured=True)
        self.assertEqual(json.loads(result)['content'], 'x = 1')
        self.assertEqual(callback.call_count, 2)
        self.assertNotIn('<think>', client.post.call_args.kwargs['json']['prompt'])
        self.assertTrue(client.post.call_args.kwargs['stream'])
        response.iter_lines.return_value = iter([b'{"response":"partial"}'])
        with self.assertRaisesRegex(ValueError, 'before completion'):
            chat(client, options, [], structured=True)
        response.iter_lines.return_value = iter([b'{"response":"{}","done":true,"done_reason":"length"}'])
        with self.assertRaisesRegex(ValueError, 'answer limit'):
            chat(client, options, [], structured=True)

    def test_worker_progress_callback_is_not_serialized_and_disk_failure_not_retried(self):
        client = BrainClient(Path('.'), {})
        client.process = SimpleNamespace(poll=lambda: None, stdin=Mock())
        client.responses = queue.Queue()
        client.responses.put(json.dumps({'progress': {'content': 'x = 1'}}))
        client.responses.put(json.dumps({'result': {'content': 'x = 1'}}))
        callback = Mock()
        result = client._request_once('code_edit', lambda: False, _on_code=callback)
        callback.assert_called_once_with('x = 1')
        self.assertTrue(json.loads(client.process.stdin.write.call_args.args[0])['stream_content'])
        self.assertEqual(result['content'], 'x = 1')
        client._request_once = Mock(side_effect=OSError('worker gone'))
        with self.assertRaises(OSError):
            client.request('code_edit', lambda: False, _on_code=callback)
        self.assertEqual(client._request_once.call_count, 1)

    def test_clear_single_alarm_target_skips_plan_and_validates_streamed_file(self):
        goal = 'create a python script for alarm in test codes folder'
        self.assertEqual(single_python_target(goal), 'alarm.py')
        self.assertIsNone(single_python_target('Create a tools folder and a Python script in TestCodes folder'))
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'TestCodes'
            project.mkdir()
            actions, client = Mock(), Mock()
            content = 'def alarm():\n    return "alarm"\n'
            def answer(operation, *_args, **kwargs):
                self.assertEqual(operation, 'code_edit')
                kwargs['_on_code']('def alarm():\n')
                self.assertIn('def alarm', (project / 'alarm.py').read_text())
                kwargs['_on_code'](content)
                return {'content': content}
            client.request.side_effect = answer
            result = Coder(actions, client).run(project, goal, selected=True)
            self.assertIn('alarm.py', result)
            self.assertEqual((project / 'alarm.py').read_text(), content)
            self.assertEqual(client.request.call_count, 1)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                Coder(actions, client).run(project, goal, selected=True)

    def test_failed_streamed_edit_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            path = project / 'alarm.py'
            original = 'def alarm():\n    return 1\n'
            path.write_text(original)
            client = Mock()
            def answer(operation, *_args, **kwargs):
                kwargs['_on_code']('def alarm(:')
                return {'content': 'def alarm(:'}
            client.request.side_effect = answer
            with self.assertRaisesRegex(ValueError, 'syntax'):
                Coder(Mock(), client).run(project, 'Modify alarm.py to return 2', selected=True)
            self.assertEqual(path.read_text(), original)
            self.assertTrue(path.with_name('alarm.py.jarvis-draft').is_file())


if __name__ == '__main__':
    unittest.main()
