"""Actual Qwen edit of authored source; never reads/runs a user's project."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from jarvis.brain import BrainClient
from jarvis.coder import Coder
from jarvis.task_state import TaskState

BASE = Path(__file__).resolve().parents[2]
ORIGINAL = '''def calculate(operation, a, b):
    if operation == "add":
        return a + b
    if operation == "subtract":
        return a - b
    if operation == "multiply":
        return a * b
    if operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    raise ValueError("Unknown operation")

def main():
    print(calculate("multiply", 6, 7))

if __name__ == "__main__":
    main()
'''


class Actions:
    def __init__(self, root):
        self.base = root
        self.task_state = TaskState(root)
        self.task_state.start('add UI to calculator.py', 'code_task', root)
        self.progress = 0

    def report(self, kind, message):
        if kind == 'task_status':
            self.progress += 1
        if kind in {'brain', 'warning', 'coding_review'}:
            print(json.dumps({'kind': kind, 'message': str(message)[:220]}), flush=True)


def verify():
    root = BASE / '.jarvis-runtime/gui-edit-fixture'
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'calculator.py'
    # This path is authored specifically for this fixture, outside user projects.
    target.write_text(ORIGINAL, encoding='utf-8')
    config = json.loads((BASE / 'config/config.json').read_text(encoding='utf-8'))
    client = BrainClient(BASE, config['brain'])
    actions = Actions(root)
    request = client.request
    evidence = {'calls': [], 'exact_current': True, 'code_progress_events': 0}
    def traced(operation, cancelled, **data):
        evidence['calls'].append(operation)
        evidence['exact_current'] &= data.get('current') == target.read_bytes().decode('utf-8')
        callback = data.get('_on_code')
        if callback:
            def progress(content):
                evidence['code_progress_events'] += 1
                callback(content)
            data['_on_code'] = progress
        return request(operation, cancelled, **data)
    client.request = traced
    started = time.monotonic()
    result = {'date': datetime.now(timezone.utc).isoformat(), 'model': config['brain']['coder'],
              'scope': 'Real local Qwen generation and authored Tkinter fixture only; no user project executed.'}
    try:
        result['edit_result'] = Coder(actions, client).run(root,
            'add UI to calculator.py using Tkinter. Preserve calculate and main. Running normally must open the UI. '
            'Use two Entry inputs, an operation ttk.Combobox with add/subtract/multiply/divide, '
            'a Calculate button wired to calculate, and a visible result/error Label. Keep it concise.', selected=True)
        result.update(evidence)
        result['generation_seconds'] = round(time.monotonic() - started, 3)
        actions.task_state.finish('completed', result['edit_result'])
        result['passed'] = result['exact_current'] and 1 <= len(result['calls']) <= 3 and all(call == 'code_edit' for call in result['calls']) and result['code_progress_events'] > 0
        result['gui_behavior'] = 'Pending separate owned GUI execution check'
    except Exception as exc:
        result.update(evidence)
        result.update(passed=False, error_type=type(exc).__name__, error=str(exc)[:500], generation_seconds=round(time.monotonic()-started, 3))
    finally:
        client.close()
    record = BASE / 'artifacts/reports/gui-edit-live-check.json'
    history = BASE / 'artifacts/reports/gui-edit-live-history.json'
    if record.exists():
        entries = json.loads(history.read_text(encoding='utf-8')) if history.exists() else []
        entries.append(json.loads(record.read_text(encoding='utf-8')))
        history.write_text(json.dumps(entries, indent=2) + '\n', encoding='utf-8')
    record.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    return result['passed']


if __name__ == '__main__':
    raise SystemExit(0 if verify() else 1)
