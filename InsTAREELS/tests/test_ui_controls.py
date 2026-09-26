import unittest
import os
from jarvis.commands import Command, parse
from jarvis.engine import Engine
from jarvis.ui_controls import UIControls, matches


def control(name, ident, role="Button", rect=None):
    return {"name": name, "role": role, "id": [ident], "rect": rect or [1, 2, 3, 4]}


class FakeRunner:
    def __init__(self, controls):
        self.controls = controls
        self.signature = "initial"
        self.requests = []
        self.title = "Test window"

    def __call__(self, request, cancelled):
        self.requests.append(request)
        if request["operation"] == "list":
            return {"controls": self.controls, "signature": self.signature, "title": self.title}
        return {"message": "Activated " + request["control"]["name"]}


class UITests(unittest.TestCase):
    def test_panel_focus_uses_last_external_window(self):
        class User:
            def GetForegroundWindow(self):
                return 1
            def GetWindowThreadProcessId(self, hwnd, pointer):
                pointer._obj.value = os.getpid() if hwnd == 1 else 42
            def IsWindow(self, hwnd):
                return hwnd == 77
            def IsWindowVisible(self, hwnd):
                return hwnd == 77
        desktop = type("Desktop", (), {"user": User(), "target": None})()
        ui = UIControls(desktop, external_handle=lambda: 77)
        self.assertEqual(ui._handle(), 77)

    def make_ui(self, controls):
        runner = FakeRunner(controls)
        desktop = type("Desktop", (), {"target": None})()
        ui = UIControls(desktop, runner=runner)
        ui._handle = lambda: 123
        return ui, runner

    def test_user_example_is_a_selection_command(self):
        self.assertEqual(parse("select comedy with cartoons"), Command("click_control", "comedy with cartoons", "select"))
        self.assertEqual(parse("click on the Save button"), Command("click_control", "Save", "click"))
        self.assertEqual(parse("select option two"), Command("choose_control", "2"))
        self.assertEqual(parse("list buttons"), Command("list_controls"))
        self.assertEqual(parse("select second video"), Command("select_context", "2:video", "select"))
        self.assertEqual(parse("select 3rd result"), Command("select_context", "3:result", "select"))
        self.assertEqual(parse("select this option"), Command("select_context", "this:option", "select"))
        self.assertEqual(parse("yeh option select karo"), Command("select_context", "this:option", "select"))

    def test_exact_label_wins_over_longer_label(self):
        values = [control("Save", 1), control("Save as", 2)]
        self.assertEqual(matches(values, "save"), values[:1])

    def test_partial_label_must_match_whole_words(self):
        values = [control("Comedy with Cartoons - Chrome", 1, "TabItem")]
        self.assertEqual(matches(values, "comedy with cartoons"), values)
        self.assertEqual(matches(values, "art"), [])

    def test_unique_control_activates_once(self):
        ui, runner = self.make_ui([control("Comedy with Cartoons", 1, "TabItem")])
        result = ui.execute(parse("select comedy with cartoons"))
        self.assertIn("Activated", result)
        self.assertEqual([r["operation"] for r in runner.requests], ["list", "activate"])

    def test_typo_in_label_matches_visible_control(self):
        ui, runner = self.make_ui([control("Comedy with Cartoons - Chrome", 1, "TabItem")])
        self.assertIn("Activated", ui.execute(parse("select comdy with cartuns")))
        self.assertEqual(runner.requests[-1]["control"]["id"], [1])

    def test_short_typo_matches_but_ambiguous_typo_asks(self):
        ui, runner = self.make_ui([control("Save", 1)])
        ui.execute(parse("select svae"))
        self.assertEqual(runner.requests[-1]["control"]["id"], [1])
        ui, runner = self.make_ui([control("Cartoons", 1), control("Cartoons 2", 2)])
        self.assertIn("select option number", ui.execute(parse("select cartuns")))
        self.assertEqual([r["operation"] for r in runner.requests], ["list"])

    def test_inferred_selection_skips_destructive_option(self):
        ui, runner = self.make_ui([control("Delete file", 1, "ListItem"),
                                   control("Open file", 2, "ListItem")])
        ui.execute(parse("select first option"))
        self.assertEqual(runner.requests[-1]["control"]["id"], [2])

    def test_numbered_option_keeps_displayed_number(self):
        ui, runner = self.make_ui([control("Delete file", 1), control("Save", 2)])
        ui.execute(parse("list buttons"))
        ui.execute(parse("select second option"))
        self.assertEqual(runner.requests[-1]["control"]["id"], [2])

    def test_second_video_uses_screen_order_and_ignores_navigation(self):
        controls = [control("Subscriptions", 1, "Hyperlink", [10, 20, 100, 50]),
                    control("Third dog video", 4, "Hyperlink", [260, 500, 500, 540]),
                    control("First dog video", 2, "Hyperlink", [260, 200, 500, 240]),
                    control("Second dog video", 3, "Hyperlink", [260, 350, 500, 390])]
        ui, runner = self.make_ui(controls)
        runner.title = "YouTube search results"
        ui.execute(parse("select second video"))
        self.assertEqual(runner.requests[-1]["control"]["id"], [3])

    def test_this_option_uses_pointer(self):
        class User:
            def GetCursorPos(self, pointer):
                pointer._obj.x, pointer._obj.y = 30, 75
                return True
        ui, runner = self.make_ui([control("Alpha", 1, "ListItem", [10, 20, 90, 50]),
                                   control("Beta", 2, "ListItem", [10, 60, 90, 100])])
        ui.desktop.user = User()
        ui.execute(parse("select this option"))
        self.assertEqual(runner.requests[-1]["control"]["id"], [2])

    def test_this_option_without_pointer_asks_when_ambiguous(self):
        ui, runner = self.make_ui([control("Alpha", 1, "ListItem"), control("Beta", 2, "ListItem")])
        response = ui.execute(parse("select this option"))
        self.assertIn("select option number", response)
        self.assertEqual([r["operation"] for r in runner.requests], ["list"])

    def test_duplicate_labels_require_number_and_do_not_click(self):
        ui, runner = self.make_ui([control("Save", 1), control("Save", 2)])
        result = ui.execute(parse("click save"))
        self.assertIn("1. Save", result)
        self.assertEqual(len(runner.requests), 1)
        ui.execute(parse("select option two"))
        self.assertEqual(runner.requests[-1]["control"]["id"], [2])

    def test_changed_controls_invalidate_number(self):
        ui, runner = self.make_ui([control("Save", 1)])
        ui.execute(parse("list buttons"))
        runner.signature = "changed"
        with self.assertRaisesRegex(ValueError, "changed"):
            ui.execute(parse("select option one"))
        self.assertTrue(all(r["operation"] == "list" for r in runner.requests))

    def test_changed_window_invalidates_number(self):
        ui, runner = self.make_ui([control("Save", 1)])
        ui.execute(parse("list buttons"))
        ui._handle = lambda: 124
        with self.assertRaisesRegex(ValueError, "changed"):
            ui.execute(parse("select option one"))

    def test_expired_choices_are_rejected(self):
        ui, runner = self.make_ui([control("Save", 1)])
        ui.execute(parse("list buttons"))
        ui.pending["time"] -= 50
        with self.assertRaisesRegex(ValueError, "expired"):
            ui.execute(parse("select option one"))

    def test_no_match_does_not_click(self):
        ui, runner = self.make_ui([control("Save", 1)])
        with self.assertRaisesRegex(ValueError, "No matching"):
            ui.execute(parse("click missing"))
        self.assertEqual(len(runner.requests), 1)

    def test_cancelled_command_does_not_inspect_or_click(self):
        ui, runner = self.make_ui([control("Save", 1)])
        ui.execute(parse("click save"), cancelled=lambda: True)
        self.assertEqual(runner.requests, [])

    def test_partial_hypothesis_never_clicks(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.feed("jarvis click save then open notepad")
        self.assertEqual(sent, [])
        engine.feed("jarvis click save then open notepad", final=True)
        self.assertEqual([c.kind for c in sent], ["click_control", "open"])

    def test_open_and_select_natural_phrase(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.feed("jarvis open chrome and select comedy with cartoons", final=True)
        self.assertEqual(sent, [Command("open", "chrome"), Command("click_control", "comedy with cartoons", "select")])


if __name__ == "__main__":
    unittest.main()
