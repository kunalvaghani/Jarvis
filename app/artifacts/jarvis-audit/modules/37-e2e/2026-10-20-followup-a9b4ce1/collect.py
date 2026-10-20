"""Fresh P37 follow-up, preserving prior evidence and unchanged-source regression lineage."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
V2 = APP / 'artifacts/jarvis-audit/codex-v2-independent-review/2026-10-20-a9b4ce1'
PREVIOUS = OUT.parent / '2026-10-20-completion-a9b4ce1'
PIN = 'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name, body): (OUT / name).write_text(body.rstrip() + '\n', encoding='utf-8')
def dump(name, data): write(name, json.dumps(data, indent=2))
assert subprocess.check_output(['git', 'rev-parse', 'claude'], cwd=APP).decode().strip() == PIN
source = json.loads((V2 / 'candidate-source-hashes.json').read_text(encoding='utf-8'))
assert all(sha(APP / name) == digest for name, digest in source.items())
patch = json.loads((V2 / 'patch-manifest.json').read_text(encoding='utf-8'))
assert all(sha(APP / name) == digest for name, digest in patch.items())
dump('source-hashes.json', source)
dump('prior-evidence-hashes.json', {p.relative_to(APP).as_posix(): sha(p)
    for folder in [PREVIOUS, V2] for p in folder.iterdir() if p.is_file()})
normal = {}
for path in [*OUT.glob('*.txt'), *OUT.glob('*.xml')]:
    before = sha(path)
    body = path.read_text(encoding='utf-8-sig')
    for start, target in [(str(APP), '%AUDIT_APP%'), ('D:\\Kunals GitHub Repo\\Jarvis\\app', '%INSTALL_APP%'),
                          (os.environ.get('USERPROFILE', 'NO_PROFILE'), '%USERPROFILE%')]:
        for spelling in {start, start.replace('\\', '/'), start.replace('\\', '\\\\')}:
            body = body.replace(spelling, target)
    body = re.sub(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"<>]+', '%USERPROFILE%', body)
    path.write_text(body, encoding='utf-8')
    normal[path.name] = {'original_sha256': before, 'saved_sha256': sha(path)}
dump('log-normalization.json', normal)
tree = ET.parse(OUT / 'targeted.xml').getroot()
executed = [{'id': c.get('name'), 'classname': c.get('classname'), 'seconds': float(c.get('time', 0)),
    'status': 'FAIL' if c.find('failure') is not None or c.find('error') is not None else 'SKIPPED' if c.find('skipped') is not None else 'PASS'}
    for c in tree.iter('testcase')]
assert len(executed) == 38 and all(r['status'] == 'PASS' for r in executed)
write('executed-results.jsonl', '\n'.join(json.dumps(r) for r in executed))
journals = [json.loads(line) for line in (OUT / 'workflow-journals.jsonl').read_text().splitlines()]
assert len(journals) == 3 and all(row['status'] == 'PASS' for row in journals)
assert journals[0]['observed_postconditions']['independent_worker_readback'] == {'A1': 9, 'A2': '=A1*2', 'sheets': ['Budget']}
cases = [json.loads(line) for line in (PREVIOUS / 'tests.jsonl').read_text(encoding='utf-8').splitlines()]
for row in cases:
    assert row['status'] == 'BLOCKED'
    row['evidence'] = ['executed-results.jsonl', 'workflow-journals.jsonl', 'launcher-check.txt']
    row['followup'] = '2026-10-20; production and reviewed changed-test hashes identical to V2; no new implementation change.'
    if row['id'] == 'JRV-37-019':
        row['reason'] += ' V2-003/IR-004 also confirms WinError 267 when the lab working directory exceeds 260 characters; both attempted invocation workarounds failed. Use shorter explicit owned lab_root; no silent relocation.'
write('tests.jsonl', '\n'.join(json.dumps(row) for row in cases))
v2 = json.loads((V2 / 'run-summary.json').read_text(encoding='utf-8'))
dump('baseline.json', {'date': '2026-10-20', 'pinned_claude': PIN, 'candidate_commit': None,
    'fresh_targeted': {'PASS': 38, 'FAIL': 0, 'SKIPPED': 0}, 'fresh_journals': 3,
    'unchanged_production_files_verified': len(source), 'reviewed_source_test_manifest_verified': True,
    'retained_full_regression': v2['runs']['candidate-final'],
    'retained_distinct_deep_lab_failure': v2['runs']['deep-lab'],
    'full_suite_not_repeated': 'No source/test changes since V2 full relevant regression; independent fresh targeted and workflow readbacks, not a new full-run claim.',
    'full_E2E': {'PASS': 0, 'BLOCKED': 26}, 'physical_hooks_or_mic': 0, 'real_sends_or_cloud': 0})
write('inventory.md', f'''# Prompt 37 follow-up - 2026-10-20

Pinned claude {PIN}; uncommitted codex-review candidate. Original live checkout still has only its user config modification; untouched. Reviewed revised P37, root/app AGENTS, current system map and cumulative P37/V2 findings. Original Master/companion catalogue were located during V2; evidence now available, historical unavailable statements remain dated.

All 560 production Python hashes and V2 changed source/test manifest match. Existing P37 fixes retained; no new implementation edits or installed dependencies. Fresh targeted tests and three workflow journals collected in this new packet. Earlier packets remain immutable. Existing V2 full relevant regression remains applicable to these hashes; it was not rerun merely to repeat unchanged results.
''')
write('changes.md', '''# Changes

No production changes. Refreshed consent/cancel/failure lifecycle and uncertain-write task regressions (38 PASS), owned workbook/API/skill/lesson readback, simulated queued send/restart and recording-fake cloud advisory journals. Updated JRV-37-019 with the independently reproduced deep-lab working-directory limitation and carried it into the cumulative handoff. No defect invented or previously blocked live test promoted to PASS.
''')
write('failures.md', '''# Blockers

All 26 full P37 acceptance journeys retain unmet requirements. Global host verifier/replay authority, semantic cloud provenance and native target/hook lifetime remain open P1 scopes. Real mic/TTS/GPU/voice preemption, accounts/apps, training, Docker/Ollama/OpenViking, all flag combinations and actual rollback remain unverified or unavailable.

V2-003 / IR-004 is an additional OPEN P2 at the DGM seam: >260-character lab process working directory fails before Git starts (WinError 267), on pinned and candidate sources. Extended cwd and Git -C alternatives failed. Ordinary short owned lab passes; explicit shorter lab_root/checkout is the workaround, not a transparent repair. Do not relocate user data or alter OS policy automatically.

Fresh targeted checks have zero failures. Retained broad V2 run: 1,896 PASS / 139 SKIPPED, plus the distinct deep-lab FAIL. These runs are not summed with fresh 38 checks. Isolated launcher still repair_required. All old blockers remain in the cumulative handoff.
''')
write('cross-pillar-matrix.md', '''# Integration evidence

| Seam | Fresh observed result | Limit |
|---|---|---|
| Actions queue -> task state -> feedback -> restart | one mock send attempt, durable paused completion event, restart replay blocker | simulated Brain/speech event; native UI/account not proved |
| API strategy -> ToolRegistry -> worker -> CAPTURED/FIX -> lessons | workbook A1=9/formula preserved by separate worker, strategy/anti-pattern stored | simulated author/consent; native Excel/voice and semantic outcome improvement not proved |
| FailureRouter -> consent -> cloud advisory | recording-fake request once, no action/duplicate consultation | no real provider; semantic provenance OPEN |
| Show Me Once consent/start/pump/cancel/promotion | lifecycle and negative admission tests pass | fake hooks/window modules; physical process exit not proved |
| DGM lab / AZR / prior integrations | unchanged-source V2 cross-pillar/retention evidence retained | deep cwd fails; live training/hardware and full user journeys BLOCKED |

No new shared interface changed. Exact component calls are in workflow-journals.jsonl. Prior full regression is linked by source identity, not described as a fresh run.
''')
write('compatibility.md', '''# Compatibility

No new interface, dependency, service, runtime manifest or launcher change. Existing direct recording/replay and ordinary successful task results retain prior behavior. Native/live/model/service coverage and all feature-off combinations remain blocked; fresh launcher output documents missing isolated assets/services. Read-only dependency routing uses the existing installed interpreters, with source in the audit checkout. No setup or repair attempted.
''')
write('security.md', '''# Security

Only owned temporary workbook/SQLite/task fixtures and fake send/cloud/hook transports. No real messages, cloud requests, microphone, native hook, private desktop capture, training or installations. Actual workbook postconditions read by a separate worker; mock no-replay and consent guard assertions do not certify live integrations. P1 provenance/verifier/target gates remain open. Logs normalize local roots and preserve raw/saved hashes. Earlier evidence untouched.
''')
write('rollback.md', '''# Rollback / reproduction

No implementation change to reverse. To reproduce: use the original installed main Python from this audit app directory, run the installed-dependency runner with test_prompt37_e2e_boundaries.py, test_task_state.py and test_task_recovery.py; run run_journeys.py in this packet; run python -m jarvis.launcher --check. No install step.

Review/apply prior source/test patches on claude only after preserving user work. Source revision must be newly committed and independently reverified; no merge/deployment requested. Retain every earlier audit original, uncertain-write checkpoint and cancelled demonstration state. No reset/clean or blind action replay.
''')
write('codex-findings-reconciliation.md', '''# Findings reconciliation

P37-001..004 local proposed lifecycle/consent/admission/durable-feedback fixes remain unchanged; fresh focused tests pass. V2-001/002 test schema/harness corrections retained; current hashes match the previously full-tested candidate. IR-004/V2-003 reopened deep cwd limitation remains OPEN P2; exact failed checks and two attempted alternatives are in the V2 packet. No fix SHA exists: parent a9b4ce1 plus uncommitted reviewed patches.

P35/P36/P37 independent verifier/provenance P1 gates remain open. Native/user integration results remain BLOCKED. No finding closed from mock success alone. See cumulative handoff and original per-prompt/V2 ledgers for exact test IDs and historical SHA context.
''')
write('verdict.md', '''# Prompt 37 follow-up - NOT READY

2026-10-20. **Fresh focused regression: 38 PASS / 0 FAIL / 0 SKIPPED. Three owned/simulated journals PASS.** Workbook readback A1=9/formula retained; uncertain mock send remains paused with replay blocker; cloud advice fake remains consented/advice-only/deduplicated.

560 production hashes and reviewed source/test manifest unchanged. Retained V2 full selection: 1,896 PASS / 139 SKIPPED; separate deep-lab failure remains OPEN P2. No fresh full run claimed and overlapping checks not added. Thirty fresh paired fake-hook exception fixtures retain 0/30 pinned vs 30/30 current cleanup; synthetic safety cost, not assistant performance proof.

**Full user acceptance: 0 PASS / 26 BLOCKED.** Isolated readiness repair_required; Claude integration still pending. All verifier/provenance/native/live/service/training gates and the deep-path limit remain in the [Claude handoff](../../../../../docs/CLAUDE_HANDOFF.md). [Case dispositions](tests.jsonl) · [Fresh journals](workflow-journals.jsonl) · [Baseline/lineage](baseline.json). No deployment or merge.
''')
packet = 'artifacts/jarvis-audit/modules/37-e2e/' + OUT.name
def add(path, body, anchor):
    text = path.read_text(encoding='utf-8')
    marker = '<!-- prompt37-followup -->\n' + body + '\n<!-- /prompt37-followup -->\n\n'
    assert '<!-- prompt37-followup -->' not in text
    assert anchor in text
    path.write_text(text.replace(anchor, marker + anchor, 1), encoding='utf-8')
add(APP / 'README.md', f'''**2026-10-20 - Prompt 37 follow-up:** 38 fresh focused checks and three owned/simulated workflow journals pass. All 560 production hashes and reviewed source/test manifest match the V2 full-tested candidate, so the unchanged full suite was not repeated. All 26 full E2E journeys remain BLOCKED; live readiness/integration, verifier/provenance and deep-lab path limits persist. No implementation, package or service change. [Evidence]({packet}/verdict.md) · [Cumulative Claude handoff](docs/CLAUDE_HANDOFF.md).''', '<!-- prompt99-review -->')
add(APP.parent / 'README.md', f'''**2026-10-20 - Prompt 37 follow-up:** 38 focused checks and three bounded workflow journals pass; full E2E acceptance remains blocked. Source unchanged from V2. [Evidence](app/{packet}/verdict.md) · [Claude handoff](app/docs/CLAUDE_HANDOFF.md).''', '<!-- prompt99-review -->')
handoff = APP / 'docs/CLAUDE_HANDOFF.md'
text = handoff.read_text(encoding='utf-8')
section = f'''## Prompt 37 follow-up - unchanged source, refreshed checks

**2026-10-20:** claude still {PIN}; local review candidate uncommitted. **38 fresh focused checks PASS / zero fail or skip; three owned/simulated workflow journals PASS.** [Follow-up packet](../{packet}/verdict.md), [26 cases](../{packet}/tests.jsonl), [source and broad-run lineage](../{packet}/baseline.json). All 560 production hashes and V2 changed source/test hashes match; no new implementation change. Retained V2 broad run is 1,896 pass/139 skip plus the distinct deep-lab failure, not a fresh full rerun or summed count.

Workbook independent readback A1=9/formula preserved, provisional CAPTURED/FIX and lesson storage; one uncertain mock send produces paused completion and restart blocker; generic recording-fake cloud advisory sends once and performs no action. Native hook/voice/UI/accounts not activated. All 26 full user journeys remain BLOCKED; isolated readiness repair_required.

**Still required:** integrate accepted patches on claude and provide new SHA; independently bind host replay/verifier receipts and actual UI/target state; establish semantic cloud provenance; native hook/voice/GPU/service/account/training and all-flags acceptance. **JRV-37-019 additionally inherits V2-003/IR-004 OPEN P2:** deep process cwd >260 chars fails on pinned/candidate before Git starts; extended cwd and Git -C alternatives failed. Use a shorter explicit owned lab_root/checkout; do not silently move files or change OS settings. Keep every earlier blocker below; no merge/deployment.

'''
assert '## Prompt 37 follow-up -' not in text
handoff.write_text(text.replace('## Prompt 99 -', section + '## Prompt 99 -', 1), encoding='utf-8')
subprocess.run(['git', 'diff', '--check'], cwd=APP.parent, check=True)
dump('validation.json', {'fresh_targeted_pass': 38, 'fresh_journals_pass': 3, 'production_hashes_match': len(source),
    'reviewed_changed_source_test_hashes_match': True, 'full_E2E_blocked': 26,
    'implementation_changes': 0, 'full_regression_reused_by_verified_identity': True, 'git_diff_check': 'PASS'})
print('38 PASS; 3 owned/simulated journals PASS; full acceptance 26 BLOCKED.')
