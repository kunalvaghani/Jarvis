"""Read-only live planning check: never executes the returned proposal."""
import json
from datetime import date
from pathlib import Path
import time
from jarvis.hermes import HermesClient

base=Path(__file__).resolve().parents[2]
options=json.loads((base/'config/config.json').read_text(encoding='utf-8'))['brain']
client = HermesClient(base, {**options, "hermes": {**options.get('hermes',{}), "timeout_seconds": 120}})
started = time.monotonic()
try:
    result = client.request("plan", lambda: False, goal="Open Calculator",
        tools=[{"action": "open", "description": "Open an installed Windows app by name"}],
        screen={}, apps=["calculator"])
    assert result["question"] == "" and result["steps"][0]["action"] == "open", result
    plan_check = {"elapsed_seconds": round(time.monotonic() - started, 2), "result": result}
    print(json.dumps({"plan": plan_check}), flush=True)
    started = time.monotonic()
    # Synthetic observations check replanning logic; no actual Calculator window is claimed.
    revised = client.request("replan", lambda: False, goal="Open Calculator",
        tools=[{"action": "open", "description": "Open an installed Windows app by name"}],
        screen={"window": "Calculator", "summary": "Calculator window is visible"},
        apps=["calculator"], completed=[{"step": result["steps"][0], "result": "Calculator window observed"}],
        remaining=[], failures=[], steps_left=5)
    assert revised["done"] is True and revised["steps"] == [], revised
    evidence = {"date": date.today().isoformat(), "kind": "Live local inference with synthetic desktop observations; proposals never executed",
                "plan": plan_check, "replan": {"elapsed_seconds": round(time.monotonic() - started, 2), "result": revised}}
    (Path(__file__).resolve().parents[2] / "artifacts/reports/hermes-readonly-check.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"replan": evidence["replan"]}))
finally:
    client.close()
