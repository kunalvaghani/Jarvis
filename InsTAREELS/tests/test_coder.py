import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from jarvis.coder import Coder, create_python_from_goal, python_file_request, named_folder_request
from jarvis.commands import Command, parse
from jarvis.engine import Engine
from jarvis.brain import Brain


class CoderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        (self.project / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
        self.actions = Mock()
        self.client = Mock()
        self.coder = Coder(self.actions, self.client)

    def test_voice_coding_command_names_project_and_goal(self):
        self.assertEqual(parse("code in project Demo: add a greeting"),
                         Command("code_task", "add a greeting", "Demo"))
        self.assertEqual(parse("fix the greeting in project Demo"),
                         Command("code_task", "the greeting", "Demo"))
        self.assertEqual(parse("add a greeting to project Demo"),
                         Command("code_task", "a greeting", "Demo"))
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.activate()
        engine.feed("code in project Demo: add a greeting and update the tests", final=True)
        self.assertEqual(sent, [Command("code_task", "add a greeting and update the tests", "Demo")])

    def test_folder_only_request_creates_folder_without_model(self):
        result = self.coder.run(self.project, "Create a folder named Tools", lambda: False)
        self.assertTrue((self.project / "Tools").is_dir())
        self.assertIn("Tools", result)
        self.client.request.assert_not_called()

    def test_selected_explorer_folder_can_create_folder_and_script(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.activate()
        engine.feed("Create a tools folder and a Python script in TestCodes folder", final=True)
        self.assertEqual(sent, [Command("task", "Create a tools folder and a Python script in TestCodes folder")])
        selected = self.project / "TestCodes"
        selected.mkdir()
        self.actions._task_folder.return_value = str(selected)
        brain = Brain(self.actions, self.project, {"enabled": True})
        brain.client = self.client
        def answer(operation, *_args, **_kwargs):
            if operation == "code_plan":
                return {"directories": ["tools"], "files": [{"path": "tools/main.py", "reason": "Program entry point"}]}
            file = selected / "tools" / "main.py"
            self.assertTrue(file.is_file())
            self.assertIn("Jarvis draft", file.read_text(encoding="utf-8"))
            return {"content": "def main():\n    return 42\n", "explanation": ""}
        self.client.request.side_effect = answer
        result = brain.run("Create a tools folder with a Python script in TestCodes folder", lambda: False)
        self.assertIn("tools/main.py", result)
        self.assertIn("return 42", (selected / "tools" / "main.py").read_text(encoding="utf-8"))

    def test_existing_project_script_can_be_modified(self):
        file = self.project / "app.py"
        file.write_text("def value():\n    return 1\n", encoding="utf-8")
        self.client.request.side_effect = [
            {"directories": [], "files": [{"path": "app.py", "reason": "Update value"}]},
            {"content": "def value():\n    return 2\n", "explanation": ""}]
        self.coder.run(self.project, "Update the app script to return 2", lambda: False)
        self.assertIn("return 2", file.read_text(encoding="utf-8"))

    def test_spoken_calculator_edit_reads_existing_file(self):
        selected = self.project / "TestCodes"
        selected.mkdir()
        existing = selected / "calculator.py"
        original = "def calculate(a, b):\n    return a + b\n"
        existing.write_text(original, encoding="utf-8")
        self.actions._task_folder.return_value = str(selected)
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.feed("Hey Jarvis, ModifyCalculator .py to add UI to it.", final=True)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].kind, "task")
        self.assertEqual(parse("ModifyCalculator .py to add UI to it.").value,
                         "Modify Calculator.py to add UI to it.")
        brain = Brain(self.actions, self.project, {"enabled": True})
        brain.client = self.client

        def answer(operation, *_args, **kwargs):
            self.assertEqual(operation, "code_edit")
            self.assertEqual(kwargs["path"], "calculator.py")
            self.assertEqual(kwargs["current"].replace("\r\n", "\n"), original)
            return {"content": original + "\ndef launch_ui():\n    pass\n", "explanation": ""}

        self.client.request.side_effect = answer
        result = brain.run(sent[0].value, lambda: False)
        self.assertIn("calculator.py", result)
        self.assertIn("def launch_ui", existing.read_text(encoding="utf-8"))
        self.assertEqual(self.client.request.call_count, 1)

    def test_original_calculator_gets_working_ui_without_model(self):
        import subprocess
        import sys
        from jarvis.coder import calculator_template

        selected = self.project / "TestCodes"
        selected.mkdir()
        file = selected / "calculator.py"
        file.write_text(calculator_template("calculator", "calculator.py"), encoding="utf-8")
        self.actions._task_folder.return_value = str(selected)
        brain = Brain(self.actions, self.project, {"enabled": True})
        brain.client = self.client
        result = brain.run("ModifyCalculator .py to add UI to it", lambda: False)
        content = file.read_text(encoding="utf-8")
        self.assertIn("calculator.py", result)
        self.assertIn("def launch_ui()", content)
        self.assertIn("ttk.Button", content)
        self.assertIn("def calculate(", content)
        self.client.request.assert_not_called()
        done = subprocess.run([sys.executable, str(file), "multiply", "6", "7"],
                              capture_output=True, text=True, check=False)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "42"))

    def test_current_explorer_folder_supplies_file_context_without_spoken_location(self):
        selected = self.project / "TestCodes"
        selected.mkdir()
        file = selected / "kunal.py"
        original = "def tasks():\n    return []\n"
        file.write_text(original, encoding="utf-8")
        self.actions._task_folder.return_value = str(selected)
        brain = Brain(self.actions, self.project, {"enabled": True})
        brain.client = self.client

        def answer(operation, *_args, **kwargs):
            self.assertEqual(operation, "code_edit")
            self.assertEqual(kwargs["path"], "kunal.py")
            self.assertEqual(kwargs["current"].replace("\r\n", "\n"), original)
            return {"content": original + "\ndef launch_ui():\n    pass\n", "explanation": ""}

        self.client.request.side_effect = answer
        brain.run("Modify Kunal .py to add UI to it", lambda: False)
        self.assertIn("def launch_ui", file.read_text(encoding="utf-8"))
        self.assertTrue(any("TestCodes" in call.args[1] and "kunal.py" in call.args[1]
                            for call in self.actions.report.call_args_list if call.args[0] == "screen"))

    def test_edit_missing_file_reports_open_folder_contents(self):
        selected = self.project / "TestCodes"
        selected.mkdir()
        (selected / "kunal.py").write_text("x = 1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not in the open folder.*kunal.py"):
            self.coder.run(selected, "Modify calculator.py to add UI", selected=True)
        self.client.request.assert_not_called()
        self.assertFalse((selected / "calculator.py").exists())

    def test_ambiguous_existing_filename_requires_subfolder(self):
        selected = self.project / "TestCodes"
        (selected / "one").mkdir(parents=True)
        (selected / "two").mkdir()
        for subfolder in ("one", "two"):
            (selected / subfolder / "kunal.py").write_text("x = 1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "multiple subfolders"):
            self.coder.run(selected, "Modify kunal.py to add UI", selected=True)
        self.client.request.assert_not_called()

    def test_unsafe_planned_folder_is_rejected(self):
        self.client.request.return_value = {"directories": ["../outside"], "files": []}
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.coder.run(self.project, "create a folder and script", lambda: False)
        self.assertFalse((self.project.parent / "outside").exists())

    def test_infers_filename_from_spoken_program_purpose(self):
        self.assertEqual(python_file_request("Create Python file with Calculator code in it."), "calculator.py")
        self.assertEqual(python_file_request("Make a Python file with code for a calculator."), "calculator.py")
        self.assertEqual(python_file_request("Create Python file called calc.py with calculator code."), "calc.py")
        self.assertIsNone(python_file_request("Create file notes.txt with exact words."))
        self.assertEqual(python_file_request("create python code for calculator in test codes project folder"), "calculator.py")
        self.assertEqual(named_folder_request("create python code for calculator in test codes project folder"), "test codes")
        self.assertEqual(python_file_request("Create the Python code for Calculator in TestCodes folder."), "calculator.py")
        self.assertEqual(named_folder_request("Create the Python code for Calculator in TestCodes folder."), "TestCodes")

    def test_creates_generated_python_in_selected_explorer_folder(self):
        self.actions._task_folder.return_value = str(self.project)
        self.client.request.return_value = {"content": "def add(a, b):\n    return a + b\n", "explanation": ""}
        result = create_python_from_goal(self.actions, self.client,
            "Create Python file with fibonacci code in it.", "fibonacci.py", lambda: False)
        self.assertIn("fibonacci.py", result)
        self.assertIn("def add", (self.project / "fibonacci.py").read_text(encoding="utf-8"))
        self.actions._task_folder.assert_called_once()
        with self.assertRaisesRegex(ValueError, "already exists"):
            create_python_from_goal(self.actions, self.client, "Create Python file with fibonacci code in it.",
                "fibonacci.py", lambda: False)

    def test_generic_voice_request_routes_to_code_generation(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.activate()
        engine.feed("Create Python file with Calculator code in it", final=True)
        self.assertEqual(sent, [Command("task", "Create Python file with Calculator code in it")])
        self.actions._task_folder.return_value = str(self.project)
        brain = Brain(self.actions, self.project, {"enabled": True})
        brain.client = self.client
        result = brain.run(sent[0].value, lambda: False)
        self.assertIn("calculator.py", result)
        self.assertEqual(self.client.request.call_count, 0)
        self.assertIn("def calculate", (self.project / "calculator.py").read_text(encoding="utf-8"))

    def test_reported_voice_phrase_creates_in_matching_selected_folder(self):
        sent = []
        engine = Engine(sent.append, lambda *args: None)
        engine.feed("Hey Jarvis, create python code for calculator in test codes project folder", final=True)
        self.assertEqual(sent, [Command("task", "create python code for calculator in test codes project folder")])
        selected = self.project / "TestCodes"
        selected.mkdir()
        self.actions._task_folder.return_value = str(selected)
        brain = Brain(self.actions, self.project, {"enabled": True})
        brain.client = self.client
        goal = sent[0].value
        result = brain.run(goal, lambda: False)
        self.assertIn("calculator.py", result)
        self.assertTrue((selected / "calculator.py").is_file())

    def test_named_folder_must_match_selected_explorer_folder(self):
        self.actions._task_folder.return_value = str(self.project)
        with self.assertRaisesRegex(ValueError, "selected File Explorer folder"):
            create_python_from_goal(self.actions, self.client,
                "create python code for calculator in test codes project folder", "calculator.py", lambda: False)
        self.client.request.assert_not_called()

    def test_plans_and_writes_python_change(self):
        file = self.project / "hello.py"
        file.write_text("def hello():\n    return 'old'\n", encoding="utf-8")
        self.client.request.side_effect = [
            {"files": [{"path": "hello.py", "reason": "Update greeting"}]},
            {"content": "def hello():\n    return 'new'\n", "explanation": "Updated greeting"}]
        result = self.coder.run(self.project, "update greeting", lambda: False)
        self.assertIn("hello.py", result)
        self.assertIn("return 'new'", file.read_text(encoding="utf-8"))
        self.assertEqual([call.args[0] for call in self.client.request.call_args_list],
                         ["code_plan", "code_edit"])

    def test_creates_new_source_file_without_overwrite(self):
        self.client.request.side_effect = [
            {"files": [{"path": "new.py", "reason": "New function"}]},
            {"content": "def greet():\n    return 'hi'\n", "explanation": ""}]
        self.coder.run(self.project, "add greet", lambda: False)
        self.assertIn("def greet", (self.project / "new.py").read_text(encoding="utf-8"))

    def test_invalid_generated_python_keeps_original(self):
        file = self.project / "hello.py"
        file.write_text("x = 1\n", encoding="utf-8")
        self.client.request.side_effect = [
            {"files": [{"path": "hello.py", "reason": "Change x"}]},
            *[{"content": "def broken(:", "explanation": ""}] * 3]
        with self.assertRaisesRegex(ValueError, "syntax"):
            self.coder.run(self.project, "change x", lambda: False)
        self.assertEqual(file.read_text(encoding="utf-8"), "x = 1\n")

    def test_all_files_are_validated_before_any_write(self):
        first = self.project / "first.py"
        second = self.project / "second.py"
        first.write_text("x = 1\n", encoding="utf-8")
        second.write_text("y = 1\n", encoding="utf-8")
        self.client.request.side_effect = [
            {"files": [{"path": "first.py", "reason": "Change x"},
                       {"path": "second.py", "reason": "Change y"}]},
            {"content": "x = 2\n", "explanation": ""},
            *[{"content": "invalid python !!!", "explanation": ""}] * 3]
        with self.assertRaisesRegex(ValueError, "syntax"):
            self.coder.run(self.project, "change both", lambda: False)
        self.assertEqual(first.read_text(encoding="utf-8"), "x = 1\n")

    def test_truncated_existing_file_is_rejected(self):
        file = self.project / "large.py"
        original = "value = 1\n" * 120
        file.write_text(original, encoding="utf-8")
        self.client.request.side_effect = [
            {"files": [{"path": "large.py", "reason": "Adjust value"}]},
            {"content": "value = 2\n", "explanation": ""}]
        with self.assertRaisesRegex(ValueError, "removed too much"):
            self.coder.run(self.project, "adjust the value", lambda: False)
        self.assertEqual(file.read_text(encoding="utf-8"), original)

    def test_syntax_error_is_repaired_before_creating_file(self):
        self.actions._task_folder.return_value = str(self.project)
        self.client.request.side_effect = [
            {"content": "A calculator program.\ndef add(a, b):\n    return a + b\n", "explanation": ""},
            {"content": "# A calculator program.\ndef add(a, b):\n    return a + b\n", "explanation": ""}]
        create_python_from_goal(self.actions, self.client, "Create Python file with fibonacci code in it.",
            "fibonacci.py", lambda: False)
        self.assertEqual(self.client.request.call_count, 2)
        self.assertIn("validation_error", self.client.request.call_args.kwargs)
        self.assertTrue((self.project / "fibonacci.py").is_file())

    def test_markdown_preamble_is_commented_before_writing_python(self):
        self.actions._task_folder.return_value = str(self.project)
        self.client.request.return_value = {"content":
            "# Calculator\n\nA simple command-line calculator.\n\n## Usage\n```bash\npython calculator.py add 1 2\n```\n\ndef add(a, b):\n    return a + b\n",
            "explanation": ""}
        create_python_from_goal(self.actions, self.client, "Create Python file with fibonacci code in it.",
            "fibonacci.py", lambda: False)
        content = (self.project / "fibonacci.py").read_text(encoding="utf-8")
        self.assertIn("# A simple command-line calculator.", content)
        self.assertIn("def add(a, b):", content)
        self.assertEqual(self.client.request.call_count, 1)

    def test_file_exists_before_generation_and_draft_can_resume(self):
        self.actions._task_folder.return_value = str(self.project)
        file = self.project / "fibonacci.py"
        def fail_generation(*_args, **_kwargs):
            self.assertTrue(file.is_file())
            self.assertIn("Jarvis draft", file.read_text(encoding="utf-8"))
            raise ValueError("Model unavailable")
        self.client.request.side_effect = fail_generation
        with self.assertRaisesRegex(ValueError, "Model unavailable"):
            create_python_from_goal(self.actions, self.client,
                "Create Python file with fibonacci code in it.", "fibonacci.py", lambda: False)
        self.assertIn("Jarvis draft", file.read_text(encoding="utf-8"))
        self.client.request.side_effect = None
        self.client.request.return_value = {"content": "def fibonacci(n):\n    return n\n", "explanation": ""}
        create_python_from_goal(self.actions, self.client,
            "Create Python file with fibonacci code in it.", "fibonacci.py", lambda: False)
        self.assertIn("def fibonacci", file.read_text(encoding="utf-8"))

    def test_existing_calculator_is_tested_without_overwrite(self):
        from jarvis.coder import calculator_template
        self.actions._task_folder.return_value = str(self.project)
        file = self.project / "calculator.py"
        file.write_text(calculator_template("calculator", "calculator.py"), encoding="utf-8")
        result = create_python_from_goal(self.actions, self.client,
            "Create Python file with Calculator code in it.", "calculator.py", lambda: False)
        self.assertIn("already has working calculator code", result)
        self.client.request.assert_not_called()

    def test_rejects_traversal_and_symlink(self):
        self.client.request.return_value = {"files": [{"path": "../elsewhere.py", "reason": "escape"}]}
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.coder.run(self.project, "write something", lambda: False)
        self.assertEqual(self.client.request.call_count, 1)

    def test_refuses_parent_directory_without_project_marker(self):
        (self.project / "pyproject.toml").unlink()
        with self.assertRaisesRegex(ValueError, "individual project"):
            self.coder.run(self.project, "make a function", lambda: False)
        self.client.request.assert_not_called()

    def test_cancellation_before_write_keeps_files(self):
        file = self.project / "hello.py"
        file.write_text("x = 1\n", encoding="utf-8")
        cancelled = [False]
        def request(operation, *_args, **_kwargs):
            if operation == "code_plan":
                return {"files": [{"path": "hello.py", "reason": "Change x"}]}
            cancelled[0] = True
            return {"content": "x = 2\n", "explanation": ""}
        self.client.request.side_effect = request
        with self.assertRaisesRegex(ValueError, "cancelled"):
            self.coder.run(self.project, "change x", lambda: cancelled[0])
        self.assertEqual(file.read_text(encoding="utf-8"), "x = 1\n")


if __name__ == "__main__":
    unittest.main()
