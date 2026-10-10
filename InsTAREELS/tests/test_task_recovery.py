import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jarvis.brain import Brain
from jarvis.task_state import TaskState


class TaskRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.actions = Mock()
        self.actions.apps = {"chrome": ["chrome.exe"]}
        self.actions.pending_open = None
        self.actions.execute.return_value = "Opened Chrome"
        self.actions.last_created = self.actions.last_modified = self.actions.last_deleted = self.actions.last_command = None
        self.state = self.actions.task_state = TaskState(self.directory.name)
        self.state.start("open chrome", "task")
        self.brain = Brain(self.actions, Path(self.directory.name), {
            "enabled": True, "task_recovery": True, "planner": "planner", "decision": "decision"})
        self.brain.client = Mock()
        self.brain.observe = Mock(return_value=(123, {"title": "Chrome", "signature": "a", "controls": []}))
        self.missing = {"action": "select", "value": "Launch Chrome", "expected": "Chrome visible"}
        self.open = {"action": "open", "value": "chrome", "expected": "Chrome visible"}

    def run_task(self):
        with patch("jarvis.brain.time.sleep"):
            return self.brain.run("open chrome", lambda: False)

    def test_missing_control_uses_fresh_alternative_and_records_failure(self):
        self.brain.client.request.side_effect = [
            {"steps": [self.missing]}, {"done": False, "steps": [self.open], "reason": "Use installed app launcher"},
            {"approved": True}, {"verified": True}, {"verified": True}]
        self.assertIn("Finished", self.run_task())
        self.actions.execute.assert_called_once()
        self.assertEqual(self.actions.execute.call_args.args[0].value, "chrome")
        request = self.brain.client.request.call_args_list[1]
        self.assertEqual(request.args[0], "replan")
        self.assertFalse(request.kwargs["failures"][0]["attempted"])
        self.assertEqual(request.kwargs["screen"]["title"], "Chrome")
        self.assertEqual(self.state.snapshot()["failures"][0]["outcome"], "not_executed")

    def test_repeated_failed_action_rejected_before_any_dispatch(self):
        self.brain.client.request.side_effect = [
            {"steps": [self.missing]}, {"done": False, "steps": [self.missing]}, {"done": False, "steps": [self.missing]}]
        with self.assertRaisesRegex(ValueError, "already failed"):
            self.run_task()
        self.actions.execute.assert_not_called()
        # The repeat is fed back once as a correction before the task pauses.
        self.assertIn("already failed", self.brain.client.request.call_args_list[2].kwargs["plan_validation_error"])

    def test_tool_exception_is_uncertain_and_never_replayed(self):
        # An uncertain navigation step is re-planned from fresh state, never resent.
        self.actions.execute.side_effect = OSError("worker broke after dispatch")
        self.brain.client.request.side_effect = [{"steps": [self.open]}, {"approved": True},
            {"done": False, "steps": [self.open]}, {"done": True, "steps": []}, {"verified": True}]
        self.assertIn("Finished", self.run_task())
        self.actions.execute.assert_called_once()
        self.assertEqual(self.state.snapshot()["failures"][0]["outcome"], "uncertain")
        self.assertEqual([call.args[0] for call in self.brain.client.request.call_args_list],
                         ["plan", "decide", "replan", "replan", "verify"])

    def test_uncertain_write_still_pauses_without_replanning(self):
        from jarvis.task_recovery import TaskFailure
        write = {"action": "create_file", "value": "notes.txt", "folder": "Downloads", "content": "", "expected": "File"}
        with self.assertRaisesRegex(ValueError, "may have taken effect"):
            self.brain.recover_task("open chrome", write, TaskFailure("broke", attempted=True), [], [], [], [], 1, lambda: False)
        self.brain.client.request.assert_not_called()
        self.brain.observe.assert_not_called()

    def test_unverified_effect_is_recorded_without_another_action(self):
        self.brain.client.request.side_effect = [
            {"steps": [self.open]}, {"approved": True}, {"verified": False, "reason": "No proof"},
            {"done": True, "steps": []}, {"verified": True}]
        self.assertIn("Finished", self.run_task())
        self.actions.execute.assert_called_once()
        self.assertTrue(self.state.snapshot()["failures"][0]["attempted"])

    def test_recovery_stops_after_configured_alternative_plans(self):
        self.brain.options["max_recoveries"] = 2
        second = {**self.missing, "value": "Different launch control"}
        third = {**self.missing, "value": "Third launch control"}
        self.brain.client.request.side_effect = [
            {"steps": [self.missing]}, {"done": False, "steps": [second]}, {"done": False, "steps": [third]}]
        with self.assertRaisesRegex(ValueError, "recovery limit"):
            self.run_task()
        self.assertEqual(len(self.state.snapshot()["failures"]), 3)
        self.actions.execute.assert_not_called()

    def test_recovery_cannot_invent_command_execution(self):
        unsafe = {"action": "run_command", "value": "echo hello", "expected": "output"}
        self.brain.client.request.side_effect = [
            {"steps": [self.missing]}, {"done": False, "steps": [unsafe]}]
        with self.assertRaisesRegex(ValueError, "not explicitly requested"):
            self.run_task()
        self.actions.execute.assert_not_called()

    def test_decision_rejection_replans_but_alternative_is_checked_again(self):
        other = {"action": "open", "value": "edge", "expected": "Browser visible"}
        self.actions.apps["edge"] = ["msedge.exe"]
        self.brain.client.request.side_effect = [{"steps": [self.open]}, {"approved": False, "reason": "Unrelated"},
            {"done": False, "steps": [other]}, {"approved": False, "reason": "Still unrelated"},
            {"done": False, "steps": [self.open]}, {"done": False, "steps": [other]}]
        with self.assertRaisesRegex(ValueError, "already failed"):
            self.run_task()
        operations = [call.args[0] for call in self.brain.client.request.call_args_list]
        self.assertEqual(operations.count("decide"), 2)  # The alternative did not bypass the check.
        self.actions.execute.assert_not_called()

    def test_failure_memory_survives_restart_without_replaying(self):
        self.state.record_failure({**self.open, "attempted": True, "reason": "uncertain"})
        restarted = TaskState(self.directory.name)
        self.assertEqual(restarted.snapshot()["status"], "interrupted")
        restarted.start("open chrome", "task")
        self.assertTrue(restarted.previous("open chrome", "task")["failures"][0]["attempted"])

    def test_cancel_before_recovery_never_calls_planner(self):
        from jarvis.task_recovery import TaskFailure
        with self.assertRaisesRegex(ValueError, "cancelled"):
            self.brain.recover_task("open chrome", self.missing, TaskFailure("missing"), [], [], [], [], 1, lambda: True)
        self.brain.client.request.assert_not_called()
        self.actions.execute.assert_not_called()

    def test_repeat_cannot_bypass_block_by_changing_unused_fields(self):
        from jarvis.task_recovery import action_key
        self.assertEqual(action_key(self.missing), action_key({**self.missing, "browser": "edge", "folder": "dummy", "content": "ignored"}))

    def test_read_error_after_dispatch_is_recorded_as_uncertain(self):
        self.brain.observe_after_action = Mock(side_effect=OSError("observation process broke"))
        self.brain.client.request.side_effect = [{"steps": [self.open]}, {"approved": True},
            {"done": True, "steps": []}, {"verified": True}]
        self.assertIn("Finished", self.run_task())
        self.assertTrue(self.state.snapshot()["failures"][0]["attempted"])
        self.actions.execute.assert_called_once()

    def test_screen_recovery_uses_fresh_vision_before_proposing_alternative(self):
        from jarvis.task_recovery import TaskFailure
        self.brain.options["screen_aware"] = True
        self.brain.visual_screen = Mock(return_value={"title": "Desktop", "image": "synthetic", "controls": []})
        self.brain.client.request.side_effect = [{"summary": "No shortcut visible"}, {"done": False, "steps": [self.open]}]
        steps, _, capture = self.brain.recover_task("open chrome", self.missing,
            TaskFailure("missing"), [], [], [self.missing], ["chrome"], 1, lambda: False)
        self.assertEqual(steps, [self.open])
        self.assertEqual(capture["summary"], "No shortcut visible")
        self.assertEqual([call.args[0] for call in self.brain.client.request.call_args_list], ["visual", "replan"])
        self.actions.execute.assert_not_called()
