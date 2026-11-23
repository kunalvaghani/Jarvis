"""Execute the user's exact Phase E two-create grant; known-ID readback only on reuse."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'app';sys.path.insert(0,str(APP))
HOME=APP/'.jarvis-runtime/lab-validation/e-local-2026-11-04'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--approved-two-creates',action='store_true');args=parser.parse_args()
    if not args.approved_two_creates:parser.error('exact explicit user approval required')
    from jarvis.neural.service import BrainService
    from jarvis.actions import Actions
    from jarvis.engine import Engine
    from jarvis.discovery.adapters.delivery import Ledger
    from jarvis.discovery.model.delivery import sha
    prepared=json.loads((ROOT/'docs/lab/evidence/e-final-export-prepared.json').read_text())
    grant=HOME/'two-create-grant';grant.mkdir(exist_ok=True)
    scope={'scope':'user-approved-phase-e-two-creates-2026-11-04','max_creates':2,'parent_id':prepared['folder_id'],
           'payloads':{r['id']:sha(r['payload']) for r in prepared['deliveries']}}
    authority=grant/'authorization.json'
    if authority.exists():
        if json.loads(authority.read_text())!=scope:raise ValueError('grant differs; never renew')
    else:
        with authority.open('x') as f:json.dump(scope,f)
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':False}}
    service=BrainService(config,HOME/'brain.sqlite3');ledger=Ledger(service.journal);a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=config,APP,service,None;a.report=lambda *args:None
    current={};outcomes=[]
    def approve(kind,detail,cancelled):
        if cancelled() or current['request_file'] not in detail:raise ValueError('scope differs')
        if ledger.payload(current['id'])!=current['payload']:raise ValueError('prepared payload changed')
        slot=grant/(current['payload']['kind']+'-slot.json')
        if slot.exists():
            # Original client construction failed before the ledger's SENT boundary.
            # Preserve the slot and record the inspected, known-not-started boundary;
            # never use this path for an ambiguous provider request.
            row=ledger.row(current['id'])
            old=service.journal.rows("SELECT state,stop_reason FROM goals WHERE text=? ORDER BY rowid DESC LIMIT 1",
                ('lab export '+current['payload']['kind']+' "'+current['request_file']+'"',))
            known='Connect Gmail API locally with launchers/Connect Jarvis Gmail API.cmd; OAuth credentials are never printed.'
            if row['state']!='PREPARED' or row['remote_id'] or not old or old[0]['state']!='uncertain' or not old[0]['stop_reason'].endswith(known):
                raise ValueError('no known pre-client boundary; never replay')
            with (grant/(current['payload']['kind']+'-known-not-started-recovery.json')).open('x') as f:
                json.dump({'boundary':'Files constructor before SENT; credentials absent in scratch root; no provider call',
                           'original_slot_preserved':True,'delivery_id':current['id']},f)
        else:
            with slot.open('x') as f:json.dump({'state':'consumed-before-dispatch','delivery_id':current['id']},f)
    a._approve=approve
    def execute(goal):
        commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate();engine.feed(goal,final=True,raw=goal)
        if len(commands)!=1:raise ValueError('one intake command required')
        return a.execute(commands[0])
    try:
        for item in sorted(prepared['deliveries'],key=lambda r:r['payload']['kind']):
            current.clear();current.update(item);kind=item['payload']['kind'];key=item['id'];started=time.monotonic();error=None
            if item['payload']['parent_id']!=scope['parent_id'] or sha(item['payload'])!=scope['payloads'][key] or ledger.payload(key)!=item['payload']:
                raise ValueError('approved destination/payload changed')
            row=ledger.row(key);slot=grant/(kind+'-slot.json')
            recovery=grant/(kind+'-known-not-started-recovery.json')
            if row['state']=='PREPARED' and not recovery.exists():
                relative=(HOME/item['request_file']).relative_to(APP).as_posix()
                try:execute('lab export '+kind+' "'+relative+'"')
                except Exception as exc:error=type(exc).__name__
            elif not row['remote_id']:error='ConsumedOrUncertainNoReplay'
            row=ledger.row(key)
            if row['remote_id']:
                try:execute('lab export inspect "'+key+'"');error=None
                except Exception as exc:error=type(exc).__name__
            row=ledger.row(key);remote=row['remote_id']
            url=('https://docs.google.com/'+('document' if kind=='report' else 'spreadsheets')+'/d/'+remote+'/edit') if remote else None
            outcomes.append({'kind':kind,'delivery_id':key,'remote_id':remote,'url':url,'state':row['state'],'error_type':error,'seconds':time.monotonic()-started})
        result={'date_local':'2026-11-04 Asia/Calcutta','scope':scope,'outcomes':outcomes,'new_model_solver_calls':0,
                'folders_sharing_deletion':False,'paid_services':False,'global_activation':False,'full_phase_e_acceptance':False}
        path=ROOT/'docs/lab/evidence/e-google-live.json'
        if path.exists():
            # Keep the first outcome; a later known-ID reconciliation gets a distinct receipt.
            path=ROOT/'docs/lab/evidence/e-google-reconciled.json'
        with path.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        print(json.dumps(outcomes))
        if any(row['state']!='VERIFIED' for row in outcomes):
            raise RuntimeError('Export qualification incomplete; inspect retained receipt; no automatic replay')
    finally:service.journal.close()

if __name__=='__main__':main()
