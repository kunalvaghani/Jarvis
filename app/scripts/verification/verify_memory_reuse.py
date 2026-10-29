"""Real persisted-library reuse trial. Never supplies a target implementation."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import sqlite3
from pathlib import Path
import sys
import time
from uuid import uuid4

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
from verify_autonomous_repair import source_manifest
from accept_search_feature import fingerprints

REQUEST=('Create a new Python command-line notes application that supports adding, listing, removing and searching notes. '
         'Reuse the verified notes implementation already in your code library where compatible and retain its provenance. '
         'Include input validation and tests that launch the real CLI. Save it as a new isolated project.')


def main():
    from jarvis.campaign_pause import assert_allowed
    assert_allowed(whole_campaign=True)
    parser=argparse.ArgumentParser();parser.add_argument('--source-run',type=Path,required=True)
    parser.add_argument('--workspace-parent',type=Path,required=True);parser.add_argument('--seconds',type=int,default=900)
    args=parser.parse_args();base=args.source_run.resolve(strict=True)
    if base.parent!=(BASE/'.jarvis-runtime/autonomous-repair').resolve():parser.error('Use a directly owned prior campaign.')
    prior=json.loads((base/'campaign.json').read_text(encoding='utf-8'))
    original=Path(prior['workspace_parent']).resolve(strict=True);original_hashes=fingerprints(original)
    gates=[json.loads(p.read_text(encoding='utf-8')) for p in base.glob('independent-acceptance-*.json')]
    if not any(g.get('status')=='PASS' and g.get('artifact_hashes')==original_hashes for g in gates):
        parser.error('Prior controlled project needs fresh matching independent acceptance; nothing changed.')
    root=base/'reuse-trials'/uuid4().hex;root.mkdir(parents=True)
    workspace=args.workspace_parent.resolve(strict=True)/root.name;workspace.mkdir()
    config_bytes=(BASE/'config/config.json').read_bytes();config_before=hashlib.sha256(config_bytes).hexdigest()
    config=json.loads(config_bytes)
    config['files_root']='files';config['project_roots']=[str(workspace),str(original)]
    config['memory']={**config.get('memory',{}),'enabled':False,'vault':str(base/'vault')}
    config['pcide']={**config.get('pcide',{}),'online_research':False}
    config['brain']={**config['brain'],'coding_backend':'jarvis','native_max_workers':1,'max_coding_seconds':args.seconds}
    config['project_intelligence']={**config.get('project_intelligence',{}),'enabled':True,
        'default_workspace':str(workspace),'search_roots':[],'search_home':False}
    for key in ('anticipation','realtime','self_evolution','cognitive_awareness','screen_awareness'):
        config[key]={**config.get(key,{}),'enabled':False}
    before_source=source_manifest()
    (root/'jarvis-source-before.json').write_text(json.dumps(before_source,indent=2),encoding='utf-8')
    campaign_started=time.monotonic();started=None
    record={'case':12,'date':datetime.now(timezone.utc).isoformat(),'result':'NOT_RUN','request':REQUEST,
        'root':str(root),'runtime_base':str(base),'workspace_parent':str(workspace),'source_campaign':base.name,
        'scope':'Production typed control saves the actual prior verified component, then production project intake/coding reads the same persisted library. Online research disabled. Prior Notes project is a controlled Test 9 fixture with a Jarvis-generated search addition, not a wholly autonomous fresh app.',
        'supervisor_supplied_target_implementation':False,'commands':[]}
    from jarvis.gpu_scheduler import configured
    record.update(configuration_sha256=config_before,gpu_policy=configured(),
        coding_policy={k:config['brain'].get(k) for k in ('native_max_turns','native_max_repairs','native_max_workers','max_coding_seconds')})
    actions=None;prior_ids=set();prior_native=set();prior_research=set()
    def save():(root/'campaign.json').write_text(json.dumps(record,indent=2,default=str),encoding='utf-8')
    def report(kind,value=''):
        with (root/'events.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps({'at':time.time(),'kind':kind,'value':value},default=str,ensure_ascii=False)+'\n')
        if kind=='task_decision' and isinstance(value,dict) and value.get('status')=='PENDING' and actions is not None:
            actions.ingress.decisions.presented(value['id'])
        if kind in {'spoken_reply','answer','warning','question','repair'}:print(kind,str(value)[:700],flush=True)
    save();print('REUSE_CAMPAIGN '+str(root),flush=True)
    try:
        from jarvis.actions import Actions
        from jarvis.engine import Engine
        actions=Actions(config,base,report)
        prior_ids={r['id'] for r in actions.ingress.store.rows()}
        prior_native={p.name for p in (base/'.jarvis-runtime/native-code').glob('*')}
        prior_research={r['id'] for r in actions.code_intel.broker.research()}
        record['metrics_before']=actions.code_intel.broker.metrics()
        actions.ingress.start();actions.thread.start();engine=Engine(actions.submit,report)
        def feed(text):
            record['commands'].append({'at':time.time(),'text':text});save()
            engine.activate();engine.feed(text,final=True,raw=text)
        feed('Save the verified notes component for future projects.')
        deadline=time.monotonic()+30;items=[]
        while time.monotonic()<deadline:
            items=[r for r in actions.code_intel.memory.all() if r['name']=='notes' and r['scope']=='global' and r['state']=='REUSABLE']
            if items:break
            time.sleep(.2)
        if not items:raise ValueError('Production save control did not produce a reusable notes component; no new project requested.')
        item=actions.code_intel.memory.verified_source(items[0]['id'])
        record['prior_component']={k:item.get(k) for k in ('id','name','state','scope','origin','license','license_files','repository','commit','tests')}
        record['prior_component']['source_sha256']=hashlib.sha256(item['source'].encode('utf-8')).hexdigest()
        feed(REQUEST)
        started=time.monotonic();last=None;idle=None
        while time.monotonic()-started<args.seconds:
            rows=[r for r in actions.ingress.store.rows() if r['id'] not in prior_ids]
            snapshot=[(r['id'],r['state']) for r in rows]
            if snapshot!=last:
                record.update(tasks=[{k:r.get(k) for k in ('id','state','command','outcome','checkpoint')} for r in rows],
                    projects=actions.project_intel.store.all(),seconds=round(time.monotonic()-started,3));save();last=snapshot
                print('TASKS '+str(snapshot),flush=True)
            active=[r for r in rows if r['state'] not in {'COMPLETED','FAILED','PARTIAL','CANCELLED'}]
            failed_only=any(r['state']=='FAILED' for r in rows) and active and all(r['state'] in {'WAITING_DEPENDENCY','WAITING_USER'} for r in active)
            if rows and (not active or failed_only) and not any(d['status']=='PENDING' for d in actions.ingress.decisions.rows()):
                idle=idle or time.monotonic()
                if time.monotonic()-idle>12:break
            else:idle=None
            time.sleep(.5)
        record.update(result='FAIL',reason='Independent retrieval/adaptation/application verification required; no benchmark benefit is assumed.')
        record['metrics_after']=actions.code_intel.broker.metrics()
        record['native_runs']=[p.name for p in (base/'.jarvis-runtime/native-code').glob('*') if p.name not in prior_native]
        record['researches']=[r for r in actions.code_intel.broker.research() if r['id'] not in prior_research]
    except Exception as error:record.update(result='BLOCKED',reason=str(error),error_type=type(error).__name__)
    finally:
        record['coding_observation_seconds']=round(time.monotonic()-started,3) if started is not None else None
        record['seconds_scope']='Latest task-state-change snapshot only; use coding_observation_seconds and record_to_shutdown_seconds for their named intervals.'
        if actions is not None:
            actions.close()
            record['tasks_at_limit']=record.get('tasks',[])
            with sqlite3.connect((base/'.jarvis-runtime/task-queue.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as con:
                con.row_factory=sqlite3.Row
                record['tasks']=[{k:(json.loads(r[k]) if k in {'command','checkpoint'} else r[k])
                    for k in ('id','state','command','outcome','checkpoint')} for r in con.execute('SELECT * FROM tasks ORDER BY number') if r['id'] not in prior_ids]
        record['original_project_unchanged']=fingerprints(original)==original_hashes
        record['jarvis_source_changed_during_trial']=source_manifest()!=before_source
        record['configuration_changed_during_trial']=hashlib.sha256((BASE/'config/config.json').read_bytes()).hexdigest()!=config_before
        record['record_to_shutdown_seconds']=round(time.monotonic()-campaign_started,3)
        record['finished_at']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({k:record.get(k) for k in ('result','reason','root','original_project_unchanged')},indent=2),flush=True)


if __name__=='__main__':main()
