from tests.layout_fixtures import fixture_path
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jarvis.actions import Actions
from jarvis.browser import browser_args, url_for
from jarvis.catalog import Catalog, AmbiguousName
from jarvis.commands import Command, parse
from jarvis.engine import Engine
from jarvis.names import rank, rank_spelling
from jarvis.ui_controls import matches, UIControls
from test_ui_controls import FakeRunner, control
from scripts.catalog.build_catalog_index import build


class NaturalNamesTests(unittest.TestCase):
    def test_phrases_from_actual_log(self):
        examples = {
            "but why is sky blue today": Command("ask", "why is sky blue today"),
            "open youtube in chrome": Command("browse", "youtube", "chrome"),
            "search my hood on chrome": Command("browser_search", "my hood", "chrome"),
            "open chrome and search MyHuna": Command("browser_search", "MyHuna", "chrome"),
            "button list": Command("list_controls"),
            "open person1 profile": Command("click_control", "open person1 profile", "select"),
            "open d drive": Command("open_drive", "D"),
            "close": Command("close_app", "this app"),
            "pause video": Command("media_control", "pause", "youtube"),
        }
        for text, command in examples.items():
            with self.subTest(text=text):
                self.assertEqual(parse(text), command)

    def test_compound_browser_search_waits_for_final_and_runs_once(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.activate()
        engine.feed("open chrome and search myhuna")
        self.assertEqual(sent, [])
        engine.feed("open chrome and search myhuna", final=True)
        self.assertEqual(sent, [Command("browser_search", "myhuna", "chrome")])

    def test_profile_chooses_open_not_menu(self):
        controls = [control("Open Person 1 profile", 1), control("More actions for Person 1", 2)]
        for query in ("Person 1", "person1", "Person one", "person1 profile"):
            self.assertEqual(matches(controls, query), controls[:1])

    def test_ambiguous_close_does_not_guess(self):
        controls = [control("Close", 1), control("Close", 2)]
        self.assertEqual(matches(controls, "close"), controls)

    def test_pause_does_not_click_play(self):
        runner = FakeRunner([control("Play (k)", 1)])
        ui = UIControls(type("Desktop", (), {"target": None})(), runner)
        ui._handle = lambda: 123
        self.assertIn("already paused", ui.execute(parse("pause")))
        self.assertTrue(all(item["operation"] == "list" for item in runner.requests))

    def test_common_app_alias_and_typo(self):
        self.assertEqual(rank("vs code", ["visual studio code", "paint"]), ["visual studio code"])
        self.assertEqual(rank("notepadd", ["notepad", "paint"]), ["notepad"])

    def test_spelling_repairs_only_real_app_names(self):
        apps = ["chrome", "spotify", "calculator", "notepad", "visual studio code"]
        for query, expected in [("chrmoe", "chrome"), ("spoitfy", "spotify"),
                                ("calclatr", "calculator"), ("notpad", "notepad"),
                                ("kalkulator", "calculator"), ("vs code", "visual studio code")]:
            with self.subTest(query=query):
                self.assertEqual(rank_spelling(query, apps), [expected])
        self.assertEqual(rank_spelling("xqzblorp", apps), [])
        self.assertEqual(rank_spelling("pa", apps), [])
        self.assertEqual(set(rank_spelling("pint", ["paint", "print"])), {"paint", "print"})

    def test_button_typos_use_current_visible_labels(self):
        controls = [control("Save", 1), control("Settings", 2), control("Continue", 3),
                    control("Play (k)", 4), control("Delete", 5)]
        for query, expected in [("svae", 1), ("setings", 2), ("contnue", 3), ("ply", 4)]:
            with self.subTest(query=query):
                self.assertEqual([c["id"] for c in matches(controls, query)], [[expected]])
        self.assertEqual(matches(controls, "deleet"), [])
        self.assertEqual(matches(controls, "xqzblorp"), [])
        self.assertEqual(matches([control("Play", 1)], "pause"), [])

    def test_typo_website_opens_real_known_url(self):
        with tempfile.TemporaryDirectory() as directory:
            actions = Actions({"files_root": "files", "apps": {"chrome": ["chrome.exe"]}}, directory, lambda *args: None)
            try:
                with patch("jarvis.actions.subprocess.Popen") as launch:
                    actions.execute(parse("open youtub"))
                    launch.assert_called_once_with(["chrome.exe", "https://www.youtube.com/"], shell=False)
            finally:
                actions.close()

    def test_search_query_is_encoded_as_url_not_shell(self):
        self.assertEqual(url_for("youtube"), "https://www.youtube.com/")
        self.assertIn("q=a%26b", url_for("a&b", search=True))
        with self.assertRaises(ValueError):
            url_for("file:///C:/test.exe")

    def test_browser_action_uses_configured_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            actions = Actions({"files_root": "files", "apps": {"chrome": ["chrome.exe"]}}, directory, lambda *args: None)
            with patch("jarvis.actions.subprocess.Popen") as launch:
                actions.execute(parse("open youtube in chrome"))
                launch.assert_called_once_with(["chrome.exe", "https://www.youtube.com/"], shell=False)
            actions.close()

    def test_file_partial_name_and_numbered_disambiguation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            paths = [base / "Project_Budget_2026.xlsx", base / "Project_Budget_2025.xlsx"]
            for path in paths:
                path.touch()
            (fixture_path(base / ".jarvis-runtime/state/file_catalog.json")).write_text(json.dumps({"files": [str(p) for p in paths], "folders": []}))
            build(base)
            config = {"files_root": "files", "apps": {}, "file_catalog": ".jarvis-runtime/state/file_catalog.json"}
            catalog = Catalog(config, base)
            self.assertEqual(catalog.resolve("budget 2026", "file"), str(paths[0]))
            with self.assertRaises(AmbiguousName):
                catalog.resolve("my budget", "file")
            actions = Actions(config, base, lambda *args: None)
            with patch("jarvis.actions.os.startfile") as launch:
                self.assertIn("Which one", actions.execute(parse("open my budget")))
                launch.assert_not_called()
                actions.execute(parse("select option two"))
                launch.assert_called_once()
            actions.close()

    def test_deletion_still_uses_exact_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            actions = Actions({"files_root": "files", "apps": {}}, directory, lambda *args: None)
            (actions.root / "important notes.txt").touch()
            with self.assertRaises(ValueError):
                actions.execute(parse("delete file notes"))
            self.assertTrue((actions.root / "important notes.txt").exists())
            actions.close()


if __name__ == "__main__":
    unittest.main()
