"""Update the local God's Eye View checkout from upstream without losing local state.

The current folder is kept as a dated backup (source only), the newest upstream main is unpacked in its place,
and `node_modules`, `.env`, caches and logs are moved across. `npm ci` runs only when the lockfile changed.
"""
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

import requests

REPO = "bilawalsidhu/gods-eye-view"
KEEP = ("node_modules", ".env", ".gev-cache", ".gev-logs", "jarvis-launch.log", "jarvis-gods-eye.json")


def digest(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def latest():
    data = requests.get("https://api.github.com/repos/" + REPO + "/commits/main", timeout=20,
                        headers={"Accept": "application/vnd.github+json", "User-Agent": "Jarvis"}).json()
    return data["sha"], data["commit"]["committer"]["date"], data["commit"]["message"].splitlines()[0][:120]


def update(source, report=lambda *a: None, cancelled=lambda: False, run=subprocess.run):
    source = Path(source)
    marker = source / "jarvis-gods-eye.json"
    try:
        current = json.loads(marker.read_text(encoding="utf-8")).get("commit", "")
    except (OSError, ValueError):
        current = ""
    sha, date, message = latest()
    if sha == current:
        return {"updated": False, "commit": sha, "date": date, "message": "Already up to date (" + date[:10] + ")."}
    report("status", "Downloading God's Eye View " + sha[:8])
    raw = requests.get("https://codeload.github.com/" + REPO + "/zip/" + sha, timeout=300,
                       headers={"User-Agent": "Jarvis"}).content
    if cancelled():
        raise ValueError("God's Eye update cancelled before changing anything.")
    archive = zipfile.ZipFile(io.BytesIO(raw))
    root = archive.namelist()[0].split("/")[0]
    stage = source.parent / (source.name + ".incoming")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    for info in archive.infolist():
        name = info.filename[len(root) + 1:]
        if not name or ".." in Path(name).parts or Path(name).is_absolute():
            continue
        target = stage / name
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    old_lock = digest(source / "package-lock.json")
    new_lock = digest(stage / "package-lock.json")
    backup = source.parent / (source.name + ".backup-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    backup.mkdir()
    moved_old, moved_new = [], []
    try:
        # Swap contents rather than renaming the folder: a shell or editor with this folder open blocks a rename.
        for child in list(source.iterdir()):
            if child.name not in KEEP:
                os.replace(child, backup / child.name)
                moved_old.append(child.name)
        for child in list(stage.iterdir()):
            if (source / child.name).exists():
                continue  # Kept local state wins (node_modules, .env, caches).
            os.replace(child, source / child.name)
            moved_new.append(child.name)
    except OSError:
        for name in moved_new:  # Put everything back exactly as it was.
            os.replace(source / name, stage / name)
        for name in moved_old:
            os.replace(backup / name, source / name)
        raise
    shutil.rmtree(stage, ignore_errors=True)
    installed = False
    if old_lock != new_lock or not (source / "node_modules").exists():
        report("status", "Installing God's Eye View dependencies (npm ci)")
        npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
        result = run([npm, "ci", "--no-audit", "--no-fund"], cwd=source, capture_output=True, text=True, timeout=1800)
        if result.returncode:
            raise ValueError("npm ci failed; the previous version is kept at " + str(backup) + ": " + result.stderr[-600:])
        installed = True
    marker.write_text(json.dumps({"commit": sha, "date": date, "message": message,
                                  "updated_at": datetime.now().isoformat(timespec="seconds")}, indent=1), encoding="utf-8")
    return {"updated": True, "commit": sha, "date": date, "message": message, "dependencies_reinstalled": installed,
            "backup": str(backup)}
