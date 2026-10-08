import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from jarvis.brain import BrainClient
from jarvis.harness import HarnessClient, HarnessProvider, healthy, readiness, repair
from jarvis.harness_process import OwnedJob, hidden_spawn
from jarvis.harness_worker import ACTIVE, audit_profile, agent_schema


class HarnessTests(unittest.TestCase):
    def test_scoped_development_plan_routing_and_path_validation(self):
        client = BrainClient(Path.cwd(), {'harness': {'enabled': True}})
        worker=Mock()
        with patch('jarvis.harness.HarnessClient',return_value=worker), patch.object(client,'_request_once',return_value={}) as regular:
            client.request('code_plan',lambda:False,goal='Build React dashboard',development=True)
            self.assertEqual(worker.request.call_args.args[0],'code_plan')
            client.request('code_plan',lambda:False,goal='Python file')
            self.assertEqual(regular.call_count,1)
            client.close()
        harness=HarnessClient(Path.cwd(),{})
        with patch.object(BrainClient,'_request_once',return_value={'directories':[],'files':[{'path':'../escape.ts','reason':'bad'}]}):
            with self.assertRaises(ValueError):harness.request('code_plan',lambda:False,development=True)

    def proposal(self):
        return {'question': '', 'steps': [{'action': 'open', 'value': 'calculator', 'expected': 'Calculator visible'}]}

    def test_research_provider_preserves_strict_session_response_contract(self):
        provider = HarnessProvider(Path.cwd())
        with patch.object(provider.client, 'request', return_value={'final': '5', 'calls': [],
                'backend': 'deepseek-harness', 'harness_session_id': 'trace'}) as infer:
            self.assertEqual(provider({'goal': 'Read sample.py'}), {'final': '5', 'calls': []})
            self.assertEqual(infer.call_args.args[0], 'agent')

    def test_profile_rejects_shell_and_unknown_active_plugins(self):
        rows = [{'id': key, 'name': value} for key, value in ACTIVE.items()]
        self.assertEqual(audit_profile(json.dumps(rows)), sorted(ACTIVE))
        for extra in ({'id': 'persistent-pwsh', 'name': '@deepseek-ai/dsh-tool-pwsh-persistent'},
                      {'id': 'extra', 'name': 'untrusted-plugin'}, rows[0]):
            with self.assertRaisesRegex(ValueError, 'isolation'):
                audit_profile(json.dumps(rows + [extra]))

    def test_disabled_tool_does_not_join_profile(self):
        rows = [{'id': key, 'name': value} for key, value in ACTIVE.items()]
        rows.append({'id': 'persistent-pwsh', 'name': 'shell', 'disabled': True})
        self.assertEqual(audit_profile(json.dumps(rows)), sorted(ACTIVE))
        rows[-1]['disabled'] = 'true'
        with self.assertRaisesRegex(ValueError, 'isolation'):
            audit_profile(json.dumps(rows))

    def test_local_schema_advertises_only_current_read_tools(self):
        schema = agent_schema({'tools': [{'action': 'read_file'}]})
        self.assertEqual(schema['properties']['calls']['maxItems'], 1)
        self.assertEqual(schema['properties']['calls']['items']['properties']['action']['enum'], ['read_file'])

    def test_routing_preserves_memory_and_other_inference_routes(self):
        client = BrainClient(Path.cwd(), {'harness': {'enabled': True}, 'hermes': {'enabled': True}})
        client.memory = Mock()
        client.memory.task_context.return_value = {'projects': []}
        worker = Mock()
        with patch('jarvis.harness.HarnessClient', return_value=worker), patch.object(client, '_request_once', return_value={}) as original:
            client.request('plan', lambda: False, goal='Open calculator')
            self.assertEqual(worker.request.call_args.kwargs['memory_context'], {'projects': []})
            client.request('code_edit', lambda: False, goal='Write a script')
            client.request('verify', lambda: False, goal='Open calculator')
            self.assertEqual(original.call_count, 2)
            client.close()
            worker.close.assert_called_once()

    def test_invalid_proposal_cannot_reach_execution(self):
        client = HarnessClient(Path.cwd(), {})
        with patch.object(BrainClient, '_request_once', return_value=self.proposal()):
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                client.request('plan', lambda: False, tools=[{'action': 'browse'}])

    def test_mixed_clarification_and_steps_remain_rejected_by_runtime(self):
        client=HarnessClient(Path.cwd(),{})
        value={**self.proposal(),'question':'Which unrelated folder?'}
        with patch.object(BrainClient,'_request_once',return_value=value) as inference:
            with self.assertRaisesRegex(ValueError,'either steps'):
                client.request('plan',lambda:False,tools=[{'action':'open'}])
            inference.assert_called_once()
            self.assertIsNone(client.process)

    def test_replan_cannot_repeat_completed_action(self):
        client = HarnessClient(Path.cwd(), {})
        proposal = {**self.proposal(), 'done': False, 'reason': 'continue'}
        with patch.object(BrainClient, '_request_once', return_value=proposal):
            with self.assertRaises(ValueError):
                client.request('replan', lambda: False, tools=[{'action': 'open'}], steps_left=3,
                    completed=[{'action': 'open', 'value': 'calculator'}])

    def test_cancelled_request_does_not_start_worker(self):
        client = HarnessClient(Path.cwd(), {})
        with patch('jarvis.brain.subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                client.request('plan', lambda: True)
            launch.assert_not_called()

    def test_missing_environment_has_setup_instruction(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn('Setup Jarvis Harness.cmd', readiness(directory))
            with self.assertRaisesRegex(ValueError, 'runtime missing'):
                HarnessClient(directory, {}).request('plan', lambda: False)

    def test_worker_loss_has_bounded_inference_retry_and_backoff(self):
        client = HarnessClient(Path.cwd(), {})
        started = time.monotonic()
        with patch.object(client, '_request_once', side_effect=[OSError('lost'), OSError('lost')]) as infer, \
                patch.object(client, 'close') as close, patch('jarvis.recovery.record') as record:
            with self.assertRaises(OSError):
                client.request('plan', lambda: False)
            self.assertEqual(infer.call_count, 2)
            self.assertGreaterEqual(time.monotonic() - started, .45)
            close.assert_called_once()
            record.assert_called_once()

    def test_cancellation_during_recovery_prevents_retry(self):
        client = HarnessClient(Path.cwd(), {})
        with patch.object(client, '_request_once', side_effect=OSError('lost')) as infer, \
                patch.object(client, 'close'), patch('jarvis.recovery.record') as record:
            with self.assertRaisesRegex(ValueError, 'cancelled during'):
                client.request('plan', Mock(side_effect=[False, True]))
            infer.assert_called_once()
            record.assert_not_called()

    def test_watchdog_clears_dead_worker_without_running_inference(self):
        owner = Mock()
        owner.harness.process.poll.return_value = 1
        self.assertFalse(healthy(owner))
        owner.harness.close.side_effect = lambda: setattr(owner.harness, 'process', None)
        self.assertTrue(repair(owner))
        owner.harness.request.assert_not_called()

    def test_hidden_spawn_attaches_only_created_process(self):
        job, spawn = Mock(), Mock()
        child = hidden_spawn(job, spawn)(['owned-runtime'])
        job.attach.assert_called_once_with(child)
        self.assertIn('creationflags', spawn.call_args.kwargs)

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows job ownership')
    def test_job_close_reaps_owned_child_and_leaves_unowned_child(self):
        import sys
        job = OwnedJob()
        owned = hidden_spawn(job, subprocess.Popen)([sys.executable, '-c', 'import time;time.sleep(30)'])
        unowned = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'], creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            job.close()
            owned.wait(timeout=5)
            self.assertIsNone(unowned.poll())
        finally:
            job.close()
            for child in (owned, unowned):
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
