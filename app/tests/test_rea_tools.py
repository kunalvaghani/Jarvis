import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from jarvis.commands import parse
from jarvis.task_state import TaskState
from jarvis import rea_tools
from jarvis.toolkits import TOOLS, execute


class ReaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.target = self.base.parent / ("rea-target-" + self.base.name)
        self.target.mkdir()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.target, ignore_errors=True))
        (self.target / "index.js").write_text("console.log(1)\n")
        self.actions = Mock()
        self.actions.base = str(self.base)
        self.actions.config = {"rea": {"enabled": True, "allow_commands": ["analyze-javascript-application"]}}
        self.actions.task_state = TaskState(self.base)
        self.actions.task_state.start("rea test", "toolkit", self.base)
        self.approvals = []
        self.actions._approve.side_effect = lambda *a, **k: self.approvals.append(a)

    def step(self, name, value=".", content=""):
        return {"action": name, "value": value, "content": content}

    def run_tool(self, name, value=".", content=""):
        return json.loads(execute(self.actions, self.step(name, value, content), lambda: False))

    def test_tools_registered(self):
        for name in ("rea_status", "rea_ingest", "rea_analyze", "rea_ledger", "rea_record"):
            self.assertIn(name, TOOLS)
        self.assertTrue(TOOLS["rea_analyze"][3], "rea_analyze must be an approved external action")
        self.assertFalse(TOOLS["rea_ingest"][3], "rea_ingest must not require approval")

    def test_status_reports_not_ready_without_entry(self):
        status = self.run_tool("rea_status")
        self.assertFalse(status["ready"])
        self.assertFalse(status["rea_entry_configured"])
        self.assertEqual(status["allow_commands"], ["analyze-javascript-application"])

    def test_ingest_creates_session_and_ledger(self):
        result = self.run_tool("rea_ingest", str(self.target))
        session = result["session"]
        self.assertEqual(result["kind"], "application")
        workspace = self.base / ".jarvis-runtime" / "rea" / session
        self.assertTrue((workspace / "session.json").is_file())
        self.assertTrue((workspace / "ledger.md").is_file())
        listed = self.run_tool("rea_ledger", ".")
        self.assertEqual(len(listed["sessions"]), 1)

    def test_ingest_rejects_relative_and_private_targets(self):
        for bad in ("relative/path", "http://127.0.0.1/x", "https://localhost/app"):
            with self.assertRaises(ValueError):
                self.run_tool("rea_ingest", bad)

    def test_ingest_rejects_runtime_internal_path(self):
        with self.assertRaises(ValueError):
            self.run_tool("rea_ingest", str(self.base))

    def test_record_appends_obligation(self):
        session = self.run_tool("rea_ingest", str(self.target))["session"]
        self.run_tool("rea_record", session, json.dumps({"kind": "obligation", "text": "Reproduce search ranking"}))
        ledger = self.run_tool("rea_ledger", session)["ledger"]
        self.assertIn("Reconstruction obligation", ledger)
        self.assertIn("Reproduce search ranking", ledger)
        with self.assertRaises(ValueError):
            self.run_tool("rea_record", session, json.dumps({"kind": "bogus", "text": "x"}))

    def test_analyze_fails_closed_without_node_or_entry(self):
        session = self.run_tool("rea_ingest", str(self.target))["session"]
        with self.assertRaises(ValueError):
            self.run_tool("rea_analyze", session, json.dumps({"command": "analyze-javascript-application"}))

    def test_analyze_rejects_non_allowlisted_command(self):
        session = self.run_tool("rea_ingest", str(self.target))["session"]
        self.actions.config["rea"]["node_path"] = None
        with self.assertRaises(ValueError):
            self.run_tool("rea_analyze", session, json.dumps({"command": "rm-rf"}))

    def test_natural_language_commands(self):
        command = parse("reverse engineer the app D:/apps/example")
        self.assertEqual(command.kind, "toolkit")
        self.assertEqual(command.value, "rea_ingest")
        self.assertEqual(json.loads(command.extra)["value"], "D:/apps/example")
        status = parse("check rea status")
        self.assertEqual((status.kind, status.value), ("toolkit", "rea_status"))


if __name__ == "__main__":
    unittest.main()
