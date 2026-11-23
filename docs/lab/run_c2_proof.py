"""Operator-assisted free-local C2 proof; all writes remain gated in real Actions.

--approved-local-output records the user's explicit C2 implementation/test scope:
new owned experiment directories only, fixed local tools, no existing scene edit.
It is not a production approval policy or an approval for other requests/tools.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from jarvis.neural.service import BrainService
from jarvis.actions import Actions
from jarvis.engine import Engine
from jarvis.discovery.model.pendulum import Pendulum,solve,compare_runs
from jarvis.discovery.c2 import NODES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-local-output',action='store_true')
    parser.add_argument('--new-trial',action='store_true',help='deliberately run fresh cases into new owned folders, never overwrite old artifacts')
    args=parser.parse_args()
    if not args.approved_local_output:parser.error('explicit approved owned-output scope required')
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True}}
    base=ROOT/'app';journal=base/'.jarvis-runtime/lab-validation/c2-proof.sqlite3'
    service=BrainService(config,journal);a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=config,base,service,None
    a.approvals_waiting=0;consents=[];current={'goal':None}
    goals=('lab build pendulum "examples/discovery/pendulum.json"',
           'lab build pendulum "examples/discovery/pendulum.json" length delta 0.5 m')
    def approved(kind,detail,cancelled):
        allowed=(not cancelled() and kind=='brain' and current['goal'] in goals
                 and NODES['build'] in detail and 'discovery.geometry.pendulum' in detail)
        if allowed:consents.append({'goal':current['goal'],'scope':detail,
                                  'basis':'user authorized fixed free-local C2 proof and new owned outputs; operator-assisted'})
        return allowed
    a.approval_handler=approved
    records=[];runs=[]
    try:
        for goal in goals:
            current['goal']=goal;commands=[]
            engine=Engine(commands.append,lambda *args:None);engine.activate();engine.feed(goal,final=True,raw=goal)
            if not commands:raise ValueError('text request did not reach Actions')
            existing=service.journal.rows('SELECT goal_id,state FROM goals WHERE text=? AND state=? ORDER BY rowid DESC LIMIT 1',(goal,'verified'))
            started=time.monotonic()
            if existing and not args.new_trial:
                row=existing[0];answer='Reused the previously verified goal; no native mutation replay.'
            else:
                answer=a.execute(commands[0]);row=service.journal.rows('SELECT goal_id,state FROM goals ORDER BY rowid DESC LIMIT 1')[0]
            elapsed=time.monotonic()-started
            if row['state']!='verified':raise ValueError('C2 native goal did not verify')
            # Read actual typed reports emitted by the dispatcher, not a hand-coded answer.
            emitted=[s for s in service.journal.signals(row['goal_id']) if s['type']=='neuron.succeeded' and s.get('task_id')=='build']
            if len(emitted)!=1:raise ValueError('actual native build signal missing or ambiguous')
            bundle=json.loads(service.journal.get(emitted[0]['payload_ref']))
            report=json.loads(service.journal.get(bundle['report']))
            run=json.loads(service.journal.get(report['run_ref']));runs.append(run)
            import hashlib
            source=goal.split('"')[1]
            if hashlib.sha256((base/source).read_bytes()).hexdigest()!=run['input_sha256']:
                raise ValueError('prior verified input changed; no automatic mutation replay')
            from jarvis.discovery.memory import LabMemory
            memory=LabMemory(service.journal)
            for name in ('pendulum.blend','pendulum.obj','pendulum.png'):
                artifact=memory.get(report['experiment_id']+'-'+name.replace('.','-'))
                if hashlib.sha256(Path(artifact.locator).read_bytes()).hexdigest()!=artifact.sha256:
                    raise ValueError('previous native output changed; inspect before new trial')
            records.append({'request':goal,'goal_id':row['goal_id'],'seconds':elapsed,'directory':report['directory'],
                            'metrics':run['metrics'],'answer':answer,'native_build_verified':True,'reused_existing_verified_goal':bool(existing) and not args.new_trial})
        comparison=compare_runs(runs[0],runs[1])
        # A separate, explicitly counted refinement trial checks time-step convergence.
        from jarvis.discovery.sandbox.local_trials import reserve
        ref=service.journal.put({'case':'C2 refinement','model':runs[0]['model']},data_type='Report')
        reserve('scipy-pendulum',ref)
        from jarvis.discovery.sandbox.budget import Budget
        import uuid
        budget=Budget(service.journal);reservation='refinement-'+uuid.uuid4().hex
        budget.reserve(reservation,cpu_s=5,disk_bytes=0)
        refined=solve(Pendulum.model_validate_json(json.dumps(runs[0]['model'])),max_step=0.01)
        budget.settle(reservation,cpu_s=refined['cpu_s'],disk_bytes=0)
        error=max(abs(a['theta_rad']-b['theta_rad']) for a,b in zip(runs[0]['samples'],refined['samples']))
        if error>1e-8:raise ValueError('time-step refinement check failed')
        result={'date_local':'2026-11-04 Asia/Calcutta','operator_assisted':True,'goals':records,'scoped_approvals':consents,
                'controlled_comparison':comparison,'refinement_max_angle_difference_rad':error,
                'new_packages':0,'gpu_rendering':False,'microphone_or_live_jarvis_ui':'NOT_RUN',
                'scope':'ideal rigid pendulum, actual SciPy dynamics/native geometry/hinge/kinematic display; no Bullet/FEA/CFD or physical validation'}
        (ROOT/'docs/lab/evidence/c2-brain-proof.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k not in ('goals','scoped_approvals')}))
    finally:service.journal.close()


if __name__=='__main__':main()
