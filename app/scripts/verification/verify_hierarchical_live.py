"""Configured local planner -> production DAG -> real scoped file reads."""
import json
from pathlib import Path
import time
from jarvis.actions import Actions
from jarvis.brain import BrainClient
from jarvis.commands import Command
from jarvis.task_state import TaskState

BASE = Path(__file__).resolve().parents[2]

def main():
    root = BASE/'.jarvis-runtime/hierarchical-live'/str(time.time_ns())
    root.mkdir(parents=True)
    (root/'one.txt').write_text('First fixture: dependency scheduling.', encoding='utf-8')
    (root/'two.txt').write_text('Second fixture: bounded parallel reads.', encoding='utf-8')
    options = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))['brain']
    options = {**options, 'hierarchical_execution': {'enabled': True, 'macro_cache': False},
        'harness': {'enabled': False}, 'hermes': {'enabled': False}}
    actions = Actions({'files_root': 'managed', 'apps': {}, '_ui_verification': True,
        'memory': {'enabled': False}, 'brain': options}, root, lambda *_: None)
    actions.allowed_tools = {'read_file'}
    def folder(name, cancelled):
        if name != 'this folder':
            raise ValueError('Only explicitly scoped fixture reads are permitted.')
        return root
    actions._task_folder = folder
    actions.task_state = TaskState(root)
    actions.brain.client.close()
    actions.brain.client = BrainClient(BASE, options)
    proposals = []
    request = actions.brain.client.request
    def record_request(operation, cancelled, **data):
        reply = request(operation, cancelled, **data)
        proposals.append(reply)
        (root/'proposals.json').write_text(json.dumps(proposals, indent=2), encoding='utf-8')
        return reply
    actions.brain.client.request = record_request
    start = time.monotonic()
    try:
        reply = actions.execute(Command('task', 'Inspect files one.txt and two.txt in this folder and report both contents.'))
        snapshot = actions.task_state.snapshot()
        result = {'date': '2026-10-14 IST', 'scope': 'Actual configured local model, Brain, DAG, ToolRegistry and two synthetic local files; no microphone, external services, desktop automation or general planning accuracy claim.',
            'elapsed_seconds': time.monotonic()-start, 'reply': reply,
            'status': snapshot['status'], 'dag': snapshot.get('dag'), 'proposals': proposals,
            'passed': all(text in reply for text in ['First fixture: dependency scheduling.', 'Second fixture: bounded parallel reads.']) and snapshot['status'] == 'completed'}
        (BASE/'artifacts/reports/hierarchical-live.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(result, indent=2), flush=True)
        raise SystemExit(0 if result['passed'] else 1)
    finally:
        actions.close()

if __name__ == '__main__':
    main()
