import json
import unittest
from unittest.mock import Mock, patch

from jarvis.inference_limits import planning_read_timeout, planning_worker_timeout
from jarvis.brain_worker import Models
from jarvis.native_tools import plan


class InferenceLimitTests(unittest.TestCase):
    def test_worker_budget_exceeds_configured_http_deadline(self):
        self.assertEqual(planning_read_timeout({}), 120)
        self.assertEqual(planning_worker_timeout({}), 150)
        self.assertEqual(planning_read_timeout({'timeout_seconds': 300}), 300)
        self.assertEqual(planning_worker_timeout({'timeout_seconds': 300}), 330)

    def test_limits_remain_bounded_and_invalid_values_fail(self):
        self.assertEqual(planning_read_timeout({'timeout_seconds': 99999}), 600)
        self.assertEqual(planning_read_timeout({'timeout_seconds': 1}), 5)
        for value in (True, None, 'never', float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                planning_read_timeout({'timeout_seconds': value})

    def test_native_http_uses_the_shared_configured_budget(self):
        client = Mock()
        client.post.return_value.json.return_value = {'message': {'tool_calls': [
            {'function': {'name': 'open', 'arguments': {'value': 'notepad', 'expected': 'Notepad visible'}}}]}}
        plan(client, 'qwen3.5:9b', 'One proposal',
             {'tools': [{'action': 'open', 'description': 'Open an app'}]}, {'timeout_seconds': 300})
        self.assertEqual(client.post.call_args.kwargs['timeout'], (5, 300))
        client.post.assert_called_once()

    def test_non_native_generation_honors_the_same_budget(self):
        model = Models()
        model.coding_options = {'timeout_seconds': 300}
        with patch('jarvis.brain_worker.chat', return_value=json.dumps({'text': 'fixture'})) as generate:
            model.generate('qwen3.5:9b', 'Read-only text', {}, 'tool_text')
        self.assertEqual(generate.call_args.args[1]['timeout_seconds'], 300)
