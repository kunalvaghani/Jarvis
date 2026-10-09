"""Record current regression/readiness without replacing earlier model checks."""
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.verification.verify_step_regression import run

BASE = Path(__file__).resolve().parents[2]


if __name__ == '__main__':
    regression = run(['-m', 'unittest', 'discover', '-s', 'tests', '-q'])
    readiness = run(['-m', 'jarvis.launcher', '--check'])
    result = {'date': datetime.now(timezone.utc).isoformat(), 'model': 'qwen3.5:9b',
        'regression': regression, 'readiness': readiness,
        'passed': regression['exit_code'] == readiness['exit_code'] == 0,
        'scope': 'Regression/readiness only. Real model inference is recorded separately; no live voice, account access or desktop execution claim.'}
    (BASE / 'artifacts/reports/qwen9-regression-check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
