"""Dated regression/readiness check; live execution measurements are separate."""
from datetime import datetime, timezone
import json

from verify_step_regression import BASE, run


if __name__ == '__main__':
    regression = run(['-m', 'unittest', 'discover', '-s', 'tests', '-q'])
    readiness = run(['-m', 'jarvis.launcher', '--check'])
    result = {'date': datetime.now(timezone.utc).isoformat(), 'regression': regression,
              'readiness': readiness, 'passed': regression['exit_code'] == readiness['exit_code'] == 0,
              'scope': 'Regression and launcher readiness only; live Qwen/file/native checks have separate records.'}
    (BASE / 'artifacts/plan-execution-regression-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
