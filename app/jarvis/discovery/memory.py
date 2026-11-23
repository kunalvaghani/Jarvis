"""Typed scientific records in the existing brain Journal, never a new database.

Artifacts are authoritative. Tables below index immutable artifact references. Down
migration deactivates the extension without deleting any scientific history.
"""
from __future__ import annotations

import json
from typing import Any
from .contracts import Edge, RECORD, bounded_json

SCHEMA = (
    'CREATE TABLE IF NOT EXISTS discovery_schema (version INTEGER PRIMARY KEY, enabled INTEGER NOT NULL)',
    'CREATE TABLE IF NOT EXISTS discovery_records (id TEXT NOT NULL, revision INTEGER NOT NULL, '
    'kind TEXT NOT NULL, ref TEXT NOT NULL, PRIMARY KEY(id,revision))',
    'CREATE TABLE IF NOT EXISTS discovery_edges (source TEXT NOT NULL, source_revision INTEGER NOT NULL, '
    'target TEXT NOT NULL, target_revision INTEGER NOT NULL, relation TEXT NOT NULL, ref TEXT NOT NULL, '
    'PRIMARY KEY(source,source_revision,target,target_revision,relation))',
)


class LabMemory:
    def __init__(self, journal: Any):
        self.journal = journal  # Caller owns lifecycle, path, WAL and transaction policy.

    def migrate(self) -> None:
        with self.journal.tx() as db:
            for statement in SCHEMA:
                db.execute(statement)
            if db.execute('SELECT COUNT(*) FROM discovery_schema WHERE version != 1').fetchone()[0]:
                raise ValueError('unsupported scientific memory schema version')
            db.execute('INSERT INTO discovery_schema VALUES (1,1) ON CONFLICT(version) DO UPDATE SET enabled=1')

    def deactivate(self) -> None:
        """Reversible logical down migration: retain every record and artifact."""
        with self.journal.tx() as db:
            db.execute('UPDATE discovery_schema SET enabled=0 WHERE version=1')

    def _ready(self) -> None:
        rows = self.journal.rows('SELECT enabled FROM discovery_schema WHERE version=1')
        if not rows or rows[0]['enabled'] != 1:
            raise ValueError('scientific memory extension is inactive')

    def put(self, record: Any) -> str:
        self._ready()
        value = RECORD.validate_json(record.model_dump_json() if hasattr(record, 'model_dump_json') else
                                     json.dumps(record, allow_nan=False))
        text = bounded_json(value.model_dump(mode='json'))
        # Journal.put performs the shared credential rejection before any index write.
        ref = self.journal.put(text, data_type='Report')
        with self.journal.tx() as db:
            old = db.execute('SELECT ref FROM discovery_records WHERE id=? AND revision=?',
                             (value.id, value.revision)).fetchone()
            if old and old[0] != ref:
                raise ValueError('scientific revisions are immutable; create a new revision')
            db.execute('INSERT OR IGNORE INTO discovery_records VALUES (?,?,?,?)',
                       (value.id, value.revision, value.kind, ref))
        from .memory_graph import index_ready
        index_ready(self, value)
        return ref

    def resolve(self, query: str, kind: str):
        """Reuse Jarvis's name ranking; return every ambiguous typed candidate."""
        from .memory_graph import resolve
        return resolve(self, query, kind)

    def get(self, identity: str, revision: int | None = None):
        sql = 'SELECT ref FROM discovery_records WHERE id=? '
        args = (identity, revision) if revision is not None else (identity,)
        rows = self.journal.rows(sql + ('AND revision=?' if revision is not None else
                                       'ORDER BY revision DESC LIMIT 1'), args)
        if not rows:
            return None
        return RECORD.validate_json(self.journal.get(rows[0]['ref']))

    def list(self, kind: str, limit: int = 50):
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('bounded memory limit must be 1..200')
        rows = self.journal.rows('SELECT r.ref FROM discovery_records r WHERE r.kind=? AND r.revision='
                                 '(SELECT MAX(n.revision) FROM discovery_records n WHERE n.id=r.id) ORDER BY r.id LIMIT ?',
                                 (kind, limit))
        return [RECORD.validate_json(self.journal.get(row['ref'])) for row in rows]

    def link(self, edge: Edge) -> str:
        self._ready()
        if not isinstance(edge, Edge):
            raise TypeError('scientific relations require a validated Edge')
        if self.get(edge.source, edge.source_revision) is None or self.get(edge.target, edge.target_revision) is None:
            raise ValueError('scientific relation has a dangling endpoint')
        ref = self.journal.put(bounded_json(edge.model_dump(mode='json')), data_type='Report')
        with self.journal.tx() as db:
            old = db.execute('SELECT ref FROM discovery_edges WHERE source=? AND source_revision=? '
                             'AND target=? AND target_revision=? AND relation=?',
                             (edge.source, edge.source_revision, edge.target, edge.target_revision, edge.relation)).fetchone()
            if old and old[0] != ref:
                raise ValueError('scientific relation evidence is immutable')
            db.execute('INSERT OR IGNORE INTO discovery_edges VALUES (?,?,?,?,?,?)',
                       (edge.source, edge.source_revision, edge.target, edge.target_revision, edge.relation, ref))
        return ref

    def index_reference(self, bank: Any, identity: str, revision: int) -> None:
        """Reference-only retrieval index in existing ReasoningBank; no copied scientific body.

        Kept separate from its strategy/anti-pattern induction and embedding semantics.
        This optional index can always be rebuilt from Journal artifacts.
        """
        row = self.get(identity, revision)
        if row is None:
            raise ValueError('cannot index missing scientific evidence')
        ref = self.journal.rows('SELECT ref FROM discovery_records WHERE id=? AND revision=?',
                                (identity, revision))[0]['ref']
        with bank.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS discovery_references '
                       '(id TEXT, revision INTEGER, kind TEXT, ref TEXT, PRIMARY KEY(id,revision))')
            db.execute('INSERT OR IGNORE INTO discovery_references VALUES (?,?,?,?)',
                       (identity, revision, row.kind, ref))
