import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from jarvis.audio import command_text
from jarvis.brain import Brain, explicit_app_launch_plan, youtube_search_plan, validate_plan
from jarvis.commands import Command, parse
from jarvis.engine import Engine


class TaskRoutingTests(unittest.TestCase):
    def test_user_youtube_workflow_stays_one_task(self):
        spoken = "open youtube and search for how to make robot and play first video."
        submit = Mock()
        engine = Engine(submit, Mock())
        engine.activate()
        engine.feed(command_text(spoken), final=True)
        submit.assert_called_once_with(Command("task", spoken.rstrip(".")))
        steps = validate_plan(youtube_search_plan(spoken))
        self.assertEqual(steps[0]["value"], "how to make robot")
        self.assertEqual(steps[0]["platform"], "youtube")
        self.assertEqual(steps[1]["position"], 1)

    def test_polite_actions_and_questions_are_distinct(self):
        self.assertEqual(parse("Can you help me open Spotify and play jazz"), Command("play_media", "jazz", "spotify"))
        self.assertEqual(parse("do open calculator"), Command("open", "calculator"))
        self.assertEqual(parse("How do robots work?").kind, "ask")
        self.assertEqual(parse("Do you know how robots work?").kind, "ask")

    def test_enter_routes_actions_and_questions(self):
        from main import App
        app = Mock()
        for text, expected in [("open calculator", "open"), ("How do robots work?", "ask"),
                               ("open youtube and search for how to make robot and play first video", "task")]:
            app.actions.submit.reset_mock()
            app.preview.get.return_value = text
            App.send_input(app)
            self.assertEqual(app.actions.submit.call_args.args[0].kind, expected)

    def test_launch_shortcut_requires_exact_configured_app(self):
        apps = {"chrome": ["chrome.exe"]}
        self.assertEqual(explicit_app_launch_plan("open chrome and select Play", apps)["steps"][0]["value"], "chrome")
        self.assertIsNone(explicit_app_launch_plan("open unknown and select Play", apps))

    def test_configured_app_launch_runs_before_model_then_observes(self):
        actions = Mock()
        actions.apps = {"chrome": ["chrome.exe"]}
        actions.pending_open = None
        actions.last_created = actions.last_modified = actions.last_deleted = actions.last_command = None
        brain = Brain(actions, Path.cwd(), {"enabled": True, "screen_aware": True, "planner": "planner", "decision": "decision"})
        brain.client = Mock()
        brain.client.base = Path.cwd()
        control = {"name": "Play", "role": "Button", "rect": [0, 0, 40, 40], "id": [1]}
        snapshot = {"title": "Chrome", "context": "chrome", "signature": "new", "controls": [control]}
        brain.observe = Mock(return_value=(123, snapshot))
        brain.visual_screen = Mock(return_value={"title": "Chrome", "ocr": "", "controls": [], "image": "test"})
        brain.client.request.side_effect = [
            {"summary": "Chrome opened", "step_verified": True, "goal_done": False},
            {"steps": [{"action": "select", "value": "Play", "expected": "Playback started"}]},
            {"approved": True, "choice": "c0"},
            {"summary": "Playing", "step_verified": True, "goal_done": True},
            {"verified": True}]
        def execute(command, cancelled):
            brain.client.request.assert_not_called()
            self.assertEqual(command, Command("open", "chrome"))
            return "Chrome opened"
        actions.execute.side_effect = execute
        with patch("jarvis.brain.time.sleep"):
            self.assertIn("Finished", brain.run("open chrome and select Play", lambda: False))
        actions.execute.assert_called_once()
        actions._ui()._activate.assert_called_once()
        self.assertEqual([c.args[0] for c in brain.client.request.call_args_list], ["visual", "plan", "decide", "visual", "verify"])

    def test_youtube_search_executes_before_models_and_selects_first_visible_video(self):
        actions = Mock()
        actions.apps = {"chrome": ["chrome.exe"]}
        actions.pending_open = None
        actions.last_created = actions.last_modified = actions.last_deleted = actions.last_command = None
        brain = Brain(actions, Path.cwd(), {"enabled": True, "screen_aware": True, "planner": "planner", "decision": "decision"})
        brain.client = Mock()
        brain.client.base = Path.cwd()
        second = {"name": "Robot tutorial two", "role": "Hyperlink", "rect": [200, 300, 500, 400], "id": [2]}
        first = {"name": "Robot tutorial one", "role": "Hyperlink", "rect": [200, 100, 500, 200], "id": [1]}
        pause = {"name": "Pause", "role": "Button", "rect": [200, 500, 250, 550], "id": [3]}
        snapshot = {"title": "YouTube", "context": "chrome", "signature": "results", "controls": [second, first, pause]}
        brain.observe = Mock(return_value=(123, snapshot))
        brain.visual_screen = Mock(return_value={"title": "YouTube", "ocr": "", "controls": [], "image": "test"})
        brain.client.request.side_effect = [
            {"summary": "Search results", "step_verified": True, "goal_done": False},
            {"approved": True, "choice": "c0"},
            {"summary": "Playing first video", "step_verified": True, "goal_done": True},
            {"verified": True}]
        def execute(command, cancelled):
            brain.client.request.assert_not_called()
            self.assertEqual(command, Command("media_search", "how to make robot", "youtube"))
            return "Search opened"
        actions.execute.side_effect = execute
        with patch("jarvis.brain.time.sleep"):
            result = brain.run("open youtube and search for how to make robot and play first video", lambda: False)
        self.assertIn("Finished", result)
        actions.execute.assert_called_once()
        self.assertEqual(actions._ui()._activate.call_args.args[2], first)
        self.assertEqual([c.args[0] for c in brain.client.request.call_args_list], ["visual", "decide", "visual", "verify"])


if __name__ == "__main__":
    unittest.main()
