"""Explicitly approved compact-v2 qualification; separate durable grant, old charges untouched."""
import argparse,json,hashlib,sys,time
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'app';sys.path.insert(0,str(BASE))
from jarvis.discovery.sandbox.budget import Budget as Original
from jarvis.neural.service import BrainService
from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.brain import BrainClient
SCOPE=(BASE/'.jarvis-runtime/lab-validation/c3-proof.sqlite3').resolve()
class Scoped(Original):
    def __init__(self,journal,**kwargs):
        if journal.path.resolve()==SCOPE:kwargs['cpu_s']=530
        super().__init__(journal,**kwargs)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--approved-c3-wire-530',action='store_true');args=parser.parse_args()
    if not args.approved_c3_wire_530:parser.error('explicit compact-v2 grant required')
    ledger=BASE/'.jarvis-runtime/lab-validation/c3-compact-wire-grant';ledger.mkdir(exist_ok=True)
    grant={'scope':'user-approved-c3-compact-wire-530-2026-11-04','day':datetime.now(timezone.utc).date().isoformat(),'max_calls':2,'cpu_allowance':530,'journal':str(SCOPE)}
    file=ledger/'authorization.json'
    if file.exists():
        if json.loads(file.read_text())!=grant:raise ValueError('grant changed/expired; do not renew automatically')
    else:
        with file.open('x',encoding='utf-8') as handle:json.dump(grant,handle)
    if all((ledger/f'slot-{i}.json').exists() for i in range(2)):raise ValueError('compact-v2 grant exhausted; no inference')
    import requests
    session=requests.Session();session.trust_env=False
    names={r['name'] for r in session.get('http://127.0.0.1:11434/api/tags',timeout=5).json()['models']}
    if not {'qwen3.5:0.8b','qwen3.5:9b'}<=names:raise ValueError('approved models unavailable; no startup/download')
    options=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))['brain']
    if options.get('planner')!='qwen3.5:9b':raise ValueError('configured model differs from scope')
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'research':True,'sim':True}}
    records=[];s=None
    try:
        with patch('jarvis.discovery.sandbox.budget.Budget',Scoped):
            s=BrainService(config,SCOPE);a=Actions.__new__(Actions)
            a.config,a.base,a._neural_service,a.allowed_tools=config,BASE,s,None
            a.execute(Command('task','lab lookup doi "10.1126/science.1192720"'))
            review=s.journal.rows('SELECT id FROM discovery_reviews ORDER BY rowid DESC LIMIT 1')[0]['id']
            for index,(mode,bound) in enumerate((('quick ',25),('',95))):
                slot=ledger/f'slot-{index}.json'
                try:
                    with slot.open('x',encoding='utf-8') as handle:json.dump({'state':'consumed-before-dispatch','mode':mode or 'configured'},handle)
                except FileExistsError:continue
                client=BrainClient(BASE,options);client.timeout_seconds=90;a.brain=SimpleNamespace(client=client)
                started=time.monotonic();answer=None;error=None
                try:answer=a.execute(Command('task','lab hypothesize '+mode+'"'+review+'"'),lambda:time.monotonic()-started>=bound)
                except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)[:500]}
                finally:client.close()
                row=s.journal.rows('SELECT goal_id,state FROM goals ORDER BY rowid DESC LIMIT 1')[0]
                item={'mode':mode or 'configured','goal_id':row['goal_id'],'state':row['state'],'seconds':time.monotonic()-started,'error':error,
                      'answer_sha256':hashlib.sha256(answer.encode()).hexdigest() if answer else None}
                records.append(item);print(json.dumps(item),flush=True)
    finally:
        result={'date_local':'2026-11-04 Asia/Calcutta','scope':grant,'attempts':records,'old_grant_reused':False,'global_policy_changed':False,'new_packages':0,'new_paid_inference':0}
        if s:
            result['model_reservations']=s.journal.rows("SELECT cpu_s,state FROM discovery_budget WHERE id LIKE 'hypotheses-%'");s.journal.close()
        (ROOT/'docs/lab/evidence/c3-compact-wire-proof.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return 0 if len(records)==2 and all(r['state']=='verified' for r in records) else 1
if __name__=='__main__':raise SystemExit(main())
