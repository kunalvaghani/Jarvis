"""Owned disposable-process test: grant contention and native lock release after crash."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
sys.path.insert(0, str(APP))
from jarvis import repair_authorization as auth

child = '''import json,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from jarvis import repair_authorization as a
root=Path(sys.argv[2])
print('ready',flush=True)
while not (root/'start').exists(): time.sleep(.01)
print(json.dumps({'consumed':a.take_dependency_repair(root) is not None}),flush=True)
'''
crasher = '''import os,sys
from pathlib import Path
p=Path(sys.argv[1]);f=p.open('a+b');f.write(b'0');f.flush();f.seek(0)
if os.name=='nt':
 import msvcrt
 msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
else:
 import fcntl
 fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
print('locked',flush=True)
sys.stdin.readline()
os._exit(17)
'''
with tempfile.TemporaryDirectory(prefix='jarvis-grant-process-') as folder:
    root = Path(folder)
    grant = root / auth.DEPENDENCY_FILE
    data = dict(environment='.venv', lock='fixture', lock_sha256='a'*64, wheelhouse='fixture',
                max_bytes=1, expires=time.time()+60, approval_id='process-fixture')
    grant.write_text(json.dumps(data), encoding='utf-8')
    children = [subprocess.Popen([sys.executable, '-c', child, str(APP), str(root)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) for _ in range(4)]
    try:
        for process in children:
            assert process.stdout.readline().strip() == 'ready'
        (root / 'start').touch()
        results = []
        for process in children:
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, stderr
            results.append(json.loads(stdout)['consumed'])
        assert sum(results) == 1
    finally:
        for process in children:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)
    grant.write_text(json.dumps(data), encoding='utf-8')
    lock = root / ('.' + auth.DEPENDENCY_FILE + '.lock')
    process = subprocess.Popen([sys.executable, '-c', crasher, str(lock)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        assert process.stdout.readline().strip() == 'locked'
        assert auth.take_dependency_repair(root) is None
        assert grant.exists()
        _, stderr = process.communicate('crash\n', timeout=10)
        assert process.returncode == 17, stderr
        assert auth.take_dependency_repair(root) is not None
        assert not grant.exists()
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=5)
result = {'date': '2026-10-20', 'scope': 'Windows owned disposable processes and grant files only; no executor, install or download',
          'four_processes': {'PASS': True, 'successful_consumers': sum(results)},
          'crash_releases_lock': {'PASS': True, 'owned_child_exit': 17}, 'posix': 'NOT RUN'}
(OUT / 'grant-process-readback.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result))
