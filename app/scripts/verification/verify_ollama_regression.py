"""Record output-repair regression/readiness separately from live inference."""
from datetime import datetime, timezone
import json
from scripts.verification.verify_step_regression import BASE, run


if __name__ == '__main__':
    regression = run(['-m', 'unittest', 'discover', '-s', 'tests', '-q'])
    readiness = run(['-m', 'jarvis.launcher', '--check'])
    result = {'date': datetime.now(timezone.utc).isoformat(), 'regression': regression,
              'readiness': readiness, 'passed': regression['exit_code'] == readiness['exit_code'] == 0,
              'scope': 'Regression/readiness only; no live voice, desktop execution or long-code generation claim.'}
    (BASE / 'artifacts/reports/ollama-regression-check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
