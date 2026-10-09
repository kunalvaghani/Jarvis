"""Exercise two replies through the real warm voice worker, without playing audio."""
import json
from datetime import date
from pathlib import Path
import subprocess
import sys
import time

base = Path(__file__).resolve().parents[2]
started = time.monotonic()
worker = subprocess.Popen([sys.executable, "-u", "-m", "jarvis.kokoro_speech", "--serve", "--no-playback"],
    cwd=base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
try:
    ready = json.loads(worker.stdout.readline())
    assert ready.get("ready"), ready
    loaded = time.monotonic() - started
    results = []
    for text in ("Hello sir. How can I help you today?", "Your workspace is ready. What would you like to do next?"):
        worker.stdin.write(json.dumps({"text": text, "voice": "af_heart", "speed": 1.0}) + "\n")
        worker.stdin.flush()
        response = json.loads(worker.stdout.readline())
        assert response.get("done"), response
        results.append(response)
    evidence = {"date": date.today().isoformat(), "kind": "Actual local worker synthesis, no speaker playback; two replies in one owned process",
                "ready_seconds": round(loaded, 3), "replies": results}
    (base / "artifacts/reports/kokoro-worker-check.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence))
finally:
    worker.stdin.close()
    try:
        worker.wait(timeout=5)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait(timeout=5)
    worker.stdout.close()
    worker.stderr.close()
