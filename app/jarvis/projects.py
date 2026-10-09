"""Find actual project directories and remember projects opened by Jarvis."""
from .paths import linked, state_file
import json
import os
from pathlib import Path
import time

from .names import rank

MARKERS = {".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "CMakeLists.txt", "pom.xml", "build.gradle", "build.gradle.kts"}
SKIP = {".git", ".venv", ".venv-brain", ".venv-training", "venv", "node_modules", "__pycache__", "build", "dist", ".next", "target", "models", "cache", ".cache", "artifacts", ".jarvis-runtime"}
SYSTEM = {"program files", "windowsapps", "xboxgames", "steamLibrary", "epic games", "ollama-models", "ollamamodels", "temp", "tmp", ".pnpm-store"}


def has_project_marker(root):
    root = Path(root)
    if any((root / marker).exists() for marker in MARKERS):
        return True
    try:
        return any(entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in {'.csproj', '.sln', '.uproject'}
                   for entry in list(os.scandir(root))[:200])
    except OSError:
        return False


def project_paths(roots):
    """Inspect at most two directory levels; never search arbitrary installed assets."""
    found = {}
    for raw in roots:
        root = Path(raw)
        if not root.is_dir():
            continue
        if root.parent != root:
            found[str(root.resolve()).casefold()] = root.resolve()
        try:
            children = [p for p in root.iterdir() if not linked(p) and p.is_dir() and p.name.casefold() not in {x.casefold() for x in SYSTEM | SKIP}]
        except OSError:
            continue
        for child in children:
            try:
                if root.drive.upper() == "D:" and root.parent == root and child.name.casefold() == "phython project":
                    continue  # The more specific root scans this once.
                container = root.parent != root and not has_project_marker(root)
                if container or root.name.casefold() == "phython project" or has_project_marker(child):
                    found[str(child.resolve()).casefold()] = child.resolve()
            except OSError:
                continue
    return list(found.values())


def activity(path):
    """A bounded sample of source/document mtimes, excluding generated dependencies."""
    latest = path.stat().st_mtime
    seen = 0
    todo = [(path, 0)]
    while todo and seen < 300:
        folder, depth = todo.pop(0)
        try:
            entries = list(os.scandir(folder))[:200]
        except OSError:
            continue
        for entry in entries:
            seen += 1
            if seen > 300:
                break
            if entry.name.casefold() in SKIP or entry.name.startswith("."):
                continue
            try:
                if linked(entry.path):
                    continue
                if entry.is_file(follow_symlinks=False) and not entry.name.endswith((".log", ".sqlite3", ".db", ".pyc")):
                    latest = max(latest, entry.stat(follow_symlinks=False).st_mtime)
                elif depth < 1 and entry.is_dir(follow_symlinks=False):
                    todo.append((Path(entry.path), depth + 1))
            except OSError:
                pass
    return latest


class Projects:
    def __init__(self, base, roots):
        self.memory_path = state_file("project_memory.json", base)
        self.roots = roots
        self.pending = None

    def _memory(self):
        try:
            data = json.loads(self.memory_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def list(self, limit=10):
        memory = self._memory()
        roots = {str(Path(root).resolve()).casefold() for root in self.roots}
        paths = [p for p in project_paths(self.roots) if str(p).casefold() not in roots]
        paths.sort(key=lambda p: max(activity(p), memory.get(str(p), 0)), reverse=True)
        return paths[:limit]

    def last(self):
        roots = {str(Path(root).resolve()).casefold() for root in self.roots}
        paths = [p for p in project_paths(self.roots) if str(p).casefold() not in roots]
        if not paths:
            raise ValueError("No project folders were found in the configured roots.")
        memory = self._memory()
        remembered = [p for p in paths if str(p) in memory]
        if remembered:
            return max(remembered, key=lambda p: memory[str(p)]), True
        return max(paths, key=activity), False

    def resolve(self, spoken):
        paths = project_paths(self.roots)
        matched = rank(spoken, [p.name for p in paths])
        choices = [p for p in paths if p.name in matched]
        if len(choices) == 1:
            return choices[0]
        if len(choices) > 1:
            raise ValueError("Several projects match that name: " + "; ".join(str(p) for p in choices[:8]))
        raise ValueError(f"No project folder named '{spoken}' in the configured project roots.")

    def remember(self, path):
        data = self._memory()
        data[str(path)] = time.time()
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.memory_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(self.memory_path)
