import json
import queue
import tempfile
import unittest
from unittest.mock import Mock, patch

from jarvis.code_stream import content_prefix
from jarvis.inference_limits import question_limits
from jarvis.knowledge_worker import answer, chat
from jarvis.question_client import QuestionClient
from jarvis.commands import parse
from jarvis.engine import Engine


class AnswerStreamTests(unittest.TestCase):
    def test_code_answer_routes_once_without_splitting_game_name(self):
        question = 'give c++ code for snake and ladder game with working ui'
        self.assertEqual(parse(question).kind, 'ask')
        sent = []
        engine = Engine(sent.append, Mock())
        engine.activate()
        engine.feed(question, final=True)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].value, question)
        self.assertEqual(parse('code in project demo: add a game').kind, 'code_task')

    def client(self, rows):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        client = QuestionClient(directory.name, Mock())
        self.addCleanup(client.close)
        client.process = Mock()
        client.process.poll.return_value = None
        client.responses = queue.Queue()
        for row in rows:
            client.responses.put(None if row is None else json.dumps(row))
        return client

    def test_active_generation_outlives_old_deadline(self):
        client = self.client([{'answer_progress': {'phase': 'Generating answer', 'text': value}}
                              for value in ('a', 'ab', 'abc')] + [{'answer': 'abcd'}])
        client.timeout = 150
        # 430 seconds overall, but never 150 seconds without model activity.
        with patch('jarvis.question_client.time.monotonic', side_effect=[0, 100, 110, 210, 220, 320, 330, 430]):
            result = client.request({'question': 'fixture', 'stream_answer': True,
                                     'options': {'max_answer_seconds': 1000}}, lambda: False)
        self.assertEqual(result['answer'], 'abcd')
        self.assertEqual(client.report.call_count, 3)
        client.process.kill.assert_not_called()

    def test_real_silence_stops_without_retry(self):
        client = self.client([])
        with patch('jarvis.question_client.time.monotonic', side_effect=[0, 331]), patch.object(client, '_start') as start:
            with self.assertRaisesRegex(TimeoutError, 'stopped producing'):
                client.request({'question': 'fixture', 'stream_answer': True}, lambda: False)
        start.assert_called_once()

    def test_progress_does_not_remove_total_ceiling(self):
        client = self.client([{'answer_progress': {'phase': 'Thinking'}}] * 3)
        with patch('jarvis.question_client.time.monotonic', side_effect=[0, 100, 110, 210, 220, 410]):
            with self.assertRaisesRegex(TimeoutError, 'maximum answer duration'):
                client.request({'question': 'fixture', 'stream_answer': True,
                                'options': {'max_answer_seconds': 350}}, lambda: False)

    def test_cancel_after_partial_never_publishes_final(self):
        client = self.client([{'answer_progress': {'phase': 'Generating answer', 'text': 'part'}}, {'answer': 'final'}])
        stop = [False]
        client.report.side_effect = lambda *_: stop.__setitem__(0, True)
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            client.request({'question': 'fixture', 'stream_answer': True}, lambda: stop[0])
        self.assertEqual(client.report.call_count, 1)

    def test_worker_loss_after_progress_does_not_restart_or_mix_answers(self):
        client = self.client([{'answer_progress': {'phase': 'Generating answer', 'text': 'part'}}, None])
        with patch.object(client, '_start') as start:
            with self.assertRaises(BrokenPipeError):
                client.request({'question': 'fixture', 'stream_answer': True}, lambda: False)
        start.assert_called_once()

    def test_invalid_stream_frames_fail_without_display(self):
        for event in ({'phase': 1}, {'phase': 'x', 'text': 1}, {'phase': 'x', 'text': 'a'*100001}):
            client = self.client([{'answer_progress': event}])
            with self.assertRaisesRegex(ValueError, 'Invalid answer stream'):
                client.request({'question': 'fixture', 'stream_answer': True}, lambda: False)
            client.report.assert_not_called()

    def test_prefix_preserves_code_escapes_and_split_unicode(self):
        text = '```cpp\nstd::cout << "Hi";\n``` 😀'
        raw = json.dumps({'needs_web': False, 'answer': text})
        prefixes = [content_prefix(raw[:i], 'answer') for i in range(len(raw)+1)]
        self.assertEqual(prefixes[-1], text)
        self.assertTrue(all(text.startswith(p) for p in prefixes if p is not None))

    def test_preview_uses_answer_field_not_json_envelope(self):
        events = []
        def generate(client, options, messages, **kwargs):
            self.assertTrue(options['stream'])
            options['on_chunk']('{"answer":"Hello\\n')
            options['on_chunk']('world","needs_web":false}')
            return '{"answer":"Hello\\nworld","needs_web":false}'
        with patch('jarvis.knowledge_worker.time.monotonic', side_effect=[1, 2]):
            result = answer({'question': 'fixture', 'stream_answer': True}, chat_fn=generate, progress=events.append)
        self.assertEqual(result['answer'], 'Hello\nworld')
        self.assertEqual(events[-1]['text'], result['answer'])
        self.assertNotIn('needs_web', events[-1]['text'])

    def test_code_example_streams_plain_source_without_action_tools(self):
        events = []
        source = '```cpp\n#include <iostream>\nint main() {}\n```'
        def generate(client, options, messages, **kwargs):
            self.assertNotIn('structured', kwargs)
            self.assertNotIn('format_schema', options)
            self.assertNotIn('tools', options)
            options['on_chunk'](source)
            return source
        with patch('jarvis.knowledge_worker.time.monotonic', return_value=1):
            result = answer({'question': 'give c++ code for snake and ladder game with working ui', 'stream_answer': True},
                            chat_fn=generate, progress=events.append)
        self.assertEqual(result['answer'], source)
        self.assertEqual(events[-1]['text'], source)

    def test_web_verification_clears_unverified_draft(self):
        events = []
        def generate(client, options, messages, structured=False):
            if structured:
                options['on_chunk']('{"answer":"Unverified","needs_web":true}')
                return '{"answer":"Unverified","needs_web":true}'
            options['on_chunk']('Verified [1].')
            return 'Verified [1].'
        with patch('jarvis.knowledge_worker.time.monotonic', side_effect=[1, 2, 3]):
            result = answer({'question': 'fixture', 'stream_answer': True}, chat_fn=generate,
                search_fn=lambda _: [{'title': 'Fixture', 'url': 'https://example.com', 'snippet': 'Evidence'}], progress=events.append)
        self.assertIn({'phase': 'Verifying online', 'text': ''}, events)
        self.assertIn('Verified [1].', result['answer'])
        self.assertNotIn('Unverified', result['answer'])

    def test_http_thinking_activity_does_not_expose_reasoning(self):
        client, response, activity, output = Mock(), Mock(), Mock(), Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_lines.return_value = iter([
            b'{"message":{"thinking":"private reasoning"},"done":false}',
            b'{"message":{"content":"Answer"},"done":true}'])
        client.post.return_value = response
        result = chat(client, {'model': 'fixture', 'stream': True, 'on_activity': activity, 'on_chunk': output}, [])
        self.assertEqual(result, 'Answer')
        activity.assert_any_call('Thinking')
        output.assert_called_once_with('Answer')
        self.assertNotIn('private reasoning', str(activity.call_args_list))

    def test_http_content_wins_over_activity_throttling(self):
        client, response = Mock(), Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_lines.return_value = iter([
            json.dumps({'message': {'content': '{"answer":"Hello'} }).encode(),
            json.dumps({'message': {'content': ' world","needs_web":false}'}, 'done': True}).encode()])
        client.post.return_value = response
        events = []
        with patch('jarvis.knowledge_worker.time.monotonic', side_effect=[1, 1.01, 2, 2.01]):
            result = answer({'question': 'fixture', 'stream_answer': True, 'options': {'model': 'fixture'}}, client=client, progress=events.append)
        self.assertEqual(events[-1]['text'], result['answer'])

    def test_question_limits_are_finite_and_bounded(self):
        self.assertEqual(question_limits({}), (300, 1800))
        self.assertEqual(question_limits({'timeout_seconds': 9999, 'max_answer_seconds': 9999}), (600, 3600))
        for bad in (True, None, 'unlimited', float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                question_limits({'max_answer_seconds': bad})
