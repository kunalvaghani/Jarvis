import json
import tempfile
import time
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis.cognition import Cognition, MODULES, NODES
from jarvis.commands import Command, parse
from jarvis.intent_handlers import execute as intent_execute


def actions(**extra):
    base = Path(tempfile.mkdtemp())
    return SimpleNamespace(base=base, whatsapp_prompts=[], current_item=None, pending_tasks=[], approvals_waiting=0,
                           session_style={}, memory=Mock(), **extra)


class WorldModelTests(unittest.TestCase):
    def test_prediction_before_any_history(self):
        mind = Cognition(actions())
        p = mind.predict(parse("send hi to mom on whatsapp"))
        self.assertEqual((p["kind"], p["external"], p["reversible"], p["needs_approval"]), ("whatsapp_send", True, False, True))
        self.assertEqual(p["success_chance"], .5)  # Unknown: 50/50.
        self.assertEqual(p["expected_seconds"], 25)
        self.assertEqual(p["uncertain"], [])
        self.assertIn("approval", mind.explain(p))
        self.assertIn("enough history", mind.explain(p))
        read = mind.predict(Command("jarvis_status", "uptime"))
        self.assertEqual((read["reversible"], read["needs_approval"]), (True, False))

    def test_learns_time_and_reliability_and_persists(self):
        a = actions()
        mind = Cognition(a)
        for _ in range(3):
            mind.act(Command("open", "notepad"), lambda: "Opened Notepad.")
        mind.act(Command("open", "notepad"), lambda: "I couldn't find Notepad.")
        stat = json.loads(mind.stats_path.read_text(encoding="utf-8"))["open"]
        self.assertEqual((stat["attempts"], stat["successes"], stat["failures"]), (4, 3, 1))
        self.assertIn("couldn't find", stat["last_failure"])
        p = Cognition(a).predict(Command("open", "notepad"))  # A new session reads the saved statistics.
        self.assertAlmostEqual(p["success_chance"], 4 / 6, places=2)
        self.assertIn("67%", Cognition(a).explain(p))

    def test_exception_is_a_failure_and_still_raised(self):
        mind = Cognition(actions())
        with self.assertRaises(RuntimeError):
            mind.act(Command("open", "x"), Mock(side_effect=RuntimeError("boom")))
        self.assertFalse(mind.last_outcome["ok"])
        self.assertEqual(mind.stats["open"]["last_failure"], "boom")

    def test_repeated_failure_becomes_a_lesson_in_the_vault(self):
        a = actions()
        mind = Cognition(a)
        for _ in range(3):
            mind.act(Command("play_media", "x"), lambda: "Failed: YouTube didn't load.")
        self.assertEqual(len(mind.lessons), 1)
        self.assertIn("play_media has failed 3 of 3", mind.lessons[0])
        a.memory.record.assert_called_once()
        self.assertEqual(a.memory.record.call_args[0][0], "Jarvis lesson")
        self.assertIn("failed 3 of the last 3", mind.predict(Command("play_media", "y"))["uncertain"][0])
        self.assertEqual(mind.relevant_lessons("play media on youtube"), [mind.lessons[0]])

    def test_your_correction_counts_as_failure(self):
        mind = Cognition(actions())
        mind.act(Command("play_media", "despacito"), lambda: "Playing Despacito.")
        mind.perceive_command(Command("task", "no, that's wrong", "unparsed"))  # How the engine sends it.
        self.assertEqual((mind.stats["play_media"]["successes"], mind.stats["play_media"]["corrections"]), (0, 1))
        self.assertIn("You corrected play_media", mind.lessons[-1])

    def test_disabled_runs_the_action_untouched(self):
        mind = Cognition(actions(), {"enabled": False})
        self.assertEqual(mind.act(Command("open", "x"), lambda: 7), 7)
        self.assertEqual(mind.stats, {})


class ExecutiveTests(unittest.TestCase):
    def test_asks_who_him_is_only_without_a_referent(self):
        a = actions()
        mind = Cognition(a)
        question = mind.deliberate(parse("message him on telegram saying hi"))
        self.assertIn("isn't clear who 'him' is", question)
        self.assertIsNone(mind.deliberate(parse("send hi to mom on whatsapp")))
        mind.act(Command("whatsapp_read", "mom"), lambda: "Mom said hello.")  # A recent conversation gives 'him/her' meaning.
        self.assertIsNone(mind.deliberate(parse("message him on telegram saying hi")))

    def test_actions_submit_stops_before_queueing(self):
        from jarvis.actions import Actions
        a = Actions.__new__(Actions)
        a.whatsapp_prompts, a.approvals_waiting, a.pending_question, a.pending_open = [], 0, None, None
        a.command_history, a.base = deque(maxlen=5), Path(tempfile.mkdtemp())
        a.current_item, a.pending_tasks, a.session_style, a.memory = None, [], {}, Mock()
        replies = []
        a.report = lambda kind, message="": replies.append((kind, message))
        a.cognition = Cognition(a)
        a.submit(parse("message him on telegram saying hi"))
        self.assertEqual(replies[0][0], "spoken_reply")
        self.assertIn("their name", replies[0][1])
        self.assertEqual(a.cognition.workspace["goal"], "messenger send: him")


class WorkingMemoryTests(unittest.TestCase):
    def test_workspace_attention_and_context(self):
        prompt = SimpleNamespace(question="Which Mom: Mom (home) or Mom (work)?")
        a = actions()
        a.whatsapp_prompts.append(prompt)
        mind = Cognition(a)
        a.cognition = mind
        mind.perceive_command(parse("what is the weather in Toronto"))
        mind.perceive_window("README.md - Visual Studio Code")
        mind.perceive_window("README.md - Visual Studio Code")  # Unchanged focus isn't a new percept.
        mind.perceive("weather_alert", "sensor", "Heavy rain expected", .7)
        mind.tick()
        wm = mind.working_memory()
        self.assertEqual(wm["goal"], "what is the weather in Toronto")
        self.assertEqual(wm["focus"], "README.md - Visual Studio Code")
        self.assertTrue(wm["pending"].startswith("Which Mom"))
        self.assertEqual(len(mind.percepts), 3)
        self.assertTrue(wm["attention"][0].startswith("you:"))  # Your words are most salient.
        from jarvis.context_hub import situation
        found = situation(a, "weather")
        self.assertEqual(found["working_memory"]["goal"], "what is the weather in Toronto")

    def test_recall_spans_memory_kinds(self):
        curator = SimpleNamespace(enabled=True, relevant=lambda q, n: [{"text": "Kunal lives in Toronto"}],
                                  conversations=lambda q: [{"date": "2026-10-10", "title": "Weather talk"}])
        skills = SimpleNamespace(context=lambda q: {"skills": [{"name": "weather", "guidance": "..."}], "procedures": []})
        learner = SimpleNamespace(enabled=True, relevant=lambda q, n: [(1., "owner/weather-app", {})])
        mind = Cognition(actions(curator=curator, skills=skills, repo_learner=learner))
        found = mind.recall("weather in toronto")
        self.assertEqual(found["declarative"], ["Kunal lives in Toronto"])
        self.assertEqual(found["episodic"], ["2026-10-10: Weather talk"])
        self.assertEqual(found["procedural_repositories"], ["owner/weather-app"])
        self.assertEqual(found["procedural_skills"], {"skills": ["weather"], "procedures": 0, "past_cases": 0})

    def test_snapshot_status_and_loop(self):
        a = actions()
        mind = Cognition(a, {"cycle_hz": 20})
        a.cognition = mind
        mind.start()
        try:
            mind.perceive("you", "speech", "hello", .9)
            time.sleep(.4)
        finally:
            mind.close()
        snap = mind.snapshot()
        self.assertEqual(set(snap["modules"]), set(MODULES))
        self.assertGreater(snap["cycles"], 2)
        self.assertTrue(mind.state_path.exists())
        self.assertIn("cognitive loop is running", mind.status_text())
        self.assertEqual(set(NODES), set(MODULES))


class PhrasingTests(unittest.TestCase):
    def test_commands(self):
        for text in ("What are you thinking?", "what's in your working memory", "cognition status", "what's on your mind"):
            self.assertEqual((parse(text).kind, parse(text).value), ("jarvis_status", "cognition"), text)
        self.assertEqual(parse("what have you learned from your mistakes").value, "lessons")
        self.assertEqual(parse("explain your architecture").value, "architecture")
        c = parse("What would happen if you send hi to mom on WhatsApp?")
        self.assertEqual((c.kind, c.value), ("cognition_predict", "send hi to mom on WhatsApp"))
        from jarvis.island_choices import navigation
        self.assertEqual(navigation(parse("show me your mind").value), ("Mind", ""))

    def test_predict_handler_does_nothing(self):
        a = actions()
        a.cognition = Cognition(a)
        reply = intent_execute(a, Command("cognition_predict", "send hi to mom on WhatsApp"))
        self.assertIn("sends a message to another person", reply)
        self.assertIn("haven't done anything", reply)
        self.assertEqual(a.cognition.stats, {})
        self.assertIn("cognitive loop", intent_execute(a, Command("jarvis_status", "cognition")))
        self.assertIn("No lessons yet", intent_execute(a, Command("jarvis_status", "lessons")))


class MindViewTests(unittest.TestCase):
    def test_draws_six_modules_and_selects_on_click(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        try:
            root.geometry("480x420")
            a = actions()
            a.cognition = Cognition(a)
            a.cognition.act(Command("open", "notepad"), lambda: "Opened.")
            from jarvis.island_mind import MindView
            view = MindView(tk.Frame(root), SimpleNamespace(actions=a))
            view.canvas.master.pack(fill="both", expand=True)
            root.update()
            view.refresh()
            self.assertEqual(set(view.boxes), set(MODULES))
            x1, y1, x2, y2 = view.boxes["executive"]
            view.click(SimpleNamespace(x=(x1 + x2) / 2, y=(y1 + y2) / 2))
            self.assertEqual(view.selected, "executive")
            self.assertIn("Last outcome: open worked", view.detail.cget("text"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
