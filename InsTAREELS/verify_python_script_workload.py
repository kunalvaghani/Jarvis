"""Actual unnamed Python-script workload and bounded owned Tkinter drawing probe."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

from jarvis.coder import Coder

BASE=Path(__file__).resolve().parent
GOAL='create a python script for drawing circle on screen in test codes folder'


def probe(script):
    import runpy
    import tkinter as tk
    from unittest.mock import patch
    roots=[];observed=[];initialize=tk.Tk.__init__
    def initialize_owned(self,*args,**kwargs):
        initialize(self,*args,**kwargs);roots.append(self)
    def bounded_loop(*args,**kwargs):
        for root in roots:
            root.update_idletasks();root.update()
            pending=[root]
            while pending:
                widget=pending.pop();pending.extend(widget.winfo_children())
                if isinstance(widget,tk.Canvas):
                    for item in widget.find_all():
                        if widget.type(item)=='oval':
                            coords=widget.coords(item)
                            if len(coords)==4 and coords[2]>coords[0] and abs((coords[2]-coords[0])-(coords[3]-coords[1]))<1:
                                observed.append({'type':'circle','canvas_visible':bool(widget.winfo_viewable()),'diameter':coords[2]-coords[0]})
    try:
        with patch.object(tk.Tk,'__init__',initialize_owned),patch.object(tk.Misc,'mainloop',bounded_loop),patch.object(tk,'mainloop',bounded_loop):
            runpy.run_path(str(script),run_name='__main__')
        assert roots and any(item['canvas_visible'] for item in observed),'No visible actual Canvas circle observed at startup.'
        print(json.dumps({'passed':True,'scope':'Actual generated script launch, bounded owned Tkinter event loop, visible Canvas circle; no screen capture or user-app input.','circles':observed}))
    finally:
        for root in roots:
            try:root.destroy()
            except tk.TclError:pass


def verify(repair_project=None):
    if repair_project:
        project=Path(repair_project).resolve(strict=True)
        assert project.is_relative_to((BASE/'.jarvis-runtime/python-script-fixture').resolve()) and project.name=='TestCodes'
    else:
        project=BASE/'.jarvis-runtime/python-script-fixture'/uuid4().hex/'TestCodes';project.mkdir(parents=True)
    options={**json.loads((BASE/'config.json').read_text())['brain'],'coding_backend':'codex','codex_workload_enabled':True}
    def report(kind,value):
        if kind=='brain':print(value,flush=True)
    coder=Coder(SimpleNamespace(base=BASE,report=report),SimpleNamespace(options=options))
    result={'date':datetime.now(timezone.utc).isoformat(),'scope':'Exact reported unnamed circle-script request through actual Jarvis workload planner and installed local Codex in an isolated TestCodes fixture. The user project and failed checkpoint are untouched.'}
    try:
        if not repair_project:result['generation']=coder.run(project,GOAL,selected=True)
        receipts=[]
        for directory in (BASE/'.jarvis-runtime/codex-workloads').iterdir():
            path=directory/'receipt.json'
            if path.exists() and json.loads(path.read_text()).get('project')==str(project):receipts.append(directory)
        assert len(receipts)==1
        plan=json.loads((receipts[0]/'plan.json').read_text());receipt=json.loads((receipts[0]/'receipt.json').read_text())
        assert len(plan['tasks'])==1
        if repair_project:
            from jarvis.codex_code import run
            from jarvis.codex_validation import repair_packet, validate_project
            contract={key:plan[key] for key in ('files','checks')}
            fresh=receipts[0]/('fresh-check-'+uuid4().hex);fresh.mkdir()
            validation=validate_project(project,fresh,GOAL,[row['path'] for row in plan['files']],contract,lambda:False,report)
            (fresh/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
            if validation['passed']:result['generation']='Fresh current-source checks already pass; no coding action repeated.'
            else:
                generated=run(coder,project,GOAL,lambda:False,initial_plan=contract,
                    initial_feedback=repair_packet(project,validation,contract),allowed_paths=[row['path'] for row in plan['files']],total_deadline=time.monotonic()+900,return_receipt=True)
                result['generation']={key:generated[key] for key in ('directory','changed','repair_turns','functional_behavior_verified','validation')}
            result['scope']+=' Fresh source/diagnostics inspected for the owned failed fixture; continued its accepted plan without replaying earlier saves.'
        else:assert receipt['status']=='passed'
        implementation=[row['path'] for row in plan['files'] if row['role']!='test']
        assert len(implementation)==1 and all(Path(row['path']).suffix=='.py' for row in plan['files'])
        assert all(check['kind'] in {'python_tests','python_script'} for check in plan['checks'])
        check=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--probe',str(project/implementation[0])],cwd=project,capture_output=True,text=True,timeout=25)
        assert check.returncode==0,check.stderr[-2000:]
        result.update(passed=True,workload_count=1,files=[row['path'] for row in plan['files']],checks=plan['checks'],drawing=json.loads(check.stdout.strip().splitlines()[-1]))
    except Exception as exc:result.update(passed=False,error_type=type(exc).__name__,error=str(exc)[:3000])
    target=BASE/'artifacts/python-script-workload-live-check.json'
    if target.exists():
        history=target.with_name('python-script-workload-live-history.json');rows=json.loads(history.read_text()) if history.exists() else []
        rows.append(json.loads(target.read_text()));history.write_text(json.dumps(rows,indent=2)+'\n')
    target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
    return result['passed']


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--probe':probe(Path(sys.argv[2]))
    elif len(sys.argv)==3 and sys.argv[1]=='--repair-project':raise SystemExit(0 if verify(sys.argv[2]) else 1)
    else:raise SystemExit(0 if verify() else 1)
