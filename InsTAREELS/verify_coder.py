"""Exercise Jarvis's local coding model on a synthetic file without writing it."""
import json
from pathlib import Path
import sys
import tempfile

from jarvis.brain import BrainClient
from jarvis.coder import Coder, check_content, create_python_from_goal, generate_checked


BASE = Path(__file__).resolve().parent


def main():
    options = json.loads((BASE / "config.json").read_text(encoding="utf-8"))["brain"]
    client = BrainClient(BASE, options)
    try:
        if "--workflow-smoke" in sys.argv:
            with tempfile.TemporaryDirectory(dir=BASE) as temporary:
                selected = Path(temporary) / "TestCodes"
                selected.mkdir()
                class Actions:
                    def report(self, kind, message):
                        print(kind.upper() + ": " + message, flush=True)
                result = Coder(Actions(), client).run(selected,
                    "Create a tools folder with a Python helper script that adds two numbers in TestCodes folder",
                    lambda: False, selected=True)
                scripts = list((selected / "tools").glob("*.py"))
                if len(scripts) != 1:
                    raise ValueError("Planner did not create one Python script in tools.")
                check_content(scripts[0], scripts[0].read_text(encoding="utf-8"))
                print(result, flush=True)
                edited = Coder(Actions(), client).run(selected,
                    f"Modify {scripts[0].name} to add a subtract function for two numbers",
                    lambda: False, selected=True)
                updated = scripts[0].read_text(encoding="utf-8")
                check_content(scripts[0], updated)
                if "subtract" not in updated:
                    raise ValueError("The coding model did not add the requested subtract function.")
                print(edited, flush=True)
                print("Live folder and script workflow passed.", flush=True)
            return
        if "--write-smoke" in sys.argv:
            with tempfile.TemporaryDirectory(dir=BASE) as temporary:
                selected = Path(temporary) / "TestCodes"
                selected.mkdir()
                class Actions:
                    last_created = None
                    def _task_folder(self, name, cancelled):
                        return str(selected)
                    def report(self, kind, message):
                        print(kind.upper() + ": " + message, flush=True)
                result = create_python_from_goal(Actions(), client,
                    "create python code for calculator in test codes project folder",
                    "calculator.py", lambda: False)
                created = selected / "calculator.py"
                check_content(created, created.read_text(encoding="utf-8"))
                print(result, flush=True)
                print("Live write smoke test passed.", flush=True)
            return
        goal = "Add a greet(name) function that returns Hello followed by the name."
        if "--calculator-only" not in sys.argv:
            plan = client.request("code_plan", lambda: False, goal=goal,
                project="SyntheticDemo", files=["greetings.py"])
            print("Plan:", plan, flush=True)
            if not isinstance(plan.get("files"), list) or len(plan["files"]) != 1 or plan["files"][0].get("path") != "greetings.py":
                raise ValueError("Coding plan did not choose the supplied file.")
            result = client.request("code_edit", lambda: False, goal=goal, project="SyntheticDemo",
                path="greetings.py", reason=plan["files"][0]["reason"],
                current="def existing():\n    return 1\n", plan=plan["files"],
                files=["greetings.py"], references={})
            content = result.get("content", "")
            check_content(Path("greetings.py"), content)
            if "def greet(" not in content or "def existing(" not in content:
                raise ValueError("Coding model omitted the requested function or existing code.")
        calculator_goal = "Create Python file with Calculator code in it."
        calculator_step = {"path": "calculator.py", "reason": "Implement a working Python calculator"}
        if "--inspect" in sys.argv:
            raw = client.request("code_edit", lambda: False, goal=calculator_goal,
                project="TestCodes", path="calculator.py", reason=calculator_step["reason"],
                current="", plan=[calculator_step], files=[], references={}, previous="", validation_error="")
            print("Raw first lines:", repr(raw.get("content", "")[:1000]), flush=True)
            return
        calculator_content = generate_checked(client, lambda: False, Path("calculator.py"), goal=calculator_goal,
            project="TestCodes", path="calculator.py", reason=calculator_step["reason"],
            current="", plan=[calculator_step], files=[], references={})
        if not any(word in calculator_content.lower() for word in ("add", "multiply", "calculate")):
            raise ValueError("Coding model did not produce recognizable calculator logic.")
        print("Local coding model generated valid Python for the calculator request. No files were changed.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
