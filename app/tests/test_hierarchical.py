import copy
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock
from jarvis.dag_execution import Executor, Tool, validate_plan
from jarvis.hierarchical import eligible, MacroMemory

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['value'],
          'properties': {'value': {'type': 'string', 'maxLength': 100}}}

def step(identifier='a', arguments=None, dependencies=None, effect=False, tool='read'):
    return {'id': identifier, 'tool': tool, 'arguments': arguments or {'value': 'data'},
        'dependencies': dependencies or [], 'expected': 'Read data',
        'permission': 'user' if effect else 'read', 'resources': {'cpu': 1, 'ram_mb': 32, 'gpu_mb': 0},
        'retry': {'attempts': 1, 'backoff_seconds': .01}, 'timeout_seconds': 2}

def graph(*steps):
    return {'version': 1, 'steps': list(steps)}

def tools(call=None, verify=None, effect=False, resource=''):
    return {'read': Tool('read', SCHEMA, call or (lambda args, cancelled: {'text': args['value']}),
        verify or (lambda args, result: result['text'] == args['value']), not effect, resource)}

class DAGTests(unittest.TestCase):
    def test_rejects_invalid_graph_before_dispatch(self):
        call = Mock()
        invalid = [graph(step(), step()), graph(step(dependencies=['missing'])),
            graph(step(dependencies=['a'])), graph(step(tool='unavailable')),
            graph(step(arguments={'extra': 'wrong'})), graph(step(effect=True)),
            graph(step('a', dependencies=['b']), step('b', dependencies=['a']))]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_plan(value, tools(call))
        call.assert_not_called()
        for mutate in [lambda s: s['resources'].update(gpu_mb=1),
                       lambda s: s['retry'].update(attempts=4),
                       lambda s: s.update(timeout_seconds=float('inf')),
                       lambda s: s.update(id=True)]:
            row = step()
            mutate(row)
            with self.assertRaises(ValueError):
                validate_plan(graph(row), tools())

    def test_reads_overlap_and_dependencies_wait_out_of_order(self):
        barrier, events = threading.Barrier(2), []
        def read(args, cancelled):
            if args['value'] in {'a', 'b'}:
                barrier.wait(timeout=2)
            events.append(args['value'])
            return {'text': args['value']}
        rows = [step('c', {'value': 'c'}, ['a', 'b']), step('a', {'value': 'a'}), step('b', {'value': 'b'})]
        result = Executor(tools(read), 2).run(validate_plan(graph(*rows), tools(read)))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(events[-1], 'c')

    def test_typed_lookup_and_task_isolation(self):
        ref = {'$ref': {'step': 'a', 'path': ['text'], 'type': 'string'}}
        result = Executor(tools()).run(validate_plan(graph(step(), step('b', {'value': ref}, ['a'])), tools()))
        self.assertEqual(result['steps']['b']['result']['text'], 'data')
        with self.assertRaises(ValueError):
            validate_plan(graph(step('b', {'value': ref})), tools())
        ref['$ref']['path'] = ['absent']
        result = Executor(tools()).run(validate_plan(graph(step(), step('b', {'value': ref}, ['a'])), tools()))
        self.assertEqual(result['steps']['b']['status'], 'failed')

    def test_read_retry_backoff_and_failure_propagation(self):
        calls = []
        def flaky(args, cancelled):
            calls.append(time.monotonic())
            if len(calls) == 1:
                raise OSError('Transient read failure')
            return {'text': args['value']}
        row = step()
        row['retry']['attempts'] = 2
        result = Executor(tools(flaky)).run(validate_plan(graph(row), tools(flaky)))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['steps']['a']['attempts'], 2)
        self.assertGreaterEqual(calls[1]-calls[0], .01)
        bad = tools(verify=lambda args, result: False)
        result = Executor(bad).run(validate_plan(graph(step(), step('b', dependencies=['a'])), bad))
        self.assertEqual(result['steps']['b']['status'], 'blocked')

    def test_uncertain_effect_never_retried_or_resumed(self):
        calls = []
        def effect(args, cancelled):
            calls.append(1)
            raise OSError('Failure after effect')
        registry, row = tools(effect, effect=True), step(effect=True)
        result = Executor(registry).run(validate_plan(graph(row), registry))
        self.assertEqual(calls, [1])
        self.assertTrue(result['steps']['a']['uncertain_effect'])
        with self.assertRaises(ValueError):
            Executor(registry).run(validate_plan(graph(row), registry), restored=result['steps'])
        row['retry']['attempts'] = 2
        with self.assertRaises(ValueError):
            validate_plan(graph(row), registry)

    def test_cancellation_and_timeout_drain_workers(self):
        stop, finished = threading.Event(), []
        def slow(args, cancelled):
            stop.set()
            while not cancelled():
                time.sleep(.005)
            finished.append(1)
            raise InterruptedError('Stopped')
        registry = tools(slow)
        result = Executor(registry).run(validate_plan(graph(step(), step('b', dependencies=['a'])), registry), stop.is_set)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(finished, [1])
        def late(args, cancelled):
            time.sleep(.08)
            finished.append(2)
            return {'text': args['value']}
        registry, row = tools(late, effect=True), step(effect=True)
        row['timeout_seconds'] = .05
        result = Executor(registry).run(validate_plan(graph(row), registry))
        self.assertEqual(finished, [1, 2])
        self.assertEqual(result['steps']['a']['error_type'], 'TimeoutError')

    def test_effect_checkpoint_precedes_dispatch_and_resource_serializes(self):
        saved, active, maximum = [], [0], [0]
        lock = threading.Lock()
        def effect(args, cancelled):
            self.assertTrue(saved)
            with lock:
                active[0] += 1
                maximum[0] = max(maximum[0], active[0])
            time.sleep(.02)
            with lock:
                active[0] -= 1
            return {'text': args['value']}
        registry = tools(effect, effect=True, resource='files')
        result = Executor(registry, checkpoint=lambda s: saved.append(s)).run(validate_plan(graph(step(effect=True), step('b', effect=True)), registry))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(maximum[0], 1)

    def test_repeated_runs_close_task_owned_threads(self):
        registry = tools()
        for _ in range(30):
            result = Executor(registry).run(validate_plan(graph(step(), step('b')), registry))
            self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(t.name.startswith('Jarvis DAG') for t in threading.enumerate()))

class IntegrationTests(unittest.TestCase):
    def test_schema_planning_activity_uses_protocol_during_redirect(self):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        from jarvis.brain_worker import Models
        models = Models.__new__(Models)
        models.client, models.coding_options = object(), {}
        models.protocol = io.StringIO()
        def chat(client, settings, messages, structured):
            self.assertTrue(structured)
            self.assertEqual(settings['format_schema']['properties']['version']['enum'], [1])
            settings['on_activity']('Generating answer')
            return json.dumps(graph(step()))
        with patch('jarvis.brain_worker.chat', chat), contextlib.redirect_stdout(io.StringIO()):
            result = models.generate('installed-model', 'Plan task', {'tools': [{'action': 'read'}]}, 'dag_plan')
        self.assertNotIn('model_used', result)
        self.assertIn('inference_activity', models.protocol.getvalue())

    def test_battery_and_cpu_use_existing_deterministic_status_path(self):
        from jarvis.commands import parse
        from jarvis.intent_handlers import system_info
        from unittest.mock import patch
        from types import SimpleNamespace
        self.assertEqual(parse('what is my battery level').kind, 'system_info')
        self.assertEqual(parse('show CPU usage').value, 'quick_cpu')
        with patch('psutil.sensors_battery', return_value=SimpleNamespace(percent=64, power_plugged=True)):
            self.assertEqual(system_info(None, 'battery'), 'Battery is 64%, plugged in.')

    def test_scope_and_policy_checked_before_any_graph_effect(self):
        from jarvis.dag_execution import Tool
        call = Mock()
        deny = Mock(side_effect=ValueError('Denied by current policy'))
        registry = tools(call, effect=True)
        registry['read'] = Tool('read', SCHEMA, call, lambda a, r: True, False, 'files', deny)
        with self.assertRaisesRegex(ValueError, 'Denied'):
            validate_plan(graph(step(effect=True)), registry)
        call.assert_not_called()

    def test_restart_blocks_effects_but_preserves_read_checkpoint(self):
        from jarvis.task_state import TaskState
        with tempfile.TemporaryDirectory() as folder:
            state = TaskState(folder)
            state.start('Read data', 'task')
            state.update_dag(graph(step()), {'a': {'status': 'running', 'effect': False}}, 'v1', {})
            restarted = TaskState(folder)
            self.assertEqual(restarted.snapshot()['status'], 'interrupted')
            self.assertIsNone(TaskState.resume_blocker(restarted.snapshot()))
            state.start('Write data', 'task')
            state.update_dag(graph(step(effect=True)), {'a': {'status': 'running', 'effect': True}}, 'v1', {})
            restarted = TaskState(folder)
            self.assertIn('uncertain', TaskState.resume_blocker(restarted.snapshot()))

    def test_fast_and_specialized_paths_preserved(self):
        options = {'hierarchical_execution': {'enabled': True}}
        for goal in ['open Chrome', 'Write code for a game', 'Send Gmail', 'Inspect Unreal Blueprints', 'Play Spotify']:
            self.assertFalse(eligible(goal, options))
        self.assertTrue(eligible('Read one.txt and two.txt in this folder', options))
        self.assertFalse(eligible('Read one.txt and two.txt', {}))

    def test_macro_exact_match_version_and_no_effect_reuse(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = MacroMemory(folder)
            memory.remember('read data', 'v1', graph(step()), tools())
            self.assertIsNotNone(memory.lookup('read data', 'v1'))
            self.assertIsNone(memory.lookup('read more data', 'v1'))
            self.assertIsNone(memory.lookup('read data', 'v2'))
            memory.remember('write data', 'v1', graph(step(effect=True)), tools(effect=True))
            self.assertIsNone(memory.lookup('write data', 'v1'))

    def test_real_actions_registry_files_and_checkpoint(self):
        from jarvis.actions import Actions
        from jarvis.commands import Command
        from jarvis.task_state import TaskState
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'one.txt').write_text('first', encoding='utf-8')
            (root/'two.txt').write_text('second', encoding='utf-8')
            actions = Actions({'files_root': 'managed', 'apps': {}, '_ui_verification': True,
                'memory': {'enabled': False}, 'brain': {'enabled': True, 'planner': 'configured-model',
                'hierarchical_execution': {'enabled': True}}}, root, lambda *_: None)
            actions.allowed_tools = {'read_file'}
            actions._task_folder = lambda name, cancelled: root
            actions.task_state = TaskState(root)
            rows = [step('one', {'value': 'one.txt', 'expected': 'Read first', 'folder': 'this folder'}, tool='read_file'),
                    step('two', {'value': 'two.txt', 'expected': 'Read second', 'folder': 'this folder'}, tool='read_file')]
            actions.brain.client = Mock()
            actions.brain.client.request.return_value = graph(*rows)
            # Enable production cache behavior only after safe fixture setup.
            actions.config['_ui_verification'] = False
            try:
                reply = actions.execute(Command('task', 'Inspect files one.txt and two.txt in this folder and report both contents'))
                self.assertIn('first', reply)
                self.assertIn('second', reply)
                self.assertEqual(actions.task_state.snapshot()['status'], 'completed')
                self.assertEqual(actions.task_state.snapshot()['dag']['steps']['one']['status'], 'succeeded')
                self.assertEqual(actions.brain.client.request.call_args.args[0], 'dag_plan')
                second = actions.execute(Command('task', 'Inspect files one.txt and two.txt in this folder and report both contents'))
                self.assertIn('second', second)
                self.assertEqual(actions.brain.client.request.call_count, 1)
                self.assertTrue(actions.task_state.snapshot()['dag']['timings']['cache_hit'])
                # Missing-file fault: repair only the failed read, retaining the
                # successful independent read rather than rerunning the graph.
                from unittest.mock import patch
                from jarvis.tools import ToolRegistry
                bad = copy.deepcopy(rows)
                bad[1]['arguments']['value'] = 'missing.txt'
                actions.brain.client.request.side_effect = [graph(*bad), graph(rows[1])]
                original = ToolRegistry.execute
                calls = []
                def dispatch(registry, proposal, cancelled, activate=None):
                    calls.append(proposal['value'])
                    return original(registry, proposal, cancelled, activate)
                with patch.object(ToolRegistry, 'execute', dispatch):
                    repaired = actions.execute(Command('task', 'Inspect one.txt and two.txt in this folder and report their contents'))
                self.assertIn('second', repaired)
                self.assertEqual(calls.count('one.txt'), 1)
                self.assertEqual(calls.count('two.txt'), 1)
                self.assertEqual(calls.count('missing.txt'), 1)
                # Analysis requests must use the existing real think adapter,
                # rather than return raw data while claiming analysis is done.
                actions.allowed_tools = {'read_file', 'think'}
                actions.brain.client.request.side_effect = [graph(*rows), {'text': 'The first file is first; the second is second.'}]
                compared = actions.execute(Command('task', 'Compare one.txt and two.txt in this folder'))
                self.assertEqual(compared, 'The first file is first; the second is second.')
                self.assertEqual(actions.brain.client.request.call_args.args[0], 'tool_text')
                self.assertIn('first', actions.brain.client.request.call_args.kwargs['context'])
            finally:
                actions.close()

if __name__ == '__main__':
    unittest.main()
