"""Real owned-file fault/cancellation benchmark, optionally using pinned baseline code."""
import argparse
import importlib
import json
from pathlib import Path
import subprocess
import tempfile

from jarvis.paths import APP_ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    if args.baseline:
        # Load only trusted, pinned repository source, without changing the checkout.
        for name in ('task_state', 'brain', 'actions'):
            module = importlib.import_module('jarvis.' + name)
            source = subprocess.check_output(['git', 'show', '0199c16:app/jarvis/' + name + '.py'], cwd=APP_ROOT)
            exec(compile(source, module.__file__, 'exec'), module.__dict__)
    from scripts.verification.verify_plan_execution import fixture, scenario
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for index, (incremental, fault) in enumerate(((False, True), (True, True), (False, False), (True, False))):
            result = fixture(Path(tmp), scenario(index, 5), incremental=incremental,
                             fault_after=2 if fault else None, cancel_after=None if fault else 1)
            safe = (result['dispatched_actions'] == (2 if fault else 1)
                    and result['completed_actions'] == 1 and result['state_status'] != 'completed')
            if fault:
                safe = safe and bool(result.get('resume_blocker'))
            rows.append({'incremental': incremental, 'fault': 'uncertain_write' if fault else 'cancellation',
                         'safe_checkpoint_no_replay': safe, 'result': result})
    result = {'scope': 'Real owned-file effects with injected failure/cancellation; simulated planner',
              'source': 'pinned 0199c16 task_state/brain/actions loaded without checkout mutation' if args.baseline else 'candidate',
              'cases': rows, 'safe_recoveries': sum(row['safe_checkpoint_no_replay'] for row in rows), 'total': len(rows)}
    Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'cases'}))


if __name__ == '__main__':
    main()
