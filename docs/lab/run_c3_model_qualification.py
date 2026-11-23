"""Operator-only C3 qualification under explicit 120->300 scratch allowance approval.
No product/default policy edit. Two fresh owned clients maximum; 95s outer cancellation.
"""
import argparse,hashlib,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'app';sys.path.insert(0,str(BASE))
from jarvis.discovery.sandbox.budget import Budget as OriginalBudget
from jarvis.neural.service import BrainService
from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.brain import BrainClient
SCOPE=(BASE/'.jarvis-runtime/lab-validation/c3-proof.sqlite3').resolve()

class ScopedBudget(OriginalBudget):
    def __init__(self,journal,**kwargs):
        if journal.path.resolve()==SCOPE:
            if kwargs.get('cpu_s',120)!=120:raise ValueError('unexpected preexisting budget override')
            kwargs['cpu_s']=300
        super().__init__(journal,**kwargs)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--approved-scratch-cpu-300',action='store_true');args=parser.parse_args()
    if not args.approved_scratch_cpu_300:parser.error('explicit user-approved scratch quota scope required')
    slots=BASE/'.jarvis-runtime/lab-validation/c3-model-extension-300'
    from jarvis.skill_memory import linked
    if any(linked(p) for p in (slots,*slots.parents)):raise ValueError('linked approval ledger')
    slots.mkdir(exist_ok=True)
    grant=slots/'authorization.json'
    if not grant.is_file():raise ValueError('recorded approval grant required; do not create or renew it from this runner')
    authorized=json.loads(grant.read_text(encoding='utf-8'))
    if authorized!={'scope':'user-approved-c3-scratch-cpu-300-2026-11-04','cpu_allowance':300,'max_additional_attempts':2,
                    'budget_day':datetime.now(timezone.utc).date().isoformat(),'journal':str(SCOPE)}:
        raise ValueError('approval scope/day changed or expired; no inference')
    if all((slots/f'attempt-{i}.json').exists() for i in range(2)):
        parser.error('both approved additional attempts consumed; no automatic reset or inference')
    import requests
    session=requests.Session();session.trust_env=False
    tags=session.get('http://127.0.0.1:11434/api/tags',timeout=5);tags.raise_for_status()
    if 'qwen3.5:9b' not in {m['name'] for m in tags.json()['models']}:raise ValueError('approved installed model unavailable; no start or download')
    options=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))['brain']
    if options.get('planner')!='qwen3.5:9b':raise ValueError('configured model no longer matches approval')
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'research':True,'sim':True}}
    records=[];s=None
    try:
        with patch('jarvis.discovery.sandbox.budget.Budget',ScopedBudget):
            s=BrainService(config,SCOPE);a=Actions.__new__(Actions)
            a.config,a.base,a._neural_service,a.allowed_tools=config,BASE,s,None
            a.execute(Command('task','lab lookup doi "10.1126/science.1192720"'))
            review=s.journal.rows('SELECT id FROM discovery_reviews ORDER BY rowid DESC LIMIT 1')[0]['id']
            for attempt in range(2):
                try:
                    with (slots/f'attempt-{attempt}.json').open('x',encoding='utf-8') as handle:
                        json.dump({'state':'consumed-before-dispatch','scope':authorized['scope']},handle)
                except FileExistsError:continue
                client=BrainClient(BASE,options);client.timeout_seconds=90;a.brain=SimpleNamespace(client=client)
                started=time.monotonic();error=None;answer=None
                try:
                    answer=a.execute(Command('task','lab hypothesize "'+review+'"'),lambda:time.monotonic()-started>=95)
                except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)[:500]}
                finally:client.close()
                row=s.journal.rows('SELECT goal_id,state FROM goals ORDER BY rowid DESC LIMIT 1')[0]
                records.append({'attempt':attempt+1,'goal_id':row['goal_id'],'state':row['state'],'seconds':time.monotonic()-started,
                    'error':error,'answer_sha256':hashlib.sha256(answer.encode()).hexdigest() if answer else None,
                    'answer':'\n'.join(line for line in (answer or '').splitlines() if ' excerpt: ' not in line)})
                if row['state']=='verified':break
    finally:
        result={'date_local':'2026-11-04 Asia/Calcutta','approval':'explicit user reply: Approve scoped CPU extension',
                'scope':'existing C3 scratch Journal only; 300 admission units, prior reservations retained; max two existing-local 9B goals',
                'attempts':records,'success':any(r['state']=='verified' for r in records),'new_packages':0,'paid_provider_calls':0,
                'global_policy_changed':False,'production_flags_activated':False}
        if s:
            result['model_reservations']=s.journal.rows("SELECT cpu_s,state FROM discovery_budget WHERE id LIKE 'hypotheses-%'")
            s.journal.close()
        (ROOT/'docs/lab/evidence/c3-model-qualification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='attempts'}))
    return 0 if result['success'] else 1
if __name__=='__main__':raise SystemExit(main())
