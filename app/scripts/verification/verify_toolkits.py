"""Live local toolkit smoke test: temporary files and existing-model reasoning only."""
import argparse
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from jarvis.brain import BrainClient
from jarvis.task_state import TaskState
from jarvis.toolkits import execute


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    if not parser.parse_args().live:
        parser.error("Pass --live to test temporary files and the configured local model.")
    base = Path(__file__).resolve().parents[2]
    options = json.loads((base / "config/config.json").read_text(encoding="utf-8"))["brain"]
    client = BrainClient(base, options)
    try:
        with tempfile.TemporaryDirectory(dir=base) as directory:
            root = Path(directory)
            (root / "notes.txt").write_bytes(b"first\r\n")
            state = TaskState(root)
            state.start("toolkit smoke", "toolkit", root)
            actions = SimpleNamespace(task_state=state, brain=SimpleNamespace(client=client),
                _task_folder=lambda folder, cancelled: root)
            step = {"action": "append_file", "value": "notes.txt", "folder": str(root), "content": "second\r\n"}
            print(execute(actions, step, lambda: False), flush=True)
            assert (root / "notes.txt").read_bytes() == b"first\r\nsecond\r\n"
            print(execute(actions, {**step, "action": "read_file"}, lambda: False), flush=True)
            result = execute(actions, {**step, "action": "write_spec", "value": "A Python add(a,b) function; give two brief requirements.", "content": ""}, lambda: False)
            assert result.strip()
            print("Local model: " + options["planner"] + "\n" + result, flush=True)
            print("Local toolkit smoke passed; no external writes performed.", flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
