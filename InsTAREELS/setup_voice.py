"""Download the free pinned Kokoro voice assets into Jarvis's model directory."""
import hashlib
import json
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else _digest(source)


def _digest(source):
    result = hashlib.sha256()
    for block in iter(lambda: source.read(1024 * 1024), b""):
        result.update(block)
    return result.hexdigest()


def setup():
    assets = json.loads((BASE / "integrations/kokoro-assets.json").read_text(encoding="utf-8"))
    client = requests.Session()
    client.trust_env = False
    for asset in assets["assets"]:
        path = BASE / asset["path"]
        if path.is_file() and digest(path) == asset["sha256"]:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".download")
        with client.get(asset["url"], stream=True, timeout=(10, 90)) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for block in response.iter_content(1024 * 1024):
                    output.write(block)
        if digest(temporary) != asset["sha256"]:
            raise ValueError("Kokoro asset checksum mismatch: " + path.name)
        temporary.replace(path)
    print("Free local Kokoro voice assets ready.")


if __name__ == "__main__":
    setup()
