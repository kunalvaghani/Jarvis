"""Actual Jarvis router/dispatcher, three public pinned repos, isolation and local LLM.

The user's implementation request explicitly authorizes these named repository
trials. That narrow test authorization is not an unattended production bypass.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import sys

from jarvis.actions import Actions
from jarvis.commands import Command,parse
from jarvis.repository_skills import RepositorySkills,engine
from jarvis.tools import ToolRegistry

BASE=Path(__file__).resolve().parents[2]
CASES=[
    ('https://github.com/mahmoud/boltons','boltons.iterutils','chunked',{'src':[1,2,3,4,5],'size':2},[[1,2],[3,4],[5]]),
    ('https://github.com/pypa/packaging','packaging.specifiers','SpecifierSet.contains',
     {'constructor':{'specifiers':'>=1.2,<2.0'},'arguments':{'item':'1.5'}},True),
    ('https://github.com/agronholm/anyio','anyio._core._eventloop','sleep',{'delay':0.02},None),
]


def main():
    started=time.monotonic();report={'date':datetime.now(timezone.utc).isoformat(),'passed':False,
        'scope':'Actual Actions command routing and ToolRegistry dispatch; three real pinned public repositories, hardened container execution, reconstructed registries and real local Qwen tool proposals. No microphone or user project controlled.',
        'approval_scope':'Explicit human implementation task authorizes only these three public repository trials; production per-call UI approval remains required.','repositories':[]}
    config=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'));config['_ui_verification']=True
    config['files_root']='.jarvis-runtime/repository-demo-files';config['apps']={}
    config['memory']={**config.get('memory',{}),'enabled':True,'vault':'.jarvis-runtime/repository-demo-memory','hermes_skills':False}
    actions=Actions(config,BASE,lambda *a:None);actions.memory.start()
    allowed={hashlib.sha256(case[0].encode()).hexdigest()[:20] for case in CASES};approved=[]
    def permission(kind,detail,cancelled):
        request=json.loads(detail)
        if kind not in {'repository_skill_validation','repository_skill_activation','repository_skill_execution'}:return False
        skill=engine(actions).get(request['skill'])
        if skill['repo_id'] not in allowed or cancelled():return False
        approved.append({'kind':kind,'skill':request['skill']});return True
    actions.approval_handler=permission
    def dispatch(action,identifier,arguments=None):
        content=json.dumps(arguments) if arguments is not None else ''
        return json.loads(actions.execute(Command('toolkit',action,json.dumps({'value':identifier,'content':content})),lambda:False))
    try:
        if '--restart-check' in sys.argv:
            previous=json.loads((BASE/'artifacts/reports/repository-skills-live.json').read_text(encoding='utf-8'))
            assert previous['passed']
            beats=list((BASE/'.jarvis-runtime').glob('heartbeat-*.json'))
            assert beats,'No supervised Jarvis heartbeat after restart.'
            beat=json.loads(max(beats,key=lambda p:p.stat().st_mtime).read_text())
            assert time.time()-beat['at']<20 and beat.get('session') and beat.get('status')=='running','Jarvis heartbeat is stale or not running.'
            report['application_heartbeat']={k:beat[k] for k in ('pid','session','at')}
            report['application_health']=beat.get('health',{})
            assert report['application_health'].get('workers',{}).get('actions'),'Jarvis action worker is not healthy.'
            for (url,module,symbol,args,expected),prior in zip(CASES,previous['repositories']):
                assert prior['url']==url
                identifier=prior['skill_id']
                definition=next(r for r in ToolRegistry(actions).catalog(symbol) if r['action']==identifier)
                result=dispatch('repository_skill_run',identifier,args)
                assert result['value']==expected
                report['repositories'].append({'url':url,'skill_id':identifier,'discoverable':bool(definition),'actual_result':result['value'],'passed':True})
            report['scope']='Fresh Actions/ToolRegistry execution after actual supervised Jarvis restart; production process heartbeat checked. No re-learning, revalidation or activation in this check; per-call trial approval remains scoped.'
            report['passed']=True
            return 0
        for url,module,symbol,args,expected in CASES:
            row={'url':url,'passed':False};report['repositories'].append(row)
            try:
                learned=json.loads(actions.execute(parse('learn repository '+url),lambda:False))
                row.update({k:learned[k] for k in ('commit','revision','candidates','supported_candidates','files_scanned')})
                registry=engine(actions)
                with registry.connect() as db:
                    found=[dict(r) for r in db.execute('SELECT id,entity FROM skills WHERE repo_id=? AND revision=?',(learned['repo_id'],learned['revision']))]
                selected=next(r for r in found if json.loads(r['entity'])['module']==module and json.loads(r['entity'])['symbol']==symbol)
                identifier=selected['id'];row['skill_id']=identifier;row['capability']=module+'.'+symbol
                row['validation']=dispatch('repository_skill_validate',identifier,{'arguments':args})
                assert row['validation']['value']==expected
                dispatch('repository_skill_activate',identifier)
                result=dispatch('repository_skill_run',identifier,args);assert result['value']==expected
                row['actual_result']=result['value'];row['async']=json.loads(selected['entity'])['async']
                from jarvis.native_tools import plan
                from jarvis.knowledge_worker import session
                definition=next(r for r in ToolRegistry(actions).catalog(symbol) if r['action']==identifier)
                with session() as client:
                    client.gpu_role='planner'
                    proposed=plan(client,'qwen3.5:9b','You are Jarvis. Call the provided repository capability once with the exact requested JSON arguments. Return a tool call; do not claim a result before execution.',
                        {'goal':'Call '+identifier+' with exactly '+json.dumps(args),'tools':[definition]},
                        {'timeout_seconds':180,'num_predict':1200})
                step=proposed['steps'][0];assert step['action']=='repository_skill_run' and step['value']==identifier
                assert json.loads(step['content'])==args,'Model changed the exact requested arguments.'
                llm_result=json.loads(actions.brain.dispatch(step,lambda:False).evidence);assert llm_result['value']==expected
                row['llm_to_dispatcher']={'passed':True,'model':proposed['model_used'],'native_tool_calling':proposed.get('native_tool_calling'),'actual_result':llm_result['value']}
                reconstructed=RepositorySkills(BASE,config['repository_skills'],actions.memory)
                actions.repository_skills=reconstructed;actions.memory.repository_skills=reconstructed
                again=dispatch('repository_skill_run',identifier,args);assert again['value']==expected
                row['restart_registry_passed']=True
                dispatch('repository_skill_lifecycle',identifier,{'operation':'disable'})
                try:dispatch('repository_skill_run',identifier,args)
                except ValueError:row['disabled_execution_blocked']=True
                else:raise AssertionError('Disabled skill still executed.')
                # Restore only these explicitly authorized trial capabilities for
                # the final real-app restart check; future calls still need UI approval.
                dispatch('repository_skill_validate',identifier,{'arguments':args})
                dispatch('repository_skill_activate',identifier)
                row['final_state']='ACTIVE'
                row['passed']=True
            except Exception as error:row.update(error_type=type(error).__name__,error=str(error)[:2000])
            print(json.dumps({'repository':url,'passed':row['passed'],'error':row.get('error')}),flush=True)
        report['persistent_memory_answer']=actions.memory.catalogue_answer('what new abilities did you learn?')
        notes=list((actions.memory.vault/'Daily').glob('*.md'))
        report['memory_outcome_notes']=any('repository_skill' in p.read_text(encoding='utf-8') for p in notes)
        report['approvals']=approved
        report['passed']=all(r['passed'] for r in report['repositories']) and report['memory_outcome_notes']
    finally:
        actions.close();report['seconds']=round(time.monotonic()-started,3)
        target=BASE/('artifacts/reports/repository-skills-restart.json' if '--restart-check' in sys.argv else 'artifacts/reports/repository-skills-live.json');history=BASE/'artifacts/reports/repository-skills-live-history.json'
        if target.exists() and '--restart-check' not in sys.argv:
            previous=json.loads(history.read_text(encoding='utf-8')) if history.exists() else []
            previous.append(json.loads(target.read_text(encoding='utf-8')))
            history.write_text(json.dumps(previous,indent=2)+'\n',encoding='utf-8')
        target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
