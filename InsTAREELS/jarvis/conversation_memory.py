"""Paired, durable sessions and bounded context projections; no action execution."""
from contextlib import closing
from datetime import datetime, timezone
import re
import sqlite3
import threading
import uuid

WORDS = re.compile(r"[^\W_]{3,}", re.UNICODE)
STOPWORDS = set("the and for with from this that what when where why how can could would should please tell explain about more again remember recall previous session conversation discussed question answer does did was were are have has its into using used based give show want know first last current saved memory context yesterday today follow up jarvis".split())
FOLLOWUP = re.compile(r"\b(?:it|its|they|them|their|this|that|those|these|same|continue|more|again|follow.up|previous|earlier|you said|we discussed)\b", re.I)


def terms(text):
    return {word.casefold() for word in WORDS.findall(text)} - STOPWORDS


def messages(turns, budget=24000):
    """Project newest/relevant paired turns to a prompt; disk retains full text."""
    result, remaining = [], budget
    for turn in reversed(turns):
        question, answer = turn['question'], turn['answer']
        if remaining < 200:
            break
        allowance = min(remaining, max(500, budget//max(1,min(len(turns),12))))
        question = question[:min(2000, allowance//3)]
        answer = answer[:max(0, allowance-len(question))]
        result[0:0] = [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer}]
        remaining -= len(question)+len(answer)
    return result


class ConversationMemory:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock, closing(self.connect()) as db, db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, started TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS turns(id TEXT PRIMARY KEY, session TEXT NOT NULL,
                    created TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending');
                CREATE INDEX IF NOT EXISTS session_turns ON turns(session,created);
                CREATE VIRTUAL TABLE IF NOT EXISTS turn_search USING fts5(id UNINDEXED, text);
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=1)
        db.row_factory = sqlite3.Row
        return db

    def start_session(self):
        identity = uuid.uuid4().hex
        with self.lock, closing(self.connect()) as db, db:
            db.execute('INSERT INTO sessions VALUES(?,?)', (identity, datetime.now(timezone.utc).isoformat()))
        return identity

    def begin(self, session, question):
        identity = uuid.uuid4().hex
        from .obsidian_memory import SENSITIVE
        saved = '[redacted sensitive text]' if SENSITIVE.search(question) else question
        with self.lock, closing(self.connect()) as db, db:
            db.execute('INSERT INTO turns(id,session,created,question) VALUES(?,?,?,?)',
                       (identity, session, datetime.now(timezone.utc).isoformat(), saved))
        return identity

    def finish(self, identity, answer='', status='complete'):
        from .obsidian_memory import SENSITIVE
        saved = '[redacted sensitive text]' if SENSITIVE.search(answer) else answer
        with self.lock, closing(self.connect()) as db, db:
            db.execute('UPDATE turns SET answer=?,status=? WHERE id=?', (saved, status, identity))
            db.execute('DELETE FROM turn_search WHERE id=?', (identity,))
            row = db.execute('SELECT question,answer FROM turns WHERE id=?', (identity,)).fetchone()
            if row and status == 'complete':
                db.execute('INSERT INTO turn_search(id,text) VALUES(?,?)',
                           (identity, row['question']+'\n'+row['answer']))

    def turns(self, session):
        with self.lock, closing(self.connect()) as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM turns WHERE session=? AND status='complete' ORDER BY created,id", (session,))]

    def matches(self, question, exclude_session, limit=8):
        keywords = terms(question)
        if not keywords:
            return []
        query = ' OR '.join('"'+word+'"' for word in sorted(keywords))
        with self.lock, closing(self.connect()) as db:
            session_rows = db.execute('''SELECT DISTINCT t.session FROM turn_search f JOIN turns t ON t.id=f.id
                WHERE turn_search MATCH ? AND t.session!=? AND t.status='complete'
                ORDER BY t.created DESC LIMIT ?''', (query, exclude_session, limit)).fetchall()
            rows = []
            for session_row in session_rows:
                row = db.execute('''SELECT t.* FROM turn_search f JOIN turns t ON t.id=f.id
                    WHERE turn_search MATCH ? AND t.session=? AND t.status='complete'
                    ORDER BY bm25(turn_search),t.created DESC LIMIT 1''', (query,session_row['session'])).fetchone()
                if row:
                    rows.append(row)
        # One contextual option per saved session; never silently combine sessions.
        sessions = {}
        for row in rows:
            row = dict(row)
            matched = keywords & terms(row['question']+' '+row['answer'])
            score = len(matched)
            if not score:
                continue
            old = sessions.get(row['session'])
            if old and old['score'] >= score:
                continue
            row.update(score=score, keywords=sorted(matched))
            sessions[row['session']] = row
        return sorted(sessions.values(), key=lambda row: (row['score'], row['created']), reverse=True)[:limit]


def current_context(history, question, budget=24000):
    """Relevant older current-session turns plus recent follow-up continuity."""
    pairs = [{'question': history[i]['content'], 'answer': history[i+1]['content']}
             for i in range(0, len(history)-1, 2)]
    keywords = terms(question)
    relevant = [(i, pair) for i, pair in enumerate(pairs)
                if keywords & terms(pair['question']+' '+pair['answer'])]
    found = bool(relevant or (pairs and FOLLOWUP.search(question)))
    if not found:
        return [], False
    # Keep older matches in the projection even when the conversation is long.
    chosen = relevant[-8:] + [(i, pair) for i, pair in enumerate(pairs[-4:], max(0, len(pairs)-4))]
    dedup = dict(chosen)
    return messages([dedup[i] for i in sorted(dedup)], budget), True
