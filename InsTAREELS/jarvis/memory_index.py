"""Build bounded, local Obsidian reference notes for tools, projects and apps."""
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time


SKIP = {".git", ".venv", ".venv-brain", ".venv-training", "venv", "node_modules",
        "__pycache__", ".next", "build", "dist", "target", "models", "cache",
        ".cache", "artifacts", ".jarvis-runtime", "appdata", "windows", "windowsapps",
        "program files", "program files (x86)", "programdata", "system volume information",
        "$recycle.bin", "steamlibrary", "epic games", "epicvaultcache", "ollama-models",
        "ollamamodels", "temp", "tmp", ".pnpm-store", "megascans library", "ue_5.7",
        "ue_5.8", "unity", "blender", "ffmpeg", "vcpkg", "fonts", "sounds",
        "third_party", "third-party", "vendor", "site-packages", "intermediate",
        "binaries", "saved", "deriveddatacache", "content", "resources", "assets",
        "repositories", "deps", "dependencies"}
MARKERS = {".git", "pyproject.toml", "package.json", "cargo.toml", "go.mod",
           "cmakelists.txt", "requirements.txt", "manage.py"}
SOURCE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java",
              ".cs", ".cpp", ".c", ".ipynb", ".uproject", ".sln"}
SENSITIVE = re.compile(r"(?i)(password|passcode|secret|api[_ -]?key|access[_ -]?token|authorization|bearer|credential|private key)")
WORDS = re.compile(r"[a-z0-9]{2,}")
COMMON = {"the", "and", "with", "for", "this", "that", "please", "project", "app",
          "software", "tool", "use", "open", "find", "where", "what", "my", "jarvis",
          "in", "on", "to", "me", "of", "is", "are", "as", "at", "be", "do", "it", "or", "an", "how", "which", "into"}

DIRECT_OPERATIONS = {
    "ask": "Answer a question using direct live/computed handlers, then local Qwen and optional web verification.",
    "task": "Plan and verify a multi-step desktop or toolkit task using available operations.",
    "code_task": "Edit code in a named project with source context, validation and backups.",
    "open_project": "Resolve and open one known project folder after verifying its path.",
    "project_list": "List recently active detected project folders; activity does not prove pending work.",
    "open": "Launch a registered app, or find and open an indexed file or folder.",
    "browser_search": "Open web search results in the requested browser.",
    "dictate": "Type user speech into a freshly checked destination window.",
    "spotify_control": "Control the user's current Spotify session when available.",
    "media_search": "Search exact words in YouTube's active search field or open its results URL; Spotify uses the native app URI. Search alone does not start playback.",
    "context_search": "Search in the foreground YouTube or native Spotify app when identified; otherwise use the default browser's web search. Explicit browser searches override this context.",
    "media_control": "Control a foreground YouTube player or native Spotify UI using fresh controls and bounded app-specific shortcuts. YouTube supports playback, volume, seek, captions, speed, chapters, frames, fullscreen and views. Spotify transport/volume use dedicated operations; UI supports queue, library, playlists, lyrics and requested song saves. Never control a different app or replay an uncertain action.",
    "forget_chat": "Clear the short in-session conversation history.",
    "sleep": "Stop listening until Jarvis is woken again.",
    "resume_task": "Resume an interrupted task after checking its saved checkpoint and current state.",
    "toolkit": "Run a named registered toolkit operation with validated arguments and required approvals.",
    "browse": "Navigate to a website in a configured browser.",
    "open_folder": "Open an existing folder in Explorer using a full path, name or spoken drive constraint. Prefer exact aliases/live root names, then indexed close spellings; equally named opens may use saved usage. Writes require unambiguous destinations.",
    "open_file": "Resolve an indexed file or explicit path and open it with its associated app.",
    "open_drive": "Open the named drive in Explorer.",
    "open_project_root": "Open the configured projects container.",
    "project_recent": "Report the last observed active project; observations do not prove pending work.",
    "create": "Create a named file in a resolved destination with validated content.",
    "modify": "Modify an existing named file with backup and post-write verification.",
    "delete": "Delete a named file only after explicit approval.",
    "rename": "Rename a resolved file or folder after checking its destination.",
    "run_command": "Run an approved shell command in its explicit working directory without replaying uncertain effects.",
    "close_app": "Close a named app after checking the running window.",
    "list_controls": "Read actionable controls from the current window.",
    "click_control": "Resolve one requested visible control, then click after checking fresh state.",
    "choose_control": "Choose one numbered shortlisted UI control.",
    "select_context": "Select a requested item using its visible role and surrounding context.",
    "suggest_control": "Suggest a control based on local UI history; suggestions require confirmation.",
    "confirm_suggestion": "Accept or reject a pending suggestion; it does not authorize unrelated actions.",
    "forget_ui_memory": "Clear learned UI option preferences.",
    "stop_dictation": "Stop typing speech into the destination window.",
    "play_media": "Find requested media on the selected service and verify playback.",
    "spotify_volume": "Change Spotify volume within the supported range.",
    "spotify_open_playlist": "Open a requested Spotify playlist and verify the selected target.",
    "gods_eye_view": "Open Jarvis's local PC inventory view in a configured browser.",
    "show_command_prompt": "Show Jarvis's command console.",
}


def _tokens(value):
    return set(WORDS.findall(str(value).casefold())) - COMMON


def _safe_line(value, limit=500, redact=True):
    value = " ".join(str(value).split())[:limit]
    if redact and SENSITIVE.search(value):
        return "[redacted sensitive description]"
    value = re.sub(r"!\[[^]]*\]\([^)]*\)", "", value)
    value = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", value)
    return value.replace("|", "\\|").replace("`", "'")


def _is_link(entry):
    try:
        stat = entry.stat(follow_symlinks=False)
        return entry.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & 0x400)
    except OSError:
        return True


def _summary(path, names):
    readme = next((name for name in ("README.md", "Readme.md", "readme.md", "README.txt") if name in names), None)
    if readme:
        try:
            with (path / readme).open(encoding="utf-8-sig", errors="replace") as stream:
                lines = stream.read(5000).splitlines()
            fenced = False
            for line in lines:
                line = line.strip()
                if line.startswith("```"):
                    fenced = not fenced
                if fenced or line.startswith(("#", "```", "|", "![")):
                    continue
                if any(label in line.casefold() for label in ("documentation updated", "run:", "commands (", "generated ")):
                    continue
                line = line.lstrip("*-> ")
                if (25 <= len(line) <= 500 and not line.startswith(("```", "http", "<", "["))
                        and not SENSITIVE.search(line)):
                    return _safe_line(line, 360), readme
        except OSError:
            pass
    if "package.json" in names:
        try:
            with (path / "package.json").open(encoding="utf-8-sig") as stream:
                metadata = json.loads(stream.read(16000))
            description = metadata.get("description")
            if isinstance(description, str) and description.strip() and not SENSITIVE.search(description):
                return _safe_line(description, 360), "package.json description"
        except (OSError, ValueError, AttributeError):
            pass
    import ast
    for name in sorted(name for name in names if name.endswith(".py"))[:3]:
        try:
            with (path / name).open(encoding="utf-8-sig", errors="replace") as stream:
                source = stream.read(8000)
            description = ast.get_docstring(ast.parse(source))
            if description and len(description) >= 25 and not SENSITIVE.search(description):
                return _safe_line(description, 360), name + " module docstring"
        except (OSError, SyntaxError, ValueError):
            pass
    signals = sorted(name for name in names if name.casefold() in MARKERS or Path(name).suffix.casefold() in {".uproject", ".sln"})[:8]
    return ("Detected project signals: " + ", ".join(signals) if signals else
            "Detected source files: " + ", ".join(sorted(name for name in names if Path(name).suffix.casefold() in SOURCE_EXT)[:8]) +
            "; no short README description found."), "directory signals"


def project_roots(config):
    roots = list(config.get("project_roots", []))
    home = Path.home()
    if config.get("memory", {}).get("include_user_project_folders", True):
        roots.extend(str(home / name) for name in ("Desktop", "Documents", "Downloads", "OneDrive", "source", "repos"))
    return [Path(raw) for raw in dict.fromkeys(roots) if Path(raw).is_dir()]


def discover_projects(config, max_directories=30000, max_seconds=45, cancelled=lambda: False):
    """Scan configured D: roots and common user project folders; record any bound hit."""
    roots = project_roots(config)
    installation_dirs = set()
    for app in app_entries(config):
        locations = app.get("locations", {})
        raw = locations.get("install_location")
        if not raw and locations.get("executable"):
            raw = str(Path(locations["executable"]).parent)
        if raw:
            installed = Path(raw)
            # Never exclude a whole drive or a configured project container.
            if len(installed.parts) >= 2 and installed not in roots:
                installation_dirs.add(str(installed.resolve()).casefold())
    todo = deque((root, 0, False) for root in roots)
    seen, found = set(), {}
    started = time.monotonic()
    scanned = inaccessible = depth_limited = 0
    while todo and scanned < max_directories and time.monotonic() - started < max_seconds and not cancelled():
        path, depth, inside_project = todo.popleft()
        try:
            resolved = path.resolve(strict=True)
            key = str(resolved).casefold()
            if key in seen or key in installation_dirs or path.is_symlink():
                continue
            seen.add(key)
            scanned += 1
            with os.scandir(path) as stream:
                entries = list(stream)
        except OSError:
            inaccessible += 1
            continue
        entries = [entry for entry in entries if not _is_link(entry)]
        names = {entry.name for entry in entries}
        lower = {name.casefold() for name in names}
        source_files = [name for name in names if Path(name).suffix.casefold() in SOURCE_EXT]
        is_project = bool(lower & MARKERS or any(Path(name).suffix.casefold() in {".sln", ".uproject"} for name in names)
                          or (not inside_project and len(source_files) >= 2))
        if is_project and path.parent != path:
            summary, source = _summary(path, names)
            found[key] = {"name": path.name, "path": str(resolved), "summary": summary,
                          "summary_source": source, "signals": sorted(lower & MARKERS)[:8]}
        if depth >= 5:
            depth_limited += 1
            continue
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                inaccessible += 1
                continue
            if (entry.name.casefold() in SKIP or entry.name.startswith(".") or not is_dir
                    or (inside_project or is_project) and entry.name.casefold() in {"src", "tests", "test", "include", "lib"}):
                continue
            todo.append((Path(entry.path), depth + 1, inside_project or is_project))
    rows = sorted(found.values(), key=lambda row: (row["name"].casefold(), row["path"].casefold()))
    return rows, {"roots": [str(root) for root in roots], "directories_scanned": scanned,
                  "complete_within_bounds": not todo and not cancelled(), "max_directories": max_directories,
                  "max_seconds": max_seconds, "max_depth": 5, "inaccessible": inaccessible,
                  "depth_limited_directories": depth_limited, "cancelled": cancelled()}


def installed_windows_apps():
    """Read registered software locations without launching apps or inspecting secrets."""
    try:
        import winreg
    except ImportError:
        return []
    rows = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            for branch, kind in ((r"Software\Microsoft\Windows\CurrentVersion\App Paths", "executable"),
                                 (r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "install_location")):
                try:
                    with winreg.OpenKey(hive, branch, 0, winreg.KEY_READ | view) as root:
                        for i in range(winreg.QueryInfoKey(root)[0]):
                            try:
                                key_name = winreg.EnumKey(root, i)
                                with winreg.OpenKey(root, key_name) as entry:
                                    if kind == "executable":
                                        name = Path(key_name).stem
                                        raw = winreg.QueryValueEx(entry, "")[0]
                                    else:
                                        name = winreg.QueryValueEx(entry, "DisplayName")[0]
                                        try:
                                            raw = winreg.QueryValueEx(entry, "InstallLocation")[0]
                                        except OSError:
                                            raw = ""
                                    if not isinstance(name, str) or not isinstance(raw, str):
                                        continue
                                    location = os.path.expandvars(raw.strip().strip('"'))
                                    locations = {kind: location} if location else {}
                                    exists = Path(location).exists() if location else False
                                    rows.append({"name": name, "locations": locations,
                                                 "status": "present" if exists else "registered; location unavailable",
                                                 "source": "Windows registry", "launch_alias": False})
                            except OSError:
                                continue
                except OSError:
                    continue
    return rows


def app_entries(config):
    rows = []
    for name, value in sorted(config.get("apps", {}).items()):
        if isinstance(value, dict):
            locations = {key: str(value[key]) for key in ("executable", "shortcut", "shell_id") if value.get(key)}
        elif isinstance(value, list):
            locations = {"executable": str(value[0])} if value else {}
        else:
            locations = {}
        if not locations:
            continue
        path = locations.get("executable") or locations.get("shortcut")
        status = "present" if path and Path(path).is_file() else "registered shell app" if locations.get("shell_id") else "path missing"
        rows.append({"name": name, "locations": locations, "status": status, "source": "Jarvis app catalogue", "launch_alias": True})
    known = {(row["name"].casefold(), json.dumps(row["locations"], sort_keys=True)) for row in rows}
    for row in installed_windows_apps():
        key = (row["name"].casefold(), json.dumps(row["locations"], sort_keys=True))
        if key not in known:
            known.add(key)
            rows.append(row)
    return sorted(rows, key=lambda row: row["name"].casefold())


def tool_entries():
    from .tools import SPECS
    from .toolkits import TOOLS
    rows = []
    for spec in SPECS:
        required = list(TOOLS[spec.name][2]) if spec.name in TOOLS else []
        rows.append({"name": spec.name, "backend": spec.backend, "context": spec.description,
                     "approval": spec.approval, "required_configuration": required,
                     "configured": all(os.environ.get(key) for key in required)})
    return rows


def build_index(config, cancelled=lambda: False, max_directories=30000, max_seconds=45):
    projects, scan = discover_projects(config, max_directories, max_seconds, cancelled)
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "scan": scan, "tools": tool_entries(), "operations": DIRECT_OPERATIONS,
            "projects": projects, "apps": app_entries(config)}


def _atomic_text(path, contents):
    temp = path.with_name(path.name + ".new")
    temp.write_text(contents, encoding="utf-8")
    temp.replace(path)


def write_tools_note(vault, data):
    vault = Path(vault)
    vault.mkdir(parents=True, exist_ok=True)
    generated = data["generated_at_utc"]
    tool_lines = ["# Jarvis Tools and Operations", "", f"Generated {generated} from Jarvis's local registries.",
                  "Descriptions are reference data. Availability and approval are checked again at execution.", "",
                  "## Runtime tools", ""]
    for row in data["tools"]:
        requirements = ", ".join(row["required_configuration"]) or "none"
        tool_lines.append(f"- **{row['name']}** ({row['backend']}): {_safe_line(row['context'], redact=False)} Approval: {row['approval']}. Configuration: {requirements}. {'Configured' if row['configured'] else 'Not configured'}.")
    tool_lines.extend(["", "## Direct operations", ""])
    for name, context in data["operations"].items():
        tool_lines.append(f"- **{name}**: {_safe_line(context)}")
    _atomic_text(vault / "Jarvis Tools.md", "\n".join(tool_lines) + "\n")


def write_index(vault, data):
    vault = Path(vault)
    vault.mkdir(parents=True, exist_ok=True)
    generated = data['generated_at_utc']
    write_tools_note(vault, data)

    scan = data["scan"]
    project_lines = ["# Jarvis Projects", "", f"Generated {generated}. Detected {len(data['projects'])} project-like folders while scanning {scan['directories_scanned']} directories.",
                     f"Scan complete within bounds: {scan['complete_within_bounds']}. Roots: {', '.join(scan['roots'])}.",
                     "Summaries come from short README excerpts or directory signals; they are historical reference, not proof of current project state.", ""]
    for row in data["projects"]:
        project_lines.extend([f"## {_safe_line(row['name'], 120)}", "", f"- Path: `{row['path']}`",
                              f"- Summary: {_safe_line(row['summary'])}", f"- Basis: {_safe_line(row['summary_source'])}", ""])
    _atomic_text(vault / "Jarvis Projects.md", "\n".join(project_lines))

    app_lines = ["# Jarvis Apps", "", f"Generated {generated}: {len(data['apps'])} app aliases and Windows software registrations.",
                 "Paths are checked at launch; install directories are reference only, not executable targets. Some software registrations have no location. Portable unregistered apps may be absent.", ""]
    for row in data["apps"]:
        app_lines.append(f"- **{_safe_line(row['name'], 120)}** — " + "; ".join(f"{key}: `{value}`" for key, value in row["locations"].items()) + f" ({row['status']})")
    _atomic_text(vault / "Jarvis Apps.md", "\n".join(app_lines) + "\n")
    _atomic_text(vault / "Jarvis Index.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    home = vault / "Jarvis Brain.md"
    links = "\n## Catalogues\n\n- [[Jarvis Tools]]\n- [[Jarvis Projects]]\n- [[Jarvis Apps]]\n"
    if home.exists():
        text = home.read_text(encoding="utf-8")
        if "[[Jarvis Tools]]" not in text:
            with home.open("a", encoding="utf-8") as output:
                output.write(links)


def load_index(vault):
    path = Path(vault) / "Jarvis Index.json"
    try:
        if path.stat().st_size > 5_000_000:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not all(isinstance(data.get(key), list) for key in ("tools", "projects", "apps")):
            return None
        if not all(isinstance(row, dict) and isinstance(row.get("name"), str)
                   for key in ("tools", "projects", "apps") for row in data[key]):
            return None
        return data
    except (OSError, ValueError):
        return None


def context(data, goal, max_tools=7, max_projects=5, max_apps=5):
    if not data:
        return {"status": "index unavailable", "tools": [], "projects": [], "apps": []}
    words = _tokens(goal)
    phrase = lambda value: ' ' + ' '.join(re.findall(r'[a-z0-9]+', str(value).casefold())) + ' '
    goal_phrase = phrase(goal)
    def ranked(rows, fields, limit, app=False):
        scored = []
        for row in rows:
            label = str(row.get("name", ""))
            candidates = words
            if app:
                candidates = words - {'find', 'file', 'files', 'folder', 'folders', 'drive', 'open', 'launch', 'start', 'close',
                                      'search', 'research', 'compare', 'tools', 'tool', 'script', 'scripts', 'code', 'create',
                                      'read', 'write', 'debug', 'video', 'videos', 'first', 'play', 'install', 'automation', 'discover'}
            exact = bool(label and phrase(label) in goal_phrase)
            score = (8 if exact else 0) + len(candidates & _tokens(" ".join(str(row.get(field, "")) for field in fields)))
            if score:
                scored.append((score, label.casefold(), row))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [row for _, _, row in scored[:limit]]
    # Saved descriptions are editable reference; live registry metadata is authoritative.
    live_tools = {row["name"]: row for row in tool_entries()}
    tools = [{**live_tools[row["name"]]}
             for row in ranked(data.get("tools", []), ("name", "context"), max_tools)
             if row["name"] in live_tools]
    projects = [row for row in ranked(data.get("projects", []), ("name", "summary"), max_projects)
                if isinstance(row.get("path"), str) and Path(row["path"]).is_dir()]
    if not projects and re.search(r"\b(?:list|show|how many|which|what)\b.*\bprojects?\b", goal, re.I):
        projects = [row for row in data.get("projects", []) if isinstance(row.get("path"), str)
                    and Path(row["path"]).is_dir()][:max_projects]
    apps = []
    for row in ranked(data.get("apps", []), ("name",), max_apps, app=True):
        locations = row.get("locations", {})
        if not isinstance(locations, dict):
            continue
        valid = {key: path for key, path in locations.items() if isinstance(path, str)
                 and (key == "shell_id" or (key in {"executable", "shortcut"} and Path(path).is_file())
                      or (key == "install_location" and Path(path).is_dir()))}
        apps.append({**row, "locations": valid, "status": row.get("status") if valid else "saved path missing or unavailable"})
    operations = {name: description for name, description in DIRECT_OPERATIONS.items()
                  if _tokens(goal) & _tokens(name + " " + description)}
    saved_scan = data.get("scan", {})
    saved_scan = saved_scan if isinstance(saved_scan, dict) else {}
    coverage = {key: value for key, value in saved_scan.items()
                if key in {"directories_scanned", "complete_within_bounds", "max_directories", "max_seconds",
                           "max_depth", "inaccessible", "depth_limited_directories", "cancelled"}
                and isinstance(value, (int, float, bool))}
    result = {"index_at_utc": str(data.get("generated_at_utc", "unknown"))[:80], "tools": tools, "operations": dict(list(operations.items())[:5]),
            "projects": projects, "apps": apps,
            "inventory_counts": {key: len(data.get(key, [])) for key in ("tools", "projects", "apps")},
            "coverage": coverage,
            "limits": "Historical catalogue only; verify paths and tool availability before acting. Index is bounded by configured scan roots and limits."}
    while len(json.dumps(result, ensure_ascii=False)) > 5000:
        key = next((key for key in ("tools", "operations", "apps", "projects") if result[key]), None)
        if key is None:
            break
        if isinstance(result[key], dict):
            result[key].pop(next(reversed(result[key])))
        else:
            result[key].pop()
    return result


def project_matches(data, name):
    """Only exact normalized names qualify; never silently pick an ambiguous project."""
    normalize = lambda value: re.sub(r"[^a-z0-9]", "", str(value).casefold())
    target = normalize(name)
    return sorted({row["path"] for row in (data or {}).get("projects", [])
                   if target and normalize(row.get("name", "")) == target
                   and isinstance(row.get("path"), str) and Path(row["path"]).is_dir()})


def catalogue_answer(data, question):
    """Answer narrowly scoped catalogue facts from saved data without model inference."""
    text = question.strip().rstrip("?.! ")
    description = re.fullmatch(r"(?:what does|tell me about|what is) (?:my |the )?(.+?) project(?: do| about)?(?: and where is its folder)?", text, re.I)
    location = re.fullmatch(r"where is (?:my |the )?(?:project )?(.+?) project(?: folder)?(?: located)?", text, re.I)
    match = description or location
    if not data or match is None:
        return None
    paths = project_matches(data, match[1])
    rows = [row for row in data.get("projects", []) if row.get("path") in paths]
    if not rows:
        return None
    if len(rows) > 1:
        return "I found multiple projects with that name: " + "; ".join(paths[:5]) + ". Name the folder you mean."
    row = rows[0]
    answer = f"{row['name']} is at {row['path']}."
    if description:
        stamp = str(data.get("generated_at_utc", "unknown date"))[:10]
        answer += f" Its saved summary ({row.get('summary_source', 'catalogue')}, {stamp}): {_safe_line(row.get('summary', 'No summary available.'))}"
    return answer


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent.parent
    config = json.loads((base / "config.json").read_text(encoding="utf-8"))
    raw = config.get("memory", {}).get("vault", ".jarvis-runtime/obsidian-vault")
    vault = Path(raw) if Path(raw).is_absolute() else base / raw
    result = build_index(config)
    if not args.dry_run:
        write_index(vault, result)
    print(json.dumps({"vault": str(vault), "projects": len(result["projects"]),
                      "apps": len(result["apps"]), "tools": len(result["tools"]),
                      "scan": result["scan"]}, ensure_ascii=False))
