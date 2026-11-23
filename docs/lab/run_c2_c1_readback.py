"""Read-only C1 inspection/planning over actual C2 native output; no native replay."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from jarvis.actions import Actions
from jarvis.engine import Engine
from jarvis.neural.service import BrainService
from jarvis.discovery.adapters.ngspice import environment

def main():
    base=ROOT/'app';proof=json.loads((ROOT/'docs/lab/evidence/c2-brain-proof.json').read_text(encoding='utf-8'))
    folder=Path(proof['goals'][-1]['directory']);source=folder/'component-project.json'
    data=json.loads(source.read_text(encoding='utf-8'));parameter=next(b['parameter']['id'] for b in data['parameters'] if b['parameter']['name']=='length')
    relative=source.relative_to(base).as_posix();before=hashlib.sha256(source.read_bytes()).hexdigest();slots=environment()['used_slots']
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True}}
    service=BrainService(config,base/'.jarvis-runtime/lab-validation/c2-c1-readback.sqlite3')
    a=Actions.__new__(Actions);a.config,a.base,a._neural_service,a.allowed_tools=config,base,service,None
    records=[]
    try:
        for goal in (f'lab inspect project "{relative}"',f'lab plan parameter "{relative}" {parameter} delta 0.1 m'):
            commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate();engine.feed(goal,final=True,raw=goal)
            if not commands:raise ValueError('ingress missing')
            answer=a.execute(commands[0]);row=service.journal.rows('SELECT goal_id,state FROM goals ORDER BY rowid DESC LIMIT 1')[0]
            if row['state']!='verified':raise ValueError('C1 inspection/plan failed')
            records.append({'request':goal,'goal_id':row['goal_id'],'state':row['state'],'answer':answer})
        after=hashlib.sha256(source.read_bytes()).hexdigest()
        if before!=after or slots!=environment()['used_slots']:raise ValueError('read/plan changed source or solver usage')
        result={'date_local':'2026-11-04 Asia/Calcutta','goals':records,'source_sha256':before,'source_unchanged':True,'ngspice_used_before_after':[slots,environment()['used_slots']],
                'scope':'Actual generated native component graph inspected and bounded downstream plan verified through C1; plan does not execute geometry or solvers.'}
        (ROOT/'docs/lab/evidence/c2-c1-readback.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='goals'}))
    finally:service.journal.close()
if __name__=='__main__':main()
