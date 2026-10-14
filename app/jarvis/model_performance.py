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
