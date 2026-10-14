import unittest
from unittest.mock import Mock, patch
from jarvis.natural_conversation import eligible, generate
from jarvis.knowledge_worker import handle_request

OPTIONS = {'natural_conversation': {'enabled': True, 'model': 'qwen3.5:0.8b'}}


class NaturalConversationTests(unittest.TestCase):
    def test_social_route_excludes_research(self):
        for text in ['Hello', "I'm tired today", 'Thanks', "Let's talk"]:
            self.assertTrue(eligible(text, OPTIONS))
        for text in ['Explain quantum mechanics', 'Write a program', 'What is the current price of gold?']:
            self.assertFalse(eligible(text, OPTIONS))
        self.assertTrue(eligible('It was mostly meetings. Any ideas?', OPTIONS, recent=True))
        self.assertFalse(eligible('Hi, explain quantum mechanics', OPTIONS))

    def test_parent_routes_followup_and_grounding_to_generated_model(self):
        import threading
        from jarvis.knowledge import Knowledge
        ready = threading.Event()
        def report(kind, value):
            if kind == 'answer':
                ready.set()
        knowledge = Knowledge(OPTIONS, report)
        knowledge.client._start = Mock()
        knowledge.client.request = Mock(return_value={'answer': 'A new reply.'})
        knowledge.start()
        try:
            knowledge.submit('Hello')
            self.assertTrue(ready.wait(2))
            ready.clear()
            knowledge.submit('It was mostly meetings. Any ideas?')
            self.assertTrue(ready.wait(2))
            payload = knowledge.client.request.call_args.args[0]
            self.assertTrue(payload['_natural_chat'])
            self.assertIn('A new reply.', str(payload['history']))
            ready.clear()
            knowledge.submit_natural('Explain available features.', 'Only verified local features.')
            self.assertTrue(ready.wait(2))
            self.assertEqual(knowledge.client.request.call_args.args[0]['grounded_reply'], 'Only verified local features.')
            ready.clear()
            knowledge._context = Mock(return_value={'history': list(knowledge.history), 'source': 'current_session', 'matches': []})
            knowledge.quick.answer = Mock(return_value='The local time is 9:04 AM.')
            knowledge.submit('What time is it?')
            self.assertTrue(ready.wait(2))
            payload = knowledge.client.request.call_args.args[0]
            self.assertEqual(payload['grounded_reply'], 'The local time is 9:04 AM.')
            self.assertTrue(payload['history'])
        finally:
            knowledge.close()

    def test_generated_reply_preserves_context_without_tools(self):
        seen = []
        def chat(client, options, messages):
            seen.append((options, messages))
            options['on_chunk']('That sounds exhausting.')
            return 'That sounds exhausting.'
        progress = Mock()
        result = generate({'question': "I'm tired", 'options': OPTIONS,
            'history': [{'role': 'user', 'content': 'I worked late.'}, {'role': 'assistant', 'content': 'A long evening.'}]}, chat, progress)
        self.assertEqual(result['answer'], 'That sounds exhausting.')
        self.assertEqual(seen[0][0]['num_gpu'], 0)
        self.assertFalse(seen[0][0]['think'])
        self.assertIn('I worked late.', str(seen[0][1]))
        self.assertNotIn('format_schema', seen[0][0])
        self.assertIsNotNone(result['conversation_metrics']['first_text_seconds'])

    def test_worker_fast_path_never_exports_history(self):
        with patch('jarvis.natural_conversation.generate', return_value={'answer': 'Fresh reply.'}) as generated, patch('jarvis.hybrid_inference.maybe_answer') as cloud:
            result = handle_request({'question': 'Hello', 'options': OPTIONS, '_natural_chat': True}, Mock())
        self.assertEqual(result['answer'], 'Fresh reply.')
        cloud.assert_not_called()
        generated.assert_called_once()

    def test_failures_are_reported_without_canned_fallback(self):
        with patch('jarvis.natural_conversation.generate', side_effect=ValueError('Model unavailable')):
            result = handle_request({'question': 'Hello', '_natural_chat': True}, Mock())
        self.assertEqual(result, {'error': 'Model unavailable'})
