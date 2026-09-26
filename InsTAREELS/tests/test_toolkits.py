import base64
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, MagicMock, patch

import requests
from jarvis.commands import parse
from jarvis.engine import Engine
from jarvis.actions import Actions
from jarvis.brain import Brain
from jarvis.task_state import TaskState
from jarvis.tools import ToolRegistry
from jarvis.toolkits import TOOLS, api, execute, public_url, remote_tool, status


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"
        self.root.mkdir()
        self.actions = Mock()
        self.actions._task_folder.return_value = self.root
        self.actions.task_state = TaskState(self.base)
        self.actions.task_state.start("tool test", "toolkit", self.root)

    def step(self, name, value=".", content=""):
        return {"action": name, "value": value, "content": content, "folder": str(self.root)}

    def test_file_list_read_search_and_resource_query_without_mutation(self):
        (self.root / "note.txt").write_bytes(b"hello world\nneedle")
        (self.root / ".hidden").write_text("needle")
        (self.root / "credentials.txt").write_text("needle")
        self.assertEqual(execute(self.actions, self.step("list_files"), lambda: False), "note.txt")
        self.assertEqual(execute(self.actions, self.step("read_file", "note.txt"), lambda: False), "hello world\nneedle")
        for tool in ("search_files", "query_resource", "knowledge_search"):
            text = execute(self.actions, self.step(tool, "needle"), lambda: False)
            self.assertIn("note.txt:2: needle", text)
            self.assertNotIn("credentials", text)
        self.assertEqual((self.root / "note.txt").read_text(), "hello world\nneedle")

    def test_scope_hidden_traversal_and_oversized_files_rejected(self):
        (self.root / "large.txt").write_bytes(b"x"*20001)
        for name in ("../outside.txt", ".hidden", "large.txt", str(self.base / "outside.txt")):
            with self.subTest(name=name), self.assertRaises(ValueError):
                execute(self.actions, self.step("read_file", name), lambda: False)

    def test_append_preserves_exact_bytes_and_creates_review(self):
        path = self.root / "note.txt"
        path.write_bytes(b"hello\r\n")
        result = execute(self.actions, self.step("append_file", "note.txt", "world\r\n"), lambda: False)
        self.assertIn("verified", result)
        self.assertEqual(path.read_bytes(), b"hello\r\nworld\r\n")
        backups = list((self.base / ".jarvis-runtime/coding").glob("*/originals/note.txt"))
        self.assertEqual(backups[0].read_bytes(), b"hello\r\n")

    def test_uncertain_append_never_replayed_and_checkpoint_blocks_resume(self):
        path = self.root / "note.txt"
        path.write_text("first", encoding="utf-8")
        replace = os.replace
        commits = []
        def fault(source, target):
            replace(source, target)
            if Path(target) == path:
                commits.append(target)
                raise OSError("uncertain commit")
        with patch("jarvis.toolkits.os.replace", side_effect=fault), self.assertRaises(OSError):
            execute(self.actions, self.step("append_file", "note.txt", "second"), lambda: False)
        self.assertEqual(len(commits), 1)
        self.assertEqual(path.read_text(), "firstsecond")
        self.assertIn("not verified", TaskState.resume_blocker(self.actions.task_state.snapshot()))

    def test_missing_credentials_are_clear_and_never_shown(self):
        with patch.dict(os.environ, {}, clear=True), patch("jarvis.toolkits.remote_tool") as remote:
            with self.assertRaisesRegex(ValueError, "JARVIS_SLACK_TOKEN"):
                execute(self.actions, self.step("slack_send", "channel", "hi"), lambda: False)
            self.assertFalse(next(row for row in status() if row["tool"] == "slack_send")["configured"])
        remote.assert_not_called()
        self.actions._approve.assert_not_called()

    def test_external_write_requires_approval_and_never_retries_timeout(self):
        step = self.step("slack_send", "channel", "exact message")
        with patch.dict(os.environ, {"JARVIS_SLACK_TOKEN": "test-secret-token"}), \
                patch("jarvis.toolkits.remote_tool", side_effect=requests.Timeout("test-secret-token")) as remote:
            with self.assertRaisesRegex(ValueError, "inspect external state") as error:
                execute(self.actions, step, lambda: False)
        self.actions._approve.assert_called_once()
        self.assertIn("exact message", self.actions._approve.call_args.args[1])
        remote.assert_called_once()
        self.assertNotIn("test-secret-token", str(error.exception))
        self.assertIn("not verified", TaskState.resume_blocker(self.actions.task_state.snapshot()))

    def test_rejected_approval_and_shutdown_prevent_network_write(self):
        with patch.dict(os.environ, {"JARVIS_SLACK_TOKEN": "test-token"}), patch("jarvis.toolkits.remote_tool") as remote:
            self.actions._approve.side_effect = ValueError("approval denied")
            with self.assertRaisesRegex(ValueError, "approval denied"):
                execute(self.actions, self.step("slack_send", "channel", "hi"), lambda: False)
            with self.assertRaisesRegex(ValueError, "cancelled"):
                execute(self.actions, self.step("slack_send", "channel", "hi"), lambda: True)
        remote.assert_not_called()

    def test_catalog_filters_unconfigured_and_irrelevant_tools(self):
        with patch.dict(os.environ, {}, clear=True):
            tools = ToolRegistry(self.actions).catalog("Read file notes.txt in project")
            names = {tool["action"] for tool in tools}
            self.assertIn("read_file", names)
            self.assertNotIn("slack_send", names)
            self.assertNotIn("github_pull_request", names)
            self.assertIn("browse", names)

    def test_natural_commands_and_explicit_json_wait_for_final_speech(self):
        self.assertEqual(parse("read file notes.txt in Documents").value, "read_file")
        self.assertEqual(parse("list files in Documents").value, "list_files")
        self.assertEqual(parse("append to file notes.txt in Documents: hello").value, "append_file")
        command = 'tool slack_send {"value":"channel","content":"hello"}'
        self.assertEqual(parse(command).value, "slack_send")
        with self.assertRaises(ValueError):
            parse('tool slack_send {"action":"delete_file"}')
        sent = []
        engine = Engine(sent.append, Mock())
        engine.activate()
        engine.feed(command)
        self.assertEqual(sent, [])
        engine.feed(command, final=True)
        self.assertEqual(len(sent), 1)

    def test_private_urls_and_redirects_never_dispatch(self):
        for url in ("file:///secret", "https://user:password@example.com", "http://127.0.0.1/"):
            with self.assertRaises(ValueError):
                public_url(url)
        client = MagicMock()
        response = client.request.return_value.__enter__.return_value
        response.status_code = 302
        with patch("jarvis.toolkits.public_url"), self.assertRaisesRegex(ValueError, "Redirect refused"):
            api(client, "GET", "https://example.com", lambda: False)
        self.assertFalse(client.request.call_args.kwargs["allow_redirects"])

    def test_response_limit_and_cancellation_close_response(self):
        client = MagicMock()
        response = client.request.return_value.__enter__.return_value
        response.status_code = 200
        response.iter_content.return_value = [b"x"*1000001]
        with patch("jarvis.toolkits.public_url"), self.assertRaisesRegex(ValueError, "1 MB"):
            api(client, "GET", "https://example.com", lambda: False)
        client.request.return_value.__exit__.assert_called_once()
        client.reset_mock()
        with patch("jarvis.toolkits.public_url"), self.assertRaisesRegex(ValueError, "cancelled before"):
            api(client, "GET", "https://example.com", lambda: True)
        client.request.assert_not_called()

    def test_web_html_extraction_excludes_scripts(self):
        with patch("jarvis.toolkits.api", return_value="<h1>Hello</h1><script>secret()</script><p>World</p>"):
            result = remote_tool(Mock(), self.step("scrape_web", "https://example.com"), lambda: False)
        self.assertIn("Hello\nWorld", result)
        self.assertNotIn("secret()", result)

    def test_github_read_and_write_payloads(self):
        source = base64.b64encode(b"value = 1\n").decode()
        with patch("jarvis.toolkits.api", return_value=json.dumps({"encoding": "base64", "size": 10, "content": source})) as request:
            result = remote_tool(Mock(), self.step("github_read_file", "owner/repo", '{"path":"app.py"}'), lambda: False)
        self.assertEqual(result, "value = 1\n")
        self.assertIn("/repos/owner/repo/contents/app.py", request.call_args.args[2])
        with patch("jarvis.toolkits.api", return_value="{}") as request:
            remote_tool(Mock(), self.step("github_add_file", "owner/repo", '{"path":"app.py","message":"Update","text":"x=2","sha":"abc"}'), lambda: False)
        self.assertEqual(request.call_args.args[1], "PUT")
        self.assertEqual(request.call_args.kwargs["json"]["sha"], "abc")

    def test_remote_provider_payloads_and_calendar_no_invitations(self):
        variables = {key: "testvalue" for data in TOOLS.values() for key in data[2]}
        variables.update(JARVIS_JIRA_URL="https://example.atlassian.net", JARVIS_SEARX_URL="https://example.com")
        cases = [("google_search", "GET", "{}"), ("serp_search", "GET", "{}"), ("searx_search", "GET", "{}"),
                 ("apollo_search", "POST", "{}"), ("slack_send", "POST", "message"), ("twitter_send", "POST", "message"),
                 ("calendar_list", "GET", ""), ("calendar_details", "GET", '{"event_id":"a"}'),
                 ("calendar_delete", "DELETE", '{"event_id":"a"}'),
                 ("calendar_create", "POST", '{"summary":"s","start":{"date":"2026-10-01"},"end":{"date":"2026-10-02"}}'),
                 ("jira_projects", "GET", ""), ("jira_search", "GET", ""),
                 ("jira_create", "POST", '{"fields":{"summary":"s"}}'), ("jira_edit", "PUT", '{"fields":{"summary":"s"}}')]
        with patch.dict(os.environ, variables):
            for name, method, content in cases:
                with self.subTest(tool=name), patch("jarvis.toolkits.api", return_value='{"ok":true}') as request:
                    remote_tool(Mock(), self.step(name, "target", content), lambda: False)
                    self.assertEqual(request.call_args.args[1], method)
            with patch("jarvis.toolkits.api") as request, self.assertRaises(ValueError):
                remote_tool(Mock(), self.step("calendar_create", "primary", '{"summary":"s","start":{},"end":{},"attendees":[]}'), lambda: False)
            request.assert_not_called()

    def test_reasoning_uses_existing_brain_with_untrusted_context(self):
        self.actions.brain.client.request.return_value = {"text": "Proposed test"}
        result = execute(self.actions, self.step("write_tests", "test addition", "def add(a,b): return a+b"), lambda: False)
        self.assertEqual(result, "Proposed test")
        call = self.actions.brain.client.request.call_args
        self.assertEqual(call.args[0], "tool_text")
        self.assertIn("def add", call.kwargs["context"])

    def test_real_action_dispatch_tracks_toolkit_without_resuming_prior_task(self):
        (self.root / "notes.txt").write_bytes(b"example")
        actions = Actions({"files_root": "files", "apps": {}}, self.base, Mock())
        actions._task_folder = lambda folder, cancelled: self.root
        try:
            result = actions.execute(parse("read file notes.txt in project"))
            self.assertEqual(result, "example")
            task = actions.task_state.snapshot()
            self.assertEqual(task["kind"], "toolkit")
            self.assertEqual(task["status"], "completed")
            self.assertFalse(actions.task_active)
        finally:
            actions.close()

    def test_planner_cannot_invent_external_send_or_append_text(self):
        brain = Brain(self.actions, self.base, {})
        with self.assertRaisesRegex(ValueError, "not explicitly requested"):
            brain.validate_remaining([self.step("slack_send", "channel", "hello")], "Research Python")
        with self.assertRaisesRegex(ValueError, "explicit exact text"):
            brain.validate_remaining([self.step("append_file", "notes.txt", "invented")], "append hello to notes.txt")
        brain.validate_remaining([self.step("slack_send", "channel", "hello")], "send hello in Slack")

    def test_authenticated_http_is_blocked_before_dispatch(self):
        client = Mock()
        with patch("jarvis.toolkits.public_url"), self.assertRaisesRegex(ValueError, "HTTPS"):
            api(client, "GET", "http://example.com", lambda: False, auth=("u", "password"))
        client.request.assert_not_called()

    def test_planned_read_supplies_actual_tool_data_to_final_goal_check(self):
        (self.root / "notes.txt").write_bytes(b"The meeting is at noon.")
        self.actions.apps = {}
        self.actions.pending_open = None
        self.actions.last_created = self.actions.last_modified = self.actions.last_deleted = self.actions.last_command = None
        brain = Brain(self.actions, self.base, {"enabled": True, "planner": "qwen3.5:4b", "decision": "qwen3.5:4b"})
        brain.observe = Mock(return_value=(0, {"title": "Desktop", "controls": []}))
        brain.observe_after_action = Mock(return_value=(0, {"title": "Desktop", "controls": []}))
        step = {**self.step("read_file", "notes.txt"), "expected": "Read the file"}
        brain.client = Mock()
        def inference(operation, cancelled, **data):
            if operation == "plan":
                return {"steps": [step]}
            if operation == "decide":
                return {"approved": True}
            self.assertIn("The meeting is at noon", " ".join(data["screen"]["trusted_evidence"]))
            return {"verified": True}
        brain.client.request.side_effect = inference
        self.assertIn("Finished", brain.run("Read notes.txt in project", lambda: False))

    def test_imap_reads_without_marking_seen_and_smtp_rejects_headers(self):
        variables = {"JARVIS_IMAP_HOST": "mail.example.com", "JARVIS_SMTP_HOST": "mail.example.com",
                     "JARVIS_EMAIL_USER": "me@example.com", "JARVIS_EMAIL_PASSWORD": "test-password"}
        mailbox = Mock()
        mailbox.search.return_value = ("OK", [b"1 2"])
        mailbox.fetch.return_value = ("OK", [(b"header", b"Subject: Test")])
        with patch.dict(os.environ, variables), patch("jarvis.toolkits.public_url"), \
                patch("jarvis.toolkits.imaplib.IMAP4_SSL") as connection:
            connection.return_value.__enter__.return_value = mailbox
            result = remote_tool(Mock(), self.step("read_email"), lambda: False)
        self.assertIn("Subject: Test", result)
        mailbox.select.assert_called_once_with("INBOX", readonly=True)
        self.assertIn("PEEK", mailbox.fetch.call_args.args[1])
        with patch.dict(os.environ, variables), patch("jarvis.toolkits.smtplib.SMTP_SSL") as smtp:
            with self.assertRaises(ValueError):
                remote_tool(Mock(), self.step("send_email", "a@example.com\nBcc:evil@example.com", '{"subject":"s","body":"b"}'), lambda: False)
        smtp.assert_not_called()
