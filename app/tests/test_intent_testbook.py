"""Natural-language coverage: the 800-scenario testbook, its permutations, and the handlers behind them."""
import json
import tempfile
import threading
import time
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis import intent_handlers as handlers
from jarvis.commands import Command, parse
from jarvis.phrasing import canonical

try:
    from tests.intent_permutations import scenarios, variants
except ImportError:  # Run from inside tests/.
    from intent_permutations import scenarios, variants

EXPECTED = json.loads((Path(__file__).parent / "fixtures" / "intent_testbook_expected.json").read_text(encoding="utf-8"))


def kind(text):
    try:
        return parse(text).kind
    except ValueError:
        return "unparsed"


class TestbookTests(unittest.TestCase):
    def test_every_scenario_and_its_three_phrasings_reach_the_expected_intent(self):
        rows = scenarios()
        self.assertEqual(len(rows), 800)
        for number, direct, polite, everyday in rows:
            for text in (direct, polite, everyday):
                with self.subTest(number=number, text=text):
                    self.assertEqual(kind(text), EXPECTED[number])

    def test_permutations_reach_the_same_intent(self):
        total = 0
        for number, direct, *_ in scenarios():
            for text in variants(direct):
                total += 1
                with self.subTest(number=number, text=text):
                    self.assertEqual(kind(text), EXPECTED[number])
        self.assertGreater(total, 15000)

    def test_every_behavior_answer_exists(self):
        for number, direct, *_ in scenarios():
            if EXPECTED[number] == "behavior":
                with self.subTest(number=number):
                    self.assertIn(parse(direct).value, handlers.BEHAVIOR)

    def test_values_that_matter(self):
        self.assertEqual(parse("Close this tab, not the entire browser."), Command("windows_command", "[329]", "{}"))
        self.assertEqual(parse("Never mind; leave the current work untouched."), Command("behavior", "nothing_cancelled"))
        self.assertEqual(parse("Could you cancel everything in the queue?").kind, "cancel_all")
        self.assertEqual(parse("Place the video in full screen."), Command("media_control", "fullscreen", "youtube"))
        self.assertEqual(parse("Type these exact words: The build PASSED at 5:30 PM.").value, "The build PASSED at 5:30 PM.")
        self.assertEqual(parse("Keep in mind that this project is called Jarvis.").value, "this project is called Jarvis")
        self.assertEqual(json.loads(parse("Write this in a professional tone.").extra)["target"], "")
        self.assertEqual(parse("Bring up YouTube, find Nadaan Parindey and play the official video."),
                         Command("play_media", "Nadaan Parindey official", "youtube"))
        self.assertEqual(parse("Look up Spotify for Kun Faya Kun, play it and show the island card."),
                         Command("play_media", "Kun Faya Kun", "spotify"))
        self.assertEqual(parse("Take away task number two."), Command("cancel_task", "2"))
        self.assertEqual(parse("Change playback speed to 1.5 times."), Command("media_control", "speed_1.5", "youtube"))
        self.assertEqual(json.loads(parse("Fly the globe to the Statue of Liberty.").value)["place"], "the Statue of Liberty")
        self.assertEqual(json.loads(parse("Show me New York from above.").value)["place"], "New York")
        self.assertEqual(parse("Search my inbox for the word invoice.").kind, "task")
        self.assertEqual(parse("Don't do the email anymore").kind, "cancel_task")

    def test_phrasing_only_rewrites_the_head(self):
        self.assertEqual(canonical("Could you pull up my desktop?"), "show my desktop")
        self.assertEqual(canonical("Quick question: what's playing?"), "what's playing")
        self.assertEqual(canonical("Hey Jarvis, give me the gist of the three newest unread emails, please."),
                         "summarize the three newest unread emails")
        self.assertEqual(canonical("Write exactly: Hold the door, please."), "Write exactly: Hold the door, please.")
        self.assertEqual(canonical("Could you tell me when a call starts ringing?"), "tell me when a call starts ringing")

    def test_unmatched_negations_still_do_nothing(self):
        for text in ("don't open notepad", "never delete file notes"):
            with self.assertRaisesRegex(ValueError, "negated"):
                parse(text)


def fake_actions(**extra):
    base = Path(tempfile.mkdtemp())
    actions = SimpleNamespace(
        base=base, config={"wake_timeout_seconds": 90, "gpu_scheduler": {"warm_seconds": 1800}, "speech": {"speed": 1.0},
                           "weather_alerts": {"interval_minutes": 30}},
        session_style={}, task_history=deque(maxlen=40), command_history=deque(maxlen=20), last_spoken="", last_typed="",
        chat_only_until=0., quiet_alerts=False, private_mode=False, knowledge=SimpleNamespace(client=SimpleNamespace()),
        queue_lock=threading.Lock(), current_item=None, pending_tasks=[], approvals_waiting=0, whatsapp_prompts=[],
        submit=Mock(), report=Mock(), weather_watch=None, last_media=None)
    for key, value in extra.items():
        setattr(actions, key, value)
    return actions


class HandlerTests(unittest.TestCase):
    def test_behavior_answers_fill_in_live_settings(self):
        actions = fake_actions()
        self.assertIn("90 seconds", handlers.behavior(actions, "conversation_mode"))
        self.assertIn("30 minutes", handlers.behavior(actions, "performance"))
        self.assertNotIn("{", " ".join(handlers.behavior(actions, key) for key in handlers.BEHAVIOR))

    def test_session_style_reaches_the_question_model_and_speech(self):
        actions = fake_actions()
        handlers.conversation_style(actions, "short")
        self.assertEqual(actions.knowledge.client.answer_style, [handlers.STYLE_TEXT["short"]])
        self.assertEqual(handlers.conversation_style(actions, "simple", "Give me a simpler version."), "")
        actions.submit.assert_called_once_with(Command("ask", "Give me a simpler version."))
        handlers.conversation_style(actions, "slower")
        self.assertAlmostEqual(actions.config["speech"]["speed"], .9)
        handlers.conversation_style(actions, "slower")
        handlers.conversation_style(actions, "slower")
        self.assertAlmostEqual(actions.config["speech"]["speed"], .85)  # Kokoro's slowest.
        self.assertIn("short", handlers.jarvis_status(actions, "style").lower())

    def test_quiet_and_private_modes_filter_announcements(self):
        actions = fake_actions()
        message = "New WhatsApp message from Jay: see you at 6"
        self.assertEqual(handlers.filter_report(actions, "spoken_reply", message), ("spoken_reply", message))
        handlers.conversation_style(actions, "private")
        self.assertEqual(handlers.filter_report(actions, "spoken_reply", message), ("spoken_reply", "New WhatsApp message from Jay."))
        self.assertEqual(handlers.filter_report(actions, "spoken_reply", "Jay wrote: hello there"), ("spoken_reply", "Jay sent new messages."))
        handlers.conversation_style(actions, "quiet")
        self.assertEqual(handlers.filter_report(actions, "spoken_reply", "Weather alert for Vadodara: storm")[0], "log")
        self.assertEqual(handlers.filter_report(actions, "spoken_reply", "Here's your answer.")[0], "spoken_reply")
        handlers.conversation_style(actions, "unquiet")
        self.assertFalse(actions.quiet_alerts or actions.private_mode)

    def test_repeat_last(self):
        actions = fake_actions(last_spoken="First sentence. Second one!")
        self.assertEqual(handlers.repeat_last(actions, "all"), "First sentence. Second one!")
        self.assertEqual(handlers.repeat_last(actions, "sentence"), "Second one!")
        self.assertIn("haven't typed", handlers.repeat_last(actions, "typed"))

    def test_task_history_answers(self):
        actions = fake_actions()
        self.assertIn("No tasks", handlers.jarvis_status(actions, "recent_tasks"))
        actions.task_history.append({"what": "open notepad", "status": "done", "result": "Opened Notepad", "at": time.time()})
        actions.task_history.append({"what": "send email", "status": "failed", "result": "Gmail sign-in expired", "at": time.time()})
        self.assertIn("open notepad (done", handlers.jarvis_status(actions, "recent_tasks"))
        self.assertIn("Gmail sign-in expired", handlers.jarvis_status(actions, "last_failure"))
        actions.command_history.extend(["open notepad", "what did I ask"])
        self.assertEqual(handlers.jarvis_status(actions, "last_command"), "Before this you asked: open notepad")

    def test_pc_facts_are_read_live(self):
        actions = fake_actions()
        self.assertRegex(handlers.system_info(actions, "memory"), r"GB of [\d.]+ GB memory is free")
        self.assertTrue(handlers.system_info(actions, "windows").startswith("Windows "))
        self.assertIn("python", handlers.system_info(actions, "running", "python").lower())

    def test_public_speech_cpu_inflection_stays_a_read_only_native_query(self):
        for phrase in ('show CPU usage', 'shows CPU usage', 'shows the CPU load'):
            self.assertEqual(parse(phrase), Command('system_info','quick_cpu'))
        with self.assertRaises(ValueError):
            parse('shows files from my project')


class GodsEyeCameraTests(unittest.TestCase):
    def eye(self):
        from jarvis import gods_eye as ge
        browser = Mock()
        browser.request.return_value = {"results": [{"name": "get_current_view_state", "ok": True,
                                                     "result": {"camera": {"latitude": 48.8, "longitude": 2.3, "heightM": 2000}}}]}
        actions = SimpleNamespace(base=tempfile.mkdtemp(), config={}, report=Mock(), _browser=lambda: browser, realtime=None)
        eye = ge.GodsEye(actions, {})
        eye.ensure_server = Mock()
        return eye, browser

    def sent(self, browser):
        return [(a["name"], a["args"]) for a in browser.request.call_args.kwargs["actions"]]

    def test_zoom_pan_orbit_hide(self):
        eye, browser = self.eye()
        eye.camera({"zoom": "out", "amount": "lot"})
        self.assertEqual(self.sent(browser), [("adjust_camera_zoom", {"direction": "out", "amount": "lot"})])
        eye.camera({"move": "pan", "direction": "right"})
        self.assertEqual(self.sent(browser)[0][1]["direction"], "right")
        eye.camera({"move": "orbit"})
        self.assertEqual(self.sent(browser)[0][1]["motion"], "orbit")
        eye.enabled_layers = {"military", "cctv"}
        self.assertIn("cctv", eye.camera({"hide": ["*"]}))
        self.assertEqual(eye.enabled_layers, set())

    def test_overhead_label_where_and_back(self):
        eye, browser = self.eye()
        eye.camera({"overhead": True})
        name, args = self.sent(browser)[0]
        self.assertEqual((name, args["latitude"], args["viewMode"]), ("fly_to_location", 48.8, "overview"))
        self.assertIn("48.800, 2.300", eye.camera({"where": True}))
        browser.request.return_value = {"results": [{"name": "get_current_view_state", "ok": True, "result": {
            "camera": {"latitude": 48.6, "longitude": 2.3, "heightM": 9000}, "center": {"latitude": 48.858, "longitude": 2.294}}}]}
        self.assertIn("looking at 48.858, 2.294 from about 9.0 km up", eye.camera({"where": True}))  # Tilted view: the point seen.
        eye.last_view = {"latitude": 48.8, "longitude": 2.3, "altitude": 2000, "label": "Eiffel Tower"}
        self.assertEqual(eye.camera({"label": True}), "Labelled Eiffel Tower on the map.")
        self.assertIn("no earlier view", eye.camera({"back": True}))
        eye.view_history = [{"latitude": 51.5, "longitude": -.1, "altitude": 9000, "label": "London"}]
        self.assertEqual(eye.camera({"back": True}), "Back to London.")
        self.assertIn("haven't drawn a route", eye.camera({"fly_route": True}))


class RepoAspectTests(unittest.TestCase):
    def test_aspects_answer_from_saved_knowledge(self):
        from jarvis.repo_learning import execute
        data = {"full_name": "psf/requests", "summary": {"purpose": "HTTP", "how_to_run": "pip install requests", "key_modules": []},
                "license": "Apache-2.0", "entry_points": ["src/requests/__init__.py"], "manifests": ["pyproject.toml"],
                "has_tests": True, "tree": ["src/", "tests/"], "languages": {"Python": 40}, "files_total": 60}
        learner = SimpleNamespace(enabled=True, viewing={"full_name": "psf/requests"}, index={"psf/requests": {"used_for": ["fetch a page"]}},
                                  knowledge=lambda name: data)
        actions = SimpleNamespace(repo_learner=learner)
        ask = lambda aspect: execute(actions, Command("repo_explain", "", aspect), lambda: False)
        self.assertIn("Apache-2.0", ask("license"))
        self.assertIn("src/requests/__init__.py", ask("entry"))
        self.assertIn("pyproject.toml", ask("dependencies"))
        self.assertIn("tests/", ask("tests"))
        self.assertIn("pip install requests", ask("setup"))
        self.assertIn("fetch a page", ask("used_for"))


class CuratorTests(unittest.TestCase):
    def test_save_now_and_pause(self):
        from jarvis.memory_curator import MemoryCurator
        jobs = []
        curator = SimpleNamespace(lock=threading.Lock(), turns=[{"q": "a"}, {"q": "b"}], _queue=jobs.append)
        self.assertEqual(MemoryCurator.save_now(curator), 2)
        self.assertEqual(jobs[0][0], "summary")
        self.assertEqual(curator.turns, [])
        paused = SimpleNamespace(enabled=True, paused=True, turns=[])
        MemoryCurator.observe(paused, "remember that I like tea", "ok")
        self.assertEqual(paused.turns, [])


if __name__ == "__main__":
    unittest.main()
