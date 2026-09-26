import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from jarvis import launcher
from jarvis.actions import Actions
from jarvis.commands import Command, parse
from jarvis.task_state import TaskState


class CrashResumeTests(unittest.TestCase):
    def test_microphone_repair_does_not_kill_active_task(self):
        from main import App
        app = App.__new__(App)
        app.listener = Mock()
        app.listener.thread.is_alive.return_value = True
        app.actions = Mock(task_active=True)
        with patch.dict(os.environ, JARVIS_SUPERVISED='1'), patch('main.os._exit') as exit:
            self.assertFalse(app.repair_listener())
            exit.assert_not_called()
            app.actions.cancel.assert_not_called()

    def test_loading_recognizer_has_grace_and_explicit_stop_cancels(self):
        from main import App
        app = App.__new__(App)
        app.listener = Mock(capture_started=False, last_audio=0, decode_started=None)
        app.listener.thread.is_alive.return_value = True
        with patch('main.time.monotonic', return_value=100):
            self.assertTrue(app.listener_healthy())
            app.listener.capture_started = True
            self.assertFalse(app.listener_healthy())
        app.actions, app.speech, app.state, app.toggle = Mock(), Mock(), Mock(), Mock()
        app.session = 0
        app.stop()
        app.actions.cancel.assert_called_once()
        self.assertFalse(app.listening_requested)

    def test_resume_retains_goal_project_and_never_replays_uncertain_action(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start('open chrome and calculator', 'task', directory)
            state.checkpoint('acting', action='open', target='chrome')
            state = TaskState(directory)
            saved = state.unfinished(automatic=True)
            self.assertEqual(saved['status'], 'interrupted')
            self.assertEqual(saved['project'], directory)
            self.assertIsNotNone(state.resume_blocker(saved))
            actions = Actions({'files_root': 'files', 'apps': {}}, directory, Mock())
            actions.brain.run = Mock()
            try:
                actions.execute(Command('resume_task', extra='automatic'))
                actions.brain.run.assert_not_called()
                self.assertEqual(actions.task_state.snapshot()['goal'], saved['goal'])
            finally:
                actions.close()

    def test_verified_task_continues_but_intentional_cancel_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start('open calculator', 'task')
            state.checkpoint('verified', action='open', target='chrome')
            actions = Actions({'files_root': 'files', 'apps': {}}, directory, Mock())
            actions.brain.run = Mock(return_value='Finished the plan')
            try:
                actions.execute(Command('resume_task', extra='automatic'))
                actions.brain.run.assert_called_once()
                self.assertEqual(actions.task_state.snapshot()['status'], 'completed')
                actions.task_state.start('open calculator', 'task')
                actions.task_state.finish('cancelled', 'Stopped by user')
                self.assertIsNone(actions.task_state.unfinished(automatic=True))
            finally:
                actions.close()

    def test_resume_phrase_does_not_capture_music_resume(self):
        self.assertEqual(parse('resume last task').kind, 'resume_task')
        self.assertNotEqual(parse('resume music').kind, 'resume_task')

    def test_supervisor_accepts_redirected_pid_past_old_timeout_and_resumes_long_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            clock = [0]
            first, second = Mock(pid=100), Mock(pid=101)
            first.poll.side_effect = lambda: None if clock[0] < 310 else 1
            first.wait.return_value = 1
            second.poll.return_value = 0
            second.wait.return_value = 0
            def heartbeat(path):
                session = path.stem.removeprefix('heartbeat-')
                return {'session': session, 'pid': 200, 'at': clock[0], 'status': 'running'}
            def sleep(seconds):
                clock[0] += seconds
            with patch.object(launcher, 'RUNTIME', runtime), patch.object(launcher, 'BASE', runtime), \
                    patch.object(launcher, 'singleton', return_value=Mock()), \
                    patch.object(launcher, 'preflight', return_value={}), \
                    patch.object(launcher, 'prepare_runtime', return_value='pythonw.exe'), \
                    patch.object(launcher, 'heartbeat_state', side_effect=heartbeat), \
                    patch.object(launcher, 'OwnedApplication') as owned, \
                    patch.object(launcher.subprocess, 'Popen', side_effect=[first, second]) as spawn, \
                    patch.object(launcher.time, 'time', side_effect=lambda: clock[0]), \
                    patch.object(launcher.time, 'sleep', side_effect=sleep), patch.object(launcher, 'record'):
                launcher.run()
                owned.return_value.attach.assert_any_call(200)
                owned.return_value.terminate.assert_not_called()
                self.assertEqual(spawn.call_args_list[1].kwargs['env']['JARVIS_RESUME_TASK'], '1')

    def test_monitor_fault_cleans_owned_process_and_stop_prevents_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            child = Mock(pid=100)
            child.poll.return_value = None
            def record(*args):
                (runtime / 'stop').touch()
            with patch.object(launcher, 'RUNTIME', runtime), patch.object(launcher, 'BASE', runtime), \
                    patch.object(launcher, 'singleton', return_value=Mock()), \
                    patch.object(launcher, 'preflight', return_value={}), \
                    patch.object(launcher, 'prepare_runtime', return_value='pythonw.exe'), \
                    patch.object(launcher, 'heartbeat_state', side_effect=OSError('injected monitor fault')), \
                    patch.object(launcher, 'OwnedApplication') as owned, \
                    patch.object(launcher.subprocess, 'Popen', return_value=child) as spawn, \
                    patch.object(launcher, 'record', side_effect=record):
                launcher.run()
                owned.return_value.terminate.assert_called_once()
                owned.return_value.close.assert_called_once()
                spawn.assert_called_once()

    @unittest.skipUnless(os.name == 'nt', 'Windows venv redirector')
    def test_actual_venv_process_is_tracked_and_terminated(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = Path(directory) / 'identity.json'
            python = Path(__file__).resolve().parents[1] / '.venv/Scripts/python.exe'
            code = 'import os,time,json,pathlib;pathlib.Path(' + repr(str(identity)) + ').write_text(json.dumps({"pid":os.getpid()}));time.sleep(60)'
            child = subprocess.Popen([str(python), '-c', code], creationflags=subprocess.CREATE_NO_WINDOW)
            owned = launcher.OwnedApplication(child)
            try:
                for _ in range(100):
                    if identity.exists():
                        break
                    time.sleep(.05)
                actual = json.loads(identity.read_text())['pid']
                self.assertNotEqual(actual, child.pid)
                owned.attach(actual)
                self.assertTrue(owned.handle)
                owned.terminate()
                child.wait(timeout=10)
            finally:
                owned.terminate()
                owned.close()


if __name__ == '__main__':
    unittest.main()
