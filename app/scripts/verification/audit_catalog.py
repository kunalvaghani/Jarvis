"""Catalog ingestion and exact result accounting. No test inference from names alone."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2]
OUT=BASE/'artifacts/jarvis-audit'

TESTS={
1:['project_structure','capabilities','runtime_health'],2:['cognition','cognition_and_routing','screen_awareness'],
3:['jarvis','intent_testbook','natural_names','windows_commands'],4:['whisper','command_cleanup','push_to_write'],
5:['f5_speech','speech','answer_stream','natural_voice'],6:['knowledge','quick_answers','context_selector','natural_conversation'],
7:['groq','inference_limits','model_selection','ollama_models'],8:['gpu_scheduler','model_recovery'],9:['deliberation'],
10:['hierarchical','task_graph','plan_execution','task_state'],11:['skill_memory','hermes_skills','capabilities'],
12:['tools','native_tools','toolkits','agent_runtime'],13:['execution','ui_controls','visual_fallback'],
14:['browser_automation'],15:['knowledge_acquisition','live_app_context'],16:['obsidian_memory','conversation_memory','cognition'],
17:['file_knowledge','file_knowledge_training','buddy'],18:['repo_learning','repository_skills'],19:['repo_abilities','repository_skill_isolation'],
20:['self_evolution','anticipation'],21:['native_coding','coding_backend'],22:['development','coding_preview'],
23:['gmail_api','gmail_writes','gmail_workflows'],24:['whatsapp'],25:['media_player','media_routes','spotify','media_process_ownership'],
26:['realtime','memory_weather'],27:['gods_eye','gods_eye_view','gods_eye_cameras'],28:['deerflow','deerflow_sandbox','repository_skill_isolation'],
29:['rea_tools'],30:['hermes','harness','model_selection'],31:['buddy','island','hud','independent_cursor'],
32:['recovery','task_recovery','launcher_readiness','task_state'],33:['toolkits','agent_runtime'],
34:['launcher_readiness','project_structure','ollama_models'],35:['groq','repository_skill_isolation','toolkits','agent_runtime'],
36:['agent_runtime','runtime_health','cognition_and_routing'],37:['hierarchical','knowledge_acquisition','task_routing']}

def ingest(pack):
    source=pack/'test_cases/jarvis_test_cases.jsonl'
    rows=[json.loads(line) for line in source.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert len(rows)==1184 and len({r['id'] for r in rows})==1184, 'Catalog count/duplicate failure'
    prompts=sorted(p for p in (pack/'prompts').glob('*.md') if p.name[:2].isdigit() and 1<=int(p.name[:2])<=37)
    assert len(prompts)==37
    modules=[]
    for p in prompts:
        text=p.read_text(encoding='utf-8')
        number=int(p.name[:2]);name=p.stem[3:]
        candidates=re.search(r'\*\*Candidate source locations.*?\*\*\s*`([^`]+)`',text)
        raw=[s.strip().rstrip('.') for s in candidates[1].split(';')] if candidates else []
        actual=[];unresolved=[]
        for value in raw:
            if '*' in value: paths=list(BASE.glob(value))
            else:
                item=BASE/value
                if not item.exists() and (BASE/'jarvis'/value).with_suffix('.py').exists():item=(BASE/'jarvis'/value).with_suffix('.py')
                paths=[item] if item.exists() else []
            if paths:actual.extend(str(path.relative_to(BASE)).replace('\\','/') for path in paths)
            else:unresolved.append(value)
        tests=[f'tests/test_{s}.py' for s in TESTS[number] if (BASE/f'tests/test_{s}.py').is_file()]
        modules.append({'number':number,'module':name,'title':text.splitlines()[0],
            'prompt_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sources':actual,'unresolved_candidates':unresolved,
            'test_candidates':tests,'status':'PARTIAL','reason':'Sources/tests inventoried; full catalog execution and per-module improvement not complete'})
    (OUT/'catalog-input.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n',encoding='utf-8')
    (OUT/'catalog-provenance.json').write_text(json.dumps({'pack':str(pack),'date':'2026-10-14 IST',
        'catalog_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'master_sha256':hashlib.sha256((pack/'prompts/00_MASTER.md').read_bytes()).hexdigest(),
        'map_matches_checkout':(pack/'system-map.md').read_bytes()==(BASE/'docs/system-map.md').read_bytes(),
        'cases':len(rows),'modules':len(modules)},indent=2)+'\n',encoding='utf-8')
    print('Validated',len(rows),'unique IDs across',len(modules),'modules')

def reconcile():
    modules=json.loads((OUT/'module-map.json').read_text())
    rows=[json.loads(s) for s in (OUT/'catalog-input.jsonl').read_text(encoding='utf-8').splitlines()]
    actual={};executed=[]
    paths=[OUT/name for name in ('catalog-tests.xml','full-tests.xml','neighbor-tests.xml',
                               'completion-targeted.xml','completion-full-regression.xml') if (OUT/name).exists()]
    paths += [p for p in OUT.glob('modules/*/*.xml') if p.name in {'cases-and-contracts.xml','full-regression.xml'}]
    for path in sorted(paths):
        for node in ET.parse(path).iter('testcase'):
            state='FAIL' if node.find('failure') is not None or node.find('error') is not None else ('SKIPPED' if node.find('skipped') is not None else 'PASS')
            if state=='SKIPPED' and node.get('classname','').endswith(('test_audit_completion_cases','test_voice_tts_audit','test_questions_context_audit','test_model_routing_audit','test_gpu_scheduler_audit','test_deliberation_audit', 'test_skill_selection_audit')):
                skipped=node.find('skipped')
                if 'BLOCKED:' in (skipped.get('message','')+(skipped.text or '')):state='BLOCKED'
            result={'node':node.get('classname','')+'::'+node.get('name',''),'status':state,'seconds':float(node.get('time','0')),'evidence':path.relative_to(OUT).as_posix()}
            executed.append(result)
            # Only dedicated catalog tests authorize case status; incidental test names are not proof.
            if path.name=='catalog-tests.xml' or path.name=='cases-and-contracts.xml' and node.get('classname','').endswith(('test_architecture_audit', 'test_perception_cognition_audit', 'test_intent_direct_audit', 'test_voice_stt_audit', 'test_voice_tts_audit', 'test_questions_context_audit', 'test_model_routing_audit', 'test_gpu_scheduler_audit', 'test_deliberation_audit', 'test_dag_planning_audit', 'test_skill_selection_audit', 'test_audit_completion_cases')):
                ids=re.findall(r'JRV[-_](\d{2})[-_](\d{3})',result['node'])
                for module,case in ids:actual.setdefault(f'JRV-{module}-{case}',[]).append(result)
    results=[]
    for row in rows:
        module=modules[int(row['id'].split('-')[1])-1]
        result={**row,'trace_id':'audit-20261014-'+row['id'],'source_paths':module['sources'],'test_candidates':module['test_candidates']}
        if row['id'] in actual:
            evidence=actual[row['id']]
            # Every parameter variant must pass; a later pass cannot hide a failure.
            priority={'FAIL':4,'BLOCKED':3,'SKIPPED':2,'NOT RUN':1,'PASS':0}
            result.update(max(evidence,key=lambda item:priority[item['status']]))
            result['executed_assertions']=evidence
            result['scope']='Dedicated offline fixture assertion; real external/human acceptance remains separate'
        else:
            result.update(status='NOT RUN',reason='Catalog-specific assertion not implemented/executed in this bounded pass; related regression is not equivalent proof')
        results.append(result)
    (OUT/'test-results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in results),encoding='utf-8')
    (OUT/'remaining-case-ids.txt').write_text('\n'.join(r['id'] for r in results if r['status'] not in {'PASS','SKIPPED'})+'\n',encoding='utf-8')
    (OUT/'executed-tests.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in executed),encoding='utf-8')
    counts=Counter(r['status'] for r in results)
    summary={'catalog_counts':{status:counts[status] for status in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN')},
        'by_tier':{tier:dict(Counter(r['status'] for r in results if r['tier']==tier)) for tier in ('P0','P1','P2')},
        'by_category':{kind:dict(Counter(r['status'] for r in results if r['case_type']==kind)) for kind in sorted({r['case_type'] for r in results})},
        'runs':{name:dict(Counter(r['status'] for r in executed if r['evidence']==name)) for name in sorted({r['evidence'] for r in executed})},
        'next_case':next((r['id'] for r in results if r['status']!='PASS'),None)}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pack',type=Path);parser.add_argument('--reconcile',action='store_true');args=parser.parse_args()
    if args.pack:ingest(args.pack)
    if args.reconcile:reconcile()
