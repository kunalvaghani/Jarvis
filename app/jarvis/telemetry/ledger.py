"""Per-step timing ledger (flag telemetry.timing_ledger, default off).

Where a task's time goes: model calls (wall time, Ollama's own token counts and timers when the result carries
them, which model), tool steps, and fixed control waits. One JSON row per event, plus a summary row when the
task ends, in .jarvis-runtime/logs/timing-ledger.jsonl. `benchmarks/ledger_report.py` turns it into p50/p95.

It only observes: with the flag off every hook calls straight through, and a ledger failure is swallowed,
never raised into the task. Waits happen inside tool steps, so wait time is a part of tool time.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import functools
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, TypeVar
from uuid import uuid4

from .. import flags

APP = Path(__file__).resolve().parents[2]
NINE_B = re.compile(r'(?i)(?<![\d.])9b\b')
F = TypeVar('F', bound=Callable[..., Any])


class Task:
    def __init__(self, path: Path, kind: str, reasoning_model: str) -> None:
        self.id, self.kind, self.path = uuid4().hex[:12], kind, path
        self.reasoning_model = reasoning_model
        self.started = time.perf_counter()
        self.lock = threading.Lock()
        self.totals: Dict[str, float] = {'model_s': 0.0, 'tool_s': 0.0, 'wait_s': 0.0}
        self.counts: Dict[str, int] = {'model_calls': 0, 'calls_9b': 0, 'steps': 0, 'prompt_tokens': 0,
                                       'output_tokens': 0}

    def is_9b(self, model: str) -> bool:
        return bool(model) and (model == self.reasoning_model or bool(NINE_B.search(model)))

    def write(self, row: Dict[str, Any]) -> None:
        try:
            line = json.dumps({'task': self.id, 'at': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                               **row}, default=str)
            with self.lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open('a', encoding='utf-8') as out:
                    out.write(line + '\n')
        except (OSError, TypeError, ValueError):
            pass  # Observation only: never fail the task over its own timing record.


_current: ContextVar[Optional[Task]] = ContextVar('jarvis_ledger_task', default=None)
_active: List[Task] = []
_active_lock = threading.Lock()


def current() -> Optional[Task]:
    """The task this thread works for; a helper thread falls back to the only active task, never a guess."""
    task = _current.get()
    if task is not None:
        return task
    with _active_lock:
        return _active[0] if len(_active) == 1 else None


def _reasoning_model(config: Mapping[str, Any]) -> str:
    try:
        return str(config['brain']['model_hierarchy']['reasoning_model'])
    except (KeyError, TypeError):
        return ''


@contextmanager
def task_scope(config: Any, kind: str, base: Optional[Path] = None) -> Iterator[Optional[Task]]:
    """One ledger task around a top-level command; nested commands belong to the outer one."""
    if _current.get() is not None or not flags.enabled(config, 'telemetry', 'timing_ledger'):
        yield None
        return
    path = (Path(base) if base is not None else APP) / '.jarvis-runtime' / 'logs' / 'timing-ledger.jsonl'
    task = Task(path, str(kind)[:40], _reasoning_model(config) if isinstance(config, Mapping) else '')
    token = _current.set(task)
    with _active_lock:
        _active.append(task)
    outcome = 'completed'
    try:
        yield task
    except BaseException as error:
        outcome = 'failed: ' + type(error).__name__
        raise
    finally:
        _current.reset(token)
        with _active_lock:
            if task in _active:
                _active.remove(task)
        total = time.perf_counter() - task.started
        totals = {k: round(v, 3) for k, v in task.totals.items()}
        other = total - task.totals['model_s'] - task.totals['tool_s']
        task.write({'type': 'task', 'kind': task.kind, 'outcome': outcome, 'total_s': round(total, 3),
                    'other_s': round(max(other, 0.0), 3), **totals, **task.counts})


def model_call(task: Task, operation: str, seconds: float, result: Any, error: Optional[BaseException]) -> None:
    row: Dict[str, Any] = {'type': 'model', 'operation': str(operation)[:40], 'seconds': round(seconds, 3)}
    if isinstance(result, dict):
        model = result.get('model_used')
        if isinstance(model, str):
            row['model'] = model[:80]
        usage = result.get('inference')
        if isinstance(usage, dict):
            for key in ('prompt_tokens', 'prompt_s', 'output_tokens', 'output_s', 'load_s', 'continued'):
                if key in usage:
                    row[key] = usage[key]
    if error is not None:
        row['error'] = type(error).__name__
    with task.lock:
        task.totals['model_s'] += seconds
        task.counts['model_calls'] += 1
        task.counts['calls_9b'] += task.is_9b(str(row.get('model', '')))
        for key in ('prompt_tokens', 'output_tokens'):
            value = row.get(key)
            if isinstance(value, int):
                task.counts[key] += value
    task.write(row)


def timed_model(method: F) -> F:
    """Decorator for BrainClient._request_once(self, operation, cancelled, **data)."""
    @functools.wraps(method)
    def wrapper(self: Any, operation: Any, cancelled: Any, **data: Any) -> Any:
        task = current()
        if task is None:
            return method(self, operation, cancelled, **data)
        started, result, failure = time.perf_counter(), None, None
        try:
            result = method(self, operation, cancelled, **data)
            return result
        except BaseException as error:
            failure = error
            raise
        finally:
            try:
                model_call(task, str(operation), time.perf_counter() - started, result, failure)
            except Exception:
                pass
    return wrapper  # type: ignore[return-value]


def timed_tool(method: F) -> F:
    """Decorator for ToolRegistry.execute(self, step, cancelled, activate=None)."""
    @functools.wraps(method)
    def wrapper(self: Any, step: Any, *args: Any, **kwargs: Any) -> Any:
        task = current()
        if task is None:
            return method(self, step, *args, **kwargs)
        started, ok = time.perf_counter(), False
        try:
            result = method(self, step, *args, **kwargs)
            ok = True
            return result
        finally:
            try:
                seconds = time.perf_counter() - started
                action = step.get('action') if isinstance(step, dict) else None
                with task.lock:
                    task.totals['tool_s'] += seconds
                    task.counts['steps'] += 1
                task.write({'type': 'tool', 'action': str(action)[:60], 'seconds': round(seconds, 3), 'ok': ok})
            except Exception:
                pass
    return wrapper  # type: ignore[return-value]


def timed_task(method: F) -> F:
    """Decorator for Actions.execute(self, command, cancelled=...): one ledger task per top-level command."""
    @functools.wraps(method)
    def wrapper(self: Any, command: Any, *args: Any, **kwargs: Any) -> Any:
        config = getattr(self, 'config', None)
        if _current.get() is not None or not flags.enabled(config, 'telemetry', 'timing_ledger'):
            return method(self, command, *args, **kwargs)
        with task_scope(config, str(getattr(command, 'kind', 'command')), getattr(self, 'base', None)):
            return method(self, command, *args, **kwargs)
    return wrapper  # type: ignore[return-value]


def pause(seconds: float, where: str = 'control') -> None:
    """A fixed wait that is also recorded; it sleeps exactly as long either way."""
    started = time.perf_counter()
    time.sleep(seconds)
    task = current()
    if task is None:
        return
    try:
        waited = time.perf_counter() - started
        with task.lock:
            task.totals['wait_s'] += waited
        task.write({'type': 'wait', 'where': where[:40], 'seconds': round(waited, 3)})
    except Exception:
        pass
