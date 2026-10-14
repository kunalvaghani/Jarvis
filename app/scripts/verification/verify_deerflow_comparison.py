"""Small live local-model comparison; results are not general intelligence scores."""
import argparse
from datetime import datetime, timezone, timedelta
import json
import re
from pathlib import Path
import subprocess
import tempfile
import time

BASE = Path(__file__).resolve().parents[2]
CASES = [
    ('arithmetic', 'print(sum([12, 18, 7]))\n', 'Read sample.py. What integer does it print? Cite sample.py.', '37'),
    ('filter', 'print([n for n in range(6) if n % 2 == 0])\n', 'Read sample.py. What exact list does it print? Cite sample.py.', '[0, 2, 4]'),
    ('failure', 'print(10 / 0)\n', 'Read sample.py. Name the exception it raises. Cite sample.py.', 'ZeroDivisionError'),
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['ollama', 'upstream'], required=True)
    p.add_argument('--label', default='baseline')
    p.add_argument('--model', default='qwen3.5:4b')
    args = p.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{1,40}', args.label):
        p.error('--label must be a short lowercase report name')
    rows = []
    for name, source, goal, expected in CASES:
        with tempfile.TemporaryDirectory(prefix='deerflow-bench-') as folder:
            Path(folder, 'sample.py').write_text(source, encoding='utf-8')
            start = time.monotonic()
            try:
                command = [str(BASE / '.venv/Scripts/python.exe'), '-m', 'jarvis.agent_cli',
                    '--backend', args.backend, '--project', folder, '--goal', goal,
                    '--model', args.model, '--max-steps', '2']
                if args.backend == 'upstream':
                    command = [str(BASE / '.venv/Scripts/python.exe'), '-m', 'jarvis.deerflow_cli',
                               '--project', folder, '--goal', goal, '--model', args.model]
                run = subprocess.run(command, cwd=BASE,
                    capture_output=True, text=True, encoding='utf-8', timeout=240,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                events = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
                answers = [e.get('answer', '') for e in events if e.get('event') == 'turn.completed']
                answer = answers[-1] if answers else ''
                read = any(e.get('event') == 'tool.completed' and e.get('tool') == 'read_file' for e in events)
                ok = run.returncode == 0 and read and expected in answer and 'sample.py' in answer
                row = {'case': name, 'ok': ok, 'answer': answer, 'source_read': read,
                       'exit_code': run.returncode, 'errors': [e for e in events if e.get('event') == 'error'],
                       'diagnostic': run.stderr[-1200:] if run.returncode else ''}
            except subprocess.TimeoutExpired:
                row = {'case': name, 'ok': False, 'error': '240 second process deadline'}
            row['seconds'] = round(time.monotonic() - start, 3)
            rows.append(row)
            print(json.dumps(row), flush=True)
    result = {'date': datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        'backend': args.backend, 'label': args.label, 'model': args.model,
        'scope': 'Three synthetic source-reading tasks, one trial each, real local inference; source bodies read through Jarvis. No web, desktop, writing, speech or general intelligence evaluation.',
        'grading': 'Required exact answer substring, source citation, successful source read and exit code. Heuristic grading; inspect saved answers.',
        'passed': sum(r['ok'] for r in rows), 'total': len(rows),
        'mean_seconds': round(sum(r['seconds'] for r in rows) / len(rows), 3), 'cases': rows}
    destination = BASE / 'artifacts/reports' / ('deerflow-' + args.backend + '-' + args.label + '.json')
    destination.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(destination), 'passed': result['passed'], 'mean_seconds': result['mean_seconds']}))
    return 0 if result['passed'] == result['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
