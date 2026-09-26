"""Compare single-shot and reusable question workers with the configured model."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from jarvis.question_client import QuestionClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    arguments = parser.parse_args()
    if not arguments.live:
        parser.error("Pass --live to run six read-only questions through the configured local model.")
    base = Path(__file__).resolve().parent
    options = json.loads((base / "config.json").read_text(encoding="utf-8"))["knowledge"]
    request = {"question": "What is two plus two? Answer in one short sentence.", "options": options}
    samples = {"single_shot_seconds": [], "reused_worker_seconds": []}
    client = QuestionClient(base, lambda kind, value: print(kind + ": " + value, flush=True))
    try:
        for index in range(3):
            started = time.perf_counter()
            process = subprocess.run([sys.executable, "-m", "jarvis.knowledge_worker"],
                input=json.dumps(request), capture_output=True, text=True, cwd=base, timeout=185,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)
            result = json.loads(process.stdout)
            elapsed = time.perf_counter() - started
            if result.get("error") or not result.get("answer"):
                raise ValueError(str(result))
            samples["single_shot_seconds"].append(round(elapsed, 3))
            print("Single-shot: " + json.dumps({"seconds": round(elapsed, 3), **result}), flush=True)
            started = time.perf_counter()
            result = client.request(request, lambda: False)
            samples["reused_worker_seconds"].append(round(time.perf_counter()-started, 3))
            print("Reusable: " + json.dumps({"pid": client.process.pid,
                "seconds": samples["reused_worker_seconds"][-1], **result}), flush=True)
        print(json.dumps({"model": options["model"], **samples}), flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
