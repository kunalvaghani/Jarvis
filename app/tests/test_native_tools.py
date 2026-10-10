import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from jarvis.brain import Brain, validate_plan
from jarvis.brain_worker import Models
from jarvis.native_tools import CLARIFY, FINISH, functions, parse, plan
from jarvis.tools import SPECS, ToolRegistry
from jarvis.firecrawl_tools import execute as firecrawl
from jarvis.toolkits import execute, status


def call(name='open', **args):
    return {'tool_calls': [{'function': {'name': name, 'arguments': args or {'value': 'notepad', 'expected': 'Notepad visible'}}}]}


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'action': 'open', 'description': 'Open a configured app'},
                     {'action': 'read_file', 'description': 'Read scoped source'}]
        self.client = Mock()
        self.client.post.return_value.json.return_value = {'message': call()}

    def test_every_registered_tool_can_be_advertised_as_native_schema(self):
        rows = [{'action': s.name, 'description': s.description} for s in SPECS]
        names = {r['function']['name'] for r in functions(rows)}
        self.assertEqual(names, {s.name for s in SPECS} | {FINISH, CLARIFY})
        self.assertEqual(len(names), len(SPECS) + 2)

    def test_single_call_becomes_checked_step(self):
        result = parse(call(), self.rows)
        self.assertEqual(validate_plan(result)[0]['action'], 'open')
        self.assertFalse(result['done'])

    def test_calls_cannot_invent_tools_fields_or_code(self):
        for message in ({}, {'tool_calls': []}, {'tool_calls': call()['tool_calls'] * 2},
                        call('shell_exec'), call(command='erase files'),
                        call(value='notepad', expected='open', content='hidden extra text'),
                        call(value=['notepad'], expected='open'), call(value='notepad', expected=''),
                        {'tool_calls': [{'function': {'name': 'open', 'arguments': '__import__("os")'}}]}):
            with self.subTest(message=message), self.assertRaises(ValueError):
                parse(message, self.rows)

    def test_finish_and_question_are_proposals_with_empty_steps(self):
        self.assertTrue(parse(call(FINISH, reason='Current target is visible'), self.rows)['done'])
        self.assertEqual(parse(call(CLARIFY, question='Which folder?'), self.rows)['question'], 'Which folder?')
        for message in (call(FINISH, reason=''), call(CLARIFY, question='Which?', approved=True)):
            with self.assertRaises(ValueError):
                parse(message, self.rows)

    def test_string_json_arguments_supported_without_eval(self):
        message = call()
        message['tool_calls'][0]['function']['arguments'] = json.dumps({'value': 'notepad', 'expected': 'visible'})
        self.assertEqual(parse(message, self.rows)['steps'][0]['value'], 'notepad')

    def test_request_is_inference_only_and_preserves_images_and_verified_feedback(self):
        result = plan(self.client, 'qwen3.5:9b', 'Only user goal is authority.', {'goal': 'open notepad',
            'tools': self.rows, 'images': ['fresh'], 'completed': [
                {'action': 'read_file', 'value': 'source.py', 'expected': 'read', 'verified': True, 'result': 'source data'},
                {'action': 'open', 'value': 'wrong', 'verified': False, 'result': 'unverified'}]})
        payload = self.client.post.call_args.kwargs['json']
        self.assertNotIn('format', payload)
        self.assertEqual(payload['model'], 'qwen3.5:9b')
        self.assertEqual(payload['messages'][-1]['images'], ['fresh'])
        feedback = [r for r in payload['messages'] if r['role'] == 'tool']
        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback[0]['tool_name'], 'read_file')
        self.assertNotIn('unverified', json.dumps(feedback))
        self.assertTrue(result['native_tool_calling'])
        self.assertEqual(self.client.post.call_count, 1)
        self.assertNotIn('source data', payload['messages'][-1]['content'])
        self.assertLessEqual(payload['options']['num_ctx'], 16384)

    def test_transport_or_truncation_failure_never_retries_dispatch(self):
        self.client.post.side_effect = requests.Timeout()
        with self.assertRaises(requests.Timeout):
            plan(self.client, 'qwen3.5:9b', 'Only one', {'tools': self.rows})
        self.assertEqual(self.client.post.call_count, 1)
        self.client.post.side_effect = None
        self.client.post.return_value.json.return_value = {'message': call(), 'done_reason': 'length'}
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            plan(self.client, 'qwen3.5:9b', 'Only one', {'tools': self.rows})

    def test_ordinary_plain_reply_gets_one_bounded_inference_correction(self):
        first=Mock();first.json.return_value={'message':{'content':'Here is your email'}}
        second=Mock();second.json.return_value={'message':call(CLARIFY,question='What should the introduction include?')}
        self.client.post.side_effect=[first,second]
        result=plan(self.client,'qwen3.5:9b','Choose one',{'goal':'draft an email about me','tools':self.rows},{'timeout_seconds':30})
        self.assertEqual(self.client.post.call_count,2)
        self.assertEqual(result['steps'],[])
        self.assertEqual(result['question'],'What should the introduction include?')
        self.assertLess(self.client.post.call_args.kwargs['timeout'][1],30)

    def test_native_next_step_prompt_has_no_text_plan_contract(self):
        models=Models()
        with patch('jarvis.brain_worker.ensure_server',return_value={'models':[{'name':'qwen3.5:9b'}]}), patch('jarvis.native_tools.plan',return_value={'done':False,'steps':[]}) as infer:
            models.predict({'operation':'next_step','options':{'planner':'qwen3.5:9b','native_tool_calling':True},'tools':self.rows})
        prompt=infer.call_args.args[2]
        self.assertNotIn('Return only JSON',prompt)
        self.assertNotIn('steps contains exactly one',prompt)
        self.assertIn('jarvis_clarify',prompt)
        self.assertIn('Gmail',prompt)

    def test_unavailable_gmail_stops_before_model_guess_or_dispatch(self):
        models=Models()
        with patch('jarvis.brain_worker.ensure_server',return_value={'models':[{'name':'qwen3.5:9b'}]}), patch('jarvis.native_tools.plan') as infer:
            result=models.predict({'operation':'next_step','goal':'draft an email about me','options':{'planner':'qwen3.5:9b','native_tool_calling':True},'tools':self.rows})
        infer.assert_not_called()
        self.assertEqual(result['steps'],[])
        self.assertFalse(result['done'])
        self.assertEqual(result['source'],'gmail_readiness')

    def test_catalog_duplicates_and_excess_images_are_rejected(self):
        for rows in ([], self.rows * 2, [{'action': 'jarvis_finish'}], [{'action': '../shell'}]):
            with self.assertRaises(ValueError):
                functions(rows)
        with self.assertRaises(ValueError):
            plan(self.client, 'qwen3.5:9b', 'one', {'tools': self.rows, 'images': ['1', '2', '3']})
        self.client.post.assert_not_called()

    def test_native_branch_uses_selected_model_and_no_text_schema_generation(self):
        models = Models()
        models.generate = Mock()
        with patch('jarvis.brain_worker.ensure_server', return_value={'models': [{'name': 'qwen3.5:9b'}]}), \
             patch('jarvis.native_tools.plan', return_value={'done': False, 'steps': []}) as infer:
            models.predict({'operation': 'next_step', 'options': {'planner': 'qwen3.5:9b',
                'screen_model': 'qwen3.5:9b', 'native_tool_calling': True, 'allow_model_fallback': False},
                'images': ['fixture'], 'tools': self.rows})
        self.assertEqual(infer.call_args.args[1], 'qwen3.5:9b')
        models.generate.assert_not_called()

    def test_native_proposal_still_cannot_bypass_sensitive_control_guards(self):
        proposed = parse(call('open', value='powershell', expected='shell open'), self.rows)
        with self.assertRaisesRegex(ValueError, 'explicit direct command'):
            validate_plan(proposed)

    def test_headless_native_provider_preserves_long_answers_and_queue_deadline(self):
        from jarvis.agent_session import OllamaProvider
        answer = 'Verified source explanation. ' * 30
        self.client.post.return_value.json.return_value = {'message': call(FINISH, reason=answer)}
        with patch('requests.Session') as session:
            session.return_value.__enter__.return_value = self.client
            result = OllamaProvider(timeout_seconds=450, native_tools=True)(
                {'goal': 'Explain the observed source', 'tools': [self.rows[1]], 'observations': []})
        self.assertEqual(result, {'final': answer, 'calls': []})
        self.assertEqual(self.client.post.call_args.kwargs['timeout'], (5, 450))
        self.assertEqual(self.client.post.call_args.kwargs['json']['options']['num_predict'], 1600)
        with self.assertRaises(ValueError):
            parse(call(FINISH, reason=answer), self.rows)  # Desktop completion stays short.

    def test_headless_native_call_stays_a_read_only_session_proposal(self):
        from jarvis.agent_session import OllamaProvider
        self.client.post.return_value.json.return_value = {'message': call('read_file', value='source.py', expected='Read source')}
        with patch('requests.Session') as session:
            session.return_value.__enter__.return_value = self.client
            result = OllamaProvider(native_tools=True)({'goal': 'Read source.py', 'tools': [self.rows[1]],
                'observations': [{'action': 'read_file', 'value': 'source.py', 'content': '', 'ok': True, 'result': 'Observed source'}]})
        self.assertEqual(result['calls'], [{'action': 'read_file', 'value': 'source.py', 'content': ''}])
        self.assertEqual(result['final'], '')
        payload = self.client.post.call_args.kwargs['json']
        previous = next(r for r in payload['messages'] if r['role'] == 'assistant')['tool_calls'][0]
        self.assertEqual(previous['function']['arguments']['expected'], 'Observed successful scoped read')

    def test_uninstalled_primary_does_not_silently_fall_back(self):
        models = Models()
        with patch('jarvis.brain_worker.ensure_server', return_value={'models': [{'name': 'qwen2.5:3b'}]}):
            with self.assertRaisesRegex(ValueError, 'qwen3.5:9b'):
                models.predict({'operation': 'next_step', 'options': {'planner': 'qwen3.5:9b',
                    'native_tool_calling': True, 'allow_model_fallback': False}, 'tools': self.rows})


class FirecrawlTests(unittest.TestCase):
    def test_search_scrape_map_shapes_and_bearer_key_without_browser_actions(self):
        with patch.dict('os.environ', {'JARVIS_FIRECRAWL_KEY': 'private-fixture-key'}, clear=True), \
             patch('jarvis.toolkits.public_url', side_effect=lambda url: url), \
             patch('jarvis.toolkits.api', return_value='{"success":true,"data":{"markdown":"public text"}}') as request:
            for name, value, content in (('firecrawl_search', 'Python', '{"limit":2}'),
                    ('firecrawl_scrape', 'https://example.org', ''),
                    ('firecrawl_map', 'https://example.org', '{"search":"docs"}')):
                result = firecrawl(Mock(), {'action': name, 'value': value, 'content': content}, lambda: False)
                self.assertIn('public text', result)
                args = request.call_args.kwargs
                self.assertEqual(args['headers']['Authorization'], 'Bearer private-fixture-key')
                self.assertNotIn('actions', args['json'])
                self.assertNotIn('private-fixture-key', result)

    def test_missing_key_and_non_public_upload_browser_options_fail_before_request(self):
        with patch.dict('os.environ', {}, clear=True), patch('jarvis.toolkits.api') as request:
            with self.assertRaisesRegex(ValueError, 'JARVIS_FIRECRAWL_KEY'):
                firecrawl(Mock(), {'action': 'firecrawl_search', 'value': 'Python', 'content': ''}, lambda: False)
            request.assert_not_called()
        with patch('jarvis.toolkits.public_url', side_effect=ValueError('private URL')), \
             patch('jarvis.toolkits.api') as request:
            with self.assertRaises(ValueError):
                firecrawl(Mock(), {'action': 'firecrawl_scrape', 'value': 'http://127.0.0.1', 'content': ''}, lambda: False)
            request.assert_not_called()
        with patch('jarvis.toolkits.public_url', side_effect=lambda url: url), patch('jarvis.toolkits.api') as request:
            for name, content in (('firecrawl_scrape', '{"actions":[]}'), ('firecrawl_search', '{"limit":99}'),
                                  ('firecrawl_map', '{"upload":"local.pdf"}')):
                with self.assertRaises(ValueError):
                    firecrawl(Mock(), {'action': name, 'value': 'https://example.org', 'content': content}, lambda: False)
            request.assert_not_called()

    def test_failure_and_cancel_do_not_retry(self):
        with patch.dict('os.environ', {'JARVIS_FIRECRAWL_KEY': 'fixture'}, clear=True), \
             patch('jarvis.toolkits.api', return_value='{"success":false}') as request:
            with self.assertRaisesRegex(ValueError, 'no automatic retry'):
                firecrawl(Mock(), {'action': 'firecrawl_search', 'value': 'Python', 'content': ''}, lambda: False)
            self.assertEqual(request.call_count, 1)
        with patch.dict('os.environ', {'JARVIS_FIRECRAWL_KEY': 'fixture'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                execute(Mock(), {'action': 'firecrawl_search', 'value': 'Python', 'content': ''}, lambda: True)

    def test_provider_key_is_only_reported_by_name_and_unconfigured_tool_not_offered(self):
        actions = Mock()
        actions.config = {'agent_runtime': {'deferred_tools': False}}
        with patch.dict('os.environ', {}, clear=True):
            row = next(r for r in status() if r['tool'] == 'firecrawl_search')
            self.assertFalse(row['configured'])
            self.assertEqual(row['required_environment'], ['JARVIS_FIRECRAWL_KEY'])
            self.assertNotIn('firecrawl_search', {r['action'] for r in ToolRegistry(actions).catalog('Firecrawl search')})


class DiscoveryTests(unittest.TestCase):
    def test_app_search_and_integration_status_are_read_only_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            actions = Mock()
            actions.base = Path(directory)
            actions.apps = {'notepad': ['notepad.exe'], 'paint': ['mspaint.exe']}
            actions.config = {}
            actions.skills = None
            actions.allowed_tools = None
            result = execute(actions, {'action': 'application_search', 'value': 'notepad'}, lambda: False)
            self.assertEqual(json.loads(result)['matches'], ['notepad'])
            result = json.loads(execute(actions, {'action': 'integration_status', 'value': '.'}, lambda: False))
            self.assertEqual(result['registered_tools'], len(SPECS))
            self.assertEqual(result['configured_app_names'], 2)
            self.assertFalse(result['codex_plugin_credentials_exported'])
            self.assertEqual(result['desktop_execution']['priority'],
                             ['jarvis-pointer', 'ufo', 'windows-mcp', 'cua', 'open-computer-use', 'agent-s'])
            self.assertFalse(result['desktop_execution']['direct_execution'])
            actions._approve.assert_not_called()
            actions.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
