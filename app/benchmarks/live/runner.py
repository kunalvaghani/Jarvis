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
from typing import Any, Callable, Dict, List, Optional

APP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))


RECORD: List[Dict[str, Any]] = []  # Tool steps of the current run (diagnosis).
CALLS: List[Dict[str, Any]] = []  # Model calls of the current run (diagnosis).


def build(approve: str = 'deny', log: Optional[Callable[[str, Any], None]] = None, memory: bool = False,
          telemetry: bool = False):
    """A real Jarvis Actions object on the user's configuration, cloud off, scripted approval answers."""
    from jarvis.actions import Actions, Desktop
    config = json.loads((APP / 'config' / 'config.json').read_text(encoding='utf-8'))
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
        memory: bool = False, telemetry: bool = False) -> Dict[str, Any]:
    def log(kind, value):
        if not quiet and kind in ('tool', 'plan', 'brain', 'answer', 'warning', 'media_card', 'question'):
            text = value.get('phase', '') + ' ' + value.get('title', '') if isinstance(value, dict) else str(value)
            print(f'  [{kind}] {text[:160]}', flush=True)
    actions, events, approvals = build(approve, log, memory, telemetry)
    started = time.monotonic()
    row: Dict[str, Any] = {'utterance': utterance, 'date': datetime.now(timezone.utc).isoformat(), 'approve': approve}
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
            answers.append(str(actions.execute(command, lambda: time.monotonic() - started > timeout)))
        row['answer'] = '\n'.join(answers)
        row['status'] = 'answered' if commands else 'not understood'
    except Exception as error:  # A refusal or failure is an outcome to judge, not a crash.
        import traceback
        row.update(status='error', error=f'{type(error).__name__}: {error}'[:2000],
                   traceback=traceback.format_exc()[-6000:])
    finally:
        row['seconds'] = round(time.monotonic() - started, 1)
        row['tools'] = [e['value'] for e in events if e['kind'] == 'tool']
        row['steps'] = list(RECORD)
        row['model_calls'] = list(CALLS)
        row['island_cards'] = [{k: e['value'].get(k) for k in ('service', 'phase', 'title', 'step', 'steps')}
                               for e in events if e['kind'] == 'media_card' and isinstance(e['value'], dict)]
        row['approvals'] = approvals
        if telemetry:
            row['ledger'] = ledger_summary(row['date'])
        row['actions'] = actions
    return row


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
