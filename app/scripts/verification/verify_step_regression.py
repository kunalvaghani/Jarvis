"""Record real regression and launcher readiness diagnostics, never desktop claims."""
from jarvis.paths import APP_ROOT, artifact_path
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parents[2]


def run(args):
    started = time.monotonic()
    result = subprocess.run([sys.executable, *args], cwd=BASE, capture_output=True,
        encoding='utf-8', errors='replace', timeout=300,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return {'exit_code': result.returncode, 'seconds': round(time.monotonic() - started, 3),
            'stdout': result.stdout[-5000:], 'stderr': result.stderr[-5000:]}


if __name__ == '__main__':
    regression = run(['-m', 'unittest', 'discover', '-s', 'tests', '-q'])
    readiness = run(['-m', 'jarvis.launcher', '--check'])
    result = {'date': datetime.now(timezone.utc).isoformat(), 'regression': regression,
              'readiness': readiness, 'passed': regression['exit_code'] == readiness['exit_code'] == 0,
              'scope': 'Regression/readiness only. Local inference timing is separate; no live voice or repeated desktop speed claim.'}
    (artifact_path(BASE, 'step-planning-regression-check.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
