"""Activate a downloaded local model only after the scenario checks passed."""
import json
import os
from pathlib import Path
import sys

from jarvis.knowledge_worker import ensure_server, session

BASE = Path(__file__).resolve().parent


def main(model):
    report = json.loads((BASE / "scenario_results.json").read_text(encoding="utf-8"))
    if report.get("model") != model or report.get("passed") != report.get("total") or report.get("total", 0) < 10:
        raise ValueError("The requested model has not passed ten or more current scenario checks.")
    installed = {item["name"] for item in ensure_server(session()).get("models", [])}
    if model not in installed:
        raise ValueError("The requested local model is not installed in Ollama.")
    path = BASE / "config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["brain"]["planner"] = model
    config["brain"]["decision"] = model
    config["knowledge"]["model"] = model
    config["knowledge"]["prompt_format"] = "ollama_chat"
    temporary = path.with_suffix(".model-tmp")
    temporary.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    print(f"Jarvis now uses {model} for planning, decisions, and answers. Restart Jarvis.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "qwen3.5:4b":
        raise SystemExit("Usage: activate_model.py qwen3.5:4b")
    main(sys.argv[1])
