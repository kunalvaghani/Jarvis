from pathlib import Path
import json
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from jarvis.memory_index import discover_projects, context, project_matches, write_index, load_index
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.brain import BrainClient
from jarvis.quick_answers import QuickAnswers
from jarvis.knowledge_worker import answer


class MemoryIndexTests(unittest.TestCase):
    def test_scanner_excludes_dependencies_and_source_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "Atlas"
            project.mkdir()
            (project / "pyproject.toml").write_text("[project]")
            (project / "README.md").write_text("# Atlas\npassword = hidden\nA desktop planner for managing local study sessions.\n")
            for sub in ("src", "node_modules"):
                child = project / sub
                child.mkdir()
                (child / "one.py").touch()
                (child / "two.py").touch()
            (project / "node_modules" / "package.json").touch()
            config = {"project_roots": [tmp], "memory": {"include_user_project_folders": False}}
            rows, scan = discover_projects(config)
            self.assertEqual([row["name"] for row in rows], ["Atlas"])
            self.assertIn("study sessions", rows[0]["summary"])
            self.assertNotIn("hidden", json.dumps(rows))
            self.assertTrue(scan["complete_within_bounds"])
            _, limited = discover_projects(config, max_directories=1)
            self.assertFalse(limited["complete_within_bounds"])

    def test_context_filters_stale_paths_and_bounds_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {"tools": [{"name": "read_file", "context": "read project " * 1000,
                               "required_configuration": ["JARVIS_TEST_MISSING"]}],
                    "projects": [{"name": "Atlas", "path": tmp, "summary": "Study project"},
                                 {"name": "Atlas", "path": tmp + "/missing"}], "apps": []}
            payload = context(data, "read Atlas project")
            self.assertEqual(len(payload["projects"]), 1)
            self.assertLessEqual(len(json.dumps(payload, ensure_ascii=False)), 5000)
            self.assertEqual(project_matches(data, "atlas"), [tmp])

    def test_index_notes_links_reload_and_ambiguous_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            memory = ObsidianMemory(tmp, {"enabled": True, "vault": str(vault)})
            memory.start()
            paths = [Path(tmp) / name / "Atlas" for name in ("first", "second")]
            for path in paths:
                path.mkdir(parents=True)
            data = {"generated_at_utc": "2026-09-30T00:00:00+00:00", "tools": [], "operations": {}, "apps": [],
                    "scan": {"directories_scanned": 2, "complete_within_bounds": True, "roots": [tmp]},
                    "projects": [{"name": "Atlas", "path": str(path), "summary": "Study planner", "summary_source": "README.md"} for path in paths]}
            write_index(vault, data)
            write_index(vault, data)
            self.assertEqual(len(memory.project_matches("Atlas")), 2)
            self.assertEqual(len(memory.task_context("Atlas")["projects"]), 2)
            self.assertEqual((vault / "Jarvis Brain.md").read_text().count("[[Jarvis Tools]]"), 1)
            self.assertEqual(load_index(vault)["projects"], data["projects"])
            (vault / "Jarvis Index.json").write_text('{"projects": 1}')
            self.assertIsNone(load_index(vault))

    def test_closed_memory_does_not_refresh_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = ObsidianMemory(tmp, {"enabled": True})
            memory.start()
            memory.close()
            with patch("jarvis.memory_index.build_index") as build:
                memory.ensure_index({})
                build.assert_not_called()

    def test_quit_cancels_inflight_refresh_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = ObsidianMemory(tmp, {"enabled": True})
            memory.start()
            entered, release = threading.Event(), threading.Event()
            def build(_config, cancelled):
                entered.set()
                release.wait(2)
                self.assertTrue(cancelled())
                return {}
            with patch("jarvis.memory_index.build_index", side_effect=build), patch("jarvis.memory_index.write_index") as write:
                memory.ensure_index({})
                self.assertTrue(entered.wait(2))
                memory.close()
                release.set()
                memory.index_thread.join(2)
                self.assertFalse(memory.index_thread.is_alive())
                write.assert_not_called()

    def test_brain_requests_receive_catalogue(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = BrainClient(tmp, {})
            client.memory = Mock()
            client.memory.task_context.return_value = {"projects": [{"name": "Atlas"}]}
            with patch.object(client, "_request_once", return_value={}) as request:
                client.request("plan", lambda: False, goal="Open Atlas")
                self.assertEqual(request.call_args.kwargs["memory_context"]["projects"][0]["name"], "Atlas")

    def test_direct_project_answer_reads_runtime_vault_and_avoids_unrelated_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = ObsidianMemory(tmp, {"enabled": True, "vault": "vault"})
            memory.start()
            data = {"generated_at_utc": "2026-09-30", "tools": [], "apps": [],
                    "projects": [{"name": "Atlas", "path": tmp, "summary": "Study planner", "summary_source": "README.md"}]}
            (memory.vault / "Jarvis Index.json").write_text(json.dumps(data))
            quick = QuickAnswers(memory)
            answer = quick.answer("What does my Atlas project do and where is its folder?")
            self.assertIn(tmp, answer)
            self.assertIn("Study planner", answer)
            self.assertIsNone(memory.catalogue_answer("How should I improve my Atlas project?"))
            data["projects"][0]["summary"] = "Runtime changed summary"
            (memory.vault / "Jarvis Index.json").write_text(json.dumps(data))
            self.assertIn("Runtime changed", quick.answer("What does my Atlas project do?"))

    def test_local_project_question_uses_catalogue_without_web(self):
        captured = []
        def chat(_client, _options, messages, structured=False):
            captured.extend(messages)
            return '{"answer":"Atlas is a study planner, according to its README excerpt.","needs_web":true}'
        result = answer({"question": "What does my Atlas project do?", "options": {"enabled": True},
                         "catalog_context": {"projects": [{"name": "Atlas", "summary": "Study planner"}]}},
                        client=Mock(), chat_fn=chat, search_fn=lambda _: self.fail("unexpected web search"))
        self.assertIn("study planner", result["answer"])
        self.assertIn("Relevant Obsidian catalogue", captured[-1]["content"])


if __name__ == "__main__":
    unittest.main()
