from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jarvis.experience import hotness, recall_tasks
from jarvis.task_state import TaskState
from jarvis.ui_memory import UIMemory
from jarvis.brain_worker import Models


class ExperienceTests(unittest.TestCase):
    def task(self, **changes):
        return dict({"goal": "search jazz music spotify", "kind": "task", "status": "completed",
                     "updated_at": "2026-09-26T00:00:00+00:00", "result": "Playback verified",
                     "checkpoints": [{"stage": "verified"}], "plan": {"remaining": ["unsafe"]}}, **changes)

    def test_decay_handles_utc_missing_invalid_and_future_times(self):
        self.assertEqual(hotness(None, 0), 0)
        self.assertEqual(hotness("bad", 0), 0)
        self.assertEqual(hotness(float("nan"), 0), 0)
        self.assertEqual(hotness(100, 0), 1)
        self.assertEqual(hotness("1970-01-01T00:00:00+00:00", 0), 1)
        self.assertLess(hotness(0, 100 * 86400), .1)

    def test_recall_excludes_unverified_failed_unrelated_and_uncertain_tasks(self):
        good = self.task()
        tasks = [good, self.task(status="failed"), self.task(checkpoints=[]),
                 self.task(goal="create report in downloads"), self.task(kind="code_task"),
                 self.task(checkpoints=[{"stage": "verified"}, {"stage": "acting"}]),
                 self.task(failures=[{"attempted": True}])]
        result = recall_tasks(tasks, "search jazz music spotify", "task")
        self.assertEqual(result, [{"goal": good["goal"], "summary": good["result"]}])
        self.assertNotIn("plan", result[0])
        self.assertEqual(recall_tasks(tasks, "open the", "task"), [])

    def test_recall_is_bounded_deduplicated_and_read_only_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start("search jazz music spotify", "task")
            state.checkpoint("verified", evidence="playback visible")
            state.finish("completed", "Playback verified")
            state.start("search jazz music spotify again", "task")
            before = state.path.read_bytes()
            restarted = TaskState(directory)
            after_restart = restarted.path.read_bytes()
            self.assertNotEqual(before, after_restart)
            self.assertEqual(len(restarted.recall("search jazz music spotify")), 1)
            self.assertEqual(restarted.path.read_bytes(), after_restart)
        tasks = [self.task(goal="search jazz music spotify " + str(i)) for i in range(8)]
        self.assertEqual(len(recall_tasks(tasks, "search jazz music spotify", "task", limit=20)), 3)

    def test_ui_suggestion_prefers_recent_success_but_requires_unique_current_control(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            memory = UIMemory(Path(directory) / "ui.json")
            memory.save({"version": 1, "contexts": {"spotify": [
                {"name": "Old", "role": "Button", "count": 10, "last_used": time.time() - 365 * 86400},
                {"name": "New", "role": "Button", "count": 3, "last_used": time.time()}]}})
            controls = [{"name": "Old", "role": "Button"}, {"name": "New", "role": "Button"}]
            self.assertEqual(memory.candidate("spotify", controls)[0]["name"], "New")
            self.assertEqual(memory.candidate("spotify", controls + [controls[1]])[0]["name"], "Old")
            self.assertIsNone(memory.candidate("chrome", controls))

    def test_planner_receives_experience_as_untrusted_background(self):
        models = Models.__new__(Models)
        models.client = Mock()
        models.generate = Mock(return_value={"steps": []})
        experience = [{"goal": "music", "summary": "verified"}]
        with patch("jarvis.brain_worker.ensure_server", return_value={"models": [{"name": "local"}]}):
            models.predict({"operation": "plan", "options": {"planner": "local", "decision": "local"}, "experience": experience})
        args = models.generate.call_args.args
        self.assertIn("untrusted summaries", args[1])
        self.assertEqual(args[2]["experience"], experience)


if __name__ == "__main__":
    unittest.main()
