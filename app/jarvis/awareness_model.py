"""JCAE state: typed observations, the world state X(t) and conservative beliefs.

Operational state only. Nothing here claims subjective experience. A source that
is unavailable is recorded as unknown; nothing is invented to fill the gap.
Private values (window titles, message text) stay in memory and are never written
to disk or handed to a cloud model by this layer.
"""
import hashlib
import json
import math
import re
import sqlite3
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field

FACETS = {'U': 'user context', 'P': 'computer and hardware', 'A': 'applications and projects',
          'T': 'tasks, goals and dependencies', 'E': 'authorized external environment', 'J': 'Jarvis operational state'}
CATEGORIES = {'user_activity': 'U', 'system': 'P', 'project': 'A', 'application': 'A', 'task': 'T',
              'external': 'E', 'jarvis': 'J'}
SENSITIVITY = ('public', 'internal', 'private')
PROVENANCE = ('observed', 'inferred', 'user_confirmed')
RETENTION = ('none', 'session', 'days')
# Human states are never raised far above their prior by indirect evidence such as app dwell time.
HUMAN_CAP = .6


def _bounded_text(value, limit):
    return str(value)[:limit].encode('utf-8', errors='replace').decode('utf-8')


@dataclass
class Observation:
    type: str
    source: str
    category: str
    values: dict
    at: float
    project: str = ''
    application: str = ''
    task: str = ''
    confidence: float = 1.
    provenance: str = 'observed'
    sensitivity: str = 'internal'
    retention: str = 'session'
    origin: str = ''
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def validate(self):
        if not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){0,5}', self.type or '') or len(self.type) > 80:
            raise ValueError('Observation type must be a dotted lowercase name')
        if self.category not in CATEGORIES or self.sensitivity not in SENSITIVITY \
                or self.provenance not in PROVENANCE or self.retention not in RETENTION:
            raise ValueError('Invalid observation category, sensitivity, provenance or retention')
        if not isinstance(self.values, dict) or len(json.dumps(self.values, default=str)) > 4000:
            raise ValueError('Observation values must be a small object')
        if type(self.confidence) not in (int, float) or not 0 <= self.confidence <= 1 or not math.isfinite(self.at):
            raise ValueError('Observation confidence/time out of range')
        self.source = _bounded_text(self.source, 64)
        self.project, self.application, self.task = (_bounded_text(v, 160) for v in (self.project, self.application, self.task))
        return self

    @property
    def facet(self):
        return CATEGORIES[self.category]

    def fingerprint(self):
        """Stable identity of 'the same thing happening again', excluding timestamps and measurements."""
        signature = self.values.get('signature')
        if signature is None:
            signature = sorted((k, v) for k, v in self.values.items() if isinstance(v, (str, bool)) and k != 'detail')
        # Task problems are deduplicated per kind of failure, not per task instance.
        raw = json.dumps([self.type, self.project, self.application, '' if self.category == 'task' else self.task, signature], default=str)
        return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]

    def public_values(self):
        """What may leave this layer (UI, persistence, investigation context)."""
        if self.sensitivity != 'private':
            return dict(self.values)
        return {k: v for k, v in self.values.items() if isinstance(v, (int, float, bool)) or k in {'signature', 'executable'}}


def severity(kind):
    """Generic severity from the event name's own vocabulary; works for event types never seen before."""
    words = set(re.split(r'[._]', kind))
    if words & {'crash', 'crashed', 'failed', 'failure', 'error', 'exhausted', 'broken', 'unavailable', 'lost'}:
        return .8
    if words & {'blocked', 'stale', 'risk', 'pressure', 'shortfall', 'degraded', 'overdue', 'repeated', 'timeout', 'low'}:
        return .6
    if words & {'question', 'deadline', 'changed', 'modified', 'conflict'}:
        return .4
    if words & {'waiting', 'approval', 'paused', 'dependency'}:
        return .3  # Normal queue states: the Queue view already presents them.
    if words & {'completed', 'succeeded', 'passed', 'recovered', 'satisfied', 'ready'}:
        return .15
    return .2


class WorldState:
    """X(t) = [U, P, A, T, E, J]: each fact keeps value, time, source, confidence, freshness and provenance."""

    def __init__(self, clock=time.time, history=20):
        self.clock = clock
        self.lock = threading.RLock()
        self.facts, self.changes = {}, {}
        self.history = history

    def set(self, facet, key, value, source, *, confidence=1., provenance='observed', ttl=60., sensitivity='internal'):
        if facet not in FACETS or provenance not in PROVENANCE or not 0 <= confidence <= 1 or ttl <= 0:
            raise ValueError('Invalid world-state fact')
        now = self.clock()
        with self.lock:
            old = self.facts.get(key)
            # A fresh user-confirmed fact is not overwritten by an inference.
            if old and old['provenance'] == 'user_confirmed' and provenance == 'inferred' and now - old['at'] <= old['ttl']:
                return old
            fact = {'facet': facet, 'value': value, 'at': now, 'source': source, 'confidence': confidence,
                    'provenance': provenance, 'ttl': float(ttl), 'sensitivity': sensitivity}
            self.facts[key] = fact
            if len(self.facts) > 2000:
                for stale in sorted(self.facts, key=lambda k: self.facts[k]['at'])[:200]:
                    self.facts.pop(stale, None)
                    self.changes.pop(stale, None)
            if not old or old['value'] != value:
                self.changes.setdefault(key, deque(maxlen=self.history)).append({'at': now, 'value': value, 'source': source})
            return fact

    def get(self, key, fresh=True):
        """None means unknown, including a fact too old to rely on for a consequential decision."""
        with self.lock:
            fact = self.facts.get(key)
            if fact is None or fresh and self.clock() - fact['at'] > fact['ttl']:
                return None
            return dict(fact)

    def value(self, key, default=None, fresh=True):
        fact = self.get(key, fresh)
        return default if fact is None else fact['value']

    def freshness(self, key):
        with self.lock:
            fact = self.facts.get(key)
            return 0. if fact is None else math.exp(-max(0., self.clock() - fact['at']) / fact['ttl'])

    def invalidate(self, key):
        with self.lock:
            self.facts.pop(key, None)

    def history_of(self, key):
        with self.lock:
            return list(self.changes.get(key, ()))

    def snapshot(self, include_private=False):
        now = self.clock()
        with self.lock:
            rows = {}
            for key, fact in self.facts.items():
                if fact['sensitivity'] == 'private' and not include_private:
                    continue
                rows.setdefault(FACETS[fact['facet']], {})[key] = {
                    'value': fact['value'], 'source': fact['source'], 'provenance': fact['provenance'],
                    'confidence': round(fact['confidence'], 3), 'age_s': round(now - fact['at'], 1),
                    'fresh': now - fact['at'] <= fact['ttl']}
            return rows


class BeliefEngine:
    """b(t+1) = Update(b(t), observation): log-odds evidence with decay toward the prior as evidence ages."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.beliefs = {}

    @staticmethod
    def _logit(p):
        p = min(1 - 1e-6, max(1e-6, p))
        return math.log(p / (1 - p))

    def _decayed(self, belief, now):
        prior = self._logit(belief['prior'])
        factor = .5 ** (max(0., now - belief['updated']) / belief['half_life'])
        return prior + (belief['log_odds'] - prior) * factor

    def update(self, proposition, likelihood_ratio, source, note='', *, kind='system', prior=.5, half_life=3600.):
        if not proposition or likelihood_ratio <= 0 or not math.isfinite(likelihood_ratio):
            raise ValueError('Belief update needs a proposition and a positive finite likelihood ratio')
        now, ratio = self.clock(), min(20., max(1 / 20., likelihood_ratio))
        with self.lock:
            belief = self.beliefs.get(proposition) or {'proposition': proposition, 'kind': kind, 'prior': prior,
                'log_odds': self._logit(prior), 'updated': now, 'half_life': float(half_life),
                'support': 0, 'contradict': 0, 'evidence': deque(maxlen=12)}
            belief['log_odds'] = self._decayed(belief, now) + math.log(ratio)
            if kind == 'user_state' and source != 'user':
                belief['log_odds'] = min(belief['log_odds'], self._logit(HUMAN_CAP))
            belief['updated'] = now
            belief['support' if ratio > 1 else 'contradict'] += 1
            belief['evidence'].append({'at': now, 'source': source, 'ratio': round(ratio, 3), 'note': _bounded_text(note, 160)})
            self.beliefs[proposition] = belief
            return self.probability(proposition)

    def probability(self, proposition):
        with self.lock:
            belief = self.beliefs.get(proposition)
            if belief is None:
                return None
            return 1 / (1 + math.exp(-self._decayed(belief, self.clock())))

    def contradictory(self, proposition):
        with self.lock:
            belief = self.beliefs.get(proposition)
            return bool(belief and belief['support'] and belief['contradict'])

    def hypotheses(self, prefix):
        """Competing explanations are kept side by side, never collapsed into one claim."""
        with self.lock:
            names = [name for name in self.beliefs if name.startswith(prefix)]
        return sorted(((name, self.probability(name)) for name in names), key=lambda row: -row[1])

    def evidence(self, proposition):
        with self.lock:
            belief = self.beliefs.get(proposition)
            return list(belief['evidence']) if belief else []

    def snapshot(self, limit=12):
        with self.lock:
            names = list(self.beliefs)
        rows = [{'proposition': n, 'p': round(self.probability(n), 3), 'kind': self.beliefs[n]['kind'],
                 'support': self.beliefs[n]['support'], 'contradict': self.beliefs[n]['contradict']} for n in names]
        return sorted(rows, key=lambda r: -abs(r['p'] - .5))[:limit]

    def export(self):
        with self.lock:
            return {k: {**v, 'evidence': list(v['evidence'])} for k, v in self.beliefs.items()}

    def load(self, rows):
        with self.lock:
            for name, row in (rows or {}).items():
                try:
                    self.beliefs[name] = {**row, 'evidence': deque(row.get('evidence', [])[-12:], maxlen=12),
                                          'log_odds': float(row['log_odds']), 'prior': float(row['prior']),
                                          'updated': float(row['updated']), 'half_life': float(row['half_life'])}
                except (KeyError, TypeError, ValueError):
                    continue  # A damaged row is dropped, never guessed.


def entropy(p):
    """Binary entropy in bits; 0 for certainty, 1 at 50/50."""
    if p is None:
        return 1.
    p = min(1 - 1e-9, max(1e-9, p))
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


class AwarenessStore:
    """Local SQLite WAL store for important observations, predictions, suggestions and learned policy."""

    def __init__(self, path, clock=time.time):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=2)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, at REAL, type TEXT, category TEXT,
                source TEXT, project TEXT, application TEXT, task TEXT, data TEXT, expires REAL);
            CREATE TABLE IF NOT EXISTS predictions (id TEXT PRIMARY KEY, kind TEXT, subject TEXT, created REAL,
                horizon REAL, raw REAL, probability REAL, data TEXT, resolved REAL, outcome INTEGER);
            CREATE TABLE IF NOT EXISTS suggestions (number INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE,
                fingerprint TEXT, situation TEXT, action TEXT, created REAL, status TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS experience (situation TEXT, action TEXT, useful REAL, useless REAL,
                updated REAL, PRIMARY KEY (situation, action));
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX IF NOT EXISTS observation_time ON observations(at);
            CREATE INDEX IF NOT EXISTS suggestion_fp ON suggestions(fingerprint);
        ''')
        self.db.commit()

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                yield self.db
                self.db.commit()
            except BaseException:
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

    def put_observation(self, observation, days):
        """Only non-private observations with day retention are persisted, and they expire."""
        if observation.retention != 'days' or observation.sensitivity == 'private' or days <= 0:
            return False
        with self.transaction() as db:
            db.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (observation.id, observation.at, observation.type, observation.category, observation.source,
                        observation.project, observation.application, observation.task,
                        json.dumps({**asdict(observation), 'values': observation.public_values()}, default=str),
                        observation.at + days * 86400))
        return True

    def observations(self, since=0, kind_prefix='', limit=200):
        with self.lock:
            rows = self.db.execute('SELECT data FROM observations WHERE at>=? AND type LIKE ? ORDER BY at DESC LIMIT ?',
                                   (since, kind_prefix + '%', int(limit))).fetchall()
        return [json.loads(r[0]) for r in rows]

    def purge(self, category=None):
        with self.transaction() as db:
            if category is None:
                return db.execute('DELETE FROM observations WHERE expires<?', (self.clock(),)).rowcount
            if category == 'all':
                return db.execute('DELETE FROM observations').rowcount
            return db.execute('DELETE FROM observations WHERE category=?', (category,)).rowcount

    def add_prediction(self, row):
        with self.transaction() as db:
            db.execute('INSERT INTO predictions VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (row['id'], row['kind'], row['subject'], row['created'], row['horizon'], row['raw'],
                        row['probability'], json.dumps(row, default=str), None, None))

    def open_predictions(self):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM predictions WHERE resolved IS NULL')]

    def resolve_prediction(self, identity, happened, note=''):
        with self.transaction() as db:
            row = db.execute('SELECT data FROM predictions WHERE id=? AND resolved IS NULL', (identity,)).fetchone()
            if not row:
                return None
            data = {**json.loads(row[0]), 'outcome': bool(happened), 'outcome_note': _bounded_text(note, 200),
                    'resolved': self.clock()}
            db.execute('UPDATE predictions SET resolved=?, outcome=?, data=? WHERE id=?',
                       (data['resolved'], int(bool(happened)), json.dumps(data, default=str), identity))
            return data

    def resolved_predictions(self, kind=None, limit=500):
        with self.lock:
            query = 'SELECT data FROM predictions WHERE resolved IS NOT NULL' + (' AND kind=?' if kind else '') + \
                    ' ORDER BY resolved DESC LIMIT ?'
            rows = self.db.execute(query, ((kind,) if kind else ()) + (int(limit),)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def add_suggestion(self, row):
        with self.transaction() as db:
            cursor = db.execute('INSERT INTO suggestions(id,fingerprint,situation,action,created,status,data) VALUES(?,?,?,?,?,?,?)',
                                (row['id'], row['fingerprint'], row['situation'], row['action'], row['created'],
                                 row['status'], json.dumps(row, default=str)))
            return cursor.lastrowid

    def suggestion(self, identity=None, number=None):
        with self.lock:
            row = self.db.execute('SELECT number, data FROM suggestions WHERE id=? OR number=?', (identity, number)).fetchone()
        return {**json.loads(row[1]), 'number': row[0]} if row else None

    def update_suggestion(self, identity, **changes):
        with self.transaction() as db:
            row = db.execute('SELECT data FROM suggestions WHERE id=?', (identity,)).fetchone()
            if not row:
                return None
            data = {**json.loads(row[0]), **changes}
            db.execute('UPDATE suggestions SET status=?, data=? WHERE id=?', (data['status'], json.dumps(data, default=str), identity))
            return data

    def suggestions(self, since=0, fingerprint=None, limit=50):
        with self.lock:
            query, args = 'SELECT number, data FROM suggestions WHERE created>=?', [since]
            if fingerprint:
                query += ' AND fingerprint=?'
                args.append(fingerprint)
            rows = self.db.execute(query + ' ORDER BY number DESC LIMIT ?', (*args, int(limit))).fetchall()
        return [{**json.loads(r[1]), 'number': r[0]} for r in rows]

    def experience(self, situation, action):
        with self.lock:
            row = self.db.execute('SELECT useful, useless FROM experience WHERE situation=? AND action=?', (situation, action)).fetchone()
        return (row[0], row[1]) if row else (0., 0.)

    def record_experience(self, situation, action, useful, weight=1.):
        with self.transaction() as db:
            db.execute('INSERT OR IGNORE INTO experience VALUES(?,?,0,0,?)', (situation, action, self.clock()))
            column = 'useful' if useful else 'useless'
            db.execute(f'UPDATE experience SET {column}={column}+?, updated=? WHERE situation=? AND action=?',
                       (float(weight), self.clock(), situation, action))

    def experience_rows(self):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT * FROM experience ORDER BY updated DESC LIMIT 200')]

    def close(self):
        with self.lock:
            self.db.close()
