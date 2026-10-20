"""Resumable model setup. Run with .venv-brain Python after installing dependencies."""
import json
import os
from pathlib import Path
import sys
import time
import subprocess
import shutil

BASE = Path(__file__).resolve().parents[2]
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
    configuration = json.loads((BASE / "config/config.json").read_text(encoding="utf-8"))
    from jarvis.model_selection import required_models
    from jarvis.ollama_models import model_plan, cache_roots, restore_cached, create_alias, ALIASES
    required = required_models(configuration)
    if "--model" in sys.argv:
        approved_pull(session, endpoint, sys.argv[sys.argv.index("--model") + 1],
                      sys.argv[sys.argv.index("--revision") + 1], int(sys.argv[sys.argv.index("--max-bytes") + 1]))
        return
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


REGISTRY = "https://registry.ollama.ai/v2/"
MANIFEST_TYPES = "application/vnd.docker.distribution.manifest.v2+json"


def _digest(value):
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:") or             any(c not in "0123456789abcdef" for c in value[7:]):
        raise SystemExit("The approved manifest names an invalid layer digest; nothing was installed.")
    return value[7:]


def _file_sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def approved_pull(session, endpoint, model, revision, max_bytes, registry=REGISTRY, store=None):
    """One approved download by content address (P34-002, R1).

    The manifest is fetched **by its approved digest**, never by the mutable tag, and every layer is fetched by its
    own digest into ``<store>/blobs``. No ``/api/pull`` of the tag is made. Bytes are capped per layer and in total by
    the approved budget, every layer is hash-checked before it is published, and the tag manifest is only written once
    all layers verify. Partial layers stay as ``-partial`` files for an approved resume; nothing is deleted, and there
    is no retry. Ollama must then list the model at the approved digest, or the run fails (files kept).
    """
    import hashlib
    import requests
    from jarvis.repair_authorization import model_reference, model_store
    path, tag = model_reference(model)  # validate again at this direct CLI/transport boundary, before HTTP
    _digest(revision)
    manifest = requests.get(registry + path + "/manifests/" + revision, timeout=(5, 30),
                            headers={"Accept": MANIFEST_TYPES})
    manifest.raise_for_status()
    raw = manifest.content
    if "sha256:" + hashlib.sha256(raw).hexdigest() != revision:
        raise SystemExit("The registry returned a manifest other than the approved revision; nothing was installed.")
    body = json.loads(raw)
    layers = [body.get("config", {})] + list(body.get("layers", []))
    sizes = [layer.get("size") for layer in layers]
    if not all(type(size) is int and size > 0 for size in sizes) or sum(sizes) > max_bytes:
        raise SystemExit("The download size of " + model + " is unknown or exceeds the approved budget; nothing was pulled.")
    store = Path(store or model_store()).resolve()
    manifests = store / "manifests" / "registry.ollama.ai"
    target = manifests / Path(path) / tag
    if not target.resolve().is_relative_to(manifests.resolve()) or not target.resolve().is_relative_to(store):
        raise SystemExit("The approved model manifest escapes its store; nothing was installed.")
    if target.exists():
        raise SystemExit("A manifest for " + model + " already exists; it was kept and nothing was installed.")
    (store / "blobs").mkdir(parents=True, exist_ok=True)
    print("Fetching approved " + model + " by digest (" + str(sum(sizes)) + " bytes, budget " + str(max_bytes) + ").",
          flush=True)
    transferred = 0
    for layer in layers:
        digest, size = _digest(layer.get("digest")), layer["size"]
        blob = store / "blobs" / ("sha256-" + digest)
        if blob.exists() and _file_sha256(blob) == digest:
            continue
        partial = blob.with_name(blob.name + "-partial")
        have = partial.stat().st_size if partial.exists() else 0
        if have > size:
            raise SystemExit("A partial layer is larger than its approved size; it was kept and nothing was installed.")
        if have < size:
            headers = {"Range": "bytes=" + str(have) + "-"} if have else {}
            with requests.get(registry + path + "/blobs/sha256:" + digest, headers=headers, stream=True,
                              timeout=(5, 90)) as response:
                response.raise_for_status()
                mode = "ab" if have and response.status_code == 206 else "wb"
                written = have if mode == "ab" else 0
                with open(partial, mode) as output:
                    for chunk in response.iter_content(1 << 20):
                        written += len(chunk)
                        transferred += len(chunk)
                        if written > size or transferred > max_bytes:
                            raise SystemExit("The registry sent more than the approved bytes; the partial layer is kept.")
                        output.write(chunk)
        if _file_sha256(partial) != digest:
            raise SystemExit("A downloaded layer does not match its approved digest; the partial file is kept.")
        os.replace(partial, blob)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".approved-partial")
    temporary.write_bytes(raw)
    os.replace(temporary, target)
    tags = session.get(endpoint + "/api/tags", timeout=10)
    tags.raise_for_status()
    installed = {row["name"]: row.get("digest", "") for row in tags.json().get("models", [])}
    listed = installed.get(model if ":" in model else model + ":latest", "")
    if "sha256:" + listed.removeprefix("sha256:") != revision:
        raise SystemExit("Ollama does not list " + model + " at the approved revision; the fetched files were kept.")
    print(model + " installed at the approved revision.", flush=True)


if __name__ == "__main__":
    setup()
