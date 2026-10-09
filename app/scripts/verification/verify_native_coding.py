"""Actual Qwen planner/executor + LocalGithub trial in a new owned fixture."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

from jarvis.coder import Coder

BASE=Path(__file__).resolve().parents[2]
ORACLE='''import unittest
from main import add
class Addition(unittest.TestCase):
 def test_positive(self): self.assertEqual(add(2,3),5)
 def test_negative(self): self.assertEqual(add(-2,3),1)
 def test_decimal(self): self.assertAlmostEqual(add(1.5,2.25),3.75)
'''


def main():
    multi='--multi' in sys.argv
    config=json.loads((BASE/'config/config.json').read_text());options={**config['brain'],'coding_backend':'jarvis','max_coding_seconds':900}
    project=BASE/'.jarvis-runtime/native-live'/uuid4().hex;project.mkdir(parents=True)
    tests={'test_main.py':ORACLE} if not multi else {
        'test_alpha.py':ORACLE.replace('from main import add','from alpha import add'),
        'test_beta.py':ORACLE.replace('from main import add','from beta import add')}
    for name,text in tests.items():(project/name).write_text(text,encoding='utf-8')
    test_hashes={name:hashlib.sha256((project/name).read_bytes()).hexdigest() for name in tests}
    events=[]
    def report(kind,value):
        if kind=='coding_activity':
            events.append(value)
            print(value.get('state'),value.get('label'),flush=True)
        elif kind=='task_status':print(value.get('phase'),flush=True)
    coder=Coder(SimpleNamespace(base=BASE,report=report),SimpleNamespace(options=options))
    started=time.monotonic();result={'date':datetime.now(timezone.utc).isoformat(),'scope':'Actual native local Qwen planner and worker in a new owned fixture; existing user projects untouched.','project':str(project),'passed':False}
    try:
        goal=('Implement two independent Python modules alpha.py and beta.py, each exposing add(a,b) returning a+b for integers and decimals. '
              'Preserve test_alpha.py and test_beta.py exactly; each already tests its corresponding module. Use two independent workers, each owning its module and its corresponding test. '
              'Use command_reference to inspect the Python workflow before editing. No imports between modules.') if multi else (
              'Implement main.py exposing add(a,b) returning a+b for integers and decimals. Read and preserve the existing test_main.py exactly; run its behavioral tests. Use one inseparable Python source and tests workload.')
        result['answer']=coder.run(project,goal,selected=True)
        assert all(hashlib.sha256((project/name).read_bytes()).hexdigest()==sha for name,sha in test_hashes.items()),'Original test assertions changed'
        checked=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(project),'-p','test_*.py','-v'],cwd=project,capture_output=True,text=True,timeout=30)
        result['independent_check']={'exit_code':checked.returncode,'output':checked.stdout+checked.stderr}
        assert checked.returncode==0,result['independent_check']['output']
        receipts=[json.loads(p.read_text()) for p in (BASE/'.jarvis-runtime/native-workloads').glob('*/receipt.json') if json.loads(p.read_text()).get('project')==str(project)]
        assert len(receipts)==1 and receipts[0]['status']=='passed'
        assert len(receipts[0]['workers'])==(2 if multi else 1),'Expected worker count was not honored'
        result.update(passed=True,workload_receipt=receipts[0],test_assertions_unchanged=True,
                      gpu_dispatches=[r['gpu'] for r in events if r.get('gpu')])
    except Exception as exc:result.update(error_type=type(exc).__name__,error=str(exc)[:5000])
    result['seconds']=round(time.monotonic()-started,3)
    target=BASE/('artifacts/reports/native-coding-multi-live-check.json' if multi else 'artifacts/reports/native-coding-live-check.json');target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('passed','seconds','error','gpu_dispatches')},indent=2),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
