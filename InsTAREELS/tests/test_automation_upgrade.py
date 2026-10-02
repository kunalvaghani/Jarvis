import json
from pathlib import Path
import queue
import tempfile
import unittest
from urllib.parse import urlparse
from unittest.mock import Mock
from types import SimpleNamespace

from jarvis.brain import validate_plan
from jarvis.browser_worker import parsed, Session
from jarvis.fast_workflows import compile_workflow, choose_result, run, search_ready
from jarvis.targeting import scoped_matches
from jarvis.task_state import TaskState
from jarvis.ui_transport import UITransport
from jarvis.grounding import direct_decision


def control(name, i, context="", href=None):
    row = {"name": name, "id": [i], "role": "Hyperlink", "rect": [200, i*30, 400, i*30+20], "context": context}
    if href:
        row["href"] = href
    return row


class WorkflowTests(unittest.TestCase):
    def test_ordinals_and_queries_are_preserved(self):
        for goal in ("open youtube and search rock and roll and play first video", "search youtube for rock and roll and play first video"):
            steps = compile_workflow(goal, {})
            self.assertEqual(steps[0]["value"], "rock and roll")
            self.assertEqual(steps[1]["position"], 1)

    def test_unknown_clauses_never_silently_dropped(self):
        self.assertIsNone(compile_workflow("open youtube and search cats and delete all files", {}))
        self.assertIsNone(compile_workflow("open chrome and open unknown app", {"chrome": ["chrome.exe"]}))
        self.assertIsNone(compile_workflow("open youtube in edge and search cats and play first video", {}))

    def test_native_spotify_route_and_named_song(self):
        steps = compile_workflow("play Dont Let Me Down on Spotify", {})
        self.assertEqual(steps[0]["platform"], "spotify")
        self.assertEqual(steps[1]["category"], "track")

    def test_duplicate_destination_is_one_choice_but_other_urls_stay_ambiguous(self):
        rows = [control("Python tutorial", 1, href="https://youtube.com/watch?v=a"), control("Python tutorial", 2, href="https://youtube.com/watch?v=a")]
        self.assertEqual(len(scoped_matches(rows, "Python tutorial")), 1)
        rows[1]["href"] = "https://youtube.com/watch?v=b"
        self.assertEqual(len(scoped_matches(rows, "Python tutorial")), 2)

    def test_named_context_disambiguates(self):
        rows = [dict(control("Play", 1, "Python tutorial"), role="Button"), dict(control("Play", 2, "Music tutorial"), role="Button")]
        self.assertEqual(scoped_matches(rows, "Play for Python tutorial"), rows[:1])

    def test_first_video_excludes_ads_channels_and_player_controls(self):
        snapshot = {"title": "cats - YouTube", "controls": [control("Ad cat video", 1, "Sponsored", "https://youtube.com/watch?v=ad"),
            control("Cat channel", 2, href="https://youtube.com/@cats"), control("Cat video", 3, href="https://youtube.com/watch?v=cat")]}
        self.assertEqual(choose_result(snapshot, {"category": "video", "position": 1})["id"], [3])

    def test_spotify_live_combo_and_song_row_shapes(self):
        snapshot = {"title": "Spotify", "context": json.dumps(["C:/Spotify.exe"]), "controls": [
            dict(control("The+Chainsmokers+Dont+Let+Me+Down", 1), role="ComboBox"),
            dict(control("Don't Let Me Down", 2, "Your Library"), role="DataItem"),
            dict(control("Don't Let Me Down", 3, "Music videos"), role="DataItem"),
            dict(control("Don't Let Me Down", 4, "Search results"), role="DataItem", metadata="Song • The Chainsmokers, Daya"),
            dict(control("Play Don't Let Me Down", 5, "Don't Let Me Down"), role="DataItem")]}
        self.assertTrue(search_ready(snapshot, "spotify", "The Chainsmokers Dont Let Me Down"))
        self.assertFalse(search_ready(snapshot, "spotify", "a different query"))
        self.assertEqual(choose_result(snapshot, {"category": "track", "value": "The Chainsmokers Dont Let Me Down"})["id"], [4])

    def fixture(self, folder, response):
        actions = Mock()
        actions.apps = {}
        actions.base = Path(folder)
        actions.config = {"agent_runtime": {"dom_browser": True}}
        actions.resume_source = None
        actions.task_state = TaskState(folder)
        actions.task_state.start("open youtube and search cats and play first video", "task")
        actions._browser.return_value.request.side_effect = response
        return actions

    def test_supported_workflow_uses_no_models_and_records_verified_steps(self):
        with tempfile.TemporaryDirectory() as folder:
            actions = self.fixture(folder, [{"verified": True, "message": "query observed"}, {"verified": True, "message": "selected identity and playback observed"}])
            result = run(actions, "open youtube and search cats and play first video", lambda: False)
            self.assertIn("Finished", result)
            self.assertEqual(actions.task_state.snapshot()["stage"], "goal_verified")
            actions.brain.run.assert_not_called()
            self.assertEqual(actions._browser.return_value.request.call_count, 2)

    def test_uncertain_browser_action_not_replayed_or_promoted(self):
        with tempfile.TemporaryDirectory() as folder:
            actions = self.fixture(folder, [RuntimeError("lost response")])
            with self.assertRaisesRegex(RuntimeError, "lost response"):
                run(actions, "open youtube and search cats and play first video", lambda: False)
            self.assertEqual(actions._browser.return_value.request.call_count, 1)
            self.assertTrue(TaskState.resume_blocker(actions.task_state.snapshot()))
            self.assertFalse(any(c["stage"] == "goal_verified" for c in actions.task_state.snapshot()["checkpoints"]))

    def test_unverified_dom_result_and_cancellation_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            actions = self.fixture(folder, [{"verified": False}])
            with self.assertRaisesRegex(ValueError, "without verification"):
                run(actions, "open youtube and search cats and play first video", lambda: False)
            self.assertEqual(actions._browser.return_value.request.call_count, 1)
            actions._browser.return_value.request.reset_mock()
            with self.assertRaisesRegex(ValueError, "cancelled"):
                run(actions, "open youtube and search cats and play first video", lambda: True)
            actions._browser.return_value.request.assert_not_called()

    def test_playwright_predicate_accepts_parse_result(self):
        url = urlparse("https://youtube.com/results?search_query=cats")
        self.assertEqual(parsed(url).path, "/results")
        self.assertEqual(parsed(url.geturl()).query, "search_query=cats")

    def test_browser_fill_requires_observed_url_and_bounded_payload(self):
        with self.assertRaises(ValueError):
            validate_plan({"steps": [{"action": "browser_fill", "value": "Search", "content": "x", "expected": "filled"}]})
        with self.assertRaises(ValueError):
            validate_plan({"steps": [{"action": "browser_click", "value": "Send", "folder": "https://example.com", "expected": "sent"}]})

    def test_user_closed_browser_not_reopened(self):
        session = Session()
        session.context, session.page = Mock(), Mock()
        session.page.is_closed.return_value = True
        with self.assertRaisesRegex(ValueError, "closed deliberately"):
            session.open({})
        self.assertTrue(session.user_closed)

    def test_explicit_search_uses_owned_browser_without_uia_attempt(self):
        from jarvis.actions import Actions
        from jarvis.commands import Command
        actions = Actions.__new__(Actions)
        actions.config = {"agent_runtime": {"dom_browser": True}}
        actions.browser_automation = None
        actions.projects = SimpleNamespace(pending=None)
        actions.report = Mock()
        actions.ui_controls = None
        actions.desktop = None
        actions._browser = Mock()
        actions._browser.return_value.request.return_value = {"message": "verified search"}
        actions._ui = Mock(side_effect=AssertionError("unexpected UIA attempt"))
        self.assertEqual(actions._execute(Command("media_search", "cats", "youtube")), "verified search")
        actions._browser.return_value.request.assert_called_once_with("search", unittest.mock.ANY, value="cats", new_task=True)

    def test_browser_volume_acknowledgement_requires_actual_readback(self):
        session = Session()
        session.page = Mock()
        session.page.url = "https://www.youtube.com/watch?v=test"
        video = session.page.locator.return_value.first
        video.evaluate.side_effect = [{"volume": .5, "position": 1, "duration": 60, "speed": 1}, None,
            {"paused": True, "muted": False, "volume": .5, "position": 1, "duration": 60, "ready": 4, "speed": 1}]
        with self.assertRaisesRegex(ValueError, "requested value was not verified"):
            session.control("volume_20")
        self.assertEqual(video.evaluate.call_count, 3)

    def test_unique_explicit_grounding_skips_decision_inference(self):
        chosen = dict(control("Home", 1), role="Button")
        self.assertTrue(direct_decision({"action": "select", "value": "Home"}, "select Home", [chosen])["approved"])
        self.assertIsNone(direct_decision({"action": "select", "value": "Home"}, "find settings", [chosen]))
        self.assertIsNone(direct_decision({"action": "select", "value": "Home"}, "select Home", [chosen, chosen]))
        self.assertIsNone(direct_decision({"action": "select", "value": "Send"}, "select Send", [dict(chosen, name="Send")]))

    def test_direct_field_requires_exact_user_text_and_no_password(self):
        chosen = dict(control("Search", 1), role="Edit")
        step = {"action": "fill_text", "value": "Search", "content": "cats"}
        self.assertIsNotNone(direct_decision(step, "fill Search with cats", [chosen]))
        self.assertIsNone(direct_decision(step, "fill Search with dogs", [chosen]))
        self.assertIsNone(direct_decision(step, "fill Search with cats", [dict(chosen, password=True)]))


class FakeProcess:
    def __init__(self, responder=None):
        self.code = None
        self.lines, self.requests = queue.Queue(), []
        self.stdout = self
        self.stdin = self
        self.responder = responder or (lambda p: {"id": p["id"], "result": {"ready": True}})

    def __iter__(self):
        while True:
            line = self.lines.get()
            if line is None:
                return
            yield line

    def write(self, line):
        payload = json.loads(line)
        self.requests.append(payload)
        if payload["request"].get("operation") == "shutdown":
            self.kill()
        else:
            response = self.responder(payload)
            if response is not None:
                self.lines.put(json.dumps(response) + "\n")

    def flush(self):
        pass

    def poll(self):
        return self.code

    def kill(self):
        self.code = -1
        self.lines.put(None)

    def wait(self, timeout=None):
        return self.code

    def close(self):
        pass


class TransportTests(unittest.TestCase):
    def test_process_is_reused_and_each_request_sent_once(self):
        process = FakeProcess()
        factory = Mock(return_value=process)
        worker = UITransport(factory=factory)
        self.addCleanup(worker.close)
        worker.request({"operation": "list"})
        worker.request({"operation": "activate"})
        factory.assert_called_once()
        self.assertEqual(len(process.requests), 2)

    def test_provider_error_does_not_replay_and_next_read_can_use_worker(self):
        process = FakeProcess(lambda p: {"id": p["id"], "error": "target changed"})
        worker = UITransport(factory=Mock(return_value=process))
        self.addCleanup(worker.close)
        with self.assertRaisesRegex(ValueError, "target changed"):
            worker.request({"operation": "activate"})
        self.assertEqual(len(process.requests), 1)
        self.assertTrue(worker.healthy())

    def test_cancel_after_dispatch_kills_only_owned_worker_and_uses_backoff(self):
        process = FakeProcess(lambda p: None)
        now = [0]
        factory = Mock(return_value=process)
        worker = UITransport(factory=factory, clock=lambda: now[0])
        self.addCleanup(worker.close)
        cancelled = Mock(side_effect=[False, True])
        with self.assertRaisesRegex(RuntimeError, "without replay"):
            worker.request({"operation": "activate"}, cancelled)
        self.assertEqual(len(process.requests), 1)
        self.assertEqual(process.code, -1)
        self.assertFalse(worker.repair())
        factory.assert_called_once()
        now[0] = 3
        replacement = FakeProcess()
        factory.return_value = replacement
        self.assertTrue(worker.repair())
        self.assertEqual(replacement.requests, [])

    def test_timeout_lost_response_is_not_retried(self):
        process = FakeProcess(lambda p: None)
        worker = UITransport(factory=Mock(return_value=process), timeout=.01)
        self.addCleanup(worker.close)
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            worker.request({"operation": "activate"})
        self.assertEqual(len(process.requests), 1)

    def test_stop_prevents_restart_or_new_dispatch(self):
        factory = Mock()
        worker = UITransport(factory=factory)
        worker.close()
        self.assertFalse(worker.repair())
        with self.assertRaises(ValueError):
            worker.request({"operation": "list"})
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
