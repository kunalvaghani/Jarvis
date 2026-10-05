"""Resumable model setup. Run with .venv-brain Python after installing dependencies."""
import json
import os
from pathlib import Path
import sys
import time
import subprocess
import shutil

BASE = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(BASE / "models" / "hf-cache")
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["USE_TF"] = "0"


def setup():
    from huggingface_hub import snapshot_download
    import requests
    if "--ollama-only" not in sys.argv:
        print("Downloading only Laya's pinned English checkpoint (resumable).", flush=True)
        snapshot_download("convaiinnovations/laya", revision="1c5edc17a7acd8701df6fc341c0d179f1c62c982",
            local_dir=BASE / "models/laya", allow_patterns=["model.safetensors", "rl_agent_config.json", "encoder/*", "tokenizer/*"], max_workers=2)
    if "--laya-only" in sys.argv:
        return
    session = requests.Session()
    session.trust_env = False
    endpoint = os.environ.get("OLLAMA_SETUP_ENDPOINT", "http://127.0.0.1:11434")
    tags = session.get(endpoint + "/api/tags", timeout=10)
    tags.raise_for_status()
    installed = {model["name"] for model in tags.json().get("models", [])}
    configuration = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    from jarvis.model_selection import required_models
    from jarvis.ollama_models import model_plan, cache_roots, restore_cached, create_alias, ALIASES
    required = required_models(configuration)
    for model in model_plan(required):
        # Inspect the active server again after each prerequisite/import, rather
        # than assuming a Windows cache is visible to a WSL Ollama process.
        tags=session.get(endpoint+'/api/tags',timeout=10);tags.raise_for_status()
        installed={row['name'] for row in tags.json().get('models',[])}
        if model in installed:
            print(model + " is already installed.", flush=True)
            continue
        if model in ALIASES:
            create_alias(session,model,endpoint)
            print(model+' local alias created from '+ALIASES[model]+'.',flush=True)
            continue
        if restore_cached(session,model,cache_roots(configuration),endpoint,report=lambda message:print(message,flush=True)):
            print(model+' restored from existing cached weights.',flush=True)
            continue
        print("Pulling " + model + " (Ollama resumes partial downloads).", flush=True)
        for attempt in range(3):
            try:
                succeeded = False
                with session.post(endpoint + "/api/pull", json={"model": model, "stream": True}, stream=True, timeout=(5, 90)) as response:
                    response.raise_for_status()
                    last_print = 0
                    for line in response.iter_lines():
                        if not line:
                            continue
                        status = json.loads(line)
                        if status.get("error"):
                            # Server errors may contain signed download URLs; keep them out of logs.
                            raise RuntimeError("Model download interrupted by the server or network.")
                        succeeded = status.get("status") == "success" or succeeded
                        if time.monotonic() - last_print > 20 or succeeded:
                            fraction = f" {status.get('completed', 0) / status['total']:.0%}" if status.get("total") else ""
                            print(model + ": " + status.get("status", "") + fraction, flush=True)
                            last_print = time.monotonic()
                if not succeeded:
                    raise RuntimeError("Model download ended before confirmation.")
                break
            except (requests.RequestException, RuntimeError) as exc:
                if attempt == 2:
                    raise RuntimeError("Could not finish " + model + ". Rerun setup to resume the download.") from None
                print("Retrying resumable download for " + model + " (attempt " + str(attempt + 2) + ").", flush=True)
                time.sleep(2)
    print("All configured Jarvis models are available on the active Ollama server.", flush=True)


if __name__ == "__main__":
    setup()
