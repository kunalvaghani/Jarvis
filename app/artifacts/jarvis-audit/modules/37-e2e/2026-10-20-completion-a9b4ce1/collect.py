"""Collect executed evidence; never promote fixture passes to live acceptance."""
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
ROOT = APP.parent
BASE = 'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip() == BASE
def write(name, body): (OUT / name).write_text(body.rstrip() + '\n', encoding='utf-8')
def dump(name, body): write(name, json.dumps(body, indent=2))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
normal = {}
prior_normal = json.loads((OUT / 'log-path-normalization.json').read_text(encoding='utf-8')) if (OUT / 'log-path-normalization.json').is_file() else {}
for path in [*OUT.glob('*.txt'), *OUT.glob('*.xml')]:
    before = sha(path)
    body = path.read_text(encoding='utf-8-sig')
    for source, target in [(str(APP), '%AUDIT_APP%'), ('D:\\Kunals GitHub Repo\\Jarvis\\app', '%INSTALL_APP%'),
                           (os.environ.get('USERPROFILE', 'NO_PROFILE'), '%USERPROFILE%')]:
        for spelling in {source, source.replace('\\', '/'), source.replace('\\', '\\\\')}:
            body = body.replace(spelling, target)
    body = re.sub(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"<>]+', '%USERPROFILE%', body)
    path.write_text(body, encoding='utf-8')
    normal[path.name] = {'original': prior_normal.get(path.name, {}).get('original', before), 'saved': sha(path)}
dump('log-path-normalization.json', normal)

runs, results = {}, []
for run in ['baseline', 'before-fixes', 'before-terminal', 'targeted', 'targeted-final', 'staged-regression', 'final', 'supplemental', 'historical-retention']:
    tree = ET.parse(OUT / (run + '.xml')).getroot()
    rows = []
    for case in tree.iter('testcase'):
        skip = case.find('skipped')
        status = 'FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIPPED' if skip is not None else 'PASS'
        rows.append({'id': case.get('name'), 'classname': case.get('classname'), 'status': status,
            'seconds': float(case.get('time', 0)), 'reason': skip.get('message') if skip is not None else '',
            'run': run, 'evidence': run + '.xml', 'base_sha': BASE})
    runs[run] = {status: sum(row['status'] == status for row in rows) for status in ['PASS', 'FAIL', 'SKIPPED']}
    runs[run]['seconds'] = sum(float(s.get('time', 0)) for s in tree.iter('testsuite'))
    results.extend(rows)
assert runs['final']['FAIL'] == runs['supplemental']['FAIL'] == 0
final = runs['final']
headline = f"{final['PASS']} PASS / 0 FAIL / {final['SKIPPED']} SKIPPED"
write('executed-results.jsonl', '\n'.join(json.dumps(row) for row in results))
dump('baseline.json', {'date': '2026-10-20', 'base_sha': BASE, 'fix_sha': None,
    'source_layers': 'base + retained P34/P35/P36 proposals + P37 uncommitted source/test patches', 'runs': runs,
    'headline_run': 'final', 'overlapping_runs_not_summed': True, 'peak_memory': 'NOT MEASURED',
    'real_cloud_requests': 0, 'real_messages': 0, 'native_hooks_or_mic': 0, 'installs': 0, 'training_runs': 0})
dump('host-profile.json', {'python': platform.python_version(), 'platform': platform.platform(),
    'machine': platform.machine(), 'logical_cpus': os.cpu_count(), 'peak_process_memory': 'NOT MEASURED',
    'interim_OS_working_set_samples': json.loads((OUT / 'memory-sample.json').read_text()),
    'memory_limit': 'Interim OS lifetime peaks, not final aggregate RSS/child/GPU peak or baseline comparison.',
    'dependency_routing': 'Existing installed main and skills venvs, read-only; source under isolated checkout.',
    'load_conditions': 'Final suite and supplemental/journal commands overlapped; elapsed times are not isolated performance comparisons.'})
paths = ['jarvis/actions.py', 'jarvis/demonstration.py', 'tests/test_prompt37_e2e_boundaries.py']
dump('source-hashes.json', {p: sha(APP / p) for p in paths})
dump('before-source-hashes.json', {'jarvis/actions.py': 'df936abcb0cea1e97198857f6e7d167367584aa23fded1ea77378f3b64a6ed41',
    'jarvis/demonstration.py': 'e6aa23d5a65e134a2a8b73b204b37568b06feefc02dcbd54ffa719c4026b3c54'})
(OUT / 'source.patch').write_bytes(subprocess.check_output(['git', 'diff', '--', 'app/jarvis/actions.py', 'app/jarvis/demonstration.py'], cwd=ROOT))
dump('source-layers.json', {'base_sha': BASE, 'fix_sha': None, 'patch': 'source.patch',
    'new_test': '../../../../../tests/test_prompt37_e2e_boundaries.py',
    'earlier_uncommitted_patches': 'P34/P35/P36 preserved; source.patch contains only the P37 production files.',
    'before': 'before-source-hashes.json', 'current': 'source-hashes.json'})
dump('review-revisions.json', {'base': BASE, 'claude': subprocess.check_output(['git', 'rev-parse', 'claude'], cwd=ROOT).decode().strip(),
    'fix_sha': None, 'branch': 'codex-review', 'status': 'uncommitted review proposals; no merge or deployment'})
prior = {}
for path in OUT.parent.iterdir():
    if not path.is_file(): continue
    rel = path.relative_to(ROOT).as_posix()
    tracked = subprocess.check_output(['git', 'show', BASE + ':' + rel], cwd=ROOT)
    assert hashlib.sha256(tracked).hexdigest() == hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    prior[path.name] = sha(path)
dump('prior-evidence-hashes.json', prior)
dump('historical-artifact-inventory.json', {p.relative_to(APP).as_posix(): sha(p)
    for p in (APP / 'artifacts/jarvis-audit/codex-independent-review').rglob('*') if p.is_file()})
retained = json.loads((OUT.parents[1] / '36-observability/2026-10-20-completion-a9b4ce1/source-hashes.json').read_text())
assert all(sha(APP / p) == digest for p, digest in retained.items())

old = {row['id']: row for row in (json.loads(s) for s in (OUT.parent / 'tests.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip())}
prompt = Path('C:/Users/kunal/Downloads/37_E2E_REVISED.md')
revised_inputs = dict(re.findall(r'- \*\*(JRV-37-\d{3}):\*\* (.+)', prompt.read_text(encoding='utf-8-sig')))
assert len(revised_inputs) == 26
dump('prompt-provenance.json', {'file': prompt.name, 'sha256': sha(prompt), 'numbered_cases': len(revised_inputs),
    'authority': 'User standing instruction authorizes safe fixes/audit from each supplied prompt; document itself is task scope, not separate permission for live side effects.'})
reasons = {
1: 'Physical voice, Gmail credentials, unread-account readback and spoken privacy acceptance not run.',
2: 'No actual Spotify play/pause readback; parser/tool fixtures do not prove playback.',
3: 'Unknown-app version research/action on a disposable native app not run.',
4: 'No fresh dropped-PDF citation/memory-isolation user journey; neighboring document guards only.',
5: 'Weather service fixtures pass; current live weather/notification freshness and duplicate delivery not established.',
6: 'No full website request -> isolated worktree -> browser preview -> approved commit journey.',
7: 'Idle/cancellation fixtures pass; physical voice interrupt/restart latency and job completion not measured.',
8: 'Provisional skill lifecycle tests pass; approval -> actual voice invocation not run.',
9: 'Groq/fallback fixture regressions pass; live local inference and physical duplicate-speech check not run.',
10: 'Physical large-model + TTS + microphone and low-VRAM acceptance not run; scheduler fixtures only.',
11: 'Uncertain mock-send durable truth/no-replay passes; real account crash/transmission acceptance not authorized.',
12: 'Fake owner-change-after-consent now refused; native desktop/browser focus and context isolation not established.',
13: 'Owned workbook API selection, separate-worker A1=9/formula preservation, CAPTURED/FIX and lesson storage pass. Native alternate UI strategy, complete workbook fidelity and user command path not established.',
14: 'Cancel/error lifecycle fixtures repaired. Actual Blender exploration/click/replay/verified provisional skill not run.',
15: 'Workbook FIX flow passes with a simulated author; changed browser selector and unrelated live-site regression not run.',
16: 'Generated adapter/schema rejection regressions pass; actual supported missing-tool container registration unavailable (Docker).',
17: 'Actual SQLite strategy/anti-pattern records observed; retrieval-driven user outcome improvement and OpenViking service not measured.',
18: 'Three-failure consent/advice-only/dedup recording-fake flow passes. Independent semantic provenance remains OPEN; no real provider acceptance.',
19: 'Sealed gate/evaluator tamper regressions pass. Exact target improvement plus voice/UIA held-out regression experiment not executed.',
20: 'AZR oracle/privacy/model registry fixtures pass. Fresh 0.5B training/checkpoint/inference acceptance not run.',
21: 'Mock boundary passes: queued Actions worker -> simulated uncertain send -> durable paused speech event -> TaskState restart blocks replay; separate DAG restored-running effect test refuses replay. One mock attempt, zero real sends. Actual rendered UI status/consumer acceptance remains BLOCKED.',
22: 'GPU priority/admission fixtures rerun; real concurrent SEAgent/DGM/AZR plus spoken command preemption not run.',
23: 'Isolated launcher observed repair_required; optional live credentials/inference not checked. Degraded fixtures do not certify actual Gmail/Spotify/YouTube/God\'s Eye/REA E2E.',
24: 'Prior MCP schema/custom-tool/skill regression suites rerun; complete live schema migration plus old custom-skill workflow not established.',
25: 'Synthetic injection, permission, privacy and outcome-identity guards pass. Arbitrary semantic privacy, all memory/tool/browser sinks and independent final verifier authority remain open.',
26: 'Fake hook stops on cancel and observation error; cancelled/failed sessions cannot promote; active-hook replacement refused. Native hook process exit and actual physical input/privacy scope unverified.'}
cases = []
for number, reason in reasons.items():
    identifier = f'JRV-37-{number:03d}'
    cases.append({'id': identifier, 'status': 'BLOCKED',
        'input': revised_inputs[identifier],
        'reason': reason, 'classification': 'partial fixture evidence; actual acceptance blocked',
        'base_sha': BASE, 'fix_sha': None, 'original_companion_available': identifier in old,
        'original_input': old.get(identifier, {}).get('input'),
        'catalog_join': 'original 001-012 retained' if number <= 12 else 'revised prompt replaces old generic catalog row; not equivalent',
        'evidence': ['executed-results.jsonl', 'workflow-journals.jsonl', 'launcher-check.txt']})
write('tests.jsonl', '\n'.join(json.dumps(row) for row in cases))
dump('coverage-summary.json', {'numbered_denominator': 26, 'PASS': 0, 'BLOCKED': 26, 'FAIL': 0, 'SKIPPED': 0,
    'NOT RUN': 0, 'old_catalog_rows': len(old), 'explanation': 'BLOCKED includes unrun live portions; pytest results are separate and never substituted for full journeys.'})
bench = list(csv.DictReader((OUT / 'benchmarks.csv').open(encoding='utf-8')))
dump('benchmark-summary.json', {revision: {'n': len(rows), 'median_ns': statistics.median(int(r['elapsed_ns']) for r in rows),
    'min_ns': min(int(r['elapsed_ns']) for r in rows), 'max_ns': max(int(r['elapsed_ns']) for r in rows),
    'sample_variance_ns2': statistics.variance(int(r['elapsed_ns']) for r in rows),
    'cleanup_successes': sum(r['cleanup_before_harness'] == 'True' for r in rows)}
    for revision in ['pinned', 'current'] for rows in [[r for r in bench if r['revision'] == revision]]})

write('inventory.md', f'''# Prompt 37 inventory — 2026-10-20

Pinned claude/HEAD {BASE}, isolated codex-review; retained P34/P35/P36 proposals. Root/app AGENTS, supplied revised Prompt 37 and findings-reconciliation contract read. Master contract unavailable. Current system-map and Phase 1–8 code/tests/reports inspected; historical recordings/training measurements are not fresh acceptance.

Real call paths inspected: command parser -> Actions queue/execute -> Brain/ToolRegistry -> strategy/adapters -> durable TaskState and skill/lesson stores. Demonstration request -> consent -> selected window -> owned hook -> pump -> replay -> provisional promotion. Changed only actions.py and demonstration.py, added dedicated regression tests; no new registry.

Original seven module files and 32 planned cases remain immutable. Stable IDs 001–012 joined; revised 013–026 replace older generic rows and are explicitly labelled. Existing 800-scenario/three-phrasing and >15,000 permutation corpus tested as linguistic routing, never action-success evidence. Installed dependencies routed read-only; application source is this worktree. Peak test-process memory NOT MEASURED. No cloud/account write, native input hook, microphone, package/model install, training or deployment.
''')
write('changes.md', '''# Local repairs

- P37-001: pump always stops its owned hook and persists a failed/cancelled/completed state; startup failure cleans up, duplicate start cannot replace an active hook. Pump refuses already terminal sessions and preserves a stop/cancel requested during an event callback. Stop failure persists failed and retains the reference for retry. Errors propagate; cleanup is not reported as successful when stop fails.
- P37-002: recheck cancellation/window PID after consent and before observation; pass cancellation through hook startup. Actions owner cleans on errors and returns no cancelled/partial demonstration as completed.
- P37-003: reject cancelled/failed/interrupted sessions and require literal True replay verification before creating a skill. Existing direct consented recording/replay remains compatible; this does not authenticate caller-created replay evidence or replace independent verifier authority.
- P37-004: after TaskState.finish downgrades an uncertain external write to paused, the matching task's durable result is returned to the worker/speech event and decision outcome. No action retry added; normal completed result objects preserved.

Before fixes: 10 FAIL / 2 PASS, captured in before-fixes.xml. Review then reproduced two terminal-state resurrection failures (before-terminal.xml), fixed before the final rerun. Final targeted neighboring run: 38 PASS, including cleanup-error/feature-off/terminal-state regressions. Staged regression 681 PASS / 5 SKIPPED is superseded by final.xml after the terminal-state fix, not added to it. Production source.patch is P37-only; new test file is separately hashed. No fix commit exists.
''')
write('failures.md', '''# Remaining acceptance blockers

No mandatory safe regression remains failing. The pre-fix failures are reproduced defects, not waived final failures. The 26 numbered dispositions in tests.jsonl remain the authoritative denominator: 0 full-journey PASS / 26 BLOCKED. BLOCKED includes live portions not run.

P37-R1 OPEN P1: independent final-verifier authority is not universal. Literal True promotion remains caller-supplied evidence; direct consented recording sessions remain eligible for compatibility. Uniform replay receipt/identity, live target binding and UI status truth need architectural acceptance. This patch closes the reproduced uncertain-send/task result mismatch only.

P37-R2 OPEN P1: physical demonstration hook exit, HWND reuse/PID lifetime races, native privacy scope and cancel mid-observation require owned disposable app acceptance. No native hook was started. No claim of physical cleanup from a Mock.

P37-R3 OPEN P1: cloud synthetic provenance is caller declared; prior semantic privacy finding remains open despite structural redaction/consent fixtures. Do not enable private-workspace cloud escalation based on these fixtures.

P37-R4 BLOCKED: isolated --check is repair_required (missing local env/assets, Docker/Ollama unavailable). Existing installed dependency roots do not establish service readiness or grant installation permission. No full voice/GPU/TTS, training, live accounts/browser/Blender or all-flags acceptance. Peak memory, E2E latency/throughput and all enabled/disabled combinations remain unmeasured.

See compatibility.md, tests.jsonl and cumulative Claude handoff for every case and next action. Prior P31–P36 blockers remain in force; no deployment.
''')
write('cross-pillar-matrix.md', '''# Change impact and final checks

| Change | Old feature / pillar seam | Invariant | Executed final evidence |
|---|---|---|---|
| demonstration pump/start/stop | Show Me Once -> A provisional skills | cancel/errors stop fake owned hook; terminal bad state cannot promote | test_prompt37_e2e_boundaries lifecycle/cancel/cleanup cases; old phase05 safe fixtures |
| post-consent recheck | native UI approvals / 31 island | cancellation or selected PID swap refuses before observation | test_request_revalidates_after_consent_before_observing; approval-binding/desktop fixture suites |
| durable task result | queued tasks, external writes / 32 recovery / 36 counters | uncertain write remains paused in durable state and speech event; never replay | test_uncertain_send_truth_reaches_worker_speech_and_restart; task_state/task_recovery; P08_flow_E |
| compatibility | deterministic voice/text intents and tools | normal results/parser routing preserved | task_state ordinary completion; intent_testbook; everyday runtime; agent_runtime; toolkits |
| neighboring A/API | CAPTURED/FIX and document fidelity | real API/readback before provisional skill | P08_flow_A; workflow-journals XLSX A1=9/formula preserved |
| B memory | strategy/anti-pattern, no silent trust transfer | stores retain bounded evidence and retrieval guards | phase04, P35/P36 tests; actual SQLite kinds in journal |
| C evolution | target/heldout authority | changed evaluator/heldout rejected | supplemental P06 tamper checks; no full target/voice experiment |
| D AZR | oracle/quarantine/experimental-only | no inference promotion or unauthorized training | phase07 safe fixtures/P35; physical training BLOCKED |
| MCP and dependencies / 33–35 | adapters, permissions, schema repair | no unauthorized executor effects / uncertain replay | P33/P34/P35 suites through final runner; no live principal/container acceptance |
| cloud | failure eligibility -> consent -> advisory only | deny zero requests, generic fake provider once, no actions | P08 cloud tests and journal; semantic provenance OPEN |

Run after the last production edit via run_regressions.py plus supplemental commands in reproduce.md. Registration/import/mock evidence is not a full user journey. Remaining physical/offline/version/flag coverage is BLOCKED.
''')
write('compatibility.md', '''# Compatibility / route limits

No dependency, runtime manifest, launch/stop script or service registration change. Demonstration start_hook adds an optional cancellation callback, preserving existing no-argument callers. Consented direct session recording/replay remains eligible, while cancelled/failed states are refused. Ordinary completed task results, including structured unread-search results, are not replaced; only matching durable paused results override optimistic task text.

Safe regression covers voice/text parsing, typed queue dispatch with simulated Brain, tools/DAG, documents, skill memory, API strategy, cloud off/on/denied, optional service failure, error/recovery and bounded evolution/AZR guards. These are selected relevant routes, not every hardware/provider/flag combination. New demonstration feature-off test proves no session request. Native hook, real voice/speaker, Excel GUI, browser focus, Blender, OpenViking, real account identity/scopes, 0.5B training, Docker/WSL and version rollback E2E remain BLOCKED. See launcher-check.txt for actual isolated readiness.
''')
write('security.md', '''# Security boundary

Tests use disposable local workbooks/SQLite/TaskState files, fake window modules/hooks, simulated Brain send and recording-fake cloud provider. Actual postconditions include separate worker workbook readback, durable paused status/speech event, restart blocker, zero real sends/requests and fake hook stop call count. No desktop recording or real input was performed.

Rechecked cancellation and selected PID after consent before observing; denial/PID swap produces zero fake Desktop calls. Truthy non-booleans cannot promote. Terminal bad session status cannot promote even with literal True. Cleanup exceptions are persisted failed, propagated, and retain an owned reference for retry. This is not proof against HWND/PID reuse, all native races, arbitrary semantic injection or forged caller replay evidence. P35/P36 privacy/identity guards rerun; their unresolved independent provenance/final-verifier gates persist.

Logs normalized for local roots; original and saved hashes retained. Workflow journals record component names and synthetic readbacks only. No credentials/private desktop/audio exported. Original configuration untouched. No installs or system/service changes to make readiness green.
''')
write('rollback.md', '''# Review and rollback

Proposals are uncommitted on codex-review, base pinned in review-revisions.json. Review source.patch and the separately hashed new test source. Apply accepted changes on claude; obtain the resulting SHA and rerun before release. Do not merge automatically.

To roll back P37, manually reverse only actions.py/demonstration.py hunks in source.patch after checking current hashes; preserve P34/P35/P36 edits and user changes. No global reset/clean, package uninstall, journal deletion or uncertain-write replay. Persisted terminal demonstration status and uncertain task records remain evidence; reopening does not grant fresh recording consent or write permission. Re-run relevant suites and launcher check after any rollback. Actual version rollback workflow was not run.
''')
write('codex-findings-reconciliation.md', f'''# Finding reconciliation — base {BASE}

| ID | Reproduction | Local repair / final tests | Status and follow-up |
|---|---|---|---|
| P37-001 | before-fixes pump/start/duplicate tests fail; pinned cleanup 0/30 | demonstration.py finally/start guard; cleanup tests incl stop-error retry; final.xml | FIXED bounded fake-hook lifecycle; native hook exit remains R2 |
| P37-002 | cancellation/PID swap reaches observation after consent | request recheck/start cancellation; parametrized consent tests plus Actions error/feature-off | FIXED observed consent seam; native lifetime races remain R2 |
| P37-003 | truthy strings/1 and cancelled session enter promotion | literal bool/eligible-status guards; parameterized promotion/cancel tests | FIXED reproduced admission; host replay authority remains R1 |
| P37-004 | worker speaks Finished although durable task paused | Actions matching durable result; queue/speech-event/restart test and P08_flow_E | FIXED task send seam; universal verifier/UI truth remains R1 |
| P35/P36 verifier and provenance | prior packet tests and handoff | all retained sources hashed and final suites rerun | OPEN; not relabelled fixed from neighboring passes |
| IR-001 / IR-002 / IR-003 | original bug register at 36fbf3ce; previous repair recorded at 32fdbfe | fresh historical-retention.xml private/unknown UIA, early training admission, 493 Windows recipe tests | FIXED bounded retention; physical/training/live target acceptance still BLOCKED |
| IR-004 | original deep Windows Git worktree portability report | recorded historical lab-final.xml; no fresh deep lab repro | UNVERIFIED fresh portability; do not infer from other fixture gates |

Fix SHA is null: local patches only, source hashes and source.patch identify changes. New tests are outside tracked diff until committed. Reproduction failures saved before production edits; final results collected after last production edit. Historical reports are not new live acceptance. See reconciliation companion folder for one-by-one ledger and evidence paths.
''')
write('reproduce.md', '''# Reproduce safely

From this worktree app directory, use the existing original main venv Python. No package setup/install required or authorized.

1. Run `python artifacts/jarvis-audit/modules/37-e2e/2026-10-20-completion-a9b4ce1/run_regressions.py --junitxml=artifacts/jarvis-audit/modules/37-e2e/2026-10-20-completion-a9b4ce1/final.xml -q`.
2. With the installed-dependency runner in the P31 independent packet, run tests/test_gpu_scheduler.py, tests/test_gpu_scheduler_audit.py, and phase06 tests `test_P06_gate_quarantines_code_or_test_or_evaluator_changes` / `test_P06_gate_refuses_when_its_policy_or_heldout_data_are_tampered`. Save supplemental.xml. Physical CUDA remains skipped.
3. Run run_journeys.py in this directory. It uses owned temporary files and existing skills Python, actual registry/adapters/stores, recording-fake cloud and simulated Brain/hook. It writes actual Python component call journals and 30 randomized pinned/current exception cleanup pairs. Workbook model author/approvals are simulated. Manual fixture cleanup of the old leaking hook is outside timing.
4. Run `python -m jarvis.launcher --check`; preserve repair_required output and do not install to hide it.
5. Run collect.py only after completed XML results exist; it verifies source/original evidence, writes classifications/reports and appends cumulative handoff documentation.

Before-fixes.xml preserves pre-repair failing tests; reproducing those requires restoring only the two pinned source files in a separate owned checkout. Do not reverse retained patches or mutate the user's running checkout. Benchmark source is loaded from git at the pinned SHA into an isolated module; no native hook is started. Cold/warm voice/GPU performance and peak memory are NOT measured.
''')
write('verdict.md', f'''# Prompt 37 — safe local work complete; release NOT READY

2026-10-20, isolated codex-review at {BASE} plus retained P34–P36 and P37 local proposals. Final relevant regression: **{headline}**. Supplemental: **{runs['supplemental']['PASS']} PASS / 0 FAIL / {runs['supplemental']['SKIPPED']} SKIPPED**, separate and overlapping, not added. Baseline 32 PASS; reproduced new tests 10 FAIL / 2 PASS plus two later terminal-state failures; final targeted 38 PASS. No final failures.

Fixed demonstration cleanup/consent/cancellation/admission and durable uncertain-send completion feedback. Three reproducible owned/simulated workflow journals include real workbook worker readback A1=9 with formula preserved; mock send paused speech-event/restart blocker; cloud consent/advice/dedup. Thirty paired pinned/current fake observer-failure fixtures improve cleanup/readback from 0/30 to 30/30. These are safety/postcondition checks, not physical hook or assistant performance proof.

26 revised case denominator: **0 full-journey PASS / 26 BLOCKED**. Physical voice/GPU/native hooks/live apps/accounts, all flags, independent verifier/provenance and training gates remain incomplete. Isolated launcher: repair_required. No installs, live sends/cloud, mic, training, merge or deployment. [Cases](tests.jsonl) · [Actual journals](workflow-journals.jsonl) · [Impact matrix](cross-pillar-matrix.md) · [Reproduction](reproduce.md) · [Cumulative Claude handoff](../../../../../docs/CLAUDE_HANDOFF.md).
''')

REC = APP / 'artifacts/jarvis-audit/reconciliation' / ('37-' + OUT.name)
REC.mkdir(parents=True, exist_ok=True)
for name in ['review-revisions.json', 'executed-results.jsonl']:
    (REC / ('repro-results.jsonl' if name == 'executed-results.jsonl' else name)).write_bytes((OUT / name).read_bytes())
for name, subset in [('legacy-regressions.jsonl', [r for r in results if r['run'] == 'final']),
                     ('cross-pillar-regressions.jsonl', [r for r in results if r['run'] in {'final', 'supplemental'} and any(k in r['classname'] for k in ['phase0', 'prompt3', 'gpu'])])]:
    (REC / name).write_text('\n'.join(json.dumps(r) for r in subset) + '\n', encoding='utf-8')
with (REC / 'findings-ledger.csv').open('w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file); writer.writerow(['finding', 'status', 'base', 'fix', 'evidence', 'reviewer_followup'])
    for n in range(1, 5): writer.writerow([f'P37-{n:03d}', 'FIXED bounded scope', BASE, 'uncommitted source hashes/patch', 'before-fixes.xml;final.xml', 'reverify accepted claude SHA; retain R1-R4'])
    for n in range(1, 4): writer.writerow([f'IR-{n:03d}', 'FIXED bounded retention', '36fbf3ce925080f7f54afa87eaf1d9b88414142d', '32fdbfe (historical repair); current base ' + BASE, 'historical-retention.xml', 'live acceptance remains blocked'])
    writer.writerow(['IR-004', 'UNVERIFIED fresh deep-lab check', '36fbf3ce925080f7f54afa87eaf1d9b88414142d', 'historical recorded repair', 'codex-independent-review/lab-final.xml (historical)', 'fresh disposable deep-path worktree reproduction required'])
for name, target in [('handoff.md', 'verdict.md'), ('unresolved.md', 'failures.md'), ('patch-assessment.md', 'changes.md'), ('artifact-inventory.md', 'inventory.md')]:
    (REC / name).write_text(f'See [Prompt 37 {target}](../../modules/37-e2e/{OUT.name}/{target}).\n', encoding='utf-8')

# Documentation and cumulative handoff updated only after final test evidence exists.
packet = 'artifacts/jarvis-audit/modules/37-e2e/' + OUT.name
def insert(path, marker, body, anchor):
    text = path.read_text(encoding='utf-8')
    block = f'<!-- {marker} -->\n{body}\n<!-- /{marker} -->\n\n'
    if f'<!-- {marker} -->' in text:
        text = re.sub(rf'<!-- {marker} -->.*?<!-- /{marker} -->\s*', lambda m: block, text, flags=re.S)
    else:
        assert anchor in text
        text = text.replace(anchor, block + anchor, 1)
    path.write_text(text, encoding='utf-8')
insert(APP / 'README.md', 'prompt37-e2e', f'''**2026-10-20 — Prompt 37 safe local repairs complete; release NOT READY.** Final relevant regression: **{headline}**. Separate supplemental fixtures: {runs['supplemental']['PASS']} pass / {runs['supplemental']['SKIPPED']} skipped; overlapping runs are not summed. Demonstration cancellation/start/observation failures clean the owned hook and persist terminal state; post-consent cancellation/PID changes refuse observation; cancelled/failed sessions and truthy non-booleans cannot promote. Cleanup failures remain explicit and retryable. An uncertain external write now returns the matching durable paused result to the queued worker's speech event rather than optimistic completion text.

Three owned/simulated journals cover real API workbook readback (A1=9 and formula preserved), provisional CAPTURED/FIX and lesson storage, uncertain mock-send restart, and consented generic recording-fake cloud advice. Thirty fixed-source fake-hook exception pairs improved cleanup 0/30 to 30/30; no E2E latency claim. **26-case acceptance: 0 full-journey pass / 26 blocked**. Native hook exit, real voice/GPU/apps/accounts, all enabled/disabled paths, global verifier/provenance and training remain incomplete; isolated readiness is repair_required. [Evidence]({packet}/verdict.md) · [Journals]({packet}/workflow-journals.jsonl) · [Cases]({packet}/tests.jsonl) · [Cumulative Claude handoff](docs/CLAUDE_HANDOFF.md).''', '<!-- prompt36-observability -->')
insert(ROOT / 'README.md', 'prompt37-e2e', f'''**2026-10-20 — Prompt 37 local acceptance repairs verified; release NOT READY.** **{headline}** in the final relevant regression. Demonstration lifecycle/consent checks and truthful uncertain-send completion repaired; native voice/apps/GPU acceptance remains blocked. [Application details](app/README.md) · [Evidence](app/{packet}/verdict.md) · [Cumulative Claude handoff](app/docs/CLAUDE_HANDOFF.md).''', '<!-- prompt36-observability -->')
handoff = APP / 'docs/CLAUDE_HANDOFF.md'
body = handoff.read_text(encoding='utf-8')
section = f'''## Prompt 37 — completed safe local repairs; acceptance NOT READY

**2026-10-20**, base {BASE}, retained P34–P36 plus uncommitted P37 changes on codex-review. [Verdict](../{packet}/verdict.md), [P37-only production patch](../{packet}/source.patch), [source hashes](../{packet}/source-hashes.json), [new tests](../tests/test_prompt37_e2e_boundaries.py), [26 cases](../{packet}/tests.jsonl), [actual workflow journals](../{packet}/workflow-journals.jsonl). No commit/merge/deployment.

P37-001 fixed fake-hook cleanup on pump/start exceptions, duplicate start rejection, terminal persistence and explicit stop-error retry. Pump also refuses terminal sessions and preserves callback cancellation; two extra reproduced failures preceded that final fix. P37-002 fixed post-consent cancellation/PID drift before observation and Actions cleanup/partial-return behavior. P37-003 rejects terminal bad sessions and truthy non-boolean replay claims. P37-004 returns matching durable paused result after uncertain external writes, preserving no-replay and ordinary successful results. Initial reproduction 10 failing / 2 passing; final targeted 38 pass. Final relevant: **{headline}**; supplemental {runs['supplemental']['PASS']} pass/{runs['supplemental']['SKIPPED']} skip, not summed. Staged 681 pass/5 skip predates the final terminal-state repair and is superseded, not summed. 800-scenario/permutation linguistic checks are not action success.

Owned workbook worker readback A1=9/formula preserved; actual CAPTURED/FIX and SQLite strategy/anti-pattern stored. Brain, author, consent callbacks, cloud provider and hook boundaries explicitly simulated where used. Queued mock-send restart has one attempt, durable paused speech event and replay blocker. Cloud fake gets one approved generic advisory, no action and no duplicate consultation. Thirty pinned/current exception pairs: cleanup 0/30 -> 30/30; no physical hook/performance claim.

### Prompt 37 — unresolved work for Claude

| ID / scope | Evidence / blocker | Required next action |
|---|---|---|
| P37-R1 OPEN P1; 008/014/021/025 | P37 closes one durable-task feedback mismatch. Replay True is still caller evidence; direct consented recording remains eligible. Universal final verifier/receipt authority, target binding and actual UI completion truth incomplete. | Bind replay to independent host receipt, selected session/step/target and actual readback; test forged/stale/cross-session receipts and physical paused UI. Preserve ordinary structured task returns and no replay. |
| P37-R2 OPEN P1; 012/014/026 | Fake hooks clean on cancel/error; no actual native hook started. HWND/PID reuse/lifetime, physical exit and cancel mid-observation not proved. | Use disposable native app, explicit scoped consent; observe owned process exit, no later input capture, no cancelled skill and fresh-target identity. Do not record personal desktop. |
| P37-R3 OPEN P1; 018/025 | Cloud three-failure/consent/fake advisory flow passes; caller label is not semantic privacy provenance. Carries P35 finding. | Enforce trusted typed synthetic provenance before provider; adversarial semantic private-context cases with zero outbound, no raw logs. |
| P37-R4 BLOCKED environment; 001–010/013–020/022–024 | Isolated launcher repair_required; no real mic/speaker/GPU/models/training/Docker/live accounts/browser/Blender/OpenViking. Fixture pass is not user acceptance. Peak memory, throughput, all flags and full version rollback not measured. | Stage approved disposable app/account/services and fixed fixtures; execute all 26 journeys with actual readback/call journals, timing/memory and enabled/disabled routes. Obtain approval only for necessary external/system changes; no real sends/deletes without scope. |

Acceptance denominator **0 full-journey PASS / 26 BLOCKED**; exact case-by-case gaps are in [tests.jsonl](../{packet}/tests.jsonl), not replaced by green regression counts. Fresh source SHA after applying accepted fixes and independent rerun required. Keep every earlier blocker below until separately resolved. Safe local Prompt 37 work is complete at this phase boundary; release remains NOT READY.

'''
if '## Prompt 37 —' not in body:
    body = body.replace('## Prompt 36 —', section + '## Prompt 36 —', 1)
handoff.write_text(body, encoding='utf-8')
recovery = APP / 'docs/CRASH_RECOVERY.md'
body = recovery.read_text(encoding='utf-8')
section = f'''## Demonstration and uncertain task completion — 2026-10-20

Recording startup/observation failures stop the owned hook and persist failed state. Cancellation stops recording and cannot create a provisional skill; if hook cleanup itself fails, the failure is persisted and the owned reference retained for retry. Fresh cancellation/PID checks occur after consent before observation. Native hook exit and HWND/PID lifetime acceptance remain unverified.

TaskState may downgrade an optimistic task result to paused when an external write is uncertain. Actions now returns that matching durable result to the worker/speech event and decision outcome. Restart must inspect the actual result; no automatic send/click/write replay. This closes the tested mock-send seam, not universal verifier/UI authority. [Prompt 37 evidence](../{packet}/verdict.md) · [Cumulative handoff](CLAUDE_HANDOFF.md).

'''
if '## Demonstration and uncertain task completion' not in body:
    body = body.replace('## Observability boundary', section + '## Observability boundary', 1)
recovery.write_text(body, encoding='utf-8')
dump('validation.json', {'date': '2026-10-20', 'required_reports': 12, 'reconciliation_files': 9,
    'numbered_denominator': 26, 'blocked_cases': 26, 'workflow_journals': 3, 'benchmark_pairs': 30,
    'prior_originals_unchanged': True, 'P34_P35_P36_source_hashes_retained': True,
    'current_source_hashes_match': True, 'full_live_E2E': 'BLOCKED', 'release': 'NOT READY'})
print(headline)
