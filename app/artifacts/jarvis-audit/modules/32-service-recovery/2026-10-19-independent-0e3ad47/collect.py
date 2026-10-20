"""Build Prompt 32 evidence without changing application or prior audit files."""
import ast
import csv
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
import types
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
BASE = next(p for p in OUT.parents if (p / 'main.py').is_file() and (p / 'jarvis').is_dir())
ROOT = BASE.parent
sys.path.insert(0, str(BASE))
SHA = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert SHA == '0e3ad4706b5120e5d0479d34333e5faa7b0931b5'
DATE = '2026-10-19 IST'
RECON = BASE / 'artifacts/jarvis-audit/reconciliation' / ('32-' + OUT.name)

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def dump(path, value):
    write(path, json.dumps(value, indent=2) + '\n')

def doc(name, text):
    write(OUT / name, f'# Prompt 32 independent audit — {DATE}\n\n{text.strip()}\n')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_xml(path):
    rows = []
    for case in ET.parse(path).iter('testcase'):
        issue = next((case.find(k) for k in ('failure', 'error', 'skipped') if case.find(k) is not None), None)
        rows.append({'id': case.get('classname') + '::' + case.get('name'),
                     'status': 'PASS' if issue is None else 'SKIPPED' if issue.tag == 'skipped' else 'FAIL',
                     'seconds': float(case.get('time', 0)), 'evidence': path.name,
                     'message': issue.get('message', '') if issue is not None else ''})
    return rows

def counts(rows):
    return {s: sum(r['status'] == s for r in rows) for s in ('PASS', 'FAIL', 'SKIPPED')}

runs = {p.name: read_xml(p) for p in OUT.glob('*.xml')}
summary = {name: counts(rows) for name, rows in runs.items()}
dump(OUT / 'baseline.json', {'pin': SHA, 'date': DATE, 'branch': 'codex-review', 'python': sys.version,
    'executable': sys.executable, 'platform': platform.platform(), 'runs': summary,
    'source_fix_sha': None, 'memory_during_baseline': 'NOT MEASURED; per-case timing retained in XML',
    'full_relevant_release_regression': 'NOT RUN after unresolved P1 stop gate',
    'scope': '72 selected recovery baseline checks; explicit native-owned-process and synthetic-secret failures',
    'master_contract': 'unavailable in repository and exact Downloads companion path',
    'reconciliation_contract': '10_CODEX_FINDINGS_RECONCILIATION.md reserves repairs for Claude; Codex read-only confirmation',
    'user_override': 'explicitly requested start 32 despite incomplete Prompt 31 acceptance',
    'original_config': 'existing user modification preserved, not copied into audit worktree'})
write(OUT / 'executed-tests.jsonl', ''.join(json.dumps(row) + '\n' for rows in runs.values() for row in rows))
source_paths = ['jarvis/launcher.py', 'jarvis/recovery.py', 'jarvis/task_state.py', 'jarvis/task_recovery.py',
    'jarvis/harness_process.py', 'jarvis/runtime_health.py', 'jarvis/gmail_writes.py', 'jarvis/mcp_bridge.py',
    'jarvis/approval_receipt.py', 'main.py', 'jarvis_bootstrap.py', 'config/runtime_manifest.json',
    'Start Jarvis.cmd', 'Stop Jarvis.cmd']
dump(OUT / 'source-hashes.json', {p: digest(BASE / p) for p in source_paths})
prior_dirs = [BASE / 'artifacts/jarvis-audit/codex-independent-review',
              BASE / 'artifacts/jarvis-audit/modules/31-ui-island-pip/2026-10-19-independent-0e3ad47']
prior = {p.relative_to(BASE).as_posix(): digest(p) for directory in prior_dirs for p in directory.rglob('*')
         if p.is_file() and '__pycache__' not in p.parts}
prior.update({p.relative_to(BASE).as_posix(): digest(p) for p in OUT.parent.iterdir() if p.is_file()})
dump(OUT / 'prior-artifact-hashes.json', prior)

# Pure healthy-service positive-control timing. No worker starts, repairs or network.
from jarvis.recovery import Watchdog
before_sha = 'ddf3247fd3d5ee6b151287c6cba358e8707090c6'
before_source = subprocess.check_output(['git', 'show', before_sha + ':app/jarvis/recovery.py'], cwd=ROOT, text=True)
same = before_source == (BASE / 'jarvis/recovery.py').read_text(encoding='utf-8')
old_module = types.ModuleType('_prompt32_previous_recovery')
exec(compile(before_source, '<pinned-prior-recovery>', 'exec'), old_module.__dict__)
def make(cls):
    dog = cls(lambda *args: None)
    for n in range(5):
        dog.register('fixture-' + str(n), lambda: True, lambda: False)
    return dog
dogs = {'before': make(old_module.Watchdog), 'after': make(Watchdog)}
for _ in range(20):
    for dog in dogs.values():
        dog.tick()
samples = {key: [] for key in dogs}
for n in range(300):
    for key in (('before', 'after') if n % 2 else ('after', 'before')):
        start = time.perf_counter_ns()
        dogs[key].tick()
        samples[key].append((time.perf_counter_ns() - start) / 1e6)
metrics = []
for key, values in samples.items():
    tracemalloc.start()
    dogs[key].tick()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    metrics.append({'revision': before_sha if key == 'before' else SHA, 'n': len(values),
                    'p50_ms': statistics.median(values), 'p95_ms': sorted(values)[int(len(values)*.95)],
                    'peak_traced_bytes': peak})
with (OUT / 'benchmarks.csv').open('w', encoding='utf-8', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(metrics[0]))
    writer.writeheader()
    writer.writerows(metrics)
dump(OUT / 'resource-profile.json', {'scope': 'synthetic five-healthy-service Watchdog.tick only; not restart/readiness latency',
    'recovery_source_identical_between_revisions': same, 'metrics': metrics, 'samples_ms': samples,
    'conclusion': 'No recovery source change or end-user improvement claim; timing differences are sampling variance.'})

# Service registrations are source-derived, including the three literal loop registrations.
tree = ast.parse((BASE / 'main.py').read_text(encoding='utf-8'))
registrations = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'register' and node.args:
        if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'watchdog':
            registrations.append({'name': node.args[0].value if isinstance(node.args[0], ast.Constant) else '<worker loop: Action/Question/Speech>',
                                  'line': node.lineno, 'source': 'main.py'})
dump(OUT / 'service-registrations.json', registrations)
write(OUT / 'service-graph.mmd', '''flowchart TD
  Bootstrap[jarvis_bootstrap: entrypoint validation] --> Launcher[launcher: session and heartbeat supervision]
  Launcher --> Owned[OwnedApplication: native handle tracking]
  Owned --> App[main.App]
  App --> Watchdog[Watchdog: enabled health/repair callbacks]
  Watchdog --> Threads[Action / Question / Speech threads]
  Watchdog --> Mic[Requested microphone]
  Watchdog --> Transports[UIA / Browser / Harness / media]
  Watchdog --> Optional[Cognition / vault index / anticipation / realtime / previews]
  Watchdog --> Models[Ollama / configured models]
  App --> TaskState[TaskState v1 checkpoints: context, not replay queue]
  TaskState --> Writes[Gmail journal and external-write uncertainty]
  Pipeline[Offline evolution and AZR pipelines] -. incomplete common lifecycle .-> Watchdog
''')
dump(OUT / 'checkpoint-schema.json', {'scope': 'source-derived description, not a new validator',
    'path': '.jarvis-runtime/state/task_state.json', 'version': 1,
    'envelope': {'current': 'null or current task object', 'history': 'list, bounded to 20 by start()'},
    'task': ['task_id', 'goal', 'kind', 'project', 'status', 'stage', 'started_at', 'updated_at', 'checkpoints', 'result'],
    'optional': ['plan', 'plan_revisions', 'dag', 'failures', 'uncertain_external_writes'],
    'commit': 'write same-directory temporary; flush/fsync; os.replace; bounded Windows sharing-error retries',
    'restart': 'running -> interrupted; no automatic execution from saved state',
    'uncertainty': 'uncertain_external_write adds action/target; external_write_verified removes matching marker; cannot finish completed while pending',
    'read_validation': 'version == 1 and history list; full schema/migration acceptance is incomplete'})

cases = [
 ('BLOCKED', 'No complete supervised startup; isolated readiness repair_required for missing runtimes/assets.'),
 ('BLOCKED', 'Generic thread restart clears queued effects in baseline; no actual speech-model worker kill/restart journey.'),
 ('BLOCKED', 'Read retry fixtures pass; no actual browser-worker kill during read.'),
 ('PASS', 'Fake provider accepts send then transport times out: journal rejects second invocation; one fake POST. No real send or physical worker crash.'),
 ('FAIL', 'P32-001: matching-session heartbeat with sibling PID is attached; real native stop terminates that sibling fixture.'),
 ('BLOCKED', 'Readiness fixture probes cover missing dependencies/timeouts; exact missing manifest-entry scenario not independently executed.'),
 ('BLOCKED', 'Docker was available in probe; core-usability acceptance with unavailable optional Docker not executed.'),
 ('BLOCKED', 'Model repair cooldown/pending fixtures pass; complete late-Ollama startup acceptance unverified.'),
 ('BLOCKED', 'Watchdog has bounded backoff delay but no finite circuit-open budget; full crash-loop acceptance incomplete.'),
 ('FAIL', 'P32-001 affects OwnedApplication.terminate used by stop; unrelated sibling fixture dies after wrong heartbeat PID attachment. Original Stop CMD not executed.'),
 ('FAIL', 'P32-002: direct repair records and launcher startup exception retain synthetic secret verbatim.'),
 ('PASS', 'TaskState atomic-commit, real Windows reader-lock, checkpoint restart and uncertain-write fixture regressions pass; not a machine-power-loss trial.'),
 ('BLOCKED', 'No crash injection at skill sidecar/SQLite trust-promotion seam; prior same-SHA skill tests are component evidence only.'),
 ('BLOCKED', 'No generated MCP server crash/read restart journey in this packet.'),
 ('BLOCKED', 'MCP timeout source refuses automatic retry; write-after-dispatch server-crash acceptance not executed.'),
 ('BLOCKED', 'Desktop exploration requires a verified isolated environment; no explorer UI-step crash trial.'),
 ('BLOCKED', 'Prior same-SHA lab retention tests exist; no new mutation-process crash injection during active evaluation.'),
 ('BLOCKED', 'Prior lease/admission and checkpoint fixtures do not establish real GPU cancellation and foreground responsiveness.'),
 ('BLOCKED', 'No cloud restart-after-uncertain-consultation recovery test; no real provider request.'),
 ('BLOCKED', 'Prompt 31 unique receipts pass at same SHA; complete UI-process restart/stale-consent journey not executed.'),
 ('BLOCKED', 'All optional workers not activated for shutdown; core ownership defect already fails.'),
 ('NOT RUN', 'Partial migration/old-schema transactional startup acceptance not executed before P1 stop gate.')]
rows = [{'id': f'JRV-32-{n:03}', 'status': status, 'reason': reason, 'sha': SHA, 'date': DATE,
         'scope': 'explicit fixture/component outcome only; not complete live acceptance'} for n, (status, reason) in enumerate(cases, 1)]
write(OUT / 'tests.jsonl', ''.join(json.dumps(row) + '\n' for row in rows))
catalog = {r['id']: r for r in (json.loads(line) for line in (OUT.parent / 'tests.jsonl').read_text(encoding='utf-8').splitlines() if line.strip())}
write(OUT / 'catalog-join.jsonl', ''.join(json.dumps({'current': row, 'prior': catalog.get(row['id']),
    'semantics': 'original retained user case' if n < 12 else 'revised targeted case; do not inherit same-ID historical semantics'}) + '\n' for n, row in enumerate(rows)))

doc('inventory.md', f'''Pinned **{SHA}** in the existing isolated `codex-review` worktree. User explicitly requested starting Prompt 32 despite incomplete Prompt 31 acceptance; that request changes the order, not the earlier readiness verdict. No application source change. The original user's modified config is untouched. [Environment/results](baseline.json), [source hashes](source-hashes.json), [executed tests](executed-tests.jsonl), [catalog join](catalog-join.jsonl).

Actual paths: jarvis_bootstrap.py → launcher.preflight/prepare_runtime/run → main.App → registered Watchdog callbacks. OwnedApplication holds the venv redirector Popen and optionally a heartbeat-supplied native process handle. TaskState v1 stores context/checkpoints, not an effect replay queue. Gmail uncertainty uses gmail_writes.py pending journal plus TaskState markers. MCP bridge timeouts explicitly refuse automatic retry. RuntimeHealth's metadata is separate from behavioral readiness.

Read app/AGENTS.md, Prompt 32, prior system map/phase evidence and independent recovery report, current source/manifest/start-stop CMDs, and actual registered services. Readiness and live behavior are different. [Source registrations](service-registrations.json), [service graph](service-graph.mmd), [checkpoint schema](checkpoint-schema.json).

Historical module-root packet contains 32 NOT RUN rows and remains unchanged. New revised cases retain original IDs 001–012; targeted 013–022 have revised semantics. Master contract remains unavailable; companion reconciliation reserves source repairs for Claude. Two P1s trigger the mandatory STOP gate; no Prompt 33 execution.''')
doc('failures.md', '''**P32-001 — P1 / APPLIES: heartbeat PID can retarget stop outside the launched process tree.** session_heartbeat checks matching session and positive integer PID only. OwnedApplication.attach calls OpenProcess on that PID without proving it is the launched child or its descendant/known job member, nor checking expected creation time. terminate then calls TerminateProcess on the attached handle.

Real Windows reproduction launches two hidden, independent Job-owned python trees: application fixture and sibling fixture. A matching synthetic session with the sibling PID passes the predicate. attach accepts it; terminate stops the sibling. The ordinary stop positive control preserves the sibling. Evidence: final-targeted.xml/txt and owned-process-trace.json (final replay trace). All touched PIDs are test-created; no user application or actual Jarvis process was targeted. The hostile/stale heartbeat is injected at the file-parsing/identity seam, not proof of a remote attacker path. Native wrong-process termination itself is real.

**P32-002 — P1 / APPLIES: repair records persist unscreened exception contents.** recovery.record writes str(message)[:1000] directly. launcher.run concatenates arbitrary exception text before calling it; main.App subsequently reads repairs.jsonl into the transcript. Two direct canary records plus one injected startup failure retain synthetic API-key/Bearer content. These are three failing assertions for one root cause. Bootstrap also logs exception text directly; it needs review as a separate sink, but no new bootstrap execution failure is claimed.

Baseline: 72 PASS. First boundary reproduction: 4 FAIL. Final targeted run: 5 PASS / 4 FAIL (ordinary ownership control, fake Gmail/WhatsApp uncertain-write and cancellation/restart fixtures pass). Duplicate runs do not create additional unique defects. No repair/fix SHA. Full relevant release regression and further live fault trials stop here under the P1 gate.''')
doc('changes.md', '''No application source, dependencies, configuration, manifest, worker or launch/stop script changed. Added an owned-process/secret fault-injection fixture, an ordinary ownership positive control, precise process/readback trace, selected no-replay tests, source/old-evidence hashes, service/checkpoint descriptions, paired synthetic profiles and reports. README/current recovery-guide notes distinguish failing current evidence from historical ownership claims. No visible UI change or new image. No installs, source repair, auto-merge or deployment.''')
doc('cross-pillar-matrix.md', '''| Seam | Evidence | Limit |
|---|---|---|
| Supervisor ↔ owned worker stop | real two-tree stop injection FAIL; normal stop control PASS | P32-001 unresolved |
| Repair exception ↔ disk/transcript | real local repair file readback FAIL | P32-002 unresolved |
| TaskState ↔ external account write | fresh fake Gmail accepted-timeout and WhatsApp uncertainty checks PASS | no account/process-send trial |
| DAG ↔ cancellation/restart | fresh Phase 8 uncertain-write restore fixture PASS | no UI-worker restart acceptance |
| Speech/mic/GPU ↔ recovery | selected baseline and same-SHA Prompt 31 fixtures | real foreground contention/worker restarts unverified |
| Skill/MCP/explorer/DGM/AZR lifecycle | source inventory plus earlier same-SHA component results | no complete optional-worker health/cancel/cleanup graph |
| SQLite/vault/migrations | checkpoint baseline only | sidecar/SQLite/migration crash acceptance unverified |
| API ↔ GUI fallback after uncertain write | earlier same-SHA code-first fixtures; fresh journal check | complete cross-route crash acceptance unverified |

The preceding Prompt 31 packet on the identical SHA has 642 PASS /13 SKIPPED in its selected regression, including seven-mechanism seams. It is referenced as existing same-source evidence, not a new Prompt 32 run or full recovery certification. Feature ON/OFF and live checks remain incomplete; no new claims are inferred from an old PASS.''')
doc('compatibility.md', '''Existing Windows Python/runtime/version is in baseline.json. No install or environment/model/database copy. python -m jarvis.launcher --check ran read-only: inspect launcher-check.txt. Isolated runtimes/assets remain missing; Docker and Ollama local health were available; Groq inference was not live tested. Readiness is not capability acceptance.

Start/Stop CMD paths quote %~dp0 and use hidden pythonw/pyw launch. They were inspected, not run against a user's live instance. No name-based kill was used in this audit. Actual ownership fencing still fails P32-001 despite static quoting correctness.

Watchdog retries use exponential backoff capped at 300 seconds; the registry has no finite circuit-open attempt budget. Supervisor delay is capped but the crash loop is not a finite retry budget. Optional pipeline services are not all independently registered. Full startup/Docker-degraded/late-Ollama/migration/physical audio/optional-worker shutdown acceptance remains BLOCKED or NOT RUN.''')
doc('security.md', '''Only two pairs of test-created hidden Windows Job trees were touched across reproductions/control. Native process operations were through exact Popen/Windows handles. owned-process-trace.json records roles, PIDs, creation times, before/after liveness and final Popen cleanup; Job closure reaps their children. No actual user app, production Jarvis, account, credential, private recording or shared service was terminated or modified.

P32-001 shows a real wrong-process stop under an injected matching-session heartbeat. The test does not establish who can write that heartbeat in deployment. P32-002 uses explicit synthetic canaries only; no real secret was printed or uploaded. Fake account tests record exactly one accepted send and reject uncertain retries. Zero unauthorized side effects cannot be claimed for supervisor ownership because the sibling fixture was incorrectly terminated.

No cloud inference, package/model install, system setting mutation or automatic uncertain action replay. Repair-log copies may appear in transcript; no comprehensive privacy claim. Source repair is reserved for Claude by the companion reconciliation contract.''')
doc('rollback.md', f'''No application repair is installed, so no production rollback. Keep this dated packet, originals and original config. Source pin {SHA}; no fix SHA. Do not reset claude or blindly apply patches. From app/, using the existing original Python interpreter:
```powershell
python -m pytest tests/test_recovery.py tests/test_launcher_readiness.py tests/test_runtime_health.py tests/test_task_state.py tests/test_task_recovery.py tests/test_model_recovery.py tests/test_everyday_runtime.py tests/test_phase01_baseline.py -q
python -m pytest artifacts/jarvis-audit/modules/32-service-recovery/{OUT.name}/test_recovery_boundaries.py -q
python -m jarvis.launcher --check
```
Boundary tests are expected to fail on the pinned source. Run future reproductions from a fresh copied packet and new XML/output directory so process traces do not overwrite this final trace. Test process cleanup is explicit in finally blocks and limited to spawned Job/Popen handles; never substitute a name-based cleanup command.''')
doc('codex-findings-reconciliation.md', f'''| Finding | Current state | Source / proof | Follow-up |
|---|---|---|---|
| P32-001 | APPLIES / P1 | {SHA}; final wrong-sibling termination FAIL | Claude ownership proof before handle attachment/termination; independent recheck |
| P32-002 | APPLIES / P1 | {SHA}; three secret persistence assertions FAIL | Claude metadata-safe logger and sink review; independent artifact check |
| P31-001 | FIXED at prior reviewed callback boundary | 1dd3e9c; same-SHA Prompt 31 packet | not reopened by this audit |
| P31-002 | FIXED at prior receipt replay boundary | 0e3ad47; same-SHA Prompt 31 packet | complete UI restart consent acceptance still unverified |
| IR-001/002/003/004 | prior narrow fixes retained | original independent checkpoint/repair; no new dedicated full rerun here | no complete recovery certificate |

Original independent base 36fbf3c, repair 32fdbfe, evidence bc71fb7; current source SHA preserved. Old reports and module-root packet are hashed and unchanged. No new fix SHA exists. Original baseline counts and case rows are not invented from planned IDs.''')
doc('repair-handoff.md', '''P32-001 proposal (not applied): establish trusted child ownership independently of heartbeat contents. Accept only the actual spawned PID or a verified descendant/job member with pinned creation identity, retain a handle after that proof, and reject unrelated or stale/mismatched identities before obtaining termination authority. Preserve Windows venv redirector compatibility. Prefer launching the application tree inside an ownership fence; never kill by executable name. Re-run wrong-PID, stale/PID-reuse, normal redirected startup, Stop/Quit and unrelated same-name process cases.

P32-002 proposal (not applied): use fixed error categories or a bounded privacy-safe serializer before every repairs.jsonl and transcript sink, including launcher/bootstrap exception paths. Scan before truncation; preserve useful service/error class without raw user content/tokens/URLs. Bootstrap must retain its independence if package imports are damaged. Re-run canaries in real output files, multiline/oversized cases and normal repair diagnostics.

Then finish circuit-breaking budgets, optional-worker registration/health/cancellation, durable uncertainty across cloud/API/GUI paths, state migrations and complete live startup/audio/restart acceptance. The Codex companion reconciliation requires read-only confirmation; implementation is reserved for Claude. No code patch is asserted verified here.''')
doc('recovery-transcripts.md', '''Native ownership before/after is in owned-process-trace.json: two same-name python.exe trees with distinct roles/creation times; matching-session sibling PID accepted; both application and sibling not alive after application stop; test-owned cleanup complete. This is the final targeted replay trace; initial boundary XML/log remains separately retained.

Log privacy before: synthetic API-key/Bearer content passed through recovery.record and the real launcher exception branch. After: parsed repairs.jsonl still contains the canary. Expected omission assertions fail. No real user content.

Exact authored fixture file outputs are preserved in [API-key sample](synthetic-api-key-repairs.jsonl), [Bearer sample](synthetic-bearer-repairs.jsonl), and [launcher exception sample](synthetic-launcher-repairs.jsonl). These three output-export reruns are duplicates of the original privacy assertions, not new root causes. repair-output-readback.xml/txt records that export/check step.

No-replay journey: fake Gmail provider accepts one POST then raises timeout. Durable Gmail journal/TaskState retains uncertainty; another invocation raises instead of posting again. WhatsApp fake transport timeouts and DAG running-write restore likewise refuse replay. See precise test IDs and assertions in final-targeted.xml/txt. These are synthetic providers with actual local state, not real account sends.''')
summary_text = '\n'.join(f'- `{name}`: {value}' for name, value in summary.items())
doc('verdict.md', f'''**NOT READY / BLOCKED — Prompt 32 started and stopped at two confirmed P1 findings. Prompt 33 NOT STARTED.**

Pin **{SHA}**, isolated codex-review. **P32-001:** heartbeat PID attachment can retarget stop to a sibling outside the launched application tree; real native test used only disposable Job-owned processes. **P32-002:** repair logs persist synthetic secrets verbatim, including through startup exception handling.

Fresh runs:

{summary_text}

Four failing assertions represent two root causes, not four independent defects. Normal-stop and account/DAG no-replay controls pass. No source repair or fix SHA; the supplied reconciliation reserves implementation for Claude. Prior Prompt 31 limits remain, although the user explicitly authorized starting this module.

Launcher readiness is separately recorded and remains repair_required for absent isolated assets. Full relevant release acceptance and additional live/optional-worker fault trials were NOT RUN after the P1 gate. No actual user process/account action, installation, deployment or automatic merge. Required artifact packet complete; module acceptance is not complete.''')

RECON.mkdir(parents=True, exist_ok=True)
for name, text in {'artifact-inventory.md': 'Old module and prior independent/Prompt31 evidence hashes are in the new packet.',
 'patch-assessment.md': 'No blind patches or application repairs. Two current source boundaries reproduced; source repair reserved for Claude.',
 'unresolved.md': 'P32-001 ownership and P32-002 repair privacy remain P1. No fix SHA; full live recovery acceptance incomplete.',
 'handoff.md': 'Read Prompt32 repair-handoff.md, preserve normal-stop/no-replay behavior, implement narrowly on Claude, then independently reverify exact resulting SHA.'}.items():
    write(RECON / name, '# Prompt 32 reconciliation\n\n' + text + '\n')
dump(RECON / 'review-revisions.json', {'pin': SHA, 'source_fix_sha': None, 'date': DATE})
with (RECON / 'findings-ledger.csv').open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(['finding', 'severity', 'pin', 'fix_sha', 'status', 'evidence'])
    writer.writerow(['P32-001', 'P1', SHA, '', 'APPLIES_FAIL', 'final-targeted.xml; owned-process-trace.json'])
    writer.writerow(['P32-002', 'P1', SHA, '', 'APPLIES_FAIL', 'final-targeted.xml; repair file canaries'])
for name, key in [('repro-results.jsonl', 'final-targeted.xml'), ('legacy-regressions.jsonl', 'baseline.xml'),
                  ('cross-pillar-regressions.jsonl', 'final-targeted.xml')]:
    write(RECON / name, ''.join(json.dumps(row) + '\n' for row in runs[key]))
dump(OUT / 'packet-hashes.json', {p.relative_to(OUT).as_posix(): digest(p) for p in OUT.rglob('*')
                               if p.is_file() and p.name != 'packet-hashes.json' and '__pycache__' not in p.parts})
print(json.dumps({'pin': SHA, 'runs': summary, 'verdict': 'NOT READY / BLOCKED', 'root_causes': 2}))
