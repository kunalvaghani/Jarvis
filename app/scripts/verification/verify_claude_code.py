"""Live local Claude Code/Qwen file creation/edit fixture; no user file touched."""
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from jarvis.coder import Coder

BASE=Path(__file__).resolve().parents[2]


def verify():
    root=BASE/'.jarvis-runtime/claude-code-fixture'
    root.mkdir(exist_ok=True)
    # Fresh bounded fixture; previous attempts remain alongside this new folder.
    from uuid import uuid4
    project=root/uuid4().hex;project.mkdir()
    options={**json.loads((BASE/'config/config.json').read_text())['brain'],
        'coding_backend':'claude-code','claude_code_model':'jarvis-claude-qwen3.5:9b','claude_code_debug':True}
    events=[]
    def report(kind,value):
        events.append((kind,value))
        if kind=='brain' or (kind=='task_status' and any(s in value.get('phase','') for s in ('Read','Write','Edit','saved','rejected'))):
            print(json.dumps({'kind':kind,'value':value})[:700],flush=True)
    actions=SimpleNamespace(base=BASE,report=report)
    coder=Coder(actions,SimpleNamespace(options=options))
    result={'date':datetime.now(timezone.utc).isoformat(),'project':str(project),
        'scope':'Actual installed Claude Code CLI with local Qwen3.5 9B; authored creation/edit fixtures only.'}
    try:
        result['create']=coder.run(project,'Create main.py with a function add(a,b) returning a+b and print(add(2,3)) under the main guard. Use Write tool, not code in your answer. Keep below 15 lines.',selected=True)
        source=(project/'main.py').read_text();assert 'def add' in source
        result['edit']=coder.run(project,'Edit main.py: preserve add and main, add subtract(a,b) returning a-b. Read current source first and use Edit tool. Keep below 20 lines.',selected=True)
        source=(project/'main.py').read_text();assert 'def subtract' in source and 'def add' in source
        guards=[];adapters=[];backups=[]
        for request in (BASE/'.jarvis-runtime/claude-code').glob('*/request.json'):
            if json.loads(request.read_text())['project']==str(project):
                events_path=request.parent/'file-events.jsonl'
                assert events_path.is_file(), 'Claude file permission bridge did not execute'
                guards.extend(json.loads(line) for line in events_path.read_text().splitlines())
                adapter=request.parent/'proxy-events.jsonl'
                assert adapter.exists(),'Local inference adapter did not record completed requests'
                adapters.extend(json.loads(line) for line in adapter.read_text().splitlines())
                backup=request.parent/'originals/main.py'
                if backup.exists():backups.append(backup.read_text())
        assert any(e['tool']=='Write' for e in guards) and any(e['tool']=='Edit' for e in guards)
        assert adapters and all(e['thinking'] is False for e in adapters)
        assert any('def add' in s and 'def subtract' not in s for s in backups),'Original source backup was not preserved'
        import subprocess,sys
        check=subprocess.run([sys.executable,str(project/'main.py')],capture_output=True,text=True,timeout=10)
        assert check.returncode==0 and check.stdout.strip()=='5', check.stdout+check.stderr
        result.update(passed=True,source=source,progress_events=sum(k=='task_status' for k,v in events),runtime_stdout=check.stdout,guard_tools=[e['tool'] for e in guards],
            adapter_requests=len(adapters),thinking_disabled=True,original_backup_verified=True)
    except Exception as exc:
        result.update(passed=False,error=str(exc))
    record=BASE/'artifacts/reports/claude-code-live-check.json'
    if record.exists():
        history=BASE/'artifacts/reports/claude-code-live-history.json'
        old=json.loads(history.read_text()) if history.exists() else []
        old.append(json.loads(record.read_text()));history.write_text(json.dumps(old,indent=2)+'\n')
    record.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
    return result['passed']


if __name__=='__main__': raise SystemExit(0 if verify() else 1)
