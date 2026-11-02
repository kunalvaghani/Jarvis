"""The brain journal: one SQLite WAL file, the source of truth for everything the brain does.

Tables: capability-graph versions, neuron proposals, signals (append-only, causal), the outbox (one row per side
effect, keyed by idempotency key, written *before* the effect), artifacts (payloads referenced by signals), goals,
shadow routes and verified route statistics. The UI and Obsidian only ever read from here.

Text is redacted before it is stored (``jarvis.tools.redact``); artifacts marked secret are refused outright.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .contracts import Neuron, Signal, artifact_ref, digest, utc_now

APP = Path(__file__).resolve().parents[2]
DEFAULT = APP / '.jarvis-runtime' / 'brain' / 'journal.sqlite3'
MAX_ARTIFACT = 2_000_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_versions (version INTEGER PRIMARY KEY AUTOINCREMENT, digest TEXT UNIQUE NOT NULL,
    created TEXT NOT NULL, neurons INTEGER NOT NULL, synapses INTEGER NOT NULL, snapshot TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proposals (node_id TEXT PRIMARY KEY, neuron TEXT NOT NULL, built_from TEXT NOT NULL,
    by TEXT NOT NULL, status TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS goals (goal_id TEXT PRIMARY KEY, text TEXT NOT NULL, state TEXT NOT NULL, created TEXT NOT NULL,
    updated TEXT NOT NULL, graph_version INTEGER, stop_reason TEXT, plan TEXT);
CREATE TABLE IF NOT EXISTS signals (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
    goal_id TEXT NOT NULL, type TEXT NOT NULL, body TEXT NOT NULL, at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS signals_goal ON signals(goal_id, seq);
CREATE TABLE IF NOT EXISTS outbox (idempotency_key TEXT PRIMARY KEY, goal_id TEXT NOT NULL, node_id TEXT NOT NULL,
    state TEXT NOT NULL, event_id TEXT, result_ref TEXT, detail TEXT, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts (ref TEXT PRIMARY KEY, data_type TEXT, privacy TEXT NOT NULL, body TEXT NOT NULL,
    created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shadow_routes (seq INTEGER PRIMARY KEY AUTOINCREMENT, goal_id TEXT NOT NULL, at TEXT NOT NULL,
    proposed TEXT NOT NULL, actual TEXT NOT NULL DEFAULT '[]', outcome TEXT);
CREATE TABLE IF NOT EXISTS route_stats (context TEXT NOT NULL, node_id TEXT NOT NULL, successes INTEGER NOT NULL DEFAULT 0,
    failures INTEGER NOT NULL DEFAULT 0, latencies TEXT NOT NULL DEFAULT '[]', updated TEXT NOT NULL,
    PRIMARY KEY (context, node_id));
"""
OUTBOX_STATES = ('pending', 'done', 'failed', 'uncertain', 'cancelled')


def _redact(text: Any) -> str:
    from ..tools import redact
    return str(redact(text if isinstance(text, str) else json.dumps(text, default=str, sort_keys=True)))


class SecretPayload(ValueError):
    """An artifact that holds a credential is never stored or passed along."""


class Journal:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False, timeout=10, isolation_level=None)
        self._db.execute('PRAGMA journal_mode=WAL')
        self._db.execute('PRAGMA synchronous=NORMAL')
        self._db.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._db.execute('BEGIN IMMEDIATE')
            try:
                yield self._db
            except BaseException:
                self._db.execute('ROLLBACK')
                raise
            self._db.execute('COMMIT')

    def rows(self, sql: str, args: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._db.execute(sql, args)
            names = [c[0] for c in cursor.description or ()]
            return [dict(zip(names, row)) for row in cursor.fetchall()]

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # Capability graph versions -------------------------------------------------------------------------------
    def save_graph(self, snapshot: Dict[str, Any]) -> int:
        """Store a graph snapshot if it differs from every earlier one; returns its version number."""
        key = digest(snapshot)
        with self.tx() as db:
            row = db.execute('SELECT version FROM graph_versions WHERE digest=?', (key,)).fetchone()
            if row:
                return int(row[0])
            cursor = db.execute('INSERT INTO graph_versions (digest, created, neurons, synapses, snapshot) '
                                'VALUES (?,?,?,?,?)', (key, utc_now(), len(snapshot.get('neurons', [])),
                                                       len(snapshot.get('synapses', [])), json.dumps(snapshot)))
            return int(cursor.lastrowid or 0)

    def graph(self, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        sql = 'SELECT version, snapshot FROM graph_versions ' + ('WHERE version=?' if version else
                                                                   'ORDER BY version DESC LIMIT 1')
        rows = self.rows(sql, (version,) if version else ())
        if not rows:
            return None
        return {'version': rows[0]['version'], **json.loads(rows[0]['snapshot'])}

    def versions(self) -> List[Dict[str, Any]]:
        return self.rows('SELECT version, digest, created, neurons, synapses FROM graph_versions ORDER BY version')

    # Proposals ---------------------------------------------------------------------------------------------
    def save_proposal(self, neuron: Neuron, built_from: List[str], by: str) -> None:
        with self.tx() as db:
            old = db.execute('SELECT built_from FROM proposals WHERE node_id=?', (neuron.node_id,)).fetchone()
            built = built_from or (json.loads(old[0]) if old else [])
            db.execute('INSERT OR REPLACE INTO proposals VALUES (?,?,?,?,?,?)',
                       (neuron.node_id, neuron.model_dump_json(), json.dumps(built), by, neuron.status, utc_now()))

    def proposals(self) -> List[Dict[str, Any]]:
        return [json.loads(r['neuron']) for r in self.rows('SELECT neuron FROM proposals ORDER BY updated')]

    def withdraw(self, node_id: str) -> bool:
        with self.tx() as db:
            return db.execute('DELETE FROM proposals WHERE node_id=?', (node_id,)).rowcount > 0

    # Goals and signals -------------------------------------------------------------------------------------
    def open_goal(self, goal_id: str, text: str, graph_version: int, plan: Any = None) -> None:
        now = utc_now()
        with self.tx() as db:
            db.execute('INSERT OR IGNORE INTO goals VALUES (?,?,?,?,?,?,?,?)',
                       (goal_id, _redact(text)[:2000], 'open', now, now, graph_version, None,
                        None if plan is None else _redact(plan)))

    def close_goal(self, goal_id: str, state: str, stop_reason: str) -> None:
        with self.tx() as db:
            db.execute('UPDATE goals SET state=?, stop_reason=?, updated=? WHERE goal_id=?',
                       (state, _redact(stop_reason)[:1000], utc_now(), goal_id))

    def goal(self, goal_id: str) -> Optional[Dict[str, Any]]:
        rows = self.rows('SELECT * FROM goals WHERE goal_id=?', (goal_id,))
        return rows[0] if rows else None

    def open_goals(self) -> List[Dict[str, Any]]:
        return self.rows("SELECT * FROM goals WHERE state='open' ORDER BY created")

    def emit(self, signal: Signal) -> Signal:
        """Append a signal. Duplicate event ids are ignored (a replayed signal never fires twice)."""
        body = signal.model_dump(mode='json')
        body['note'] = _redact(body.get('note', ''))[:400]
        with self.tx() as db:
            db.execute('INSERT OR IGNORE INTO signals (event_id, goal_id, type, body, at) VALUES (?,?,?,?,?)',
                       (signal.event_id, signal.goal_id, signal.type, json.dumps(body), signal.timestamp_utc))
        return signal

    def signals(self, goal_id: Optional[str] = None, after: int = 0, limit: int = 500) -> List[Dict[str, Any]]:
        sql = 'SELECT seq, body FROM signals WHERE seq>? ' + ('AND goal_id=? ' if goal_id else '') + \
              'ORDER BY seq LIMIT ?'
        args: Tuple[Any, ...] = (after, goal_id, limit) if goal_id else (after, limit)
        return [{'seq': r['seq'], **json.loads(r['body'])} for r in self.rows(sql, args)]

    # Outbox: journal before side effects -------------------------------------------------------------------
    def claim(self, key: str, goal_id: str, node_id: str, event_id: str) -> Optional[Dict[str, Any]]:
        """Record intent to act. Returns the earlier row if this key was already claimed (never act twice)."""
        with self.tx() as db:
            row = db.execute('SELECT state, result_ref, detail FROM outbox WHERE idempotency_key=?', (key,)).fetchone()
            if row:
                return {'state': row[0], 'result_ref': row[1], 'detail': row[2]}
            db.execute('INSERT INTO outbox VALUES (?,?,?,?,?,?,?,?)',
                       (key, goal_id, node_id, 'pending', event_id, None, None, utc_now()))
        return None

    def settle(self, key: str, state: str, result_ref: Optional[str] = None, detail: str = '') -> None:
        if state not in OUTBOX_STATES:
            raise ValueError(state)
        with self.tx() as db:
            db.execute('UPDATE outbox SET state=?, result_ref=?, detail=?, updated=? WHERE idempotency_key=?',
                       (state, result_ref, _redact(detail)[:1000], utc_now(), key))

    def pending(self) -> List[Dict[str, Any]]:
        return self.rows("SELECT * FROM outbox WHERE state='pending' ORDER BY updated")

    # Artifacts ---------------------------------------------------------------------------------------------
    def put(self, data: Any, data_type: Optional[str] = None, privacy: str = 'local_private') -> str:
        text = data if isinstance(data, str) else json.dumps(data, default=str, sort_keys=True)
        if _redact(text) != text:
            raise SecretPayload('the payload holds a credential; it is not stored or passed on')
        text = text[:MAX_ARTIFACT]
        ref = artifact_ref(text)
        with self.tx() as db:
            db.execute('INSERT OR IGNORE INTO artifacts VALUES (?,?,?,?,?)', (ref, data_type, privacy, text, utc_now()))
        return ref

    def get(self, ref: str) -> Optional[str]:
        rows = self.rows('SELECT body FROM artifacts WHERE ref=?', (ref,))
        return rows[0]['body'] if rows else None

    # Shadow routes -----------------------------------------------------------------------------------------
    def shadow(self, goal_id: str, proposed: Any) -> None:
        with self.tx() as db:
            db.execute('INSERT INTO shadow_routes (goal_id, at, proposed) VALUES (?,?,?)',
                       (goal_id, utc_now(), _redact(proposed)))

    def shadow_actual(self, goal_id: str, tool: str) -> None:
        with self.tx() as db:
            row = db.execute('SELECT seq, actual FROM shadow_routes WHERE goal_id=? ORDER BY seq DESC LIMIT 1',
                             (goal_id,)).fetchone()
            if row:
                actual = json.loads(row[1])
                if len(actual) < 200:
                    actual.append(tool)
                db.execute('UPDATE shadow_routes SET actual=? WHERE seq=?', (json.dumps(actual), row[0]))

    def shadow_outcome(self, goal_id: str, outcome: str) -> None:
        with self.tx() as db:
            db.execute('UPDATE shadow_routes SET outcome=? WHERE goal_id=? AND outcome IS NULL', (outcome, goal_id))

    def judge_latest(self, outcome: str) -> Optional[str]:
        """An independent check (a live-test oracle) judged the latest shadowed goal. Returns its goal id."""
        if outcome not in ('verified', 'failed'):
            raise ValueError(outcome)
        with self.tx() as db:
            row = db.execute('SELECT seq, goal_id FROM shadow_routes ORDER BY seq DESC LIMIT 1').fetchone()
            if row is None:
                return None
            db.execute('UPDATE shadow_routes SET outcome=? WHERE seq=?', (outcome, row[0]))
            return str(row[1])

    def shadow_rows(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.rows('SELECT * FROM shadow_routes ORDER BY seq DESC LIMIT ?', (limit,))
        for row in rows:
            row['proposed'], row['actual'] = json.loads(row['proposed']), json.loads(row['actual'])
        return rows

    # Verified route statistics (Phase 4 plasticity reads and writes these) ---------------------------------
    def record_outcome(self, context: str, node_id: str, verified: bool, seconds: Optional[float] = None) -> None:
        with self.tx() as db:
            row = db.execute('SELECT successes, failures, latencies FROM route_stats WHERE context=? AND node_id=?',
                             (context, node_id)).fetchone()
            ok, bad, lat = (row[0], row[1], json.loads(row[2])) if row else (0, 0, [])
            if seconds is not None:
                lat = (lat + [round(float(seconds), 2)])[-50:]
            db.execute('INSERT OR REPLACE INTO route_stats VALUES (?,?,?,?,?,?)',
                       (context, node_id, ok + int(verified), bad + int(not verified), json.dumps(lat), utc_now()))

    def stats(self, context: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = 'SELECT * FROM route_stats' + (' WHERE context=?' if context else '')
        rows = self.rows(sql, (context,) if context else ())
        for row in rows:
            row['latencies'] = json.loads(row['latencies'])
        return rows
