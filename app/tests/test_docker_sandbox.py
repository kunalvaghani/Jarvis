import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from jarvis.docker_runtime import DockerService,desktop_environment,desktop_start_lock
from jarvis.deerflow_sandbox import SandboxJob
from jarvis.recovery import Watchdog
from jarvis.brain import replannable


class DockerRecoveryTests(unittest.TestCase):
    def test_desktop_keeps_profile_paths_but_excludes_secret_environment(self):
        import os
        values={'LOCALAPPDATA':'local','APPDATA':'roaming','USERPROFILE':'profile','PATH':'bin',
            'GROQ_API_KEY':'never-forward','JARVIS_FIRECRAWL_KEY':'never-forward','DOCKER_AUTH_CONFIG':'never-forward'}
        with patch.dict(os.environ,values,clear=True):
            env=desktop_environment()
        self.assertEqual(env['LOCALAPPDATA'],'local')
        self.assertEqual(env['APPDATA'],'roaming')
        self.assertEqual(env['USERPROFILE'],'profile')
        self.assertFalse(set(values).intersection(env)-{'LOCALAPPDATA','APPDATA','USERPROFILE','PATH'})

    def test_missing_profile_fails_without_launching_desktop(self):
        import os
        if os.name!='nt': self.skipTest('Windows profile requirement')
        with patch.dict(os.environ,{'PATH':'bin'},clear=True),self.assertRaises(ValueError):
            desktop_environment()

    def test_startup_lock_excludes_second_owner_and_releases(self):
        with tempfile.TemporaryDirectory() as base:
            with desktop_start_lock(base) as first:
                self.assertTrue(first)
                with desktop_start_lock(base) as second:self.assertFalse(second)
            with desktop_start_lock(base) as third:self.assertTrue(third)

    def test_startup_race_does_not_dispatch_second_launch(self):
        service=DockerService('.')
        with patch('jarvis.docker_runtime.engine_status',return_value={'status':'unavailable'}),patch('jarvis.docker_runtime.shutil.which',return_value='docker'),patch('jarvis.docker_runtime.desktop_start_lock') as lock,patch('jarvis.docker_runtime.subprocess.run') as start:
            lock.return_value.__enter__.return_value=False
            service._start()
            start.assert_not_called()
            self.assertGreater(service.next_start,0)

    def test_successful_start_uses_desktop_environment_and_hidden_flag(self):
        service=DockerService('.')
        with patch('jarvis.docker_runtime.engine_status',side_effect=[{'status':'unavailable'},{'status':'unavailable'},{'status':'available'}]),patch('jarvis.docker_runtime.shutil.which',return_value='docker'),patch('jarvis.docker_runtime.desktop_start_lock') as lock,patch('jarvis.docker_runtime.desktop_environment',return_value={'LOCALAPPDATA':'local'}) as env,patch('jarvis.docker_runtime.subprocess.run',return_value=Mock(returncode=0)) as start,patch('jarvis.recovery.record'):
            lock.return_value.__enter__.return_value=True
            service._start()
            self.assertEqual(start.call_args.kwargs['env'],{'LOCALAPPDATA':'local'})
            self.assertIn('creationflags',start.call_args.kwargs)

    def test_deliberate_shutdown_prevents_start(self):
        service = DockerService('.', stopped=lambda: True)
        with patch('jarvis.docker_runtime.subprocess.run') as start:
            self.assertTrue(service.repair())
            service._start()
            start.assert_not_called()

    def test_running_shared_engine_is_never_restarted_or_stopped(self):
        service = DockerService('.')
        with patch('jarvis.docker_runtime.engine_status', return_value={'status': 'available'}), patch('jarvis.docker_runtime.subprocess.run') as start:
            service._start()
            service.close()
            start.assert_not_called()

    def test_fault_and_backoff_without_task_replay(self):
        service = DockerService('.')
        with patch('jarvis.docker_runtime.engine_status', return_value={'status': 'unavailable'}), patch('jarvis.docker_runtime.shutil.which', return_value='docker'), patch('jarvis.docker_runtime.subprocess.run', side_effect=OSError), patch('jarvis.recovery.record'):
            service._start()
            self.assertEqual(service.attempts, 1)
            self.assertGreater(service.next_start, 0)
            self.assertFalse(service.repair())
        watchdog = Watchdog(Mock(), clock=lambda: 0)
        watchdog.register('Docker', lambda: False, lambda: False)
        watchdog.tick()
        self.assertEqual(watchdog.services['Docker']['next'], 10)

    def test_sandbox_task_is_not_replannable_after_uncertain_dispatch(self):
        self.assertFalse(replannable({'action': 'deerflow_sandbox_task'}, {}))


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.job = SandboxJob(self.temp.name)
        self.job.root.mkdir(parents=True)
        for name in ('workspace', 'outputs'):
            (self.job.root / name).mkdir()
        self.job.state.update(status='running', image='image')

    def test_no_escape_or_overwrite(self):
        self.job.observe('sandbox_write', 'a.py', 'print(1)')
        with self.assertRaises(ValueError):
            self.job.observe('sandbox_write', 'a.py', 'print(2)')
        with self.assertRaises(ValueError):
            self.job.path('../../private')
        with self.assertRaises(ValueError):
            self.job.observe('sandbox_write', 'empty.py', '')
        self.assertFalse((self.job.root / 'workspace/empty.py').exists())

    def test_free_media_spec_rejects_injection_fields_and_nonfinite_values(self):
        from jarvis.deerflow_media import validate
        with self.assertRaises(ValueError):
            validate('chart', {'labels': ['x'], 'values': [float('nan')]})
        with self.assertRaises(ValueError):
            validate('video', {'duration': 900})
        with self.assertRaises(ValueError):
            validate('pdf', {'title': 'x', 'command': 'unsafe'})
        self.assertEqual(validate('chart', {'labels': ['x'], 'values': [1]})['kind'], 'chart')

    def test_completed_and_uncertain_commands_are_not_replayed(self):
        with patch.object(self.job, 'owned', return_value={'State': {'Running': True}}), patch.object(self.job.runtime, 'cli', return_value=b'1') as call:
            self.assertEqual(self.job.execute('python -c "print(1)"'), '1')
            with self.assertRaises(ValueError):
                self.job.execute('python -c "print(1)"')
            call.assert_called_once()
        with patch.object(self.job, 'owned', return_value={'State': {'Running': True}}), patch.object(self.job.runtime, 'cli', side_effect=ValueError):
            with self.assertRaises(ValueError):
                self.job.execute('uncertain')
            self.assertEqual(self.job.state['status'], 'uncertain')
        with self.assertRaises(ValueError):
            self.job.execute('different command')

    def test_parent_cleanup_preserves_worker_checkpoint(self):
        self.job.state['calls'] = [{'command': 'done', 'status': 'completed'}]
        self.job.save()
        parent = SandboxJob(self.temp.name, self.job.identifier)
        parent.state['calls'] = []
        with patch.object(parent, 'owned', return_value={}), patch.object(parent.runtime, 'cli', return_value=b''):
            parent.close()
        saved = json.loads((self.job.root / 'state.json').read_text())
        self.assertEqual(saved['calls'][0]['command'], 'done')

    def test_input_copies_are_scoped_and_credentials_are_excluded(self):
        (self.job.root / 'uploads').mkdir()
        project = Path(self.temp.name) / 'project'
        project.mkdir()
        (project / 'data.csv').write_text('x\n1\n')
        rows = self.job.stage_inputs(project, ['data.csv'])
        self.assertEqual(rows[0]['bytes'], (project / 'data.csv').stat().st_size)
        (self.job.root / 'uploads/data.csv').write_text('copy changed')
        self.assertEqual((project / 'data.csv').read_text(), 'x\n1\n')
        for names in ([{}], ['../data.csv'], ['.env'], ['passwords.txt'], ['data.csv', 'data.csv']):
            with self.assertRaises(ValueError):
                self.job.stage_inputs(project, names)

    def test_storage_guard_stops_only_attested_owned_container(self):
        for index in range(1001):
            (self.job.root / 'outputs' / str(index)).touch()
        with patch.object(self.job.storage_stop, 'wait', return_value=False), patch.object(self.job, 'owned', return_value={'Id': 'owned-id'}), patch.object(self.job.runtime, 'cli') as cli:
            self.job._storage_guard()
            cli.assert_called_once_with(['kill', 'owned-id'], timeout=8)

    def test_live_owner_is_not_reaped(self):
        from jarvis.deerflow_sandbox import reap_orphans
        self.job.save()
        with patch('jarvis.deerflow_sandbox.RepositorySandbox.cli') as cli:
            self.assertEqual(reap_orphans(self.temp.name), 0)
            cli.assert_not_called()

    def test_delivery_uses_actual_json_instead_of_model_claim(self):
        from jarvis.deerflow import execute
        (self.job.root / 'outputs/result.json').write_text('{"value":37}')
        actions = Mock(base=self.temp.name, config={})
        with patch.object(SandboxJob, '__enter__', return_value=self.job), patch.object(SandboxJob, '__exit__'), patch('jarvis.deerflow.request', return_value={'answer': 'The value is 39.'}):
            result = json.loads(execute(actions, {'action': 'deerflow_sandbox_task', 'value': 'Create result.json'}, lambda: False))
        self.assertEqual(result['artifact_evidence'][0]['observed_json'], {'value': 37})
        self.assertNotIn('39', result['answer'])
        self.assertIn('39', (self.job.root / 'model-report.json').read_text())

    def test_dead_owner_reaping_preserves_outputs(self):
        import psutil
        from jarvis.deerflow_sandbox import reap_orphans
        self.job.save()
        output = self.job.root / 'outputs/result.txt'
        output.write_text('preserve')
        original_process = psutil.Process
        owner_pid = self.job.state['owner_pid']
        def process(pid=None):
            if pid == owner_pid:
                raise psutil.NoSuchProcess(pid)
            return original_process(pid)
        with patch('psutil.Process', side_effect=process), patch.object(SandboxJob, 'owned', return_value={'Id': 'owned-id'}), patch('jarvis.deerflow_sandbox.RepositorySandbox.cli', return_value=b'') as cli:
            self.assertEqual(reap_orphans(self.temp.name), 1)
            cli.assert_called_once_with(['rm', '--force', self.job.name], timeout=10)
        self.assertEqual(output.read_text(), 'preserve')
