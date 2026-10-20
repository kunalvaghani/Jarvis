"""Collect the 146ba83 independent confirmation from saved XML and pinned source."""
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
OLD='cd8861ce720ade303485ee2023430dd8c6b4f0ba'
SHA='146ba831e7ae5df1a953b0f910288c41c9ab4689'
PRIOR=OUT.parent/'2026-10-19-independent-cd8861c'

def write(name,text): (OUT/name).write_text(text.rstrip()+'\n',encoding='utf-8')
def dump(name,data): write(name,json.dumps(data,indent=2,ensure_ascii=False))
def git(*args): return subprocess.check_output(['git',*args],cwd=APP)
assert git('rev-parse','HEAD').decode().strip()==SHA
results=[];summary={}
for label in ['repair-replay','regression','cross-pillar','optional-routes']:
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
dump('baseline.json',dict(completed_date=DATE,packet_started_date='2026-10-20',date_note='Fresh confirmation on 2026-10-20 IST.',
    source_sha=SHA,prior_sha=OLD,branch='codex-review',platform=platform.platform(),python=sys.version,executable=sys.executable,
    runs=summary,totals=totals,test_process_peak_memory='NOT MEASURED; synthetic benchmark allocation peak only',
    dependencies='Existing original .venv and .venv-skills interpreters; audited source/cwd remain isolated',
    upstream_claim='3473 passed/147 skips is author evidence, not independently added to totals'))
paths=['jarvis/mcp_bridge.py','jarvis/mcp_contract.py','jarvis/mcp_synthesis.py','jarvis/provider_identity.py',
       'jarvis/toolkits.py','jarvis/tools.py','jarvis/skill_evolution.py','jarvis/skill_memory.py','jarvis/skill_store.py',
       'jarvis/launcher.py','jarvis/recovery.py','tests/test_prompt33_followup.py']
dump('source-hashes.json',{p:hashlib.sha256((APP/p).read_bytes()).hexdigest() for p in paths})
dump('prior-evidence-hashes.json',{p.relative_to(APP).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
    for p in PRIOR.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
names=['test_mcp_boundaries.py','test_recovery_boundaries.py','test_contract_edges.py','test_provider_context.py','test_configured_identity.py']
dump('replay-source-comparison.json',{name:(OUT/name).read_bytes()==(PRIOR/name).read_bytes() for name in names})
dump('protocol.json',{'stdio_protocol':mcp_bridge.VERSION,'runtime':mcp_synthesis.image_status(),
    'dependency_change':'NONE','transport_change':'NONE','direct_sdk_build_pin':'mcp==2.3.0',
    'identity_policy':'labels unverified; credential change rejected absent independent principal/workspace/scope confirmation; no production verifier registered'})

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

# Appended to collect.py by build_collector.py; helpers/actual XML results are defined in that prefix.
oldcases={r['id']:r for r in [json.loads(s) for s in (PRIOR/'tests.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]}
updates={
 4:('PASS','Mock/local boundary: draft-only Slack goal rejects slack_send; denied approval sends nothing; approved exact channel/message reaches intercepted API. No real Slack draft/send.'),
 7:('PASS','Real local stdio: two approved calls observe synthetic rotated environment token via hash readback; returned token content is redacted. No OAuth refresh/live-provider claim.'),
 22:('PASS','All original two-account switch tests, including stale-label B-token, refuse before write; stable-token control succeeds. Mock independent verifier accepts same principal/workspace/scopes and rejects other principal/workspace/narrow scopes. Live identity remains BLOCKED.')}
cases=[]
for i in range(1,23):
    ident=f'JRV-33-{i:03}';previous=oldcases[ident]
    status,reason=updates.get(i,(previous['status'],previous['reason']))
    cases.append(dict(id=ident,status=status,reason=reason,sha=SHA,prior_status=previous['status'],date=DATE,
                      evidence='executed-results.jsonl; repair-replay.xml; regression.xml; optional-routes.xml; cross-pillar.xml'))
write('tests.jsonl','\n'.join(json.dumps(r) for r in cases))

# Also measure the changed provider-context path under an unchanged synthetic credential.
from jarvis import provider_identity
previous_identity=types.ModuleType('audit_previous_provider_identity')
exec(compile(git('show',OLD+':app/jarvis/provider_identity.py'),'<fixed-prior-provider>','exec'),previous_identity.__dict__)
environment={'JARVIS_GOOGLE_ACCOUNT':'account-a@example.test','JARVIS_GOOGLE_ACCESS_TOKEN':'SYNTHETIC_BENCH_TOKEN'}
for label,module,revision in [('before',previous_identity,OLD),('after',provider_identity,SHA)]:
    for _ in range(20): module.ProviderContext('calendar',environment).recheck(environment)
    samples=[];tracemalloc.start()
    for _ in range(300):
        start=time.perf_counter_ns();module.ProviderContext('calendar',environment).recheck(environment)
        samples.append((time.perf_counter_ns()-start)/1e6)
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    measure.append(dict(revision=label,sha=revision,samples=300,fixture='provider context capture/recheck, stable synthetic token, no verifier',
        p50_ms=statistics.median(samples),p95_ms=sorted(samples)[284],traced_peak_bytes=peak))
with (OUT/'benchmarks.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(measure[0]));w.writeheader();w.writerows(measure)
dump('benchmark-provenance.json',{'before':OLD,'after':SHA,'warmup':20,'samples_per_fixture_revision':300,
 'scope':'Two fixed-input pairs: bridge+contract with fake transport, and changed provider context with stable synthetic credential/no verifier. Entire respective sources loaded from named revisions. Warm sequential tracemalloc, no provider/process/model latency or improvement claim.'})

write('inventory.md',f'''# Prompt 33 independent confirmation — {DATE}

Pinned claude/audit `{SHA}`, prior `{OLD}`, isolated codex-review. Pending audit docs preserved under pre-update before fast-forward; original user configuration untouched. Application AGENTS, Prompt 33 and supplied reconciliation contract applied; master contract remains unavailable. Codex performs independent confirmation without application source repairs.

Inspected actual provider_identity/toolkits changes and updated author tests/report. Labels are now display/drift detection only. No production principal verifier is registered, so credential changes while approval is pending reject before dispatch; unchanged approved context uses its captured snapshot. Explicit verifier API may confirm principal/workspace/scopes for rotation, but tests of it are labelled MOCK. Five independent repro files are byte-identical to the prior packet. Four obsolete author tests assuming label-based identity were replaced by explicit verifier/default-refusal controls; original Codex assertions were not weakened.

Actual paths remain ToolRegistry → toolkits → agent_tools → mcp_bridge for MCP, and toolkits → ProviderContext → remote_tool for optional writes. Generated Docker identity/sandbox, schema/result validation and literal-reference dependent-skill invalidation remain. MCP stdio protocol and installed image/dependencies unchanged. New independent Slack intent/approval and stdio token readback/redaction cases add coverage.

Prior packets and author 3473/147 full-suite claims remain historical, not independent totals. Source/image/schema hashes and saved XML are authoritative for this run. Test process peak memory not measured; paired allocation benchmarks are explicitly synthetic. No source/config/dependency/model/UI changes, installs, cloud requests, live provider writes or production process targets by Codex.
''')
write('failures.md','''# No reported defect reproduced at the final SHA

P33-001, P33-002, P33-003 and P33-004 all pass the unchanged independent reproductions in this packet. Original P32-001/002 retain passing native/synthetic controls. No failing pytest checks in this fresh confirmation.

This closes the reported findings within tested scope, not all Prompt 33 acceptance. Remaining BLOCKED requirements: real provider identities/scopes/consent/refresh, broad filesystem policy for trusted external host executables, controlled provider read-rate-limit backoff, full schema-version/skill compatibility migration, concurrent registration while another task executes (including multi-process), ReasoningBank retrieval-to-disabled/provisional-tool identity, and native Blender/Unreal MCP unavailable-route acceptance. Complete live/native startup remains unavailable in the isolated environment. Process peak memory was not captured.

No production principal verifier exists. Credential replacement requires fresh approval by default; no automatic token refresh/reconnect safety for live accounts is certified. Configured host executables remain trusted OS programs, not sandboxed by an MCP tool allowlist. SKIPPED=0 means selected fixtures ran; it does not turn these unexecuted gates into PASS.
''')
write('codex-findings-reconciliation.md',f'''# Finding reconciliation at {SHA}

| Finding | Fix SHA | Fresh evidence | Status |
|---|---|---|---|
| P33-001 P1 source integrity | 2c4ea56 | Original real Docker drift rejection, code/spec/image/private-copy controls | FIXED |
| P33-002 P2 input schema/tail/equality | cd8861c | Original invalid argument + full array tail/enum/const/budget controls | FIXED |
| P33-003 P2 malformed output/resource | cd8861c | Original envelope + output tail/resource/content controls | FIXED |
| P33-004 P1 account-context drift | 146ba83 | Unlabelled, changed-label and stale-label B-token reproductions refuse; unchanged token succeeds; explicit mock verifier principal/workspace/scope checks | FIXED |
| P32-001 P1 ownership | 2c4ea56 | Native sibling preserved/descendant terminated controls | Retained FIXED |
| P32-002 P1 repair privacy | 2c4ea56 | Synthetic original/late/multiline/bootstrap canaries | Retained FIXED |

Exact complete source SHAs are in baseline/source-hash artifacts and reconciliation review-revisions.json. Current replay is 63 PASS, not a claim that every old author test survived unchanged. Five original independent fixtures are byte-identical. Four old author P33-004 tests that assumed labels proved identity were retired and replaced by explicit mock-verifier and fail-closed assertions, as documented in the reviewed diff/author report. No failing original Codex assertion was removed.

Neighbor retention: 223 direct regression checks; 19 focused cross-pillar; 4 new optional-route cases. Exact IDs/class/run/evidence in executed-results.jsonl. Upstream 3473/147 is author evidence only. Further full-module gates remain BLOCKED; no blanket release certification.
''')
write('remaining-work.md','''# Remaining Prompt 33 acceptance

All four reported P33 findings now have independent passing repros. No source repair is pending for those findings. To complete the wider module:

1. Implement/review real read-only provider principal verification and validate scopes/consent/refresh against explicitly authorized accounts. Until then preserve credential-change refusal and fresh approval.
2. Prove full schema-version migration with dependent-skill compatibility tests and lineage, including memory references; current literal-reference invalidation/restore is narrower.
3. Exercise registration concurrently with another active task and multi-process readers/writers; the existing 16-thread drift-update test is narrower.
4. Establish ReasoningBank retrieval-to-call policy for disabled/provisional MCPs and actual tool/version identity.
5. Validate filesystem-policy narrowing for trusted external host servers, provider rate-limit read backoff, and Blender/Unreal API-unavailable MCP routes. Current generated Docker restrictions and no-write-retry controls do not prove those cases.
6. Complete full live/native startup/worker/service acceptance and representative resource measurements in a prepared environment; this worktree's launcher remains repair_required.

No module 34 work, deployment, account writes, packages or real verifier setup is authorized by this evidence packet. The selected fixture run is complete; release/full-module verdict remains NOT READY/BLOCKED under Prompt 33's missing-safety-evidence gate.
''')
write('registration-transcript.md','''# Executed lifecycle and returned data

Fresh complete Phase 3 tests register SHA256/Celsius tools through real offline Docker/SDK, execute via ToolRegistry with a checked returned 98.6 for Celsius 37, then detect tampering, unregister and assert no labelled leftovers. Before-call independent source drift is rejected. Identity/private-copy extra controls are explicitly mocked where their source says so. Fixed author/approval callbacks, no live Alita/model or native approval UI certificate.

New local stdio token case makes two separately approved calls, verifies the returned hash matches each synthetic rotated environment token, and verifies the literal token is redacted from evidence/approval. This demonstrates configured stdio per-call refresh, not OAuth refresh or live provider identity.

New Slack cases reject slack_send for a draft-only goal and verify denied approval yields no intercepted write while approved exact channel/message yields one mock POST. No real Slack draft or message created. Raw XML and adjacent literal schema/server/spec files preserve reproducibility; no full JSON-RPC wire capture was enabled.
''')
write('adapter-matrix.md','''# Actual versus mocked routes

| Route | Actual execution | Limit |
|---|---|---|
| Generated MCP | Offline Docker/SDK, registry/call/health/unregister and data readback | Fixed author/approval |
| Local stdio/token rotation | Real disposable child processes and synthetic token hash readback/redaction | No OAuth/live provider |
| Calendar/Slack | Real ToolRegistry/adapter/context, intercepted API ledger | No real account scopes/events/messages |
| Principal verification | Explicit mocked read-only verifier, default absence fails closed | No production verifier registered |
| Memory/skills/concurrency | Actual SQLite/catalog and 16-thread drift updates | No full migration or registration-during-task proof |
| Recovery | Real owned Windows fixture trees and synthetic disk logs | No running Jarvis/user process targeted |
''')
write('cross-pillar-matrix.md','''# Cross-pillar retention

Complete direct affected regression: 223 PASS. Registry/generated server/skill FIX-DERIVED lifecycle is included in the complete Phase 3 suite. API-first/no-write-fallback replay, memory contradiction/planner use, cloud-output inertness/disabled-default, immutable evaluator/protected surfaces, experimental model approval and DAG recovery/no-replay: 19 focused PASS.

Account permission/identity tests now all PASS in controlled mocks; default missing verifier rejects changed credentials. Dependent literal-reference skill disable/retrieval/restore and 16-thread registry drift controls PASS. Full schema compatibility migration, ReasoningBank identity, active registration concurrency and live scopes remain BLOCKED. Selected seam checks are not full Phase 1–8/global acceptance. No cloud call/training or live provider write.
''')
write('compatibility.md','''# Compatibility and readiness

Python 3.10.6 host with existing original utility interpreters routed read-only; reviewed source/data stay isolated. MCP stdio protocol 2025-11-25 and existing labelled image/SDK unchanged. No dependency/model/protocol installs. Bounded schema subset intentionally rejects unsupported schemas; arbitrary JSON Schema support is not claimed.

Changed behavior: configured account labels are unverified display values. An unchanged credential can use its approved snapshot. A changed credential requires fresh approval unless an independently registered read-only verifier proves the same principal/workspace and sufficient scopes. No production verifier is registered, so default refusal is expected and tested.

Isolated launcher-check.json still reports repair_required for missing environments/checkpoints. Docker/Ollama availability is readiness only. Author ready/full-suite evidence came from another environment and does not supersede this result. No native approval UI/live provider integration certificate.
''')
write('security.md','''# Security result

All reported P33-001…004 and original P32-001/002 safety reproductions pass independently at the final SHA. In particular, configured labels no longer set identity_verified; a token for B under label A refuses before dispatch, while the stable-token control succeeds once. No verifier is registered by default; unknown replacement identity fails closed. Explicit mock-verifier tests validate same-principal rotation and reject another principal/workspace/narrow scope/failing lookup.

No unapproved effects observed in selected fixtures. API writes are intercepted, all tokens/body/identities are synthetic, and native termination is limited to test-owned Job trees. No real sends/events, paid API, cloud private data, desktop recording, model training, package install or shared-service operation. No application source changes by Codex. Pattern redaction and successful fixtures are not universal privacy or release proof. Wider missing safety gates in remaining-work.md keep the full module NOT READY/BLOCKED.
''')
write('changes.md','''# Codex scope

Preserved pending audit docs, fast-forwarded isolated codex-review to the actual Claude fix, and copied five independent repro files byte-for-byte into this new packet. Added four optional-route assertions, raw observations/XML, source/evidence hashes, paired bridge/context benchmarks and reports. Updated both READMEs and the recovery guide with the current independent status. No application source, config, dependency, model, UI/artwork, service policy, commit, deployment or main merge. Original user config and historical packets preserved. No screenshot applies to this nonvisual verification.
''')
write('rollback.md','''# Rollback

No Codex application source/protocol/dependency repair to revert. pre-update preserves the audit docs before fast-forward. Retain the previous packets and do not reset the original checkout. Tests close only owned temporary processes/Job trees and their labelled generated containers. Any future protocol/config rollback must preserve generated identity, disabled-skill state and uncertain-write checkpoints. Do not restore label-based automatic rotation: absent an independent verifier, require fresh approval after credential drift. No image rebuild/install as a rollback shortcut.
''')
write('verdict.md',f'''# Prompt 33 — reported findings VERIFIED FIXED; full acceptance PARTIAL / NOT READY

{DATE}, independent isolated codex-review pinned to `{SHA}`. **{totals['PASS']} PASS / {totals['FAIL']} FAIL / {totals['SKIPPED']} SKIPPED**: 63 original/follow-up repairs, 223 complete directly affected regressions, 19 focused cross-pillar checks and 4 optional-route cases.

P33-001/002/003/004 all pass their reported independent reproductions, including the stale-label B-token failure. Original P32 ownership/privacy controls retain passing results. No unresolved reproduced P0/P1/P2 from those findings. Default changed credentials reject before dispatch; independent rotation verification is tested only with explicit mocks and no production verifier is registered.

[Reconciliation](codex-findings-reconciliation.md) · [Remaining full-module gates](remaining-work.md) · [22 cases](tests.jsonl) · [Raw run provenance](baseline.json).

The selected independent verification is complete; full Prompt 33 deployment acceptance remains BLOCKED by live identity/scopes, schema/skill migration, memory/concurrency/policy and environment gates. Worktree launcher repair_required. No source repair by Codex, real provider write, install, deployment or module 34. Real offline compute lifecycle passes with fixed author/approval; synthetic paired benchmarks are not live latency or improvement claims.
''')

recon=APP/'artifacts/jarvis-audit/reconciliation/33-2026-10-20-independent-146ba83'
recon.mkdir(exist_ok=True)
for name,origin in [('artifact-inventory.md','inventory.md'),('patch-assessment.md','changes.md'),('unresolved.md','remaining-work.md'),('handoff.md','remaining-work.md')]:
    text=(OUT/origin).read_text(encoding='utf-8')
    text=re.sub(r'\]\(([^)]+)\)',lambda m:'](../../modules/33-mcp-integrations/'+OUT.name+'/'+m[1]+')',text)
    (recon/name).write_text(text,encoding='utf-8')
fixes={'P33-001':'2c4ea56eb7967929e49dad07b0612cb99caaf56e','P33-002':OLD,'P33-003':OLD,'P33-004':SHA,
       'P32-001':'2c4ea56eb7967929e49dad07b0612cb99caaf56e','P32-002':'2c4ea56eb7967929e49dad07b0612cb99caaf56e'}
(recon/'review-revisions.json').write_text(json.dumps({'before':OLD,'audit':SHA,'fixes':fixes,'date':DATE},indent=2))
with (recon/'findings-ledger.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['finding','status','fix_sha','verified_at_sha'])
    for ident,fix in fixes.items(): w.writerow([ident,'FIXED',fix,SHA])
for name,labels in [('repro-results.jsonl',{'repair-replay','optional-routes'}),('legacy-regressions.jsonl',{'regression'}),('cross-pillar-regressions.jsonl',{'cross-pillar'})]:
    (recon/name).write_text('\n'.join(json.dumps(r) for r in results if r['run'] in labels)+'\n',encoding='utf-8')
print(json.dumps({'sha':SHA,'totals':totals,'runs':summary},indent=2))
