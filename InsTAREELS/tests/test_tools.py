import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from jarvis.actions import Actions
from jarvis.brain import ALLOWED
from jarvis.brain_worker import SCHEMAS
from jarvis.commands import Command
from jarvis.tools import TOOL_NAMES, ToolRegistry


class ToolTests(unittest.TestCase):
    def test_catalog_planner_and_executor_agree(self):
        catalog = ToolRegistry(Mock()).catalog()
        self.assertEqual({item["action"] for item in catalog}, ALLOWED)
        self.assertEqual(set(SCHEMAS["plan"]["properties"]["steps"]["items"]["properties"]["action"]["enum"]), set(TOOL_NAMES))
        self.assertEqual({item["backend"] for item in catalog}, {"files", "terminal", "browser", "desktop", "toolkit"})
        self.assertTrue({"delete_file", "run_command", "send_email", "github_delete_file", "slack_send", "calendar_delete"}
                        <= {item["action"] for item in catalog if item["approval"] == "user"})

    def test_routes_browser_terminal_and_desktop_without_replaying(self):
        actions = Mock()
        actions.execute.return_value = "Attempted"
        registry = ToolRegistry(actions)
        for action, expected in [
            ("browse", Command("browse", "example.com", "edge")),
            ("browser_search", Command("browser_search", "example.com", "edge")),
            ("run_command", Command("run_command", "example.com")),
            ("open", Command("open", "example.com")),
            ("close_app", Command("close_app", "example.com"))]:
            actions.execute.reset_mock()
            registry.execute({"action": action, "value": "example.com", "browser": "edge"}, lambda: False)
            self.assertEqual(actions.execute.call_count, 1)
            self.assertEqual(actions.execute.call_args.args[0], expected)
        result = registry.execute({"action": "media_search", "value": "jazz", "platform": "spotify"}, lambda: False)
        self.assertEqual(result.backend, "spotify")
        self.assertEqual(actions.execute.call_args.args[0], Command("media_search", "jazz", "spotify"))

    def test_select_requires_checked_control_and_cancellation_blocks_dispatch(self):
        actions, activate = Mock(), Mock(return_value="Activated Save")
        registry = ToolRegistry(actions)
        step = {"action": "select", "value": "Save"}
        with self.assertRaisesRegex(ValueError, "freshly checked"):
            registry.execute(step, lambda: False)
        result = registry.execute(step, lambda: False, activate)
        self.assertEqual(result.evidence, "Activated Save")
        activate.assert_called_once()
        actions.execute.assert_not_called()
        with self.assertRaisesRegex(ValueError, "cancelled"):
            registry.execute({"action": "open", "value": "chrome"}, lambda: True)
        actions.execute.assert_not_called()
        with self.assertRaisesRegex(ValueError, "Unsupported tool"):
            registry.execute({"action": "invented", "value": "anything"}, lambda: False)

    def test_real_file_tools_and_delete_approval_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "files"
            root.mkdir()
            (Path(directory) / "file_catalog.json").write_text(json.dumps({"folders": [str(root)], "files": []}))
            actions = Actions({"files_root": "files", "apps": {}, "file_catalog": "file_catalog.json"}, directory, Mock())
            registry = ToolRegistry(actions)
            try:
                step = {"action": "create_file", "value": "notes.txt", "folder": str(actions.root), "content": "hello"}
                registry.execute(step, lambda: False)
                path = actions.root / "notes.txt"
                self.assertEqual(path.read_text(), "hello")
                registry.execute({**step, "action": "modify_file", "find": "hello", "content": "updated"}, lambda: False)
                self.assertEqual(path.read_text(), "updated")
                actions.approval_handler = Mock(return_value=False)
                actions.recycler = Mock()
                with self.assertRaisesRegex(ValueError, "approval was not given"):
                    registry.execute({**step, "action": "delete_file"}, lambda: False)
                self.assertTrue(path.exists())
                actions.recycler.assert_not_called()
                actions.approval_handler.assert_called_once()
            finally:
                actions.close()
