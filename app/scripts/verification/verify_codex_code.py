"""Actual installed Codex with local Qwen: owned creation/edit fixture."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4
from jarvis.coder import Coder

BASE=Path(__file__).resolve().parents[2]


def verify():
    project=BASE/'.jarvis-runtime/codex-code-fixture'/uuid4().hex;project.mkdir(parents=True)
    options={**json.loads((BASE/'config/config.json').read_text())['brain'],
        'coding_backend':'codex','codex_model':'jarvis-codex-qwen3.5:9b'}
    events=[]
    def report(kind,value):
        events.append((kind,value))
        if kind=='brain' or (kind=='task_status' and any(s in value.get('phase','') for s in ('Read','Write','Edit','saved'))):
            print(json.dumps({'kind':kind,'value':value})[:500],flush=True)
    coder=Coder(SimpleNamespace(base=BASE,report=report),SimpleNamespace(options=options))
    result={'date':datetime.now(timezone.utc).isoformat(),'project':str(project),
        'scope':'Actual installed Codex CLI with local Qwen3.5 9B; authored source creation/edit and Python runtime fixtures.'}
    try:
        result['create']=coder.run(project,'Create main.py with add(a,b) returning a+b and print(add(2,3)) under the main guard. Use the Jarvis Write tool. Keep below 15 lines. Running main.py must print exactly one line: 5. Behavioral unittests must check add and this exact CLI output.',selected=True)
        original=(project/'main.py').read_bytes();assert b'def add' in original
        result['edit']=coder.run(project,'Modify main.py: preserve add and the main guard unchanged; add subtract(a,b) returning a-b. Read the current source first; use the Jarvis Edit tool. Keep below 20 lines. Running main.py must still print exactly one line: 5. Do not add a subtract print/demo. Update behavioral unittests to check add, subtract and the unchanged exact CLI output.',selected=True)
        source=(project/'main.py').read_text();assert 'def add' in source and 'def subtract' in source
        guards=[];adapters=[];backups=[]
        for request in (BASE/'.jarvis-runtime/codex-code').glob('*/request.json'):
            if json.loads(request.read_text())['project']!=str(project): continue
            guards.extend(json.loads(s) for s in (request.parent/'file-events.jsonl').read_text().splitlines())
            adapters.extend(json.loads(s) for s in (request.parent/'proxy-events.jsonl').read_text().splitlines())
            backup=request.parent/'originals/main.py'
            if backup.exists(): backups.append(backup.read_bytes())
        applied=[e for e in guards if e.get('stage')=='applied']
        assert {'Write','Edit'} <= {e['tool'] for e in applied}
        assert original in backups,'Original source was not backed up'
        assert adapters and all(e.get('thinking') is False for e in adapters if e['stage']=='completed')
        check=subprocess.run([sys.executable,str(project/'main.py')],capture_output=True,text=True,timeout=10)
        assert check.returncode==0 and check.stdout.strip()=='5',{'stdout':check.stdout,'stderr':check.stderr,'exit_code':check.returncode}
        result.update(passed=True,source=source,guard_tools=[e['tool'] for e in applied],
            adapter_requests=sum(e['stage']=='completed' for e in adapters),thinking_disabled=True,
            original_backup_verified=True,progress_events=sum(k=='task_status' for k,v in events),runtime_stdout=check.stdout)
    except Exception as exc: result.update(passed=False,error=str(exc))
    target=BASE/'artifacts/reports/codex-code-live-check.json'
    if target.exists():
        history=target.with_name('codex-code-live-history.json')
        old=json.loads(history.read_text()) if history.exists() else []
        old.append(json.loads(target.read_text()));history.write_text(json.dumps(old,indent=2)+'\n')
    target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
    return result['passed']


if __name__=='__main__': raise SystemExit(0 if verify() else 1)
