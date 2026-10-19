"""Package observed Prompt 36 evidence without treating blocked gates as passed."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
ROOT = APP.parent
BASE = 'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip() == BASE

def write(name, value): (OUT / name).write_text(value.rstrip() + '\n', encoding='utf-8')
def dump(name, value): write(name, json.dumps(value, indent=2, ensure_ascii=False))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

normal = {}
for path in [*OUT.glob('*.txt'), *OUT.glob('*.xml')]:
    before = sha(path)
    value = path.read_text(encoding='utf-8-sig')
    for source, target in [(str(APP), '%AUDIT_APP%'), ('D:\\Kunals GitHub Repo\\Jarvis\\app', '%INSTALL_APP%'),
                           (os.environ.get('USERPROFILE', 'NO_PROFILE'), '%USERPROFILE%')]:
        for spelling in {source, source.replace('\\', '/'), source.replace('\\', '\\\\')}:
            value = value.replace(spelling, target)
    value = re.sub(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"<>]+', '%USERPROFILE%', value)
    path.write_text(value, encoding='utf-8')
    normal[path.name] = {'original': before, 'saved': sha(path)}
dump('log-path-normalization.json', normal)

results, runs = [], {}
for label in ['baseline', 'before', 'selection-before', 'targeted', 'targeted-final', 'supplemental', 'final-regression']:
    tree = ET.parse(OUT / (label + '.xml')).getroot()
    rows = []
    for case in tree.iter('testcase'):
        skip = case.find('skipped')
        status = 'FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIPPED' if skip is not None else 'PASS'
        rows.append({'id': case.get('name'), 'classname': case.get('classname'), 'status': status,
                     'seconds': float(case.get('time', 0)), 'reason': skip.get('message') if skip is not None else '',
                     'run': label, 'base_sha': BASE, 'evidence': label + '.xml'})
    runs[label] = {s: sum(row['status'] == s for row in rows) for s in ['PASS', 'FAIL', 'SKIPPED']}
    runs[label]['seconds'] = sum(float(s.get('time', 0)) for s in tree.iter('testsuite'))
    results.extend(rows)
final = runs['final-regression']; assert final['FAIL'] == 0
headline = f"{final['PASS']} PASS / 0 FAIL / {final['SKIPPED']} SKIPPED"
write('executed-results.jsonl', '\n'.join(json.dumps(row) for row in results))
dump('baseline.json', {'date': '2026-10-20', 'base_sha': BASE, 'source': 'base + retained P34/P35 proposals + P36 local changes',
     'runs': runs, 'headline_run': 'final-regression', 'overlapping_runs_not_summed': True,
     'baseline_failure': 'JRV-11-007 missing Hermes metadata at isolated path; final read-only wrapper uses verified existing installed 210-row catalog.',
     'peak_test_process_memory': 'NOT MEASURED', 'real_cloud_calls': 0, 'messages': 0, 'training_runs': 0,
     'physical_UI_or_mic': False, 'installs': 0})

paths = ['jarvis/agent_events.py', 'jarvis/tools.py', 'jarvis/skill_store.py', 'jarvis/skill_evolution.py',
         'jarvis/cloud_architect.py', 'tests/test_prompt36_observability.py', 'tests/test_phase01_baseline.py',
         'tests/test_phase03_living_skills.py', 'tests/test_phase05_escalation_demonstration.py']
dump('source-hashes.json', {name: sha(APP / name) for name in paths})
(OUT / 'source.patch').write_bytes(subprocess.check_output(['git', 'diff', '--', *('app/' + name for name in paths)], cwd=ROOT))
dump('source-layers.json', {'base': BASE, 'fix_sha': None,
     'patch_scope': 'Tracked-file diff versus base includes overlapping Prompt 35 tool/cloud/skill repairs. New P36 test file is separately hashed. Do not discard retained changes.',
     'pre_P36_hashes': 'before-source-hashes.json', 'current': 'source-hashes.json',
     'earlier_packets': ['../../35-security/2026-10-20-completion-a9b4ce1', '../../34-dependencies/2026-10-20-completion-a9b4ce1']})

old = {row['id']: row for row in (json.loads(s) for s in (OUT.parent / 'tests.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip())}
dispositions = {
1: ('BLOCKED', 'No ten-command physical voice/end-to-end run. Synthetic helper samples are not command latency.'),
2: ('BLOCKED', 'No ten cold model questions, first-token latency or inference run. First-call helper pair is not model cold start.'),
3: ('BLOCKED', 'Five actual registry calls with mocked read dispatch share real TaskState UUID, distinct call IDs, host monotonic clock and lifecycle rows. All stages including Verify/voice-to-speech are not correlated end-to-end.'),
4: ('PASS', 'Fixed pinned 36fbf3ce source vs current UI/lease functions, same fixtures/runtime, seed-36 randomized pair order, host pressure and hashes captured. Synthetic only.'),
5: ('BLOCKED', 'Measured overhead is reported as cost, not a win; exact accuracy-rise/p95-doubling experiment not executed.'),
6: ('BLOCKED', 'No intermittent flake reproduced. Missing isolated Hermes data is a deterministic environment blocker, resolved for final tests by existing installed metadata.'),
7: ('BLOCKED', 'Synthetic GPU scheduler admission/counter retention run; actual GPU stress/shedding not executed.'),
8: ('PASS', 'Actual tool durations use perf_counter; lifecycle carries monotonic_ns plus clock_id separately from wall-clock at. Five-call monotonic readback captured.'),
9: ('BLOCKED', 'No live streamed model-to-final-verifier journey; explicit refuted skill steps no longer earn verified credit, but global completion/UI proof remains partial.'),
10: ('BLOCKED', 'No 100-action process-memory leak alert implementation/run. Memory lesson DB growth is a separate storage measurement.'),
11: ('PASS', 'Injected locked event/cloud logs degrade diagnosis without duplicate dispatch/consultation; deny policy still enforced. Journal cap preserves old bytes. No new logging-off configuration flag claimed.'),
12: ('PASS', 'All 24 numbered cases retained in coverage denominator, including blocked; pytest runs and scenario catalog reported separately without summing overlaps.'),
13: ('PASS', 'Selected-only no-execution task now retains selected count with zero applied, verified or fallback; alternate executed routes can still count fallback.'),
14: ('BLOCKED', 'Counter-side explicit False readback now records verification_failed and no completed_verified. Global UI/task status under every conflicting verifier route not established.'),
15: ('PASS', 'Reopened SQLite store rejects duplicate selection for same task/skill/event; existing duplicate-finish retention passes.'),
16: ('PASS', 'Independent disposable evaluator/heldout/code tamper rejection tests rerun; comparator does not accept changed heldout/evaluator source.'),
17: ('BLOCKED', 'Model gate/experimental registry guards retained; exact loss-down/heldout-down training checkpoint not produced or evaluated.'),
18: ('PASS', '100 synthetic near-duplicate trajectories normalize to one stored lesson; database bytes and elapsed time captured. General semantic novelty and unlimited retention not proven.'),
19: ('BLOCKED', 'No real matched API/UIA/GUI latency/readback experiment. Fake UI objects and isolated adapter regressions do not substitute.'),
20: ('PASS', 'Privacy-blocked consultation records categorical privacy_blocked with hashed correlation, zero mock sends and no payload/reason text. Tool preflight also records metadata.'),
21: ('PASS', 'Fresh 500 paired warm samples per two synthetic scenarios plus first-call pairs, raw-samples.csv, code/hash/host/seed/variance/CI; no real throughput claim. Historical raw samples not found.'),
22: ('BLOCKED', 'Physical voice during LoRA/DGM, actual p95/cancel latency and VRAM pressure not run; no training or mic activation authorized.'),
23: ('BLOCKED', 'Malformed stored evidence counted explicitly and cannot crash metrics; no complete dashboard status/denominator audit across all UI/report consumers.'),
24: ('BLOCKED', 'New skill/cloud/tool events use bounded metadata; old skill evidence exports sanitized on read. Historical raw logs/other telemetry exports and every sink not migrated or fully certified.')}
cases = []
for number, (status, reason) in dispositions.items():
    ident = f'JRV-36-{number:03}'
    cases.append({'id': ident, 'status': status, 'reason': reason, 'date': '2026-10-20', 'base_sha': BASE,
                  'original_catalog_status': old.get(ident, {}).get('status', 'UNAVAILABLE'),
                  'catalog_join': 'Original scenario retained' if number <= 12 else 'Revised definition replaces differently defined historical generic fault row',
                  'evidence': 'executed-results.jsonl; trace-readback.jsonl; benchmark-provenance.json; memory-growth-readback.json'})
write('tests.jsonl', '\n'.join(json.dumps(row) for row in cases))
coverage = {status: sum(row['status'] == status for row in cases) for status in ['PASS', 'FAIL', 'BLOCKED', 'SKIPPED', 'NOT RUN']}
dump('coverage-summary.json', {'denominator': len(cases), 'statuses': coverage,
     'verdict': 'NOT READY', 'all_required_gates_passed': all(row['status'] == 'PASS' for row in cases),
     'note': 'Scenario acceptance denominator is separate from pytest test counts. Missing evidence is not a pass.'})

write('inventory.md', '''# Prompt 36 inventory — 2026-10-20

Isolated codex-review base a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6 plus retained Prompt 34/35 and new proposed observability changes. review-revisions.json, before-source-hashes.json and source-layers.json distinguish layers; no fix commit invented. User's standing policy authorizes safe fixes and continued work, with cumulative Claude handoff. Root/app AGENTS and supplied reconciliation contract read; master contract unavailable. Original user configuration untouched.

Read current system-map, earlier independent review/security/benchmark records and phase source/tests. Actual telemetry producers/consumers: ToolRegistry / agent_events / execution_contracts / execution_strategy; TaskState and skill memory/store/evolution; cloud_architect; ReasoningBank; evolution evaluator/model gate. Model/voice/UI/background clocks are not uniformly correlated. No new registry/event bus introduced.

Original 36 module catalog: 32 planned IDs; original 001–012 retained, revised 013–024 differ from old generic fault rows. Old originals immutable. Historical independent benchmark aggregate and measurement code found; historical raw per-sample N=500 data not found because original code saved only aggregates. New raw measurements are a fresh replication, not recovered evidence. host-profile.json records runtime/resource provenance without hostname/private roots. No packages/models/services installed or started, real cloud, messages, recordings or training.
''')
write('changes.md', f'''# Local changes and verification

P36-001: SkillStore event evidence now keeps an allowlist of metadata (version, categorical cause/reason, evidence count), never arbitrary readback text or serialized-JSON truncation. Raw failure detail is not written. Metrics safely parse/sanitize old evidence and count malformed records without rewriting historical DBs.

P36-002: explicitly refuted bound tool steps cannot receive completed_verified credit even when a task claims completion/goal_verified. P36-003: selected/no execution means selected only; alternate executed tools still count as fallback. Restart idempotency remains in SQLite unique keys.

P36-004: tool lifecycle/outcome and nested cloud events carry host monotonic_ns/clock_id, with TaskState UUID captured once per registry call via ContextVar. Wall time remains for ordering. P36-005: optional journal OSError cannot block/replay permitted execution or bypass deny policy; storage cap 32 MiB stops append and exposes limited status, without deleting old evidence. P36-006: cloud v2 logs contain decisions, hashed problem identity and payload bytes/digest, not payload/advice/raw reason; blocked privacy/eligibility/duplicate/provider states recorded; 8 MiB cap and OSError degrade diagnosis without retrying consultation.

Baseline 128 pass/1 fail/1 skip: Hermes data missing at isolated path. Original installed 210-row catalog verified and routed read-only in final wrapper; no source install/workaround or expected-xfail. First adverse suite 8 fail/1 pass includes two invalid test fixtures missing a toolkit folder; corrected pinned-source probe with a valid folder independently confirms absent task/monotonic metadata and locked-log dispatch blocking. Six other original failures and separate selected-only failure are genuine. Measurement collector initially missed its old-trace directory; fixed harness, not app.

Updated three explicit legacy assertions for the new privacy/clock schema, preserving dispatch, payload allowlist, counter and idempotency checks. Targeted final 59 pass. Final relevant: **{headline}**. Supplemental evaluator/GPU admission results are separate in baseline.json; do not sum overlapping runs. No dependency/config/UI-artwork change, screenshot, commit, merge or deployment.
''')
write('trace-schema.md', '''# Trace schema and trust

Agent event version 1 retains at, event, call_id and allowlisted tool/metadata; adds monotonic_ns (integer nanoseconds) and clock_id (opaque process clock domain). task_id is optional host TaskState UUID captured in registry call context, never copied from model metadata. Call ID correlates tool.started/completed/failed/outcome; tool.completed means dispatch returned, not goal verified. Durations use perf_counter or same-clock monotonic differences; do not subtract wall dates or mix clock domains across restarts.

Cloud decision version 2: wall time, monotonic clock fields, optional scoped task_id, problem_id_hash and categorical decision. Sent records add payload_bytes/sha256 only. No payload, raw reasons, advice, credential, filename or source content in these new rows. Skill event metadata includes bounded integer version/evidence_count and categorical cause/reason. Raw historical evidence is sanitized on metrics read, not erased from storage.

Trace readback is five actual registry calls / actual TaskState with mocked read dispatch and no file access by tools. It does not cover STT/cleanup/model/DAG/Verify/memory/UI/speech/background request IDs end-to-end. Existing outcome authority and global UI truth remain separate release gates. Logging loss cannot grant approval or verification; missing records may block promotion/diagnosis.
''')
write('failures.md', '''# Remaining blockers and review risks

P36-R1: completed_verified telemetry now rejects explicit step refutation, but still relies on host task/checkpoint history for other cases. Direct historical/host event insertion and model/self-asserted or stale goal_verified provenance need uniform independent verifier identity/version binding. Global TaskState/UI completion is not repaired by a counter fix (case 014 remains BLOCKED).

P36-R2: no universal trace across voice/STT/router/model/Verify/UI/speech and background workers; no ten warm commands, cold first tokens, physical voice-under-training or 100-action process leak alert. Cannot turn helper timings into throughput or responsiveness claims.

P36-R3: caps/locks are per process; no cross-process logging/retention/backpressure/crash-fsync stress. Status flags exist but every UI/dashboard consumer has not been audited. Old raw cloud/skill logs remain local and require an explicitly reviewed migration/export policy; do not silently delete them. All-sink privacy/case 024 remains blocked.

P36-R4: original raw N=500 samples unavailable (aggregate/code present); fresh samples are separate. No real matched API/UIA/GUI or actual accuracy/p95 tradeoff or loss/heldout training experiment. CI is a normal approximation for paired mean of serial synthetic samples, not population/median/p95 certification.

Initial Hermes baseline failure is a deterministic isolated-data issue, not a flake. Final wrapper reads verified existing install metadata; final assertion is not waived. Skipped physical/runtime checks remain explicit. Prior P31–P35 release gates remain in cumulative handoff. No final executed regression failure may be called healthy.
''')
write('cross-pillar-matrix.md', '''# Cross-system retention

| Seam | Fresh evidence | Remaining limit |
|---|---|---|
| Task/tool/skill | Five-call trace, SQLite restart/counters, refuted step, selected-only, malformed evidence | Uniform end-to-end verifier authority/UI completion |
| Pillar A / MCP | Living skills, Prompt 33 identity/contracts, skill selection with installed metadata, Prompt 35 guards | Every worker/version/tenant trace not bound |
| Pillar B / exploration | 100 near-duplicate trajectories -> one lesson; DB growth measured | Semantic novelty, caches/contradictions and live OpenViking trace |
| Pillar C DGM / EEVEE | Independent protected gate and separate evaluator/heldout tamper checks | Actual performance comparison on all foreground/background loads |
| Pillar D AZR | Oracle/registry/budget/lease regressions, GPU admission fixtures | No real training loss/heldout/VRAM/preemption measurement |
| API/structured/GUI | Existing adapter and desktop fake/readback regressions | No matched native endpoint latency comparison |
| Cloud | Metadata-only blocked/sent/returned decisions; recording fake only | Caller provenance and all-sink privacy remain open |
| Show Me Once / legacy voice | Consent/security/desktop and routing guards retained; synthetic snapshot benchmark | No real mic, recording, UIA COM, DPI or UAC acceptance |
| Recovery / dependencies | Task recovery, no-replay, P34 authorization and P35 boundaries retained | Every producer's monotonic/identity domain and crash logs not certified |

Exact outcomes/skip reasons in executed-results.jsonl; overlapping runs not summed. Tool contexts tested without fresh privileged account writes or inference.
''')
write('compatibility.md', '''# Compatibility and operational limits

No dependency, model, launcher/runtime-manifest/config change. Version-1 agent readers tolerate added clock/task fields; cloud metadata rows explicitly version 2. Three regression assertions now expect metadata counts/digests and clock fields instead of raw text/payload. Existing approvals, actual fake outbound payload, counter idempotency and dispatch validation remain asserted.

Logging unavailable/capped: functionality proceeds once under the same policy and approval checks with diagnosis degraded; no replay. Missing outcomes cannot establish verification or trusted promotion. No automatic log deletion/rotation. Old raw telemetry is not migrated or claimed clean. Invalid legacy event JSON yields categorical metrics and invalid_evidence_count rather than a crash.

Hermes/skills roots read from original install where explicitly routed, not copied. Isolated launcher --check remains repair_required (missing local env/assets; unavailable Docker/Ollama endpoints). Physical/runtime skip reasons retained. Whole original environment was not recreated. No UI images applicable.
''')
write('security.md', '''# Privacy, authorization and truthful status

Synthetic canary in skill evidence/failure and cloud problem ID/payload is absent from new metadata rows. Unknown/raw evidence fields are dropped; old evidence exports sanitize to categorical metadata. Lifecycle envelope cannot be overwritten by extra model metadata. Host task identity is captured, not accepted from event arguments. Clock domain separates process durations from wall dates.

Locked journals and size limits do not override deny policy or repeat dispatch/consultation. Caps preserve existing bytes; no user-file deletion. Cloud fake transport tests verify sent bytes separately while production logs retain only digest/size. This does not solve P35 arbitrary semantic provenance, all telemetry export privacy or malicious native-code sandboxing.

All scenario statuses remain in coverage-summary.json denominator; 24-case acceptance is distinct from many pytest checks. NOT READY with blocked cases is required even when relevant tests pass. No private screen/cloud payload, real message, recording, install or training performed. Exported root paths normalized with before/after hashes; no unrelated desktop or account data captured.
''')
write('rollback.md', '''# Reproduction and rollback

No production deployment, package/model migration or database schema migration occurred. New stored rows use bounded metadata; raw evidence is intentionally not recoverable from new logs. Existing historical files remain; no destructive migration/rollback performed or claimed. Reverse only accepted Prompt 36 code hunks in a review branch if needed, preserving Prompt 34/35 work and immutable evidence. source.patch is cumulative versus base at overlapping files; consult source-layers.json and prior packet before applying/reversing.

run_regressions.py runs current audited source with existing installed dependency/metadata roots read-only; tests/test_prompt36_observability.py is the new suite. measure.py writes only owned temporary fixtures and this packet, reads pinned source with git show, and saves raw CSV. Never run the original historical benchmark writer directly: it overwrites its old output path. No setup/install script is needed to reproduce safe fixtures; unavailable live checks stay blocked.
''')
write('codex-findings-reconciliation.md', '''# Finding reconciliation

| Finding | Reproduction | Local repair / final evidence |
|---|---|---|
| P36-001 P1 skill evidence privacy/JSON | Raw canary / long event JSON / corrupt historical row | Metadata-only writes, safe historical export, invalid counter; new tests and final XML |
| P36-002 P1 false verified attribution | Completed task with refuted bound step | Failed category, no verified count; global UI/authority still open |
| P36-003 P2 selection misclassification | selection-before.xml | No execution => selected only; alternate route fallback retained |
| P36-004 P2 missing task/monotonic correlation | Corrected pinned valid-folder readback | ContextVar host TaskState/clock fields; five-call trace-readback.jsonl |
| P36-005 P2 telemetry failure blocks tool | Corrected pinned locked-journal readback | Optional OS failure/size cap, policy retained, once-only dispatch |
| P36-006 P1 cloud telemetry payload/missing deny decision | before.xml / recording-fake cloud | v2 metadata, privacy-blocked reason, no payload; once-only consult under log loss |

Fix SHA is NONE (uncommitted proposal); base/hash/layer provenance is explicit. Existing IR-001/IR-002 benchmark comparisons are replicated on same synthetic shapes with raw data newly saved; old N=500 raw samples unavailable, not fabricated. Prior audit originals and Prompt 34/35 findings stay intact. Original 001–012 scenario IDs retained; revised 013–024 are not equivalent to older same-number generic fault rows.
''')
write('verdict.md', f'''# Prompt 36 — safe local work complete; release NOT READY

2026-10-20, isolated codex-review base `{BASE}` plus retained P34/P35 and new local observability proposals. Final relevant regression: **{headline}**. Supplemental evaluator/GPU fixtures: **{runs['supplemental']['PASS']} PASS / {runs['supplemental']['FAIL']} FAIL / {runs['supplemental']['SKIPPED']} SKIPPED**, separate and not automatically added. Targeted final: 59 PASS.

Fixed metadata privacy/JSON integrity, explicit false-verification attribution, selection-only counters, host task/monotonic correlation, optional bounded logging and categorical cloud decisions. Fresh 500 warm pairs per synthetic UI/lease scenario plus first-call pairs saved as 2,004 raw observations; variance/paired-mean CI and host profile included. These are helper safety overheads, not end-to-end latency, throughput, model accuracy or responsiveness evidence.

24-case denominator: {coverage}. Blocked cases keep overall NOT READY. No real messages/cloud/recording/training/installation/deployment. [Cases](tests.jsonl) · [Changes](changes.md) · [Trace schema](trace-schema.md) · [Blockers](failures.md) · [Cumulative Claude handoff](../../../../../docs/CLAUDE_HANDOFF.md).
''')

recon = APP / 'artifacts/jarvis-audit/reconciliation/36-2026-10-20-completion-a9b4ce1'; recon.mkdir(exist_ok=True)
for name, report in [('artifact-inventory.md', 'inventory.md'), ('patch-assessment.md', 'changes.md'),
                     ('unresolved.md', 'failures.md'), ('handoff.md', 'verdict.md')]:
    (recon / name).write_text('See [report](../../modules/36-observability/' + OUT.name + '/' + report + ').\n', encoding='utf-8')
(recon / 'review-revisions.json').write_bytes((OUT / 'review-revisions.json').read_bytes())
with (recon / 'findings-ledger.csv').open('w', newline='', encoding='utf-8') as handle:
    writer = csv.writer(handle); writer.writerow(['finding', 'status', 'base', 'fix'])
    for i in range(1, 7): writer.writerow([f'P36-{i:03}', 'FIXED bounded scope', BASE, 'local source hashes/patch'])
    for i in range(1, 5): writer.writerow([f'P36-R{i}', 'BLOCKED/UNVERIFIED', BASE, 'NONE'])
for name, run in [('repro-results.jsonl', 'before'), ('legacy-regressions.jsonl', 'baseline'), ('cross-pillar-regressions.jsonl', 'final-regression')]:
    (recon / name).write_text('\n'.join(json.dumps(row) for row in results if row['run'] == run) + '\n', encoding='utf-8')
print(json.dumps({'final': final, 'supplemental': runs['supplemental'], 'coverage': coverage, 'cases': len(cases)}))
