import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jarvis.actions import Actions
from jarvis.commands import Command, parse
from jarvis.gods_eye_view import GodsEyeView, URL


class GodsEyeViewTests(unittest.TestCase):
    def test_voice_command_is_direct(self):
        for phrase in ("Open God's Eye View", "launch gods eye view", "show god's eye"):
            self.assertEqual(parse(phrase), Command("gods_eye_view", "", "chrome"))
        self.assertEqual(parse("Open God's Eye View in Edge"), Command("gods_eye_view", "", "edge"))

    def test_missing_local_install_explains_setup(self):
        with tempfile.TemporaryDirectory() as folder, patch("jarvis.gods_eye_view.ready", return_value=False):
            with self.assertRaisesRegex(ValueError, "not installed"):
                GodsEyeView(Path(folder)).start()

    def test_existing_server_is_reused(self):
        with tempfile.TemporaryDirectory() as folder, patch("jarvis.gods_eye_view.ready", return_value=True):
            app = GodsEyeView(Path(folder))
            self.assertEqual(app.start(), URL)
            self.assertIsNone(app.process)

    def test_action_opens_local_console_in_browser(self):
        actions = Actions.__new__(Actions)
        actions.projects = Mock(pending=None)
        actions.report = Mock()
        actions.gods_eye_view = Mock()
        actions.gods_eye_view.start.return_value = URL
        actions.apps = {"chrome": ["chrome.exe"]}
        actions.desktop = None
        with patch("jarvis.actions.subprocess.Popen") as launched:
            result = actions.execute(Command("gods_eye_view"))
        actions.gods_eye_view.start.assert_called_once()
        launched.assert_called_once_with(["chrome.exe", URL], shell=False)
        self.assertIn("God's Eye View", result)


if __name__ == "__main__":
    unittest.main()
