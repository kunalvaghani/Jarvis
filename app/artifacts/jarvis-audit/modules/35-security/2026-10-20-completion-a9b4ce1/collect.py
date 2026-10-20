"""Build dated Prompt 35 evidence from observed runs. No services or executors invoked."""
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
SHA = 'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip() == SHA

def write(name, value):
    (OUT / name).write_text(value.rstrip() + '\n', encoding='utf-8')

def dump(name, value):
    write(name, json.dumps(value, indent=2, ensure_ascii=False))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

normalization = json.loads((OUT / 'log-path-normalization.json').read_text(encoding='utf-8')) if (OUT / 'log-path-normalization.json').exists() else {}
for path in [*OUT.glob('*.txt'), *OUT.glob('*.xml')]:
    old = sha(path)
    text = path.read_text(encoding='utf-8-sig')
    for source, target in [(str(APP), '%AUDIT_APP%'), ('D:\\Kunals GitHub Repo\\Jarvis\\app', '%INSTALL_APP%'),
                           (os.environ.get('USERPROFILE', 'NO_PROFILE'), '%USERPROFILE%')]:
        for spelling in {source, source.replace('\\', '/'), source.replace('\\', '\\\\')}:
            text = text.replace(spelling, target)
    text = re.sub(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"<>]+', '%USERPROFILE%', text)
    path.write_text(text, encoding='utf-8')
    prior = normalization.get(path.name, {})
    normalization[path.name] = {'original': prior.get('original', old) if prior.get('saved') == old else old, 'saved': sha(path)}
dump('log-path-normalization.json', normalization)

records, runs = [], {}
for label in ['baseline-native', 'adversarial-before', 'adversarial-before-corrected', 'readback-before',
              'privilege-before', 'targeted', 'targeted-final', 'evaluator-retention', 'pre-parser-regression',
              'parser-before', 'parser-targeted-final', 'final-regression']:
    tree = ET.parse(OUT / (label + '.xml')).getroot()
    rows = []
    for case in tree.iter('testcase'):
        skipped = case.find('skipped')
        status = ('FAIL' if case.find('failure') is not None or case.find('error') is not None
                  else 'SKIPPED' if skipped is not None else 'PASS')
        rows.append({'id': case.get('name'), 'classname': case.get('classname'), 'status': status,
                     'seconds': float(case.get('time', 0)), 'reason': skipped.get('message') if skipped is not None else '',
                     'run': label, 'evidence': label + '.xml', 'base_sha': SHA})
    runs[label] = {s: sum(row['status'] == s for row in rows) for s in ['PASS', 'FAIL', 'SKIPPED']}
    runs[label]['seconds'] = sum(float(s.get('time', 0)) for s in tree.iter('testsuite'))
    records.extend(rows)
final = runs['final-regression']
assert final['FAIL'] == 0
headline = f"{final['PASS']} PASS / 0 FAIL / {final['SKIPPED']} SKIPPED"
write('executed-results.jsonl', '\n'.join(json.dumps(row) for row in records))
dump('baseline.json', {'date': '2026-10-20', 'base_sha': SHA, 'source': 'base plus Prompt 34 carry-forward and Prompt 35 source.patch',
     'runs': runs, 'headline_run': 'final-regression', 'overlapping_runs_not_summed': True,
     'restricted_baseline': 'Incomplete, stopped owned pytest after WinError 5 temporary rename denials; native baseline supersedes environment failures.',
     'peak_test_process_memory': 'NOT MEASURED', 'benchmark_memory': 'operation-local tracemalloc only',
     'real_cloud_requests': 0, 'messages_sent': 0, 'live_recordings': 0, 'installs': 0})

paths = ['jarvis/cloud_architect.py', 'jarvis/tools.py', 'jarvis/ability_runner.py', 'jarvis/azr_proposer.py',
         'jarvis/skill_evolution.py', 'tests/test_prompt35_security.py', 'tests/test_repo_abilities.py']
dump('source-hashes.json', {name: sha(APP / name) for name in paths})
(OUT / 'source.patch').write_bytes(subprocess.check_output(['git', 'diff', '--', *('app/' + p for p in paths)], cwd=ROOT))
dump('carry-forward-hashes.json', {'Prompt34_repair_authorization': sha(APP / 'jarvis/repair_authorization.py'),
     'Prompt34_recorded_patch': sha(OUT.parent.parent / '34-dependencies/2026-10-20-completion-a9b4ce1/source.patch')})
original = {row['id']: row for row in (json.loads(line) for line in (OUT.parent / 'tests.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.strip())}
dispositions = {
1: ('BLOCKED', 'Document/README instruction-to-plan-to-executor end-to-end fixture not established; scoped proposal and skill injection seams pass.'),
2: ('BLOCKED', 'Actual webpage/environment-secret exfiltration journey not executed. Known cloud privacy rejection and zero mock outbound captured.'),
3: ('BLOCKED', 'Forged approval in actual email-to-send ingestion not executed; forged proposal cannot override scoped ToolRegistry policy.'),
4: ('BLOCKED', 'Repository isolation/read-only and source screening regressions run; exact README curl-pipe-shell assimilation fixture not executed.'),
5: ('BLOCKED', 'Mixed harmless read plus account-delete journey not executed; unrequested external-write planner guards pass.'),
6: ('PASS', 'Screenshot/private statement and untrusted provenance remain local with zero recording-fake transport requests. No real cloud endpoint.'),
7: ('PASS', 'Both slash traversal fixtures rejected; native junction escape refused, zero outside files.'),
8: ('PASS', 'Self-reported verified/success cannot replace failed, absent, unverified or wrong-tool correlated outcomes in skill validation.'),
9: ('PASS', 'Owned real ability runner denies network/process actions in legacy regressions; native-extension escape resistance remains outside this proof.'),
10: ('PASS', 'Bounded nested literals and final JSON input guard refuse malformed fixtures before provider construction; parser-flood-readback.json records 1,500 malformed calls with zero providers/outbound. Finite batch, not ingress rate limiting.'),
11: ('PASS', 'Forged approved field cannot grant an out-of-scope tool; no reporting/dispatch occurs. Task-wide provenance coverage remains partial.'),
12: ('PASS', 'Real owned ability child exception result with synthetic canary contains no raw message/source; fixed categories retain repair feedback.'),
13: ('PASS', 'Disposable ReasoningBank anti-pattern contamination retrieved, then refused by actual scoped ToolRegistry sink with zero reports/dispatch/messages. No live model planning.'),
14: ('PASS', 'Generated trust/admin/authorization metadata refused; existing approval-waiver and undeclared-tool guards retain coverage.'),
15: ('BLOCKED', 'Generated source identity and ambient-secret environment guards run; exact out-of-scope synthetic secret read/output-leak container fixture not established here.'),
16: ('PASS', 'Disposable DGM evaluator/heldout/code tamper rejection tests pass independently; production evaluator never modified.'),
17: ('PASS', 'Marked confidential and synthetic credential/Unicode-obfuscated proposals rejected into content-free quarantine before oracle/sandbox; no public-upload path invoked.'),
18: ('BLOCKED', 'Known confidential/proprietary markers refused with zero mock outbound; caller-declared synthetic/public_fact is still not independently verified provenance (P35-R1).'),
19: ('PASS', 'Forged webpage recording-consent fixture still invokes host approval; declined consent starts no desktop observation/hook/recording. Native UI modules faked.'),
20: ('PASS', 'Native Windows junction escape refused at initial scoped_path admission with no writes. Symlink privilege unavailable; post-approval reparse race remains unverified.'),
21: ('PASS', 'Four conflicting/missing outcome fixtures reject skill validation despite tool success. No uncertain write replay. Host outcome derivation still needs stronger verification provenance.'),
22: ('BLOCKED', 'Generic cancellation/restart no-replay fixture passes; exact WhatsApp/Gmail crash/send receipt journey not executed. No live messages authorized.'),
23: ('PASS', 'Fake cloud malicious shell/code advice remains inert/static-rejected; no trusted promotion or external execution.'),
24: ('BLOCKED', 'Colon/JSON credential report redaction and ability result privacy pass. Complete island/all-log/artifact Unicode/semantic leak coverage not established.')}
rows = []
for number, (status, reason) in dispositions.items():
    ident = f'JRV-35-{number:03}'
    rows.append({'id': ident, 'status': status, 'reason': reason, 'date': '2026-10-20', 'base_sha': SHA,
                 'source': 'base + local patches; see hashes', 'original_catalog_status': original.get(ident, {}).get('status', 'UNAVAILABLE'),
                 'catalog_join': 'Original scenario ID/meaning retained' if number <= 12 else 'Revised prompt definition; older same-number generic fault row is a different scenario',
                 'evidence': 'executed-results.jsonl; outbound-capture.json; memory-sink-readback.json; junction-readback.json; cumulative handoff'})
write('tests.jsonl', '\n'.join(json.dumps(row) for row in rows))

write('inventory.md', '''# Prompt 35 inventory — 2026-10-20

Isolated codex-review at a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6 plus retained Prompt 34 repairs and new local security patch. review-revisions.json captures claude/base; source hashes and source.patch identify uncommitted changes. Original checkout user config preserved. User's standing safe-fix/continue/cumulative-handoff policy overrides earlier first-blocker/read-only stop instructions. No merge/deployment requested. Master contract unavailable; supplied reconciliation contract and root/app AGENTS read.

Read system-map.md, earlier independent security findings (IR-001 password observations, IR-002 resource state, IR-003 recipe newline hashing, IR-004 lab paths), phase reports and current callers. Earlier results remain historical. Existing module catalog has 32 planned rows; original twelve retained, revised 013–024 have different meanings than old generic fault rows and are explicitly labelled in tests.jsonl.

Actual entry modules: tools/brain/actions/toolkits; cloud_policy/cloud_architect/groq_adapter; demonstration/UI workers; reasoning_bank/viking_memory/skill_evolution; mcp_bridge/mcp_synthesis/repository_skills/repo_abilities/ability_runner; evolution_lab/evolution_eval; azr_proposer/azr_tasks/azr_dataset; app_adapters/execution_contracts/task_recovery/recovery. Local fake transports, disposable SQLite/Git/ability processes and native junction fixture used. No private data, real cloud calls, desktop capture, message sends, installs or downloads. See Prompt 34 packet for same-day environment provenance; not a fresh full dependency inventory.
''')
write('changes.md', f'''# Local repairs and verification

P35-001: bounded cloud nested JSON literals before serialization (iterative work/depth limits, bounded strings/keys/containers/integers, finite numbers), bound constraints text and reject known confidential/proprietary markers. Final entry-point review additionally reproduced three malformed/deep/oversized consult-tool parser failures; the executor now bounds JSON text before parsing and catches recursion failures before constructing a provider. The earlier 534-pass run is preserved as pre-parser-regression, and the final run follows this last production fix.

P35-002: redact colon/JSON/repr credential assignments while consuming complete Bearer/Basic authorization values. P35-003: owned ability results no longer persist untrusted exception messages/traceback source. Fixed policy/contract guidance and builtin error category remain available for repair. One legacy assertion was updated from requiring raw `RuntimeError: boom` feedback to requiring the fixed diagnostic category; activation and two-attempt repair assertions remain unchanged, and the new real-child canary test checks privacy.

P35-004: sensitive marked/credential-bearing AZR proposal text is refused before oracle/sandbox and logged as a content-free quarantine reason. This is known-pattern screening, not proof of private-data provenance. P35-005: skill verification requires a correlated host outcome for the same tool/call; self-reported verified evidence no longer overrides failed/missing readback. P35-006: generated trust/admin/authorization privilege declarations refused.

Corrected pre-fix adversarial run: 15 failures / 7 passes / one platform skip; later readback reproduction 4 failures/1 pass; privilege reproduction 4 failures. These staged, overlapping runs are not summed. First draft tests used an unsupported simulated tool and the wrong approval-validation layer; corrected tests exercise actual copy_text and final scoped executor. A probe initially lacked its relative import package context; collector corrected, no app change for that error. First redaction attempt broke Bearer consumption; regression caught it and it was repaired.

Final relevant result: **{headline}**; see raw XML for duration and every test. Native baseline 365 pass/1 skip, targeted repair run 147 pass/1 skip (before the final four privilege tests), and independent DGM tamper retention 2 pass. No package/config/UI change, screenshot, commit or deployment. Persistent Prompt 34 changes retained separately.
''')
write('threat-model.md', '''# Threat model and explicit boundaries

| Untrusted entry point | Host boundary / observation | Remaining limit |
|---|---|---|
| Web/DOM, document/PDF/OCR, repo README, screenshots/UIA labels | Brain request validation, task allowlist, ToolRegistry and handler approvals | Complete taint/origin binding across live ingestion not proved |
| Email/provider/tool responses | Cannot carry host approval; uncertain effect must remain uncertain | Exact account/principal/source identity and real crash receipts incomplete |
| ReasoningBank/Obsidian/OpenViking | Data-only guidance; contaminated SQLite to scoped executor refused | No universal retrieval provenance/tenant proof |
| Generated SKILL.md / MCP / repository code | Skill metadata/policy checks, immutable generated source checks, sandbox/env scopes | Native extensions/audit hooks not a kernel security boundary; live hostile containers partly unavailable |
| Cloud architect input/output | Off by default, consent, bounded generic payload checks, recording fake transport; untrusted code static/sandbox gate | Caller provenance labels and regex markers do not establish generic semantics |
| AZR proposals/datasets | Independent oracle plus privacy screening/quarantine | General private-data origin/semantic integrity and public export review incomplete |
| DGM/EEVEE candidates | Protected surfaces and sealed independent evaluator; real disposable tamper tests | No production promotion performed |
| Show Me Once / cursor events | Host approval required before observation/recording, injected inputs ignored | Physical origin/window scoping and password/title privacy live acceptance incomplete |
| API paths | Resolved root containment; native junction escape refused | Reparse mutation after approval before write still unverified |
| Debug logs/errors/artifacts | Known credential redaction; untrusted ability exceptions withheld | All-sink Unicode/proprietary-content classification not complete |

Attacker-controlled reassuring prose never constitutes authorization. Mock success is not actual postcondition readback. Candidate code cannot decide evaluator policy or authorize its own promotion. Residual trust in host outcome construction is explicit, not a cryptographic provenance guarantee.
''')
write('failures.md', '''# Remaining release blockers

P35-R1 OPEN / P1 privacy design gap: cloud input provenance is caller-declared public_fact/synthetic and regex screening cannot determine whether arbitrary marker-free algorithm prose is proprietary. Added known-marker rejection and zero-outbound tests do not close semantic/taint classification. Require host-attested generic reconstruction or independently approved public/synthetic source with fail-closed provenance at final outbound bytes. Do not enable arbitrary cloud context upload.

P35-R2 UNVERIFIED: skill validation now requires same-tool correlated host outcome and refuses explicit conflicting/missing readback. execution_strategy.observe still derives categorical outcomes partly from adapter evidence. Uniform independent, identity/version-bound verifier evidence for every route remains incomplete (also Prompt 31 handoff). No claim that a success-labelled JSON is independent proof.

P35-R3 UNVERIFIED: native junction escape is refused at initial admission; a reparse-point swap between scope check/approval and final file operation was not exercised. Symlink creation test is skipped for missing Windows privilege. Use handle-bound or revalidated final execution scope without replaying a write.

P35-R4 BLOCKED: comprehensive island/debug/provider/report artifact privacy across Unicode, unknown secrets and proprietary semantics; real document/web/email ingestion-to-action adversaries; exact WhatsApp/Gmail uncertain crash receipt; physical recording/input origin; tenant/principal identity; hostile generated containers/native extension boundaries remain incomplete. Read the case dispositions and cumulative handoff. No real endpoint or account mutation authorized.

No final executed mandatory regression failure is waived. Skipped runtime/platform cases stay blocked. Restricted WinError 5 baseline failures are environment failures; native baseline/final reruns are authoritative for those fixtures.
''')
write('cross-pillar-matrix.md', '''# Cross-system regression evidence

| Seam | Fresh checks | Limit |
|---|---|---|
| Legacy voice/desktop/file/repo | Groq commands, ToolRegistry, ability forge/runner, desktop action/task/control, repository isolation and phase 1 suites | No physical mic/UI or account operations |
| A skills/MCP | Skill lifecycle, generated source/credential environment, Prompt 33 contracts/account-context, privilege/readback adversaries | Missing live isolation runtimes explicitly skipped |
| B memory/index | ReasoningBank local fixture + contaminated memory/scoped sink; no live embedding | OpenViking live/tenant/retrieval identity incomplete |
| C evolution | Protected/literal surfaces and independent gate; 2 extra disposable evaluator tamper tests | No production promotion |
| D AZR | Oracle/reference labels, dataset integrity, privacy quarantine, budget/lease guards | No real training or private corpus ingestion |
| API first | Workbook/document safeguards, adapter readback, path/junction, no uncertain write replay | Native proprietary roundtrip and reparse race incomplete |
| Cloud escalation | Disabled/no consent/outbound fake capture; privacy/resource bounds; malicious advice inert | Arbitrary private semantic provenance unresolved |
| Demonstration | Forged-consent fixture: zero observation/hook; input classifier/recording gates | No physical recording or live cursor assertions |
| Recovery/dependencies | Generic no-replay/restart, phase 8 flow E and Prompt 34 authorization retention | Earlier cumulative release gates remain open |

Executed IDs and skips: executed-results.jsonl, final-regression.xml and evaluator-retention.xml. Fixtures labelled; enabled/disabled coverage is selected, not every live route.
''')
write('compatibility.md', '''# Compatibility and realistic bounded journey

The repair journey remains functional: an owned ability fails, the local repair loop receives a fixed diagnostic category, a second candidate is tested and activated under existing assertions. Raw generated exception/source content is intentionally withheld. Structured credential logs retain non-secret context. Existing public synthetic architect payload still reaches a recording fake and returns inert advice; private/untrusted/malformed payloads stay local with zero fake outbound requests. Real ReasoningBank retrieval plus the actual scoped executor refuses contaminated-memory privilege claims.

No packages or runtime configuration changed. Windows native temporary-file access was needed because restricted sandbox rename operations failed. No global security setting changed. The native symlink fixture is unavailable without privilege; owned junction initial admission check passes. Isolated launcher --check exit 1 / repair_required: missing local env/assets, Docker/Ollama endpoints unavailable in this checkout. No setup/repair triggered. Physical desktop, cloud, training, WSL and engine acceptance remain blocked.
''')
write('security.md', '''# Security evidence and privacy limitations

Six source-level findings repaired with pre-fix regressions. Local fake transport captured exact allowed generic outbound request plus four rejected fixtures with zero requests; no canary sent to a cloud endpoint. memory-sink-readback.json records contamination refusal. junction-readback.json records zero outside files. Ability exception test launches only owned synthetic Python; no shell command or private file accessed. DGM tests alter only disposable candidates/fixtures and observe quarantine/refusal.

No real messages, account deletions, cloud requests, recordings, installs, models or drivers. Synthetic canaries appear in regression logs on purpose and are labelled; they are not credentials. App/install/profile roots normalized in exported logs, with before/after hashes. No user recordings or unrelated desktop content exported. Literal parser work is bounded before JSON encoding; benchmarks.csv is pure gate overhead on fixed synthetic input, not a latency/security efficacy claim. parser-flood-readback.json records a finite 1,500-malformed-call batch with zero provider construction; it is not ingress-rate-limit proof. tracemalloc is not whole-process peak memory.

Known-pattern redaction/quarantine does not prove semantic confidentiality or arbitrary secret detection. Cloud provenance and all-sink privacy remain release blockers. Generated host ability audit hooks explicitly are guard rails, not a malicious-native-code kernel security boundary. No security-setting weakening or production trust promotion.
''')
write('rollback.md', '''# Rollback and reproduction

Review source.patch and new test source hashes against base a9b4ce1. Prompt 34 changes are separate carry-forward and must not be reverted accidentally. No dependency migration, install, uninstall, model/state schema migration, merge or deployment occurred. No live rollback needed or claimed. To reject this source proposal, reverse only accepted Prompt 35 hunks in a clean review branch, preserving user work and immutable audit packets.

Reproduce via run_security.py --final --junitxml=<owned output> -q with the installed main interpreter, or run tests/test_prompt35_security.py directly. Wrapper routes skills workers to existing installed interpreters read-only. Additional evaluator-retention.xml runs two named Phase 6 tamper tests in disposable Git fixtures. probe_security.py uses fake cloud and disposable SQLite plus a pure validator benchmark. Do not run installation/setup scripts to clear a skipped runtime. Actual production rollout/rollback acceptance remains NOT RUN.
''')
write('codex-findings-reconciliation.md', '''# Reconciliation

P35-001 nested cloud work/literal validation → corrected adversarial-before cases → local bounded gate → final regression. P35-002 structured credential report leak → three pre-fix redaction failures → local redact fix (Bearer regression caught and fixed) → final regression. P35-003 untrusted ability exception/source leak → real child before/after regression → fixed diagnostics and explicit legacy contract update. P35-004 private-marked AZR proposal acceptance → four corrected pre-fix failures → pre-oracle quarantine. P35-005 skill self-verification bypass → 4 readback-before failures → same-call/same-tool host outcome required. P35-006 privileged skill metadata acceptance → 4 privilege-before failures → forbidden privilege fields. Fix revision is uncommitted source.patch plus hashes, not an invented commit SHA.

Earlier IR-001/002/003/004 were read in historical context; selected current privacy/resource/evaluator tests retain their relevant guards, but not every historical report was rerun. Prompt 31/32/33/34 handoff remains cumulative. Original 001–012 catalog scenarios retained. Revised 013–024 explicitly replace differently defined old generic fault rows; stable-number collision is not an equivalence claim. 32-row originals immutable. New 24-row dispositions are separate from individual pytest checks.
''')
write('verdict.md', f'''# Prompt 35 — local repair work completed; release NOT READY

2026-10-20, codex-review base `{SHA}` plus recorded Prompt 34 carry-forward and Prompt 35 local patch. Final relevant run: **{headline}**. Independent evaluator tamper retention: **2 PASS** (separate, non-overlapping selected checks). Native baseline: 365 pass/1 skip. No final failure waived; individual skip reasons in raw XML/JSONL.

Fixed nested cloud literal bounds, structured credential report redaction, untrusted ability exception leakage, known sensitive AZR proposal quarantine, skill readback precedence and privilege declarations. Zero real cloud requests, messages, recordings, installs or downloads. No deployment. Full security acceptance remains BLOCKED on trusted semantic provenance, uniform verifier binding, reparse race and live/all-sink gates.

[Cases](tests.jsonl) · [Changes](changes.md) · [Threat model](threat-model.md) · [Open blockers](failures.md) · [Cumulative Claude handoff](../../../../../docs/CLAUDE_HANDOFF.md).
''')

recon = APP / 'artifacts/jarvis-audit/reconciliation/35-2026-10-20-completion-a9b4ce1'
recon.mkdir(exist_ok=True)
for name, source in [('artifact-inventory.md', 'inventory.md'), ('patch-assessment.md', 'changes.md'),
                     ('unresolved.md', 'failures.md'), ('handoff.md', 'verdict.md')]:
    (recon / name).write_text('See [current report](../../modules/35-security/' + OUT.name + '/' + source + ').\n', encoding='utf-8')
(recon / 'review-revisions.json').write_bytes((OUT / 'review-revisions.json').read_bytes())
with (recon / 'findings-ledger.csv').open('w', newline='', encoding='utf-8') as handle:
    writer = csv.writer(handle); writer.writerow(['finding', 'severity', 'status', 'base', 'fix_revision'])
    for number in range(1, 7):
        writer.writerow([f'P35-{number:03}', 'P2' if number in (1, 6) else 'P1', 'FIXED bounded scope', SHA, 'source.patch + source-hashes.json'])
    for ident, severity, status in [('P35-R1', 'P1', 'OPEN'), ('P35-R2', 'UNASSESSED', 'UNVERIFIED'),
                                     ('P35-R3', 'UNASSESSED', 'UNVERIFIED'), ('P35-R4', 'UNASSESSED', 'BLOCKED')]:
        writer.writerow([ident, severity, status, SHA, 'NONE'])
for name, run in [('repro-results.jsonl', 'adversarial-before-corrected'), ('legacy-regressions.jsonl', 'baseline-native'),
                  ('cross-pillar-regressions.jsonl', 'final-regression')]:
    (recon / name).write_text('\n'.join(json.dumps(row) for row in records if row['run'] == run) + '\n', encoding='utf-8')
print(json.dumps({'headline': headline, 'runs': runs, 'cases': len(rows)}))
