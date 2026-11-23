"""Explicitly approved two-create Google qualification, durable grant, no other external writes."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'app';sys.path.insert(0,str(APP))
PROOF=APP/'.jarvis-runtime/lab-validation/d2-live-root'

def main():
    p=argparse.ArgumentParser();p.add_argument('--approved-two-creates',action='store_true');args=p.parse_args()
    if not args.approved_two_creates:p.error('explicit user approval required')
    prepared=json.loads((ROOT/'docs/lab/evidence/d2-live-prepared.json').read_text())
    grant=PROOF/'two-create-grant';grant.mkdir(exist_ok=True)
    authorization={'scope':'user-approved-d2-two-creates-2026-11-04','max_creates':2,'parent_id':prepared['folder_id'],
        'payloads':{row['id']:hashlib.sha256(json.dumps(row['payload'],sort_keys=True).encode()).hexdigest() for row in prepared['deliveries']}}
    if (grant/'authorization.json').exists():
        if json.loads((grant/'authorization.json').read_text())!=authorization:raise ValueError('authorization differs; do not renew')
    else:
        with (grant/'authorization.json').open('x') as f:json.dump(authorization,f)
    from jarvis.neural.service import BrainService
    from jarvis.actions import Actions
    from jarvis.commands import Command
    from jarvis.discovery.adapters.delivery import Ledger
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':True}}
    s=BrainService(config,PROOF/'brain.sqlite3');ledger=Ledger(s.journal)
    a=Actions.__new__(Actions);a.config,a.base,a._neural_service,a.allowed_tools=config,APP,s,None;a.report=lambda *args:None
    outcomes=[];current={}
    def approve(tool,summary,cancelled):
        if cancelled() or current['path'] not in summary:raise ValueError('approval scope differs')
        with (grant/(current['kind']+'-slot.json')).open('x') as f:
            json.dump({'state':'consumed-before-dispatch','delivery_id':current['id'],'scope':authorization['scope']},f)
    a._approve=approve
    try:
        for kind in ('report','table'):
            payload=next(row for row in prepared['deliveries'] if row['payload']['kind']==kind)
            key=payload['id'];body=ledger.payload(key)
            if body!=payload['payload'] or body['parent_id']!=authorization['parent_id']:raise ValueError('prepared payload changed')
            relative=(PROOF/(kind+'-request.json')).relative_to(APP).as_posix()
            current.update(kind=kind,path=relative,id=key)
            row=ledger.row(key);started=time.monotonic();error=None
            if row['state']=='PREPARED' and not (grant/(kind+'-slot.json')).exists():
                try:a.execute(Command('task','lab export '+kind+' "'+relative+'"'))
                except Exception as exc:error=type(exc).__name__
            elif not row['remote_id']:error='ConsumedOrUncertainNoReplay'
            row=ledger.row(key)
            if row['remote_id']:
                try:a.execute(Command('task','lab export inspect "'+key+'"'));error=None
                except Exception as exc:error=type(exc).__name__
            row=ledger.row(key);url=('https://docs.google.com/'+('document' if kind=='report' else 'spreadsheets')+'/d/'+row['remote_id']+'/edit') if row['remote_id'] else None
            outcomes.append({'kind':kind,'delivery_id':key,'state':row['state'],'remote_id':row['remote_id'],'url':url,'seconds':time.monotonic()-started,'error_type':error})
            print(json.dumps(outcomes[-1]),flush=True)
        doc=next((r for r in outcomes if r['kind']=='report' and r['state']=='VERIFIED'),None)
        source_verified=False
        if doc:
            try:
                a.execute(Command('task','lab source drive-id "'+doc['remote_id']+'"'));source_verified=True
            except Exception:pass
        result={'date_local':'2026-11-04 Asia/Calcutta','scope':authorization,'outcomes':outcomes,
            'created_doc_source_read_verified':source_verified,'new_model_solver_calls':0,'new_folders':0,'shared_or_deleted':False,
            'global_flags_changed':False,'paid_services':False}
        (ROOT/'docs/lab/evidence/d2-google-live.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        if not all(r['state']=='VERIFIED' for r in outcomes) or not source_verified:raise ValueError('one or more live gates unmet; retained state, no duplicate creation')
    finally:s.journal.close()
if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'state':'LIVE_PROOF_BLOCKED','error_type':type(exc).__name__}));raise SystemExit(1)
