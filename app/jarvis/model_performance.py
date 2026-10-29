"""Local metadata-only feedback. Completion is never treated as answer accuracy."""
import json
from pathlib import Path
import sqlite3
import threading
from contextlib import closing


class PerformanceTracker:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.Lock();self.rows={}
        with closing(sqlite3.connect(self.path,timeout=.25)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS feedback(category TEXT,model TEXT,correct INTEGER,incorrect INTEGER,PRIMARY KEY(category,model))')
            db.execute('CREATE TABLE IF NOT EXISTS coding_runs(id TEXT PRIMARY KEY,at REAL,provider TEXT,model TEXT,category TEXT,latency_ms REAL,valid INTEGER,verified INTEGER,reason TEXT,tokens INTEGER)')
            self.rows={(r[0],r[1]):(r[2],r[3]) for r in db.execute('SELECT * FROM feedback')}

    def cloud_failed_class(self,category,model):
        with self.lock:
            correct,incorrect=self.rows.get((category,model),(0,0))
            return correct+incorrect>=3 and incorrect>correct

    def feedback(self,category,model,correct):
        if category not in {'complex','medium','unknown'} or type(correct) is not bool or not isinstance(model,str) or len(model)>150:
            raise ValueError('Invalid routing feedback metadata.')
        with self.lock,closing(sqlite3.connect(self.path,timeout=.25)) as db, db:
            db.execute('INSERT INTO feedback VALUES (?,?,?,?) ON CONFLICT(category,model) DO UPDATE SET correct=correct+excluded.correct,incorrect=incorrect+excluded.incorrect',
                (category,model,int(correct),int(not correct)))
            row=db.execute('SELECT correct,incorrect FROM feedback WHERE category=? AND model=?',(category,model)).fetchone()
            self.rows[(category,model)]=tuple(row)

    def reset(self):
        with self.lock,closing(sqlite3.connect(self.path,timeout=.25)) as db, db:
            db.execute('DELETE FROM feedback');self.rows={}

    def coding_result(self,identifier,provider,model,category,latency_ms,valid,*,verified=None,reason='',tokens=None):
        import re,time
        if (not re.fullmatch('[a-f0-9]{32}',identifier) or provider not in ('local','groq','gemini')
                or category not in ('coding','planning','repair','analysis') or not re.fullmatch('[a-z0-9_]{0,100}',reason)
                or tokens is not None and (type(tokens) is not int or tokens<0)):raise ValueError('Invalid coding telemetry.')
        with self.lock,closing(sqlite3.connect(self.path,timeout=.25)) as db,db:
            db.execute('INSERT OR REPLACE INTO coding_runs VALUES(?,?,?,?,?,?,?,?,?,?)',
                (identifier,time.time(),provider,model,category,float(latency_ms),int(valid),None if verified is None else int(verified),reason,tokens))

    def coding_summary(self,category):
        with self.lock,closing(sqlite3.connect(self.path,timeout=.25)) as db:
            return [{'provider':row[0],'model':row[1],'samples':row[2],'valid_proposals':row[3],
                     'verified_results':row[4],'mean_latency_ms':row[5],'total_reported_tokens':row[6],
                     'metered_samples':row[7]} for row in db.execute(
                'SELECT provider,model,COUNT(*),SUM(valid),SUM(COALESCE(verified,0)),AVG(latency_ms),SUM(tokens),COUNT(tokens) FROM coding_runs WHERE category=? GROUP BY provider,model',(category,))]
