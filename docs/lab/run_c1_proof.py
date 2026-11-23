"""Explicit C1 text-ingress proof using synthetic files, no network or solver."""
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from jarvis.engine import Engine
from jarvis.actions import Actions
from jarvis.neural.service import BrainService
from jarvis.discovery.memory import LabMemory
from jarvis.discovery.adapters.ngspice import environment


def main():
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True}}
    base=ROOT/'app'
    files=list((base/'examples/discovery').glob('*.json'))
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    solver_before=environment()['used_slots']
    service=BrainService(config,base/'.jarvis-runtime/lab-validation/c1-proof.sqlite3')
    actions=Actions.__new__(Actions)
    actions.config,actions.base,actions._neural_service,actions.allowed_tools=config,base,service,None
    results=[]
    try:
        goals=('lab inspect project "examples/discovery/wing-study.json"',
               'lab plan parameter "examples/discovery/wing-study.json" wing.angle delta 3 degree',
               'lab inspect asset "examples/discovery/asset-dossier.json"')
        for goal in goals:
            commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate();engine.feed(goal,final=True,raw=goal)
            if not commands:raise ValueError('text ingress produced no request')
            started=time.monotonic();answer=actions.execute(commands[0]);elapsed=time.monotonic()-started
            row=service.journal.rows('SELECT goal_id,state FROM goals ORDER BY rowid DESC LIMIT 1')[0]
            if row['state']!='verified':raise ValueError('C1 request did not verify')
            fired=[s.get('target_node') for s in service.journal.signals(row['goal_id']) if s['type']=='neuron.fired']
            results.append({'request':goal,'goal_id':row['goal_id'],'seconds':elapsed,'fired':fired,'answer':answer})
        invalid='lab plan parameter "examples/discovery/wing-study.json" wing.angle set 100 degree'
        commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate();engine.feed(invalid,final=True,raw=invalid)
        try:actions.execute(commands[0])
        except ValueError:invalid_refused=True
        else:raise ValueError('invalid bounds were accepted')
        memory=LabMemory(service.journal)
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        from jarvis.discovery.c1 import neurons
        result={'date_local':'2026-11-04 Asia/Calcutta','scope':'synthetic C1 source/dependency integrity, not vehicle/physics acceptance',
                'goals':results,'invalid_bound_refused':invalid_refused,'source_files_unchanged':before==after,
                'typed_components':len(memory.list('Component')),'typed_sources':len(memory.list('Source')),
                'project_snapshots':len(memory.list('RunArtifact')),'ngspice_slots_before':solver_before,
                'ngspice_slots_after':environment()['used_slots'],'c1_nodes_when_flags_off':len(neurons({})),
                'voice_acceptance':'NOT_RUN','live_drive_or_asset_provider':'NOT_RUN','new_dependencies':0}
        if not result['source_files_unchanged'] or result['ngspice_slots_before']!=result['ngspice_slots_after']:
            raise ValueError('proof modified source files or consumed a solver slot')
        (ROOT/'docs/lab/evidence/c1-brain-proof.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='goals'}))
    finally:service.journal.close()


if __name__=='__main__':main()
