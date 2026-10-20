"""Collect bounded memory continuation evidence; never overwrite prior packets."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = OUT.parents[4]
REVIEW = APP.parent
SOURCE = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')
PRIOR = OUT.parent / '2026-10-20-independent-e5af0e7'
SHA = 'e5af0e700517bac5fb48dcebc8f6cc9c9df9a369'
assert APP.name == 'app'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip() == SHA
hashes = {p: hashlib.sha256((SOURCE / p).read_bytes()).hexdigest()
          for p in json.loads((PRIOR / 'source-hashes.json').read_text(encoding='utf-8'))}
assert hashes == json.loads((PRIOR / 'source-hashes.json').read_text(encoding='utf-8'))
(OUT / 'source-hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
def write(name, text):
    (OUT / name).write_text(text.strip() + '\n', encoding='utf-8')
def count(name):
    cases = ET.parse(OUT / (name + '.xml')).findall('.//testcase')
    return {'PASS': sum(not any(c.find(tag) is not None for tag in ('skipped', 'failure', 'error')) for c in cases),
            'FAIL': sum(c.find('failure') is not None or c.find('error') is not None for c in cases),
            'SKIPPED': sum(c.find('skipped') is not None for c in cases)}
runs = {name: count(name) for name in ('focused', 'neighbors')}
assert runs['neighbors'] == {'PASS': 109, 'FAIL': 0, 'SKIPPED': 1}
write('baseline.json', json.dumps({'date': '2026-10-20', 'sha': SHA, 'runs': runs,
    'overlap_not_summed': True, 'production_files_unchanged': len(hashes),
    'prior_same_source_full': '../2026-10-20-independent-e5af0e7/full.xml',
    'prior_full_counts': {'PASS': 1907, 'FAIL': 0, 'SKIPPED': 139},
    'fresh_full_run': False, 'reason': 'Only portable test/evidence/docs added; 560 production hashes identical.'}, indent=2))
case_rows = [json.loads(line) for line in (PRIOR / 'tests.jsonl').read_text(encoding='utf-8').splitlines() if line]
for row in case_rows:
    if 'JRV-37-017' in json.dumps(row):
        row['fresh_memory_seam'] = 'PASS: memory on/off, anti-pattern reaches serialized BrainClient request; actual workbook outcome unchanged; fake planner, full acceptance still BLOCKED.'
write('tests.jsonl', '\n'.join(json.dumps(row) for row in case_rows))
journals = [json.loads((OUT / f'reasoning-repeat-{enabled}.json').read_text(encoding='utf-8')) for enabled in (False, True)]
write('workflow-journals.jsonl', '\n'.join(json.dumps(row) for row in journals))
with (OUT / 'benchmarks.csv').open('w', newline='', encoding='utf-8') as output:
    writer = csv.DictWriter(output, fieldnames=['memory_enabled', 'attempt', 'elapsed_seconds', 'lessons', 'verified_goal_success'])
    writer.writeheader()
    for journal in journals:
        for row in journal['rows']:
            writer.writerow({'memory_enabled': journal['memory_enabled'], 'attempt': row['attempt'],
                'elapsed_seconds': row['elapsed_seconds'], 'lessons': row['lesson_count_at_transport'],
                'verified_goal_success': row['verified_goal_success']})
patch = subprocess.run(['git', 'diff', '--no-index', '--', 'NUL', 'app/tests/test_prompt37_reasoning_repeat.py'],
                       cwd=REVIEW, capture_output=True).stdout
assert patch and b'new file mode' in patch
(OUT / 'new-test.patch').write_bytes(patch)
subprocess.run(['git', 'apply', '--check', '--cached', str(OUT / 'new-test.patch')], cwd=SOURCE, check=True)
write('inventory.md', f'''# Memory repeat continuation — 2026-10-20
Pinned Claude `{SHA}` in a detached checkout. Production source is unchanged across {len(hashes)} hashes.
Actual path: ToolRegistry.office_xlsx → existing skills worker → failure → harness task record → LearningMemory.learn_from_task → ReasoningBank SQLite → LearningMemory.lessons → BrainClient.request/_request/_request_once JSON wire → recording fake planner → ToolRegistry → independent openpyxl worker readback.
Real local file and SQLite operations; fake worker transport deliberately ignores hints. Task completion/trajectory is supplied by this harness, not full Actions/Brain orchestration. No model, voice, native GUI or account claim.
Read app/AGENTS.md and revised Prompt 37. Earlier discovery/contract inventories remain in [prior packet](../2026-10-20-independent-e5af0e7/inventory.md).
''')
write('changes.md', '''# Changes
One portable two-variant regression proposed on codex-review; test-only copy in pinned checkout. No production repair required by this journey. [Patch](new-test.patch), [test](../../../../../tests/test_prompt37_reasoning_repeat.py).
No dependency, service, configuration, launcher or UI behavior change. Memory off/on tests use existing dependency interpreters read-only. Fresh focused 2 pass; final neighboring 109 pass/1 skip includes both focused variants and UI crash restart regression; counts overlap.
''')
write('failures.md', '''# Failures and gaps
No regression assertion failures. The task itself fails twice per variant as deliberately induced: Unknown worksheet. A1 remains 1 rather than requested 5; formula and workbook hash unchanged. Memory-on repeat receives one provisional anti-pattern but simulated planner ignores it. This is honest no improvement, not assistant success.
JRV-37-017 full journey remains BLOCKED: available real planner and actual Actions/Brain task completion loop were not exercised. Fresh launcher reports repair_required; no install/download performed.
Carry forward all prior open issues: global verifier/replay receipts/target identity (P1), caller-declared cloud provenance (P1), deep process cwd WinError267 (P2), principal/concurrency/real dependency transport gates, native/voice/account/GPU/training and broad feature-off gates. No blocker closed by retrieval alone.
''')
write('cross-pillar-matrix.md', '''# Change impact
| Change | Legacy / pillar seam | Invariant | Fresh regression |
|---|---|---|---|
| Test only: failed workbook repeat | API/ToolRegistry → learning → planner | Retrieved hint cannot imply success | JRV-37-017 memory-on/off |
| No production change | P34 dependency / P35 security / P36 status / P37 recovery | Existing boundaries retained | neighbors.xml, 109 pass / 1 skip |
| UI recovery neighbor | queued external mock → crash → UI | No replay; truthful paused status | JRV-37-021 in neighbors.xml |
All 26 acceptance IDs retained in tests.jsonl: one scoped mock UI PASS, 25 BLOCKED. This new seam does not close an additional full acceptance case.
''')
write('compatibility.md', '''# Compatibility
Windows; existing original .venv and .venv-skills read-only. Pinned source supplies Jarvis and worker code. No package installations.
Feature off: zero lessons/learning. Feature on: first request zero lessons; second request one bounded provisional anti-pattern. Both variants honestly retain failed task outcomes.
One neighboring skip is recorded verbatim in neighbors.xml, not promoted to PASS. Launcher output in launcher.txt is readiness only, not live feature validation.
''')
write('security.md', '''# Security scope
Owned synthetic workbook and temporary SQLite only. Invalid worksheet rejected before approval or write. Four independent worker readbacks plus SHA-256 checks preserve original workbook bytes/formula/value. No real model/cloud request, account action, microphone, private screen or native hook.
Planner transport is fake; final executor is actual ToolRegistry. New test exercises ordinary invalid-sheet rejection, not complete adversarial privacy/authorization certification. Prior P1 concerns remain open.
''')
write('rollback.md', '''# Rollback and reproduction
Test-only proposal; omit new test if rejected. Preserve old evidence and user configuration. No production/runtime rollback needed.
From pinned app, set JARVIS_E2E_DEPENDENCY_APP to original installed app, JARVIS_E2E_EVIDENCE_DIR to a new owned output directory; run existing main Python `-m pytest tests/test_prompt37_reasoning_repeat.py -q`. No downloads. Memory tests skip explicitly if skills interpreter is absent.
The [final selection](boundary-selection.json) and [runner](run_suite.py) specify neighboring test IDs. Prior full relevant run is reusable only after matching source-hashes.json; it predates this test and is not a newly rerun full suite.
''')
write('codex-findings-reconciliation.md', f'''# Reconciliation
Source `{SHA}`; no new production defect found. P99-R1 previous production integration remains resolved at 3fbfbf6/e5af0e7. New UI and memory regressions await Claude review/integration, without auto-merge.
JRV-37-017: fresh bounded evidence added, full acceptance BLOCKED. P99-R2 verifier/target and P99-R3 cloud provenance remain OPEN P1; P99-R4/R5/R6 and V2-003/IR-004 remain open at prior scope. [Prior reconciliation](../2026-10-20-independent-e5af0e7/codex-findings-reconciliation.md).
''')
write('verdict.md', f'''# NOT READY — 2026-10-20
Pinned `{SHA}`. Fresh final neighboring run **109 PASS / 0 FAIL / 1 SKIPPED**, including new two-variant memory seam. Initial focused run 2 pass overlaps, not summed. Prior identical-production-source full run 1907 pass/139 skip retained, not rerun or added to fresh counts.
Memory-on repeat receives an anti-pattern in the actual serialized planning request. The fake planner repeats invalid choice; real workbook readback proves **no task improvement**, no mutation, no false success. Memory-off comparison remains functional without lessons.
JRV-37-017 remains **BLOCKED** for real planner/full orchestration; one scoped JRV-37-021 PASS and 25 blocked revised cases carried forward. Global P1 safety/privacy and unavailable live gates remain open. No release certification, merge or deployment.
[Journals](workflow-journals.jsonl), [fresh XML](neighbors.xml), [gaps](failures.md), [baseline](baseline.json), [patch](new-test.patch).
''')
marker = '<!-- prompt37-memory-continuation -->'
for path, prefix in ((APP / 'README.md', ''), (REVIEW / 'README.md', 'app/')):
    original = path.read_text(encoding='utf-8')
    if marker not in original:
        paragraph = f'''\n{marker}
**2026-10-20 ReasoningBank continuation:** pinned `e5af0e7`; fresh neighboring fixtures **109 pass / 1 skip**. Real workbook/SQLite/BrainClient wire with simulated planner: retrieved anti-pattern reaches repeat request, task outcome honestly does not improve; memory-off comparison also checked. No production change or live inference claim. JRV-37-017 remains blocked for full orchestration/real planner. [Evidence]({prefix}artifacts/jarvis-audit/modules/37-e2e/2026-10-20-memory-e5af0e7/verdict.md); [Claude handoff]({prefix}docs/CLAUDE_HANDOFF.md).\n'''
        first, rest = original.split('\n', 1)
        path.write_text(first + '\n' + paragraph + rest, encoding='utf-8')
handoff = APP / 'docs/CLAUDE_HANDOFF.md'
original = handoff.read_text(encoding='utf-8')
heading = '## Prompt 37 - ReasoningBank repeat continuation at e5af0e7'
if heading not in original:
    section = f'''{heading}

**2026-10-20:** [packet](../artifacts/jarvis-audit/modules/37-e2e/2026-10-20-memory-e5af0e7/verdict.md), [new portable test](../tests/test_prompt37_reasoning_repeat.py), [patch](../artifacts/jarvis-audit/modules/37-e2e/2026-10-20-memory-e5af0e7/new-test.patch). Fresh final neighboring **109 pass/1 skip**, including memory on/off. Production source remains identical across 560 hashes to prior e5af0e7 full run (1907 pass/139 skip); no new full-run claim. Real worker workbook readback/hash, ToolRegistry, LearningMemory/SQLite and BrainClient JSON serialization show second request has one anti-pattern. Simulated planner ignores it; both attempts fail with original workbook intact. Retrieval is proven; improvement is honestly absent. No production fix needed.

**Remaining:** JRV-37-017 full Actions/Brain task orchestration and available real planner NOT RUN/BLOCKED. Acceptance stays one scoped mock UI PASS/25 BLOCKED. Review/integrate newly proposed UI and memory tests on claude, return committed SHA; stage approved real planner/disposable orchestration journey. All prior global verifier/target/replay P1, cloud provenance P1, deep-cwd P2 and native/voice/account/GPU/training/principal/concurrency/transport gates remain open. No auto-install/merge/deploy. [Full gaps](../artifacts/jarvis-audit/modules/37-e2e/2026-10-20-memory-e5af0e7/failures.md).

'''
    original = original.replace('## Prompt 37 - independent committed-source continuation at e5af0e7', section + '## Prompt 37 - independent committed-source continuation at e5af0e7', 1)
    handoff.write_text(original, encoding='utf-8')
required = ['inventory.md','baseline.json','tests.jsonl','failures.md','changes.md','cross-pillar-matrix.md',
            'benchmarks.csv','compatibility.md','security.md','rollback.md','codex-findings-reconciliation.md','verdict.md']
assert all((OUT / name).is_file() for name in required)
assert len(case_rows) == 26
subprocess.run(['git', 'diff', '--check'], cwd=REVIEW, check=True)
write('validation.json', json.dumps({'required_reports': 12, 'cases': len(case_rows), 'source_hashes_unchanged': len(hashes),
    'patch_check': 'PASS', 'diff_check': 'PASS', 'production_edits': 0, 'fresh_results': runs}, indent=2))
print(json.dumps({'results': runs, 'source_hashes_unchanged': len(hashes), 'packet': str(OUT)}))
