import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory
from jarvis.task_state import TaskState


class SkillMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.memory = ObsidianMemory(self.root, {"enabled": True, "vault": "vault"})
        self.skills = SkillMemory(self.memory)
        self.memory.skills = self.skills
        self.skills.sync()

    def task(self, goal="Open Chrome and search weather", status="completed", verified=True):
        step = {"action": "search", "value": "weather", "expected": "Search results visible", "verified": True,
                "observation": {"control_id": "old-id"}}
        return {"goal": goal, "kind": "task", "status": status, "result": "Done",
                "plan": {"completed": [step]}, "checkpoints": [
                    {"stage": "procedure_surface", "screen": "Chrome"},
                    {"stage": "verified", "action": "search", "target": "weather"},
                    *([{ "stage": "goal_verified", "evidence": "Current search results confirmed"}] if verified else [])]}

    def test_sync_and_relevance(self):
        self.assertEqual(len(list(self.memory.vault.glob("Jarvis Skills/Builtins/*/SKILL.md"))), 9)
        context = self.skills.context("Search YouTube videos")
        self.assertIn("youtube-media", [s["name"] for s in context["skills"]])
        self.assertLessEqual(len(context["skills"]), 2)
        self.assertIn("[[Jarvis Skills]]", (self.memory.vault / "Jarvis Brain.md").read_text())

    def test_verified_success_updates_latest_revision(self):
        task = self.task()
        self.skills.record(task)
        task["checkpoints"][1]["target"] = "new visible results"
        self.skills.record(task)
        record = next(iter(self.skills.procedures.values()))
        self.assertEqual(record["revision"], 2)
        self.assertEqual(record["successes"], 2)
        self.assertEqual(record["steps"][0]["target"], "new visible results")
        loaded = SkillMemory(self.memory)
        self.assertEqual(loaded.procedures, self.skills.procedures)
        self.assertNotIn("old-id", json.dumps(record))

    def test_partial_failed_cancelled_or_uncertain_never_promoted(self):
        for status in ("failed", "paused", "cancelled"):
            self.skills.record(self.task(status=status))
        self.skills.record(self.task(verified=False))
        uncertain = self.task()
        uncertain["failures"] = [{"attempted": True}]
        self.skills.record(uncertain)
        self.assertEqual(self.skills.procedures, {})
        self.assertEqual(len(next((self.memory.vault / "Jarvis Executions").glob("*.jsonl")).read_text().splitlines()), 5)

    def test_failed_reuse_preserves_recipe_and_disables_fast_proposal(self):
        self.skills.record(self.task())
        self.assertIsNotNone(self.skills.proposal(self.task()["goal"], "Chrome"))
        before = next(iter(self.skills.procedures.values()))["steps"]
        self.skills.record(self.task(status="failed"))
        self.assertEqual(next(iter(self.skills.procedures.values()))["steps"], before)
        self.assertIsNone(self.skills.proposal(self.task()["goal"], "Chrome"))
        self.assertTrue(self.skills.context("Open Chrome and search weather")["procedures"])

    def test_fast_proposal_requires_exact_goal_surface_and_navigation(self):
        task = self.task()
        self.skills.record(task)
        self.assertIsNone(self.skills.proposal("Open Chrome and search tomorrow weather", "Chrome"))
        self.assertIsNone(self.skills.proposal(task["goal"], "Spotify"))
        self.assertIsNone(self.skills.proposal(task["goal"], ""))
        task["plan"]["completed"][0]["action"] = "run_command"
        self.skills.record(task)
        self.assertIsNone(self.skills.proposal(task["goal"], "Chrome"))

    def test_project_scope_is_not_reused_in_other_project(self):
        task = self.task("Fix project calculator")
        task.update(kind="code_task", project="D:/project")
        self.skills.record(task)
        self.assertFalse(self.skills.context(task["goal"], "code_task", "D:/other")["procedures"])
        self.assertTrue(self.skills.context(task["goal"], "code_task", "D:/project")["procedures"])

    def test_credentials_and_dictation_not_saved(self):
        task = self.task("Type API key super-private-value")
        task["checkpoints"][1].update(action="type_text", target="private message body")
        self.skills.record(task)
        log = next((self.memory.vault / "Jarvis Executions").glob("*.jsonl")).read_text()
        self.assertNotIn("super-private-value", log)
        self.assertNotIn("private message body", log)
        self.assertFalse(self.skills.procedures)

    def test_corruption_preserved_and_closed_memory_does_not_write(self):
        index = self.memory.vault / "Jarvis Procedures.json"
        index.write_text("broken", encoding="utf-8")
        damaged = SkillMemory(self.memory)
        damaged.safe_record(self.task())
        damaged.sync()
        self.assertTrue(damaged.error)
        self.assertEqual(index.read_text(), "broken")
        self.skills.close()
        self.skills.record(self.task())
        self.assertFalse((self.memory.vault / "Jarvis Executions").exists())

    def test_finish_callback_and_direct_execution_log(self):
        state = TaskState(self.root)
        state.on_finish = self.skills.safe_record
        state.start("test task", "task")
        state.checkpoint("goal_verified", evidence="fresh result")
        state.finish("completed", "done")
        self.assertEqual(len(self.skills.procedures), 1)
        actions = Actions.__new__(Actions)
        actions._learning_local = threading.local()
        actions.task_state = state
        actions.skills = self.skills
        actions._execute = Mock(return_value="Opened")
        self.assertEqual(actions.execute(Command("open", "notepad")), "Opened")
        lines = next((self.memory.vault / "Jarvis Executions").glob("*.jsonl")).read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertFalse(json.loads(lines[-1])["verified"])

    def test_memory_failure_does_not_fail_or_replay_external_action(self):
        self.skills.record = Mock(side_effect=OSError("disk full"))
        self.skills.safe_record(self.task())
        self.skills.record.assert_called_once()
        self.assertIn("disk full", self.memory.error)

    def test_planning_and_code_receive_relevant_skill_context(self):
        from jarvis.brain import BrainClient
        client = BrainClient.__new__(BrainClient)
        client.memory, client.options, client.worker_module = self.memory, {}, "test_worker"
        client._request_once = Mock(return_value={"steps": []})
        client.request("plan", lambda: False, goal="Search YouTube videos")
        context = client._request_once.call_args.kwargs["skill_context"]
        self.assertIn("youtube-media", [s["name"] for s in context["skills"]])
        client.request("code_edit", lambda: False, goal="Fix project code", skill_project="D:/project")
        context = client._request_once.call_args.kwargs["skill_context"]
        self.assertIn("project-coding", [s["name"] for s in context["skills"]])

    def test_tampered_navigation_target_and_expired_route_not_used(self):
        task = self.task()
        self.skills.record(task)
        item = next(iter(self.skills.procedures.values()))
        item["proposal"][0]["value"] = "unrequested destination"
        self.assertIsNone(self.skills.proposal(task["goal"], "Chrome"))
        item["proposal"][0]["value"] = "weather"
        item["updated_at"] = "2020-01-01T00:00:00+00:00"
        self.assertIsNone(self.skills.proposal(task["goal"], "Chrome"))


if __name__ == "__main__":
    unittest.main()
