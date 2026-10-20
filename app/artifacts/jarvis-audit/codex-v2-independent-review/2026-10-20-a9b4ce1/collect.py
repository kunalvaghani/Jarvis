"""Package independent V2 evidence after the final selected regression completes."""
import csv
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
ROOT = APP.parent
BASE = 'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6'
def write(name, body): (OUT / name).write_text(body.rstrip() + '\n', encoding='utf-8')
def dump(name, value): write(name, json.dumps(value, indent=2))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip() == BASE
source = json.loads((OUT / 'candidate-source-hashes.json').read_text())
assert all(sha(APP / name) == digest for name, digest in source.items())
parents = json.loads((OUT / 'parent-evidence-index.json').read_text())
changed_parents = [name for name, row in parents.items() if sha(APP / name) != row['sha256']]
assert not changed_parents, changed_parents
normal = {}
old_normal = json.loads((OUT / 'log-normalization.json').read_text(encoding='utf-8')) if (OUT / 'log-normalization.json').is_file() else {}
for path in [*OUT.glob('*.txt'), *OUT.glob('*.xml')]:
    old = sha(path)
    body = path.read_text(encoding='utf-8-sig')
    for start, replacement in [(str(APP), '%AUDIT_APP%'), ('D:\\Kunals GitHub Repo\\Jarvis\\app', '%INSTALL_APP%'),
        ('D:\\Kunals GitHub Repo\\LocalGithub\\Jarvis-codex-v2-baseline\\app', '%PINNED_APP%'),
        (os.environ.get('USERPROFILE', 'NO_PROFILE'), '%USERPROFILE%')]:
        for spelling in {start, start.replace('\\', '/'), start.replace('\\', '\\\\')}:
            body = body.replace(spelling, replacement)
    body = re.sub(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"<>]+', '%USERPROFILE%', body)
    path.write_text(body, encoding='utf-8')
    normal[path.name] = {'original_sha256': old_normal.get(path.name, {}).get('original_sha256', old), 'saved_sha256': sha(path)}
dump('log-normalization.json', normal)
runs, all_rows = {}, []
for run in ['pinned-boundaries', 'pinned-prior-findings', 'candidate-boundaries', 'candidate-full',
            'triage', 'tool-schema-before', 'schema-final', 'harness-preflight', 'candidate-final', 'deep-lab', 'pinned-deep-lab']:
    root = ET.parse(OUT / (run + '.xml')).getroot()
    rows = []
    for case in root.iter('testcase'):
        skipped = case.find('skipped')
        fail = case.find('failure')
        error = case.find('error')
        status = 'FAIL' if fail is not None or error is not None else 'SKIPPED' if skipped is not None else 'PASS'
        rows.append({'id': case.get('name'), 'classname': case.get('classname'), 'status': status,
            'seconds': float(case.get('time', 0)), 'reason': skipped.get('message') if skipped is not None else '',
            'failure': (fail.get('message', '')[:600] if fail is not None else error.get('message', '')[:600] if error is not None else ''),
            'run': run, 'source': 'pinned' if run.startswith('pinned') else 'candidate', 'xml': run + '.xml'})
    runs[run] = {s: sum(r['status'] == s for r in rows) for s in ['PASS', 'FAIL', 'SKIPPED']}
    runs[run]['seconds'] = sum(float(s.get('time', 0)) for s in root.iter('testsuite'))
    all_rows.extend(rows)
main_final = runs['candidate-final']
assert main_final['FAIL'] == 0, main_final
assert runs['deep-lab']['FAIL'] == runs['pinned-deep-lab']['FAIL'] == 1
final = {status: main_final[status] + runs['deep-lab'][status] for status in ['PASS', 'FAIL', 'SKIPPED']}
mutations = json.loads((OUT / 'mutation-results.json').read_text())
assert len(mutations['mutants']) == 6 and all(r['killed'] for r in mutations['mutants'])
assert mutations['tracked_original_bytes_restored']
environment = json.loads((OUT / 'environment-readback.json').read_text())
assert all(r['pip_check_returncode'] == 0 for r in environment['environment_results'])
headline = f"{final['PASS']} PASS / {final['FAIL']} FAIL / {final['SKIPPED']} SKIPPED"
write('03-executed-results.jsonl', '\n'.join(json.dumps(row) for row in all_rows))
dump('run-summary.json', {'runs': runs, 'headline': 'candidate-final plus distinct deep-lab test', 'final_distinct_candidate_checks': final, 'overlaps_not_summed': True,
    'full_assistant_live_E2E': 0, 'owned_component_workflow_journals': 3, 'mutation_pairs': 6,
    'mutation_assertion_failures_are_expected': True, 'superseded_partial_run': 'interrupted-run.json',
    'release': 'NOT READY FOR DEPLOYMENT'})

# An ID link is evidence discovery, not an assertion that the complete expected behavior passed.
final_rows = [r for r in all_rows if r['run'] == 'candidate-final']
links = {}
for row in final_rows:
    for a, b in re.findall(r'JRV[-_](\d{2})[-_](\d{3})', row['id']):
        links.setdefault(f'JRV-{a}-{b}', []).append({'id': row['id'], 'classname': row['classname'], 'status': row['status']})
specs = [json.loads(s) for s in (OUT / 'corpus-specifications.jsonl').read_text().splitlines()]
coverage = []
for row in specs:
    coverage.append({'id': row['id'], 'variant': row['variant'], 'specification': row.get('input_and_expected', row.get('expected')),
        'full_acceptance_status': 'BLOCKED' if row['id'].startswith(tuple(f'JRV-{n}-' for n in range(31, 38))) else 'NOT RUN',
        'linked_fresh_test_rows': links.get(row['id'], []), 'link_limit': 'ID only; expected-behavior equivalence is not established by a name match.'})
write('04-coverage.jsonl', '\n'.join(json.dumps(row) for row in coverage))
dump('case-accounting.json', {'imported_id_behavior_variants': len(specs), 'original_planned_ids': 1184,
    'original_checkpoint_planned_ids': 797, 'planned_ids_never_converted_to_pass': True,
    'fresh_named_ID_links': len(links), 'candidate_pytest': final,
    'revised_P37_user_journeys': {'PASS': 0, 'BLOCKED': 26},
    'full_live_integrations': 0})

bench = list(csv.DictReader((OUT / 'benchmarks.csv').open(encoding='utf-8')))
summary = {}
for revision in ['pinned', 'current']:
    rows = [r for r in bench if r['revision'] == revision]
    values = sorted(int(r['elapsed_ns']) for r in rows)
    summary[revision] = {'n': len(values), 'p50_ns': statistics.median(values), 'p95_ns_nearest_rank': values[math.ceil(.95 * len(values)) - 1],
        'sample_variance_ns2': statistics.variance(values), 'cleanup_successes': sum(r['cleanup_before_harness'] == 'True' for r in rows)}
pairs = {revision: {int(r['pair']): int(r['elapsed_ns']) for r in bench if r['revision'] == revision} for revision in ['pinned', 'current']}
delta = [pairs['current'][i] - pairs['pinned'][i] for i in sorted(pairs['pinned'])]
mean = statistics.mean(delta); error = 1.96 * statistics.stdev(delta) / math.sqrt(len(delta))
summary['paired_mean_delta_ns'] = mean
summary['approximate_normal_95CI_delta_ns'] = [mean - error, mean + error]
summary['scope'] = 'Synthetic observer-failure cleanup including current durable write; no real command latency, accuracy or throughput claim. No statistical population inference for physical hooks.'
dump('benchmark-summary.json', summary)

write('01-source-audit.md', f'''# Source and evidence audit — 2026-10-20

Pinned claude/parent: `{BASE}`. Live claude has a user configuration modification, excluded from this audit; Claude stopped/committed precondition is not established. Candidate is uncommitted codex-review at the same parent plus separately hashed Prompt 34–37 proposals. No candidate commit invented, no live claude/main edit. review-revisions.json and candidate-source-hashes.json identify these layers.

560 Python source files hashed before execution; 272 Jarvis Python files parse, including package initializers. source-graph.json records 266 top-level module records, import edges and 120 actual ToolRegistry specifications. Existence/registration/importability/fixture tests are distinct from live reachability and outcomes. Existing system map, actual source call paths, current launcher config/service checks and Phase 1–8 handoff/evidence were inspected. Module docstrings and source graph preserve reproducible discovery; this is not a line-by-line security proof of all code.

Core seams: Engine/commands -> Actions queue/execute -> Brain/ToolRegistry -> strategy/adapters -> TaskState/Verify receipts -> skills/ReasoningBank; optional native UI/browser, cloud, evolution and AZR admission remain separate. Ten installed environment metadata/consistency checks refreshed offline. Two pip-less workers checked with existing main pip --python, without installation. Isolated launcher reports repair_required; no environment repair attempted.

Original independent verdict/bug/security/patch/results reopened. 5,116 earlier artifact hashes preserved and rechecked. 33 fresh pinned prior-finding checks include synthetic private UIA, early training admission, Windows recipes and owned Git lab. Historical full model/voice/recording/container results are not rerun evidence. Master pack found at its recorded path: prompts/00_MASTER.md; differently named 00_MASTER_CONTRACT.md unavailable. Unrelated EDITH master download excluded.
''')
write('02-corpus-inventory.md', f'''# Corpus lineage

Original companion catalogue: **1,184 unique IDs**, from all 37 original module prompts; hash matches the checked-out catalogue. All original prompts, original Master, seven revised prompts and Prompt 99 indexed with headings/hashes in corpus-provenance.json. Revised cases are deduplicated by ID plus expected behavior, preserving conflicting old/new meanings: **{len(specs)} variants**. Earlier 797 planned checkpoint IDs are historical scope, never a passing count.

corpus-specifications.jsonl stores planned specifications; 04-coverage.jsonl links fresh named tests without assuming behavior equivalence from an ID. Original module/phase reports remain immutable. Fresh regression counts are run-summary.json; full-journey acceptance remains blocked where unrun. Exact excluded test functions and reasons are full-selection.json. Missing installed authoring/browser/model/vault prerequisites are not silently changed into passes.
''')
with (OUT / '05-findings-ledger.csv').open('w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file); writer.writerow(['finding', 'status', 'pinned', 'candidate_fix', 'fresh_evidence', 'follow_up'])
    for n in range(1, 5):
        writer.writerow([f'IR-{n:03d}', 'PARTIAL / REOPENED P2 for deep working directory' if n == 4 else 'FIXED bounded checks; broader live acceptance incomplete', BASE,
            'Historical repair retained at pinned SHA', 'pinned-prior-findings.xml; candidate-final.xml',
            'deep-lab.xml and pinned-deep-lab.xml FAIL: WinError 267; use shorter explicit owned lab_root; no silent relocation' if n == 4 else 'No live GPU/UI/global privacy certification'])
    for name in ['P31-001', 'P31-002', 'P32-001', 'P32-002', 'P33-001', 'P33-002', 'P33-003', 'P33-004']:
        writer.writerow([name, 'retained bounded boundary repair', BASE, 'historical integrated repair', 'candidate-final.xml', 'Native/live principal/concurrency gates remain in cumulative handoff'])
    for prompt, count in [(34,2), (35,6), (36,6), (37,4)]:
        for n in range(1, count + 1): writer.writerow([f'P{prompt}-{n:03d}', 'BASE DEFAULT FIX + LOCAL HARDENING' if prompt == 34 else 'LOCAL CANDIDATE ONLY', BASE,
            'source-only.patch + separate new tests, commit null', 'pinned-boundaries.xml; candidate-boundaries.xml; candidate-final.xml', 'Claude must integrate accepted patch and provide new SHA for independent rerun'])
    writer.writerow(['V2-001', 'FIXED test compatibility', BASE, 'two bounded clock-schema allow-lists strengthened', 'triage.xml; tool-schema-before.xml; candidate-final.xml', 'No production privacy relaxation'])
    writer.writerow(['V2-002', 'FIXED audit harness', BASE, 'source cwd + explicit installed dependency routes', 'candidate-full.xml superseded; harness-preflight.xml; candidate-final.xml', 'Default isolated path readiness still blocked'])
    writer.writerow(['V2-003 / IR-004', 'OPEN P2 portability', BASE, 'No production change; two attempted invocation alternatives failed', 'deep-lab.xml; pinned-deep-lab.xml; long-path-probe.json', 'Choose short explicit owned lab_root; no automatic move/global OS setting'])

write('06-failures-and-fixes.md', '''# Failures, repairs and retained limits

Committed source: boundary corpus 64 FAIL / 15 PASS / 1 SKIPPED. Review candidate on the same corpus: 79 PASS / 1 SKIPPED. These are independent defect reproductions, not 64 distinct root causes. P34 default readiness guards already exist at the pin; additional P34 hardening and P35–P37 local proposals are absent from claude. Exact source-only.patch and test-change.patch provided for review.

First broad candidate run: 39 FAIL / 1,857 PASS / 139 SKIPPED. Diagnosed child imports from repository cwd, missing isolated LocalGithub/Hermes metadata routes, and two legacy allow-lists rejecting new bounded monotonic/clock fields. One interrupted rerun is preserved as superseded-partial.txt/interrupted-run.json and has no complete count. All known categories passed a 33-test corrected preflight. Two assertion updates retain categorical key bounds, content-leak canaries and now require positive integer monotonic time / 32-character clock ID. Production source was not changed for V2; prior P34–P37 proposals were preserved.

Mutation preliminary result 4/6 killed is not accepted as safety proof: stale-selector edit targeted a different branch than the selected test, and heldout mutant had invalid CRLF handling. Corrected final-guard mutation and exact-byte preservation yield six passing controls and six assertion-failing mutants, all source restored. Neither import/syntax errors nor a surviving irrelevant mutation count as a kill.

Remaining unfixable or unrun release gates are 13-unresolved-blockers.md and the cumulative Claude handoff. No test weakening, installs, account side effects or real recordings to clear blockers.

V2-003 / IR-004 reopened P2: an additional real owned Git lab test places the lab working directory itself over 260 characters. Both pinned and candidate fail with NotADirectoryError / WinError 267 before Git starts. Existing core.longpaths protects repository paths, but does not close this process-cwd boundary. An extended Windows cwd prefix and short-cwd Git -C route were both tried in owned fixtures and failed. Ordinary short lab ownership/worktree tests pass. No safe transparent relocation or OS change attempted; use a shorter explicit owned lab_root/checkout and keep deep-location acceptance blocked. The one failed supplemental check is included in the final distinct candidate count, not hidden behind the passing full selection.
''')
write('07-security-findings.md', '''# Security and integrity

Fresh tested invariants include deny-policy execution, argument/approval binding, simulated cloud outbound capture, private/unknown UIA snapshot exclusion, generated skill/MCP constraints, independent false-success rejection, held-out/evaluator seals, deterministic no-replay, task identities, native pointer transport fakes and bounded metadata. Six deliberately violating mutants are rejected by assertion failures with passing controls. Owned workbook readback, native/Git/loopback component tests are identified by actual test bodies and journals; successful model text or mock return never establishes full user acceptance.

OPEN P1: universal host verifier/receipt authority and target binding; caller-declared synthetic cloud provenance; approved mutable model tag/byte-budget transport and execution-lock race; full live principal/scopes, shared task-generation/service concurrency and all-sink privacy remain incomplete. See inherited handoff for exact scopes. Existing guards do not establish all-source semantic privacy or native sandbox confinement.

No live personal account write/send/delete, private input capture, paid API, model download/training, installation or deployment. Fixture processes/files only. Superseded audit runner was identified by exact script/XML arguments before stopping its owned tree; shared/user processes untouched. Mutation checkout restored tracked original bytes; independent test overlays retained. No exhaustive current CVE/license/semantic scan or fresh GPU security test claimed.
''')
write('08-performance-benchmarks.md', '''# Measurements and limits

benchmarks.csv: 30 randomized paired pinned/current observer-failure fixtures (seed 37), 60 raw samples, same interpreter and fake owned hook. Cleanup/readback succeeds 0/30 pinned vs 30/30 candidate. Timings include candidate durable failure cleanup, while old harness cleanup is outside timing. benchmark-summary.json records p50/p95, variance and a limited approximate paired-mean CI. This demonstrates a bounded safety repair and its cost, not an assistant speed improvement.

Three workflow journals record actual Python component calls and postconditions. Real owned workbook separate-worker readback A1=9/formula preserved; CAPTURED/FIX and SQLite lessons. Simulated Brain send produces paused completion event and restart blocker with one mock attempt. Recording-fake cloud consent/advisory/dedupe causes no real requests/actions. Journal profiling affects elapsed times; they are not latency benchmarks.

Environment package versions/consistency are fresh. OS interim process working-set samples are separate if present; no aggregate baseline/candidate RAM, GPU VRAM, foreground latency, cold/warm model TTFT, physical speech, accuracy/precision/recall or general task completion improvement measured. Test elapsed times overlapped independent checks and must not be compared as controlled performance. Domain privacy/retention cannot be traded for a latency win.
''')
write('09-four-pillars-verification.md', '''# Pillar / addition verdicts

| Capability | Fresh bounded evidence | Full acceptance |
|---|---|---|
| A living skills | CAPTURED/FIX/DERIVED, metadata/outcome attribution, generated schema and provisional lifecycle tests; real fixture workbook CAPTURED/FIX | PARTIAL; live generated MCP host/container, native app/voice skill and verifier authority blocked |
| B exploration/memory | SQLite strategy/anti-pattern, quarantine/source/identity fixtures, failure routing | PARTIAL; real exploration/OpenViking retrieval outcomes and semantic contamination coverage blocked |
| C evolution | owned Git lab, bounded surfaces/lineage, immutability/tamper, independent gate rules; heldout mutation rejected | PARTIAL; complete target-win/voice/UIA-heldout degradation, live rollback acceptance blocked |
| D AZR | deterministic task/oracle, data/privacy/registry/admission fixtures and pre-import refusal | PARTIAL; fresh 0.5B training, checkpoint compatibility and physical voice preemption blocked |
| API-first | actual workbook worker fidelity, strategies/adapter contracts and negative approval cases | PARTIAL; complete proprietary formats/signatures/native alternate workflows blocked |
| Cloud architect | failure eligibility -> explicit consent -> abstract synthetic recording-fake -> advice-only/dedupe; payload guards | PARTIAL; independent semantic provenance OPEN; no real cloud acceptance |
| Show Me Once | consent/cancel/PID fake checks; error cleanup, terminal state, literal verification admission; mutation controls | PARTIAL; native hook lifetime, actual capture/replay and host receipt authority blocked |

No sum of these component results establishes an end-to-end assistant outcome. Original Phase 1–8 evidence remains historical and separately hashed.
''')

audit_files = {1:'architecture',2:'perception_cognition',3:'intent_direct',4:'voice_stt',5:'voice_tts',6:'questions_context',7:'model_routing',
8:'gpu_scheduler',9:'deliberation',10:'dag_planning',11:'skill_selection',12:'tool_registry',13:'desktop_control',14:'browser_playwright',
15:'app_research',16:'memory',17:'rag_documents',18:'repo_learning',19:'ability_forge',20:'self_evolution',21:'native_coding',
22:'web_development',23:'gmail',24:'whatsapp',25:'media',26:'realtime',27:'gods_eye',28:'sandbox_deerflow',29:'reverse_engineering',30:'harness_planners'}
lines = ['# Legacy and revised-module retention', '', '| Module | Fresh selected test coverage | Limit |', '|---|---|---|']
for n in range(1, 38):
    matched = [r for r in final_rows if (f'test_{audit_files[n]}_audit' in r['classname'] if n <= 30 else f'prompt{n}' in r['classname'])]
    counts = {s: sum(r['status'] == s for r in matched) for s in ['PASS','FAIL','SKIPPED']}
    lines.append(f"| {n:02d} | {counts['PASS']} pass / {counts['FAIL']} fail / {counts['SKIPPED']} skip in named selected file(s) | Fixture/owned-component scope; registration is not live acceptance. |")
write('10-legacy-retention.md', '\n'.join(lines) + '\n\nFull IDs/classnames are in 03-executed-results.jsonl. Standard tests supplement these counts; overlapping wrappers are not unique real outcomes. All 31–37 revised acceptance variants retained with explicit BLOCKED/NOT RUN coverage, not inferred from passing neighboring tests. Missing credentials, native/hardware/service and all-flags combinations remain unresolved. Browser/build tests excluded for absent isolated prerequisites are listed explicitly.\n')
write('11-mutation-quality.md', '''# Mutation controls

Six actual disposable-checkout mutations: deny policy bypass; accepting tool-success instead of host readback; stale final UI selection signature guard removed; deterministic DAG Verify disabled; heldout seal check disabled; uncertain effect restore barrier removed. Each has a passing unmodified control, then assertion failures with pytest exit 1 and zero collection errors. All source bytes restored after each mutation and pinned tracked bytes restored after candidate mirror testing.

mutation-results.json includes exact old/mutant hashes, test IDs, control/mutant XML and durations. Six kills prove these six checks discriminate those violations, not that the entire suite detects every bug. Preliminary wrong-branch/CRLF-invalid aggregate/status/hashes are recorded in mutation-preliminary.json and excluded. Preliminary per-case XML/text filenames were superseded, not separately preserved; only final corrected evidence is used. Added independent tests remain owned overlays; no user worktree mutated.
''')
write('12-code-fixes-and-diffs.md', '''# Exact proposed changes for Claude

source-only.patch is the retained uncommitted P34–P37 production diff against the pinned SHA; it is not already integrated into claude. V2 needed no further production repair. New V2 changes update two legacy telemetry schema assertions to recognize bounded clock fields and verify their types, plus reproducible audit harness configuration/cwd fixes. No privilege, privacy, retry or executor behavior relaxed.

test-change.patch includes tracked test edits plus new independently added test files. patch-manifest.json hashes every proposed source/test path. Read earlier per-prompt findings and the cumulative handoff before selectively applying; preserve original user configuration. New tests are not included by ordinary git diff until added, so the generated patch includes them explicitly. Candidate commit remains null. After Claude integrates accepted changes, provide the resulting committed SHA and rerun this review; no auto-merge/deployment.
''')
write('13-unresolved-blockers.md', '''# Release blockers and next action

1. **P99-R1 / integrated revision BLOCKED:** claude still equals the pinned parent with dirty user config; review proposals are uncommitted in codex-review. User config excluded. Claude-stop/commit precondition not established. Review/apply accepted exact patches on claude, preserve user work, provide new SHA and independently rerun. Do not describe candidate results as integrated claude success.
2. **P99-R2 / verifier P1 OPEN:** universal independent host receipt authority, caller replay claims, selected-target binding, conflicting UI completion and native hook/process lifetime acceptance. Narrow guards and uncertain-send backend feedback are fixed locally; full authority/physical truth is not established.
3. **P99-R3 / cloud P1 OPEN:** caller-declared synthetic provenance is not proof of generic semantics. Trusted provenance + adversarial semantic private-context outbound oracle required. No cloud/private account activation as a workaround.
4. **P99-R4 / inherited dependency/security gates:** approved mutable model tag/size transport, staged venv executable relocation, immutable execution-lock/artifact race, full advisory/license reachability, native engine/WSL/principal/concurrency/service coverage remain. Ten current consistency checks do not close these. No install/download authorization implied.
5. **P99-R5 / full E2E BLOCKED:** all 26 revised P37 user journeys retain unmet full-acceptance requirements; zero full live integrations certified. Physical mic/TTS/GPU/preemption, fresh training, real accounts/native apps, OpenViking/Docker/Ollama, all feature-off combinations, peak resources/latency and actual version rollback need approved disposable environments. Read individual P37 case dispositions and all prior handoff sections.
6. **P99-R6 / completeness:** 1,184 original planned IDs plus revised behaviors are not all individually reimplemented/live-proved. ID matches do not prove expected behavior equivalence. Exact exclusions and skips remain visible. No exhaustive whole-code vulnerability/semantic audit or type-checker run claimed.
7. **P99-R7 / V2-003 / IR-004 OPEN P2:** real >260-character lab working directory fails on both sources before Git starts (WinError 267). Extended cwd and Git -C alternatives failed. Ordinary short lab works; use explicit shorter owned lab_root/checkout. Full transparent long-cwd support not fixed. No global settings, silent move or cleanup of user paths.

Isolated readiness remains repair_required. Earlier 31–37 blockers persist until independently closed. No deployment.
''')
write('14-rollback-and-reproduction.md', '''# Reproduction and rollback

Use existing installed main Python. `run_suite.py --root <audit-app> --mode full --junitxml=<absolute-output> -q` executes the final selection. Run the same script with detached pinned app and --mode boundary after adding only the independent test overlay; production source stays pinned. Pinned prior findings use pytest test_independent_review.py, test_windows_commands.py and P06 lab ownership test. `mutate.py` uses only the detached disposable checkout and restores tracked source; `run_journeys.py`, `environment.py`, `corpus.py`, and `collect.py` save evidence. No setup/install command.

Harness explicitly sets audited app cwd, existing installed skills interpreters, original Hermes metadata only for the audit root, and explicit existing LocalGithub dependency path when no explicit path is supplied. Explicit nonexistent paths still fail tests. These are test configurations, not production default-path repairs. See full-selection.json and artifact scripts for exact files/nodes. Retain initial failures/superseded partial run, never count them as final success.

Review source-only.patch/test-change.patch and manifest before integration. Reverse only accepted narrow hunks after checking current hashes; preserve prior repairs, user config and all audit originals. No reset/clean, automatic merge, package uninstall or uncertain-write replay. Detached audit checkout retains test overlays and can be inspected; it was not deleted. Actual package/version rollback not performed. Repeat final suite/readiness after any accepted change.
''')
write('15-final-verdict.md', f'''# NOT READY FOR DEPLOYMENT

2026-10-20. Audited pinned claude `{BASE}` plus a separately hashed **uncommitted codex-review candidate**. Claude integration/stop precondition remains unmet; live dirty configuration excluded. Candidate commit: null; source-only.patch and test-change.patch are the reviewable changes.

**Candidate final relevant regression: {headline}.** Same boundary corpus: pinned 64 FAIL / 15 PASS / 1 SKIPPED; candidate 79 PASS / 1 SKIPPED. Fresh pinned prior-finding checks: 33 PASS. Six passing mutation controls reject all six actual violations with assertion failures. Ten existing environment consistency checks pass without installing anything. Overlapping/staged runs are not summed.

The full selected suite itself passed {main_final['PASS']} tests with {main_final['SKIPPED']} skips. One distinct additional deep-lab check fails on both pinned and candidate source: Windows rejects the >260-character process working directory before Git starts. Both attempted invocation alternatives failed; IR-004 is reopened for this P2 boundary. Use a shorter explicit owned lab_root/checkout; no silent relocation or OS mutation. This failure remains in the final count.

Three owned/simulated workflow journals provide real workbook worker readback and bounded mock-send/cloud postconditions. Thirty pinned/current fake observer-failure pairs improve cleanup 0/30 -> 30/30; no end-user speed claim. **Full live assistant integrations: 0. All 26 revised P37 full user journeys remain BLOCKED.** Pillars/additions/legacy paths are partially verified within stated component scope.

Open verifier authority, semantic cloud provenance, approved artifact transport/install races and physical/live/service/training gates prohibit deployment. Isolated launcher remains repair_required. No live personal-account write, private recording/cloud disclosure, package/model installation, fresh training, automatic merge or deployment. [Blockers](13-unresolved-blockers.md) · [Pillars](09-four-pillars-verification.md) · [Counts](run-summary.json) · [Mutation proof](mutation-results.json) · [Cumulative Claude handoff](../../../../docs/CLAUDE_HANDOFF.md).
''')

# Exact test patch includes untracked independently created tests.
tracked_patch = subprocess.check_output(['git', 'diff', BASE, '--', 'app/tests'], cwd=ROOT)
parts = [tracked_patch.decode('utf-8')]
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', 'app/tests'], cwd=ROOT).decode().splitlines()
for name in untracked:
    path = ROOT / name
    if path.suffix != '.py': continue
    parts.append(''.join(difflib.unified_diff([], path.read_text(encoding='utf-8').splitlines(keepends=True),
        fromfile='/dev/null', tofile='b/' + name)))
(OUT / 'test-change.patch').write_bytes('\n'.join(parts).encode('utf-8'))
changed_names = set(subprocess.check_output(['git', 'diff', '--name-only', BASE], cwd=ROOT).decode().splitlines())
manifest = {name: sha(APP / name) for name in source if 'app/' + name in changed_names}
for path in (APP / 'tests').glob('test_*.py'):
    name = path.relative_to(APP).as_posix()
    if 'app/' + name in untracked or 'app/' + name in changed_names:
        manifest[name] = sha(path)
dump('patch-manifest.json', manifest)

packet = 'artifacts/jarvis-audit/codex-v2-independent-review/' + OUT.name
def block(path, body, anchor):
    text = path.read_text(encoding='utf-8')
    wrapped = '<!-- prompt99-review -->\n' + body + '\n<!-- /prompt99-review -->\n\n'
    if '<!-- prompt99-review -->' in text:
        text = re.sub(r'<!-- prompt99-review -->.*?<!-- /prompt99-review -->\s*', lambda m: wrapped, text, flags=re.S)
    else:
        assert anchor in text
        text = text.replace(anchor, wrapped + anchor, 1)
    path.write_text(text, encoding='utf-8')
block(APP / 'README.md', f'''**2026-10-20 — Prompt 99 independent review: NOT READY FOR DEPLOYMENT.** Candidate final relevant regression: **{headline}**. Pinned a9b4ce1 boundary corpus: 64 failed/15 passed/1 skipped; uncommitted review candidate: 79 passed/1 skipped. Fresh original-finding retention: 33 passed. Six corrected safety mutants are rejected by assertion failures with passing controls. Ten installed environment consistency checks pass offline; pip-less workers use existing main pip's target-interpreter check.

Claude has not integrated the local P34–P37 proposals; original user configuration is excluded. Two legacy telemetry assertions now accept only the added bounded clock fields and check their types; no further production behavior changed in Prompt 99. The 1,184 original planned IDs and revised behaviors remain separate from executed tests. Three owned/simulated workflow journals are not full assistant E2E proof: **zero full live integrations certified; all 26 revised P37 journeys retain blockers**. Global verifier authority, semantic cloud provenance, approved artifact/dependency races and native/service/training acceptance remain incomplete. Isolated readiness: repair_required. [Final verdict]({packet}/15-final-verdict.md) · [Exact changes]({packet}/12-code-fixes-and-diffs.md) · [Cumulative Claude handoff](docs/CLAUDE_HANDOFF.md).''', '<!-- prompt37-e2e -->')
block(ROOT / 'README.md', f'''**2026-10-20 — Prompt 99 independent review: NOT READY FOR DEPLOYMENT.** **{headline}** on the uncommitted review candidate; integrated claude verification and full live E2E remain blocked. Six safety mutation controls discriminate deliberate violations. [Evidence](app/{packet}/15-final-verdict.md) · [Application scope](app/README.md) · [Cumulative Claude handoff](app/docs/CLAUDE_HANDOFF.md).''', '<!-- prompt37-e2e -->')
handoff = APP / 'docs/CLAUDE_HANDOFF.md'
text = handoff.read_text(encoding='utf-8')
section = f'''## Prompt 99 - final independent review and repair handoff

**2026-10-20: NOT READY FOR DEPLOYMENT.** Pinned claude/parent {BASE}; candidate remains uncommitted codex-review. User's live config excluded, Claude-stop/integrated-commit precondition unverified. [Verdict](../{packet}/15-final-verdict.md), [source patch](../{packet}/source-only.patch), [test patch including new files](../{packet}/test-change.patch), [manifest](../{packet}/patch-manifest.json), [ledger](../{packet}/05-findings-ledger.csv), [counts](../{packet}/run-summary.json), [all blockers](../{packet}/13-unresolved-blockers.md).

Final distinct candidate checks: **{headline}**. Full selected suite {main_final['PASS']} pass/{main_final['SKIPPED']} skip plus one separate failed deep-lab test. **P99-R7 / V2-003 / IR-004 OPEN P2:** both pinned and candidate reject a >260-character working directory before Git starts (WinError 267). Extended cwd and short-cwd Git -C alternatives failed; ordinary short lab passes. Use shorter explicit owned lab_root/checkout; no silent relocation, OS change or user-file cleanup. Deep-location acceptance remains blocked.

Same boundary corpus pinned: 64 fail/15 pass/1 skip; candidate: 79 pass/1 skip. Fresh original-finding bounded checks: 33 pass; the additional failed long-cwd check reopens IR-004. Ten environment consistency checks pass, including read-only target-pip checks for two pip-less workers. Six valid safety mutations killed with assertion failures and passing controls, tracked disposable source restored. Initial wrong-cwd/missing dependency routes and two stale clock allow-lists diagnosed; corrected preflight 33 pass and final full rerun. Two test assertions strengthened; no further production changes in V2. Earlier P34–P37 proposals still require integration on claude.

Original test pack/Master found at the historical path; 1,184 IDs and all 37 original/seven revised prompts indexed by ID+behavior. Earlier reports claiming Master unavailable retain their historical context. 5,116 parent artifacts unchanged. Three fresh owned/simulated journals and 30 paired cleanup fixtures provide bounded postconditions, not live assistant certification. Full live integrations 0; all 26 revised P37 journeys remain blocked.

**Carry-forward for Claude:** P99-R1 integrate accepted exact patches, preserve user config and provide committed SHA for new audit; P99-R2 bind host verifier/replay receipts and native targets/status/hook lifetime; P99-R3 independently establish cloud synthetic provenance; P99-R4 resolve approved transport/lock/venv/advisory/principal/concurrency gates; P99-R5 stage approved disposable native/voice/GPU/service/account/training acceptance; P99-R6 prove expected behavior per original/revised case, all flags, resources and full regression scope. Do not install, download, activate accounts, record private data, publish or replay writes to clear blockers without the required authorization. Keep every older unresolved section below until independently closed. No automatic merge/deployment. Stop at this review boundary.

'''
if '## Prompt 99 -' not in text: text = text.replace('## Prompt 37', section + '## Prompt 37', 1)
handoff.write_text(text, encoding='utf-8')
write('README.md', '[Independent V2 verdict](15-final-verdict.md). All other reports, scripts, raw observations and exact patches in this dated packet are supporting evidence; prior originals remain immutable.')
index = OUT.parent / 'README.md'
index.write_text(f'# Codex V2 independent review\n\n[2026-10-20 pinned a9b4ce1 review]({OUT.name}/15-final-verdict.md): NOT READY FOR DEPLOYMENT.\n', encoding='utf-8')
subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
dump('validation.json', {'parent_artifacts_rechecked': len(parents), 'parent_artifacts_changed': 0,
    'production_hashes_unchanged_during_V2': True, 'mutation_controls': 6, 'mutation_kills': 6,
    'source_restored': True, 'candidate_commit': None, 'git_diff_check': 'PASS'})
print(headline)
