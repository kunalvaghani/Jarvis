"""Bounded real F5 worker protocol checks without speaker playback."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time


def main():
    base = Path(__file__).resolve().parents[2]
    events = queue.Queue()
    with (base / '.jarvis-runtime/f5-worker-check.log').open('w', encoding='utf-8') as log:
        worker = subprocess.Popen([sys.executable, '-u', '-m', 'jarvis.f5_speech', '--serve', '--no-playback'],
            cwd=base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        def read():
            for line in worker.stdout:
                events.put(json.loads(line))
            events.put({'error': 'Worker exited'})
        threading.Thread(target=read, daemon=True).start()
        rows = []
        def until(predicate, seconds=120):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                row = events.get(timeout=max(.01, deadline-time.monotonic()))
                rows.append(row)
                if row.get('error'):
                    raise RuntimeError(row)
                if predicate(row):
                    return row
            raise TimeoutError('F5 worker made no expected progress')
        def send(row):
            worker.stdin.write(json.dumps(row)+'\n')
            worker.stdin.flush()
        try:
            until(lambda row: row.get('ready'))
            unicode_check = '--unicode' in sys.argv
            first = 'Good evening, sir. I am ready to assist.'
            if unicode_check:
                first = 'Good evening\udc81, sir. Your \U0001d401old answer is ready\ud800. I am here to help.'
            send({'id': 1, 'text': first})
            send({'id': 2, 'text': 'Your workspace is ready. We can proceed when you are.'})
            until(lambda row: row.get('id') == 2 and row.get('done'))
            assert [row['id'] for row in rows if row.get('done')] == [1, 2]
            send({'id': 3, 'text': 'This reply is cancelled and must not be replayed.'})
            send({'stop': True})
            until(lambda row: row.get('stopped'), 5)
            send({'id': 4, 'text': 'The previous reply was stopped. I am still here.'})
            until(lambda row: row.get('id') == 4 and row.get('done'))
            assert not any(row.get('done') and row.get('id') == 3 for row in rows)
            result = {'kind': 'Actual F5 worker inference; no speaker playback', 'events': rows,
                      'ordered_replies': True, 'stop_and_new_reply': True, 'malformed_unicode_input': unicode_check}
            filename = 'f5-worker-unicode-verification.json' if unicode_check else 'f5-worker-verification.json'
            (base / '.jarvis-runtime' / filename).write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps(result))
        finally:
            worker.stdin.close()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
            worker.stdout.close()


if __name__ == '__main__':
    main()
