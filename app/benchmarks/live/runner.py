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


def build(approve: str = 'deny', log: Optional[Callable[[str, Any], None]] = None):
    """A real Jarvis Actions object on the user's configuration, cloud off, scripted approval answers."""
    from jarvis.actions import Actions, Desktop
    config = json.loads((APP / 'config' / 'config.json').read_text(encoding='utf-8'))
    config['groq'] = {**config.get('groq', {}), 'enabled': False}
    config['gemini'] = {**config.get('gemini', {}), 'enabled': False}
    # Isolation: no user memory read or written, no background knowledge work; a fresh task state per run
    # (a previous run's paused question must never steer the next run).
    config['memory'] = {**config.get('memory', {}), 'enabled': False}
    config['knowledge_acquisition'] = {**config.get('knowledge_acquisition', {}), 'enabled': False}
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
    from uuid import uuid4
    from jarvis.task_state import TaskState
    state = APP / '.jarvis-runtime' / 'live-control' / uuid4().hex
    state.mkdir(parents=True)
    actions.task_state = TaskState(state)
    approvals: List[Dict[str, Any]] = []

    def handler(kind, detail, cancelled):
        answer = approve == 'approve'
        approvals.append({'kind': kind, 'detail': str(detail)[:1000], 'answer': 'approved' if answer else 'denied'})
        return answer
    actions.approval_handler = handler
    return actions, events, approvals


def run(utterance: str, approve: str = 'deny', timeout: float = 600.0, quiet: bool = False) -> Dict[str, Any]:
    from jarvis.commands import parse

    def log(kind, value):
        if not quiet and kind in ('tool', 'plan', 'brain', 'answer', 'warning', 'media_card', 'question'):
            text = value.get('phase', '') + ' ' + value.get('title', '') if isinstance(value, dict) else str(value)
            print(f'  [{kind}] {text[:160]}', flush=True)
    actions, events, approvals = build(approve, log)
    started = time.monotonic()
    row: Dict[str, Any] = {'utterance': utterance, 'date': datetime.now(timezone.utc).isoformat(), 'approve': approve}
    try:
        command = parse(utterance)
        row['command'] = {'kind': command.kind, 'value': str(command.value)[:300]}
        row['answer'] = str(actions.execute(command, lambda: time.monotonic() - started > timeout))
        row['status'] = 'answered'
    except Exception as error:  # A refusal or failure is an outcome to judge, not a crash.
        import traceback
        row.update(status='error', error=f'{type(error).__name__}: {error}'[:2000],
                   traceback=traceback.format_exc()[-6000:])
    finally:
        row['seconds'] = round(time.monotonic() - started, 1)
        row['tools'] = [e['value'] for e in events if e['kind'] == 'tool']
        row['island_cards'] = [{k: e['value'].get(k) for k in ('service', 'phase', 'title', 'step', 'steps')}
                               for e in events if e['kind'] == 'media_card' and isinstance(e['value'], dict)]
        row['approvals'] = approvals
        row['actions'] = actions
    return row


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
