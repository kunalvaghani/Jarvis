"""Restricted execution of induction answers (model-written Python) for the AZR oracle.

Model code is never executed in the Jarvis process. Each batch runs in the reviewed MCP runtime
container (no network, read-only root, no capabilities, non-root, PID/memory/CPU limits and a
lifetime fence; see ``mcp_synthesis.server_config``) behind a Jarvis-owned harness. The harness
forks one child per program with restricted builtins and OS limits (CPU seconds, address space,
no core files) and kills it after a wall-clock deadline, so a runaway C-level loop or allocation
loses only that program. Every case is run twice so nondeterministic programs fail (AZR's
determinism check). The static screen (``azr_tasks.screen_program``) runs first; passing it is not
treated as proof of safety.
"""
import json
from pathlib import Path
import subprocess
import uuid

from .azr_tasks import SAFE_BUILTINS, screen_program

HARNESS = r'''
import builtins, json, os, resource, select, signal, sys, time
SAFE = set(json.loads(sys.argv[1]))
spec = json.loads(sys.stdin.read())

def evaluate(program):
    allowed = {name: getattr(builtins, name) for name in SAFE}
    namespace = {"__builtins__": allowed}
    row = {"id": program["id"], "cases": []}
    try:
        exec(compile(program["source"], "answer", "exec"), namespace)
        function = namespace["f"]
        for case in program["cases"]:
            outputs = []
            for _ in range(2):
                value = case["input"]
                value = list(value) if isinstance(value, list) else value
                outputs.append(function(value))
            try:
                shown = json.loads(json.dumps(outputs[0]))
            except (TypeError, ValueError):
                shown = None
            expected = case["output"]
            row["cases"].append({"ok": outputs[0] == outputs[1] and (expected is None or outputs[0] == expected),
                                 "deterministic": outputs[0] == outputs[1], "output": shown})
    except BaseException as error:
        row["error"] = type(error).__name__
    return row

results = []
for program in spec["programs"]:
    read_end, write_end = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_end)
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_AS, (160 * 2 ** 20, 160 * 2 ** 20))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        data = json.dumps(evaluate(program)).encode()
        os.write(write_end, data[:2 ** 20])
        os._exit(0)
    os.close(write_end)
    chunks, deadline = [], time.monotonic() + 5
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        ready, _, _ = select.select([read_end], [], [], remaining)
        if not ready:
            break
        chunk = os.read(read_end, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    os.close(read_end)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    _, status = os.waitpid(pid, 0)
    try:
        row = json.loads(b"".join(chunks))
    except ValueError:
        row = {"id": program["id"], "cases": [], "error": "killed_by_limit"}
    results.append(row)
print(json.dumps(results))
'''


class SandboxUnavailable(RuntimeError):
    pass


def run_programs(base, programs, cancelled=lambda: False, timeout=120):
    """programs: [{id, source, cases:[{input, output}]}]. Screen first; execute only in the container."""
    from .mcp_synthesis import image_status, reap, server_config
    screened, results = [], {}
    for program in programs:
        try:
            screen_program(program['source'])
            screened.append(program)
        except (ValueError, SyntaxError) as exc:
            results[program['id']] = {'passed': False, 'screen': 'rejected: ' + str(exc)[:120], 'cases': []}
    if not screened:
        return results
    status = image_status(cancelled)
    if not status['available']:
        raise SandboxUnavailable(status['reason'])
    folder = Path(base) / '.jarvis-runtime' / 'azr' / 'sandbox' / uuid.uuid4().hex[:12]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'server.py').write_text(HARNESS, encoding='utf-8')
    name = 'gen-azr-' + folder.name
    config = server_config(name, folder, 'azr', status['image_id'], timeout)
    args = [*config['args'], json.dumps(sorted(SAFE_BUILTINS))]
    try:
        completed = subprocess.run([config['command'], *args], input=json.dumps({'programs': screened}),
                                   capture_output=True, text=True, timeout=timeout + 30)
    finally:
        reap(name)
    try:
        rows = json.loads(completed.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise SandboxUnavailable('sandbox produced no result: ' + completed.stderr[-300:]) from None
    for row in rows:
        cases = row.get('cases', [])
        results[row['id']] = {'passed': not row.get('error') and bool(cases) and all(c['ok'] for c in cases)
                              and len(cases) == len(next(p for p in screened if p['id'] == row['id'])['cases']),
                              'screen': 'passed', 'error': row.get('error'), 'cases': cases,
                              'deterministic': all(c['deterministic'] for c in cases) if cases else None}
    return results
