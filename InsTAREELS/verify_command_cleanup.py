"""Synthetic local model comparison; no microphone capture or task execution."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
import requests
from jarvis.command_cleanup import CommandCleanup, allowed_edit, proposal_payload, chosen_text, settings
from jarvis.engine import Engine

CASES = [
    ("jarvis um open note pad", "jarvis open notepad"),
    ("jarvis open you tube", "jarvis open youtube"),
    ("jarvis please launch spot ify", "jarvis please launch spotify"),
    ("jarvis opne calculator", "jarvis open calculator"),
    ("jarvis uh what is gravity", "jarvis what is gravity"),
    ("jarvis open chrome", "jarvis open chrome"),
    ("jarvis don't delete notes.txt", "jarvis don't delete notes.txt"),
    ("jarvis write um open note pad", "jarvis write um open note pad"),
    ("jarvis set volume to 37", "jarvis set volume to 37"),
    ("jarvis search for you tube bugs", "jarvis search for you tube bugs"),
    ("jarvis open chrome then close spotify", "jarvis open chrome then close spotify"),
    ("jarvis send Maya 25 dollars", "jarvis send Maya 25 dollars"),
    ("hey jarvis erm could you start cal culator", "hey jarvis could you start calculator"),
    ("jarvis opun chrome", "jarvis open chrome"),
    ("jarvis open Note Pad.txt", "jarvis open Note Pad.txt"),
    ("jarvis type you tube and um", "jarvis type you tube and um"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["qwen2.5:0.5b", "qwen3.5:0.8b", "qwen2.5:3b-instruct"])
    args = parser.parse_args()
    results = []
    with requests.Session() as session:
        session.trust_env = False
        for model in args.models:
            rows = []
            for source, expected in CASES:
                started = time.monotonic()
                payload = proposal_payload(source, allowed_edit(source), settings({"model": model}), stream=False)
                try:
                    response = session.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=(1, 60))
                    response.raise_for_status()
                    data = response.json()
                    candidate = chosen_text(json.loads(data["message"]["content"]), source, allowed_edit(source))
                    guarded = candidate if candidate in (source, allowed_edit(source)) else source
                    rows.append({"source": source, "expected": expected, "candidate": candidate,
                                 "guarded": guarded, "seconds": round(time.monotonic() - started, 4),
                                 "load_seconds": round(data.get("load_duration", 0) / 1e9, 4),
                                 "raw_correct": candidate == expected, "guarded_correct": guarded == expected})
                except Exception as exc:
                    rows.append({"source": source, "error": type(exc).__name__, "seconds": round(time.monotonic()-started, 4)})
                print(model, len(rows), rows[-1]["seconds"], rows[-1].get("raw_correct"), flush=True)
            times = [row["seconds"] for row in rows[1:]]
            results.append({"model": model, "first_request_seconds": rows[0]["seconds"],
                "warm_median_seconds": round(statistics.median(times), 4), "warm_max_seconds": max(times),
                "raw_correct": sum(row.get("raw_correct", False) for row in rows),
                "guarded_correct": sum(row.get("guarded_correct", False) for row in rows), "cases": rows})
    record = {"at": datetime.now(timezone.utc).isoformat(), "scope": f"{len(CASES)} authored text fixtures per model; no real audio or execution; production prompt/options/schema and finite-edit guard; nonstream measurement harness; first request may be already loaded", "results": results}
    Path("artifacts/command-cleanup-model-check.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps([{key: value for key, value in result.items() if key != "cases"} for result in results], indent=2))
    verify_runtime()


def verify_runtime():
    config = json.loads(Path('config.json').read_text(encoding='utf-8'))
    events, requests_made = [], [0]
    from jarvis.command_cleanup import propose
    def request(*args):
        requests_made[0] += 1
        return propose(*args)
    cleanup = CommandCleanup(config['command_cleanup'], lambda *args: events.append(args), request=request)
    engine = Engine(lambda *_: None, lambda *_: None)
    engine.activate()
    live = []
    for source, expected in CASES:
        started = time.monotonic()
        result = cleanup.clean(source, engine)
        live.append({'source': source, 'expected': expected, 'result': result,
                     'correct': result == expected, 'seconds': round(time.monotonic()-started, 4)})
    Path('artifacts/command-cleanup-runtime-check.json').write_text(json.dumps({
        'at': datetime.now(timezone.utc).isoformat(), 'scope': 'Live loopback Ollama plus production cleanup/filter on synthetic transcripts; no microphone or task execution',
        'model': config['command_cleanup']['model'], 'requests': requests_made[0],
        'correct': sum(row['correct'] for row in live), 'cases': live, 'events': events}, indent=2), encoding='utf-8')
    print(json.dumps({'runtime_correct': sum(row['correct'] for row in live), 'cases': len(live),
                      'requests': requests_made[0], 'max_seconds': max(row['seconds'] for row in live)}, indent=2))


if __name__ == "__main__":
    main()
