"""Paired live-inference/real ToolRegistry owned-file tasks, independently graded.

Only file reads are admitted. Nothing on the user's desktop is touched. These
are bounded component end-to-end tasks, not complete Brain/voice acceptance.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from jarvis.brain_worker import Models
from jarvis.tools import ToolRegistry, SPECS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--repeat', type=int, default=2)
    parser.add_argument('--executor', choices=['qwen3.5:2b', 'qwen3.5:4b'], default='qwen3.5:2b')
    parser.add_argument('--recovery-probe', action='store_true', help='Inject one invalid native reply after a real verified prerequisite read')
    args = parser.parse_args()
    if args.out.exists() or not 1 <= args.repeat <= 10:
        parser.error('New output directory and 1-10 repetitions required.')
    args.out.mkdir(parents=True)
    owned = (args.out/'owned-files').resolve()
    owned.mkdir()
    contents = {'notes.txt': 'public fixture alpha\n', 'main.py': 'def add(a, b):\n    return a + b\n',
                'second.txt': 'public fixture beta\n'}
    for filename, text in contents.items():
        (owned/filename).write_bytes(text.encode())
    def scope(folder, cancelled):
        if folder not in {'this folder', '.', str(owned)}:
            raise ValueError('Read outside benchmark-owned folder refused.')
        return str(owned)
    actions = SimpleNamespace(base=args.out.resolve(), config={}, allowed_tools={'read_file', 'list_files'},
                              _task_folder=scope, report=lambda *a: None, task_state=None)
    registry = ToolRegistry(actions)
    tools = [{'action': s.name, 'description': s.description} for s in SPECS if s.name in actions.allowed_tools]
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))['brain']
    worker = Models()
    rows = []
    cases = [('routine', ['notes.txt']), ('coding', ['main.py']), ('workflow', ['notes.txt', 'second.txt'])]
    if args.recovery_probe:
        cases = [('workflow', ['notes.txt', 'second.txt'])]
    for repetition in range(args.repeat):
        # Alternate configuration order to reduce warming/order bias.
        for label in (['baseline', 'hierarchy'] if repetition % 2 == 0 else ['hierarchy', 'baseline']):
            for case, filenames in cases:
                goal = ('Read ' + ' and '.join(filenames) + ' in this folder' + (' before debugging the code' if case == 'coding' else ''))
                options = {**config, 'model_hierarchy': {'enabled': label == 'hierarchy',
                    'execution_model': args.executor, 'reasoning_model': 'qwen3.5:9b'}}
                completed, results, attempts = [], {}, []
                original_post = worker.client.post
                injected = [False]
                if args.recovery_probe:
                    initial = {'action': 'read_file', 'value': filenames[0], 'folder': 'this folder', 'expected': 'Exact public bytes'}
                    evidence = registry.execute(initial, lambda: False).evidence
                    if evidence != contents[filenames[0]]:
                        raise ValueError('Prerequisite readback failed before fault injection.')
                    results[filenames[0]] = True
                    completed.append({**initial, 'verified': True, 'confirmed': True, 'result': evidence})
                    def fault_once(url, **kwargs):
                        if url.endswith('/api/chat') and not injected[0]:
                            import requests
                            injected[0] = True
                            response = requests.Response()
                            response.status_code = 200
                            response._content = b'{"done":true,"message":{"content":"injected invalid native proposal","tool_calls":[]}}'
                            return response
                        return original_post(url, **kwargs)
                    worker.client.post = fault_once
                start = time.perf_counter()
                row = {'configuration': label, 'executor': args.executor, 'case': case,
                       'repetition': repetition, 'at': datetime.now(timezone.utc).isoformat(),
                       'fault_injection': args.recovery_probe}
                try:
                    for _ in range(len(filenames)+1):
                        result = worker.predict({'operation': 'next_step', 'options': options, 'goal': goal,
                            'tools': tools, 'screen': {'title': 'Owned file fixture', 'folder': 'this folder'},
                            'completed': completed, 'steps_left': len(filenames)+1-len(completed),
                            'last_result': completed[-1] if completed else None})
                        attempts.append({'model': result.get('model_used'), 'route': result.get('model_route'), 'inference': result.get('inference')})
                        steps = result.get('steps', [])
                        if not steps:
                            break
                        step = steps[0]
                        if (step.get('action') != 'read_file' or step.get('value') not in filenames
                                or step['value'] in results):
                            raise ValueError('Wrong/redundant tool or target; no read dispatched.')
                        tool_start = time.perf_counter()
                        evidence = registry.execute(step, lambda: False).evidence
                        expected = contents[step['value']]
                        verified = evidence == expected
                        results[step['value']] = verified
                        completed.append({**step, 'verified': verified, 'confirmed': verified,
                                          'result': evidence, 'tool_wall_s': time.perf_counter()-tool_start})
                        if all(results.get(name) for name in filenames):
                            break  # Independent exact read oracle, not model done/confidence.
                    row.update(verified=all(results.get(name) for name in filenames), reads=results,
                               steps=completed, attempts=attempts)
                except Exception as error:
                    row.update(verified=False, error_type=type(error).__name__, error=str(error)[:300], attempts=attempts)
                row['wall_s'] = time.perf_counter()-start
                worker.client.post = original_post
                row['fault_injected'] = injected[0]
                rows.append(row)
                with (args.out/'rows.jsonl').open('a', encoding='utf-8') as output:
                    output.write(json.dumps(row)+'\n')
                print(json.dumps({k: row[k] for k in ('configuration', 'case', 'wall_s', 'verified')}), flush=True)
    summary = {}
    for label in ('baseline', 'hierarchy'):
        selected = [r for r in rows if r['configuration'] == label]
        values = sorted(r['wall_s'] for r in selected)
        summary[label] = {'samples': len(values), 'verified': sum(r['verified'] for r in selected),
                          'p50_s': statistics.median(values), 'p95_s': values[math.ceil(.95*len(values))-1]}
    (args.out/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    worker.client.close()


if __name__ == '__main__':
    main()
