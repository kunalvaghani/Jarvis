"""Dated regression/readiness evidence for the one-window glass notch."""
from datetime import datetime, timezone
import json
from pathlib import Path
from scripts.verification.verify_step_regression import run


if __name__ == '__main__':
    regression = run(['-m','unittest','discover','-s','tests','-q'])
    readiness = run(['-m','jarvis.launcher','--check'])
    result = {'date':datetime.now(timezone.utc).isoformat(), 'regression':regression,
        'readiness':readiness, 'passed':regression['exit_code']==readiness['exit_code']==0,
        'scope':'Regression and launcher readiness. UI fixtures are separate; no live voice, account action or guaranteed frame-rate claim.'}
    Path('artifacts/reports/notch-regression-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    raise SystemExit(0 if result['passed'] else 1)
