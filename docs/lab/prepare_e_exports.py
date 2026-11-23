"""Prepare full Phase E audit export via the real D2 path; deliberately deny creation."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'app';sys.path.insert(0,str(APP))
HOME=APP/'.jarvis-runtime/lab-validation/e-local-2026-11-04'

def main():
    from jarvis.neural.service import BrainService
    from jarvis.actions import Actions
    from jarvis.engine import Engine
    from jarvis.discovery.adapters.delivery import Ledger
    from jarvis.discovery.acceptance import artifact
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':False}}
    with (HOME/'full-export-preparation-started.json').open('x') as f:json.dump({'state':'consumed; deny-only'},f)
    service=BrainService(config,HOME/'brain.sqlite3');a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=config,HOME,service,None
    a.report=lambda *args:None;a.approvals_waiting=0;a.approval_handler=lambda *args:False
    try:
        request={'title':'Jarvis Phase E partial qualification 2026-11-04','parent_id':'0AMVTcmM1XWY0Uk9PVA','artifact_id':'phase-e-local-acceptance'}
        with (HOME/'full-report-request.json').open('x',encoding='utf-8') as f:json.dump(request,f)
        commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate();goal='lab export report "full-report-request.json"';engine.feed(goal,final=True,raw=goal)
        try:a.execute(commands[0])
        except ValueError:pass
        last=service.journal.rows('SELECT state FROM goals ORDER BY rowid DESC LIMIT 1')[0]
        if last['state']!='denied':raise ValueError('write gate must deny during preparation')
        ledger=Ledger(service.journal);selected=[]
        for row in service.journal.rows('SELECT * FROM discovery_deliveries'):
            payload=artifact(service.journal,row['payload_ref'])
            if payload['kind']=='table' or 'phase-e-local-acceptance' in payload.get('text',''):
                if row['state']!='PREPARED' or row['remote_id']:raise ValueError('prepared state changed')
                selected.append({'id':row['id'],'payload':payload,'request_file':'table-request.json' if payload['kind']=='table' else 'full-report-request.json'})
        if len(selected)!=2:raise ValueError('exact full report and table required')
        result={'date_local':'2026-11-04 Asia/Calcutta','folder_id':request['parent_id'],'max_creates':2,
                'scope':'PREPARED ONLY; full Phase E remains unmet, score0 certified, G/H unmet','deliveries':selected}
        with (ROOT/'docs/lab/evidence/e-final-export-prepared.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        print(json.dumps({'prepared':[(r['payload']['kind'],r['payload']['title'],r['id']) for r in selected],'external_writes':0}))
    finally:service.journal.close()

if __name__=='__main__':main()
