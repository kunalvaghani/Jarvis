"""Durable command admission and validated lifecycle, separate from tool checkpoints.

Only metadata transactions are retried by SQLite. No external effect is replayed here.
"""
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

TERMINAL = {'COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED'}
WAITING = {'WAITING_DEPENDENCY', 'WAITING_APPROVAL', 'WAITING_USER', 'PAUSED', 'RETRY_BACKOFF'}
STATES = TERMINAL | WAITING | {'RECEIVED', 'CLASSIFYING', 'QUEUED', 'READY', 'RUNNING', 'VERIFYING'}
EDGES = {
    'RECEIVED': {'CLASSIFYING', 'CANCELLED'},
    'CLASSIFYING': {'QUEUED', 'COMPLETED', 'PARTIAL', 'FAILED', 'WAITING_USER', 'CANCELLED'},
    'QUEUED': {'READY', 'RUNNING', 'WAITING_DEPENDENCY', 'WAITING_APPROVAL', 'PAUSED', 'CANCELLED'},
    'READY': {'RUNNING', 'WAITING_DEPENDENCY', 'PAUSED', 'CANCELLED'},
    'RUNNING': {'VERIFYING', 'WAITING_USER', 'WAITING_APPROVAL', 'PAUSED', 'RETRY_BACKOFF', 'FAILED', 'CANCELLED', 'PARTIAL'},
    'VERIFYING': TERMINAL | {'WAITING_USER', 'WAITING_APPROVAL', 'PAUSED', 'RETRY_BACKOFF'},
    'WAITING_DEPENDENCY': {'QUEUED', 'FAILED', 'CANCELLED', 'PAUSED'},
    'WAITING_APPROVAL': {'QUEUED', 'RUNNING', 'PARTIAL', 'CANCELLED'},
    'WAITING_USER': {'QUEUED', 'CANCELLED', 'PARTIAL'},
    'PAUSED': {'QUEUED', 'CANCELLED', 'PARTIAL'},
    'RETRY_BACKOFF': {'QUEUED', 'CANCELLED', 'FAILED'},
}


class TaskStore:
    def __init__(self, path, clock=time.time, capacity=512):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.clock, self.capacity = clock, capacity
        self.lock = threading.RLock()
        self.local = threading.local()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=2)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS tasks (
                number INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                idem TEXT UNIQUE NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                state TEXT NOT NULL, command TEXT NOT NULL, original TEXT NOT NULL DEFAULT '{}', spec TEXT NOT NULL DEFAULT '{}',
                retries INTEGER NOT NULL DEFAULT 0, outcome TEXT NOT NULL DEFAULT '',
                checkpoint TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY, task TEXT NOT NULL, at REAL NOT NULL,
                state TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY, task TEXT NOT NULL, data TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS task_state ON tasks(state);
        ''')
        self.db.commit()

    @contextmanager
    def transaction(self):
        with self.lock:
            outer = not getattr(self.local, 'transaction', False)
            if outer:
                self.db.execute('BEGIN IMMEDIATE')
                self.local.transaction = True
            try:
                yield
                if outer:
                    self.db.commit()
            except BaseException:
                if outer:
                    self.db.rollback()
                raise
            finally:
                if outer:
                    self.local.transaction = False

    @staticmethod
    def decode(row):
        if row is None:
            return None
        row = dict(row)
        for key in ('command', 'original', 'spec', 'checkpoint'):
            row[key] = json.loads(row[key])
        return row

    def get(self, identity):
        with self.lock:
            return self.decode(self.db.execute('SELECT * FROM tasks WHERE id=?', (identity,)).fetchone())

    def rows(self, active=False, limit=None, since=0):
        with self.lock:
            query, args = 'SELECT * FROM tasks WHERE number>=?', [since]
            if active:
                query += " AND state NOT IN ('COMPLETED','PARTIAL','FAILED','CANCELLED')"
            query += ' ORDER BY number DESC'
            if limit is not None:
                query += ' LIMIT ?';args.append(int(limit))
            return list(reversed([self.decode(row) for row in self.db.execute(query,args)]))

    def counts(self):
        with self.lock:
            return dict(self.db.execute('SELECT state,count(*) FROM tasks GROUP BY state').fetchall())

    def admit(self, command, key=None):
        """Caller-provided event identity deduplicates retries; repeated intent is allowed."""
        if not isinstance(command, dict) or set(command) != {'kind','value','extra'} or any(not isinstance(v,str) or len(v)>100000 for v in command.values()):
            raise ValueError('A command must contain bounded string fields')
        key = key or uuid.uuid4().hex
        with self.transaction():
            previous = self.db.execute('SELECT id FROM tasks WHERE idem=?', (key,)).fetchone()
            if previous:
                return previous[0], False
            count = self.db.execute("SELECT count(*) FROM tasks WHERE state NOT IN ('COMPLETED','PARTIAL','FAILED','CANCELLED')").fetchone()[0]
            if count >= self.capacity:
                raise BufferError('Task admission is full; request was not accepted. Retry after a task finishes.')
            identity, now = uuid.uuid4().hex, self.clock()
            self.db.execute('INSERT INTO tasks(id,idem,created,updated,state,command,original) VALUES(?,?,?,?,?,?,?)',
                            (identity, key, now, now, 'RECEIVED', json.dumps(command), json.dumps(command)))
            self._event(identity, 'RECEIVED', 'Durably admitted')
            return identity, True

    def _event(self, identity, state, detail):
        self.db.execute('INSERT INTO events(task,at,state,detail) VALUES(?,?,?,?)',
                        (identity, self.clock(), state, str(detail)[:8000]))

    def transition(self, identity, state, detail='', expected=None, **updates):
        if state not in STATES or set(updates) - {'command', 'spec', 'checkpoint', 'outcome', 'retries'}:
            raise ValueError('Invalid task transition fields')
        with self.transaction():
            row = self.get(identity)
            if expected is not None and row and row['state'] not in expected:
                raise ValueError('Task changed before lifecycle claim')
            if not row or state != row['state'] and state not in EDGES.get(row['state'], set()):
                raise ValueError('Invalid task lifecycle transition')
            fields = {'state': state, 'updated': self.clock(), **updates}
            fields = {k: json.dumps(v) if k in {'command', 'spec', 'checkpoint'} else v for k, v in fields.items()}
            self.db.execute('UPDATE tasks SET '+','.join(k+'=?' for k in fields)+' WHERE id=?', (*fields.values(), identity))
            self._event(identity, state, detail)

    def setting(self, key, value=None):
        if value is None:
            with self.lock:
                row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
                return json.loads(row[0]) if row else None
        with self.transaction():
            if value is not None:
                self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, json.dumps(value)))
            row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def recover(self):
        """Admission interrupted before dispatch is safe; effects require reconciliation."""
        for row in self.rows(active=True):
            state = row['state']
            if state == 'CLASSIFYING':
                # Classification may have delegated a conversation or immediate action.
                self.transition(row['id'], 'WAITING_USER', 'Interrupted admission; inspect before resubmitting')
            elif state in {'RUNNING', 'VERIFYING'}:
                self.transition(row['id'], 'PAUSED', 'Process interrupted; fresh reconciliation required',
                                checkpoint={**row['checkpoint'], 'uncertain': True})

    def history(self, identity):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT at,state,detail FROM events WHERE task=? ORDER BY seq', (identity,))]
