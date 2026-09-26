"""Minimal standard-library entry point, independent of the supervised package."""
import ast
import json
from pathlib import Path
import runpy
import shutil
import sys
import time

BASE = Path(__file__).resolve().parent


def restore_entrypoints(base=BASE):
    base = Path(base)
    runtime = base / ".jarvis-runtime"
    runtime.mkdir(exist_ok=True)
    for relative in ("jarvis/__init__.py", "jarvis/recovery.py", "jarvis/launcher.py"):
        source = base / relative
        try:
            ast.parse(source.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeError, OSError):
            saved = runtime / "sources" / relative
            ast.parse(saved.read_text(encoding="utf-8"))
            if source.exists():
                damaged = runtime / "damaged" / (str(time.time_ns()) + "-" + source.name)
                damaged.parent.mkdir(exist_ok=True)
                shutil.copy2(source, damaged)
            source.parent.mkdir(exist_ok=True)
            shutil.copy2(saved, source)
            with (runtime / "repairs.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps({"at": time.time(), "message":
                    "Restored invalid launcher source " + relative + " from its startup snapshot."}) + "\n")


def main():
    runtime = BASE / ".jarvis-runtime"
    runtime.mkdir(exist_ok=True)
    if "--stop" in sys.argv:
        (runtime / "stop").touch()
        return
    try:
        restore_entrypoints()
        runpy.run_module("jarvis.launcher", run_name="__main__")
    except Exception as exc:
        with (runtime / "repairs.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps({"at": time.time(), "message":
                "Launcher could not recover: " + str(exc)}) + "\n")


if __name__ == "__main__":
    main()
