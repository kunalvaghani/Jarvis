"""Actual read-only CLI and upstream Qwen inference on a synthetic source file."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import time

BASE = Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory(prefix='harness-research-', dir=BASE / '.jarvis-runtime') as folder:
        Path(folder, 'sample.py').write_text('print(2 + 3)\n', encoding='utf-8')
        started = time.monotonic()
        child = subprocess.run([str(BASE / '.venv/Scripts/python.exe'), '-m', 'jarvis.agent_cli',
            '--backend', 'harness', '--project', folder, '--goal', 'Read sample.py and explain what it prints.',
            '--max-steps', '2'], cwd=BASE, capture_output=True, text=True, encoding='utf-8', timeout=220,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        events = [json.loads(line) for line in child.stdout.splitlines() if line.strip()]
        completed = [row for row in events if row.get('event') == 'turn.completed']
        reads = [row for row in events if row.get('event') == 'tool.completed' and row.get('tool') == 'read_file']
        answer = completed[-1].get('answer', '') if completed else ''
        report = {'date': datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(), 'scope': 'Actual Jarvis read-only CLI + real Harness/Qwen on a temporary synthetic project; no desktop actions.',
            'seconds': round(time.monotonic()-started, 3), 'exit_code': child.returncode,
            'read_events': len(reads), 'answer': answer,
            'ok': child.returncode == 0 and bool(reads) and bool(completed) and '5' in answer}
        if not report['ok']:
            errors = [row for row in events if row.get('event') == 'error']
            report['errors'] = errors or [{'error': child.stderr[-1000:]}]
        (BASE / 'artifacts/reports/harness-research-check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report))
        return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
