"""Shared fixtures for project-intelligence tests: a real TaskIngress, simulated workers and a fake coder."""
import threading
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis.commands import Command
from jarvis.project_intel import ProjectIntelligence
from jarvis.task_ingress import TaskIngress


class Clock:
    def __init__(self):
        self.now = time.time()

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def workspace_tree(tmp_path):
    """A configured project root with a Projects folder and an old monitoring app to reference."""
    roots = tmp_path / 'roots'
    (roots / 'Projects').mkdir(parents=True)
    old = roots / 'Projects' / 'OldMonitoringApp'
    (old / 'monitor').mkdir(parents=True)
    (old / 'README.md').write_text('# Old monitoring app\nShows CPU and RAM usage.', encoding='utf-8')
    (old / 'monitor' / 'cpu_monitor.py').write_text('import psutil\n\ndef cpu():\n    return psutil.cpu_percent()\n', encoding='utf-8')
    (old / 'main.py').write_text('from monitor.cpu_monitor import cpu\nprint(cpu())\n', encoding='utf-8')
    (roots / 'Projects' / 'NotesSite').mkdir()
    return roots, old


def make(tmp_path, *, ingress=True, options=None):
    roots, old = workspace_tree(tmp_path)
    clock, events = Clock(), []
    actions = SimpleNamespace(base=tmp_path, config={'project_roots': [str(roots)], 'task_queue': {}}, memory=Mock(),
                              report=lambda kind, message: events.append((kind, message)), generation=0,
                              closed=threading.Event(), queue_lock=threading.RLock(), pending_tasks=[], thread=threading.Thread(),
                              awareness=None)
    if ingress:
        actions.ingress = TaskIngress(actions, tmp_path / 'queue.sqlite3', {})
        actions.ingress.store.clock = actions.ingress.scheduler.clock = actions.ingress.decisions.clock = clock
        actions.ingress.scheduler.observe = lambda: {'ram_available_mb': 32000, 'cpu_percent': 0, 'desktop': True, 'battery_low': False}
    else:
        actions.ingress = None
    projects = ProjectIntelligence(actions, {'enabled': True, 'search_roots': [], 'search_home': False, **(options or {})}, clock=clock,
                                   store_path=tmp_path / 'projects.sqlite3')
    actions.project_intel = projects
    return SimpleNamespace(actions=actions, projects=projects, clock=clock, events=events, roots=roots, reference=old,
                           ingress=actions.ingress)


def say(env, text):
    """Route one utterance exactly as Actions does for project commands."""
    from jarvis.commands import parse
    try:
        command = parse(text)
    except ValueError:
        command = Command('task', text, 'unparsed')
    if command.kind == 'task' and not command.extra:
        command = Command('task', command.value, '')
    assert env.projects.claims(command), (text, command)
    return env.projects.handle(command)


def admit(env):
    """The ingress worker's classification step for every RECEIVED admission."""
    ingress = env.ingress
    for row in ingress.store.rows(active=True):
        if row['state'] != 'RECEIVED':
            continue
        stored = ingress.store.setting('admission_overrides:' + row['id'])
        ingress.store.transition(row['id'], 'CLASSIFYING')
        ingress.scheduler.put_nowait((0, Command(**row['command']), threading.Event()), row['id'], stored)


def fake_coder(env, command):
    """Writes one file per instruction into the workspace and records a byte readback, like a real handler would."""
    workspace = Path(command.extra)
    name = 'module_' + str(len(list(workspace.glob('module_*.py'))) + 1) + '.py'
    path = workspace / name
    body = '# ' + command.value[:200].replace('\n', ' ') + '\n'
    if 'tests' in command.value.casefold():
        (workspace / 'tests').mkdir(exist_ok=True)
        path = workspace / 'tests' / ('test_' + name)
        body += 'def test_placeholder():\n    assert True\n'
    path.write_text(body, encoding='utf-8')
    env.ingress.scheduler.record_effect({'kind': 'file', 'path': str(path), 'bytes': path.stat().st_size, 'verification': 'fresh byte readback'})
    return 'Wrote ' + path.name


def run_next(env, coder=fake_coder, fail=None):
    """Dispatch one legacy-lane task through the real scheduler; returns (row, result) or None."""
    import queue
    ingress = env.ingress
    admit(env)
    try:
        generation, command, token = ingress.scheduler.get(timeout=0)
    except queue.Empty:
        return None
    identity = ingress.scheduler.local.identity
    try:
        env.projects.dispatch_guard(identity)
        if fail and fail(command):
            raise RuntimeError('build failed: missing dependency')
        if command.kind == 'project_step':
            result = env.projects.run_step(command.value)
        elif command.kind == 'code_task':
            result = coder(env, command)
        else:
            result = 'done'
        ingress.scheduler.outcome('COMPLETED', result, {})
    except Exception as exc:
        ingress.scheduler.outcome('CANCELLED' if token.is_set() else 'FAILED', str(exc))
        result = exc
    ingress.scheduler.task_done()
    env.projects.reconcile(force=True)
    return ingress.store.get(identity), result


def drain(env, limit=40, **kwargs):
    rows = []
    for _ in range(limit):
        step = run_next(env, **kwargs)
        if step is None:
            admit(env)
            if run_next(env, **kwargs) is None:
                break
            continue
        rows.append(step)
    return rows


def resolve_decisions(env, seconds=20.1):
    """Present pending routine choices, let the 20-second timer elapse, apply through the real path."""
    ingress = env.ingress
    for decision in ingress.decisions.rows():
        if decision['status'] == 'PENDING' and decision['presented_at'] is None:
            ingress.decisions.presented(decision['id'])
    env.clock.advance(seconds)
    for decision in ingress.decisions.tick():
        ingress.apply_decision(decision)
        env.projects.observe_report('task_decision', decision)


def plan(env):
    return env.projects.store.active()['plan']['tasks']


def close(env):
    env.projects.close()
    if env.ingress is not None:
        env.ingress.close()
        env.ingress.store.db.close()


def command_of(env, key):
    task = plan(env)[key]
    return Command(**env.ingress.store.get(task['task_id'])['command'])


__all__ = ['Clock', 'make', 'say', 'admit', 'run_next', 'drain', 'resolve_decisions', 'plan', 'close', 'command_of', 'asdict']
