"""Actual native Qwen HTML/CSS/JS workers plus independent browser oracle."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from types import SimpleNamespace
from uuid import uuid4

from jarvis.coder import Coder
from jarvis.codex_validation import validate_project

BASE=Path(__file__).resolve().parents[2]
GOAL=('Create a plain responsive counter website in index.html, style.css and app.js. '
      'Use a real button id=increment, a text-bearing span id=count initially showing exactly 0, '
      'and a heading reading Native Jarvis Counter. Clicking increment once shows 1 and twice shows 2. '
      'Link style.css and app.js from index.html; no network dependencies or framework. '
      'Split markup, styles and logic into independent workers with agreed DOM ids. Browser checks must exercise the real clicks and visible text.')


def main():
    options={**json.loads((BASE/'config/config.json').read_text())['brain'],'coding_backend':'jarvis','max_coding_seconds':1200}
    root=BASE/'.jarvis-runtime/native-web-live'/uuid4().hex;root.mkdir(parents=True)
    events=[]
    def report(kind,value):
        if kind=='coding_activity':events.append(value);print(value.get('state'),value.get('label'),flush=True)
        elif kind=='task_status':print(value.get('phase'),flush=True)
    coder=Coder(SimpleNamespace(base=BASE,report=report),SimpleNamespace(options=options))
    started=time.monotonic();result={'date':datetime.now(timezone.utc).isoformat(),'project':str(root),'passed':False,
        'scope':'Actual native Qwen plain-website generation in owned fixture; fixed independent browser oracle, no user project or account changed.'}
    try:
        result['answer']=coder.run(root,GOAL,selected=True)
        oracle={'files':[{'path':name,'role':role,'purpose':'Required counter '+role} for name,role in [('index.html','frontend'),('style.css','frontend'),('app.js','logic')]],
                'checks':[{'kind':'browser','path':'index.html','steps':[
                    {'action':'text','selector':'#count','value':'0'}, {'action':'click','selector':'#increment'},
                    {'action':'text','selector':'#count','value':'1'}, {'action':'click','selector':'#increment'},
                    {'action':'text','selector':'#count','value':'2'}]}]}
        check=root.parent/('oracle-'+uuid4().hex);check.mkdir()
        validation=validate_project(root,check,GOAL,[f['path'] for f in oracle['files']],oracle,lambda:False,report)
        assert validation['passed'],json.dumps(validation['errors'])
        result.update(passed=True,independent_validation=validation,gpu_dispatches=[r['gpu'] for r in events if r.get('gpu')])
    except Exception as exc:result.update(error_type=type(exc).__name__,error=str(exc)[:5000])
    result['seconds']=round(time.monotonic()-started,3)
    target=BASE/'artifacts/reports/native-web-live-check.json'
    if target.exists():
        history=BASE/'artifacts/reports/native-web-live-history.json'
        rows=json.loads(history.read_text()) if history.exists() else []
        rows.append(json.loads(target.read_text()));history.write_text(json.dumps(rows,indent=2),encoding='utf-8')
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('passed','seconds','error')},indent=2),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
