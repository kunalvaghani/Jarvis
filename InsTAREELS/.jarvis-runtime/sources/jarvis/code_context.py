"""Read-only project discovery inspired by agenticSeek's file-finder workflow.

Independently implemented for Jarvis; no upstream source is imported or executed.
"""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re
import uuid

CONTEXT_BUDGET = 6000
_CONFIG = {"readme.md", "pyproject.toml", "package.json", "go.mod", "cargo.toml"}


def related_context(project, files, goal, focus=(), budget=CONTEXT_BUDGET):
    """Find useful source snippets inside the selected project, with bounded I/O."""
    project = Path(project).resolve()
    focus = set(focus)
    directories = {str(Path(name).parent) for name in focus}
    imported = set()
    for name in focus:
        path = project / name
        try:
            if path.suffix != ".py" or path.is_symlink() or not path.resolve().is_relative_to(project):
                continue
            with path.open("rb") as source:
                text = source.read(14001)
            if len(text) > 14000:
                continue
            tree = ast.parse(text.decode("utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.replace(".", "/") for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    prefix = list(Path(name).parent.parts)
                    if node.level:
                        prefix = prefix[:max(0, len(prefix)-node.level+1)]
                    else:
                        prefix = []
                    module = "/".join([*prefix, (node.module or "").replace(".", "/")]).strip("/")
                    imported.add(module)
                    imported.update(module + "/" + alias.name for alias in node.names)
        except (OSError, UnicodeError, SyntaxError):
            continue
    words = set(re.findall(r"[a-z][a-z0-9_]{2,}", goal.casefold())) - {
        "the", "and", "add", "create", "modify", "file", "code", "project", "folder", "update"}
    candidates = []
    for name in files[:160]:
        path = project / name
        if name in focus or any(part.startswith(".") for part in Path(name).parts) or re.search(r"(?:secret|credential|password|private_key|access_token)", path.stem, re.I):
            continue
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(project) or not path.is_file() or path.stat().st_size > 14000:
                continue
            with path.open("rb") as source:
                raw = source.read(14001)
            if len(raw) > 14000:
                continue
            text = raw.decode("utf-8")
        except (OSError, UnicodeError):
            continue
        score = (5 * len(words & set(re.findall(r"[a-z][a-z0-9_]+", name.casefold())))
                 + 2 * len(words & set(re.findall(r"[a-z][a-z0-9_]+", text.casefold())))
                 + (2 if str(path.parent.relative_to(project)) in directories else 0)
                 + (1 if path.name.casefold() in _CONFIG else 0)
                 + (12 if Path(name).with_suffix("").as_posix() in imported else 0))
        if score:
            candidates.append((score, name, text))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    result = {}
    for _, name, text in candidates[:4]:
        remaining = budget - sum(len(value) for value in result.values())
        if remaining < 100:
            break
        marker = "\n[Reference excerpt truncated]"
        limit = min(2500, remaining)
        result[name] = text[:limit-len(marker)] + marker if len(text) > limit else text
    return result


def bounded_references(context, target, prepared=(), budget=CONTEXT_BUDGET):
    """Prioritize freshly generated sibling files so subsequent edits agree."""
    ordered = {**dict(prepared), **{key: value for key, value in context.items() if key not in dict(prepared)}}
    result, used = {}, 0
    for name, text in ordered.items():
        if name == target or not text:
            continue
        limit = min(2500, budget-used)
        if limit <= 0:
            break
        result[name] = text[:limit]
        used += len(result[name])
    return result


def save_change_review(project, prepared, runtime_base):
    """Preserve originals and a diff before commits; never restore or replay edits."""
    directory = Path(runtime_base) / ".jarvis-runtime" / "coding" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    changes, diffs = [], []
    for path, original, content in prepared:
        relative = path.relative_to(project).as_posix()
        if original is not None:
            backup = directory / "originals" / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb") as output:
                output.write(original)
        diffs.extend(difflib.unified_diff((original.decode("utf-8") if original is not None else "").splitlines(keepends=True),
                                        content.splitlines(keepends=True), fromfile="before/"+relative, tofile="after/"+relative))
        changes.append({"path": relative,
                        "before_sha256": hashlib.sha256(original).hexdigest() if original is not None else None,
                        "after_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
    (directory / "changes.diff").write_text("".join(diffs), encoding="utf-8")
    (directory / "review.json").write_text(json.dumps({"project": str(project), "status": "prepared",
                                                       "files": changes}, indent=2) + "\n", encoding="utf-8")
    return directory


def apply_replacements(current, replacements):
    """Materialize exact edits in memory; reject ambiguous or stale matches."""
    if not current or not isinstance(replacements, list) or not 1 <= len(replacements) <= 12:
        raise ValueError("Targeted edits need an existing file and one to twelve replacements.")
    content = current
    for edit in replacements:
        if (not isinstance(edit, dict) or set(edit) != {"find", "replace"}
                or not isinstance(edit["find"], str) or not edit["find"]
                or not isinstance(edit["replace"], str)
                or len(edit["find"]) > 20000 or len(edit["replace"]) > 20000):
            raise ValueError("A targeted edit needs exact nonempty find text and replacement text.")
        matches = content.count(edit["find"])
        if matches != 1:
            raise ValueError(f"Targeted edit matched {matches} locations; use unique exact text from the current file.")
        content = content.replace(edit["find"], edit["replace"], 1)
        if len(content) > 20000:
            raise ValueError("Targeted edits produced oversized file content.")
    return content


def check_python_interfaces(current, content, goal):
    """Do not silently discard top-level functions/classes during a small edit."""
    try:
        before, after = ast.parse(current), ast.parse(content)
    except SyntaxError:
        return  # Broken input can be repaired; output syntax is checked separately.
    names = lambda tree: {node.name for node in tree.body
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    missing = names(before) - names(after)
    if not missing:
        return
    def affirmative(pattern):
        for match in re.finditer(pattern, goal, re.I):
            prefix=re.split(r'[.;\n]',goal[:match.start()])[-1]
            if not re.search(r"\b(?:not|never|avoid|without)\b|\bdon['’]t\b",prefix,re.I):
                return True
        return False
    if affirmative(r"\b(?:rewrite|replace entire|remove most)\b"):
        return
    missing={name for name in missing if not affirmative(
        r"\b(?:remove|delete|rename)\s+(?:(?:the|existing|old|function|class|method)\s+)*[\"'`]?"
        +re.escape(name)+r"\b")}
    if missing:
        raise ValueError("Generated edit removed existing functions/classes: " + ", ".join(sorted(missing)) + ". Preserve unrelated interfaces.")
