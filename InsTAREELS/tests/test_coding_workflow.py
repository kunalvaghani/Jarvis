import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jarvis.code_context import apply_replacements, related_context, bounded_references
from jarvis.coder import Coder, generate_checked, project_files, workspace_coding_request
from jarvis.task_state import TaskState


class CodingWorkflowTests(unittest.TestCase):
    def test_application_source_precedes_large_reference_trees(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'integrations').mkdir()
            (root / 'jarvis').mkdir()
            for index in range(200):
                (root / 'integrations' / f'upstream{index}.py').write_text('x = 1')
            (root / 'jarvis/runtime.py').write_text('def run(): pass')
            self.assertIn('jarvis/runtime.py', project_files(root, limit=20))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        self.actions, self.client = Mock(), Mock()
        self.coder = Coder(self.actions, self.client)

    def test_targeted_edit_keeps_unrelated_bytes_and_line_endings(self):
        file = self.project / "app.py"
        original = b"def value():\r\n    return 1\r\n\r\ndef unrelated():\r\n    return 'keep'\r\n"
        file.write_bytes(original)
        self.client.request.return_value = {"content": "", "replacements": [{"find": "return 1", "replace": "return 2"}]}
        self.coder.run(self.project, "Modify app.py to return 2", lambda: False)
        self.assertEqual(file.read_bytes(), original.replace(b"return 1", b"return 2"))
        self.assertEqual(self.client.request.call_count, 1)

    def test_ambiguous_patch_is_corrected_in_memory_before_writing(self):
        file = self.project / "app.py"
        original = "a = 1\nb = 1\n"
        file.write_text(original, encoding="utf-8")
        def infer(operation, cancelled, **data):
            self.assertEqual(file.read_text(encoding="utf-8"), original)
            if not data["validation_error"]:
                return {"content": "", "replacements": [{"find": "1", "replace": "2"}]}
            self.assertIn("matched 2 locations", data["validation_error"])
            return {"content": "", "replacements": [{"find": "a = 1", "replace": "a = 2"}]}
        self.client.request.side_effect = infer
        self.coder.run(self.project, "Modify app.py to set a to 2", lambda: False)
        self.assertEqual(file.read_text(encoding="utf-8"), "a = 2\nb = 1\n")
        self.assertEqual(self.client.request.call_count, 2)

    def test_targeted_edit_protocol_rejects_missing_and_empty_matches(self):
        for edits in ([{"find": "missing", "replace": "new"}], [{"find": "", "replace": "new"}],
                      [{"find": "x", "replace": "new", "path": "other.py"}], "not a list"):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                apply_replacements("x = 1\n", edits)

    def test_existing_public_function_loss_is_retried_then_original_is_kept(self):
        file = self.project / "app.py"
        original = "def keep():\n    return 1\n"
        file.write_text(original, encoding="utf-8")
        self.client.request.return_value = {"content": "def added():\n    return 2\n"}
        with self.assertRaisesRegex(ValueError, "removed existing functions"):
            self.coder.run(self.project, "Modify app.py to add a function", lambda: False)
        self.assertEqual(file.read_text(encoding="utf-8"), original)
        self.assertEqual(self.client.request.call_count, 3)

    def test_explicit_subfolder_disambiguates_duplicate_basename(self):
        for sub in ("one", "two"):
            (self.project / sub).mkdir()
            (self.project / sub / "app.py").write_text("value = 1\n", encoding="utf-8")
        self.client.request.return_value = {"content": "value = 2\n"}
        self.coder.run(self.project, "Modify one/app.py to set value to 2", lambda: False)
        self.assertEqual((self.project / "two/app.py").read_text(encoding="utf-8"), "value = 1\n")
        self.assertEqual(self.client.request.call_args.kwargs["path"], "one/app.py")

    def test_read_only_context_prioritizes_imports_and_excludes_secrets(self):
        (self.project / "app.py").write_text("from helpers import greet\n", encoding="utf-8")
        (self.project / "helpers.py").write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
        (self.project / "credentials.json").write_text('{"secret":"private"}', encoding="utf-8")
        (self.project / ".hidden.json").write_text('{"secret":"hidden"}', encoding="utf-8")
        for index in range(6):
            (self.project / f"a{index}.py").write_text("value = 1\n", encoding="utf-8")
        files = project_files(self.project)
        self.assertNotIn(".hidden.json", files)
        before = {name: (self.project / name).read_bytes() for name in files}
        context = related_context(self.project, files, "Modify app.py", ["app.py"])
        self.assertEqual(next(iter(context)), "helpers.py")
        self.assertNotIn("credentials.json", context)
        self.assertLessEqual(sum(map(len, context.values())), 6000)
        self.assertEqual(before, {name: (self.project / name).read_bytes() for name in files})

    def test_multi_file_generation_receives_fresh_sibling_code(self):
        def infer(operation, cancelled, **data):
            if operation == "code_plan":
                return {"files": [{"path": "helpers.py", "reason": "new greet"}, {"path": "app.py", "reason": "use greet"}]}
            if data["path"] == "helpers.py":
                return {"content": "def greet(name):\n    return 'Hi ' + name\n"}
            self.assertIn("def greet(name)", data["references"]["helpers.py"])
            return {"content": "from helpers import greet\nresult = greet('Ada')\n"}
        self.client.request.side_effect = infer
        self.coder.run(self.project, "Create a greeting program", lambda: False)
        self.assertIn("greet('Ada')", (self.project / "app.py").read_text(encoding="utf-8"))

    def test_interrupted_atomic_write_keeps_backup_and_blocks_action_replay(self):
        file = self.project / "app.py"
        file.write_text("value = 1\n", encoding="utf-8")
        original = file.read_bytes()
        state = self.actions.task_state = TaskState(self.base)
        state.start("Modify app.py", "code_task", self.project)
        self.client.request.return_value = {"content": "value = 2\n"}
        replace = os.replace
        commits = []
        def fault(source, destination):
            replace(source, destination)
            if Path(destination) == file:
                commits.append(str(destination))
                raise OSError("injected uncertain result after replacement")
        with patch("jarvis.coder.os.replace", side_effect=fault):
            with self.assertRaisesRegex(OSError, "uncertain result"):
                self.coder.run(self.project, "Modify app.py", lambda: False)
        self.assertEqual(commits, [str(file)])
        self.assertEqual(self.client.request.call_count, 1)
        self.assertIn("value = 2", file.read_text(encoding="utf-8"))
        backup = list((self.base / ".jarvis-runtime/coding").glob("*/originals/app.py"))
        self.assertEqual(len(backup), 1)
        self.assertEqual(backup[0].read_bytes(), original)
        restarted = TaskState(self.base)
        self.assertIn("not verified", restarted.resume_blocker(restarted.snapshot()))

    def test_bounded_context_prefers_generated_sources_and_extended_languages_route(self):
        refs = bounded_references({"old.py": "x"*8000}, "app.py", [("new.py", "y"*4000)])
        self.assertEqual(next(iter(refs)), "new.py")
        self.assertLessEqual(sum(map(len, refs.values())), 6000)
        for filename in ("main.go", "Main.java", "hello.c", "query.sql", "script.ps1"):
            self.assertTrue(workspace_coding_request("Create " + filename))
        self.assertFalse(workspace_coding_request("Open Documents and modify file notes.txt: replace old with new"))
