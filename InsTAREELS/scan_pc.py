"""Index paths only. Never read user file contents, follow junctions, or launch apps."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import time

BASE = Path(__file__).resolve().parent
SKIP = {"windows", "windowsapps", "programdata", "appdata", "$recycle.bin",
        "system volume information", "config.msi", "node_modules", ".git", ".venv",
        "venv", "__pycache__", "cache", "caches", "npm-cache", "temp", "tmp",
        ".cache", ".pnpm-store", ".codex", ".agents", ".claude", ".cursor"}


def alias(name):
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    return " ".join(re.sub(r"[^\w. +#-]", " ", name.lower()).split())


def save(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def add_spoken_aliases(apps):
    candidates = {}
    for name, target in list(apps.items()):
        short = re.sub(r"\s+(?:v?\d[\d.]*)(?:\s.*)?$", "", name).strip()
        if short and short != name:
            candidates.setdefault(short, []).append(target)
    for short, targets in candidates.items():
        if all(target == targets[0] for target in targets):
            apps.setdefault(short, targets[0])
    for short, full in {"vs code": "visual studio code", "vscode": "visual studio code", "chrome": "google chrome"}.items():
        if full in apps:
            apps.setdefault(short, apps[full])


def main():
    config_path = BASE / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sources = json.loads((BASE / "installed_apps.scan.json").read_text(encoding="utf-8-sig"))
    backup = BASE / "config.before-pc-scan.json"
    if not backup.exists():
        shutil.copy2(config_path, backup)
    apps = dict(config["apps"])
    protected = set(apps)
    for item in sources["apps"]:
        name = alias(item["Name"])
        if name and name not in protected:
            apps[name] = {"shell_id": item["AppID"]}
    for item in sources["shortcuts"]:
        target = Path(os.path.expandvars(item["target"])) if item["target"] else None
        name = alias(item["name"])
        if name and name not in protected and target and target.suffix.lower() == ".exe" and target.is_file():
            apps[name] = {"shortcut": item["shortcut"], "executable": str(target)}
    for item in sources["app_paths"]:
        path = Path(os.path.expandvars(item["target"]))
        name = alias(Path(item["name"]).stem)
        if name and name not in apps and path.is_file():
            apps[name] = [str(path)]
    # Useful spoken aliases share an already discovered launch target.
    synonyms = {"chrome": "google chrome", "vs code": "visual studio code", "code": "visual studio code",
                "word": "word", "excel": "excel", "power point": "powerpoint", "file manager": "file explorer"}
    for short, full in synonyms.items():
        if full in apps:
            apps.setdefault(short, apps[full])
    add_spoken_aliases(apps)
    roots = sources["roots"]
    files, folders, excluded, inaccessible = [], [], [], []
    stack = list(roots)
    started = last_report = time.monotonic()
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink() or entry.stat(follow_symlinks=False).st_file_attributes & 0x400:
                            excluded.append(entry.path)
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.lower() in SKIP:
                                excluded.append(entry.path)
                            else:
                                folders.append(entry.path)
                                stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            files.append(entry.path)
                    except OSError:
                        inaccessible.append(entry.path)
        except OSError:
            inaccessible.append(directory)
        if time.monotonic() - last_report > 15:
            print(f"Scanned {len(files):,} file paths, {len(folders):,} folders…", flush=True)
            last_report = time.monotonic()
    home = Path.home()
    named_folders = dict(config.get("folders", {}))
    for name in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos", "OneDrive", "Dropbox"):
        if (home / name).is_dir():
            named_folders.setdefault(name.lower(), str(home / name))
    named_folders.setdefault("jarvis files", str((BASE / config["files_root"]).resolve()))
    for drive in roots:
        named_folders.setdefault(f"{drive[0].lower()} drive", drive)
    config["apps"] = dict(sorted(apps.items()))
    config["folders"] = named_folders
    config.setdefault("files", {})
    config["file_catalog"] = "file_catalog.json"
    save(BASE / "file_catalog.json", {"version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
         "roots": roots, "files": files, "folders": folders})
    report = {"app_aliases": len(apps), "files": len(files), "folders": len(folders),
              "elapsed_seconds": round(time.monotonic() - started, 1),
              "excluded_directory_names": sorted(SKIP), "excluded_paths": excluded,
              "inaccessible_paths": inaccessible}
    save(BASE / "scan_report.json", report)
    save(config_path, config)
    from build_catalog_index import build
    build(BASE)
    print(json.dumps({k:v for k,v in report.items() if not isinstance(v, list)}, indent=2))


if __name__ == "__main__":
    main()
