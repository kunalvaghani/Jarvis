"""Live local-model checks on varied synthetic requests; desktop apps are untouched."""
import json
from pathlib import Path
import sys
import tempfile
import time

from jarvis.actions import Actions
from jarvis.brain import BrainClient, normalize_plan, validate_plan
from jarvis.commands import Command, parse
from jarvis.knowledge_worker import answer, session

BASE = Path(__file__).resolve().parents[2]


def has(steps, action, **fields):
    return any(step["action"] == action and all(str(step.get(key, "")).casefold() == value.casefold()
                                                for key, value in fields.items()) for step in steps)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    config = json.loads((BASE / "config/config.json").read_text(encoding="utf-8"))
    candidate = sys.argv[1] if len(sys.argv) > 1 else None
    if candidate:
        config["brain"]["planner"] = candidate
        config["brain"]["decision"] = candidate
        config["knowledge"]["model"] = candidate
    client = BrainClient(BASE, config["brain"])
    results = []
    cases = [
        ("Open YouTube in Chrome", lambda s: has(s, "browse", value="YouTube")),
        ("Open Chrome and search for Python tutorials", lambda s: has(s, "browser_search")),
        ("Open folder Downloads and create a file called ideas.txt there and write hello Kunal in it",
         lambda s: has(s, "create_file", value="ideas.txt", folder="Downloads", content="hello Kunal")),
        ("Create a file called log.txt in this folder and write test run complete",
         lambda s: has(s, "create_file", value="log.txt", folder="this folder", content="test run complete")),
        ("Play jazz on YouTube", lambda s: has(s, "media_search", platform="youtube") and has(s, "select")),
        ("Play lo-fi focus on Spotify", lambda s: has(s, "media_search", platform="spotify") and has(s, "select")),
        ("Close Chrome", lambda s: has(s, "close_app")),
        ("Open folder Downloads", lambda s: has(s, "open", value="Downloads")),
        ("Choose Person 1 profile", lambda s: has(s, "select")),
        ("Open Downloads, create notes.txt there and write first line, then close Notepad",
         lambda s: has(s, "create_file", folder="Downloads", content="first line") and has(s, "close_app")),
    ]
    try:
        for number, (goal, check) in enumerate(cases, 1):
            started = time.monotonic()
            try:
                screen = {"title": "Chrome profile picker" if "Person 1" in goal else "Desktop",
                          "controls": ["Open Kunal profile", "Open Person 1 profile", "More actions for Person 1"] if "Person 1" in goal else []}
                plan = client.request("plan", lambda: False, goal=goal, screen=screen,
                                      apps=["chrome", "notepad", "file explorer"])
                steps = normalize_plan(validate_plan(plan), goal)
                passed = check(steps)
                detail = {**plan, "steps": steps}
            except Exception as exc:
                passed, detail = False, str(exc)
            row = {"case": number, "goal": goal, "passed": passed,
                   "seconds": round(time.monotonic() - started, 1), "detail": detail}
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)

        # The file case exercises Jarvis's actual file-action path in an isolated folder.
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "Downloads"
            folder.mkdir()
            local_config = {"files_root": "JarvisFiles", "apps": {}, "folders": {"downloads": str(folder)}}
            actions = Actions(local_config, directory, lambda *_: None)
            try:
                file_plan = results[2]["detail"]
                step = next(s for s in file_plan["steps"] if s["action"] == "create_file")
                outcome = actions.execute(Command("create_in_folder", step["value"],
                    json.dumps({"folder": step["folder"], "content": step["content"]})))
                path = folder / step["value"]
                passed = path.is_file() and path.read_text(encoding="utf-8") == "hello Kunal"
                try:
                    actions.execute(Command("create_in_folder", step["value"],
                        json.dumps({"folder": step["folder"], "content": "overwrite"})))
                    passed = False
                except FileExistsError:
                    pass
                row = {"case": 11, "goal": "Execute file plan and refuse overwrite in isolated folder",
                       "passed": passed, "detail": outcome}
            except Exception as exc:
                row = {"case": 11, "goal": "Execute file plan and refuse overwrite in isolated folder",
                       "passed": False, "detail": str(exc)}
            finally:
                actions.close()
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)

        # Query routing and answer model, without a real web request.
        started = time.monotonic()
        response = answer({"question": "Why does the sky look blue?", "options": config["knowledge"]},
            client=session(), search_fn=lambda _q: [{"title": "Sky color", "url": "https://example.org/sky",
                "snippet": "Air scatters shorter blue wavelengths of sunlight more strongly than red wavelengths."}])
        row = {"case": 12, "goal": "Answer a general question locally", "passed": bool(response.get("answer")) and
               "could not" not in response["answer"].casefold(), "seconds": round(time.monotonic() - started, 1),
               "detail": response.get("answer", "")[:300]}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        row = {"case": 13, "goal": "Route a current question to web verification",
               "passed": parse("search the internet for current weather").kind == "ask"}
        results.append(row)
        print(json.dumps(row), flush=True)
    finally:
        client.close()
    report = {"model": config["brain"]["planner"], "passed": sum(row["passed"] for row in results),
              "total": len(results), "results": results}
    (BASE / "artifacts/reports/scenario_results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"RESULT {report['passed']}/{report['total']}", flush=True)
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
