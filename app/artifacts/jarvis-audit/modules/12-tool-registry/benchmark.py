"""Prompt12 ToolRegistry benchmark: identical owned fixtures, fake actions, network forbidden.

Usage: python benchmark.py <code_root> <mode> <out.jsonl>
code_root contains the jarvis/ package to measure (pre-change copy or current app/).
Cold samples are fresh processes (import + first dispatch); warm samples reuse one process.
"""
import json
import os
import subprocess
import sys
import time

CHILD = r'''
import json, os, sys, tempfile, time
t0 = time.perf_counter()
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import psutil, requests
from jarvis.tools import ToolRegistry
root = Path(tempfile.mkdtemp()); (root/'proj').mkdir()
(root/'proj/a.txt').write_text('fixture text\n' * 50, encoding='utf-8')
for i in range(20): (root/'proj'/f'f{i}.txt').write_text(f'needle {i}', encoding='utf-8')
calls = []
actions = SimpleNamespace(base=root, config={}, allowed_tools=None, report=Mock(), _approve=Mock(),
    execute=lambda command, cancelled: calls.append(command.kind) or 'ok',
    _task_folder=lambda folder, cancelled: str(root/'proj'))
STEPS = [{'action': 'read_file', 'value': 'a.txt', 'folder': 'proj'},
         {'action': 'search_files', 'value': 'needle', 'folder': 'proj'},
         {'action': 'open', 'value': 'notepad'},
         {'action': 'create_file', 'value': 'x.txt', 'folder': 'proj', 'content': 'hi'}]
INVALID = [{'action': 'open'}, {'action': 'nope', 'value': 'x'}, {'action': 'open', 'value': 3}]
def batch():
    out = []
    for step in STEPS:
        out.append(ToolRegistry(actions).execute(step, lambda: False).evidence)
    rejected = 0
    for step in INVALID:
        try: ToolRegistry(actions).execute(step, lambda: False)
        except Exception: rejected += 1
    return out, rejected
def forbid(*a, **k): raise AssertionError('network forbidden in benchmark')
with patch.object(requests.sessions.Session, 'request', forbid):
    mode = sys.argv[2]
    if mode == 'cold':
        out, rejected = batch(); ms = (time.perf_counter() - t0) * 1000
        samples = [ms]
    else:
        batch()  # warm-up
        samples = []
        for _ in range(20):
            s = time.perf_counter(); out, rejected = batch(); samples.append((time.perf_counter() - s) * 1000)
digest = json.dumps([o.replace(str(root), '<root>') for o in out], sort_keys=True)
print(json.dumps({'samples': samples, 'rss': psutil.Process().memory_info().rss, 'digest': digest,
                  'rejected': rejected, 'dispatched_kinds': sorted(set(calls)), 'network_calls': 0}))
'''


def run(code_root, kind):
    result = subprocess.run([sys.executable, '-c', CHILD, code_root, kind], capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise SystemExit(result.stderr[-2000:])
    return json.loads(result.stdout.strip().splitlines()[-1])


def main():
    code_root, mode, out = sys.argv[1:4]
    rows = []
    for _ in range(5):
        row = run(code_root, 'cold')
        rows.append({'mode': mode, 'kind': 'cold', 'milliseconds': row['samples'][0], 'rss_bytes': row['rss'],
                     'digest': row['digest'], 'rejected': row['rejected'], 'network_calls': row['network_calls']})
    warm = run(code_root, 'warm')
    for ms in warm['samples']:
        rows.append({'mode': mode, 'kind': 'warm', 'milliseconds': ms, 'rss_bytes': warm['rss'],
                     'digest': warm['digest'], 'rejected': warm['rejected'], 'network_calls': warm['network_calls']})
    with open(out, 'w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row) + '\n')


if __name__ == '__main__':
    main()
