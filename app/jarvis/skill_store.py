"""Living skill registry: stable identities and transactional performance history.

SQLite (.jarvis-runtime/skills/skill_store.sqlite3) is the authoritative history.
Identities follow OpenSpace's `.skill_id` sidecar convention (one line,
`<name>__imp_<8 hex>`) for skill folders Jarvis owns (bundled `skills/`,
`custom-skills/`, evolved skills); read-only roots (Obsidian personal and learned
guides, Hermes and DeerFlow references) are mapped by root + relative path in
SQLite so their folders are never written. Existing `.skill_id` files are kept.

Counters are derived from `skill_events`, whose `event_key` is unique per
(task, skill, event), so retries, crash recovery and repeated finish hooks can
never double-count. Nothing here grants a permission or selects a tool; trust is
evidence about guidance quality only.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import uuid

SKILL_ID_FILENAME = '.skill_id'
SKILL_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}__(?:imp|cap|fix|der)_[a-f0-9]{8}')
EVENTS = ('selected', 'applied', 'completed_verified', 'fallback', 'failed')
TRUST = ('provisional', 'trusted', 'demoted')
ORIGINS = ('imported', 'captured', 'derived', 'fixed')
OWNED_ROOTS = ('Builtins', 'Custom', 'Evolved')
FAILURE_CAUSES = ('control_not_found', 'precondition_changed', 'permission_denied', 'verification_failed',
                  'tool_unavailable', 'timeout', 'cancelled', 'uncertain_effect', 'other')

SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_records (
    skill_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', root TEXT NOT NULL,
    relative_path TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, trust_state TEXT NOT NULL DEFAULT 'trusted',
    lineage_origin TEXT NOT NULL DEFAULT 'imported', lineage_generation INTEGER NOT NULL DEFAULT 0,
    lineage_parent_ids_json TEXT NOT NULL DEFAULT '[]', lineage_change_summary TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, compatibility_json TEXT NOT NULL DEFAULT '{}',
    source_task_id TEXT NOT NULL DEFAULT '', epoch_event_id INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT NOT NULL, last_updated TEXT NOT NULL, UNIQUE(root, relative_path));
CREATE TABLE IF NOT EXISTS skill_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE, skill_id TEXT NOT NULL,
    event_type TEXT NOT NULL, task_id TEXT NOT NULL, at TEXT NOT NULL, evidence_json TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS idx_events_skill ON skill_events(skill_id, event_type);
CREATE TABLE IF NOT EXISTS skill_versions (
    skill_id TEXT NOT NULL, version INTEGER NOT NULL, content_hash TEXT NOT NULL, body TEXT NOT NULL,
    diff TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, created_at TEXT NOT NULL, evidence_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(skill_id, version));
CREATE TABLE IF NOT EXISTS skill_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE, skill_id TEXT NOT NULL, task_id TEXT NOT NULL,
    cause TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', at TEXT NOT NULL);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def content_hash(body):
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def event_evidence(value):
    """Metadata only; never truncate serialized JSON or retain arbitrary evidence text."""
    if not isinstance(value, dict):
        return {}
    result = {}
    if type(value.get('version')) is int and 0 < value['version'] <= 1_000_000:
        result['version'] = value['version']
    if isinstance(value.get('cause'), str) and value['cause'] in FAILURE_CAUSES:
        result['cause'] = value['cause']
    if value.get('reason') in ('bound tools unused', 'recovered or unverified'):
        result['reason'] = value['reason']
    if isinstance(value.get('evidence'), list):
        result['evidence_count'] = min(len(value['evidence']), 12)
    elif type(value.get('evidence_count')) is int and 0 <= value['evidence_count'] <= 12:
        result['evidence_count'] = value['evidence_count']
    return result


def read_event_evidence(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return {}, False
    return event_evidence(value), isinstance(value, dict)


def generate_skill_id(name, kind='imp'):
    slug = re.sub(r'[^a-z0-9-]', '-', str(name).casefold())[:64].strip('-') or 'skill'
    return f'{slug}__{kind}_{uuid.uuid4().hex[:8]}'


def read_sidecar(folder):
    path = Path(folder) / SKILL_ID_FILENAME
    try:
        if path.is_symlink() or path.stat().st_size > 200:
            return None
        value = path.read_text(encoding='utf-8').strip()
    except OSError:
        return None
    return value if SKILL_ID.fullmatch(value) else None


def ensure_sidecar(folder, name):
    """OpenSpace-compatible identity; an existing valid sidecar is always kept."""
    existing = read_sidecar(folder)
    if existing:
        return existing
    if (Path(folder) / SKILL_ID_FILENAME).exists():
        return None  # Invalid sidecar is preserved for review; the SQLite mapping keeps identity stable.
    identifier = generate_skill_id(name)
    path = Path(folder) / SKILL_ID_FILENAME
    temporary = path.with_name('.skill_id.tmp-' + uuid.uuid4().hex[:8])
    temporary.write_text(identifier + '\n', encoding='utf-8')
    try:
        # No-clobber: a concurrent writer's identity wins and ours is discarded.
        import os
        os.link(temporary, path)
    except FileExistsError:
        pass
    finally:
        temporary.unlink(missing_ok=True)
    return read_sidecar(folder) or identifier


class SkillStore:
    def __init__(self, base):
        self.path = Path(base) / '.jarvis-runtime' / 'skills' / 'skill_store.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.error = None
        try:
            self._initialize()
        except sqlite3.DatabaseError as exc:
            # Preserve the damaged file for review and start an empty history.
            damaged = self.path.with_name('skill_store.damaged-' + uuid.uuid4().hex[:8] + '.sqlite3')
            for suffix in ('-wal', '-shm'):
                Path(str(self.path) + suffix).unlink(missing_ok=True)
            self.path.replace(damaged)
            self.error = 'Skill history was damaged and preserved as ' + damaged.name + ': ' + str(exc)[:200]
            self._initialize()

    def _initialize(self):
        # executescript commits implicitly, so schema setup uses its own plain connection.
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            try:
                integrity = db.execute('PRAGMA quick_check').fetchone()[0]
                if integrity != 'ok':
                    raise sqlite3.DatabaseError('integrity check failed: ' + integrity)
                db.executescript(SCHEMA)
            finally:
                db.close()

    @contextmanager
    def connect(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
            db.row_factory = sqlite3.Row
            try:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('PRAGMA foreign_keys=ON')
                db.execute('BEGIN IMMEDIATE')
                yield db
                db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                raise
            finally:
                db.close()

    # ---- identity ------------------------------------------------------------------------------------------------
    def register(self, row, folder=None):
        """Upsert one discovered skill; returns its stable skill_id."""
        root, relative = row['origin'], row['provenance']['relative_path']
        body_hash = row['provenance']['sha256']
        identifier = None
        if root in OWNED_ROOTS and folder is not None:
            try:
                identifier = ensure_sidecar(folder, row['name'])
            except OSError:
                identifier = None  # Read-only checkout: fall back to the SQLite mapping.
        stamp = now()
        with self.connect() as db:
            existing = db.execute('SELECT * FROM skill_records WHERE root=? AND relative_path=?', (root, relative)).fetchone()
            if identifier is None:
                identifier = existing['skill_id'] if existing else generate_skill_id(row['name'])
            if existing and existing['skill_id'] != identifier:
                # A sidecar is authoritative: keep history by moving the mapping.
                db.execute('UPDATE skill_records SET skill_id=? WHERE skill_id=?', (identifier, existing['skill_id']))
                db.execute('UPDATE skill_events SET skill_id=? WHERE skill_id=?', (identifier, existing['skill_id']))
                existing = db.execute('SELECT * FROM skill_records WHERE skill_id=?', (identifier,)).fetchone()
            current = db.execute('SELECT * FROM skill_records WHERE skill_id=?', (identifier,)).fetchone()
            if current is None:
                db.execute('INSERT INTO skill_records(skill_id,name,description,root,relative_path,trust_state,content_hash,'
                           'first_seen,last_updated) VALUES(?,?,?,?,?,?,?,?,?)',
                           (identifier, row['name'], row['description'][:1024], root, relative,
                            row.get('trust_state', 'trusted'), body_hash, stamp, stamp))
                db.execute('INSERT OR IGNORE INTO skill_versions(skill_id,version,content_hash,body,status,created_at) '
                           'VALUES(?,1,?,?,?,?)', (identifier, body_hash, row['body'], 'active', stamp))
            elif current['content_hash'] != body_hash:
                version = current['version'] + 1
                db.execute('UPDATE skill_records SET content_hash=?, version=?, description=?, last_updated=? WHERE skill_id=?',
                           (body_hash, version, row['description'][:1024], stamp, identifier))
                db.execute("UPDATE skill_versions SET status='superseded' WHERE skill_id=? AND status='active'", (identifier,))
                db.execute('INSERT OR IGNORE INTO skill_versions(skill_id,version,content_hash,body,status,created_at) '
                           'VALUES(?,?,?,?,?,?)', (identifier, version, body_hash, row['body'], 'active', stamp))
        return identifier

    def record(self, skill_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM skill_records WHERE skill_id=?', (skill_id,)).fetchone()
        return dict(row) if row else None

    def records(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM skill_records ORDER BY name')]

    # ---- telemetry ---------------------------------------------------------------------------------------------------
    def event(self, skill_id, event_type, task_id, evidence=None):
        """Idempotent: the same (task, skill, event) is stored at most once."""
        if event_type not in EVENTS or not isinstance(task_id, str) or not task_id or len(task_id) > 64:
            raise ValueError('Invalid skill event.')
        key = hashlib.sha256('\n'.join((task_id, skill_id, event_type)).encode()).hexdigest()
        payload = json.dumps(event_evidence(evidence), ensure_ascii=False)
        with self.connect() as db:
            if db.execute('SELECT 1 FROM skill_records WHERE skill_id=?', (skill_id,)).fetchone() is None:
                raise ValueError('Unknown skill identity.')
            cursor = db.execute('INSERT OR IGNORE INTO skill_events(event_key,skill_id,event_type,task_id,at,evidence_json) '
                                'VALUES(?,?,?,?,?,?)', (key, skill_id, event_type, task_id, now(), payload))
            return cursor.rowcount == 1

    def failure(self, skill_id, task_id, cause, detail=''):
        """Detail log; counters read causes from the failed event's evidence."""
        cause = cause if cause in FAILURE_CAUSES else 'other'
        key = hashlib.sha256('\n'.join((task_id, skill_id, 'failure', cause)).encode()).hexdigest()
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO skill_failures(event_key,skill_id,task_id,cause,detail,at) VALUES(?,?,?,?,?,?)',
                       (key, skill_id, task_id, cause, '', now()))  # Category only; raw failures can contain private data.

    def metrics(self, skill_id, current_version=False):
        """Lifetime counters, or only evidence since the active version (current_version=True)."""
        with self.connect() as db:
            since = 0
            if current_version:
                row = db.execute('SELECT epoch_event_id FROM skill_records WHERE skill_id=?', (skill_id,)).fetchone()
                since = row['epoch_event_id'] if row else 0
            counts = {name: 0 for name in EVENTS}
            for row in db.execute('SELECT event_type, COUNT(*) AS n FROM skill_events WHERE skill_id=? AND id>? '
                                  'GROUP BY event_type', (skill_id, since)):
                counts[row['event_type']] = row['n']
            last = db.execute("SELECT at, evidence_json FROM skill_events WHERE skill_id=? AND id>? AND "
                              "event_type='completed_verified' ORDER BY id DESC LIMIT 1", (skill_id, since)).fetchone()
            causes = {}
            invalid = 0
            for row in db.execute("SELECT evidence_json FROM skill_events WHERE skill_id=? AND id>? AND event_type='failed'",
                                  (skill_id, since)):
                saved, valid = read_event_evidence(row['evidence_json'])
                invalid += not valid
                cause = saved.get('cause', 'other')
                cause = cause if cause in FAILURE_CAUSES else 'other'
                causes[cause] = causes.get(cause, 0) + 1
            recent = [row['event_type'] for row in db.execute(
                "SELECT event_type FROM skill_events WHERE skill_id=? AND id>? AND event_type IN ('completed_verified','failed') "
                'ORDER BY id DESC LIMIT 10', (skill_id, since))]
        return {'selected_count': counts['selected'], 'applied_count': counts['applied'],
                'completed_verified_count': counts['completed_verified'], 'fallback_count': counts['fallback'],
                'failed_count': counts['failed'], 'last_verified_at': last['at'] if last else None,
                'last_verified_evidence': read_event_evidence(last['evidence_json'])[0] if last else None,
                'invalid_evidence_count': invalid + (not read_event_evidence(last['evidence_json'])[1] if last else 0),
                'failure_causes': causes, 'recent_outcomes': recent}

    def all_metrics(self):
        """Lifetime ranking metrics for every skill in one read (planning-path cost)."""
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                rows = {}
                for row in db.execute('SELECT skill_id, event_type, COUNT(*) AS n, MAX(at) AS last FROM skill_events '
                                      'GROUP BY skill_id, event_type'):
                    item = rows.setdefault(row['skill_id'], {'selected_count': 0, 'applied_count': 0,
                                           'completed_verified_count': 0, 'fallback_count': 0, 'failed_count': 0,
                                           'last_verified_at': None})
                    item[row['event_type'] + '_count'] = row['n']
                    if row['event_type'] == 'completed_verified':
                        item['last_verified_at'] = row['last']
                return rows
            finally:
                db.close()

    def selected_for(self, task_id):
        with self.connect() as db:
            return [r['skill_id'] for r in db.execute(
                "SELECT DISTINCT skill_id FROM skill_events WHERE task_id=? AND event_type='selected'", (task_id,))]

    def set_source_task(self, skill_id, task_id):
        with self.connect() as db:
            db.execute('UPDATE skill_records SET source_task_id=? WHERE skill_id=?', (str(task_id)[:64], skill_id))

    def tasks_with(self, skill_id, event_type, current_version=False):
        with self.connect() as db:
            since = db.execute('SELECT epoch_event_id FROM skill_records WHERE skill_id=?', (skill_id,)).fetchone() if current_version else None
            return [r['task_id'] for r in db.execute('SELECT task_id FROM skill_events WHERE skill_id=? AND event_type=? AND id>?',
                                                     (skill_id, event_type, since['epoch_event_id'] if since else 0))]

    def new_epoch(self, skill_id):
        """Evidence after this point describes the newly active version only."""
        with self.connect() as db:
            latest = db.execute('SELECT COALESCE(MAX(id), 0) AS n FROM skill_events').fetchone()['n']
            db.execute('UPDATE skill_records SET epoch_event_id=? WHERE skill_id=?', (latest, skill_id))

    # ---- lifecycle ---------------------------------------------------------------------------------------------------
    def set_state(self, skill_id, *, enabled=None, trust_state=None, compatibility=None):
        updates, values = [], []
        if enabled is not None:
            updates.append('enabled=?')
            values.append(1 if enabled else 0)
        if trust_state is not None:
            if trust_state not in TRUST:
                raise ValueError('Unknown trust state.')
            updates.append('trust_state=?')
            values.append(trust_state)
        if compatibility is not None:
            updates.append('compatibility_json=?')
            values.append(json.dumps(compatibility, sort_keys=True)[:2000])
        if not updates:
            return
        with self.connect() as db:
            db.execute('UPDATE skill_records SET ' + ', '.join(updates) + ', last_updated=? WHERE skill_id=?',
                       (*values, now(), skill_id))

    def add_lineage(self, skill_id, origin, parents, generation, summary):
        if origin not in ORIGINS:
            raise ValueError('Unknown lineage origin.')
        with self.connect() as db:
            db.execute('UPDATE skill_records SET lineage_origin=?, lineage_parent_ids_json=?, lineage_generation=?, '
                       'lineage_change_summary=? WHERE skill_id=?',
                       (origin, json.dumps(list(parents)), generation, str(summary)[:500], skill_id))

    def versions(self, skill_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM skill_versions WHERE skill_id=? ORDER BY version', (skill_id,))]

    def add_version(self, skill_id, body, diff, status, evidence):
        with self.connect() as db:
            current = db.execute('SELECT version FROM skill_records WHERE skill_id=?', (skill_id,)).fetchone()
            latest = db.execute('SELECT MAX(version) AS v FROM skill_versions WHERE skill_id=?', (skill_id,)).fetchone()['v'] or 0
            version = latest + 1
            db.execute('INSERT INTO skill_versions(skill_id,version,content_hash,body,diff,status,created_at,evidence_json) '
                       'VALUES(?,?,?,?,?,?,?,?)', (skill_id, version, content_hash(body), body, diff[:20000], status, now(),
                                                    json.dumps(evidence, default=str)[:4000]))
            return version, current['version'] if current else None

    def activate_version(self, skill_id, version):
        with self.connect() as db:
            row = db.execute('SELECT * FROM skill_versions WHERE skill_id=? AND version=?', (skill_id, version)).fetchone()
            if row is None:
                raise ValueError('Unknown skill version.')
            db.execute("UPDATE skill_versions SET status='superseded' WHERE skill_id=? AND status='active'", (skill_id,))
            db.execute("UPDATE skill_versions SET status='active' WHERE skill_id=? AND version=?", (skill_id, version))
            db.execute('UPDATE skill_records SET version=?, content_hash=?, last_updated=? WHERE skill_id=?',
                       (version, row['content_hash'], now(), skill_id))
            return dict(row)

    def mark_version(self, skill_id, version, status):
        with self.connect() as db:
            db.execute('UPDATE skill_versions SET status=? WHERE skill_id=? AND version=?', (status, skill_id, version))
