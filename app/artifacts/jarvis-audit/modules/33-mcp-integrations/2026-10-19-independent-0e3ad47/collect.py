"""Rebuild the dated audit reports from saved pytest XML and local source evidence."""
import csv
import hashlib
import importlib.util
import json
import platform
import re
from pathlib import Path
import statistics
import subprocess
import sys
import time
import tracemalloc
import types
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
sys.path.insert(0, str(APP))
from jarvis import mcp_bridge, mcp_synthesis

def write(name, text):
    (OUT / name).write_text(text.rstrip() + '\n', encoding='utf-8')

def dump(name, data):
    write(name, json.dumps(data, indent=2, ensure_ascii=False))

def git(*args):
    return subprocess.check_output(['git', *args], cwd=APP).decode('utf-8').strip()

sha = git('rev-parse', 'HEAD')
prior = '6f880332610cc1a5c483f702c5f33b43d1537aa0'
assert sha == '0e3ad4706b5120e5d0479d34333e5faa7b0931b5'
assert git('rev-parse', 'claude') == sha
spec = importlib.util.spec_from_file_location('audit_mcp_cases', OUT / 'test_mcp_boundaries.py')
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)
rows, summaries = [], {}
for label in ('baseline', 'living-skills', 'boundaries', 'neighbors'):
    root = ET.parse(OUT / (label + '.xml')).getroot()
    subset = []
    for test in root.iter('testcase'):
        status = 'FAIL' if test.find('failure') is not None or test.find('error') is not None else 'SKIPPED' if test.find('skipped') is not None else 'PASS'
        row = dict(id=test.get('name'), classname=test.get('classname'), status=status,
                   seconds=float(test.get('time', 0)), run=label, sha=sha,
                   evidence=label + '.xml')
        subset.append(row)
    rows += subset
    summaries[label] = {status:sum(r['status']==status for r in subset) for status in ('PASS','FAIL','SKIPPED')}
    summaries[label]['seconds'] = sum(float(s.get('time', 0)) for s in root.findall('testsuite'))
write('executed-results.jsonl', '\n'.join(json.dumps(r) for r in rows))
totals = {s:sum(r['status']==s for r in rows) for s in ('PASS','FAIL','SKIPPED')}
dump('baseline.json', dict(date='2026-10-19', sha=sha, branch=git('branch','--show-current'),
    python=sys.version, executable=sys.executable, platform=platform.platform(),
    runs=summaries, total=totals, test_process_peak_memory='NOT MEASURED',
    scope='Offline local processes/containers and fake providers; no live account acceptance',
    installed_dependency_wrapper='../../31-ui-island-pip/2026-10-19-independent-0e3ad47/run_installed_dependencies.py'))

source_paths = ['jarvis/mcp_bridge.py','jarvis/mcp_synthesis.py','jarvis/tools.py','jarvis/toolkits.py',
 'jarvis/agent_tools.py','jarvis/agent_session.py','jarvis/skill_evolution.py','jarvis/skill_store.py',
 'jarvis/task_state.py','scripts/setup/setup_mcp_runtime.py','docs/system-map.md']
hashes = {p:hashlib.sha256((APP / p).read_bytes()).hexdigest() for p in source_paths}
dump('source-hashes.json', hashes)
oldroot = OUT.parent
old = [p for p in oldroot.iterdir() if p.is_file()]
old += list((APP / 'artifacts/jarvis-audit/phase-03').glob('*'))
dump('prior-evidence-hashes.json', {p.relative_to(APP).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in old if p.is_file()})
dump('protocol.json', {'bridge_protocol':mcp_bridge.VERSION,'transports':['stdio'],
    'capabilities':{},'server_requests':'refused; no sampling/elicitation/roots',
    'image':mcp_synthesis.image_status(),'SDK_build_pin':'mcp==2.3.0',
    'build_pin_scope':'SDK fixed, transitive packages recorded in historical image manifest; not a complete dependency lock'})
source = mcp_synthesis.generate(cases.SPEC)
write('approved-generated-server.py', source)
dump('generated-spec.json', cases.SPEC)
write('stdio-fixture-server.py', cases.SERVER)
dump('captured-schema.json', {'origin':'literal schema emitted by executed local fixture, see stdio-fixture-server.py',
    'tools':[{'name':'echo','inputSchema':{'type':'object','required':['count'],
    'properties':{'count':{'type':'integer'}},'additionalProperties':False}}]})
dump('schema-version-hashes.json', {name:hashlib.sha256((OUT / name).read_bytes()).hexdigest()
    for name in ('captured-schema.json','generated-spec.json','approved-generated-server.py')})
observation = json.loads((OUT / 'generated-drift-observation.json').read_text())
call = json.loads(observation['approval_detail'])
dump('permission-manifest.json', dict(generated_call=call,
    registration_digest=observation['registered_digest'], current_digest=observation['current_digest'],
    policy={'network':'none','host_mounts':'single read-only server.py','uid':'65534:65534',
            'memory':'256m','pids':32,'capabilities':'ALL dropped','filesystem':'read-only except bounded tmpfs',
            'approval':'synthetic callback for registration and each call; no actual UI approval proof'}))

# Paired fixed-input microbenchmark; no services or model calls.
previous_source = subprocess.check_output(['git','show',prior+':app/jarvis/mcp_synthesis.py'],cwd=APP)
previous = types.ModuleType('jarvis.audit_prior_synthesis')
exec(compile(previous_source, '<fixed-prior-mcp-synthesis>', 'exec'), previous.__dict__)
measurements = []
for name, module, version in [('prior',previous,prior),('current',mcp_synthesis,sha)]:
    for _ in range(20):
        module.screen(module.generate(cases.SPEC),cases.SPEC)
    samples=[]
    tracemalloc.start()
    for _ in range(300):
        started=time.perf_counter_ns()
        module.screen(module.generate(cases.SPEC),cases.SPEC)
        samples.append((time.perf_counter_ns()-started)/1e6)
    _,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    measurements.append(dict(revision=name,sha=version,fixture='generate+AST-screen fixed SHA256 spec',
        samples=len(samples),p50_ms=statistics.median(samples),p95_ms=sorted(samples)[284],traced_peak_bytes=peak))
with (OUT / 'benchmarks.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=list(measurements[0]))
    writer.writeheader();writer.writerows(measurements)
dump('benchmark-provenance.json', {'prior_source_sha256':hashlib.sha256(previous_source).hexdigest(),
    'current_source_sha256':hashes['jarvis/mcp_synthesis.py'], 'scope':'warm sequential microbenchmark including tracemalloc; not MCP latency or performance improvement',
    'prior_commit':prior,'no_source_optimization':True})

reasons = {
1:('BLOCKED','Live calendar scopes/access and account fixture not validated; no real account reads.'),
2:('BLOCKED','Calendar write approval route inspected; exact case/account readback not executed.'),
3:('BLOCKED','Credential catalog regression passes generically; absent-Jira-specific case not executed.'),
4:('BLOCKED','Slack approval/timeout regressions pass; no dedicated Slack draft action or real send journey proven.'),
5:('FAIL','test_JRV_33_005_schema_invalid_call_must_not_reach_server; P33-002'),
6:('FAIL','test_JRV_33_006_malformed_result_must_raise_typed_error; P33-003'),
7:('BLOCKED','No OAuth refresh/rotation/reconnect fixture; explicit env credential forwarding only.'),
8:('BLOCKED','Tenant/account isolation not established.'),
9:('BLOCKED','Generated AST/Docker restriction passes; trusted external executable has host privileges and is not sandboxed.'),
10:('BLOCKED','Bridge has no retry/backoff scheduler; provider-specific rate-limit behavior not exercised.'),
11:('PASS','Local stdio test_JRV_33_018_namespaced_lookup_keeps_builtin_authority; wrappers do not promote remote short names.'),
12:('PASS','Local stdio test_JRV_33_017_dead_host_is_called_once_and_blocks_resume; timeout/cancel legacy controls also pass.'),
13:('FAIL','Actual generated Docker registration/call returned altered source output; P33-001. Fixed author/callback, not live Alita/model.'),
14:('PASS','Scope: generated AST rejects 6 malicious implementations, offline container restriction check passes, ambient secret canary absent in stdio child. Trusted configured executable remains host-trusted.'),
15:('BLOCKED','Skills bind wrapper names, not MCP server/tool/schema versions; dependent skill invalidation not implemented/proven.'),
16:('PASS','Scope: executor returns injection text as evidence without dispatch. Live planner resistance not proven.'),
17:('PASS','Real local stdio host exits after marker append: one marker only, resume blocked; no GUI fallback invoked.'),
18:('PASS','Two real local stdio servers advertise echo; explicit server resolution and built-in run_command preserved.'),
19:('BLOCKED','No Blender/Unreal API-unavailable MCP fallback fixture in this pass.'),
20:('BLOCKED','Concurrent registration/task-routing stress not executed; only registry mutations explicitly lock.'),
21:('BLOCKED','Disabled server direct call rejects in executed test, but ReasoningBank retrieval-to-call path not executed. Provisional generated tools intentionally callable with approval.'),
22:('BLOCKED','Two mock account/workspace approval identity switch not executed; no structured account identity in current MCP approval payload.')}
oldrows = [json.loads(line) for line in (oldroot / 'tests.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
catalog=[]
for number,(status,reason) in reasons.items():
    ident=f'JRV-33-{number:03}'
    catalog.append(dict(id=ident,status=status,reason=reason,sha=sha,date='2026-10-19',
        original_status=next((r['status'] for r in oldrows if r['id']==ident),'UNAVAILABLE'),
        evidence='executed-results.jsonl; boundaries.xml; living-skills.xml; source-hashes.json'))
write('tests.jsonl','\n'.join(json.dumps(r) for r in catalog))

write('inventory.md', f'''# Prompt 33 independent inventory — 2026-10-19

Pinned claude/audit HEAD `{sha}`; isolated `codex-review`. Original checkout user config untouched. See [source hashes](source-hashes.json), [baseline](baseline.json), [historical hashes](prior-evidence-hashes.json). Module originals are planned NOT RUN case rows, not executed proof. The master contract file is unavailable; Downloads reconciliation contract read and applied (Codex confirmation read-only, Claude owns source repairs).

Path/call chain: ToolRegistry → toolkits → agent_tools → mcp_bridge.execute → short-lived StdioClient. Local `.jarvis/mcp.json` configs override generated names. `mcp_synthesis` validates a fixed typed spec, templates/screens Python, tests in an existing image, approves registration, atomically saves generated registry. `health` explicitly checks source hash; invocation does not (P33-001). Health/unregister may restore an older registry entry. No remote short name replaces a built-in. `SkillEvolution` binds registry wrapper names; schema identity migration/invalidation is not established.

Protocol `2025-11-25`, stdio only, bounded JSON lines/pagination/timeouts; no HTTP transport, resources, sampling or elicitation. Disabled/trusted flags and exact tool allowlists gate executable start. Generated tools remain provisional yet callable with per-call approval, by design. There is no separate global MCP feature flag; enabled config/entry is the switch. Tokens are named via `env_names`; no automatic OAuth refresh. Calendar/Jira/Slack are direct requests adapters in toolkits, credential-gated by process environment, not full MCP provider clients.

Read system-map, toolkit guide, Phase 3 implementation/security/commit evidence, prior independent findings, current source and tests. The prior same-SHA Prompt 31 packet has 642 passed/13 skipped across neighboring Phase 1–8 suites; this is historical retention evidence, not newly executed Prompt 33 acceptance. Original Phase 3 fixes G4/G5 (container cleanup/argument limit) reproduce passing in the fresh 34-test suite. Its tamper claim requires an explicit health call and does not cover dispatch integrity.

No source, dependency, runtime manifest, launcher, account, UI or model changes. Test process peak memory was not captured; benchmark memory is explicitly limited to the measured collector operation.
''')
write('failures.md', '''# Confirmed findings

## P33-001 — P1: approved generated source integrity is not enforced at invocation

Registration screens/tests and stores code_sha256. mcp_synthesis.configurations discards that identity from returned config; mcp_bridge.execute starts the mounted source without verifying it. Health verifies only when called separately. Real offline Docker fixture registers a valid SHA256 tool, replaces its implementation after registration, and calls through ToolRegistry. It returns UNREVIEWED_SYNTHETIC_RESULT, despite a different current digest. Per-call approval shows command/path/arguments, not the changed source/hash. See generated-drift-observation.json and permission-manifest.json. This proves an execution integrity gap, not a container escape or demonstrated remote ability to edit host source. Container network/filesystem restrictions remained active.

Failing test: test_JRV_33_013_generated_source_change_rejected_before_call. Fix SHA: none. Status APPLIES / OPEN. Source: jarvis/mcp_synthesis.py configurations/health; jarvis/mcp_bridge.py execute.

## P33-002 — P2: advertised input schema is not validated before tools/call

The real local server advertises required integer count and additionalProperties=false. A string count reaches tools/call and is accepted as evidence. execute checks the allowlisted name and argument-object shape only. Test test_JRV_33_005_schema_invalid_call_must_not_reach_server fails. Source: mcp_bridge.execute. No real external write occurred. Schema version tracking and dependent-skill revalidation remain additionally BLOCKED, not falsely counted as this test's proof.

## P33-003 — P2: malformed tool result accepted as evidence

The local server returns content as a string and isError as string "false". The dict passes the check that isError is not literal True and becomes ToolResult evidence. Test test_JRV_33_006_malformed_result_must_raise_typed_error fails. This does not prove final task completion/verification accepts it. Source: mcp_bridge.execute.

Prior P32-001 ownership and P32-002 repair-log privacy remain OPEN on this unchanged SHA. No claim that Prompt 32 was repaired by starting 33.
''')
write('repair-handoff.md', '''# Claude repair handoff

Pinned SHA and raw assertions are in baseline.json/boundaries.xml. Reproduce from app with the existing interpreter: `python -m pytest artifacts/jarvis-audit/modules/33-mcp-integrations/2026-10-19-independent-0e3ad47/test_mcp_boundaries.py -q`. Docker tests need the existing labelled jarvis-mcp-runtime:1 image; do not install/rebuild silently.

1. P33-001: retain generated tool identity through configuration/dispatch, enforce approved implementation/spec/schema/image identity immediately before execution, and prevent mutation between validation and mounted execution. Disable drifted entries and dependent skills until revalidated/reapproved. Merely calling health earlier leaves a race. Include source/version identity in final approval. Preserve explicit per-call approval, sandbox and no-retry behavior.
2. P33-002: validate bounded advertised input schema and exact arguments before tools/call; define supported schema subset, reject unsupported schemas, pin schema/version and invalidate dependent skill contracts on change.
3. P33-003: validate MCP result envelopes/content/structured output/error flag types and output schema where supplied; raise typed failure while preserving uncertainty for attempted writes. Do not manufacture success or retry.
4. Run failing assertions unchanged, then the 94 baseline, 34 living-skill and 36 routing/recovery checks, plus concurrent registration and schema/skill lineage/account-switch cases still blocked here. Reverify prior Prompt 32 P1s independently. Produce exact fix SHA for new Codex confirmation.

Codex made no application source fix under the read-only independent-confirmation contract. STOP on P1; no module 34 or deployment.
''')
write('registration-transcript.md', '''# Registration / invocation / unregister evidence

Actual independent Docker trace: generated SPEC → static screen → real tools/list and two test vectors → synthetic registration approval → provisional registry entry. Then host test changes only the generated implementation. ToolRegistry mcp_call → synthetic per-call approval → actual altered structuredContent returned. Exported response and actual call approval are in generated-drift-observation.json; approved source and spec are saved alongside. Finally unregister and labelled reap ran in the test's finally block. The failed safety assertion is retained, not xfailed.

Separate existing test_P03_mcp_workflows_register_call_and_unregister passed: registers SHA256 and Celsius tools, actual Celsius call returns approximately 98.6 for 37, explicit health detects modified SHA256 source and unregisters it, and labelled cleanup reports zero leftover containers. The raw XML records the assertions' result; no packet-level JSON-RPC wire capture was enabled. The fixture source and advertised literal schema are preserved; do not call this a full transport capture.

The realistic supported journey is the offline compute-tool lifecycle with real Docker/SDK/bridge/ToolRegistry and returned data. Author/model and approvals are fixed synthetic callbacks. No live Alita author, native approval UI, account write or production journey is certified.
''')
write('adapter-matrix.md', '''# Actual adapter coverage

| Route | Evidence | Limit |
|---|---|---|
| Local stdio | Real child processes, init/list/call, error/timeout/cancel/death | Synthetic server, local-only markers |
| Generated MCP | Existing offline Docker image and SDK, real registration/invocation/health/unregister | Fixed author and approval callbacks; integrity failure |
| Calendar/Jira/Slack | Source inspection and toolkit credential/approval/error fixture regressions | No real account, scope, consent, refresh or final provider readback |
| Built-in namespace | Two real local stdio servers with same echo name | Explicit wrapper routing, no model-choice proof |
| Ambient secrets | Synthetic env canary excluded from child | Configured trusted host process still has filesystem/OS privileges |
| Memory/skills | 34 real local skill/SQLite/adapter lifecycle tests | No MCP schema dependent-skill version invalidation or account switch proof |
''')
write('cross-pillar-matrix.md', '''# Cross-pillar retention

| Seam | Fresh evidence | Status / limitation |
|---|---|---|
| ToolRegistry / generated MCP / skill FIX/DERIVED | living-skills.xml 34 PASS; boundaries.xml | Existing lifecycle passes; integrity FAIL; dependent schema invalidation BLOCKED |
| API-first router / MCP / programmatic routes | neighbors.xml routing tests | PASS existing routing; Blender/Unreal missing-API MCP fallback NOT RUN |
| Permissions / provider schema | baseline.xml toolkit and registry suite; boundaries.xml | Approval/deny controls PASS; input/output schema FAIL |
| Task recovery / uncertain write | stdio death and timeout, task_recovery suite | PASS bounded fixture; prior recovery P1s remain OPEN |
| Cloud advice / untrusted code | 6 malicious generated implementation controls | AST policy PASS; live cloud-to-MCP journey NOT RUN |
| DGM / immutable evaluator | Prior same-SHA Prompt 31 full regression includes Phase 6 | Historical only; fresh module-wide run stopped on P1 |
| Memory / identity and versions | Phase 3 skill telemetry PASS | Server/schema/account binding and ReasoningBank retrieval-to-disabled-tool BLOCKED |

No claim that all seven mechanisms completed full acceptance. See tests.jsonl for all 22 stable cases.
''')
write('changes.md', '''# Change scope

Added independent fixture tests, raw observations, reports, hashes and a paired measurement in this dated subdirectory. Updated the audit worktree root/app README with current results and repair links. No application source repair, dependency/protocol change, installation, UI change, service recovery mutation, commit, merge or deployment. Existing recovery documentation qualification belongs to the previous Prompt 32 work and is retained. Module originals remain immutable. No screenshot is applicable to this nonvisual audit.
''')
write('compatibility.md', '''# Compatibility and readiness

Python 3.10.6 host; existing Docker Linux engine 29.8.2. See protocol.json for actual labelled image ID/SDK and launcher-check.json for read-only readiness. SDK direct build pin is mcp==2.3.0; historical image package inventory is retained unchanged. No dependencies fetched or changed. Exact stdio protocol 2025-11-25 is supported; other versions fail negotiation. HTTP MCP and token-refresh orchestration are unsupported in this bridge.

Fresh runs: baseline 94 PASS; Phase 3 34 PASS; neighbors 36 PASS; boundary 5 PASS/3 FAIL. Total 169 PASS/3 FAIL, no skips. Isolated worktree uses the original installed interpreter/utility dependencies through the saved read-only wrapper; reviewed source/cwd and test data remain isolated. Launcher exits 1 / repair_required for missing isolated environments and model assets; Docker availability is readiness, not a live-account test.

Full final acceptance stopped on unresolved P1. No new source was edited, so there is no after-fix success claim. Disabled server direct execution rejects; comprehensive enabled/disabled cloud/account routes and soak/concurrency acceptance remain BLOCKED.
''')
write('security.md', '''# Security observations

P33-001 P1 integrity blocker remains unresolved; P33-002/003 P2 contract failures remain unresolved. Real container restrictions pass; tampering changes computation inside that container and does not demonstrate an escape. Trusted configured stdio executables are executable host programs, not a sandbox: an allowlisted tool name cannot narrow their OS/filesystem privileges. `env_names` forwarding is explicit; synthetic ambient secret is excluded; no real secrets collected.

Uncertain-death fixture appends one local marker before exiting, no automatic second call occurs and durable resume is blocked. Built-in namespace remains authoritative, disabled entries fail start checks, injection text stays returned evidence without direct dispatch. This does not certify an LLM against semantic injection. Account identity/version/final authorization uniformity, refresh/scopes, concurrent registration, and dependency transitive locking remain unverified or unsupported. No paid API, live provider write/read, private desktop capture, microphone, shared-service start/stop or package install was used.
''')
write('rollback.md', '''# Rollback

No source/protocol/dependency changes to roll back. Remove or archive only this dated evidence directory and its README paragraphs if desired; do not alter original module evidence or other pending audit work. Tests use temporary roots, owned stdio children and generated containers labelled for their disposable server; unregister/reap cleanup is in finally. Do not restore stale production registry entries blindly. Any future repair needs versioned config/skill compatibility rollback and a fresh no-replay/account-identity check. Do not run setup_mcp_runtime.py as a rollback: it is a networked build.
''')
write('codex-findings-reconciliation.md', f'''# Findings reconciliation

Pinned source `{sha}`. New P33-001 (P1), P33-002 (P2), P33-003 (P2) all APPLIES / OPEN; fix SHA none. Map to exact failed tests in failures.md and boundaries.xml; baseline/neighbor retention results in executed-results.jsonl. Existing Phase 3 G4/G5 independently PASS; its explicit health tamper check passes but does not refute P33-001 dispatch tampering. Original 32-row catalog (including 12 user cases) is retained and joined by stable ID in tests.jsonl for the revised 22 cases; original extras are not relabelled executed.

Prior P32-001/P32-002 remain OPEN at the same SHA; Prompt 31 receipt/callback repairs retain their independent evidence, but full acceptance was partial. Prior independent review and Phase 1–8 evidence are accessible; no screenshot used as proof and no blanket reconciliation-complete claim. Source repairs reserved to Claude by the supplied read-only confirmation contract. Follow-up: repair-handoff.md, fresh exact-SHA replay, then unexecuted mandatory gates.
''')
write('verdict.md', f'''# Prompt 33 — NOT READY / BLOCKED

2026-10-19, pinned claude `{sha}`, independent isolated codex-review.

**169 passed / 3 failed** across 172 fresh pytest checks: 94 baseline, 34 living-skill/MCP lifecycle, 36 routing/recovery and 5 passing boundary controls. Boundary failures establish **P33-001 P1** (changed generated source executes without revalidation), **P33-002 P2** (schema-invalid arguments dispatched), and **P33-003 P2** (malformed result accepted). Raw XML and generated-drift-observation.json preserve actual results.

Stopped on P1; no source fixes, live provider writes, installation, merge or deployment. [Findings](failures.md) · [Claude repair handoff](repair-handoff.md) · [All 22 cases](tests.jsonl) · [Run provenance](baseline.json).

Offline Docker compute lifecycle works with fixed author/approval callbacks; no live model/account/full native journey certificate. Launcher repair_required and mandatory account/schema-version/concurrency/memory gates remain BLOCKED. Earlier Prompt 32 P1s remain unresolved. Benchmark is warm generate+AST-screen overhead versus fixed Phase 3 commit, not service latency or improvement. Master contract unavailable; supplied independent read-only reconciliation contract applied. Stop at module boundary; no module 34.
''')

recon = APP / 'artifacts/jarvis-audit/reconciliation/33-2026-10-19-independent-0e3ad47'
recon.mkdir(exist_ok=True)
for name, origin in [('artifact-inventory.md','inventory.md'),('patch-assessment.md','changes.md'),
                     ('unresolved.md','failures.md'),('handoff.md','repair-handoff.md')]:
    content = (OUT / origin).read_text(encoding='utf-8')
    content = re.sub(r'\]\(([^)]+)\)',
        lambda m: '](' + '../../modules/33-mcp-integrations/' + OUT.name + '/' + m[1] + ')', content)
    (recon / name).write_text(content,encoding='utf-8')
(recon / 'review-revisions.json').write_text(json.dumps({'claude':sha,'audit':sha,'fix_sha':None,'prior_phase3':prior},indent=2))
with (recon / 'findings-ledger.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.writer(f);writer.writerow(['finding','priority','status','pinned_sha','fix_sha','test'])
    for ident,priority,number in [('P33-001','P1','013'),('P33-002','P2','005'),('P33-003','P2','006')]:
        writer.writerow([ident,priority,'APPLIES/OPEN',sha,'NONE','JRV-33-'+number])
for name, labels in [('repro-results.jsonl',{'boundaries'}),('legacy-regressions.jsonl',{'baseline','neighbors'}),('cross-pillar-regressions.jsonl',{'living-skills'})]:
    (recon / name).write_text('\n'.join(json.dumps(r) for r in rows if r['run'] in labels)+'\n',encoding='utf-8')
print(json.dumps({'sha':sha,'totals':totals,'runs':summaries,'packet':str(OUT)},indent=2))
