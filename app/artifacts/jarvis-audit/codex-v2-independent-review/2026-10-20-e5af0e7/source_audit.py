"""Reproducible source reachability and corpus mapping, separate from runtime proof."""
import ast
import hashlib
import json
from pathlib import Path
import sys

out=Path(__file__).resolve().parent
app=Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-v2-mutants-e5af0e7/app')
sys.path.insert(0,str(app))
from scripts.verification.audit_catalog import TESTS
def dump(name,value):
    (out/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
def records(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
config=json.loads((app/'config/config.json').read_text(encoding='utf-8'))
sections=['brain','knowledge','speech','reasoning_bank','viking_memory','exploration','cloud_architect',
          'self_evolution','evolution_lab','groq','demonstration','execution_strategy']
flags={section:{key:row[key] for key in ('enabled','planner','planning_backend','model','screen_model') if key in row}
       for section in sections if isinstance(row:=config.get(section),dict)}
dump('tracked-config-flags.json',{'scope':'tracked pinned configuration only; live dirty config excluded; credentials/paths omitted',
    'flags':flags,'absent_sections':[section for section in sections if section not in config]})
definitions={
 'core':('Commands/Engine -> Actions queue -> Brain -> ToolRegistry -> TaskState -> App event consumers',
         ['commands','engine','actions','brain','tools','task_state']),
 'A':('ToolRegistry outcome -> SkillStore -> SkillEvolution CAPTURED/FIX/DERIVED; generated tools -> MCP bridge',
      ['tools','skill_store','skill_evolution','mcp_synthesis','mcp_bridge']),
 'B':('Actions task on_finish -> LearningMemory -> ReasoningBank -> BrainClient lessons; idle -> exploration/viking',
      ['actions','learning_memory','reasoning_bank','exploration','viking_memory','self_evolution']),
 'C':('SelfEvolution.research_maintenance -> AutoResearch -> ExperimentLab -> sealed gate -> approved promotion/rollback',
      ['self_evolution','autoresearch','evolution_lab','evolution_surfaces','evolution_promotion']),
 'D':('Offline AZR generators/oracle -> split data -> training admission -> experimental registry; no runtime replacement',
      ['azr_tasks','azr_reward','azr_dataset','azr_proposer','model_registry']),
 'API-first':('Brain.validate_remaining -> execution_strategy -> app_adapters -> worker -> verified readback',
      ['brain','execution_strategy','app_adapters']),
 'Cloud':('Brain.recover_task -> FailureRouter -> registered consult tool -> consent/privacy/quota -> provider',
      ['brain','deliberation','cloud_architect','cloud_policy']),
 'ShowMe':('Actions request/consent -> DemonstrationSession -> native hook worker -> structured replay -> provisional promote',
      ['actions','demonstration','skill_evolution']),
 '31':('main App approval/event drain -> interface -> Island/Desk/Pip -> receipt boundaries',
      ['interface','island','island_desk','approval_scope']),
 '32':('RuntimeHealth -> supervised owned services -> recovery/backoff -> TaskState paused outcome',
      ['runtime_health','recovery','supervision','task_state']),
 '33':('ToolRegistry -> MCP profile/identity/schema validation -> bridge transport',
      ['tools','mcp_bridge','mcp_synthesis','toolkits']),
 '34':('launcher readonly readiness -> explicit Repair authorization -> stage_environment / ModelRecovery -> approved_pull',
      ['launcher','repair_authorization','model_recovery']),
 '35':('ToolRegistry final policy -> approval/identity -> API/tool execution/readback',
      ['tools','approval_scope','cloud_architect','ability_runner']),
 '36':('ToolRegistry lifecycle -> AgentEvents -> bounded redaction/clock/traces',
      ['tools','agent_events']),
 '37':('Queued commands -> real worker state/readback -> task/memory/UI with explicitly simulated planner/account',
      ['actions','brain','tools','learning_memory','task_state'])}
claims=[]
for domain,(route,names) in definitions.items():
    paths=[f'jarvis/{name}.py' for name in names if (app/f'jarvis/{name}.py').is_file()]
    claims.append({'domain':domain,'call_path':route,'source_paths':paths,
        'source_review':'actual definitions/call sites plus graph; not whole-code semantic proof',
        'live_functionality':'BLOCKED / not independently certified','fixture_tests':'linked in final XML after execution'})
dump('claim-evidence-map.json',claims)
imports={}
for test in (app/'tests').glob('test_*.py'):
    found=set()
    tree=ast.parse(test.read_text(encoding='utf-8-sig'))
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom) and node.module:
            if node.module=='jarvis':
                found.update('jarvis/'+alias.name+'.py' for alias in node.names if (app/'jarvis'/(alias.name+'.py')).is_file())
            elif node.module.startswith('jarvis.'):
                path=node.module.replace('.','/')+'.py'
                if (app/path).is_file(): found.add(path)
    imports[test.name]=sorted(found)
specs=records(out/'corpus-specifications.jsonl')
original={row['id']:row for row in specs if row['variant']=='original'}
rows=[]
for row in specs:
    module=int(row['id'].split('-')[1])
    candidates=[f'test_{name}.py' for name in TESTS[module] if (app/'tests'/f'test_{name}.py').is_file()]
    base=original.get(row['id'],{})
    rows.append({**row,'severity':row.get('tier',base.get('tier','unspecified')),
       'module':row.get('module',base.get('module',f'module-{module}')),
       'candidate_source_modules':sorted({path for name in candidates for path in imports.get(name,[])}),
       'legacy_call_path':definitions.get(str(module),definitions['core'])[0],
       'new_pillars':'potential shared tool/memory/approval/evolution interfaces; case-specific proof not inferred',
       'supported_environment':row.get('execution',base.get('execution','owned fixtures first; live requires configured runtime and approval')),
       'mapping_limit':'static test imports and catalog grouping, not semantic equivalence or case execution'})
(out/'mapped-corpus.jsonl').write_text('\n'.join(json.dumps(row) for row in rows)+'\n',encoding='utf-8')
parsed={}
for folder in ('jarvis','scripts','evolution_eval'):
    for path in (app/folder).rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
        parsed[path.relative_to(app).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
dump('candidate-static-checks.json',{'parsed':len(parsed),'syntax_errors':0,'type_checker':'NOT RUN; no new tool installation',
    'source_hashes_match':parsed==json.loads((out/'candidate-source-hashes.json').read_text(encoding='utf-8'))})
print(json.dumps({'claims':len(claims),'mapped_id_behavior_rows':len(rows),'ast_parsed':len(parsed)}))
