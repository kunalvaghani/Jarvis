"""VerifiedCodeMemory: a versioned local library of reusable code with provenance, license and evidence.

States only move forward on evidence (DISCOVERED -> INSPECTED -> LICENSE_CHECKED -> COMPATIBLE ->
SANDBOX_TESTED -> PROJECT_VERIFIED -> REUSABLE); STALE and REJECTED are reachable from any state.
Nothing becomes trusted because it was downloaded. Source text is stored only when its license
permits copying or it is the user's own local code; otherwise only metadata and links are kept.
Project-scoped items are never returned for another project unless the user names that project.
Structured authority is this SQLite store; an Obsidian note per reusable item feeds the existing
vault/OpenViking retrieval and is never read back as authority.
"""
import hashlib
import json
import math
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

STATES = ('DISCOVERED', 'INSPECTED', 'LICENSE_CHECKED', 'COMPATIBLE', 'SANDBOX_TESTED', 'PROJECT_VERIFIED', 'REUSABLE',
          'STALE', 'REJECTED')
ORDER = {state: index for index, state in enumerate(STATES[:7])}
TRUSTED = {'PROJECT_VERIFIED', 'REUSABLE'}
# Copying source requires one of these and a license file; anything else is metadata-only.
PERMISSIVE = {'MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'ISC', '0BSD', 'Zlib', 'Unlicense', 'CC0-1.0'}
EVIDENCE_WEIGHT = {'DISCOVERED': .1, 'INSPECTED': .25, 'LICENSE_CHECKED': .35, 'COMPATIBLE': .45, 'SANDBOX_TESTED': .65,
                   'PROJECT_VERIFIED': .85, 'REUSABLE': 1., 'STALE': .05, 'REJECTED': 0.}


def tokens(text):
    raw = re.findall(r'[A-Za-z][a-z0-9]+|[A-Z]+(?![a-z])|\d+', str(text or ''))
    return [t.casefold() for t in raw if len(t) > 1]


def normalized_hash(source):
    """Duplicate detection ignores whitespace and line-ending differences."""
    return hashlib.sha256(re.sub(r'\s+', ' ', str(source)).strip().encode('utf-8')).hexdigest()


def scope_for(project):
    return 'project:' + hashlib.sha256(str(Path(project).resolve()).casefold().encode('utf-8')).hexdigest()[:16]


class VerifiedCodeMemory:
    def __init__(self, root, clock=time.time, vault=None):
        self.root, self.clock, self.vault = Path(root), clock, Path(vault) if vault else None
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.root / 'library.sqlite3', check_same_thread=False, timeout=2)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, name TEXT NOT NULL, scope TEXT NOT NULL, version INTEGER NOT NULL,
                state TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, source_hash TEXT, created REAL, updated REAL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history (seq INTEGER PRIMARY KEY, item TEXT NOT NULL, at REAL NOT NULL, state TEXT NOT NULL,
                detail TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS item_name ON items(name, scope);
            CREATE INDEX IF NOT EXISTS item_hash ON items(source_hash);
        ''')
        self.db.commit()

    @contextmanager
    def transaction(self):
        with self.lock:
            nested = self.db.in_transaction
            try:
                yield self.db
                if not nested:
                    self.db.commit()
            except BaseException:
                if not nested:
                    self.db.rollback()
                raise

    # --- writing ------------------------------------------------------------------------------------------------
    def add(self, *, name, description, category, language, framework='', framework_version='', dependencies=None,
            origin, source=None, license='', license_files=(), repository='', commit='', scope='global', interface='',
            example='', limitations='', tests=None, symbols=None, security=None, state='DISCOVERED'):
        """Register a candidate; an identical source in the same scope returns the existing item (deduplicated)."""
        from .cloud_policy import SECRET
        if state not in STATES or not name or not origin:
            raise ValueError('Code memory needs a name, origin and a valid state')
        copy_allowed = origin.startswith('local:') or (license in PERMISSIVE and bool(license_files))
        if source is not None and SECRET.search(source):
            raise ValueError('Source contains a credential-like value; it is never stored in the code library')
        stored_source = source if copy_allowed else None
        digest = normalized_hash(source) if source is not None else None
        with self.transaction() as db:
            if digest:
                same = db.execute('SELECT id FROM items WHERE source_hash=? AND scope=?', (digest, scope)).fetchone()
                if same:
                    self._event(same[0], 'DEDUPLICATED', f'Identical source from {origin}')
                    return self.get(same[0])
            previous = db.execute('SELECT version FROM items WHERE name=? AND scope=? ORDER BY version DESC LIMIT 1',
                                  (name, scope)).fetchone()
            version = (previous[0] + 1) if previous else 1
            identity, now = uuid.uuid4().hex, self.clock()
            data = {'id': identity, 'name': name[:120], 'description': str(description)[:600], 'category': category,
                    'language': language, 'framework': framework, 'framework_version': framework_version,
                    'dependencies': dict(dependencies or {}), 'origin': origin, 'repository': repository, 'commit': commit,
                    'license': license or 'unknown', 'license_files': list(license_files), 'copy_allowed': copy_allowed,
                    'source_stored': stored_source is not None, 'scope': scope, 'version': version,
                    'interface': str(interface)[:1500], 'example': str(example)[:1500], 'limitations': str(limitations)[:600],
                    'tests': tests or {}, 'symbols': list(symbols or [])[:60], 'security': security or {},
                    'used_in': [], 'failures': [], 'modifications': [], 'last_verified': None, 'performance': {}}
            if stored_source is not None:
                folder = self.root / 'items' / identity
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'source.txt').write_text(stored_source, encoding='utf-8')
            db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (identity, data['name'], scope, version, state, 1, digest, now, now, json.dumps(data)))
            self._event(identity, state, f'Registered from {origin}' + ('' if copy_allowed else ' (metadata only: copying not permitted)'))
        return self.get(identity)

    def _event(self, identity, state, detail):
        self.db.execute('INSERT INTO history(item,at,state,detail) VALUES(?,?,?,?)', (identity, self.clock(), state, str(detail)[:2000]))

    def transition(self, identity, state, evidence, **updates):
        """Forward-only promotion on evidence; STALE/REJECTED are always allowed."""
        if state not in STATES:
            raise ValueError('Unknown code memory state')
        with self.transaction() as db:
            item = self.get(identity)
            if item is None:
                raise ValueError('Unknown code memory item')
            current = item['state']
            if state in ORDER and current in ORDER and ORDER[state] < ORDER[current]:
                raise ValueError(f'Cannot move {current} back to {state}; mark it STALE and re-verify instead')
            if current == 'REJECTED' and state != 'REJECTED':
                raise ValueError('A rejected item must be registered again from a fresh inspection')
            if state == 'REUSABLE' and current not in {'PROJECT_VERIFIED', 'STALE', 'REUSABLE'}:
                raise ValueError('Only project-verified code can become reusable')
            if state == 'REUSABLE' and current == 'STALE':
                raise ValueError('Stale code must be re-verified in a project first')
            data = {k: v for k, v in item.items() if k not in {'state', 'enabled', 'source'}}
            data.update(updates)
            if state in {'SANDBOX_TESTED', 'PROJECT_VERIFIED', 'REUSABLE'}:
                data['last_verified'] = self.clock()
            db.execute('UPDATE items SET state=?, updated=?, data=? WHERE id=?', (state, self.clock(), json.dumps(data, default=str), identity))
            self._event(identity, state, evidence)
        item = self.get(identity)
        if state == 'REUSABLE':
            self._note(item)
        return item

    def record_use(self, identity, project, ok, detail=''):
        with self.transaction() as db:
            item = self.get(identity)
            data = {k: v for k, v in item.items() if k not in {'state', 'enabled', 'source'}}
            key = 'used_in' if ok else 'failures'
            data[key] = (data[key] + [{'project': str(project), 'at': self.clock(), 'detail': str(detail)[:300]}])[-30:]
            db.execute('UPDATE items SET updated=?, data=? WHERE id=?', (self.clock(), json.dumps(data, default=str), identity))
            self._event(identity, item['state'], ('Used successfully in ' if ok else 'Failed in ') + str(project))
        return self.get(identity)

    def mark_stale(self, identity, reason):
        return self.transition(identity, 'STALE', reason)

    def set_enabled(self, identity, enabled):
        with self.transaction() as db:
            db.execute('UPDATE items SET enabled=? WHERE id=?', (1 if enabled else 0, identity))
            self._event(identity, self.get(identity)['state'], 'Enabled by user' if enabled else 'Disabled by user')

    def remove(self, identity):
        """User-requested removal: the record and any stored copy are deleted; history is kept."""
        with self.transaction() as db:
            db.execute('DELETE FROM items WHERE id=?', (identity,))
            self._event(identity, 'REJECTED', 'Removed by user')
        folder = self.root / 'items' / identity
        source = folder / 'source.txt'
        if source.is_file():
            source.unlink()
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()

    def refresh_staleness(self, project_dependencies, now=None):
        """Mark items stale when a project they target now uses an incompatible major framework/dependency version."""
        changed = []
        for item in self.all():
            if item['state'] in {'STALE', 'REJECTED'}:
                continue
            for name, wanted in item['dependencies'].items():
                have = project_dependencies.get(name)
                if have and major(have) is not None and major(wanted) is not None and major(have) != major(wanted):
                    self.mark_stale(item['id'], f'{name} {wanted} recorded; target uses {have}')
                    changed.append(item['id'])
                    break
        return changed

    # --- reading ------------------------------------------------------------------------------------------------
    def get(self, identity, source=True):
        with self.lock:
            row = self.db.execute('SELECT state, enabled, data FROM items WHERE id=?', (identity,)).fetchone()
        return self._decode(row, source) if row else None

    def _decode(self, row, source=True):
        data = json.loads(row['data'])
        path = self.root / 'items' / data['id'] / 'source.txt'
        text = path.read_text(encoding='utf-8') if source and data.get('source_stored') and path.is_file() else None
        return {**data, 'state': row['state'], 'enabled': bool(row['enabled']), 'source': text}

    def all(self, include_disabled=True, source=True):
        with self.lock:
            rows = self.db.execute('SELECT state, enabled, data FROM items ORDER BY updated DESC').fetchall()
        rows = [self._decode(r, source) for r in rows]
        return [r for r in rows if include_disabled or r['enabled']]

    def history(self, identity):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT at, state, detail FROM history WHERE item=? ORDER BY seq', (identity,))]

    def search(self, query, *, language=None, framework=None, project=None, scopes=None, trusted_only=False, limit=8):
        """Hybrid retrieval: exact name/symbol hits + BM25 over name, description, symbols and category + filters.

        Visible scopes: global plus the current project's own scope, plus any scope the user explicitly named.
        """
        visible = {'global'} | ({scope_for(project)} if project else set()) | set(scopes or ())
        # Metadata only while ranking; stored source is read for the returned results alone.
        items = [i for i in self.all(include_disabled=False, source=False) if i['scope'] in visible and i['state'] != 'REJECTED']
        if trusted_only:
            items = [i for i in items if i['state'] in TRUSTED]
        if language:
            items = [i for i in items if i['language'].casefold() == language.casefold()]
        if framework:
            items = [i for i in items if not i['framework'] or i['framework'].casefold() == framework.casefold()]
        wanted = tokens(query)
        if not wanted or not items:
            return []
        documents = {i['id']: tokens(' '.join([i['name'], i['description'], i['category'], ' '.join(i['symbols']), i['interface']]))
                     for i in items}
        average = sum(len(d) for d in documents.values()) / len(documents)
        frequency = {t: sum(1 for d in documents.values() if t in d) for t in set(wanted)}
        rows = []
        for item in items:
            doc = documents[item['id']]
            bm25 = 0.
            for term in set(wanted):
                tf = doc.count(term)
                if not tf:
                    continue
                idf = math.log(1 + (len(documents) - frequency[term] + .5) / (frequency[term] + .5))
                bm25 += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * len(doc) / max(1, average)))
            exact = 1. if any(term in tokens(item['name']) for term in wanted) and set(tokens(item['name'])) <= set(wanted) else 0.
            symbol = .5 if any(set(tokens(s)) and set(tokens(s)) <= set(wanted) for s in item['symbols']) else 0.
            coverage = len(set(wanted) & set(doc)) / len(set(wanted))
            if not bm25 and not exact and not symbol:
                continue
            reliability = EVIDENCE_WEIGHT[item['state']] * (1 if not item['failures'] else len(item['used_in']) / (len(item['used_in']) + len(item['failures'])))
            rows.append({'item': item, 'bm25': round(bm25, 4), 'coverage': round(coverage, 3), 'exact': exact, 'symbol': symbol,
                         'reliability': round(reliability, 3),
                         'score': round(.45 * min(1, bm25 / 4) + .25 * coverage + .15 * max(exact, symbol) + .15 * reliability, 4)})
        rows.sort(key=lambda r: -r['score'])
        return [{**row, 'item': self.get(row['item']['id'])} for row in rows[:limit]]

    def _note(self, item):
        """Vault note for semantic retrieval by the existing Obsidian/OpenViking stack (metadata, never secrets)."""
        if not self.vault:
            return
        try:
            folder = self.vault / 'Jarvis Code Library'
            folder.mkdir(parents=True, exist_ok=True)
            name = re.sub(r'[^A-Za-z0-9 _-]+', '', item['name'])[:80] or item['id']
            lines = [f"# {item['name']} (v{item['version']})", '', item['description'], '',
                     f"- Category: {item['category']} · {item['language']} {item['framework']} {item['framework_version']}".rstrip(),
                     f"- State: {item['state']} · License: {item['license']} · Origin: {item['origin']}",
                     f"- Dependencies: {', '.join(f'{k} {v}' for k, v in item['dependencies'].items()) or 'none'}",
                     f"- Interface: {item['interface'][:300]}", f"- Limitations: {item['limitations'] or 'none recorded'}"]
            (folder / f'{name}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        except OSError:
            pass  # The structured library remains authoritative.

    def stats(self):
        rows = self.all()
        counts = {}
        for row in rows:
            counts[row['state']] = counts.get(row['state'], 0) + 1
        return {'items': len(rows), 'states': counts, 'reusable': counts.get('REUSABLE', 0),
                'uses': sum(len(r['used_in']) for r in rows), 'failures': sum(len(r['failures']) for r in rows)}

    def close(self):
        with self.lock:
            self.db.close()


def major(version):
    found = re.search(r'(\d+)', str(version or ''))
    return int(found[1]) if found else None
