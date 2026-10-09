from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jarvis.actions import Actions
from jarvis.commands import Command, parse
from jarvis.projects import Projects


class ProjectTests(unittest.TestCase):
    def test_open_project_root_uses_relocated_configured_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "New Projects"
            root.mkdir()
            actions = Actions({"files_root": "Files", "apps": {},
                               "project_roots": [str(root / "missing"), str(root)]},
                              directory, lambda *_: None)
            try:
                with patch("jarvis.actions.os.startfile") as opened:
                    self.assertEqual(actions.execute(Command("open_project_root")), f"Opened {root}")
                    opened.assert_called_once_with(str(root))
            finally:
                actions.close()

    def test_project_phrases_and_short_choice(self):
        examples = {
            "open my pending project": Command("project_list"),
            "which project was i using": Command("project_recent"),
            "tell me which project i was using": Command("project_recent"),
            "option 2": Command("choose_control", "2"),
            "open project folder from d drive": Command("open_project_root"),
            "open project InsTAREELS": Command("open_project", "InsTAREELS"),
        }
        for phrase, expected in examples.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(parse(phrase), expected)

    def test_discovers_directories_not_icon_files_and_remembers_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Projects"
            root.mkdir()
            alpha = root / "Alpha"
            beta = root / "Beta"
            alpha.mkdir()
            beta.mkdir()
            (alpha / "package.json").write_text("{}", encoding="utf-8")
            (beta / "pyproject.toml").write_text("", encoding="utf-8")
            (root / "PythonProject.ico").write_bytes(b"icon")
            projects = Projects(directory, [str(root)])
            self.assertEqual({p.name for p in projects.list()}, {"Alpha", "Beta"})
            self.assertEqual(projects.resolve("alpha"), alpha)
            with self.assertRaises(ValueError):
                projects.resolve("PythonProject")
            projects.remember(alpha)
            self.assertEqual(projects.last(), (alpha, True))

    def test_spoken_name_consumes_pending_list_before_planner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Projects"
            root.mkdir()
            alpha = root / "Alpha"
            alpha.mkdir()
            (alpha / "package.json").write_text("{}", encoding="utf-8")
            events = []
            actions = Actions({"files_root": "Files", "apps": {}, "project_roots": [str(root)]}, directory,
                              lambda *event: events.append(event))
            self.assertIn("Alpha", actions.execute(Command("project_list")))
            with patch.object(actions, "_open_project", return_value="Opened Alpha") as opened:
                self.assertEqual(actions.execute(Command("task", "Alpha")), "Opened Alpha")
            opened.assert_called_once()
            actions.brain.client.request = lambda *_a, **_k: self.fail("Planner was called")
            actions.close()

    def test_project_launch_uses_codex_workspace_and_chrome_youtube(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "Alpha"
            project.mkdir()
            actions = Actions({"files_root": "Files", "apps": {"chrome": ["chrome.exe"]},
                               "project_roots": [directory]}, directory, lambda *_: None)
            with patch("jarvis.actions.os.startfile") as explorer, patch("jarvis.actions.subprocess.Popen") as launch, \
                    patch("shutil.which", return_value="codex.exe"):
                result = actions._open_project(project, lambda: False)
            self.assertIn("YouTube in Chrome", result)
            explorer.assert_called_once_with(str(project))
            self.assertEqual(launch.call_args_list[0].args[0], ["codex.exe", "app", str(project)])
            self.assertEqual(launch.call_args_list[1].args[0], ["chrome.exe", "https://www.youtube.com/"])
            actions.close()

    def test_open_folder_name_uses_real_project_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "Alpha"
            project.mkdir()
            (project / "package.json").write_text("{}", encoding="utf-8")
            actions = Actions({"files_root": "Files", "apps": {}, "project_roots": [directory]},
                              directory, lambda *_: None)
            with patch("jarvis.actions.os.startfile") as explorer:
                result = actions.execute(Command("open_folder", "Alpha"))
            self.assertIn(str(project), result)
            explorer.assert_called_once_with(str(project))
            actions.close()


if __name__ == "__main__":
    unittest.main()
