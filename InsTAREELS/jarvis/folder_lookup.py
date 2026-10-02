"""Drive-scoped folder discovery and local preferences for opening folders."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import threading

from .names import common, rank_spelling


def folder_request(text, *, strip_kind=True):
    """Remove spoken qualifiers, preserving a literal absolute path."""
    text = text.strip()
    if Path(text).is_absolute():
        return text, None
    drive = re.search(r"(?:\s+(?:(?:in|on|from|under|at)\s+)?(?:the\s+)?|^)([a-z])(?:\s*:\s*|\s+)(?:drive|disk)(?:\s+folder)?$", text, re.I)
    scope = drive[1].upper() if drive else None
    if drive:
        text = text[:drive.start()].strip()
    if strip_kind:
        text = re.sub(r"^(?:the |my )?(?:folder|directory)\s+|\s+(?:folder|directory)$", "", text, flags=re.I).strip()
    return common(text), scope


class FolderLookup:
    def __init__(self, catalog):
        self.catalog = catalog
        self.base = catalog.base
        self.history_path = self.base / '.jarvis-runtime/folder-usage.json'
        self.lock = threading.RLock()
        self.history = {}
        self.error = None
        try:
            if self.history_path.exists():
                data = json.loads(self.history_path.read_text(encoding='utf-8'))
                if data.get('version') != 1 or not isinstance(data.get('folders'), dict):
                    raise ValueError('Invalid folder usage index; preserve it for review.')
                for path, row in data['folders'].items():
                    if (not Path(path).is_absolute() or not isinstance(row, dict)
                            or not isinstance(row.get('count'), int) or row['count'] < 1
                            or not isinstance(row.get('last_opened'), str)):
                        raise ValueError('Invalid folder usage entry; preserve it for review.')
                self.history = data['folders']
        except (OSError, ValueError, TypeError) as exc:
            self.error = str(exc)

    @staticmethod
    def scoped(path, drive):
        return not drive or Path(path).drive.casefold() == (drive + ':').casefold()

    def roots(self, drive):
        if drive:
            return [Path(drive + ':\\')]
        roots = {Path(p).anchor for p in self.catalog.config.get('project_roots', []) if Path(p).is_absolute()}
        roots.update(Path(p).anchor for p in self.catalog.config.get('folders', {}).values() if Path(p).is_absolute())
        return [Path(p) for p in sorted(roots)]

    def resolve(self, original, *, prefer_usage=False):
        from .catalog import key
        query, drive = folder_request(original)
        raw, _ = folder_request(original, strip_kind=False)
        if Path(query).is_absolute():
            return self.catalog._exists(str(Path(query).resolve()), 'folder')
        if not query:
            if drive:
                return self.catalog._exists(drive + ':\\', 'folder')
            raise ValueError('Name a folder or a drive.')
        for alias, path in self.catalog.config.get('folders', {}).items():
            path = str((self.base / path).resolve())
            if key(alias) in {key(query), key(raw)} and self.scoped(path, drive):
                return self.catalog._exists(path, 'folder')
        # Read just drive-root entries; newly created top-level folders need no full scan.
        live = []
        for root in self.roots(drive):
            try:
                live.extend(str(p) for p in root.iterdir() if p.is_dir())
            except OSError:
                continue
        exact_root = [p for p in live if key(Path(p).name) == key(raw)]
        if not exact_root:
            exact_root = [p for p in live if key(Path(p).name) == key(query)]
        if drive and exact_root:
            return self.choose(exact_root, original, drive, prefer_usage)
        source = self.base / self.catalog.config.get('file_catalog', 'file_catalog.json')
        database = source.with_suffix('.sqlite3')
        candidates = set(live)
        candidates.update(p for p in self.history if self.scoped(p, drive))
        if database.is_file():
            with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
                stat = source.stat()
                if connection.execute('SELECT size,mtime FROM metadata').fetchone() != (stat.st_size, stat.st_mtime_ns):
                    # A live root match still works while the deep index needs rebuilding.
                    labels = rank_spelling(query, [Path(p).name for p in live])
                    if labels:
                        return self.choose([p for p in live if Path(p).name in labels], original, drive, prefer_usage)
                    raise ValueError('Catalog index is outdated. Run build_catalog_index.py or refresh the PC catalog.')
                scope = " AND substr(path,1,3)=? COLLATE NOCASE" if drive else ''
                args = [drive + ':\\'] if drive else []
                rows = connection.execute("SELECT path FROM paths WHERE kind='folder' AND name=?" + scope, [key(raw), *args]).fetchall()
                if not rows:
                    rows = connection.execute("SELECT path FROM paths WHERE kind='folder' AND name=?" + scope, [key(query), *args]).fetchall()
                if not rows:
                    terms = key(query).split()
                    clauses = ' AND '.join("name LIKE ? ESCAPE '\\'" for _ in terms)
                    patterns = ['%' + t.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%' for t in terms]
                    rows = connection.execute("SELECT path FROM paths WHERE kind='folder' AND " + clauses + scope + ' LIMIT 2001', [*patterns, *args]).fetchall()
                    if len(rows) > 2000:
                        raise ValueError('Too many folders match. Add the drive or parent folder name.')
                if not rows and len(key(query)) >= 4:
                    # Indexed prefix range supplies typo candidates; do not require the typo as a substring.
                    prefix = key(query)[:2]
                    upper = prefix[:-1] + chr(ord(prefix[-1]) + 1)
                    rows = connection.execute("SELECT path FROM paths WHERE kind='folder' AND name>=? AND name<? AND length(name) BETWEEN ? AND ?" + scope + ' LIMIT 2001', [prefix, upper, max(1, len(key(query))-3), len(key(query))+3, *args]).fetchall()
                    if len(rows) > 2000:
                        raise ValueError('Too many similar folder names. Add a parent folder or use the full path.')
                # Parent/name references still use the existing exact parent index semantics.
                for split in range(1, len(key(query).split())):
                    parts = key(query).split()
                    rows.extend(connection.execute("SELECT path FROM paths WHERE kind='folder' AND parent=? AND name=?" + scope,
                        [' '.join(parts[:split]), ' '.join(parts[split:]), *args]).fetchall())
                candidates.update(row[0] for row in rows)
        elif source.is_file():
            data = json.loads(source.read_text(encoding='utf-8'))
            candidates.update(data.get('folders', []))
        candidates = [p for p in candidates if self.scoped(p, drive)]
        index = {}
        for path in candidates:
            item = Path(path)
            for label in (item.name, str(Path(item.parent.name) / item.name)):
                index.setdefault(label, set()).add(path)
        labels = [label for label in index if common(label) == raw]
        if not labels:
            labels = rank_spelling(query, index)
        matches = {p for label in labels for p in index[label]}
        return self.choose(matches, original, drive, prefer_usage)

    def choose(self, matches, name, drive=None, prefer_usage=False):
        from .catalog import AmbiguousName
        matches = sorted({str(Path(p).resolve()) for p in matches if self.scoped(p, drive) and Path(p).is_dir()})
        if not matches:
            raise ValueError(f"No existing folder matching '{name}'. Add a parent folder or refresh scan_pc.ps1.")
        if len(matches) == 1:
            return matches[0]
        # Usage chooses among equally relevant names, never overrides drive/name constraints.
        with self.lock:
            usage = sorted(matches, key=lambda p: (self.history.get(p, {}).get('count', 0), self.history.get(p, {}).get('last_opened', '')), reverse=True)
            if self.history.get(usage[0], {}).get('count', 0) > self.history.get(usage[1], {}).get('count', 0):
                if prefer_usage and len({Path(p).name.casefold() for p in matches}) == 1:
                    return usage[0]
        # Explicit drive requests favor the drive-root folder over library/dependency copies.
        top = [p for p in matches if Path(p).parent == Path(Path(p).anchor)] if drive else []
        if len(top) == 1:
            return top[0]
        raise AmbiguousName(name, usage)

    def record_open(self, path, query):
        """Track accepted Explorer launch requests; not independent UI verification."""
        from .skill_memory import atomic
        from .obsidian_memory import clean
        if self.error or not Path(path).is_dir():
            return
        with self.lock:
            path = str(Path(path).resolve())
            before = self.history.get(path, {})
            self.history[path] = {'count': before.get('count', 0) + 1,
                'last_opened': datetime.now(timezone.utc).isoformat(), 'last_query': clean(query, 200)}
            recent = sorted(self.history.items(), key=lambda pair: pair[1]['last_opened'], reverse=True)[:500]
            self.history = dict(recent)
            try:
                atomic(self.history_path, json.dumps({'version': 1, 'folders': self.history}, ensure_ascii=False, indent=2))
                memory = getattr(self.catalog, 'memory', None)
                if memory and memory.enabled and not memory.index_stop.is_set():
                    note = '# Jarvis Folder Usage\n\n[[Jarvis Brain]]\n\nAccepted folder-open requests; Explorer visibility is not independently verified. Only Jarvis opens are counted.\n\n'
                    for p, row in sorted(recent, key=lambda pair: pair[1]['count'], reverse=True):
                        note += f"- `{clean(p, 500)}` — {row['count']} opens; {row['last_opened']}; request: {row['last_query']}\n"
                    with memory.lock:
                        from .skill_memory import linked
                        if linked(memory.vault):
                            raise ValueError('Folder memory cannot follow linked vault paths.')
                        atomic(memory.vault / 'Jarvis Folder Usage.md', note)
                        brain = memory.vault / 'Jarvis Brain.md'
                        if linked(brain):
                            raise ValueError('Folder memory cannot follow a linked brain note.')
                        text = brain.read_text(encoding='utf-8') if brain.exists() else '# Jarvis Brain\n'
                        if '[[Jarvis Folder Usage]]' not in text:
                            atomic(brain, text + '\n[[Jarvis Folder Usage]]\n')
            except (OSError, ValueError) as exc:
                self.error = 'Folder usage save: ' + str(exc)
                memory = getattr(self.catalog, 'memory', None)
                if memory:
                    memory.error = self.error
