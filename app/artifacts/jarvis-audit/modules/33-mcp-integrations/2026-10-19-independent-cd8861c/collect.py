"""Collect the cd8861c independent continuation from saved XML and pinned source."""
import csv
import hashlib
import json
import platform
from pathlib import Path
import re
import runpy
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
import types
from unittest.mock import patch
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
APP=next(p for p in OUT.parents if (p/'main.py').is_file())
sys.path.insert(0,str(APP))
from jarvis import mcp_bridge,mcp_synthesis,mcp_contract
DATE='2026-10-20'
OLD='2c4ea56eb7967929e49dad07b0612cb99caaf56e'
SHA='cd8861ce720ade303485ee2023430dd8c6b4f0ba'
PRIOR=OUT.parent/'2026-10-19-independent-2c4ea56'

def write(name,text): (OUT/name).write_text(text.rstrip()+'\n',encoding='utf-8')
def dump(name,data): write(name,json.dumps(data,indent=2,ensure_ascii=False))
def git(*args): return subprocess.check_output(['git',*args],cwd=APP)
assert git('rev-parse','HEAD').decode().strip()==SHA
results=[];summary={}
for label in ['repair-replay','regression','cross-pillar','configured-identity']:
    root=ET.parse(OUT/(label+'.xml')).getroot();subset=[]
    for test in root.iter('testcase'):
        status='FAIL' if test.find('failure') is not None or test.find('error') is not None else 'SKIPPED' if test.find('skipped') is not None else 'PASS'
        subset.append(dict(id=test.get('name'),classname=test.get('classname'),status=status,
                           seconds=float(test.get('time',0)),run=label,sha=SHA,evidence=label+'.xml'))
    results+=subset
    summary[label]={s:sum(r['status']==s for r in subset) for s in ['PASS','FAIL','SKIPPED']}
    summary[label]['seconds']=sum(float(s.get('time',0)) for s in root.findall('testsuite'))
totals={s:sum(r['status']==s for r in results) for s in ['PASS','FAIL','SKIPPED']}
write('executed-results.jsonl','\n'.join(json.dumps(r) for r in results))
dump('baseline.json',dict(completed_date=DATE,packet_started_date='2026-10-19',date_note='Run crossed midnight IST; directory retains start date.',
    source_sha=SHA,prior_sha=OLD,branch='codex-review',platform=platform.platform(),python=sys.version,executable=sys.executable,
    runs=summary,totals=totals,test_process_peak_memory='NOT MEASURED; synthetic benchmark allocation peak only',
    dependencies='Existing original .venv and .venv-skills interpreters; audited source/cwd remain isolated',
    upstream_claim='3469 passed/147 skips is author evidence, not independently added to totals'))
paths=['jarvis/mcp_bridge.py','jarvis/mcp_contract.py','jarvis/mcp_synthesis.py','jarvis/provider_identity.py',
       'jarvis/toolkits.py','jarvis/tools.py','jarvis/skill_evolution.py','jarvis/skill_memory.py','jarvis/skill_store.py',
       'jarvis/launcher.py','jarvis/recovery.py','tests/test_prompt33_followup.py']
dump('source-hashes.json',{p:hashlib.sha256((APP/p).read_bytes()).hexdigest() for p in paths})
dump('prior-evidence-hashes.json',{p.relative_to(APP).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
    for p in PRIOR.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
names=['test_mcp_boundaries.py','test_recovery_boundaries.py','test_contract_edges.py','test_provider_context.py']
dump('replay-source-comparison.json',{name:(OUT/name).read_bytes()==(PRIOR/name).read_bytes() for name in names})
dump('protocol.json',{'stdio_protocol':mcp_bridge.VERSION,'runtime':mcp_synthesis.image_status(),
    'dependency_change':'NONE','transport_change':'NONE','direct_sdk_build_pin':'mcp==2.3.0',
    'identity_policy':'configured labels marked verified; changed credentials with same label accepted as rotation'})

# Fixed fake-transport fixture at the two real revisions, not a model/provider latency benchmark.
prior=types.ModuleType('jarvis.audit_prior_bridge');prior.__package__='jarvis'
exec(compile(git('show',OLD+':app/jarvis/mcp_bridge.py'),'<fixed-prior-bridge>','exec'),prior.__dict__)
prior_contract=types.ModuleType('jarvis.mcp_contract')
exec(compile(git('show',OLD+':app/jarvis/mcp_contract.py'),'<fixed-prior-contract>','exec'),prior_contract.__dict__)
class FixedClient:
    def __init__(self,*a): pass
    def initialize(self): pass
    def tools(self): return [{'name':'echo','inputSchema':{'type':'object','properties':{'count':{'type':'integer'}},'required':['count']}}]
    def request(self,*a): return {'content':[{'type':'text','text':'fixed synthetic result'}]}
    def close(self): pass
measure=[]
with tempfile.TemporaryDirectory() as folder:
    actions=types.SimpleNamespace(base=Path(folder),task_state=None,_approve=lambda *a:None)
    configs={'fixture':{'command':sys.executable,'args':[],'allow_tools':['echo'],'enabled':True,'trusted':True}}
    step={'action':'mcp_call','value':'fixture','content':json.dumps({'name':'echo','arguments':{'count':1}})}
    for label,module,sha in [('before',prior,OLD),('after',mcp_bridge,SHA)]:
        helper=prior_contract if label=='before' else mcp_contract
        with patch.object(module,'StdioClient',FixedClient),patch.object(module,'configurations',return_value=configs),patch.dict(sys.modules,{'jarvis.mcp_contract':helper}):
            for _ in range(20): module.execute(actions,step,lambda:False)
            samples=[];tracemalloc.start()
            for _ in range(300):
                start=time.perf_counter_ns();module.execute(actions,step,lambda:False)
                samples.append((time.perf_counter_ns()-start)/1e6)
            _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        measure.append(dict(revision=label,sha=sha,samples=300,fixture='fixed bridge call; fake transport/approval',
            p50_ms=statistics.median(samples),p95_ms=sorted(samples)[284],traced_peak_bytes=peak))
with (OUT/'benchmarks.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(measure[0]));w.writeheader();w.writerows(measure)
dump('benchmark-provenance.json',{'before':OLD,'after':SHA,'warmup':20,'samples':300,
    'limitation':'Bridge and mcp_contract source both loaded from the named revisions. Fake transport/approval and fixed valid scalar fixture; warm sequential tracemalloc run. Not subprocess/provider/model latency, no performance improvement claim.'})
fixture=runpy.run_path(str(OUT/'test_mcp_boundaries.py'))
write('stdio-fixture-server.py',fixture['SERVER'])
write('generated-server.py',mcp_synthesis.generate(fixture['SPEC']))
dump('generated-spec.json',fixture['SPEC'])
dump('captured-schema.json',{'origin':'literal schema in executed stdio fixture',
    'tools':[{'name':'echo','inputSchema':{'type':'object','required':['count'],'properties':{'count':{'type':'integer'}},'additionalProperties':False}}]})
dump('schema-version-hashes.json',{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest()
    for name in ['captured-schema.json','generated-spec.json','generated-server.py']})
dump('permission-manifest.json',{'local_stdio':'explicit echo allowlist, trusted disposable interpreter',
    'generated':'existing offline labelled image, network none, read-only root/mount, UID 65534, dropped caps, bounded resources, verified private source',
    'approval_and_author':'synthetic callbacks','provider_transport':'intercepted in-memory API; synthetic A/B credentials only',
    'real_provider_writes':0,'installations':0,'unowned_process_targets':0})

oldcases={r['id']:r for r in [json.loads(s) for s in (PRIOR/'tests.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]}
updates={5:('PASS','Original scalar, array-tail, boolean enum/const failures all independently replay PASS; bounded supported schema subset only.'),
         6:('PASS','Original malformed envelopes, output array tail and embedded-resource failures all replay PASS; supported content block controls pass.'),
         15:('BLOCKED','New literal-reference dependent-skill invalidation/retrieval/restore tests PASS; actual schema migration and skill-version compatibility postconditions not independently established.'),
         20:('BLOCKED','16-thread mark_drifted consistency test PASS; concurrent registration during task execution and multi-process routing not established.'),
         21:('BLOCKED','Disabled direct calls and literal-reference dependent skill retrieval controls PASS; full ReasoningBank retrieval-to-call/provisional-reference gate not established.'),
         22:('FAIL','P33-004 PARTIAL/P1: unconfigured credential and changed-label cases now refuse, but unchanged label incorrectly verifies another account token as rotation.')}
cases=[]
for i in range(1,23):
    ident=f'JRV-33-{i:03}';old=oldcases[ident]
    status,reason=updates.get(i,(old['status'],old['reason']))
    if status=='PASS': reason='Fresh replay at '+SHA[:7]+'. '+reason
    cases.append(dict(id=ident,status=status,reason=reason,source_sha=SHA,previous_status=old['status'],date=DATE,
        evidence='executed-results.jsonl; repair-replay.xml; regression.xml; configured-identity.xml'))
write('tests.jsonl','\n'.join(json.dumps(r) for r in cases))

write('inventory.md',f'''# Prompt 33 continuation — {DATE}

Pinned claude/audit `{SHA}` after `{OLD}`, isolated codex-review. The directory retains its 2026-10-19 start date; fresh completion results are 2026-10-20 IST. Pending audit docs saved under pre-update before fast-forward; original user config untouched. Application AGENTS and supplied Prompt 33/reconciliation contract read. Master contract still unavailable. Codex confirmation is read-only for application source; repairs reserved to Claude.

Reviewed actual source diff, provider_identity, toolkit dispatcher, MCP contract/bridge/synthesis, follow-up tests and author repair report. Four independent repro files copied byte-for-byte; their outputs relocate by __file__ into this packet. No source edit/test assertion weakening. New configured-identity fixture checks the acknowledged label-only limitation independently.

ProviderContext now captures configured labels, HMAC credential fingerprints and a process-local settings snapshot before approval. Changed labels and unlabelled credential changes reject; identical labels authorize credential replacement as rotation. A nonempty label is marked verified without asking the provider (remaining P33-004). MCP validator now visits whole arrays/objects, rejects over-budget values, uses JSON-aware equality and checks nested resource shape. Generated identity/sandbox/stdio protocol preserved. Drift disables literal-reference dependent skills; health restores matching markers. No full schema/version lineage or multi-process registration claim.

Source/image/schema hashes, raw XML, snapshots and benchmark provenance are adjacent. Earlier independent/author reports remain historical. Author 3469/147 is not our count. No app source/dependency/config/model/UI changes, installs, real account calls, private capture or production process target by Codex.
''')
write('failures.md','''# Remaining failure: P33-004 — P1 / PARTIAL

The old unlabelled credential-switch repro now passes, as do changed-label, stable-context and token-on-card controls. However ProviderContext.verified means only that non-secret identity keys are nonempty. recheck treats any replacement credential with unchanged identity text as verified same-account rotation. It does not establish which principal owns that credential.

Independent JRV-33-022 fixture starts label account-a@example.test and token A. While approval is pending it replaces only the token with one assigned to mock account B. The approval still displays account A and identity_verified:true. The adapter dispatches POST with B's credential and A's event body. The stable-token control writes only to mock A. All provider HTTP is intercepted, so no real event/network request occurred. See configured-switch.json, configured-stable.json and configured-identity.xml.

Exact failing test: test_JRV_33_022_configured_label_does_not_verify_a_replacement_token[other-account-token]. Source: jarvis/provider_identity.py ProviderContext.__init__ verified assignment and recheck current.rotated branch; jarvis/toolkits.py passes the rechecked context to dispatch. This is the acknowledged unverified-rotation limit in Claude's repair notes, independently reproduced, not a newly claimed real provider exploit or external process environment mutation. Same underlying P33-004 remains OPEN/PARTIAL; no replacement finding ID or downgrade.

P33-001/002/003 and original P32-001/002 reproductions PASS at the new SHA. Schema array/enum/result fixes are verified within the tested supported subset. These passes do not establish full account, concurrency, memory/schema migration or live module acceptance.
''')
write('repair-handoff.md',f'''# Remaining Claude repair

At `{SHA}`, P33-004 is still P1/PARTIAL. Keep the passing P33-001/002/003 and original P32 controls intact.

Do not call a credential's principal verified from a user-configured label. Safe immediate behavior: if the credential changes during pending approval and its actual principal cannot be established, reject before dispatch and obtain fresh approval/context. Alternatively retain the approved credential snapshot rather than swapping in an unverified replacement. Allow automatic rotation only with independently checked provider principal/workspace/scope evidence bound to the approved identity, never label equality alone. Do not send a write to discover the account, log tokens, or introduce blind retries. Missing identity verification must fail closed; no live account/network setup is required to implement the refusal.

Reproduce with `python -m pytest artifacts/jarvis-audit/modules/33-mcp-integrations/{OUT.name}/test_configured_identity.py -q`. Preserve both parameterized assertions: stable A succeeds and B's token never writes. Add a separate real or explicitly mocked identity-verification boundary test for legitimate same-principal rotation; existing tests that assume every changed token with label A belongs to A are not identity evidence.

Rerun the 57 original/follow-up checks, 223 direct regressions, 19 focused cross-pillar checks, and this case. Supply exact fix SHA. Codex source repairs remain reserved to Claude under the supplied read-only confirmation contract. STOP at current P1; do not start module 34 or deploy.
''')
write('codex-findings-reconciliation.md',f'''# Findings at {SHA}

| Finding | Independent status | Evidence |
|---|---|---|
| P33-001 P1 | FIXED for reported integrity defect | Original Docker repro and identity/private-copy controls PASS |
| P33-002 P2 | FIXED for reported scalar/tail/equality defects | Original and new-edge repros PASS; whole-value budget controls PASS |
| P33-003 P2 | FIXED for reported envelope/resource/tail defects | Original and edge repros PASS; supported block controls PASS |
| P33-004 P1 | PARTIAL/OPEN | Original unlabelled switch PASS; unchanged-label/other-account-token FAIL |
| P32-001/002 P1 | Retained FIXED for original defects | Native sibling/descendant and synthetic privacy repros PASS |

Repair SHA for passing defects `{SHA}` (P33-001/P32 earlier repair 2c4ea56 retained); no remaining P33-004 fix SHA. Four audit fixture files byte-identical. Exact test/class/run IDs in executed-results.jsonl, affected regression.xml and cross-pillar.xml. Author full-suite results are not independent totals. Prior immutable packets and source hashes retained. Broader mandatory acceptance gates remain BLOCKED.
''')
write('registration-transcript.md','''# Actual lifecycle proof

Complete Phase 3 regression reruns real offline Docker/SDK registration of SHA256/Celsius tools, per-call ToolRegistry execution returning approximately 98.6 for 37, explicit source-drift health/unregister and labelled cleanup. Original independent before-call drift rejection passes. Identity/private-copy tests include explicitly mocked image status where shown in their source. New dependent-skill tests verify disabling, retrieval exclusion, literal server references and explicit restore; the 16-thread fixture covers drift updates only.

Fixed authors and approval callbacks; no live Alita/model author or native approval UI. XML contains assertion evidence, not a full raw JSON-RPC capture. Repro server/spec/schema files and their hashes are saved. Account transport is an intercepted ledger with synthetic identities, zero real events. No account scopes/refresh/protocol interoperability acceptance claimed.
''')
write('adapter-matrix.md','''# Real versus mocked adapters

| Path | Actual run | Limit |
|---|---|---|
| Generated MCP | Existing offline Docker/SDK, registry, calls, health/unregister | Fixed author/approval, no live account |
| stdio boundaries | Real disposable Python children | Synthetic schemas/results/marker readback |
| Calendar/provider identity | Actual dispatcher/context, intercepted API, synthetic A/B tokens | No provider who-am-I/scopes; stale-label failure |
| Dependent skills | Actual local SkillMemory/SQLite state/retrieval | Literal references; no full version migration |
| Concurrency | 16 threads drift-update the same registry | No registration during task/multi-process stress |
| Recovery | Real hidden Job-owned fixture trees and synthetic disk logs | No actual Jarvis/user apps targeted |
''')
write('cross-pillar-matrix.md','''# Cross-pillar retention

Registry/generated/skill evolution: complete Phase 3 in regression.xml PASS; literal-dependent invalidation/restore in repair-replay PASS. Full schema/skill compatibility migration remains BLOCKED.

API-first/no uncertain fallback, memory contradiction/planner use, cloud-output inertness/disabled-default, protected evaluator surfaces, experimental model approval, and DAG recovery/no-replay: 19 focused checks in cross-pillar.xml PASS. Complete affected registry/provider/router/launcher/recovery suites in regression.xml PASS. No cloud requests, model training or real provider writes.

P33-004 account boundary FAIL despite passing generic permission controls. ReasoningBank-to-disabled/provisional MCP, concurrent registration during task execution, provider rate limiting and real scopes remain BLOCKED. Do not turn selected seam retention into a full Phase 1–8/global release certificate.
''')
write('compatibility.md','''# Compatibility and environment

Python 3.10.6 host, original installed utility interpreters routed read-only; audited source/data in the isolated worktree. Exact MCP stdio protocol 2025-11-25 and existing labelled SDK image unchanged. No dependency/model/protocol installs or updates by Codex. New validator intentionally supports a bounded subset, not arbitrary JSON Schema. New identity labels are non-secret settings, not provider-attested identities.

Read-only launcher-check.json remains repair_required for missing isolated environments/assets. Docker/Ollama availability is readiness evidence only. Claude's ready/full-suite results came from another environment; no transplantation into this run. Run started 2026-10-19 and finished 2026-10-20 IST; packet directory retains start date.
''')
write('security.md','''# Security gate

P33-004 remains P1/PARTIAL: unchanged configured labels cannot verify replacement bearer credentials. The approval falsely asserts identity_verified:true in the reproduced fixture; actual intercepted dispatch targets B. Credentials and identities are synthetic; only account labels/body/status are exported, no real secret/private desktop content.

Original source integrity, input/output tail/equality/resource, process-ownership and repair-log-canary defects now pass. No final verification bypass, container escape or actual provider compromise is claimed. Live scopes, identity attestation, consent/refresh, complete schema-dependent skill migration and concurrency remain unproven. No source safety guarantee weakened to obtain a PASS; new failing assertion retained. STOP/NOT READY.
''')
write('changes.md','''# Scope

Fast-forwarded isolated codex-review after saving pending audit documentation; four original independent repro files copied byte-for-byte into this packet. Added one parameterized account fixture, reports, raw XML/ledger output, hashes and paired bridge-wrapper benchmark. Updated root/app README and recovery guide with fresh independent status. No application source, config, dependency, model, UI/artwork or service policy change by Codex. Original user config and prior audit packets preserved; no merge to main/deployment/commit. No screenshots apply to this nonvisual audit.
''')
write('rollback.md','''# Rollback

No Codex source/protocol/dependency repair to revert. Pre-update preserves pending docs before the audit fast-forward. Retain prior packet hashes and do not reset the original user's checkout. Tests close only owned fixture processes/Job trees and generated labelled containers. No image rebuild/install as a rollback shortcut. Any future fix must retain original account snapshot/no-replay guarantees, generated identity compatibility and disabled-skill state across rollback.
''')
write('verdict.md',f'''# Prompt 33 — NOT READY / BLOCKED

Completed {DATE} IST at `{SHA}`. **{totals['PASS']} passed / {totals['FAIL']} failed / {totals['SKIPPED']} skipped** across {len(results)} fresh checks. Original/follow-up replay: 57 PASS. Complete directly affected regression: 223 PASS. Focused cross-pillar: 19 PASS. New account test: stable-token control PASS; replacement token for another account with unchanged label FAIL.

P33-001/002/003 reported defects and original P32 ownership/privacy defects are verified fixed within tested scope. **P33-004 P1 remains PARTIAL:** configured labels marked verified cannot establish who owns a replacement credential, so B's token dispatches A's approved event. Intercepted API only; zero real events.

[Remaining finding](failures.md) · [Claude handoff](repair-handoff.md) · [Finding reconciliation](codex-findings-reconciliation.md) · [22 stable cases](tests.jsonl) · [Fresh provenance](baseline.json).

No application source repair by Codex under the supplied read-only confirmation contract. No module 34, deployment or installs. Broader live identity/scope, schema/skill migration, memory and concurrency acceptance remain BLOCKED. Launcher repair_required. Benchmark is synthetic wrapper overhead only, not performance improvement. Directory retains the pre-midnight start date; these results are dated 2026-10-20.
''')

recon=APP/'artifacts/jarvis-audit/reconciliation/33-2026-10-20-independent-cd8861c'
recon.mkdir(exist_ok=True)
for name,origin in [('artifact-inventory.md','inventory.md'),('patch-assessment.md','changes.md'),('unresolved.md','failures.md'),('handoff.md','repair-handoff.md')]:
    content=(OUT/origin).read_text(encoding='utf-8')
    content=re.sub(r'\]\(([^)]+)\)',lambda m:'](../../modules/33-mcp-integrations/'+OUT.name+'/'+m[1]+')',content)
    (recon/name).write_text(content,encoding='utf-8')
(recon/'review-revisions.json').write_text(json.dumps({'before':OLD,'repair':SHA,'audit':SHA,'remaining_fix_sha':None,'date':DATE},indent=2))
with (recon/'findings-ledger.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['finding','status','repair_sha','current_sha'])
    for ident,status in [('P33-001','FIXED'),('P33-002','FIXED'),('P33-003','FIXED'),('P33-004','PARTIAL/OPEN'),('P32-001','FIXED'),('P32-002','FIXED')]:
        fix=OLD if ident in {'P33-001','P32-001','P32-002'} else SHA if status=='FIXED' else 'NONE'
        w.writerow([ident,status,fix,SHA])
for name,labels in [('repro-results.jsonl',{'repair-replay','configured-identity'}),('legacy-regressions.jsonl',{'regression'}),('cross-pillar-regressions.jsonl',{'cross-pillar'})]:
    (recon/name).write_text('\n'.join(json.dumps(r) for r in results if r['run'] in labels)+'\n',encoding='utf-8')
print(json.dumps({'sha':SHA,'totals':totals,'runs':summary},indent=2))
