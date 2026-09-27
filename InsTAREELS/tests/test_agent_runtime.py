import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from jarvis.agent_context import coding_context, compact_context, instruction_context, repository_map, scoped, skill_catalog
from jarvis.agent_session import AgentSession, ReadActions
from jarvis.agent_tools import execute, git_read
from jarvis.coder import Coder
from jarvis.mcp_bridge import StdioClient, execute as mcp_execute
from jarvis.task_state import TaskState
from jarvis.tools import ToolRegistry


SERVER = '''import json, sys, time
for line in sys.stdin:
    message = json.loads(line)
    method = message['method']
    if 'id' not in message:
        continue
    if method == 'initialize':
        result = {'protocolVersion':'2025-11-25', 'capabilities':{'tools':{}}, 'serverInfo':{'name':'test','version':'1'}}
    elif method == 'tools/list':
        result = {'tools':[{'name':'echo','description':'Echo arguments','inputSchema':{'type':'object'}}, {'name':'forbidden','inputSchema':{'type':'object'}}]}
    elif method == 'tools/call':
        if message['params']['arguments'].get('delay'):
            time.sleep(5)
        result = {'content':[{'type':'text','text':json.dumps(message['params']['arguments'])}]}
    else:
        result = {}
    print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}), flush=True)
'''


class AgentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'app'
        self.project.mkdir()
        (self.base / '.git').mkdir()
        (self.project / 'pyproject.toml').write_text('[project]\nname="demo"\n')
        (self.project / 'app.py').write_text('def hello():\n    return 1\n')
        self.actions = ReadActions(self.base, self.project)

    def step(self, name, value='.', **data):
        return {'action': name, 'value': value, 'folder': str(self.project), **data}

    def test_hierarchical_guidance_stops_at_repository_and_nested_target(self):
        (self.base / 'AGENTS.md').write_text('Root guidance')
        (self.project / 'AGENTS.md').write_text('App guidance')
        nested = self.project / 'lib'
        nested.mkdir()
        (nested / 'AGENTS.md').write_text('Nested guidance')
        rows = instruction_context(self.project, 'lib/new.py')
        self.assertEqual([r['text'] for r in rows], ['Root guidance', 'App guidance', 'Nested guidance'])
        self.assertEqual([r['path'] for r in rows], ['AGENTS.md', 'app/AGENTS.md', 'app/lib/AGENTS.md'])
        with self.assertRaises(ValueError):
            instruction_context(self.project, '../outside.py')

    def test_instructions_fail_closed_on_budget_and_invalid_encoding(self):
        path = self.project / 'AGENTS.md'
        path.write_text('x' * 6100)
        with self.assertRaisesRegex(ValueError, 'context budget'):
            instruction_context(self.project)
        path.write_bytes(b'\xff')
        with self.assertRaises(UnicodeError):
            instruction_context(self.project)

    def add_skill(self, directory, name='review'):
        path = self.project / directory / name / 'SKILL.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\nname: ' + name + '\ndescription: Review Python code\n---\nPreserve public interfaces.\n')
        return path

    def test_explicit_skills_and_enabled_plugin_bundles_are_data_only(self):
        self.add_skill('.agents/skills')
        plugin = self.project / '.jarvis/plugins/extra'
        plugin.mkdir(parents=True)
        (plugin / 'plugin.json').write_text('{"enabled":true}')
        self.add_skill('.jarvis/plugins/extra/skills', 'audit')
        self.assertEqual({r['name'] for r in skill_catalog(self.project)}, {'review', 'audit'})
        self.assertEqual(coding_context(self.project, 'inspect')['selected_skills'], [])
        self.assertEqual(coding_context(self.project, 'inspect $review')['selected_skills'][0]['name'], 'review')
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            coding_context(self.project, 'inspect $missing')
        (plugin / 'plugin.json').write_text('{"enabled":false}')
        self.assertEqual(len(skill_catalog(self.project)), 1)

    def test_source_map_never_imports_code_and_excludes_credentials(self):
        (self.project / 'app.py').write_text('raise RuntimeError("do not import")\ndef hello(): pass\nclass App: pass\n')
        (self.project / 'credentials.py').write_text('secret = 1')
        result = repository_map(self.project)
        self.assertIn('hello, App', result)
        self.assertNotIn('credentials', result)

    def test_deferred_search_loads_configured_tool_without_executing_it(self):
        registry = ToolRegistry(self.actions)
        before = {r['action'] for r in registry.catalog('help')}
        self.assertNotIn('git_diff', before)
        result = registry.execute(self.step('tool_search', 'git_diff'), lambda: False)
        self.assertIn('git_diff', result.evidence)
        self.assertIn('git_diff', {r['action'] for r in registry.catalog('help')})
        with patch.dict(os.environ, {}, clear=True):
            self.assertNotIn('send_email', {r['action'] for r in registry.search('email send')})
        self.assertNotIn('run_command', {r['action'] for r in registry.search('command')})

    def test_read_batch_preserves_order_and_captures_individual_failure(self):
        calls = [{'action': 'repository_map', 'value': '.'}, {'action': 'read_file', 'value': 'absent.txt'}]
        text = execute(self.actions, self.step('read_batch', content=json.dumps({'calls': calls})), lambda: False)
        rows = json.loads(text)
        self.assertTrue(rows[0]['ok'])
        self.assertFalse(rows[1]['ok'])
        self.assertIn('hello', rows[0]['result'])

    def test_read_batch_rejects_writes_network_nested_calls_and_cross_scope(self):
        for action in ('append_file', 'run_command', 'mcp_call', 'web_search', 'read_batch'):
            with self.subTest(action=action), self.assertRaises(ValueError):
                execute(self.actions, self.step('read_batch', content=json.dumps({'calls': [{'action': action, 'value': '.'}]})), lambda: False)
        with self.assertRaises(ValueError):
            execute(self.actions, self.step('read_file', '../outside.py'), lambda: False)

    def test_deny_policy_blocks_dispatch_and_events_omit_payload(self):
        policy = self.base / '.jarvis/policy.json'
        policy.parent.mkdir()
        policy.write_text('{"deny_tools":["repository_map"]}')
        with self.assertRaisesRegex(ValueError, 'denied'):
            ToolRegistry(self.actions).execute(self.step('repository_map'), lambda: False)
        policy.write_text('{"hooks":[{"event":"before_tool","tool":"repository_map","decision":"deny"}]}')
        with self.assertRaisesRegex(ValueError, 'hook'):
            ToolRegistry(self.actions).execute(self.step('repository_map'), lambda: False)
        policy.write_text('{}')
        (self.project / 'note.txt').write_text('PRIVATE SOURCE CONTENT')
        ToolRegistry(self.actions).execute(self.step('read_file', 'note.txt'), lambda: False)
        text = (self.base / '.jarvis-runtime/agent-events.jsonl').read_text()
        self.assertNotIn('PRIVATE SOURCE CONTENT', text)
        self.assertIn('tool.completed', text)

    def test_malformed_policy_and_executable_hooks_fail_closed(self):
        policy = self.base / '.jarvis/policy.json'
        policy.parent.mkdir()
        for content in ('{', '{"hooks":[{"command":"run arbitrary code"}]}', '{"deny_tools":"all"}'):
            policy.write_text(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                ToolRegistry(self.actions).execute(self.step('repository_map'), lambda: False)

    def test_compaction_preserves_user_goal_and_source_and_marks_excerpts(self):
        data = {'goal': 'exact goal', 'current': 'source stays exact', 'repository_instructions': [{'text': 'guidance'}],
                'completed': [{'action': 'read_file', 'value': 'app.py', 'result': 'x' * 30000}]}
        result = compact_context(data, limit=1000)
        for key in ('goal', 'current', 'repository_instructions'):
            self.assertEqual(result[key], data[key])
        self.assertLess(len(result['completed'][0]['result']), 600)
        self.assertIn('context_compaction', result)
        self.assertEqual(data['completed'][0]['result'], 'x' * 30000)

    def test_coder_receives_guidance_and_skills_before_generation(self):
        (self.project / 'AGENTS.md').write_text('Keep hello')
        self.add_skill('.agents/skills')
        actions, client = Mock(), Mock()
        client.request.return_value = {'content': 'def hello():\n    return 2\n'}
        Coder(actions, client).run(self.project, 'Modify app.py using $review')
        data = client.request.call_args.kwargs
        self.assertEqual(data['repository_instructions'][0]['text'], 'Keep hello')
        self.assertEqual(data['selected_skills'][0]['name'], 'review')

    def test_coder_bad_nested_guidance_does_not_create_draft(self):
        nested = self.project / 'lib'
        nested.mkdir()
        (nested / 'AGENTS.md').write_text('x' * 9000)
        actions, client = Mock(), Mock()
        client.request.return_value = {'files': [{'path': 'lib/new.py', 'reason': 'new'}]}
        with self.assertRaises(ValueError):
            Coder(actions, client).run(self.project, 'Create a helper program')
        self.assertFalse((nested / 'new.py').exists())

    def test_session_loop_observes_then_finishes_and_resume_never_replays(self):
        events = []
        session = AgentSession(self.base, self.project, emit=events.append)
        def provider(context):
            if not context['completed']:
                return {'calls': [{'action': 'repository_map', 'value': '.'}], 'final': ''}
            self.assertIn('hello', context['completed'][0]['result'])
            return {'calls': [], 'final': 'Found hello in app.py'}
        self.assertIn('hello', session.run('Map this project', provider))
        resumed = AgentSession(self.base, self.project, session.identifier)
        with patch('jarvis.tools.ToolRegistry.execute', side_effect=AssertionError('replayed')):
            self.assertEqual(resumed.run('What did you find?', lambda c: {'final': 'hello', 'calls': []}), 'hello')
        self.assertIn('turn.completed', [row['event'] for row in events])
        self.assertNotIn('def hello', session.path.read_text())

    def test_session_rejects_writes_repetition_wrong_project_and_budget(self):
        session = AgentSession(self.base, self.project)
        with self.assertRaisesRegex(ValueError, 'scoped read'):
            session.run('write', lambda c: {'calls': [{'action': 'create_file', 'value': 'new.py'}]})
        with self.assertRaisesRegex(ValueError, 'Repeated'):
            session.run('map', lambda c: {'calls': [{'action': 'repository_map', 'value': '.'}]})
        with self.assertRaisesRegex(ValueError, 'budget'):
            session.run('map', lambda c: {'calls': [{'action': 'repository_map', 'value': '.'}]}, max_steps=1)
        with self.assertRaisesRegex(ValueError, 'project does not match'):
            AgentSession(self.base, self.base, session.identifier)
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            session.run('map', lambda c: {}, cancelled=lambda: True)

    def test_explicit_source_is_read_before_model_can_answer(self):
        session = AgentSession(self.base, self.project)
        def answer(context):
            self.assertEqual(context['completed'][0]['action'], 'read_file')
            self.assertIn('def hello', context['completed'][0]['result'])
            return {'final': 'Inspected hello', 'calls': []}
        result = session.run('Read app.py and explain hello', answer)
        self.assertEqual(result, 'Inspected hello')
        with self.assertRaisesRegex(ValueError, 'budget'):
            session.run('Read absent.py', lambda c: {'final': 'guess', 'calls': []}, max_steps=2)

    def test_conflicting_final_and_call_is_corrected_without_dispatch(self):
        session = AgentSession(self.base, self.project)
        answers = iter([{'final': 'incorrect premature answer', 'calls': [{'action': 'read_file', 'value': 'app.py'}]},
                        {'final': 'corrected final', 'calls': []}])
        result = session.run('Explain the previous finding', lambda c: next(answers))
        self.assertEqual(result, 'corrected final')
        self.assertTrue(any(row['event'] == 'model.response_rejected' for row in session.history))
        self.assertFalse(any(row['event'] == 'tool.started' for row in session.history))

    def test_parallel_research_has_separate_context_budgets_and_fork_has_no_calls(self):
        session = AgentSession(self.base, self.project)
        def provider(context):
            if context['goal'] == 'Fail this child':
                raise ValueError('injected provider fault')
            return {'final': context['goal'] + ' inspected', 'calls': []}
        results = session.research_parallel(['Read symbols', 'Fail this child', 'Read guidance'], provider)
        self.assertEqual([row['ok'] for row in results], [True, False, True])
        self.assertEqual(len({row['session_id'] for row in results}), 3)
        session.run('Original goal', provider)
        child = session.fork()
        self.assertNotEqual(session.identifier, child.identifier)
        self.assertIn('Original goal', child.path.read_text())
        self.assertNotIn('tool.started', child.path.read_text())
        with self.assertRaises(ValueError):
            session.research_parallel(['one'] * 4, provider)
        with self.assertRaises(ValueError):
            session.research_parallel(['one'], provider, cancelled=lambda: True)

    def test_real_git_observation_and_diff_scope(self):
        repo = self.base / 'git-project'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
        (repo / 'app.py').write_text('x = 1\n')
        subprocess.run(['git', '-C', str(repo), 'add', 'app.py'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'Initial'], check=True, capture_output=True)
        (repo / 'app.py').write_text('x = 2\n')
        self.assertIn('app.py', git_read(repo, 'git_status', '.', lambda: False))
        self.assertIn('+x = 2', git_read(repo, 'git_diff', 'app.py', lambda: False))
        self.assertIn('Initial', git_read(repo, 'git_log', '.', lambda: False))
        with self.assertRaises(ValueError):
            git_read(repo, 'git_diff', '.', lambda: False)
        with self.assertRaises(ValueError):
            git_read(repo, 'git_status', '.', lambda: True)


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.server = self.base / 'server.py'
        self.server.write_text(SERVER)
        self.config = {'enabled': True, 'trusted': True, 'command': sys.executable,
                       'args': [str(self.server)], 'allow_tools': ['echo'], 'timeout_seconds': 1}
        folder = self.base / '.jarvis'
        folder.mkdir()
        (folder / 'mcp.json').write_text(json.dumps({'servers': {'fixture': self.config}}))
        self.actions = Mock(base=self.base)
        self.actions.task_state = TaskState(self.base)
        self.actions.task_state.start('MCP fixture', 'toolkit')

    def step(self, action='mcp_call', args=None):
        return {'action': action, 'value': 'fixture', 'content': json.dumps(args or {'name': 'echo', 'arguments': {'text': 'hello'}})}

    def test_real_handshake_tools_and_call_with_exact_approval(self):
        result = json.loads(mcp_execute(self.actions, self.step(), lambda: False))
        self.assertIn('hello', result['content'][0]['text'])
        self.actions._approve.assert_called_once()
        self.assertIn(sys.executable.replace('\\', '\\\\'), self.actions._approve.call_args.args[1])
        result = json.loads(mcp_execute(self.actions, self.step('mcp_list_tools', {'unused': True}), lambda: False))
        self.assertEqual([tool['name'] for tool in result], ['echo'])

    def test_unlisted_tool_and_untrusted_process_never_execute(self):
        with patch('jarvis.mcp_bridge.subprocess.Popen') as start:
            with self.assertRaises(ValueError):
                mcp_execute(self.actions, self.step(args={'name': 'forbidden', 'arguments': {}}), lambda: False)
            start.assert_not_called()
            self.config['trusted'] = False
            with self.assertRaises(ValueError):
                StdioClient(self.config, self.base, lambda: False)
            start.assert_not_called()

    def test_denied_approval_prevents_process_start(self):
        self.actions._approve.side_effect = ValueError('approval denied')
        with patch('jarvis.mcp_bridge.subprocess.Popen') as start, self.assertRaisesRegex(ValueError, 'denied'):
            mcp_execute(self.actions, self.step(), lambda: False)
        start.assert_not_called()

    def test_timeout_calls_once_closes_owned_process_and_preserves_uncertainty(self):
        original = StdioClient.request
        requests = []
        def record(client, method, params=None):
            requests.append(method)
            return original(client, method, params)
        with patch.object(StdioClient, 'request', record), self.assertRaisesRegex(ValueError, 'timed out'):
            mcp_execute(self.actions, self.step(args={'name': 'echo', 'arguments': {'delay': True}}), lambda: False)
        self.assertEqual(requests.count('tools/call'), 1)
        self.assertIn('not verified', self.actions.task_state.resume_blocker(self.actions.task_state.snapshot()))

    def test_cancellation_and_malformed_stdout_close_without_retry(self):
        stop = [False]
        client = StdioClient(self.config, self.base, lambda: stop[0])
        try:
            client.initialize()
            stop[0] = True
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                client.request('tools/list')
        finally:
            client.close()
        self.assertIsNotNone(client.process.poll())
        self.server.write_text('print("invalid json", flush=True)\n')
        client = StdioClient(self.config, self.base, lambda: False)
        try:
            with self.assertRaises(ValueError):
                client.initialize()
        finally:
            client.close()
        self.assertIsNotNone(client.process.poll())

    def test_status_never_starts_server_or_discloses_config_values(self):
        with patch('jarvis.mcp_bridge.subprocess.Popen') as start:
            result = mcp_execute(self.actions, self.step('mcp_status'), lambda: False)
        start.assert_not_called()
        self.assertNotIn(sys.executable, result)
        self.assertIn('fixture', result)

    def test_unresponsive_stdin_and_oversized_output_are_bounded(self):
        self.server.write_text('import time\ntime.sleep(10)\n')
        client = StdioClient(self.config, self.base, lambda: False)
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(ValueError, 'timed out'):
                client.request('fixture', {'payload': 'x' * 50000})
        finally:
            client.close()
        self.assertLess(time.monotonic() - started, 4)
        self.server.write_text('print("x"*300000, flush=True)\n')
        client = StdioClient(self.config, self.base, lambda: False)
        try:
            with self.assertRaises(ValueError):
                client.initialize()
        finally:
            client.close()


if __name__ == '__main__':
    unittest.main()
