from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from jarvis.model_recovery import ModelRecovery
from jarvis.recovery import Watchdog


class ModelRecoveryTests(unittest.TestCase):
    def create(self, directory, coder="Qwen3-Coder:latest"):
        config = {"brain": {"enabled": True, "planner": "planner", "coder": coder,
            "hermes": {"enabled": True, "model": "hermes"}}}
        return ModelRecovery(directory, config, Mock(), lambda: False)

    def tags(self, recovery, names):
        recovery.client = Mock()
        recovery.client.get.return_value.json.return_value = {"models": [{"name": name} for name in names]}

    def test_installed_coder_name_avoids_redundant_download(self):
        recovery = self.create(Path.cwd())
        self.tags(recovery, ["planner", "Qwen3-Coder:latest", "hermes"])
        self.assertTrue(recovery.healthy())
        self.assertEqual(recovery.missing, [])

    def test_missing_model_is_identified_and_hermes_is_included(self):
        recovery = self.create(Path.cwd(), "qwen3-coder:30b")
        self.tags(recovery, ["planner", "Qwen3-Coder:latest"])
        self.assertFalse(recovery.healthy())
        self.assertEqual(recovery.missing, ["hermes", "qwen3-coder:30b"])

    def test_async_pending_does_not_count_as_repair_failure_or_block_other_service(self):
        clock = [0]
        report, repair, other = Mock(), Mock(return_value=None), Mock()
        watchdog = Watchdog(report, clock=lambda: clock[0])
        watchdog.register("models", lambda: False, repair)
        watchdog.register("other", lambda: False, other)
        for at in (0, 5, 10):
            clock[0] = at
            watchdog.tick()
        self.assertEqual(watchdog.services["models"]["failures"], 0)
        self.assertFalse(any("not repaired yet" in call.args[1] and "models" in call.args[1] for call in report.call_args_list))
        self.assertTrue(other.called)
        watchdog.close()
        count = repair.call_count
        watchdog.tick()
        self.assertEqual(repair.call_count, count)

    def test_download_in_progress_and_cooldown_are_pending(self):
        recovery = self.create(Path.cwd())
        recovery.thread = Mock()
        recovery.thread.is_alive.return_value = True
        self.assertIsNone(recovery.repair())
        recovery.thread = None
        recovery.next_attempt = float("inf")
        self.assertIsNone(recovery.repair())

    def test_shutdown_prevents_download_launch(self):
        recovery = self.create(Path.cwd())
        recovery.closing = lambda: True
        with patch("jarvis.model_recovery.threading.Thread") as thread:
            self.assertFalse(recovery.repair())
            thread.assert_not_called()

    def test_failed_download_reports_real_cooldown_and_preserves_other_work(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".jarvis-runtime").mkdir()
            recovery = self.create(directory)
            recovery.missing = ["coder"]
            process = Mock()
            process.poll.return_value = 1
            process.returncode = 1
            with patch("jarvis.model_recovery.subprocess.Popen", return_value=process), patch("jarvis.model_recovery.time.monotonic", return_value=100):
                recovery.download()
            self.assertEqual(recovery.next_attempt, 400)
            self.assertIsNone(recovery.process)
            self.assertIn("next attempt in 300 seconds", recovery.report.call_args.args[1])
            process.kill.assert_not_called()
