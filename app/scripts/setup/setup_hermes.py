"""Install a pinned MIT Hermes checkout in a separate local Python runtime."""
import json
import os
from pathlib import Path
import subprocess
import sys

from jarvis.hermes import REVISION

BASE = Path(__file__).resolve().parents[2]


def run(args, env=None):
    subprocess.run([str(arg) for arg in args], cwd=BASE, env=env, check=True)


def main():
    source = BASE / "integrations/hermes-agent"
    if not source.exists():
        run(["git", "clone", "--no-checkout", "https://github.com/NousResearch/hermes-agent.git", source])
        run(["git", "-C", source, "checkout", "--detach", REVISION])
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], cwd=BASE, text=True).strip()
    if revision != REVISION:
        raise ValueError("Hermes checkout differs from the reviewed revision; setup stopped without changing it.")
    bootstrap = BASE / ".venv-hermes-bootstrap"
    if not (bootstrap / "Scripts/python.exe").exists():
        run([sys.executable, "-m", "venv", bootstrap])
    run([bootstrap / "Scripts/python.exe", "-m", "pip", "--isolated", "install", "uv==0.12.21"])
    env = dict(os.environ, UV_PYTHON_INSTALL_DIR=str(BASE / ".jarvis-runtime/hermes-python"),
               UV_CACHE_DIR=str(BASE / ".jarvis-runtime/hermes-cache"))
    uv = bootstrap / "Scripts/uv.exe"
    run([uv, "python", "install", "3.14.7"], env)
    python = BASE / ".venv-hermes/Scripts/python.exe"
    if not python.exists():
        run([uv, "venv", ".venv-hermes", "--python", "3.14.7", "--python-preference", "only-managed"], env)
    run([uv, "pip", "install", "--python", python, "-e", source], env)
    run([python, "-m", "jarvis.hermes_worker", "--check"])
    run([sys.executable, '-m', 'scripts.skills.build_hermes_skill_catalog'])
    config_path = BASE / "config/config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.setdefault("brain", {}).setdefault("hermes", {"enabled": True, "model": "qwen3.5:4b", "timeout_seconds": 120})
    config.setdefault("memory", {})['hermes_skills'] = True
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Hermes installed and skill catalogue indexed; existing planner preference preserved. Restart Jarvis to load it.")


if __name__ == "__main__":
    main()
