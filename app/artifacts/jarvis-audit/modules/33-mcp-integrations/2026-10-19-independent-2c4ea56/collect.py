"""Collect immutable replay results and a fixed-fixture benchmark for the repair SHA."""
import csv
import hashlib
import json
import platform
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
import types
from unittest.mock import patch
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
sys.path.insert(0,str(APP))
from jarvis import mcp_bridge, mcp_synthesis

def write(name,text):
    (OUT/name).write_text(text.rstrip()+'\n',encoding='utf-8')

def dump(name,data):
    write(name,json.dumps(data,indent=2,ensure_ascii=False))

def git(*args):
    return subprocess.check_output(['git',*args],cwd=APP)

SHA = git('rev-parse','HEAD').decode().strip()
OLD = '0e3ad4706b5120e5d0479d34333e5faa7b0931b5'
assert SHA == '2c4ea56eb7967929e49dad07b0612cb99caaf56e'
PRIOR = OUT.parent/'2026-10-19-independent-0e3ad47'
results=[]
summary={}
for label in ['repair-replay','regression','cross-pillar','contract-edges','provider-context']:
    root=ET.parse(OUT/(label+'.xml')).getroot()
    subset=[]
    for test in root.iter('testcase'):
        status='FAIL' if test.find('failure') is not None or test.find('error') is not None else 'SKIPPED' if test.find('skipped') is not None else 'PASS'
        subset.append(dict(id=test.get('name'),classname=test.get('classname'),status=status,
            seconds=float(test.get('time',0)),run=label,sha=SHA,evidence=label+'.xml'))
    results+=subset
    summary[label]={s:sum(r['status']==s for r in subset) for s in ['PASS','FAIL','SKIPPED']}
    summary[label]['seconds']=sum(float(s.get('time',0)) for s in root.findall('testsuite'))
totals={s:sum(r['status']==s for r in results) for s in ['PASS','FAIL','SKIPPED']}
write('executed-results.jsonl','\n'.join(json.dumps(r) for r in results))
dump('baseline.json',dict(date='2026-10-19',claude_sha=SHA,prior_sha=OLD,branch=git('branch','--show-current').decode().strip(),
    platform=platform.platform(),python=sys.version,interpreter=sys.executable,runs=summary,totals=totals,
    memory='Test process peak memory NOT MEASURED; benchmark allocation peak is fixture-only',
    isolated_dependencies='Existing original .venv/.venv-skills interpreters, audited source/cwd remain isolated',
    author_report='Claude 3449 passed/147 skipped is upstream evidence only, not our fresh count'))

paths=['jarvis/mcp_bridge.py','jarvis/mcp_contract.py','jarvis/mcp_synthesis.py','jarvis/toolkits.py',
       'jarvis/tools.py','jarvis/agent_tools.py','jarvis/skill_evolution.py','jarvis/task_state.py',
       'jarvis/launcher.py','jarvis/recovery.py','jarvis_bootstrap.py','main.py','tests/test_prompt32_33_repairs.py']
dump('source-hashes.json',{p:hashlib.sha256((APP/p).read_bytes()).hexdigest() for p in paths})
dump('prior-evidence-hashes.json',{p.relative_to(APP).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
    for p in PRIOR.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
dump('replay-source-comparison.json',{
    'MCP_fixture_byte_identical':(OUT/'test_mcp_boundaries.py').read_bytes()==(PRIOR/'test_mcp_boundaries.py').read_bytes(),
    'recovery_fixture_byte_identical':(OUT/'test_recovery_boundaries.py').read_bytes()==(APP/'artifacts/jarvis-audit/modules/32-service-recovery/2026-10-19-independent-0e3ad47/test_recovery_boundaries.py').read_bytes(),
    'optional_provider_source_unchanged_by_repair':git('show',OLD+':app/jarvis/toolkits.py')==git('show',SHA+':app/jarvis/toolkits.py'),
    'source_changes':'None by Codex; replay fixture output paths relocate naturally via __file__ into this new packet'})
dump('protocol.json',{'stdio_protocol':mcp_bridge.VERSION,'runtime':mcp_synthesis.image_status(),
    'generated_identity':['code_sha256','spec_sha256','schema_sha256','image_id'],
    'transports':['stdio'],'setup_dependency_pin':'mcp==2.3.0','dependency_or_protocol_change':'NONE'})

# Use the exact same non-generated call and fake transport before/after; no network/process in benchmark.
prior=types.ModuleType('jarvis.audit_prior_bridge')
prior.__package__='jarvis'
exec(compile(git('show',OLD+':app/jarvis/mcp_bridge.py'),'<fixed-prior-bridge>','exec'),prior.__dict__)
class FixedClient:
    def __init__(self,*a): pass
    def initialize(self): pass
    def tools(self):
        return [{'name':'echo','inputSchema':{'type':'object','properties':{'count':{'type':'integer'}},'required':['count']}}]
    def request(self,*a): return {'content':[{'type':'text','text':'fixed synthetic result'}]}
    def close(self): pass
measure=[]
with tempfile.TemporaryDirectory() as directory:
    actions=types.SimpleNamespace(base=Path(directory),task_state=None,_approve=lambda *a:None)
    config={'fixture':{'command':sys.executable,'args':[],'allow_tools':['echo'],'enabled':True,'trusted':True}}
    step={'action':'mcp_call','value':'fixture','content':json.dumps({'name':'echo','arguments':{'count':1}})}
    for label,module,sha in [('before',prior,OLD),('after',mcp_bridge,SHA)]:
        with patch.object(module,'StdioClient',FixedClient),patch.object(module,'configurations',return_value=config):
            for _ in range(20): module.execute(actions,step,lambda:False)
            values=[]
            tracemalloc.start()
            for _ in range(300):
                start=time.perf_counter_ns();module.execute(actions,step,lambda:False)
                values.append((time.perf_counter_ns()-start)/1e6)
            _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        measure.append(dict(revision=label,sha=sha,samples=300,fixture='fixed non-generated bridge call; fake transport and approval',
                            p50_ms=statistics.median(values),p95_ms=sorted(values)[284],traced_peak_bytes=peak))
with (OUT/'benchmarks.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(measure[0]));w.writeheader();w.writerows(measure)
dump('benchmark-provenance.json',{'before':OLD,'after':SHA,'iterations':300,'warmup':20,
    'scope':'Warm sequential synthetic bridge overhead including tracemalloc. No subprocess, Docker, provider, model or approval UI latency; no improvement claim.'})

# Preserve the exact fixture schemas/server source needed to reproduce the new transport observations.
fixture=__import__('runpy').run_path(str(OUT/'test_mcp_boundaries.py'))
write('stdio-fixture-server.py',fixture['SERVER'])
write('generated-server.py',mcp_synthesis.generate(fixture['SPEC']))
dump('generated-spec.json',fixture['SPEC'])
dump('captured-schema.json',{'origin':'literal advertised schema from executed contract-edge fixture',
    'tools':[{'name':'echo','inputSchema':{'type':'object','required':['count'],
              'properties':{'count':{'type':'array','items':{'type':'integer'}}},'additionalProperties':False}}]})
dump('schema-version-hashes.json',{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest()
    for name in ['captured-schema.json','generated-spec.json','generated-server.py']})
dump('permission-manifest.json',{'stdio':'Trusted local fixture interpreter only; explicit allow_tools echo',
    'generated':'Existing Docker image, no network, read-only root/server mount, non-root, cap-drop ALL, bounded pids/memory/CPU; private verified execution copy',
    'approval':'Fixed synthetic callbacks; no live/native approval UI proof',
    'provider':'jarvis.toolkits.api replaced by in-memory ledger; synthetic A/B credentials only',
    'real_account_writes':0,'installations':0,'production_process_targets':0})

priorcases={r['id']:r for r in [json.loads(s) for s in (PRIOR/'tests.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]}
cases=[]
changes={
 1:('PASS','Mock-only calendar GET uses account A credential and synthetic A event. Server-side scope enforcement/live account BLOCKED.'),
 2:('PASS','Mock-only calendar_create approval denial prevents intercepted API invocation. Live provider final readback BLOCKED.'),
 3:('PASS','Absent Jira with cleared environment is excluded from the goal catalog.'),
 5:('FAIL','Original integer-string assertion PASS, but 1001st array item and boolean enum/const checks FAIL. P33-002 PARTIAL.'),
 6:('FAIL','Original malformed envelope assertion PASS; output array tail and empty resource checks FAIL. P33-003 PARTIAL.'),
 13:('PASS','Original real Docker source-drift rejection PASS; normal generated compute lifecycle PASS. Fixed author/approval; no live model.'),
 22:('FAIL','P33-004 P1: synthetic account switches A→B during pending approval and intercepted calendar POST targets B. No real event.')}
for i in range(1,23):
    ident=f'JRV-33-{i:03}';old=priorcases[ident]
    status,reason=changes.get(i,(old['status'],old['reason']))
    # Retain only tests actually rerun for passing legacy case mappings.
    if i in {11,12,14,16,17,18}:
        reason='Fresh replay/related regressions PASS at '+SHA[:7]+'. '+reason
    cases.append(dict(id=ident,status=status,reason=reason,sha=SHA,prior_status=old['status'],
                      evidence='executed-results.jsonl; repair-replay.xml; regression.xml; contract-edges.xml; provider-context.xml'))
write('tests.jsonl','\n'.join(json.dumps(r) for r in cases))

write('inventory.md',f'''# Prompt 33 continuation — 2026-10-19

Pinned claude and audit HEAD `{SHA}` (previous `{OLD}`), isolated `codex-review`. All pending audit docs were saved in pre-update before fast-forwarding; original checkout still has its user config modification, untouched. Application instructions read. Master contract remains unavailable; supplied Downloads reconciliation contract requires Codex read-only independent confirmation and source repairs on Claude. No application source edited by Codex.

Source/call chain unchanged: ToolRegistry → toolkits → agent_tools → mcp_bridge. Generated configurations now retain code/spec/schema/image pins, verify before approval, mount a private verified source copy, and compare the advertised schema. Drift removes generated entries from callable configurations. New mcp_contract validates input/output at the call boundary. Explicit health may repin stored spec/schema after tests; dependent skill lineage/version revalidation is still open. Non-generated servers use current advertised schema without a pin.

Reviewed actual diff, upstream repair record/XML/logs, current bridge/synthesis/validator/launcher/recovery/provider source, original independent packet and stable cases. Upstream 3,449 PASS/147 skips is historical author evidence, not our count. Fresh XML is the authority for this run. SDK/image/protocol unchanged; see protocol.json and source hashes. Generated flags, stdio bounds, per-call approval, no-retry policy and direct optional provider architecture remain as in the previous inventory.

No source/model/dependency/protocol change by Codex, no account sends, actual events, installs, desktop captures or shared-process kills. Test process peak memory not measured; paired allocation benchmark is explicitly synthetic.
''')
write('failures.md', '''# Current findings

## P33-004 — P1 / NEWLY REPRODUCED: credential context can change after approval

JRV-33-022 executes the real ToolRegistry → toolkits.execute → remote_tool path with the API transport replaced by an in-memory ledger. Start with synthetic account A credential and event request. The approval callback simulates switching current credentials to account B while approval was pending. The returned approval detail contains action/calendar ID/event content but no account identity. remote_tool then rereads os.environ and dispatches POST with account B credential. The ledger records the account-A event body targeting B. No network call/event occurred.

Source: jarvis/toolkits.py execute approval and remote_tool environment lookup/calendar headers. Source is unchanged by 2c4ea56, so this is a preexisting uncovered boundary, not a new repair regression. Scope: a credential switch inside the running process; no claim that Windows externally changes an existing process environment or that current UI supplies an account-switch action. Stable-token mock read and denied-write controls pass. Actual account scopes/consent remain unverified.

Reproduce: test_provider_context.py::test_JRV_33_022_account_switch_during_approval_must_not_write_other_workspace. Evidence: provider-context.xml and account-switch-observation.json. Fix SHA NONE. Status APPLIES/OPEN.

## P33-002 — P2 / PARTIAL repair: input/output schema checks have gaps

The original string-for-integer transport assertion now passes. However validate_schema_value walks only value[:1000] without rejecting longer arrays; invalid element 1001 reaches real local tools/call. The same function accepts an invalid tail in outputSchema structured content. Native Python equality makes false satisfy enum [0], and true satisfy const 1. Three input edge assertions and one output assertion fail. Bounds must fail closed rather than silently accepting unchecked tails; JSON equality must distinguish booleans and numbers.

Tests: test_JRV_33_005_array_tail_is_validated_before_real_stdio_call; test_JRV_33_006_output_array_tail_is_validated; test_JRV_33_005_json_boolean_is_not_numeric_enum_or_const (2 parameterizations). Evidence contract-edges.xml and array-tail-observation.json. No provider effects in these tests.

## P33-003 — P2 / PARTIAL repair: nested resource contents remain unchecked

The original malformed content/isError assertion now passes. A real local server returning content=[{type:resource,resource:{}}] is still accepted as ToolResult evidence. validate_result verifies only resource is a dict; required URI and valid text/blob resource shape are not checked. test_JRV_33_006_empty_embedded_resource_is_not_valid_evidence fails; resource-observation.json preserves exact output. This proves evidence acceptance, not final goal verification.

## Verified original fixes

P33-001 FIXED for original source-drift reproduction and new identity/private-copy checks. P32-001 and P32-002 FIXED for original native sibling-process and synthetic repair-log failures. All original assertions unchanged (byte-identical copied fixture files); repair-replay.xml has 28 PASS. Full Prompt 32/33 acceptance remains BLOCKED by further requirements. No blanket privacy guarantee from pattern-based redaction, no account/live/concurrency certification.
''')
write('repair-handoff.md',f'''# Next Claude repair handoff

Review `{SHA}`. No source changes by Codex. Supplied independent-confirmation contract reserves repair to Claude.

1. P33-004: represent the selected provider account/workspace as a stable identity separate from credential text; include identity, scope and target in approval, bind it to the task/call, and recheck immediately before dispatch. Use the approved identity's credential or reject drift. Do not put tokens in approval/logs. Add two mock accounts with a pending approval and prove zero writes to B after authorizing A. Handle token rotation for the same verified identity distinctly from account switching.
2. P33-002: validate every array item or reject the entire over-budget value; never slice validation input silently. Implement JSON type-aware equality for enum/const. Preserve bounded recursion/size, strict supported-schema behavior and no retry. Test both input and output tail limits.
3. P33-003: validate nested embedded-resource URI/text/blob shape and the supported content contract, rather than accepting arbitrary dictionaries. Preserve uncertain-write checkpoints on malformed results.
4. Rerun these new tests unchanged, the original repair replay, complete affected suites, and focused cross-pillar regressions. Add missing MCP schema dependent-skill invalidation, concurrency, memory retrieval and identity tests. Produce a new exact SHA for independent review.

From app: existing interpreter `python -m pytest artifacts/jarvis-audit/modules/33-mcp-integrations/{OUT.name}/test_contract_edges.py artifacts/jarvis-audit/modules/33-mcp-integrations/{OUT.name}/test_provider_context.py -q`. These cases use synthetic stdio/memory transports, no account writes or installs. See baseline.json for complete prior runs. STOP at current P1; no module 34 or deployment.
''')
write('codex-findings-reconciliation.md',f'''# Exact finding reconciliation

Base `{OLD}` → repair `{SHA}`. Original fixture files copied byte-for-byte into this directory so evidence never overwrites prior originals.

| Finding | Independent result | Remaining work |
|---|---|---|
| P33-001 P1 | FIXED: original drift repro PASS, code/spec/image/missing-pin rejection and private-copy controls PASS | Full schema-dependent skill lineage and concurrency not certified |
| P33-002 P2 | PARTIAL: original integer-string repro PASS | Array tails and JSON boolean/numeric enum/const FAIL |
| P33-003 P2 | PARTIAL: original malformed envelope repro PASS | Embedded resource contents and output array tail FAIL |
| P33-004 P1 | APPLIES/OPEN: new two-account switching fixture FAIL | No fix SHA |
| P32-001 P1 | FIXED for native sibling repro, normal stop and real-descendant controls PASS | Full live service acceptance remains open |
| P32-002 P1 | FIXED for original canaries/startup branch plus late/multiline/bootstrap controls PASS | Pattern redaction is not universal privacy proof |

Exact tests: executed-results.jsonl, repair-replay.xml, contract-edges.xml, provider-context.xml. Related retention: regression.xml and cross-pillar.xml. No author result copied into independent totals. Prior packet remains historical; no blanket full reconciliation completion.
''')
write('registration-transcript.md', '''# Lifecycle evidence

Fresh regression includes test_P03_mcp_workflows_register_call_and_unregister: real offline Docker/SDK registers SHA256 and Celsius tools, calls Celsius through ToolRegistry and independently checks returned 98.6 for 37, detects source drift via explicit health, unregisters, and checks no labelled leftovers. Original independent generated-source mutation before invocation is now rejected by the repaired call boundary. Repair identity/private-copy controls also pass; some image checks in those extra tests are explicitly mocked (see source).

Fixed synthetic author and approval callbacks; no live model/Alita author or native approval UI. XML records executed assertions rather than a full JSON-RPC wire transcript. stdio-fixture-server.py, captured-schema.json, generated-server.py and generated-spec.json preserve reproducible source/schema; hashes are in schema-version-hashes.json. New provider trace is an intercepted memory ledger, not a live provider response.
''')
write('adapter-matrix.md', '''# Real versus mock

| Route | Actual execution | Limit |
|---|---|---|
| Generated compute MCP | Existing offline Docker image + official SDK + ToolRegistry | Fixed author and approval; no model or account |
| stdio schema/results/death | Real local children and marker readback | Synthetic servers only |
| Native process ownership | Real hidden test-owned Windows Job trees | No actual Jarvis or user process targeted |
| Repair log privacy | Actual disk writes in temporary roots; exported synthetic readback | Canaries only, not universal redaction proof |
| Calendar/Jira account cases | Actual registry/provider adapter, intercepted API and synthetic env | No server-side scope/consent or real events |
| Cross pillars | Fixed local memory, evaluator, routing and recovery fixtures | Not complete live Phase 1–8 acceptance |
''')
write('cross-pillar-matrix.md','''# Fresh cross-pillar retention

| Seam | Evidence | Result |
|---|---|---|
| Registry/generated server/skill FIX-DERIVED | Complete Phase 3 in regression.xml | Existing lifecycle PASS; dependent schema-lineage still BLOCKED |
| API-first/desktop/browser fallback | Router suite + selected Phase 2 outage/no-replay | PASS local fixtures; native Blender/Unreal fallback not fully tested |
| Permission/provider schema | Original repair replay plus new edge tests | Original repro PASS, contract/account edges FAIL |
| Task recovery/uncertain writes | Complete affected recovery suites + Phase 8 Flow E | PASS fixtures; full live worker restart not certified |
| Cloud advice/untrusted code | Phase 5 malicious-output and disabled-default controls | PASS mocked cloud; no cloud call |
| DGM/immutable evaluator | Phase 6 production surfaces/protected sources + Phase 7 unsealed evaluator | PASS selected invariants, not full candidate optimization/training |
| Memory/tool identity | Phase 4 contradiction/planner integration | PASS generic memory; MCP version/account retrieval BLOCKED |

Complete direct regression 223 PASS; focused cross-pillar 19 PASS. Final global regression stopped at P1. Earlier 642/13 and author 3449/147 are historical, not freshly executed here.
''')
write('compatibility.md','''# Compatibility

Host Python 3.10.6 and existing installed utility interpreter; isolated audited source and disposable data. Protocol remains 2025-11-25, stdio only. Existing Docker image/SDK identity captured in protocol.json. No package, transport, model or launcher configuration change by Codex. New schema subset may reject unsupported advertised schemas intentionally; this is not full JSON Schema support. Legacy missing generated identity pins require explicit revalidation; no silent migration claim.

launcher-check.json remains repair_required for isolated missing environments/checkpoints, while Docker and configured local Ollama models are available. Claude's ready result was from the original environment and does not supersede this worktree result. Enabled/disabled direct server, namespace and no-retry fixture controls reran; full provider scopes/refresh/tenant and concurrent registration remain BLOCKED.
''')
write('security.md','''# Security

P33-004 is a P1 account-context binding failure conditional on a credential switch within the running process. The test replaces the API with an in-memory ledger and exports only synthetic identities/body, never credentials. It does not claim the user can change an existing process's environment externally. Source was unchanged by the repair. Stable context and denied writes have passing controls.

P33-002/003 remain PARTIAL after passing their exact original reproductions: unchecked input/output tails, boolean numeric equality and unvalidated embedded resource. No final task-verification bypass or container escape demonstrated. Generated source integrity failure P33-001 is repaired within tested scope; Docker restrictions remain effective. Original recovery ownership/privacy P1s pass independent native/canary tests. Redaction is pattern-based, not a universal privacy certificate.

No live sends/events, provider reads, paid APIs, training, installations, private desktop recording or shared-service starts/stops. Source changes reserved to Claude by the supplied read-only confirmation contract. Full release NOT READY.
''')
write('changes.md','''# Changes by Codex

Fast-forwarded only the isolated codex-review checkout to the actual Claude repair commit after preserving pending audit docs under pre-update. Added byte-identical copies of independent repro tests with outputs naturally scoped to this packet, new edge/account tests, XML/text observations, hashes, benchmark and reports. Updated root/app README and recovery guide with current independent status. No application source, dependency, config, visible UI/artwork, service policy, commit, merge into main or deployment changed. Original checkout user config and prior evidence preserved.
''')
write('rollback.md','''# Rollback

No Codex application source or dependency change to roll back. Prior audit documentation is preserved byte-for-byte in pre-update; prior packets are hashed. Do not reset the original checkout or overwrite newer Claude work. The audit fast-forward points at the repair commit; preserve its evidence if reviewing another SHA. Tests clean only their owned temporary processes/Job trees and labelled generated servers. Source/protocol rollback for a future repair must preserve generated identity compatibility, stale-skill refusal and uncertain-write checkpoints. Do not rebuild images/install packages as a rollback shortcut.
''')
write('verdict.md',f'''# Prompt 33 continuation — NOT READY / BLOCKED

2026-10-19 independent confirmation at `{SHA}`. Fresh checks: **{totals['PASS']} PASS / {totals['FAIL']} FAIL / {totals['SKIPPED']} SKIPPED**. Original repair replay 28 PASS; complete direct regression 223 PASS; focused cross-pillar retention 19 PASS. New edge/account fixtures have 3 PASS and 6 FAIL.

P33-001 source integrity fix verified, and original P32 ownership/privacy failures independently pass. P33-002 and P33-003 pass their original reproductions but remain PARTIAL under broader validation. New **P33-004 P1**: account-A calendar request can dispatch under account B after a credential-context change during approval (intercepted fake API, zero real events). STOP at P1.

[Findings](failures.md) · [Next repair handoff](repair-handoff.md) · [Finding reconciliation](codex-findings-reconciliation.md) · [Stable cases](tests.jsonl) · [Fresh run provenance](baseline.json).

No source repairs by Codex under the supplied independent read-only contract. No deployment, installs or module 34. Schema-dependent skill revalidation, concurrency/memory integration and live account acceptance remain BLOCKED. Worktree launcher repair_required. Real offline compute-tool lifecycle passes with fixed author/approval; no live-model/account certificate. Benchmark is synthetic dispatch overhead only.
''')

recon=APP/'artifacts/jarvis-audit/reconciliation/33-2026-10-19-independent-2c4ea56'
recon.mkdir(exist_ok=True)
for name,origin in [('artifact-inventory.md','inventory.md'),('patch-assessment.md','changes.md'),('unresolved.md','failures.md'),('handoff.md','repair-handoff.md')]:
    content=(OUT/origin).read_text(encoding='utf-8')
    content=re.sub(r'\]\(([^)]+)\)',lambda m:'](../../modules/33-mcp-integrations/'+OUT.name+'/'+m[1]+')',content)
    (recon/name).write_text(content,encoding='utf-8')
(recon/'review-revisions.json').write_text(json.dumps({'before':OLD,'repair':SHA,'audit':SHA,'new_fix_sha':None},indent=2))
with (recon/'findings-ledger.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['finding','priority','status','repair_sha','test_case'])
    for ident,priority,status,case in [('P33-001','P1','FIXED','JRV-33-013'),('P33-002','P2','PARTIAL','JRV-33-005'),('P33-003','P2','PARTIAL','JRV-33-006'),('P33-004','P1','OPEN','JRV-33-022'),('P32-001','P1','FIXED','JRV-32-005'),('P32-002','P1','FIXED','JRV-32-011')]:
        w.writerow([ident,priority,status,SHA if status!='OPEN' else 'NONE',case])
for name,labels in [('repro-results.jsonl',{'repair-replay','contract-edges','provider-context'}),('legacy-regressions.jsonl',{'regression'}),('cross-pillar-regressions.jsonl',{'cross-pillar'})]:
    (recon/name).write_text('\n'.join(json.dumps(r) for r in results if r['run'] in labels)+'\n',encoding='utf-8')
print(json.dumps({'sha':SHA,'totals':totals,'runs':summary},indent=2))
