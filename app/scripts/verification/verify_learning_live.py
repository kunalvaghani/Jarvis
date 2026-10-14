"""Configured local planner with acquired local help -> guarded real file reads."""
import json
from pathlib import Path
import time
from jarvis.actions import Actions
from jarvis.brain import BrainClient
from jarvis.commands import Command
from jarvis.task_state import TaskState

BASE = Path(__file__).resolve().parents[2]

def main():
    root = BASE/'.jarvis-runtime/learning-live'/str(time.time_ns())
    root.mkdir(parents=True)
    (root/'one.txt').write_text('Diagram one: a red circle.', encoding='utf-8')
    (root/'two.txt').write_text('Diagram two: a blue square.', encoding='utf-8')
    (root/'help.md').write_text('Fixture diagram descriptions are plain text. Read one.txt and two.txt in the explicitly scoped folder to compare them.', encoding='utf-8')
    options = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))['brain']
    options = {**options, 'hierarchical_execution': {'enabled': True, 'macro_cache': False},
        'harness': {'enabled': False}, 'hermes': {'enabled': False}}
    actions = Actions({'files_root':'managed', '_ui_verification':True, 'memory':{'enabled':False},
        'apps':{'Fixture':{'documentation_file':str(root/'help.md')}},
        'knowledge_acquisition':{'enabled':True,'online':False}, 'brain':options}, root, lambda *_:None)
    actions.allowed_tools = {'read_file'}
    def folder(name, cancelled):
        if name not in {'this folder',str(root)}:
            raise ValueError('Only owned fixture reads are permitted.')
        return root
    actions._task_folder = folder
    actions.task_state = TaskState(root)
    actions.brain.client.close()
    actions.brain.client = BrainClient(BASE, options)
    request = actions.brain.client.request
    requests = []
    def record(operation, cancelled, **data):
        reply = request(operation, cancelled, **data)
        requests.append({'operation':operation, 'learning_context_supplied':bool(data.get('learning_context')), 'reply':reply})
        return reply
    actions.brain.client.request = record
    started = time.monotonic()
    try:
        reply = actions.execute(Command('task', 'Use Fixture diagram help to inspect one.txt and two.txt in this folder and report both exact descriptions.'))
        task = actions.task_state.snapshot()
        result = {'date':'2026-10-14 IST','scope':'Actual configured local model, acquired configured local help, production Brain/DAG/ToolRegistry and two synthetic files. No live GUI/model-quality generalization.',
            'elapsed_seconds':time.monotonic()-started,'requests':requests,'reply':reply,
            'status':task['status'],'learning':task.get('learning',{}),
            'passed':task['status']=='completed' and any(r['operation']=='dag_plan' and r['learning_context_supplied'] for r in requests)
                and all(s in reply for s in ('Diagram one: a red circle.','Diagram two: a blue square.'))}
        (BASE/'artifacts/reports/learning-live.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2),flush=True)
        raise SystemExit(0 if result['passed'] else 1)
    finally:
        actions.close()

if __name__ == '__main__':main()
