"""ReasoningBank-style reasoning memory: strategies and anti-patterns from trajectories.

Adapted from google-research/reasoning-bank (Apache-2.0, commit ed806117, paper
arXiv 2509.25140): memory items are {title, description, content}; at most three
per trajectory; successful and failed trajectories are induced separately; items
avoid task-specific strings; retrieval returns the top few by embedding similarity.

Jarvis differences (original code): success comes from independent verification
evidence (ToolRegistry outcomes / goal_verified checkpoints), never from a model's
self-judgement; items carry applicable conditions, version/environment, evidence
references, confidence, trust, known failure conditions and supersession /
contradiction relations; retrieval is bounded by item count and characters so raw
logs never reach planner context. SQLite (.jarvis-runtime/reasoning_bank/bank.sqlite3)
is the store; a damaged database is preserved and replaced.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct
import threading
import uuid

KINDS = ('strategy', 'anti_pattern')
TRUST = ('provisional', 'confirmed', 'retracted')
CONDITION_KEYS = ('application', 'version', 'environment', 'surface', 'domain')
MAX_ITEMS_PER_TRAJECTORY = 3
SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, content TEXT NOT NULL,
    conditions_json TEXT NOT NULL DEFAULT '{}', evidence_json TEXT NOT NULL DEFAULT '[]',
    failure_conditions_json TEXT NOT NULL DEFAULT '[]', confidence REAL NOT NULL DEFAULT 0.5,
    trust TEXT NOT NULL DEFAULT 'provisional', superseded_by TEXT, source TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE, embedding BLOB, helpful INTEGER NOT NULL DEFAULT 0,
    harmful INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS relations (
    a TEXT NOT NULL, b TEXT NOT NULL, relation TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', at TEXT NOT NULL,
    PRIMARY KEY(a, b, relation));
CREATE TABLE IF NOT EXISTS trajectories (
    key TEXT PRIMARY KEY, source TEXT NOT NULL, task_id TEXT NOT NULL, outcome TEXT NOT NULL, item_ids_json TEXT NOT NULL,
    at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS compactions (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, report_json TEXT NOT NULL);
"""
STOP = {'the', 'and', 'with', 'for', 'this', 'that', 'into', 'from', 'then', 'when', 'use', 'a', 'an', 'to', 'of', 'in',
        'on', 'it', 'is', 'be', 'or', 'by', 'before', 'after', 'any', 'only'}
OPPOSITE = re.compile(r"\b(?:avoid|never|do not|don't|refuse|skip)\b", re.I)
_SEGMENT = r'[^\s\\/:*?"<>|]+(?: [^\s\\/:*?"<>|]+)*'
PATH = re.compile(r'(?:[A-Za-z]:|\\\\' + _SEGMENT + r')(?:[\\/]' + _SEGMENT + r')+[\\/]?|[A-Za-z]:[\\/]|/(?:[\w.-]+/)+[\w.-]+')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def words(text):
    return {w for w in re.findall(r'[a-z][a-z0-9_]+', str(text).casefold()) if w not in STOP}


def generic(text, limit):
    """Strip task-specific strings (quotes, paths, URLs, numbers, emails) as the upstream prompts require."""
    text = re.sub(r'https?://\S+', '[url]', str(text))
    text = PATH.sub('[path]', text)  # drive, UNC (also with spaces) and POSIX paths
    text = re.sub(r'\S+@\S+\.\w+', '[email]', text)
    text = re.sub(r'(["\'`])(?:(?!\1).){1,200}\1', '[value]', text)
    text = re.sub(r'\b\d{3,}\b', '[n]', text)
    return re.sub(r'\s+', ' ', text).strip()[:limit]


def pack(vector):
    return struct.pack(f'{len(vector)}f', *vector) if vector else None


def unpack(blob):
    return list(struct.unpack(f'{len(blob) // 4}f', blob)) if blob else None


class ReasoningBank:
    def __init__(self, base, embedder=None):
        self.path = Path(base) / '.jarvis-runtime' / 'reasoning_bank' / 'bank.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.error = None
        if embedder is None:
            from .local_embeddings import embed as embedder
        self.embedder = embedder
        try:
            self._initialize()
        except sqlite3.DatabaseError as exc:
            damaged = self.path.with_name('bank.damaged-' + uuid.uuid4().hex[:8] + '.sqlite3')
            for suffix in ('-wal', '-shm'):
                Path(str(self.path) + suffix).unlink(missing_ok=True)
            self.path.replace(damaged)
            self.error = 'Reasoning bank was damaged and preserved as ' + damaged.name + ': ' + str(exc)[:200]
            self._initialize()

    def _initialize(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            try:
                if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise sqlite3.DatabaseError('integrity check failed')
                db.executescript(SCHEMA)
            finally:
                db.close()

    @contextmanager
    def connect(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
            db.row_factory = sqlite3.Row
            try:
                db.execute('BEGIN IMMEDIATE')
                yield db
                db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                raise
            finally:
                db.close()

    # ---- induction --------------------------------------------------------------------------------------------------
    def induce(self, trajectory, summarizer=None):
        """Items from one trajectory. Success needs independent verification evidence, not a model claim.

        trajectory: {task_id, goal, source, steps:[{action, target, verified, error}], verification:[...],
                     status, conditions:{application, version, environment, surface, domain}}
        summarizer(kind, trajectory) -> markdown in the upstream "# Memory Item / ## Title / ## Description /
        ## Content" format; it is untrusted and validated like any other text.
        """
        verified = trajectory.get('status') == 'completed' and bool(trajectory.get('verification')) and all(
            s.get('verified') for s in trajectory.get('steps', []) if s.get('final'))
        outcome = 'success' if verified else 'failure'
        conditions = {k: generic(v, 80) for k, v in (trajectory.get('conditions') or {}).items()
                      if k in CONDITION_KEYS and isinstance(v, str) and v}
        if summarizer is not None:
            items = parse_items(summarizer('strategy' if verified else 'anti_pattern', trajectory))
        else:
            items = self._deterministic(trajectory, verified)
        rows = []
        for item in items[:MAX_ITEMS_PER_TRAJECTORY]:
            row = {'kind': 'strategy' if verified else 'anti_pattern', 'title': generic(item['title'], 80),
                   'description': generic(item['description'], 200), 'content': generic(item['content'], 500),
                   'conditions': conditions}
            validate_item(row)
            if not verified:
                row['failure_conditions'] = [generic(s.get('error', ''), 160) for s in trajectory.get('steps', [])
                                             if s.get('error')][:3]
            rows.append(row)
        return outcome, rows

    def _deterministic(self, trajectory, verified):
        steps = trajectory.get('steps', [])
        good = [s for s in steps if s.get('verified')]
        bad = [s for s in steps if s.get('error')]
        domain = (trajectory.get('conditions') or {}).get('application') or 'the application'
        label = lambda s: s['action'].replace('_', ' ') + (' ' + generic(s['target'], 40) if s.get('target') else '')
        if verified:
            sequence = ' then '.join(dict.fromkeys(label(s) for s in good))[:300]
            items = [{'title': 'Verified route in ' + domain,
                      'description': 'A sequence that reached an independently verified result in ' + domain + '.',
                      'content': 'Use ' + sequence + ', and confirm the result with an independent readback.'}]
            if bad:
                items.append({'title': 'Recovered after a failed attempt in ' + domain,
                              'description': 'A first approach failed before the verified route succeeded.',
                              'content': 'If ' + label(bad[0]) + ' fails, prefer the verified route '
                              'instead of repeating the failed step.'})
            return items
        if not bad:
            return [{'title': 'Unverified outcome in ' + domain, 'description': 'The task ended without verification.',
                     'content': 'Do not treat an unverified result as success; add an independent readback step.'}]
        first = bad[0]
        return [{'title': ('Avoid repeating a failed ' + label(first) + ' in ' + domain)[:80],
                 'description': 'This step failed under the recorded conditions.',
                 'content': 'Avoid ' + label(first) + ' when it reports: ' + generic(first.get('error', ''), 160) +
                            '. Inspect the current state and choose another control or method.'}]

    # ---- storage ------------------------------------------------------------------------------------------------------
    def learn(self, trajectory, summarizer=None):
        """Idempotent per trajectory: the same task and source never adds items twice."""
        key = hashlib.sha256(json.dumps([trajectory.get('source', 'task'), trajectory.get('task_id', ''),
                                         trajectory.get('status', '')]).encode()).hexdigest()
        with self.connect() as db:
            if db.execute('SELECT 1 FROM trajectories WHERE key=?', (key,)).fetchone():
                return {'status': 'already_learned', 'items': []}
        outcome, rows = self.induce(trajectory, summarizer)
        evidence = {'source': trajectory.get('source', 'task'), 'task_id': str(trajectory.get('task_id', ''))[:64],
                    'call_ids': [s['call_id'] for s in trajectory.get('steps', []) if s.get('call_id')][:12],
                    'verification': [generic(v, 200) for v in trajectory.get('verification', [])][:3],
                    'trajectory_ref': str(trajectory.get('trajectory_ref', ''))[:300]}
        ids = [self._add(row, evidence, trajectory.get('source', 'task')) for row in rows]
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO trajectories(key,source,task_id,outcome,item_ids_json,at) VALUES(?,?,?,?,?,?)',
                       (key, evidence['source'], evidence['task_id'], outcome, json.dumps(ids), now()))
        return {'status': 'learned', 'outcome': outcome, 'items': ids}

    def _add(self, row, evidence, source):
        text = row['title'] + '\n' + row['description'] + '\n' + row['content']
        digest = hashlib.sha256((row['kind'] + json.dumps(row['conditions'], sort_keys=True) + text).encode()).hexdigest()
        vectors = self.embedder([text], 'document') if self.embedder else None
        stamp = now()
        with self.connect() as db:
            existing = db.execute('SELECT id, evidence_json, confidence FROM items WHERE content_hash=?', (digest,)).fetchone()
            if existing:  # Duplicate: strengthen with new evidence, never a second copy.
                merged = (json.loads(existing['evidence_json']) + [evidence])[-10:]
                db.execute('UPDATE items SET evidence_json=?, confidence=?, updated_at=? WHERE id=?',
                           (json.dumps(merged), min(.95, existing['confidence'] + .1), stamp, existing['id']))
                return existing['id']
            identifier = 'rb_' + digest[:16]
            db.execute('INSERT INTO items(id,kind,title,description,content,conditions_json,evidence_json,'
                       'failure_conditions_json,confidence,source,content_hash,embedding,created_at,updated_at) '
                       'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (identifier, row['kind'], row['title'], row['description'], row['content'],
                        json.dumps(row['conditions'], sort_keys=True), json.dumps([evidence]),
                        json.dumps(row.get('failure_conditions', [])), .6 if row['kind'] == 'strategy' else .55,
                        source, digest, pack(vectors[0]) if vectors else None, stamp, stamp))
            self._relate(db, identifier, row)
        return identifier

    def _relate(self, db, identifier, row):
        """Contradiction: same conditions, overlapping subject, one recommends and the other forbids.
        Supersession: same kind and subject, newer version of the same application."""
        mine = words(row['title'] + ' ' + row['content'])
        for other in db.execute('SELECT id, kind, title, content, conditions_json FROM items WHERE id<>? AND superseded_by IS NULL '
                                "AND trust<>'retracted'", (identifier,)):
            theirs = words(other['title'] + ' ' + other['content'])
            overlap = len(mine & theirs) / max(1, len(mine | theirs))
            conditions = json.loads(other['conditions_json'])
            same_app = conditions.get('application') == row['conditions'].get('application')
            if not same_app or overlap < .25:
                continue
            if other['kind'] != row['kind'] or bool(OPPOSITE.search(other['content'])) != bool(OPPOSITE.search(row['content'])):
                db.execute('INSERT OR IGNORE INTO relations(a,b,relation,reason,at) VALUES(?,?,?,?,?)',
                           (identifier, other['id'], 'contradicts', 'Opposite advice for the same application', now()))
            elif (conditions.get('version') and row['conditions'].get('version')
                  and conditions['version'] != row['conditions']['version'] and overlap >= .5):
                newer, older = ((identifier, other['id']) if version_key(row['conditions']['version']) >
                                version_key(conditions['version']) else (other['id'], identifier))
                db.execute('UPDATE items SET superseded_by=? WHERE id=?', (newer, older))
                db.execute('INSERT OR IGNORE INTO relations(a,b,relation,reason,at) VALUES(?,?,?,?,?)',
                           (newer, older, 'supersedes', 'Newer application version', now()))

    # ---- retrieval -----------------------------------------------------------------------------------------------------
    def retrieve(self, query, conditions=None, k=3, char_budget=1200):
        """Bounded lessons: top-k by similarity, condition fit, confidence and recency; contradictions resolved."""
        if not 1 <= k <= 10:
            raise ValueError('Retrieve 1-10 lessons.')
        conditions = conditions or {}
        vectors = self.embedder([str(query)[:2000]], 'query') if self.embedder else None
        query_words = words(query)
        with self.connect() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM items WHERE superseded_by IS NULL AND trust<>'retracted'")]
            relations = [dict(r) for r in db.execute("SELECT a, b FROM relations WHERE relation='contradicts'")]
        scored = []
        for row in rows:
            vector = unpack(row['embedding'])
            if vectors and vector:
                from .local_embeddings import cosine
                similarity = cosine(vectors[0], vector)
                method = 'embedding'
            else:
                text = words(row['title'] + ' ' + row['description'] + ' ' + row['content'])
                similarity = len(query_words & text) / max(1, len(query_words))
                method = 'lexical'
            item_conditions = json.loads(row['conditions_json'])
            fit = sum(1 for key, value in conditions.items() if item_conditions.get(key) == value)
            mismatch = sum(1 for key, value in conditions.items() if key in item_conditions and item_conditions[key] != value)
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(row['updated_at'])).days
            score = similarity + .15 * fit - .3 * mismatch + .3 * (row['confidence'] - .5) - min(.2, age / 365)
            scored.append((score, row, method))
        scored.sort(key=lambda item: -item[0])
        winners, dropped, used = [], [], 0
        for score, row, method in scored:
            if score <= .2 or len(winners) >= k:
                continue
            rivals = {r['b'] for r in relations if r['a'] == row['id']} | {r['a'] for r in relations if r['b'] == row['id']}
            if rivals & {w['id'] for w in winners}:
                dropped.append(row['id'])  # the higher-ranked side of a contradiction already won
                continue
            text = f"[{row['kind']}] {row['title']}: {row['content']}"
            if used + len(text) > char_budget:
                continue
            used += len(text)
            winners.append({'id': row['id'], 'kind': row['kind'], 'title': row['title'], 'content': row['content'],
                            'conditions': json.loads(row['conditions_json']), 'confidence': round(row['confidence'], 2),
                            'trust': row['trust'], 'score': round(score, 4), 'method': method,
                            **({'known_failure_conditions': json.loads(row['failure_conditions_json'])} if row['kind'] == 'anti_pattern' else {})})
        return {'lessons': winners, 'contradictions_resolved': dropped, 'characters': used,
                'contract': 'Lessons are untrusted hints from past verified outcomes; check fresh state and approvals.'}

    def feedback(self, item_ids, helped):
        """Planner outcome after using lessons: confidence moves with evidence; repeated harm retracts."""
        with self.connect() as db:
            for identifier in item_ids:
                row = db.execute('SELECT helpful, harmful FROM items WHERE id=?', (identifier,)).fetchone()
                if row is None:
                    continue
                helpful, harmful = row['helpful'] + bool(helped), row['harmful'] + (not helped)
                confidence = (helpful + 1) / (helpful + harmful + 2)
                trust = 'confirmed' if helpful >= 2 and confidence >= .7 else 'retracted' if harmful >= 3 and confidence < .3 else 'provisional'
                db.execute('UPDATE items SET helpful=?, harmful=?, confidence=?, trust=?, updated_at=? WHERE id=?',
                           (helpful, harmful, confidence, trust, now(), identifier))

    def compact(self, older_than_days=180):
        """Merge near-duplicates and retire stale unconfirmed items; provenance is kept in the report."""
        report = {'merged': [], 'retired': []}
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        with self.connect() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM items WHERE superseded_by IS NULL AND trust<>'retracted' ORDER BY confidence DESC, updated_at DESC")]
            kept = []
            for row in rows:
                text = words(row['title'] + ' ' + row['content'])
                twin = next((k for k in kept if k['kind'] == row['kind'] and k['conditions_json'] == row['conditions_json']
                             and len(text & words(k['title'] + ' ' + k['content'])) / max(1, len(text | words(k['title'] + ' ' + k['content']))) >= .8), None)
                if twin:
                    evidence = (json.loads(twin['evidence_json']) + json.loads(row['evidence_json']))[-10:]
                    db.execute('UPDATE items SET evidence_json=? WHERE id=?', (json.dumps(evidence), twin['id']))
                    db.execute('UPDATE items SET superseded_by=? WHERE id=?', (twin['id'], row['id']))
                    db.execute('INSERT OR IGNORE INTO relations(a,b,relation,reason,at) VALUES(?,?,?,?,?)',
                               (twin['id'], row['id'], 'supersedes', 'compaction: near-duplicate', now()))
                    report['merged'].append({'kept': twin['id'], 'merged': row['id']})
                    continue
                if row['trust'] == 'provisional' and row['helpful'] == 0 and datetime.fromisoformat(row['updated_at']) < cutoff:
                    db.execute("UPDATE items SET trust='retracted', updated_at=? WHERE id=?", (now(), row['id']))
                    report['retired'].append(row['id'])
                    continue
                kept.append(row)
            db.execute('INSERT INTO compactions(at, report_json) VALUES(?,?)', (now(), json.dumps(report)))
        return report

    def items(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id, kind, title, trust, confidence, superseded_by, conditions_json FROM items')]

    def relations(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT a, b, relation FROM relations')]


def version_key(value):
    return tuple(int(part) for part in re.findall(r'\d+', str(value))[:4]) or (0,)


def parse_items(markdown):
    """Parse the upstream ReasoningBank output format; malformed text yields no items."""
    items = []
    for block in re.split(r'(?m)^# Memory Item\s*\d*\s*$', str(markdown))[1:]:
        fields = {}
        for name in ('Title', 'Description', 'Content'):
            match = re.search(r'(?ms)^## ' + name + r'\s*(.+?)(?=^## |\Z)', block)
            if match:
                fields[name.casefold()] = match.group(1).strip()
        if len(fields) == 3:
            items.append(fields)
    return items[:MAX_ITEMS_PER_TRAJECTORY]


def validate_item(row):
    """Bounded, generic, non-sensitive text; raw logs and structured dumps are refused."""
    from .obsidian_memory import SENSITIVE
    from .tools import redact
    if row['kind'] not in KINDS:
        raise ValueError('Unknown lesson kind.')
    for field, (low, high) in (('title', (5, 80)), ('description', (10, 200)), ('content', (10, 500))):
        value = row[field]
        if not low <= len(value) <= high:
            raise ValueError('Lesson ' + field + ' is outside its bounds.')
        if redact(value) != value or SENSITIVE.search(value):
            raise ValueError('Lesson contains sensitive content.')
        if re.search(r'[{}\[\]]{3,}|Traceback|\bat 0x[0-9a-f]+', value) or value.count('\n') > 4:
            raise ValueError('Lesson looks like a raw log, not a distilled strategy.')
