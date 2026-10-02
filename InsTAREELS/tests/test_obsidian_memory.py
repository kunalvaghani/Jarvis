from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from jarvis.obsidian_memory import ObsidianMemory
from jarvis.knowledge_worker import answer


class ObsidianMemoryTests(unittest.TestCase):
    def test_vault_records_activity_and_retrieves_relevant_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ObsidianMemory(directory, {"enabled": True, "vault": "vault"})
            memory.start()
            memory.record("Jarvis request", "code in project Atlas")
            memory.observe_window("Atlas - Visual Studio Code", 123, now=1000)
            memory.observe_window("Chrome", 456, now=1060)
            rows = memory.recall("What did I do in Atlas?")
            self.assertTrue(any("Atlas" in row["observation"] for row in rows))
            self.assertFalse(any("Atlas" in row["observation"] for row in memory.recall("Atlas yesterday")))
            note = next((Path(directory) / "vault" / "Daily").glob("*.md"))
            self.assertIn("observed about 1.0 min", note.read_text(encoding="utf-8"))
            self.assertIn("[[Jarvis Brain]]", note.read_text(encoding="utf-8"))
            self.assertIn(f"[[Daily/{note.stem}|{note.stem}]]",
                (Path(directory) / "vault" / "Jarvis Brain.md").read_text(encoding="utf-8"))
            memory.close()

    def test_sensitive_text_is_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ObsidianMemory(directory, {"enabled": True, "vault": "vault"})
            memory.start()
            memory.record("Jarvis request", "password is 123")
            note = next((Path(directory) / "vault" / "Daily").glob("*.md"))
            self.assertNotIn("123", note.read_text(encoding="utf-8"))

    def test_memory_question_uses_observations_without_web_search(self):
        calls = []
        def chat(_client, _options, messages, structured=False):
            calls.append(messages)
            return '{"answer":"Atlas was observed on 2026-09-29.","needs_web":false}'
        result = answer({"question": "What did I work on yesterday?", "options": {"enabled": True},
            "memory_context": [{"date_utc": "2026-09-29",
                "observation": "- 12:00 UTC | Foreground window: Atlas"}]},
            client=Mock(), chat_fn=chat, search_fn=lambda _: self.fail("unexpected web search"))
        self.assertIn("Atlas", result["answer"])
        self.assertIn("Relevant Obsidian memory observations", calls[0][-1]["content"])

    def test_personal_questions_retrieve_profile_without_injecting_it_elsewhere(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ObsidianMemory(directory, {"enabled": True, "vault": "vault"})
            memory.start()
            (memory.vault / "Kunal Vaghani.md").write_text(
                "# Kunal Vaghani\n\n- Father: Rajeshbhai Vaghani\n", encoding="utf-8")
            self.assertIn("Rajeshbhai", memory.recall("What is my father's name?")[0]["observation"])
            self.assertEqual(memory.recall("What is a Python function?"), [])
            self.assertEqual(memory.recall("Tell me about Python"), [])
