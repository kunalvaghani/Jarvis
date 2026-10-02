from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jarvis.actions import Actions
from jarvis.brain import Brain, explicit_command_plan, explicit_file_plan, normalize_plan, validate_plan
from jarvis.brain_worker import Models
from jarvis.commands import Command
from jarvis.engine import Engine


class PlanTests(unittest.TestCase):
    def test_configured_coder_handles_project_edits_and_code_drafts(self):
        models = Models.__new__(Models)
        models.client = Mock()
        models.generate = Mock(return_value={"content": "", "explanation": ""})
        installed = {"models": [{"name": "qwen3.5:4b"}, {"name": "qwen3-coder:30b"}]}
        options = {"planner": "qwen3.5:4b", "coder": "qwen3-coder:30b"}
        with patch("jarvis.brain_worker.ensure_server", return_value=installed):
            models.predict({"operation": "code_edit", "options": options, "path": "app.py"})
            self.assertEqual(models.generate.call_args.args[0], "qwen3-coder:30b")
            models.predict({"operation": "tool_text", "options": options, "tool": "write_code"})
            self.assertEqual(models.generate.call_args.args[0], "qwen3-coder:30b")
            models.predict({"operation": "tool_text", "options": options, "tool": "think"})
            self.assertEqual(models.generate.call_args.args[0], "qwen3.5:4b")

    def test_missing_configured_coder_does_not_switch_to_planner(self):
        models = Models.__new__(Models)
        models.client = Mock()
        installed = {"models": [{"name": "qwen3.5:4b"}]}
        with patch("jarvis.brain_worker.ensure_server", return_value=installed):
            with self.assertRaisesRegex(ValueError, "qwen3-coder:30b"):
                models.predict({"operation": "code_plan", "options":
                    {"planner": "qwen3.5:4b", "coder": "qwen3-coder:30b"}})

    def test_planning_schema_allows_only_supplied_configured_tools(self):
        from jarvis.brain_worker import SCHEMAS
        models = Models.__new__(Models)
        models.client = Mock()
        with patch("jarvis.brain_worker.chat", return_value='{"question":"","steps":[]}') as generate:
            models.generate("planner", "Plan", {"tools": [{"action": "read_file"}, {"action": "write_tests"}]}, "plan")
        settings = generate.call_args.args[1]
        actions = settings["format_schema"]["properties"]["steps"]["items"]["properties"]["action"]["enum"]
        self.assertEqual(actions, ["read_file", "write_tests"])
        self.assertEqual(settings["num_ctx"], 16384)
        self.assertIn("slack_send", SCHEMAS["plan"]["properties"]["steps"]["items"]["properties"]["action"]["enum"])

    def test_exact_file_requests_keep_filename_and_replacement(self):
        delete = explicit_file_plan("Delete file old.txt in Downloads")
        self.assertEqual(delete["steps"][0]["action"], "delete_file")
        self.assertEqual(delete["steps"][0]["value"], "old.txt")
        edit = explicit_file_plan("Modify file notes.txt in Documents: replace old with new")
        self.assertEqual(edit["steps"][0]["find"], "old")
        self.assertEqual(edit["steps"][0]["content"], "new")
        self.assertEqual(edit["steps"][0]["folder"], "Documents")
        sentence = explicit_file_plan("Modify file notes.txt in Documents: replace old. with new.")
        self.assertEqual(sentence["steps"][0]["content"], "new.")
        full = explicit_file_plan("Overwrite file notes.txt in Documents with content Hello.")
        self.assertEqual(full["steps"][0]["content"], "Hello.")
        command = explicit_command_plan("Run command echo hello")
        self.assertEqual(command["steps"][0]["value"], "echo hello")

    def test_visual_model_accepts_structured_result_in_thinking_field(self):
        models = Models.__new__(Models)
        models.client = Mock()
        response = models.client.post.return_value
        response.json.return_value = {"message": {"content": "", "thinking":
            '{"summary":"Calculator is visible","step_verified":true,"goal_done":false,"reason":"button shown"}'}}
        with patch("jarvis.brain_worker.ensure_server", return_value={"models": [{"name": "qwen3-vl:4b"}]}):
            result = models.predict({"operation": "visual", "options": {"screen_model": "qwen3-vl:4b"},
                "goal": "find button", "step": None, "completed": [], "previous": None,
                "screen": {"title": "Calculator", "ocr": "7", "controls": ["7"], "image": "jpeg"}})
        self.assertEqual(result["summary"], "Calculator is visible")

    def test_normalizes_redundant_browser_open_and_incomplete_music_search(self):
        steps = [{"action": "open", "value": "chrome", "expected": "Chrome open"},
                 {"action": "media_search", "value": "lo-fi focus", "browser": "chrome", "platform": "spotify",
                  "expected": "Results"}]
        normalized = normalize_plan(steps, "Play lo-fi focus on Spotify")
        self.assertEqual([s["action"] for s in normalized], ["media_search", "select"])
        self.assertEqual(normalized[1]["value"], "lo-fi focus result")

    def test_normalizes_selected_folder_without_launching_it(self):
        steps = [{"action": "open", "value": "this folder", "expected": "Open"},
                 {"action": "create_file", "value": "log.txt", "folder": "this folder",
                  "content": "hello", "expected": "File exists"}]
        self.assertEqual([s["action"] for s in normalize_plan(steps, "Create log.txt in this folder")], ["create_file"])

    def test_trims_only_unrequested_trailing_newline_from_file_content(self):
        step = {"action": "create_file", "value": "notes.txt", "folder": "Downloads",
                "content": "first line\n", "expected": "file exists"}
        self.assertEqual(normalize_plan([step], "Create notes.txt in Downloads and write first line")[0]["content"], "first line")
        self.assertEqual(normalize_plan([step], "Create notes.txt in Downloads and write something else")[0]["content"], "first line\n")

    def test_rejects_model_invented_actions(self):
        for action, value in [("shell", "echo hi"), ("delete", "notes"), ("select", "Send"), ("open", "powershell")]:
            with self.subTest(action=action, value=value), self.assertRaises(ValueError):
                validate_plan({"steps": [{"action": action, "value": value, "expected": "done"}]})

    def test_file_edit_and_approved_actions_have_bounded_plan_shapes(self):
        steps = [{"action": "modify_file", "value": "notes.txt", "folder": "Documents",
                  "find": "old", "content": "new", "expected": "new text on disk"},
                 {"action": "delete_file", "value": "old.txt", "folder": "Documents", "expected": "file removed"},
                 {"action": "run_command", "value": "echo done", "expected": "exit code zero"}]
        self.assertEqual(validate_plan({"steps": steps}), steps)
        with self.assertRaisesRegex(ValueError, "folder"):
            validate_plan({"steps": [{"action": "delete_file", "value": "old.txt", "expected": "gone"}]})

    def test_bounds_plan_and_handles_clarification(self):
        with self.assertRaises(ValueError):
            validate_plan({"steps": [{"action": "open", "value": "chrome", "expected": "Chrome"}] * 7})
        with self.assertRaisesRegex(ValueError, "Which profile"):
            validate_plan({"question": "Which profile?", "steps": []})

    def test_free_form_only_dispatches_after_final(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.activate()
        engine.feed("find a repair shop video")
        self.assertEqual(sent, [])
        engine.feed("find a repair shop video", final=True)
        self.assertEqual(sent, [Command("task", "find a repair shop video")])

    def test_explicit_task_keeps_all_clauses_for_planner(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.activate()
        engine.feed("task open youtube then find repair shops", final=True)
        self.assertEqual(sent, [Command("task", "open youtube then find repair shops")])

    def test_new_instruction_cancels_existing_task(self):
        with tempfile.TemporaryDirectory() as directory:
            actions = Actions({"files_root": "files", "apps": {}}, directory, lambda *args: None)
            actions.task_active = True
            old_generation = actions.generation
            actions.submit(Command("open", "chrome"))
            self.assertGreater(actions.generation, old_generation)
            actions.close()


class LoopTests(unittest.TestCase):
    def test_invalid_dependencies_stop_before_any_external_action(self):
        self.brain.client.request.return_value = {"steps": [
            {"action": "open", "value": "chrome", "expected": "Chrome open", "id": 0, "dep": [1]},
            {"action": "open", "value": "calculator", "expected": "Calculator open", "id": 1, "dep": [0]}]}
        with self.assertRaisesRegex(ValueError, "prerequisite"):
            self.brain.run("open chrome and calculator", lambda: False)
        self.actions.execute.assert_not_called()

    def test_adaptive_replaces_remaining_tasks_using_verified_result(self):
        self.brain.options["adaptive_planning"] = True
        first = {"action": "open", "value": "chrome", "expected": "Chrome open"}
        old = {"action": "open", "value": "notepad", "expected": "Notepad open"}
        replacement = {"action": "open", "value": "calculator", "expected": "Calculator open"}
        self.actions.apps.update(notepad=["notepad.exe"], calculator=["calc.exe"])
        self.actions.execute.return_value = "Opened app"
        self.actions.last_created = self.actions.last_modified = self.actions.last_deleted = self.actions.last_command = None
        self.brain.client.request.side_effect = [
            {"steps": [first, old]}, {"approved": True}, {"verified": True},
            {"done": False, "reason": "Calculator is still required", "steps": [replacement]},
            {"approved": True}, {"verified": True},
            {"done": True, "steps": [], "reason": "Both apps visible"}, {"verified": True}]
        with patch("jarvis.brain.time.sleep"):
            result = self.brain.run("open chrome and calculator", lambda: False)
        self.assertIn("Finished", result)
        self.assertEqual([call.args[0].value for call in self.actions.execute.call_args_list], ["chrome", "calculator"])
        revisions = [call for call in self.brain.client.request.call_args_list if call.args[0] == "replan"]
        self.assertEqual(revisions[0].kwargs["remaining"], [old])
        self.assertEqual(revisions[0].kwargs["last_result"]["value"], "chrome")
        self.assertTrue(revisions[0].kwargs["last_result"]["verified"])

    def test_adaptive_inference_failure_does_not_execute_stale_remaining_plan(self):
        self.brain.options["adaptive_planning"] = True
        self.actions.execute.return_value = "Opened Chrome"
        self.brain.client.request.side_effect = [
            {"steps": [{"action": "open", "value": "chrome", "expected": "Chrome open"},
                       {"action": "open", "value": "calculator", "expected": "Calculator open"}]},
            {"approved": True}, {"verified": True}, ValueError("model stopped")]
        with patch("jarvis.brain.time.sleep"), self.assertRaisesRegex(ValueError, "Task paused.*model stopped"):
            self.brain.run("open chrome and calculator", lambda: False)
        self.actions.execute.assert_called_once()

    def test_adaptive_rejects_completed_action_anywhere_in_plan(self):
        step = {"action": "open", "value": "chrome", "expected": "Chrome open"}
        other = {"action": "open", "value": "calculator", "expected": "Calculator open"}
        self.brain.client.request.return_value = {"done": False, "steps": [other, step]}
        with self.assertRaisesRegex(ValueError, "already completed"):
            self.brain.revise_plan("open chrome and calculator", {}, [], [step], [other], 1, lambda: False)
        self.actions.execute.assert_not_called()

    def test_completed_action_cannot_be_repeated_by_changing_unused_browser(self):
        completed = {"action": "open", "value": "chrome", "expected": "Chrome visible", "browser": "chrome"}
        self.brain.client.request.return_value = {"done": False, "steps": [{**completed, "browser": "edge"}]}
        with self.assertRaisesRegex(ValueError, "already completed"):
            self.brain.revise_plan("open chrome", {}, [], [completed], [], 1, lambda: False)
        self.actions.execute.assert_not_called()

    def test_adaptive_does_not_accept_empty_unfinished_plan_or_over_budget(self):
        for response in ({"done": False, "steps": []}, {"done": True, "steps": self.plan["steps"]},
                         {"done": False, "steps": self.plan["steps"] * 2}):
            with self.subTest(response=response):
                self.brain.client.request.return_value = response
                with self.assertRaises(ValueError):
                    self.brain.revise_plan("play video", {}, [], [{"action": "open", "value": "chrome"}], [], 5, lambda: False)

    def test_adaptive_cancel_after_inference_prevents_plan_acceptance(self):
        stopped = [False]
        def request(*args, **kwargs):
            stopped[0] = True
            return {"done": True, "steps": []}
        self.brain.client.request.side_effect = request
        with self.assertRaisesRegex(ValueError, "cancelled"):
            self.brain.revise_plan("play video", {}, [], [{"action": "open", "value": "chrome"}], [], 1, lambda: stopped[0])

    def setUp(self):
        self.actions = Mock()
        self.actions.apps = {"chrome": ["chrome.exe"]}
        self.actions.pending_open = None
        self.brain = Brain(self.actions, Path.cwd(), {"enabled": True, "planner": "planner", "decision": "decision"})
        self.brain.client = Mock()
        self.control = {"name": "Play", "id": [1], "role": "Button", "rect": [0, 0, 10, 10]}
        self.snapshot = {"title": "YouTube", "context": "chrome", "signature": "a", "controls": [self.control]}
        self.brain.observe = Mock(return_value=(123, self.snapshot))
        self.plan = {"steps": [{"action": "select", "value": "Play", "expected": "Pause button visible"}]}
        self.responses = [self.plan, {"approved": True, "choice": "c0"}, {"verified": True}, {"verified": True}]

    def test_resume_observes_and_executes_only_remaining_action(self):
        done = {"action": "open", "value": "chrome", "expected": "Chrome open", "verified": True}
        remaining = {"action": "open", "value": "calculator", "expected": "Calculator open"}
        self.actions.resume_source = {"plan": {"completed": [done]}, "checkpoints": []}
        self.actions.apps["calculator"] = ["calc.exe"]
        self.actions.last_created = self.actions.last_modified = self.actions.last_deleted = self.actions.last_command = None
        self.actions.execute.return_value = "Opened calculator"
        self.brain.client.request.side_effect = [{"steps": [remaining]}, {"approved": True},
                                                {"verified": True}, {"verified": True}]
        with patch("jarvis.brain.time.sleep"):
            result = self.brain.run("open chrome and calculator", lambda: False)
        self.assertIn("Finished", result)
        self.assertEqual(self.actions.execute.call_count, 1)
        self.assertEqual(self.actions.execute.call_args.args[0].value, "calculator")
        self.assertEqual(self.brain.client.request.call_args_list[0].kwargs["completed"], [done])
        self.assertGreater(self.brain.observe.call_count, 1)

    def test_resume_rejects_repeated_completed_action(self):
        done = {"action": "open", "value": "chrome", "expected": "Chrome open", "verified": True}
        self.actions.resume_source = {"plan": {"completed": [done]}, "checkpoints": []}
        self.brain.client.request.return_value = {"steps": [done]}
        with self.assertRaisesRegex(ValueError, "already completed"):
            self.brain.run("open chrome", lambda: False)
        self.actions.execute.assert_not_called()

    def test_post_action_observation_waits_for_new_window_without_reacting(self):
        before = {"title": "Desktop", "signature": "old", "controls": []}
        after = {"title": "Chrome", "signature": "new", "controls": []}
        self.brain.observe.side_effect = [(1, before), (2, after)]
        with patch("jarvis.brain.time.sleep"):
            handle, landed = self.brain.observe_after_action((1, before), "open", lambda: False)
        self.assertEqual(handle, 2)
        self.assertEqual(landed["title"], "Chrome")
        self.assertEqual(self.brain.observe.call_count, 2)
        self.actions.execute.assert_not_called()

    def test_post_action_observation_uses_fresh_file_state(self):
        after = {"title": "TestCodes", "signature": "same", "controls": []}
        self.brain.observe.return_value = (1, after)
        with patch("jarvis.brain.time.sleep") as sleep:
            _, landed = self.brain.observe_after_action((1, after), "create_file", lambda: False)
        self.assertIs(landed, after)
        self.brain.observe.assert_called_once()
        sleep.assert_not_called()

    def test_unique_exact_choice_skips_laya_and_is_verified(self):
        self.brain.client.request.side_effect = self.responses
        with patch("jarvis.brain.time.sleep"):
            result = self.brain.run("play video", lambda: False)
        self.assertIn("Finished", result)
        self.assertEqual([call.args[0] for call in self.brain.client.request.call_args_list], ["plan", "decide", "verify", "verify"])
        self.actions._ui()._activate.assert_called_once()

    def test_rejected_decision_does_not_act(self):
        self.brain.client.request.side_effect = [self.plan, {"approved": False, "reason": "ambiguous"}]
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.brain.run("play video", lambda: False)
        self.actions._ui()._activate.assert_not_called()

    def test_stale_screen_does_not_act(self):
        self.brain.client.request.side_effect = self.responses
        self.brain.observe.side_effect = [(123, self.snapshot), (123, self.snapshot), (456, self.snapshot)]
        with self.assertRaisesRegex(ValueError, "target changed"):
            self.brain.run("play video", lambda: False)
        self.actions._ui()._activate.assert_not_called()

    def test_failed_verification_never_replays_click(self):
        self.responses[2] = {"verified": False, "reason": "No evidence"}
        self.brain.client.request.side_effect = self.responses
        with patch("jarvis.brain.time.sleep"):
            result = self.brain.run("play video", lambda: False)
        self.assertIn("could not be verified", result)
        self.actions._ui()._activate.assert_called_once()

    def test_invented_choice_id_is_rejected(self):
        self.responses[1] = {"approved": True, "choice": "c99"}
        self.brain.client.request.side_effect = self.responses
        with self.assertRaises(ValueError):
            self.brain.run("play video", lambda: False)
        self.actions._ui()._activate.assert_not_called()

    def test_wrong_choice_never_clicks(self):
        self.responses[1] = {"approved": True, "choice": "none"}
        self.brain.client.request.side_effect = self.responses
        with self.assertRaisesRegex(ValueError, "disagree"):
            self.brain.run("play video", lambda: False)
        self.actions._ui()._activate.assert_not_called()

    def test_full_goal_failure_does_not_claim_completion(self):
        self.responses[-1] = {"verified": False, "reason": "Only the first part is complete"}
        self.brain.client.request.side_effect = self.responses
        with patch("jarvis.brain.time.sleep"):
            result = self.brain.run("play video", lambda: False)
        self.assertIn("full goal is not verified", result)

    def test_cancellation_between_decision_and_action(self):
        cancelled = [False]
        def request(operation, *args, **kwargs):
            response = self.responses.pop(0)
            if operation == "decide":
                cancelled[0] = True
            return response
        self.brain.client.request.side_effect = request
        # Real observe checks cancellation through its UI worker. Assert the callback reaches activation too.
        def activate(*args):
            self.assertTrue(args[-1]())
            return "cancelled"
        self.actions._ui()._activate.side_effect = activate
        with self.assertRaisesRegex(ValueError, "cancelled"):
            self.brain.run("play video", lambda: cancelled[0])

    def test_screen_aware_replans_from_landed_screen(self):
        self.brain.options["screen_aware"] = True
        self.brain.client.base = Path.cwd()
        self.actions.apps["calculator"] = ["calc.exe"]
        self.brain.visual_screen = Mock(side_effect=[
            {"title": "Desktop", "ocr": "", "image": "first", "controls": []},
            {"title": "Chrome", "ocr": "", "image": "second", "controls": []},
            {"title": "Calculator", "ocr": "", "image": "third", "controls": []}])
        first = {"steps": [{"action": "open", "value": "chrome", "expected": "Chrome visible"}]}
        second = {"done": False, "steps": [{"action": "open", "value": "calculator", "expected": "Calculator visible"}]}
        self.brain.client.request.side_effect = [
            {"summary": "Desktop", "step_verified": True, "goal_done": False}, first,
            {"approved": True},
            {"summary": "Chrome window", "step_verified": True, "goal_done": False}, second,
            {"approved": True},
            {"summary": "Calculator window", "step_verified": True, "goal_done": True},
            {"verified": True}]
        with patch("jarvis.brain.time.sleep"):
            result = self.brain.run("open chrome and calculator", lambda: False)
        self.assertIn("Finished", result)
        self.assertEqual([call.args[0] for call in self.brain.client.request.call_args_list],
            ["visual", "plan", "decide", "visual", "replan" if self.brain.options.get("adaptive_planning") else "plan", "decide", "visual", "verify"])
        self.assertEqual([call.args[0].value for call in self.actions.execute.call_args_list],
            ["chrome", "calculator"])

    def test_screen_aware_adaptive_replans_from_landed_screen(self):
        self.brain.options["adaptive_planning"] = True
        self.test_screen_aware_replans_from_landed_screen()

    def test_screen_aware_stops_when_landed_screen_does_not_confirm_step(self):
        self.brain.options["screen_aware"] = True
        self.brain.client.base = Path.cwd()
        self.brain.visual_screen = Mock(return_value={"title": "Desktop", "ocr": "", "image": "test", "controls": []})
        self.brain.client.request.side_effect = [
            {"summary": "Desktop", "step_verified": True, "goal_done": False},
            {"steps": [{"action": "open", "value": "chrome", "expected": "Chrome visible"}]},
            {"approved": True},
            {"summary": "Still desktop", "step_verified": False, "goal_done": False, "reason": "Chrome not shown"},
            {"summary": "Still desktop", "step_verified": False, "goal_done": False, "reason": "Chrome not shown"}]
        with patch("jarvis.brain.time.sleep"):
            result = self.brain.run("open chrome", lambda: False)
        self.assertIn("Chrome not shown", result)
        self.assertEqual(self.actions.execute.call_count, 1)
        self.assertEqual(self.brain.visual_screen.call_count, 3)

    def test_screen_aware_reobserves_loading_page_without_repeating_action(self):
        self.brain.options["screen_aware"] = True
        self.brain.client.base = Path.cwd()
        self.brain.visual_screen = Mock(side_effect=[
            {"title": "Desktop", "ocr": "", "image": "before", "controls": []},
            {"title": "Chrome", "ocr": "Loading", "image": "loading", "controls": []},
            {"title": "Chrome", "ocr": "Ready", "image": "ready", "controls": []}])
        self.brain.client.request.side_effect = [
            {"summary": "Desktop", "step_verified": True, "goal_done": False},
            {"steps": [{"action": "open", "value": "chrome", "expected": "Chrome visible"}]},
            {"approved": True},
            {"summary": "Loading", "step_verified": False, "goal_done": False, "reason": "Loading"},
            {"summary": "Chrome ready", "step_verified": True, "goal_done": True},
            {"verified": True}]
        with patch("jarvis.brain.time.sleep"):
            result = self.brain.run("open chrome", lambda: False)
        self.assertIn("Finished", result)
        self.actions.execute.assert_called_once()
        self.assertEqual(self.brain.visual_screen.call_count, 3)

    def test_replace_plan_cannot_silently_overwrite_entire_file(self):
        self.brain.client.request.return_value = {"steps": [{"action": "modify_file", "value": "notes.txt",
            "folder": "Documents", "find": "", "content": "new", "expected": "file changed"}]}
        with self.assertRaisesRegex(ValueError, "overwrite the whole file"):
            self.brain.run("Open Documents and modify file notes.txt: replace old with new", lambda: False)
        self.actions.execute.assert_not_called()

    def test_plan_cannot_change_a_different_named_file(self):
        self.brain.client.request.return_value = {"steps": [{"action": "delete_file", "value": "other.txt",
            "folder": "Documents", "expected": "removed"}]}
        with self.assertRaisesRegex(ValueError, "filename you did not name"):
            self.brain.run("First open Documents and then delete file notes.txt there", lambda: False)
        self.actions.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
