from tests.layout_fixtures import fixture_path
import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from jarvis.recovery import Watchdog, restart_thread, ui_loop
from jarvis.launcher import preflight, supervised_restart, singleton
import jarvis.launcher as launcher


class RecoveryTests(unittest.TestCase):
    def test_atomic_source_snapshot_preserves_previous_backup_after_failed_copy(self):
        from jarvis.launcher import source_snapshot
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'current.py'
            saved = Path(directory)/'saved.py'
            source.write_text('new = True\n')
            saved.write_text('known_good = True\n')
            def incomplete(src,dst):
                Path(dst).write_text('partial')
                raise OSError('injected copy failure')
            with patch('jarvis.launcher.shutil.copy2',side_effect=incomplete):
                with self.assertRaises(OSError): source_snapshot(source,saved)
            self.assertEqual(saved.read_text(),'known_good = True\n')
            self.assertEqual(list(Path(directory).glob('.jarvis-snapshot-*')),[])
            source_snapshot(source,saved)
            self.assertEqual(saved.read_text(),source.read_text())

    def test_independent_bootstrap_restores_launcher_before_import(self):
        from jarvis_bootstrap import restore_entrypoints
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "jarvis").mkdir()
            (base / ".jarvis-runtime/sources/jarvis").mkdir(parents=True)
            for name in ("__init__.py", "paths.py", "recovery.py", "launcher.py"):
                (base / "jarvis" / name).write_text("pass\n")
                (base / ".jarvis-runtime/sources/jarvis" / name).write_text("pass\n")
            (base / "jarvis/launcher.py").write_text("def broken(\n")
            restore_entrypoints(base)
            self.assertEqual((base / "jarvis/launcher.py").read_text(), "pass\n")
            self.assertIn("Restored invalid launcher", (base / ".jarvis-runtime/repairs.jsonl").read_text())

    def test_stop_interrupts_owned_setup_process(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            child = Mock()
            child.poll.return_value = None
            def stop(_):
                (runtime / "stop").touch()
            with patch.object(launcher, "RUNTIME", runtime), \
                 patch.object(launcher.subprocess, "Popen", return_value=child), \
                 patch.object(launcher.time, "sleep", side_effect=stop):
                with self.assertRaises(InterruptedError):
                    launcher.runtime_command(["owned-setup"], Mock())
            child.terminate.assert_called_once()
            child.wait.assert_called_once()

    def test_ui_loop_recovers_without_replaying_external_actions(self):
        class App:
            closing = False
            ui_failures = {}
            root = Mock()
        app = App()
        callback = Mock(side_effect=[RuntimeError("display failed"), None])
        callback.__name__ = "display_tick"
        wrapped = ui_loop(80)(callback)
        with patch("jarvis.recovery.record"):
            wrapped(app)
            app.root.after.assert_called_once()
            retry = app.root.after.call_args.args[1]
            retry()
        self.assertEqual(callback.call_count, 2)
        app.closing = True
        wrapped(app)
        self.assertEqual(callback.call_count, 2)

    def test_repair_is_verified_and_reported_only_after_recovery(self):
        report, health = Mock(), [False]
        def fix():
            health[0] = True
            return True
        watchdog = Watchdog(report)
        watchdog.register("worker", lambda: health[0], fix)
        watchdog.tick()
        self.assertIn("was stopped and fixed", report.call_args.args[1])
        watchdog.tick()
        self.assertEqual(report.call_count, 2)

    def test_failed_repair_backs_off_and_intentional_stop_is_respected(self):
        now, enabled = [0], [True]
        repair = Mock(return_value=False)
        watchdog = Watchdog(Mock(), clock=lambda: now[0])
        watchdog.register("worker", lambda: False, repair, lambda: enabled[0])
        watchdog.tick()
        watchdog.tick()
        repair.assert_called_once()
        now[0] = 20
        enabled[0] = False
        watchdog.tick()
        repair.assert_called_once()
        enabled[0] = True
        watchdog.tick()
        self.assertEqual(repair.call_count, 2)
        watchdog.close()
        now[0] = 1000
        watchdog.tick()
        self.assertEqual(repair.call_count, 2)

    def test_async_repair_is_announced_when_later_health_check_succeeds(self):
        report, health = Mock(), [False]
        watchdog = Watchdog(report)
        watchdog.register("models", lambda: health[0], lambda: False)
        watchdog.tick()
        health[0] = True
        watchdog.tick()
        self.assertIn("was stopped and fixed", report.call_args.args[1])

    def test_dead_worker_restarts_without_replaying_queued_actions(self):
        class Worker:
            def __init__(self):
                self.closed = threading.Event()
                self.queue = queue.Queue()
                self.queue.put("old click")
                self.thread = threading.Thread(target=lambda: None)
                self.generation = 0
                self.ran = threading.Event()
            def cancel(self):
                self.generation += 1
            def _run(self):
                self.ran.set()
                self.closed.wait(2)
        worker = Worker()
        self.assertTrue(restart_thread(worker, "test-worker"))
        self.assertTrue(worker.ran.wait(1))
        self.assertTrue(worker.queue.empty())
        self.assertEqual(worker.generation, 1)
        self.assertFalse(restart_thread(worker, "test-worker"))
        worker.closed.set()
        worker.thread.join(1)
        self.assertFalse(restart_thread(worker, "test-worker"))

    def test_syntax_and_config_repair_preserve_damaged_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "jarvis").mkdir()
            config = {"apps": {}, "whisper": {}, "model_path": "models/test"}
            (fixture_path(base / "config/config.json")).write_text(json.dumps(config))
            (base / "main.py").write_text("pass\n")
            preflight(base)
            (base / "main.py").write_text("def broken(\n")
            preflight(base)
            self.assertEqual((base / "main.py").read_text(), "pass\n")
            self.assertEqual(len(list((base / ".jarvis-runtime/damaged").iterdir())), 1)
            (fixture_path(base / "config/config.json")).write_text("broken")
            preflight(base)
            self.assertEqual(json.loads((base / "config/config.json").read_text()), config)
            self.assertEqual(len(list((base / ".jarvis-runtime").glob("config.damaged.*"))), 1)

    def test_stop_prevents_supervisor_restart(self):
        self.assertFalse(supervised_restart(1, True))
        self.assertFalse(supervised_restart(0, False))
        self.assertTrue(supervised_restart(1, False))

    @unittest.skipUnless(os.name == "nt", "Windows lock")
    def test_second_launcher_cannot_acquire_live_instance_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock"
            first = singleton(path)
            try:
                self.assertIsNotNone(first)
                self.assertIsNone(singleton(path))
            finally:
                first.close()

    def test_supervisor_restarts_crashed_owned_process_then_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            runtime = base / ".jarvis-runtime"
            runtime.mkdir()
            children = []
            def spawn(*args, **kwargs):
                child = Mock()
                code = 1 if not children else 0
                child.poll.return_value = code
                child.wait.return_value = code
                children.append(child)
                self.assertEqual(kwargs["env"]["JARVIS_SUPERVISED"], "1")
                return child
            with patch.object(launcher, "BASE", base), patch.object(launcher, "RUNTIME", runtime), \
                 patch.object(launcher, "singleton", return_value=Mock()), \
                 patch.object(launcher, "preflight", return_value={}), \
                 patch.object(launcher, "prepare_runtime", return_value=base / "pythonw.exe"), \
                 patch.object(launcher.subprocess, "Popen", side_effect=spawn), \
                 patch.object(launcher.time, "sleep"):
                launcher.run()
            self.assertEqual(len(children), 2)
            self.assertIn("stopped unexpectedly", (runtime / "repairs.jsonl").read_text())

    def test_inference_transport_retries_without_dispatching_actions(self):
        from jarvis.brain import BrainClient
        with tempfile.TemporaryDirectory() as directory:
            client = BrainClient(directory, {})
            client._request_once = Mock(side_effect=[ValueError("Brain worker stopped"), {"verified": True}])
            client.close = Mock()
            self.assertEqual(client.request("verify", lambda: False), {"verified": True})
            self.assertEqual(client._request_once.call_count, 2)
            client._request_once.reset_mock(side_effect=True)
            client._request_once.side_effect = ValueError("Task cancelled.")
            with self.assertRaises(ValueError):
                client.request("verify", lambda: True)
            client._request_once.assert_called_once()
