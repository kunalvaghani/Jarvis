import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jarvis.actions import Actions
from jarvis.brain import explicit_file_plan, validate_plan
from jarvis.catalog import Catalog
from jarvis.clarification import TaskClarification
from jarvis.commands import Command
from jarvis.engine import Engine


class ClarificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.downloads = self.base / "Downloads"
        self.downloads.mkdir()
        self.events = []
        self.actions = Actions({"files_root": "files", "apps": {},
            "folders": {"downloads": str(self.downloads)},
            "brain": {"enabled": True, "planner": "planner", "decision": "decision"}},
            self.base, lambda *event: self.events.append(event))

    def test_reported_utterance_runs_file_workflow_without_explorer_or_coder(self):
        brain = self.actions.brain
        brain.options["adaptive_planning"] = True
        brain.observe = Mock(return_value=(0, {}))
        brain.client = Mock()
        brain.client.request.return_value = {"approved": True, "verified": True}
        spoken = "Hey Jarvis, open folder downloads, create a file called JarvisTest .txt there and write hello kunal in it."
        engine = Engine(self.actions.submit, Mock())
        with patch("jarvis.actions.os.startfile") as launch, patch("jarvis.coder.Coder.run") as coder, patch("jarvis.brain.time.sleep"):
            engine.feed(spoken, final=True)
            _, command = self.actions.queue.get_nowait()
            result = self.actions.execute(command)
        self.assertIn("Finished", result)
        self.assertEqual((self.downloads / "JarvisTest.txt").read_text(), "hello kunal")
        launch.assert_called_once_with(str(self.downloads))
        coder.assert_not_called()
        self.assertNotIn("plan", [call.args[0] for call in brain.client.request.call_args_list])
        self.assertNotIn("replan", [call.args[0] for call in brain.client.request.call_args_list])

    def test_missing_folder_answer_continues_the_original_file_task(self):
        brain = self.actions.brain
        brain.observe = Mock(return_value=(0, {}))
        brain.client = Mock()
        brain.client.request.return_value = {"approved": True, "verified": True}
        original = "Create a file called greeting.txt and write hello"
        self.assertIn("waiting for your answer", self.actions.execute(Command("task", original)))
        self.assertEqual(self.actions.task_state.snapshot()["status"], "paused")
        self.actions.submit(Command("ask", "Downloads"))
        self.actions.knowledge.cancel()  # No answer is sent to the knowledge worker.
        _, reply = self.actions.queue.get_nowait()
        self.assertEqual(reply.kind, "clarified_task")
        with patch("jarvis.brain.time.sleep"):
            self.actions.execute(reply)
        self.assertEqual((self.downloads / "greeting.txt").read_text(), "hello")
        self.assertIsNone(self.actions.pending_question)

    def test_invalid_folder_answer_keeps_question_pending(self):
        self.actions.brain.run = Mock(side_effect=TaskClarification("Which folder?", "folder"))
        self.actions.execute(Command("task", "Create a file called a.txt and write hi"))
        reply = self.actions._resolve_reply(Command("task", "unknown-folder"))
        self.assertEqual(reply.kind, "clarification_blocked")
        self.assertIsNotNone(self.actions.pending_question)

    def test_number_name_and_ordinal_answer_choose_pending_open(self):
        choices = [Command("open_folder", "Downloads"), Command("open_folder", "Documents")]
        for text, expected in [("one", "1"), ("the second one", "2"), ("Documents", "2"), ("I choose Downloads", "1")]:
            with self.subTest(text=text):
                self.actions.pending_open = {"time": time.monotonic(), "choices": choices}
                self.assertEqual(self.actions._resolve_reply(Command("ask", text)), Command("choose_control", expected))

    def test_pending_project_and_ui_replies_do_not_become_questions(self):
        self.actions.projects.pending = {"time": time.monotonic(), "choices": [Path("Alpha"), Path("Beta")]}
        self.assertEqual(self.actions._resolve_reply(Command("task", "second")), Command("choose_control", "2"))
        self.actions.projects.pending = None
        self.actions.ui_controls = Mock()
        self.actions.ui_controls.pending = {"time": time.monotonic(), "choices": [{"name": "Save draft"}]}
        self.assertEqual(self.actions._resolve_reply(Command("ask", "Save draft")), Command("choose_control", "1"))

    def test_expired_choices_are_not_answered_as_general_queries(self):
        self.actions.pending_open = {"time": time.monotonic()-46, "choices": [Command("open_folder", "Downloads")]}
        reply = self.actions._resolve_reply(Command("ask", "one"))
        self.assertEqual(reply.kind, "clarification_blocked")
        self.assertIn("expired", reply.value)

    def test_planner_question_is_retained_and_short_answer_replans(self):
        brain = self.actions.brain
        brain.observe = Mock(return_value=(0, {}))
        brain.client = Mock()
        brain.client.request.return_value = {"question": "Which music genre?", "steps": []}
        self.actions.execute(Command("task", "Find some music for me"))
        reply = self.actions._resolve_reply(Command("task", "jazz"))
        self.assertEqual(reply.kind, "clarified_task")
        self.assertIn("Find some music for me", reply.value)
        self.assertIn("Your answer: jazz", reply.value)

    def test_uncertain_external_action_cannot_be_replayed_by_an_answer(self):
        def ask_after_uncertain_action(*args):
            self.actions.task_state.checkpoint("acting", action="create_file", target="a.txt")
            raise TaskClarification("Which folder?", "folder")
        self.actions.brain.run = Mock(side_effect=ask_after_uncertain_action)
        self.actions.execute(Command("task", "Create a file"))
        reply = self.actions._resolve_reply(Command("task", "Downloads"))
        self.assertEqual(reply.kind, "clarification_blocked")
        self.assertIn("not verified", reply.value)

    def test_new_question_clears_pending_task(self):
        self.actions.brain.run = Mock(side_effect=TaskClarification("Which folder?", "folder"))
        self.actions.execute(Command("task", "Create a file"))
        question = Command("ask", "What is Python?")
        self.assertEqual(self.actions._resolve_reply(question), question)
        self.assertIsNone(self.actions.pending_question)

    def test_full_folder_path_works_without_catalog(self):
        self.assertEqual(Catalog({}, self.base).resolve(str(self.downloads), "folder"), str(self.downloads))

    def test_python_purpose_answer_is_used_instead_of_repeating_question(self):
        from jarvis.coder import python_file_request
        self.actions.execute(Command("task", "Create a Python file with code"))
        reply = self.actions._resolve_reply(Command("task", "calculator"))
        self.assertEqual(reply.kind, "clarified_task")
        self.assertEqual(python_file_request(reply.value), "calculator.py")

    def test_invalid_option_keeps_list_and_pointer_selection_is_not_a_number(self):
        self.actions.pending_open = {"time": time.monotonic(), "choices": [Command("open_folder", "Downloads")]}
        self.assertEqual(self.actions._resolve_reply(Command("ask", "two")).kind, "clarification_blocked")
        self.assertIsNotNone(self.actions.pending_open)
        pointer = Command("select_context", "this:option", "select")
        self.assertEqual(self.actions._resolve_reply(pointer), pointer)

    def test_ambiguous_folder_question_happens_before_any_action(self):
        from jarvis.catalog import AmbiguousName
        self.actions.catalog.resolve = Mock(side_effect=AmbiguousName("shared", [str(self.downloads), str(self.actions.root)]))
        self.actions.execute(Command("task", "Create a file called a.txt in shared and write hi"))
        self.assertEqual(self.actions.pending_question["choices"], [str(self.downloads), str(self.actions.root)])
        self.assertIsNone(self.actions.task_state.resume_blocker(self.actions.pending_question["source"]))

    def test_decision_worker_receives_supported_catalog_and_step_scope(self):
        from jarvis.brain_worker import Models
        models = Models.__new__(Models)
        models.client = Mock()
        models.generate = Mock(return_value={"approved": True})
        catalog = [{"action": "create_file", "description": "Write a named new file"}]
        with patch("jarvis.brain_worker.ensure_server", return_value={"models": [{"name": "model"}]}):
            models.predict({"operation": "decide", "options": {"decision": "model"}, "goal": "Create a file",
                "step": {"action": "create_file"}, "screen": {}, "candidates": [], "tools": catalog})
        self.assertEqual(models.generate.call_args.args[2]["tools"], catalog)
        self.assertIn("Check this one step", models.generate.call_args.args[1])

    def test_expired_task_question_and_cancel_cannot_resume(self):
        self.actions.brain.run = Mock(side_effect=TaskClarification("Which folder?", "folder"))
        self.actions.execute(Command("task", "Create a file"))
        self.actions.pending_question["time"] -= 181
        self.assertEqual(self.actions._resolve_reply(Command("ask", "Downloads")).kind, "clarification_blocked")
        self.actions.execute(Command("task", "Create a file"))
        self.actions.cancel()
        self.assertIsNone(self.actions.pending_question)

    def test_folder_choice_resolves_to_exact_path(self):
        paths = [str(self.downloads), str(self.actions.root)]
        self.actions.brain.run = Mock(side_effect=TaskClarification("Which folder?", "folder"))
        self.actions.execute(Command("task", "Create a file called a.txt in shared and write hi"))
        self.actions.pending_question["choices"] = paths
        reply = self.actions._resolve_reply(Command("choose_control", "2"))
        plan = explicit_file_plan(reply.value)
        self.assertEqual(plan["steps"][0]["folder"], paths[1])

    def test_create_plan_preserves_content_punctuation_and_destination(self):
        plan = explicit_file_plan("Create a file called notes.txt in Downloads and write Hello.")
        step = validate_plan(plan)[0]
        self.assertEqual((step["folder"], step["content"]), ("Downloads", "Hello."))


if __name__ == "__main__":
    unittest.main()
