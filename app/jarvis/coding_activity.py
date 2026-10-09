"""Actual coding activity and review events; display failures never replay work."""
from datetime import datetime, timezone
import difflib
import json
import threading
import time
from uuid import uuid4

_lock = threading.RLock()


def emit(report, run, row):
    row = {'date': datetime.now(timezone.utc).isoformat(), **row}
    try:
        with _lock, (run/'activity.jsonl').open('a', encoding='utf-8') as output:
            output.write(json.dumps(row, ensure_ascii=False)+'\n')
    except OSError:
        pass
    try:
        report('coding_activity', row)
    except Exception:
        pass
    return row


class Activity:
    def __init__(self, report, run, kind, label, detail='', worker=''):
        self.report, self.run = report, run
        self.row = {'id':uuid4().hex, 'kind':kind, 'label':str(label)[:300],
                    'detail':str(detail)[:24000], 'worker':worker, 'state':'running'}
        self.started = time.monotonic()
        emit(report, run, self.row)

    def finish(self, state='completed', **result):
        self.row.update(state=state, seconds=round(time.monotonic()-self.started,3), **result)
        return emit(self.report, self.run, self.row)


def review(before, after, name):
    lines=list(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
                                  fromfile=name, tofile=name))
    return {'file':name, 'added':sum(s.startswith('+') and not s.startswith('+++') for s in lines),
            'removed':sum(s.startswith('-') and not s.startswith('---') for s in lines),
            'diff':''.join(lines)[:48000]}
