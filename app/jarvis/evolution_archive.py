"""Darwin Gödel Machine-style evolutionary archive for Jarvis candidates (Pillar C).

Adapted from the method of the Darwin Gödel Machine (jennyzzt/dgm, Apache-2.0; arXiv 2505.22954):
an open-ended archive keeps every evaluated variant with its lineage, and parents are drawn
with probability proportional to a sigmoid of their score times 1/(1 + children), so strong
but under-explored variants are preferred while weaker ones keep a chance (DGM's
``score_child_prop``). DGM checkpoints the archive per generation in ``dgm_metadata.jsonl``;
here a SQLite archive records each candidate and each experiment stage instead. No DGM code
is copied. Differences: candidates are bounded surface mutations (not free-form agent code),
fitness is multi-objective with a Pareto front, and nothing in the archive deploys anything.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import sqlite3
import uuid

STATUSES = {'seed', 'running', 'evaluated', 'qualified', 'retained', 'rejected', 'quarantined', 'discarded',
            'interrupted', 'proposed', 'deployed', 'rolled_back', 'deploy_failed'}
SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates(
  id TEXT PRIMARY KEY, parent_id TEXT, surface TEXT NOT NULL, generation INTEGER NOT NULL,
  mutation_type TEXT NOT NULL, mutation_json TEXT NOT NULL, files_json TEXT NOT NULL,
  source_commit TEXT NOT NULL, lab_commit TEXT, values_json TEXT NOT NULL, values_digest TEXT NOT NULL,
  hypothesis TEXT, status TEXT NOT NULL, fitness_json TEXT, gate_json TEXT, failure_reason TEXT,
  diversity REAL, environment_json TEXT, seed INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(parent_id) REFERENCES candidates(id));
CREATE INDEX IF NOT EXISTS candidates_surface ON candidates(surface, status);
CREATE TABLE IF NOT EXISTS runs(
  id TEXT PRIMARY KEY, candidate_id TEXT, stage TEXT NOT NULL, state_json TEXT NOT NULL,
  started_at TEXT NOT NULL, updated_at TEXT NOT NULL, finished INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
VERSION = 1


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class EvolutionArchive:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript(SCHEMA)
            stored = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if stored and int(stored[0]) != VERSION:
                raise ValueError('Unsupported evolution archive schema version: ' + stored[0])
            db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)", (str(VERSION),))
            db.commit()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    # ---- candidates --------------------------------------------------------------------------------------------------
    def add(self, surface, values, values_digest, source_commit, parent_id=None, mutation_type='seed', mutation=None,
            files=(), hypothesis='', status='seed', seed=None, environment=None):
        if status not in STATUSES:
            raise ValueError('Unknown candidate status.')
        identifier = 'cand_' + uuid.uuid4().hex[:12]
        with closing(self.connect()) as db, db:
            generation = 0
            if parent_id is not None:
                parent = db.execute('SELECT generation, surface FROM candidates WHERE id=?', (parent_id,)).fetchone()
                if parent is None or parent['surface'] != surface:
                    raise ValueError('Parent candidate is missing or belongs to another surface.')
                generation = parent['generation'] + 1
            db.execute('INSERT INTO candidates(id, parent_id, surface, generation, mutation_type, mutation_json, files_json,'
                       ' source_commit, values_json, values_digest, hypothesis, status, environment_json, seed, created_at,'
                       ' updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (identifier, parent_id, surface, generation, mutation_type, json.dumps(mutation or {}),
                        json.dumps(list(files)), source_commit, json.dumps(values, sort_keys=True), values_digest,
                        hypothesis[:1000], status, json.dumps(environment or {}), seed, now(), now()))
        return identifier

    def update(self, identifier, **fields):
        allowed = {'status', 'fitness', 'gate', 'failure_reason', 'diversity', 'lab_commit', 'environment'}
        if set(fields) - allowed:
            raise ValueError('Unknown archive fields: ' + ', '.join(sorted(set(fields) - allowed)))
        if 'status' in fields and fields['status'] not in STATUSES:
            raise ValueError('Unknown candidate status.')
        columns = {'fitness': 'fitness_json', 'gate': 'gate_json', 'environment': 'environment_json'}
        assignments, values = [], []
        for key, value in fields.items():
            assignments.append(columns.get(key, key) + '=?')
            values.append(json.dumps(value, sort_keys=True) if key in columns else value)
        with closing(self.connect()) as db, db:
            changed = db.execute('UPDATE candidates SET ' + ', '.join(assignments) + ', updated_at=? WHERE id=?',
                                 (*values, now(), identifier)).rowcount
        if not changed:
            raise ValueError('Unknown candidate: ' + identifier)

    def get(self, identifier):
        with closing(self.connect()) as db:
            row = db.execute('SELECT * FROM candidates WHERE id=?', (identifier,)).fetchone()
        return self._row(row) if row else None

    def candidates(self, surface=None, statuses=None):
        query, args = 'SELECT * FROM candidates', []
        clauses = []
        if surface:
            clauses.append('surface=?')
            args.append(surface)
        if statuses:
            clauses.append('status IN (' + ','.join('?' * len(statuses)) + ')')
            args.extend(statuses)
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        with closing(self.connect()) as db:
            return [self._row(r) for r in db.execute(query + ' ORDER BY created_at, id', args)]

    @staticmethod
    def _row(row):
        data = dict(row)
        for key in ('mutation_json', 'files_json', 'values_json', 'fitness_json', 'gate_json', 'environment_json'):
            data[key[:-5]] = json.loads(data.pop(key)) if data.get(key) else None
        return data

    def lineage(self, identifier):
        chain, seen = [], set()
        while identifier and identifier not in seen:
            seen.add(identifier)
            row = self.get(identifier)
            if row is None:
                break
            chain.append(row)
            identifier = row['parent_id']
        return chain

    def children_count(self, identifier):
        with closing(self.connect()) as db:
            return db.execute('SELECT COUNT(*) FROM candidates WHERE parent_id=?', (identifier,)).fetchone()[0]

    # ---- selection, diversity and retention --------------------------------------------------------------------------
    def eligible_parents(self, surface):
        """Seeds and variants that passed every hard gate (qualified, retained or deployed)."""
        return [row for row in self.candidates(surface, ['seed', 'qualified', 'retained', 'deployed'])]

    def select_parent(self, surface, rng=None, objective_key='train_score'):
        """DGM ``score_child_prop``: sigmoid(score) x 1/(1 + children), sampled with a seeded RNG."""
        rows = self.eligible_parents(surface)
        if not rows:
            raise ValueError('No eligible parent for surface ' + surface)
        rng = rng or random.Random(0)
        scores = [((row.get('fitness') or {}).get(objective_key)) for row in rows]
        known = [s for s in scores if isinstance(s, (int, float))]
        low, high = (min(known), max(known)) if known else (0., 1.)
        weights = []
        for row, score in zip(rows, scores):
            normalized = .5 if not isinstance(score, (int, float)) or high == low else (score - low) / (high - low)
            weights.append(1 / (1 + math.exp(-10 * (normalized - .5))) / (1 + self.children_count(row['id'])))
        return rng.choices(rows, weights=weights, k=1)[0]

    def diversity(self, surface, values, distance):
        """Distance to the nearest archived variant of the surface (0 means a duplicate)."""
        others = [row['values'] for row in self.candidates(surface)]
        return min((distance(surface, values, other) for other in others), default=1.)

    def pareto_front(self, surface, objectives):
        """Non-dominated evaluated variants; objectives maps fitness key -> 'max' | 'min'."""
        rows = [r for r in self.candidates(surface) if r.get('fitness') and r['status'] not in {'quarantined', 'interrupted'}]
        def better_or_equal(a, b):
            return all((a['fitness'].get(k, -math.inf) >= b['fitness'].get(k, -math.inf)) if d == 'max' else
                       (a['fitness'].get(k, math.inf) <= b['fitness'].get(k, math.inf)) for k, d in objectives.items())
        def strictly(a, b):
            return better_or_equal(a, b) and any(a['fitness'].get(k) != b['fitness'].get(k) for k in objectives)
        return [r for r in rows if not any(strictly(o, r) for o in rows if o['id'] != r['id'])]

    # ---- experiment checkpoints --------------------------------------------------------------------------------------
    def checkpoint(self, run_id, stage, state, candidate_id=None, finished=False):
        with closing(self.connect()) as db, db:
            db.execute('INSERT INTO runs(id, candidate_id, stage, state_json, started_at, updated_at, finished)'
                       ' VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET candidate_id=COALESCE(excluded.candidate_id,'
                       ' runs.candidate_id), stage=excluded.stage, state_json=excluded.state_json,'
                       ' updated_at=excluded.updated_at, finished=excluded.finished',
                       (run_id, candidate_id, stage, json.dumps(state, sort_keys=True), now(), now(), int(finished)))

    def unfinished_runs(self):
        with closing(self.connect()) as db:
            rows = db.execute('SELECT * FROM runs WHERE finished=0 ORDER BY started_at').fetchall()
        return [{**dict(r), 'state': json.loads(r['state_json'])} for r in rows]

    def summary(self):
        with closing(self.connect()) as db:
            counts = db.execute('SELECT surface, status, COUNT(*) AS n FROM candidates GROUP BY surface, status').fetchall()
        result = {}
        for row in counts:
            result.setdefault(row['surface'], {})[row['status']] = row['n']
        return result
