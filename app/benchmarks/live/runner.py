"""Live acceptance runner: hand Jarvis a request exactly as typed input does, then judge it independently.

Jarvis runs through commands.parse -> Actions.execute (planner, tool registry, control routes, island
reports). The runner never calls a control tool itself: it only plays the user where a case says so
(answering an approval card yes or no) and afterwards checks the outcome with its own oracle.
Cloud models are disabled for these runs; everything stays on this PC.

    python benchmarks/live/runner.py smoke "open example.com and tell me the main heading"
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

APP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))


RECORD: List[Dict[str, Any]] = []  # Tool steps of the current run (diagnosis).
CALLS: List[Dict[str, Any]] = []  # Model calls of the current run (diagnosis).


def build(approve: str = 'deny', log: Optional[Callable[[str, Any], None]] = None, memory: bool = False,
          telemetry: bool = False, enable: Tuple[str, ...] = (), cloud: bool = False):
    """A real Jarvis Actions object on the user's configuration, scripted approval answers.

    Default isolation: cloud models off, no memory. `cloud=True` keeps Groq and Gemini as the user configured them
    (full-capability runs, user decision 2026-11-02); memory is read-only whenever it is on.
    """
    from jarvis.actions import Actions, Desktop
    config = json.loads((APP / 'config' / 'config.json').read_text(encoding='utf-8'))
    if not cloud:
        config['groq'] = {**config.get('groq', {}), 'enabled': False}
        config['gemini'] = {**config.get('gemini', {}), 'enabled': False}
    # Isolation: no user memory read or written, no background knowledge work; a fresh task state per run
    # (a previous run's paused question must never steer the next run).
    stored = config.get('memory', {})
    if memory:  # Read the vault, but never learn from a test run.
        config['memory'] = {**stored, 'long_term': {**stored.get('long_term', {}), 'learn_facts': False,
                                                    'summarize_conversations': False},
                            'experience_learning': {**stored.get('experience_learning', {}), 'enabled': False}}
    else:
        config['memory'] = {**stored, 'enabled': False}
    config['knowledge_acquisition'] = {**config.get('knowledge_acquisition', {}), 'enabled': False}
    if telemetry:  # Observation only: the per-step timing ledger and shadow log for this run.
        config['telemetry'] = {**config.get('telemetry', {}), 'timing_ledger': True, 'shadow_log': True}
    from jarvis import flags
    for name in enable:  # Upgrade v2 flags turned on for this run only (on/off flags to true, modes to "act").
        section, _, key = name.partition('.')
        default = flags.FLAGS[(section, key)]  # KeyError for an unknown flag: a typo must not pass silently.
        config[section] = {**config.get(section, {}), key: 'act' if isinstance(default, str) else True}
    events: List[Dict[str, Any]] = []
    lock = threading.Lock()

    def report(kind, value):
        row = {'t': round(time.monotonic(), 3), 'kind': kind,
               'value': value if isinstance(value, (dict, list)) else str(value)[:2000]}
        with lock:
            events.append(row)
        if log:
            log(kind, value)
    actions = Actions(config, APP, report, Desktop())
    # Diagnosis record only: each tool step and the start of its result (observes, never changes behaviour).
    from jarvis import tools as tool_module
    steps: List[Dict[str, Any]] = []
    original = tool_module.ToolRegistry._execute_traced
    if not getattr(original, '_recorded', False):
        def recorded(self, step, cancelled, activate=None):
            row = {'action': step.get('action') if isinstance(step, dict) else None,
                   'value': str(step.get('value', ''))[:200] if isinstance(step, dict) else '',
                   'content': str(step.get('content', ''))[:300] if isinstance(step, dict) else ''}
            try:
                result = original(self, step, cancelled, activate)
                row['result'] = str(getattr(result, 'evidence', result))[:1500]
                return result
            except Exception as error:
                row['error'] = f'{type(error).__name__}: {error}'[:500]
                raise
            finally:
                RECORD.append(row)
        recorded._recorded = True
        tool_module.ToolRegistry._execute_traced = recorded
    RECORD.clear()
    CALLS.clear()
    client = actions.brain.client
    original_once = client._request_once

    def timed(operation, cancelled, **data):  # Diagnosis: which model call took how long (never changes it).
        started = time.monotonic()
        row = {'operation': operation, 'started': round(started, 1)}
        CALLS.append(row)
        try:
            return original_once(operation, cancelled, **data)
        except Exception as error:
            row['error'] = f'{type(error).__name__}: {error}'[:300]
            raise
        finally:
            row['seconds'] = round(time.monotonic() - started, 1)
    client._request_once = timed
    from uuid import uuid4
    from jarvis.task_state import TaskState
    state = APP / '.jarvis-runtime' / 'live-control' / uuid4().hex
    state.mkdir(parents=True)
    actions.task_state = TaskState(state)
    approvals: List[Dict[str, Any]] = []

    def handler(kind, detail, cancelled):
        if isinstance(approve, (list, tuple)):  # Approve only a card that names something the user asked for.
            answer = any(str(name).lower() in str(detail).lower() for name in approve)
        else:
            answer = approve == 'approve'
        approvals.append({'kind': kind, 'detail': str(detail)[:1000], 'answer': 'approved' if answer else 'denied'})
        return answer
    actions.approval_handler = handler
    return actions, events, approvals


def run(utterance: str, approve: str = 'deny', timeout: float = 600.0, quiet: bool = False,
        memory: bool = False, telemetry: bool = False, enable: Tuple[str, ...] = (), cloud: bool = False,
        interrupt_after: Optional[float] = None, crash_after: Optional[float] = None) -> Dict[str, Any]:
    """One request through the app's own entry path.

    interrupt_after: the user's stop (the same cancel signal the Stop control sends) after that many seconds.
    crash_after: the planner worker process is killed after that many seconds (fault injection); Jarvis must fail
    cleanly and never repeat or half-finish a write. Brain scenarios, Phase 0 (2026-11-02).
    """
    def log(kind, value):
        if not quiet and kind in ('tool', 'plan', 'brain', 'answer', 'warning', 'media_card', 'question'):
            text = value.get('phase', '') + ' ' + value.get('title', '') if isinstance(value, dict) else str(value)
            print(f'  [{kind}] {text[:160]}', flush=True)
    built = time.monotonic()
    actions, events, approvals = build(approve, log, memory, telemetry, enable, cloud)
    started = time.monotonic()
    row: Dict[str, Any] = {'utterance': utterance, 'date': datetime.now(timezone.utc).isoformat(), 'approve': approve,
                           'flags': list(enable), 'full': cloud and memory, 'build_s': round(started - built, 2)}
    resources = Resources().__enter__()
    try:
        # Exactly the app's entry for typed/spoken text (main.py: Engine(actions.submit).feed(command_text(text), ...)).
        from jarvis.audio import command_text
        from jarvis.commands import Command
        from jarvis.conversation_intent import model_kind, quick_kind
        from jarvis.engine import Engine
        commands: List[Any] = []
        engine = Engine(commands.append, lambda *_: None)
        engine.activate()
        engine.feed(command_text(utterance), final=True, raw=utterance)
        answers = []
        for command in commands:
            if command.kind == 'task' and command.extra == 'unparsed':  # Actions.submit -> _route_unparsed.
                kind = quick_kind(command.value) or model_kind(command.value, {'model': actions.config.get(
                    'context_selector', {}).get('model', 'qwen3.5:0.8b'), 'timeout_seconds': 3.0}, lambda: False)
                command = Command('ask' if kind == 'chat' else 'task', command.value)
            row.setdefault('commands', []).append({'kind': command.kind, 'value': str(command.value)[:300]})
            if command.kind == 'ask':  # The app answers conversation on its chat path: no task runs.
                answers.append('[Jarvis treated this as conversation; no task was run]')
                continue
            def cancelled() -> bool:
                late = interrupt_after is not None and time.monotonic() - started > interrupt_after
                if late and 'interrupted_at' not in row:
                    row['interrupted_at'] = round(time.monotonic() - started, 1)
                return time.monotonic() - started > timeout or late
            if crash_after is not None:
                def crash() -> None:
                    client = getattr(getattr(actions, 'brain', None), 'client', None)
                    process = getattr(client, 'process', None)
                    if process is not None and process.poll() is None:
                        process.kill()
                        row['crashed_at'] = round(time.monotonic() - started, 1)
                threading.Timer(crash_after, crash).start()
            answers.append(str(actions.execute(command, cancelled)))
        row['answer'] = '\n'.join(answers)
        row['status'] = 'answered' if commands else 'not understood'
    except Exception as error:  # A refusal or failure is an outcome to judge, not a crash.
        import traceback
        row.update(status='error', error=f'{type(error).__name__}: {error}'[:2000],
                   traceback=traceback.format_exc()[-6000:])
    finally:
        row['seconds'] = round(time.monotonic() - started, 1)
        resources.__exit__()
        row['peak_ram_mb'], row['peak_vram_mb'] = round(resources.peak_ram_mb), round(resources.peak_vram_mb)
        firsts = [e['t'] for e in events if e['kind'] in ('tool', 'media_card')]
        row['first_action_s'] = round(min(firsts) - started, 1) if firsts else None
        row['tools'] = [e['value'] for e in events if e['kind'] == 'tool']
        row['steps'] = list(RECORD)
        row['wasted_retries'] = wasted_retries(row['steps'])
        row['model_calls'] = list(CALLS)
        row['island_cards'] = [{k: e['value'].get(k) for k in ('service', 'phase', 'title', 'step', 'steps')}
                               for e in events if e['kind'] == 'media_card' and isinstance(e['value'], dict)]
        row['approvals'] = approvals
        if telemetry:
            row['ledger'] = ledger_summary(row['date'])
        row['actions'] = actions
    return row


def run_parallel(utterances: List[str], approve: Any = 'deny', timeout: float = 1200.0, telemetry: bool = False,
                 enable: Tuple[str, ...] = (), cloud: bool = False, memory: bool = False) -> Dict[str, Any]:
    """Several orders at once through Jarvis's own queue (TaskIngress -> ScheduledQueue workers).

    The queue database is a fresh temporary one: the user's real queue (and its single-owner lock) is never
    touched, and test tasks can never be recovered into it.
    """
    import tempfile
    from jarvis.task_ingress import TaskIngress
    events_log: List[str] = []
    actions, events, approvals = build(approve, lambda kind, value: events_log.append(kind), memory, telemetry, enable,
                                       cloud)
    started = time.monotonic()
    row: Dict[str, Any] = {'utterance': ' || '.join(utterances), 'date': datetime.now(timezone.utc).isoformat(),
                           'approve': approve, 'flags': list(enable), 'parallel': len(utterances)}
    folder = Path(tempfile.mkdtemp(prefix='jarvis-parallel-queue-'))
    ingress = TaskIngress(actions, folder / 'task-queue.sqlite3', actions.config.get('task_queue', {}))
    actions.ingress = ingress
    try:
        ingress.start()
        from jarvis.commands import Command
        row['task_ids'] = [actions.submit(Command('task', u)) for u in utterances]
        while time.monotonic() - started < timeout and (ingress.scheduler.qsize() or ingress.scheduler.active):
            time.sleep(.5)
        row['status'] = 'answered' if time.monotonic() - started < timeout else 'timeout'
        row['task_states'] = [(r.get('number'), r.get('state'), str(r.get('detail') or '')[:300])
                              for r in ingress.store.rows()]
        row['answer'] = '\n'.join(str(e['value'])[:500] for e in events if e['kind'] in ('answer', 'spoken_reply'))
    except Exception as error:
        row.update(status='error', error=f'{type(error).__name__}: {error}'[:2000])
    finally:
        try:
            ingress.close()
        except Exception:
            pass
        row['seconds'] = round(time.monotonic() - started, 1)
        row['tools'] = [e['value'] for e in events if e['kind'] == 'tool']
        row['steps'] = list(RECORD)
        row['approvals'] = approvals
        if telemetry:
            row['ledger'] = ledger_summary(row['date'])
        row['actions'] = actions
    return row


class Resources:
    """Peak RAM (this process and its children, e.g. the planner worker) and GPU memory while a task runs."""

    def __init__(self, interval: float = 2.0) -> None:
        self.interval, self.stop, self.peak_ram_mb, self.peak_vram_mb = interval, threading.Event(), 0.0, 0.0
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self) -> None:
        import subprocess
        import psutil
        me = psutil.Process()
        while not self.stop.is_set():
            try:
                rss = me.memory_info().rss + sum(c.memory_info().rss for c in me.children(recursive=True))
                self.peak_ram_mb = max(self.peak_ram_mb, rss / 2**20)
            except psutil.Error:
                pass
            try:
                out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                                     capture_output=True, text=True, timeout=5).stdout
                self.peak_vram_mb = max(self.peak_vram_mb, float(out.strip().splitlines()[0]))
            except (OSError, ValueError, IndexError, subprocess.SubprocessError):
                pass
            self.stop.wait(self.interval)

    def __enter__(self) -> 'Resources':
        self.thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop.set()
        self.thread.join(5)


def wasted_retries(steps: List[Dict[str, Any]]) -> int:
    """Tool calls repeated with identical arguments within one task (each repeat after the first counts)."""
    seen: Dict[str, int] = {}
    for step in steps:
        key = json.dumps([step.get('action'), step.get('value'), step.get('content')], default=str, sort_keys=True)
        seen[key] = seen.get(key, 0) + 1
    return sum(n - 1 for n in seen.values() if n > 1)


def ledger_summary(since: str) -> Optional[Dict[str, Any]]:
    """The timing-ledger summary of the task(s) this run started (None if the ledger wrote nothing)."""
    path = APP / '.jarvis-runtime' / 'logs' / 'timing-ledger.jsonl'
    try:
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    except (OSError, ValueError):
        return None
    tasks = [r for r in rows if r.get('type') == 'task' and str(r.get('at', '')) >= since]
    if not tasks:
        return None
    keys = ('total_s', 'model_s', 'tool_s', 'wait_s', 'other_s', 'prompt_tokens', 'output_tokens', 'model_calls',
            'calls_9b', 'steps')
    return {'tasks': len(tasks), **{k: round(sum(float(t.get(k) or 0) for t in tasks), 3) for k in keys}}


def main(argv: List[str]) -> int:
    if len(argv) >= 2 and argv[0] == 'smoke':
        row = run(' '.join(argv[1:]))
        actions = row.pop('actions')
        try:
            actions.close()
        except Exception:
            pass
        print(json.dumps({k: v for k, v in row.items() if k != 'island_cards'}, indent=1, default=str)[:6000])
        print('island cards:', len(row['island_cards']), [c['service'] + ':' + c['phase'] for c in row['island_cards']][:20])
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
