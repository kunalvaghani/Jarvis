"""PIRAE durable project state: projects, requirements and a versioned specification.

Operational state lives here (SQLite WAL), not in conversation history. Every requirement keeps its
category (explicit, inferred, recommendation, assumption, unknown, confirmed, rejected), its source
evidence and the spec version that introduced or changed it. Each change writes a new immutable
spec snapshot, so earlier versions stay available for explanation and rollback.
"""
import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

CATEGORIES = ('explicit', 'inferred', 'recommendation', 'assumption', 'unknown', 'confirmed', 'rejected')
KINDS = ('objective', 'functional', 'constraint', 'preference', 'priority', 'deliverable', 'reference', 'location')
STATUSES = ('active', 'removed', 'superseded', 'conflicting')


def slug(text, limit=48):
    value = re.sub(r'[^a-z0-9]+', '-', str(text).casefold()).strip('-')[:limit].strip('-')
    return value or 'project'


class ProjectStore:
    def __init__(self, path, clock=time.time):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=2)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS projects (number INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS requirements (project TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(project, id));
            CREATE TABLE IF NOT EXISTS spec_versions (project TEXT NOT NULL, version INTEGER NOT NULL, at REAL NOT NULL,
                change TEXT NOT NULL, snapshot TEXT NOT NULL, PRIMARY KEY(project, version));
            CREATE TABLE IF NOT EXISTS history (seq INTEGER PRIMARY KEY, project TEXT NOT NULL, at REAL NOT NULL,
                kind TEXT NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
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

    def setting(self, key, value=None, default=None):
        if value is None:
            with self.lock:
                row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default
        with self.transaction() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, json.dumps(value)))
        return value

    # --- projects -----------------------------------------------------------------------------------------------
    def create(self, name, objective, kind, subject):
        identity, now = uuid.uuid4().hex, self.clock()
        data = {'id': identity, 'name': name[:80], 'slug': slug(name), 'objective': objective[:2000], 'description': objective[:2000],
                'type': kind, 'subject': subject[:60], 'workspace': None, 'workspace_state': 'unknown', 'references': [],
                'architecture': None, 'questions': [], 'decisions': [], 'plan': {'tasks': {}, 'milestones': []},
                'verification': {}, 'version': 0, 'status': 'discovering', 'priority': 0, 'workflow': None,
                'created': now}
        with self.transaction() as db:
            db.execute('INSERT INTO projects(id,created,updated,data) VALUES(?,?,?,?)', (identity, now, now, json.dumps(data)))
            self.event(identity, 'created', {'name': name, 'objective': objective})
            self.setting('active_project', identity)
        return self.get(identity)

    def get(self, identity):
        with self.lock:
            row = self.db.execute('SELECT number, data FROM projects WHERE id=?', (identity,)).fetchone()
        return {**json.loads(row[1]), 'number': row[0]} if row else None

    def all(self):
        with self.lock:
            rows = self.db.execute('SELECT number, data FROM projects ORDER BY number').fetchall()
        return [{**json.loads(r[1]), 'number': r[0]} for r in rows]

    def save(self, project):
        project = {k: v for k, v in project.items() if k != 'number'}
        with self.transaction() as db:
            if not db.execute('UPDATE projects SET updated=?, data=? WHERE id=?',
                              (self.clock(), json.dumps(project, default=str), project['id'])).rowcount:
                raise ValueError('Unknown project')
        return self.get(project['id'])

    def active(self):
        identity = self.setting('active_project')
        return self.get(identity) if identity else None

    def event(self, project, kind, data):
        with self.transaction() as db:
            db.execute('INSERT INTO history(project,at,kind,data) VALUES(?,?,?,?)', (project, self.clock(), kind, json.dumps(data, default=str)[:20000]))

    def history(self, project, limit=50):
        with self.lock:
            rows = self.db.execute('SELECT at, kind, data FROM history WHERE project=? ORDER BY seq DESC LIMIT ?', (project, limit)).fetchall()
        return [{'at': r[0], 'kind': r[1], **json.loads(r[2])} for r in reversed(rows)]

    # --- requirements and versions --------------------------------------------------------------------------------
    def requirements(self, project, include_inactive=False):
        with self.lock:
            rows = [json.loads(r[0]) for r in self.db.execute('SELECT data FROM requirements WHERE project=?', (project,))]
        rows.sort(key=lambda r: (r['created_version'], r['created']))
        return rows if include_inactive else [r for r in rows if r['status'] == 'active']

    def requirement(self, project, identity):
        with self.lock:
            row = self.db.execute('SELECT data FROM requirements WHERE project=? AND id=?', (project, identity)).fetchone()
        return json.loads(row[0]) if row else None

    def add_requirement(self, project, text, *, kind, category, polarity='require', source='user', evidence='', change=None):
        if kind not in KINDS or category not in CATEGORIES or polarity not in {'require', 'prohibit'}:
            raise ValueError('Invalid requirement kind/category/polarity')
        with self.transaction() as db:
            version = self._bump(project)
            count = db.execute('SELECT count(*) FROM requirements WHERE project=?', (project,)).fetchone()[0]
            row = {'id': 'R' + str(count + 1), 'text': text[:500], 'kind': kind, 'category': category, 'polarity': polarity,
                   'status': 'active', 'created': self.clock(), 'created_version': version, 'updated_version': version,
                   'evidence': [{'source': source, 'text': str(evidence)[:300], 'version': version, 'at': self.clock()}]}
            db.execute('INSERT INTO requirements VALUES(?,?,?)', (project, row['id'], json.dumps(row)))
            self._snapshot(project, version, change or {'op': 'add', 'requirement': row['id'], 'text': row['text']})
        return row

    def update_requirement(self, project, identity, *, change, source='user', evidence='', **fields):
        if set(fields) - {'text', 'status', 'category', 'polarity', 'kind'}:
            raise ValueError('Invalid requirement update')
        with self.transaction() as db:
            row = self.requirement(project, identity)
            if row is None:
                raise ValueError('Unknown requirement')
            version = self._bump(project)
            previous = {k: row[k] for k in fields}
            row.update(fields, updated_version=version)
            row['evidence'] = (row['evidence'] + [{'source': source, 'text': str(evidence)[:300], 'version': version,
                                                   'at': self.clock(), 'previous': previous}])[-20:]
            db.execute('UPDATE requirements SET data=? WHERE project=? AND id=?', (json.dumps(row), project, identity))
            self._snapshot(project, version, {**change, 'requirement': identity})
        return row

    def _bump(self, project):
        row = self.get(project)
        row['version'] += 1
        self.save(row)
        return row['version']

    def _snapshot(self, project, version, change):
        snapshot = [{k: r[k] for k in ('id', 'text', 'kind', 'category', 'polarity', 'status')}
                    for r in self.requirements(project, include_inactive=True)]
        self.db.execute('INSERT INTO spec_versions VALUES(?,?,?,?,?)', (project, version, self.clock(), json.dumps(change), json.dumps(snapshot)))
        self.event(project, 'spec_version', {'version': version, **change})

    def versions(self, project):
        with self.lock:
            rows = self.db.execute('SELECT version, at, change, snapshot FROM spec_versions WHERE project=? ORDER BY version', (project,)).fetchall()
        return [{'version': r[0], 'at': r[1], 'change': json.loads(r[2]), 'snapshot': json.loads(r[3])} for r in rows]

    def close(self):
        with self.lock:
            self.db.close()
