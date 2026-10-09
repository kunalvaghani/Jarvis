import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from jarvis.brain import Brain, validate_plan
from jarvis.commands import parse
from jarvis.desktop_actions import apply_control, explicit_desktop_plan, shortcut_key
from jarvis.ui_worker import perform


class DesktopActionTests(unittest.TestCase):
    def test_explicit_requests_route_as_tasks(self):
        goals = ["fill Search field with robot tutorials", "scroll down", "press control plus f",
                 "open File menu", "select Cancel in the dialog"]
        for goal in goals:
            with self.subTest(goal=goal):
                self.assertEqual(parse(goal).kind, "task")
                validate_plan(explicit_desktop_plan(goal))
        self.assertEqual(parse("open Chrome and fill Search field with robot tutorials").kind, "task")
        self.assertEqual(parse("open File menu and select Save as").kind, "task")
        self.assertIsNone(explicit_desktop_plan("fill Search field with robots and click Search"))
        self.assertIsNone(explicit_desktop_plan("press alt f then select Save as"))
        self.assertEqual(explicit_desktop_plan("fill Search field with rock and roll")["steps"][0]["content"], "rock and roll")
        self.assertEqual(shortcut_key("Control plus Shift plus S"), "ctrl+shift+s")
        self.assertEqual(shortcut_key("control shift s"), "ctrl+shift+s")
        self.assertEqual(shortcut_key("alt left"), "alt+left")
        for value in ["delete", "enter", "win+r", "ctrl+s{ENTER}"]:
            with self.assertRaises(ValueError):
                shortcut_key(value)

    def test_fill_sets_value_once_without_typing_or_submission(self):
        element = Mock()
        element.iface_value.CurrentIsReadOnly = False
        element.iface_value.CurrentValue = "robot tutorials"
        self.assertEqual(apply_control(element, {"name": "Search", "role": "Edit"}, "fill_text", "robot tutorials"), "Filled Search; exact field value verified")
        element.iface_value.SetValue.assert_called_once_with("robot tutorials")
        element.type_keys.assert_not_called()

    def test_ignored_text_entry_is_not_claimed_successful(self):
        element = Mock()
        element.iface_value.CurrentIsReadOnly = False
        element.iface_value.CurrentValue = "old"
        with self.assertRaisesRegex(ValueError, "could not be verified"):
            apply_control(element, {"name": "Search", "role": "Edit"}, "fill_text", "new")
        element.iface_value.SetValue.assert_called_once_with("new")
        element.iface_value.CurrentIsReadOnly = True
        with self.assertRaisesRegex(ValueError, "read-only"):
            apply_control(element, {"name": "Search", "role": "Edit"}, "fill_text", "new")
        with self.assertRaisesRegex(ValueError, "non-password"):
            apply_control(element, {"name": "Password", "role": "Edit", "password": True}, "fill_text", "secret")

    def test_scroll_and_menu_call_one_pattern(self):
        element = Mock()
        apply_control(element, {"name": "Page", "role": "Pane"}, "scroll", "down")
        element.iface_scroll.Scroll.assert_called_once_with(2, 3)
        apply_control(element, {"name": "File", "role": "MenuItem"}, "open_menu")
        element.iface_expand_collapse.Expand.assert_called_once()
        element.iface_invoke.Invoke.assert_not_called()

    def test_pattern_failure_never_replays_action(self):
        element = Mock()
        element.iface_value.CurrentIsReadOnly = False
        element.iface_value.SetValue.side_effect = RuntimeError("provider failed")
        with self.assertRaises(RuntimeError):
            apply_control(element, {"name": "Search", "role": "Edit"}, "fill_text", "hello")
        element.iface_value.SetValue.assert_called_once()
        element.type_keys.assert_not_called()

    def make_brain(self, plan, controls, goal):
        actions = Mock()
        actions.apps = {}
        actions.pending_open = None
        actions.last_created = actions.last_modified = actions.last_deleted = actions.last_command = None
        brain = Brain(actions, Path.cwd(), {"enabled": True, "planner": "planner", "decision": "decision"})
        brain.client = Mock()
        snapshot = {"title": "Example", "context": "app", "signature": "same", "controls": controls}
        brain.observe = Mock(return_value=(123, snapshot))
        brain.client.request.side_effect = [plan, {"approved": True, "choice": "c0"}, {"verified": True}, {"verified": True}]
        actions._ui().runner.return_value = {"message": "Action applied"}
        return brain, actions, snapshot

    def test_planned_field_entry_executes_then_observes(self):
        goal = "Search for robot tutorials in the app"
        control = {"name": "Search", "role": "Edit", "id": [1], "rect": [0, 0, 100, 30]}
        plan = {"steps": [{"action": "fill_text", "value": "Search", "content": "robot tutorials", "expected": "Text entered"}]}
        brain, actions, snapshot = self.make_brain(plan, [control], goal)
        with patch("jarvis.brain.time.sleep"):
            self.assertIn("Finished", brain.run(goal, lambda: False))
        request = actions._ui().runner.call_args.args[0]
        self.assertEqual(request["operation"], "fill_text")
        self.assertEqual(request["control"], control)
        self.assertEqual(request["content"], "robot tutorials")
        self.assertGreaterEqual(brain.observe.call_count, 4)
        actions.execute.assert_not_called()

    def test_changed_field_does_not_receive_text(self):
        goal = "Search for robot tutorials in the app"
        control = {"name": "Search", "role": "Edit", "id": [1], "rect": [0, 0, 100, 30]}
        plan = {"steps": [{"action": "fill_text", "value": "Search", "content": "robot tutorials", "expected": "Text entered"}]}
        brain, actions, snapshot = self.make_brain(plan, [control], goal)
        brain.observe.side_effect = [(123, snapshot), (123, snapshot), (456, snapshot)]
        with self.assertRaisesRegex(ValueError, "target changed"):
            brain.run(goal, lambda: False)
        actions._ui().runner.assert_not_called()

    def test_shortcut_rechecks_window_then_runs_once(self):
        goal = "Navigate to the browser address bar"
        plan = {"steps": [{"action": "shortcut", "value": "ctrl+l", "expected": "Address bar focused"}]}
        brain, actions, snapshot = self.make_brain(plan, [], goal)
        with patch("jarvis.brain.time.sleep"):
            self.assertIn("Finished", brain.run(goal, lambda: False))
        actions._ui().runner.assert_called_once()
        self.assertEqual(actions._ui().runner.call_args.args[0]["signature"], "same")
        self.assertEqual(actions._ui().runner.call_args.args[0]["value"], "ctrl+l")

    def test_dialog_selection_requires_active_modal_dialog(self):
        goal = "Dismiss the prompt using Cancel"
        button = {"name": "Cancel", "role": "Button", "id": [1], "rect": [0, 0, 100, 30]}
        plan = {"steps": [{"action": "handle_dialog", "value": "Cancel", "expected": "Dialog dismissed"}]}
        brain, actions, snapshot = self.make_brain(plan, [button], goal)
        with self.assertRaisesRegex(ValueError, "No accessible modal"):
            brain.run(goal, lambda: False)
        actions._ui()._activate.assert_not_called()
        brain, actions, snapshot = self.make_brain(plan, [button], goal)
        snapshot["is_dialog"] = True
        with patch("jarvis.brain.time.sleep"):
            self.assertIn("Finished", brain.run(goal, lambda: False))
        actions._ui()._activate.assert_called_once()

    def test_worker_rejects_stale_shortcut_before_sending_keys(self):
        desktop = Mock()
        window = desktop.return_value.window.return_value.wrapper_object.return_value
        gui = Mock()
        gui.IsWindow.return_value = True
        gui.GetForegroundWindow.return_value = 123
        process = Mock()
        process.GetWindowThreadProcessId.return_value = (1, 42)
        pywinauto = Mock(Desktop=desktop)
        patterns = Mock(NoPatternInterfaceError=type("NoPatternInterfaceError", (Exception,), {}))
        with patch.dict("sys.modules", {"pywinauto": pywinauto, "pywinauto.uia_defines": patterns,
                                       "win32gui": gui, "win32process": process}), \
             patch("jarvis.ui_worker.collect", return_value=([], {}, "fresh")):
            with self.assertRaisesRegex(ValueError, "controls changed"):
                perform({"operation": "shortcut", "handle": 123, "owner_pid": 999,
                         "signature": "stale", "value": "ctrl+s"})
        window.type_keys.assert_not_called()
