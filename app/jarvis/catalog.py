"""Exact, ambiguity-aware name lookup for the local path catalog."""
from collections import defaultdict
import json
from pathlib import Path
import re
import sqlite3
from .names import common, rank


class AmbiguousName(ValueError):
    def __init__(self, name, matches):
        self.matches = matches
        super().__init__(f"{len(matches)} matches for '{name}': " + "; ".join(matches[:10]))


def key(value):
    value = re.sub(r"\s+dot\s+", ".", value.lower())
    return " ".join(re.sub(r"[^\w]+", " ", value.replace("_", " ")).split())


class Catalog:
    def __init__(self, config, base):
        self.config, self.base = config, Path(base)
        self.indexes = {}
        from .folder_lookup import FolderLookup
        self.folders = FolderLookup(self)

    def resolve(self, name, kind, *, prefer_usage=False):
        if kind == 'folder':
            return self.folders.resolve(name, prefer_usage=prefer_usage)
        # A user-supplied full path does not depend on a potentially stale index.
        if Path(name).is_absolute():
            return self._exists(str(Path(name).resolve()), kind)
        name = common(name) if not any(c in name for c in ("/", "\\", ":")) else name
        explicit = self.config.get("files" if kind == "file" else "folders", {})
        for alias, path in explicit.items():
            if key(alias) == key(name):
                return self._exists(str((self.base / path).resolve()), kind)
        catalog = self.base / self.config.get("file_catalog", ".jarvis-runtime/state/file_catalog.json")
        database = catalog.with_suffix(".sqlite3")
        if database.is_file():
            with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
                stat = catalog.stat()
                recorded = connection.execute("SELECT size,mtime FROM metadata").fetchone()
                if recorded != (stat.st_size, stat.st_mtime_ns):
                    raise ValueError("Catalog index is outdated. Run scripts/catalog/build_catalog_index.py or refresh the PC catalog.")
                full = connection.execute("SELECT path FROM paths WHERE kind=? AND path=? COLLATE NOCASE", (kind, name)).fetchall()
                if full:
                    matches = [row[0] for row in full]
                else:
                    query = key(name)
                    rows = connection.execute("SELECT path FROM paths WHERE kind=? AND name=? UNION SELECT path FROM paths WHERE kind=? AND stem=?", (kind, query, kind, query)).fetchall()
                    # Support 'parent folder filename' without indexing every full path.
                    if not rows:
                        words = query.split()
                        for split in range(1, len(words)):
                            rows.extend(connection.execute("SELECT path FROM paths WHERE kind=? AND parent=? AND (name=? OR stem=?)",
                                (kind, " ".join(words[:split]), " ".join(words[split:]), " ".join(words[split:]))).fetchall())
                    if not rows:
                        terms = [term for term in query.split() if term not in {"my", "the"}]
                        if terms:
                            # Bound both work and candidate count for the million-path catalog.
                            clauses = " AND ".join("replace(name,' ','') LIKE ? ESCAPE '\\'" for _ in terms)
                            patterns = ["%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%" for term in terms]
                            candidates = connection.execute("SELECT path,name,stem FROM paths WHERE kind=? AND " + clauses + " LIMIT 201", [kind, *patterns]).fetchall()
                            if len(candidates) > 200:
                                raise ValueError("Too many files match that short name. Add another word or the parent folder.")
                            labels = rank(query, [label for row in candidates for label in row[1:]])
                            rows = [(path,) for path, label, stem in candidates if label in labels or stem in labels]
                    matches = list({row[0] for row in rows})
            return self._choose(matches, name, kind)
        if kind not in self.indexes:
            catalog = self.base / self.config.get("file_catalog", ".jarvis-runtime/state/file_catalog.json")
            if not catalog.is_file():
                raise ValueError("No file catalog yet. Run scan_pc.ps1.")
            data = json.loads(catalog.read_text(encoding="utf-8"))
            index = defaultdict(set)
            for path in data["files" if kind == "file" else "folders"]:
                item = Path(path)
                for label in {str(item), item.name, item.stem, str(Path(item.parent.name) / item.name)}:
                    index[key(label)].add(path)
            self.indexes[kind] = index
        found = self.indexes[kind].get(key(name), [])
        if not found:
            labels = rank(name, self.indexes[kind])
            found = {path for label in labels for path in self.indexes[kind][label]}
        return self._choose(found, name, kind)

    def _choose(self, matches, name, kind):
        matches = sorted(matches)
        matches = [path for path in matches if (Path(path).is_file() if kind == "file" else Path(path).is_dir())]
        if not matches:
            raise ValueError(f"No indexed {kind} named '{name}'. Run scripts/catalog/scan_pc.ps1 to refresh the catalog.")
        if len(matches) > 1:
            raise AmbiguousName(name, matches)
        return matches[0]

    @staticmethod
    def _exists(path, kind):
        if not (Path(path).is_file() if kind == "file" else Path(path).is_dir()):
            raise ValueError(f"The configured {kind} no longer exists: {path}")
        return path
