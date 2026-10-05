"""Dated multilingual/local-CLI regressions; live UI checks remain separate."""
from datetime import datetime, timezone
import json
from verify_step_regression import BASE, run

if __name__ == '__main__':
    regression=run(['-m','unittest','discover','-s','tests','-q'])
    readiness=run(['-m','jarvis.launcher','--check'])
    result={'date':datetime.now(timezone.utc).isoformat(),'regression':regression,'readiness':readiness,
        'passed':regression['exit_code']==readiness['exit_code']==0,
        'scope':'Regression and launcher readiness; actual local CLI creation/edit and nine UI browser checks are separate records.'}
    target=BASE/'artifacts/coding-regression-check.json'
    if target.exists():
        history=target.with_name('coding-regression-history.json')
        old=json.loads(history.read_text()) if history.exists() else []
        old.append(json.loads(target.read_text()));history.write_text(json.dumps(old,indent=2)+'\n')
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
    raise SystemExit(0 if result['passed'] else 1)
