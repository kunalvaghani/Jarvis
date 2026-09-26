import json
from pathlib import Path
import tempfile
import unittest

from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.task_state import TaskState


class TaskStateTests(unittest.TestCase):
    def test_completed_task_emits_spoken_reply_and_keeps_action_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            events = []
            actions = Actions({"files_root": "files", "apps": {}}, directory, lambda *args: events.append(args))
            actions.brain.run = lambda goal, cancelled: "Finished. Your request is complete."
            try:
                actions.start()
                actions.submit(Command("task", "open calculator"))
                actions.queue.join()
                self.assertIn(("spoken_reply", "Finished. Your request is complete."), events)
                self.assertIn(("action", "Finished. Your request is complete."), events)
            finally:
                actions.close()

    def test_plan_revisions_survive_restart_as_context_not_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start("open two apps", "task")
            remaining = [{"action": "open", "value": "calculator"}]
            done = [{"action": "open", "value": "chrome", "verified": True}]
            state.update_plan(remaining, done, "Chrome verified")
            remaining.clear()
            restarted = TaskState(directory)
            self.assertEqual(restarted.snapshot()["status"], "interrupted")
            self.assertEqual(restarted.snapshot()["plan"]["remaining"][0]["value"], "calculator")
            restarted.start("open two apps", "task")
            self.assertEqual(restarted.previous("open two apps", "task")["plan"]["completed"], done)

    def test_restart_marks_unfinished_task_and_preserves_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start("Create a calculator", "task")
            state.checkpoint("created_draft", target="calculator.py")
            restarted = TaskState(directory)
            current = restarted.snapshot()
            self.assertEqual(current["status"], "interrupted")
            self.assertEqual(current["checkpoints"][0]["target"], "calculator.py")
            restarted.start("Add a UI", "task")
            restarted.finish("completed", "UI added")
            self.assertEqual(restarted.snapshot()["status"], "completed")
            saved = json.loads((Path(directory) / "task_state.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["history"][0]["status"], "interrupted")

    def test_previous_context_only_for_same_unfinished_goal(self):
        with tempfile.TemporaryDirectory() as directory:
            state = TaskState(directory)
            state.start("Open the second video", "task")
            state.checkpoint("verified", action="open", target="YouTube", screen="Chrome")
            state.finish("paused", "The next result was ambiguous")
            state.start("Open the second video", "task")
            prior = state.previous("Open the second video", "task")
            self.assertEqual(prior["checkpoints"][0]["screen"], "Chrome")
            self.assertIsNone(state.previous("A different goal", "task"))

    def test_action_task_records_failure_and_success(self):
        with tempfile.TemporaryDirectory() as directory:
            actions = Actions({"files_root": "files", "apps": {}}, directory, lambda *args: None)
            actions.brain.run = lambda goal, cancelled: "Finished the plan"
            self.assertEqual(actions.execute(Command("task", "open calculator")), "Finished the plan")
            self.assertEqual(actions.task_state.snapshot()["status"], "completed")
            def fail(goal, cancelled):
                raise ValueError("Planner failed")
            actions.brain.run = fail
            with self.assertRaisesRegex(ValueError, "Planner failed"):
                actions.execute(Command("task", "open calculator"))
            current = actions.task_state.snapshot()
            self.assertEqual(current["status"], "failed")
            self.assertEqual(current["result"], "Planner failed")
            def pause(goal, cancelled):
                raise ValueError("Task paused after the last verified action: replanner stopped")
            actions.brain.run = pause
            with self.assertRaisesRegex(ValueError, "Task paused"):
                actions.execute(Command("task", "open calculator"))
            self.assertEqual(actions.task_state.snapshot()["status"], "paused")
            actions.close()


if __name__ == "__main__":
    unittest.main()
