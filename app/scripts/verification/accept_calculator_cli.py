"""Independent real-process probes of the CLI protocol chosen by Jarvis.

No application files, assertions or callbacks are edited by this supervisor.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('campaign', type=Path)
    parser.add_argument('--protocol', choices=('long','compact'), default='long', help='Operation spelling documented by the generated application')
    parser.add_argument('--allow-scoped-repair', action='store_true', help='Explicitly observe an existing-project repair without a fresh-creation claim')
    args = parser.parse_args()
    run = args.campaign.resolve(strict=True)
    campaign = json.loads((run/'campaign.json').read_text(encoding='utf-8'))
    scoped = campaign.get('mode') == 'explicit existing-project task'
    if campaign.get('case') != 1 or (scoped and not args.allow_scoped_repair):
        parser.error('Requires fresh CLI case1, or explicit --allow-scoped-repair')
    projects = campaign.get('projects', [])
    if not scoped and len(projects) != 1:
        parser.error('Requires exactly one registered project')
    project = Path(campaign['workspace_parent'] if scoped else projects[0]['workspace']).resolve(strict=True)
    from jarvis.codex_workload import fingerprint
    before = fingerprint(project)
    record = {'date': datetime.now(timezone.utc).isoformat(), 'status': 'FAIL', 'campaign': run.name,
              'model': campaign.get('model'), 'project': str(project),
              'fresh_creation_intake': not scoped, 'existing_project_repair': scoped,
              'protocol': args.protocol,
              'scope': 'Independent subprocess arithmetic/input-validation and unchanged generated-source checks for the Jarvis-selected operation/operand CLI. No GUI, visual-quality, reuse or performance acceptance.',
              'supervisor_authored_implementation': False, 'source_before': before, 'checks': [], 'errors': []}
    if scoped:record['scope'] = 'Existing-project repair only, without fresh-creation acceptance. '+record['scope']
    record['original_request'] = campaign.get('request')
    record['project_ids'] = [row['id'] for row in projects]
    record['jarvis_source_changed_during_trial'] = campaign.get('jarvis_source_changed_during_trial')
    def probe(name, argv, expected=None):
        try:
            if args.protocol=='compact':argv=[{'subtract':'sub','multiply':'mul','divide':'div'}.get(argv[0],argv[0]),*argv[1:]]
            result = subprocess.run([sys.executable, '-B', 'main.py', *argv], cwd=project,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=8)
            observed = {'name': name, 'argv': argv, 'exit_code': result.returncode,
                        'stdout': result.stdout, 'stderr': result.stderr}
            if expected is None:
                if result.returncode == 0 or not (result.stderr.strip() or result.stdout.strip()):
                    raise ValueError('Invalid input was not rejected with an explanation')
                if 'Traceback (most recent call last)' in result.stderr:
                    raise ValueError('Input validation leaked an uncaught Python exception')
            else:
                text = result.stdout.strip()
                match = re.fullmatch(r'(?:Result:\s*)?([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)', text, re.I)
                if result.returncode or result.stderr.strip() or not match:
                    raise ValueError('Expected successful numeric result without stderr')
                if Decimal(match[1]) != Decimal(str(expected)):
                    raise ValueError('Incorrect numeric result: '+text)
            record['checks'].append(observed | {'passed': True})
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            record['errors'].append({'name': name, 'type': type(error).__name__, 'error': str(error),
                                     'observed': locals().get('observed')})
    for operation, left, right, expected in (
            ('add', '2', '3', 5), ('subtract', '5', '8', -3),
            ('multiply', '6', '7', 42), ('divide', '9', '2', '4.5'),
            ('add', '-3.5', '2.25', '-1.25'), ('subtract', '-2', '-7', 5),
            ('multiply', '-2.5', '4', -10), ('divide', '-9', '-3', 3),
            ('divide', '0', '2', 0), ('multiply', '0', '4', 0)):
        probe(operation+' '+left+' '+right, [operation, left, right], expected)
    for name, argv in (
            ('division by zero', ['divide', '1', '0']),
            ('non-numeric operand', ['add', 'banana', '2']),
            ('non-numeric right operand', ['add', '2', 'banana']),
            ('unknown operation', ['unknown', '1', '2']),
            ('missing operand', ['add', '1'])):
        probe(name, argv)
    try:
        result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(project), '-p', 'test_*.py', '-v'],
                                cwd=project, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        record['original_tests'] = {'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
        if result.returncode or not re.search(r'Ran [1-9]\d* tests?', result.stderr):
            record['errors'].append({'name': 'original generated tests', 'error': 'Original behavioral tests did not pass'})
    except (OSError, subprocess.TimeoutExpired) as error:
        record['errors'].append({'name': 'original generated tests', 'error': str(error)})
    record['source_after'] = fingerprint(project)
    record['source_unchanged'] = record['source_after'] == before
    coding = [row for row in campaign.get('tasks', []) if row.get('command', {}).get('kind') == 'code_task']
    record['coding_task_states'] = [{'id': row['id'], 'state': row['state']} for row in coding]
    record['campaign_finished'] = bool(campaign.get('finished_at'))
    terminal = {'COMPLETED', 'FAILED', 'PARTIAL', 'CANCELLED'}
    record['unfinished_tasks'] = [row['id'] for row in campaign.get('tasks', []) if row['state'] not in terminal]
    record['failed_work_tasks'] = [row['id'] for row in campaign.get('tasks', [])
                                   if row.get('command', {}).get('kind') in {'project_step', 'code_task'}
                                   and row['state'] in {'FAILED', 'CANCELLED', 'PARTIAL'}]
    if (record['source_unchanged'] and not record['errors'] and len(record['checks']) == 15
            and coding and all(row['state'] == 'COMPLETED' for row in coding) and record['campaign_finished']
            and not record['unfinished_tasks'] and not record['failed_work_tasks']):
        record['status'] = 'PASS'
    output = run/('independent-cli-acceptance-'+uuid4().hex+'.json')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps({'status': record['status'], 'checks': len(record['checks']), 'errors': len(record['errors']),
                      'source_unchanged': record['source_unchanged'], 'evidence': str(output)}))


if __name__ == '__main__':
    main()
