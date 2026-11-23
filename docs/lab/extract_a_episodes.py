"""Read-only reconstruction of old A traces; never invent missing instrumentation.

Exact retained TaskState arguments/Journal proposals are preserved privately.
Old logs lack stage-bound state digests: these stay null, with separate hashes
of observed evidence. The new production StageJournal records exact digests.
"""
import hashlib,json,re,sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'app/.jarvis-runtime/lab-validation'


def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def extract(home):
    receipt=json.loads((home/'result-private.json').read_text(encoding='utf-8'))
    events=[json.loads(line) for line in (home/'events-private.jsonl').read_text(encoding='utf-8').splitlines()]
    exact={}
    for path in (home/'task-owner').rglob('task_state.json'):
        state=json.loads(path.read_text(encoding='utf-8'))
        def visit(value):
            if isinstance(value,dict):
                if 'action' in value and 'value' in value:
                    exact.setdefault(value['action']+' '+str(value['value']),[]).append(value)
                for child in value.values():visit(child)
            elif isinstance(value,list):
                for child in value:visit(child)
        visit(state)
    db=sqlite3.connect((home/'brain.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    proposals=[]
    try:
        tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'discovery_planner_calls' in tables:
            for row in db.execute('SELECT * FROM discovery_planner_calls'):
                body=db.execute('SELECT body FROM artifacts WHERE ref=?',(row['proposal_ref'],)).fetchone()
                if body:proposals.append({'call_state':row['state'],'goal_id':row['goal_id'],'proposal':json.loads(body[0])})
    finally:db.close()
    rows=[];observed=set();pending=None;first=None
    for n,event in enumerate(events):
        kind=event['kind'];value=event['value']
        if kind=='plan' and not value.startswith('Revised remaining tasks:'):
            command=value.removeprefix('Next from current screen: ')
            if not re.match(r'^[a-z_]+ ',command):continue
            name,argument=command.split(' ',1)
            matches=exact.get(command,[])
            args=({k:matches[0][k] for k in ('action','value','content','folder','browser','expected','find','platform') if k in matches[0]}
                  if matches else {'action':name,'value':argument})
            pending={'event_index':n,'stage':'legacy_unstaged','action':name,'arguments':args,
                'arguments_complete':bool(matches),'elapsed_s':event['elapsed_s'],'pre_state_digest':None,'post_state_digest':None,
                'observed_evidence_before':sha(sorted(observed)),'observed_evidence_after':None,
                'outcome':'proposal_only','artifact_refs':[],'budget_usage':None,'retry_reason':None}
            rows.append(pending)
        if kind=='action' and pending is not None:
            refs=sorted(set(re.findall(r'artifact://sha256/[a-f0-9]{64}',value)))
            observed.update(refs);pending.update(outcome='tool_result_observed',artifact_refs=refs,
                observed_evidence_after=sha(sorted(observed)),tool_output_partial=len(value)>=16000,
                duration_s=event['elapsed_s']-pending['elapsed_s'])
            pending=None
        if kind=='brain' and 'repeated an earlier action' in value and first is None:
            first={'elapsed_s':event['elapsed_s'],'event_index':n,'observed_reason':value,
                'meaning':'proposal rejected before replay; not evidence that a side effect was executed twice'}
        if kind in ('repair','attempt_error') and rows:rows[-1]['retry_reason']=value
    return {'case':receipt['case'],'goal':receipt['goal'],'episodes':rows,'journal_proposals':proposals,
        'first_logged_no_progress':first,'terminal_error':receipt.get('error'),
        'model_calls':receipt.get('model_calls'),'source_hash_unchanged':receipt.get('source_sha256_before')==receipt.get('source_sha256_after'),
        'limits':'Historical logs have no authoritative per-stage state digest or full resource accounting; null is retained, never reconstructed as fact.'}


def main():
    out=BASE/'episode-audit-2026-11-06';out.mkdir(exist_ok=False);summaries=[]
    for home in sorted(BASE.glob('a-a[12]-attempt-*')):
        if not (home/'result-private.json').is_file():continue
        result=extract(home);(out/(home.name+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        summaries.append({'attempt':home.name,'case':result['case'],'observed_proposals':len(result['episodes']),
            'first_logged_no_progress':result['first_logged_no_progress'],'source_hash_unchanged':result['source_hash_unchanged']})
    public={'date':'2026-11-06','scope':'historical reconstruction, not new autonomous acceptance','attempts':summaries,
        'private_exact_arguments_retained':True,'historical_missing_fields_not_fabricated':True}
    (ROOT/'docs/lab/evidence/a-episode-audit-2026-11-06.json').write_text(json.dumps(public,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'attempts':len(summaries),'output':out.relative_to(ROOT).as_posix()}))


if __name__=='__main__':main()
