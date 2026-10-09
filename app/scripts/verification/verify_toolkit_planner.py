"""Check actual local toolkit planning without desktop or account actions."""
import json
from pathlib import Path

from jarvis.brain import validate_plan
from jarvis.brain_worker import Models
from jarvis.tools import ToolRegistry


def main():
    base = Path(__file__).resolve().parents[2]
    options = json.loads((base / "config/config.json").read_text(encoding="utf-8"))["brain"]
    models = Models()
    catalog = ToolRegistry(None).catalog("Prepare a useful comparison")
    print(f"Configured planning catalog: {len(catalog)} operations", flush=True)
    try:
        for goal, required in (
            ("Find useful public sources about Python asyncio and compare the main tradeoffs.", "web_search"),
            ("Read source.txt in Demo and draft tests for its functions. Discover the source before drafting.", "read_file"),
        ):
            result = models.predict({"operation": "plan", "options": options, "goal": goal,
                "screen": {"title": "Desktop", "controls": []}, "apps": [], "completed": [],
                "prior_task": None, "experience": [], "tools": catalog})
            print(json.dumps({"goal": goal, "plan": result}, ensure_ascii=False), flush=True)
            steps = validate_plan(result)
            if required not in {step["action"] for step in steps}:
                raise ValueError("Planner omitted " + required + ": " + json.dumps(result))
        source = "def subtract(a, b):\n    return a - b\n"
        read = {"action": "read_file", "value": "source.txt", "folder": "Demo",
                "expected": "Source read", "result": source, "verified": True}
        result = models.predict({"operation": "replan", "options": options,
            "goal": "Read source.txt in Demo and draft tests for its functions. Return a draft without saving or executing it.",
            "screen": {"title": "Tool result", "controls": [], "tool_results": [read]},
            "apps": [], "completed": [read], "remaining": [], "last_result": read,
            "steps_left": 5, "failures": [], "tools": catalog})
        steps = validate_plan(result, [read])
        if result.get("done") is not False or steps[0]["action"] != "write_tests" or "def subtract" not in steps[0].get("content", ""):
            raise ValueError("Planner did not use the read source to draft tests: " + json.dumps(result))
        print(json.dumps({"replan": result}, ensure_ascii=False), flush=True)
        print("Local toolkit planning checks passed. No desktop, network-tool or account actions executed.", flush=True)
    finally:
        models.client.close()


if __name__ == "__main__":
    main()
