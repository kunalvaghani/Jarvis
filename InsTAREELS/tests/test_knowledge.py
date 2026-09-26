import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from jarvis.commands import Command, parse
from jarvis.engine import Engine
from jarvis.knowledge_worker import answer
from jarvis.knowledge import Knowledge
from jarvis.actions import Actions
from jarvis.ui_controls import UIControls
from jarvis.ui_memory import UIMemory
from test_ui_controls import FakeRunner, control


class KnowledgeTests(unittest.TestCase):
    def test_answer_style_is_conversational_but_keeps_structured_protocol(self):
        chat = unittest.mock.Mock(return_value=json.dumps({"answer": "Four.", "needs_web": False}))
        self.assertEqual(answer({"question": "What is two plus two?"}, chat_fn=chat)["answer"], "Four.")
        prompt = chat.call_args.args[2][0]["content"]
        self.assertIn("short, natural sentences", prompt)
        self.assertIn("not the required JSON envelope", prompt)

    def test_english_mode_has_no_conflicting_hindi_output_instruction(self):
        chat = unittest.mock.Mock(return_value=json.dumps({"answer": "Four.", "needs_web": False}))
        answer({"question": "What is two plus two?", "options": {"answer_language": "en"}}, chat_fn=chat)
        instructions = chat.call_args.args[2][0]["content"]
        self.assertIn("Respond only in English", instructions)
        self.assertNotIn("Respond in Hindi", instructions)
        self.assertNotIn("Devanagari", instructions)

    def test_question_submission_bypasses_desktop_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            actions = Actions({"files_root": "files", "apps": {}}, directory, lambda *args: None)
            actions.knowledge.submit = unittest.mock.Mock()
            actions.submit(Command("ask", "why", "web"))
            self.assertTrue(actions.queue.empty())
            actions.knowledge.submit.assert_called_once_with("why", True)
            actions.close()

    def test_cancel_kills_worker_without_publishing_answer(self):
        started = threading.Event()
        killed = threading.Event()
        class Process:
            returncode = None
            stdin = unittest.mock.Mock()
            def __init__(self):
                self.stdout = self
            def __iter__(self):
                started.set()
                while self.returncode is None:
                    time.sleep(.02)
                return iter(())
            def close(self):
                pass
            def wait(self, **kwargs):
                return self.returncode
            def poll(self):
                return self.returncode
            def kill(self):
                self.returncode = -1
                killed.set()
        events = []
        worker = Knowledge({}, lambda *event: events.append(event))
        with patch("jarvis.question_client.subprocess.Popen", return_value=Process()):
            worker.start()
            try:
                worker.submit("test")
                self.assertTrue(started.wait(2))
                worker.cancel()
                self.assertTrue(killed.wait(2))
                self.assertFalse(any(kind == "answer" for kind, _ in events))
            finally:
                worker.close()
                worker.thread.join(2)

    def test_question_routing_and_final_only(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.activate()
        engine.feed("why is the sky blue then red at sunset")
        self.assertEqual(sent, [])
        engine.feed("why is the sky blue then red at sunset", final=True)
        self.assertEqual(sent, [Command("ask", "why is the sky blue then red at sunset")])
        self.assertEqual(parse("search the internet for python"), Command("ask", "python", "web"))

    def test_question_while_dictating_is_only_text(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.activate()
        engine.feed("write what is the weather", final=True)
        self.assertEqual([c.kind for c in sent], ["begin_dictation", "type"])

    def test_known_answer_stays_local(self):
        search = unittest.mock.Mock(side_effect=AssertionError("Unexpected network"))
        result = answer({"question": "explain gravity"}, chat_fn=lambda *a, **kw: json.dumps({"answer": "Attraction.", "needs_web": False}), search_fn=search)
        self.assertEqual(result["answer"], "Attraction.")
        search.assert_not_called()

    def test_uncertain_answer_searches_and_attaches_actual_sources(self):
        calls = []
        def chat(*args, **kwargs):
            calls.append(args[2])
            return json.dumps({"answer": "Unsure", "needs_web": True}) if kwargs.get("structured") else "Found it [1]."
        result = answer({"question": "what is a rare thing"}, chat_fn=chat,
            search_fn=lambda q: [{"title": "Example", "url": "https://example.com", "snippet": "Evidence"}])
        self.assertIn("https://example.com", result["answer"])
        self.assertIn("untrusted data", calls[1][0]["content"])

    def test_current_queries_go_straight_to_web(self):
        chat = unittest.mock.Mock(return_value="Verified answer [1]")
        search = unittest.mock.Mock(return_value=[{"title": "Source", "url": "https://example.com", "snippet": "Today"}])
        answer({"question": "weather today"}, chat_fn=chat, search_fn=search)
        search.assert_called_once_with("weather today")
        self.assertEqual(chat.call_count, 1)

    def test_network_failure_does_not_present_draft_as_verified(self):
        result = answer({"question": "latest news"}, search_fn=unittest.mock.Mock(side_effect=OSError("offline")))
        self.assertIn("could not verify", result["answer"])

    def test_internet_off_does_not_search(self):
        search = unittest.mock.Mock()
        result = answer({"question": "news today", "options": {"internet": False}}, search_fn=search)
        search.assert_not_called()
        self.assertIn("disabled", result["answer"])


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "memory.json"
        self.memory = UIMemory(self.path)
        self.controls = [control("Comedy", 1), control("Music", 2)]
        self.runner = FakeRunner(self.controls)
        def runner(request, cancelled):
            result = self.runner(request, cancelled)
            if request["operation"] == "list":
                result.update(context="chrome/page", title="Page")
            return result
        self.ui = UIControls(type("Desktop", (), {"target": None})(), runner, self.memory)
        self.ui._handle = lambda: 123

    def learn(self):
        self.ui.execute(parse("select comedy"))
        self.runner.requests.clear()

    def test_persistence_and_context_isolation(self):
        self.learn()
        memory = UIMemory(self.path)
        self.assertEqual(memory.candidate("chrome/page", self.controls)[0]["name"], "Comedy")
        self.assertIsNone(memory.candidate("other/page", self.controls))

    def test_offer_waits_and_yes_only_runs_once(self):
        self.learn()
        self.assertIn("Say yes or no", self.ui.suggest(force=True))
        self.assertTrue(all(r["operation"] == "list" for r in self.runner.requests))
        self.ui.execute(parse("yes"))
        with self.assertRaises(ValueError):
            self.ui.execute(parse("yes"))
        self.assertEqual(sum(r["operation"] == "activate" for r in self.runner.requests), 1)

    def test_no_lists_alternatives_and_learns_new_choice(self):
        self.learn()
        self.ui.suggest(force=True)
        self.assertIn("Which one", self.ui.execute(parse("no")))
        self.assertTrue(all(r["operation"] == "list" for r in self.runner.requests))
        self.ui.execute(parse("select option two"))
        self.assertEqual(self.runner.requests[-1]["control"]["name"], "Music")
        self.assertEqual(len(self.memory.read()["contexts"]["chrome/page"]), 2)

    def test_stale_or_cancelled_offer_never_activates(self):
        self.learn()
        self.ui.suggest(force=True)
        self.runner.signature = "new"
        with self.assertRaises(ValueError):
            self.ui.execute(parse("yes"))
        self.ui.suggest(force=True)
        self.ui.clear_pending()
        with self.assertRaises(ValueError):
            self.ui.execute(parse("yes"))
        self.assertTrue(all(r["operation"] == "list" for r in self.runner.requests))

    def test_failed_activation_is_not_learned(self):
        self.ui.runner = unittest.mock.Mock(side_effect=[{"controls": self.controls, "signature": "x", "context": "chrome/page"}, ValueError("failed")])
        with self.assertRaises(ValueError):
            self.ui.execute(parse("select comedy"))
        self.assertFalse(self.path.exists())

    def test_ambiguous_remembered_label_is_not_suggested(self):
        self.learn()
        self.runner.controls.append(control("Comedy", 3))
        self.assertIsNone(self.ui.suggest(force=True))

    def test_expired_offer_is_not_activated(self):
        self.learn()
        self.ui.suggest(force=True)
        self.ui.offer["time"] -= 60
        with self.assertRaises(ValueError):
            self.ui.execute(parse("yes"))
        self.assertTrue(all(r["operation"] == "list" for r in self.runner.requests))

    def test_confirmation_requires_final_speech(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.activate()
        engine.feed("yes then open notepad")
        self.assertEqual(sent, [])
        engine.feed("no then open notepad", final=True)
        self.assertEqual(sent[0], Command("confirm_suggestion", "no"))


if __name__ == "__main__":
    unittest.main()
