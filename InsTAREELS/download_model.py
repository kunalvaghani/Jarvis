"""Download Whisper once; runtime inference uses local files only."""
import json
import os
from pathlib import Path
import hashlib
import argparse
from concurrent.futures import ThreadPoolExecutor
import re
import time

BASE = Path(__file__).resolve().parent
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def main():
    import requests
    parser = argparse.ArgumentParser(description="Download a local CTranslate2 Whisper model.")
    parser.add_argument("--model", help="Model name for the progress message")
    parser.add_argument("--repo", help="Hugging Face repository containing model.bin")
    parser.add_argument("--output", help="Workspace-relative destination directory")
    parser.add_argument("--parallel", type=int, default=1, help="Parallel range requests for large weights (1-8)")
    args = parser.parse_args()
    if not 1 <= args.parallel <= 8:
        raise ValueError("Parallel downloads must be between 1 and 8.")
    config = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    target = (BASE / (args.output or config["model_path"])).resolve()
    if target != BASE and BASE not in target.parents:
        raise ValueError("Model output must stay inside the Jarvis workspace.")
    model = args.model or config["whisper"]["model"]
    if not re.fullmatch(r"[a-z0-9.-]+", model):
        raise ValueError("Use a Systran model name such as small.en or medium.en.")
    target.mkdir(parents=True, exist_ok=True)
    repo = args.repo or config["whisper"].get("repo") or f"Systran/faster-whisper-{model}"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Use a Hugging Face repository like Systran/faster-whisper-small.")
    print(f"Downloading Whisper {model} into {target} (resumable)…", flush=True)
    response = requests.get(f"https://huggingface.co/api/models/{repo}", params={"blobs": "true"}, timeout=60)
    response.raise_for_status()
    metadata = response.json()
    revision = metadata["sha"]
    for item in metadata["siblings"]:
        name = item["rfilename"]
        if name not in {"model.bin", "config.json", "tokenizer.json", "vocabulary.txt", "vocabulary.json", "preprocessor_config.json"}:
            continue
        destination = target / name
        expected_size = item.get("size")
        digest = item.get("lfs", {}).get("sha256")
        if destination.is_file() and (not expected_size or destination.stat().st_size == expected_size):
            if not digest or file_hash(destination) == digest:
                print(f"Already installed: {name}", flush=True)
                continue
        partial = destination.with_name(name + ".partial")
        for attempt in range(4):
            try:
                start = partial.stat().st_size if partial.exists() else 0
                url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
                if name == "model.bin" and args.parallel > 1 and expected_size and expected_size - start > 64 * 1024 * 1024:
                    download_parallel(url, partial, start, expected_size, args.parallel)
                else:
                    headers = {"Range": f"bytes={start}-"} if start else {}
                    with requests.get(url, headers=headers, stream=True, timeout=(30, 120)) as download:
                        download.raise_for_status()
                        append = start > 0 and download.status_code == 206
                        with partial.open("ab" if append else "wb") as output:
                            for chunk in download.iter_content(1024 * 1024):
                                output.write(chunk)
                if expected_size and partial.stat().st_size != expected_size:
                    raise IOError(f"Incomplete download: {name}")
                if digest and file_hash(partial) != digest:
                    partial.unlink()
                    raise IOError(f"Model checksum mismatch: {name}")
                partial.replace(destination)
                print(f"Installed {name}", flush=True)
                break
            except (requests.RequestException, IOError) as exc:
                if attempt == 3:
                    raise
                print(f"Retrying {name}: {type(exc).__name__}", flush=True)
                time.sleep(2)
    print("Local Whisper model ready.")


def download_parallel(url, partial, start, size, workers):
    """Fetch independent verified byte ranges, then append them in order."""
    import requests
    chunk_size = 64 * 1024 * 1024
    ranges = [(begin, min(begin + chunk_size, size) - 1)
              for begin in range(start, size, chunk_size)]

    def fetch(bounds):
        begin, end = bounds
        part = partial.with_name(f"{partial.name}.{begin}-{end}.range")
        length = end - begin + 1
        if part.is_file() and part.stat().st_size == length:
            return part
        for attempt in range(3):
            try:
                with requests.get(url, headers={"Range": f"bytes={begin}-{end}"},
                                  stream=True, timeout=(30, 120)) as response:
                    response.raise_for_status()
                    if response.status_code != 206 or response.headers.get("Content-Range", "").split("/")[0] != f"bytes {begin}-{end}":
                        raise IOError("Model host did not honor the requested byte range.")
                    with part.open("wb") as output:
                        for chunk in response.iter_content(1024 * 1024):
                            output.write(chunk)
                if part.stat().st_size != length:
                    raise IOError("Incomplete model byte range.")
                return part
            except (requests.RequestException, IOError):
                if attempt == 2:
                    raise
                time.sleep(2)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(fetch, ranges))
    with partial.open("ab") as output:
        for part in parts:
            with part.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
            part.unlink()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
