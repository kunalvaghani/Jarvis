"""Reconcile new committed claude source and the owned mock-send/UI acceptance journey."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
REVIEW = next(p for p in OUT.parents if (p / 'main.py').is_file())
SOURCE = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')
PIN = 'e5af0e700517bac5fb48dcebc8f6cc9c9df9a369'
INTEGRATION = '3fbfbf68b6e5cd964191db2c3245efbc2f5a3772'
OLD = OUT.parent / '2026-10-20-followup-a9b4ce1'
def write(name, body): (OUT / name).write_text(body.rstrip() + '\n', encoding='utf-8')
def dump(name, body): write(name, json.dumps(body, indent=2))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE).decode().strip() == PIN
assert subprocess.run(['git','diff','--quiet'],cwd=SOURCE).returncode == 0
production = {}
for folder in ['jarvis','scripts','evolution_eval']:
    for path in (SOURCE / folder).rglob('*.py'):
        production[path.relative_to(SOURCE).as_posix()] = sha(path)
dump('source-hashes.json', production)
prior = {path.relative_to(REVIEW).as_posix(): sha(path) for folder in [OLD, OUT.parent / '2026-10-20-completion-a9b4ce1']
         for path in folder.iterdir() if path.is_file()}
dump('prior-evidence-hashes.json', prior)
normal = {}
for path in [*OUT.glob('*.txt'), *OUT.glob('*.xml')]:
    before = sha(path)
    body = path.read_text(encoding='utf-8-sig')
    for start, target in [(str(SOURCE), '%PINNED_APP%'), (str(REVIEW), '%REVIEW_APP%'),
                          ('D:\\Kunals GitHub Repo\\Jarvis\\app', '%INSTALL_APP%'),
                          (os.environ.get('USERPROFILE','NO_PROFILE'), '%USERPROFILE%')]:
        for spelling in {start, start.replace('\\','/'), start.replace('\\','\\\\')}:
            body = body.replace(spelling,target)
    body = re.sub(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"<>]+','%USERPROFILE%',body)
    path.write_text(body,encoding='utf-8')
    normal[path.name] = {'original_sha256':before,'saved_sha256':sha(path)}
dump('log-normalization.json',normal)
runs, executed = {}, []
for run in ['baseline','full','ui-restart','ui-restart-portable']:
    tree = ET.parse(OUT / (run+'.xml')).getroot()
    rows = []
    for case in tree.iter('testcase'):
        skip = case.find('skipped')
        status = 'FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIPPED' if skip is not None else 'PASS'
        rows.append({'id':case.get('name'),'classname':case.get('classname'),'status':status,'run':run,
                     'seconds':float(case.get('time',0)),'reason':skip.get('message') if skip is not None else '',
                     'source_sha':PIN,'evidence':run+'.xml'})
    runs[run] = {s:sum(row['status']==s for row in rows) for s in ['PASS','FAIL','SKIPPED']}
    runs[run]['seconds'] = sum(float(s.get('time',0)) for s in tree.iter('testsuite'))
    executed.extend(rows)
assert all(row['FAIL']==0 for row in runs.values())
assert runs['baseline']['PASS']==104
assert runs['ui-restart-portable']['PASS']==1
write('executed-results.jsonl','\n'.join(json.dumps(row) for row in executed))
full = runs['full']
headline = f"{full['PASS']} PASS / 0 FAIL / {full['SKIPPED']} SKIPPED"
ui = json.loads((OUT/'ui-restart-journal.json').read_text(encoding='utf-8'))
assert ui['source_sha']==PIN and ui['status']=='PASS'
assert ui['postconditions']['mock_outbox_rows']==1 and ui['postconditions']['planner_calls_after_restart']==0
assert 'Task paused:' in ui['postconditions']['ui_overview'] and 'Task paused:' in ui['postconditions']['live_text']
journals = [json.loads(line) for line in (OUT/'workflow-journals.jsonl').read_text().splitlines()]
assert len(journals)==3 and all(row['status']=='PASS' for row in journals)
portable = REVIEW/'tests/test_prompt37_ui_restart.py'
assert sha(portable)==sha(SOURCE/'tests/test_prompt37_ui_restart.py')
test_patch = ''.join(difflib.unified_diff([],portable.read_text(encoding='utf-8').splitlines(keepends=True),
                                       fromfile='/dev/null',tofile='b/app/tests/test_prompt37_ui_restart.py'))
(OUT/'new-test.patch').write_bytes(test_patch.encode('utf-8'))
dump('test-overlay.json',{'new_test':'tests/test_prompt37_ui_restart.py','sha256':sha(portable),
    'pinned_production_changes':0,'test_overlay_only':True,'portable_test_pending_integration':True})
dump('baseline.json',{'date':'2026-10-20','pinned_claude':PIN,'integrated_repairs_commit':INTEGRATION,
    'prior_review_parent':'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6','runs':runs,
    'headline_run':'full','additional_nonoverlapping_UI_case':1,'overlapping_runs_not_summed':True,
    'fresh_full_run':True,'production_changes':0,'new_test_only':True,
    'runtime_readiness':'repair_required','real_account_sends':0,'real_cloud_requests':0,'microphone_or_native_hook':0,
    'initial_test_file_setup_error':'ui-test-setup-error.xml: missing file after shell quoting error, not an application failure; corrected before test execution'})
dump('review-revisions.json',{'audited':PIN,'integration':INTEGRATION,
    'claude_at_report':subprocess.check_output(['git','rev-parse','claude'],cwd=REVIEW).decode().strip(),
    'source_checkout':'isolated detached checkout at audited SHA; test-only overlay',
    'new_test_fix_commit':None,'no_merge_or_live_tree_edit':True})
cases = [json.loads(line) for line in (OLD/'tests.jsonl').read_text(encoding='utf-8').splitlines()]
for row in cases:
    row['base_sha']=PIN
    row['fix_sha']=None
    row['retained_repairs_commit']=INTEGRATION
    row['followup']='Fresh independent verification of committed e5af0e7, superseding pending-integration status for the earlier reviewed repairs.'
    row['evidence']=['executed-results.jsonl','workflow-journals.jsonl','launcher-check.txt']
    if row['id']=='JRV-37-021':
        row['status']='PASS'
        row['classification']='owned process/UI integration with explicitly simulated send and speech transport'
        row['reason']='Real child process exits 27 after a single mock-outbox attempt and durable uncertain checkpoint. New Actions instance reloads interrupted state. Resume is queued through the real worker and App report/drain/Island/Desk consumers. Actual Tk Text and live StringVar read back Task paused; planner not called, speech sink called once, pending checkpoint retained, mock outbox stays one. No real account or physical audio claim.'
        row['evidence']+=['ui-restart-journal.json','ui-restart-portable.xml','new-test.patch']
    if row['id']=='JRV-37-023':
        row['reason']+=' New P34 digest transport/in-place rollback/frozen-original-lock fixture regressions independently pass on e5af0e7. Real registry/rebuild/server visibility remain NOT RUN.'
write('tests.jsonl','\n'.join(json.dumps(row) for row in cases))
dump('coverage-summary.json',{'numbered_denominator':26,'PASS':1,'BLOCKED':25,'FAIL':0,'SKIPPED':0,'NOT RUN':0,
    'passing_case':'JRV-37-021 as requested with mock send plus real process/Tk consumers',
    'real_voice_or_account_integrations':0})

write('inventory.md',f'''# Independent Prompt 37 continuation - 2026-10-20

Pinned new claude `{PIN}` in a fresh detached checkout. Claude integrated the earlier P34-P37 proposals at `{INTEGRATION}` and added P34-R1/R2/R3 changes at the audited SHA. Old a9b4ce1 packets remain historical. No production edits to the new checkout; only the independently authored portable test was overlaid. Review proposals/docs remain in codex-review. Live user config untouched.

Read current root/app AGENTS, revised P37, system map, cumulative handoff and Claude integration repair record; inspected new launcher/setup diffs and actual Actions/App/Island/Desk consumers. Source hashes, actual XML/journals and test overlay identify lineage. Existing original Master/companion catalogue context from V2 retained; no new planned-ID pass inference.
''')
write('changes.md', '''# New work

Added tests/test_prompt37_ui_restart.py, a portable regression for JRV-37-021. A real owned child running Actions exits 27 after one mock-outbox attempt and an uncertain checkpoint. A fresh Actions instance queues resume; real App.report and App.drain deliver the paused result through Island/Desk and actual Tk widgets. Reads actual overview/live text, verifies one speech-sink call and zero planner calls, and reads the durable marker/outbox again.

The test bypasses App constructor (no mic/model startup), uses hidden owned widgets and fake send/speech boundaries. Only the drain recovery scheduler wrapper is bypassed so assertion failures propagate; the event consumer body executes. No screenshot, account send, native hook or physical audio. No production behavior changed. One setup run failed to find the not-yet-created test after shell quoting failed; setup-error evidence retained and superseded by successful portable execution.
''')
write('failures.md', '''# Remaining blockers

Fresh full selected regression and new portable UI journey have no failures. Revised case denominator is now 1 bounded mock-send/UI PASS and 25 BLOCKED. The earlier full P37-021 UI-consumer gap is closed for the requested mock case; universal host verifier authority and all other UI paths are not certified.

P35/P37 semantic cloud provenance and independent replay/target/receipt authority remain OPEN P1. Native hook lifetime, physical voice/GPU/TTS/preemption, actual accounts/apps/engines, OpenViking/Docker/Ollama, fresh training and every feature-off combination remain incomplete. Isolated readiness is repair_required. Existing IR-004/V2-003 deep process-cwd >260-character limit remains OPEN P2; ordinary short lab works. No new deep-path repair was claimed.

New P34 code fixes were independently exercised using the 66 existing mocked dependency-repair tests within the 104-test baseline. This closes those previously reported implementation cases at fixture scope, not live registry/CDN/Ollama model visibility or real approved rebuild/console-script/rollback acceptance. No installation or download attempted.
''')
write('cross-pillar-matrix.md', '''# Impact / integration matrix

| Seam | Fresh assertion | Scope |
|---|---|---|
| Queued task -> actual crash -> restart | exit 27, pending uncertain marker, one owned mock-outbox row | actual process and TaskState; send simulated |
| Resume -> App.report/drain -> Island/Desk -> Tk | paused overview/live text; no success text, no planner call, speech sink once | actual consumers/widgets, hidden; no physical voice/account |
| API strategy -> worker -> CAPTURED/FIX -> memory | separate worker workbook A1=9, formula retained, strategy and anti-pattern stored | owned files; author/consent simulated |
| Failures -> approval -> cloud advisory | fake outbound once, no action or duplicate consultation | transport simulated; semantic provenance still OPEN |
| P34 -> 32/35/37 recovery | digest-bound URLs/budgets, original-lock snapshot, in-place rebuild/rollback regressions | mocked network/commands; no real install/download |
| A-D and legacy 01-37 | fresh full selected suite through run_suite.py | exact selections/exclusions saved; no sum-as-full-E2E claim |

No production shared interface changed. New portable UI test executed separately after creation; baseline and journal helpers overlap full-suite checks and are not summed as unique cases.
''')
write('compatibility.md', '''# Compatibility

No dependency, runtime manifest, service or production interface change. New regression follows the existing Windows/Tk fixture approach, disables mic/speech/model startup, and uses an optional explicit JARVIS_E2E_EVIDENCE_DIR for journals. Real selected source is the isolated e5af0e7 checkout. Installed interpreters/Hermes metadata/LocalGithub are read-only test dependencies; user configuration is excluded.

All stated native/live/flag/model service limitations remain blocked. The new case intentionally uses the requested mock send, not actual external delivery. Existing all-feature and global UI truth acceptance remain incomplete.
''')
write('security.md', '''# Security / side effects

Real child os._exit is confined to an owned fixture process. The only delivery side effect is one JSONL row in a temporary mock outbox. UI widgets are owned, hidden, and read programmatically. Speech is a Mock sink; mic, account send, network provider and desktop capture are inactive. A planner callback after restart raises immediately, so the test cannot silently infer or replay.

New dependency repair cases intercept commands/requests. The fresh full suite uses fake transports and owned files/Git/loopback/utility app fixtures; unsupported cases are explicit skips or exclusions. No package/model install, private recording or global setting changes. Local roots normalized in raw output with before/saved hashes.
''')
write('rollback.md', '''# Reproduction / rollback

Use existing main Python. Run run_suite.py --root <isolated-e5af-app> --mode full --junitxml=<absolute-output> -q. The 104-test baseline selects P34 dependency/completion/remaining routes plus P37/task state/task recovery files. Run pytest tests/test_prompt37_ui_restart.py separately with optional JARVIS_E2E_EVIDENCE_DIR pointing to an owned packet; no setup step. run_workflows.py reproduces three owned/simulated journals and the fixed historical paired cleanup comparison.

No production rollback required. The new test is proposed via new-test.patch, which applies to the pinned index; review/integrate on claude and rerun that test. Never reset/clean the old review worktree or overwrite user config. New detached checkout retains a test-only overlay. No automatic merge/deployment, deleting user files or uncertain-write replay.
''')
write('codex-findings-reconciliation.md',f'''# Finding reconciliation at {PIN}

| Finding | Current state | Fresh evidence |
|---|---|---|
| P99-R1 prior P34-P37 integration | RESOLVED for earlier production repairs: integrated at {INTEGRATION}; independently exercised at {PIN} | full.xml, baseline.xml; source-hashes.json |
| P37-001..004 | integrated fixes retained | lifecycle/consent/no-replay/task regressions in fresh baseline/full |
| JRV-37-021 actual UI-consumer gap | PASS in requested mock-send scope | portable process-crash/restart/Tk text test and journal |
| P34-R1/R2/R3 original implementation cases | code+fixture repair independently verified; live gates still BLOCKED | 66 mocked dependency tests within 104 baseline; fresh full suite |
| Global verifier / cloud provenance / native target lifetime | OPEN P1, not closed by one passing UI path | failures.md and cumulative handoff |
| IR-004/V2-003 deep cwd | still OPEN P2, source unchanged here | inherited V2 reproduction and failed alternatives |

New portable test has no integration SHA yet. No production patch proposed in this continuation. Preserve historical uncommitted-candidate verdicts as dated evidence, not current integration state.
''')
write('verdict.md',f'''# Prompt 37 - fresh committed-source verification; release NOT READY

2026-10-20. Audited `{PIN}` in a fresh isolated checkout. Earlier reviewed production repairs are now integrated at `{INTEGRATION}`. **Fresh full relevant regression: {headline}.** Focused baseline: 104 PASS. New portable process/UI journey: 1 PASS, separate from the full selection; initial development run exercises the same case and is not another unique PASS.

**JRV-37-021 now PASS at the requested mock-send scope:** real child exits 27, restart reloads the uncertain checkpoint, queued resume reaches actual App/Island/Desk/Tk consumers, both text fields say Task paused, planner is not called, speech sink receives one message and outbox remains one row. No real sends, audio or private desktop capture.

26 revised cases: **1 bounded process/mock/UI PASS / 25 BLOCKED**. Other live/native/account/training/verifier/provenance/service gates remain unresolved. Isolated readiness: repair_required. No production changes, installs, downloads, merge or deployment. [Case record](tests.jsonl) · [UI readback](ui-restart-journal.json) · [Proposed test](new-test.patch) · [Handoff](../../../../../docs/CLAUDE_HANDOFF.md).
''')
packet='artifacts/jarvis-audit/modules/37-e2e/'+OUT.name
def add(path,body,anchor):
    text=path.read_text(encoding='utf-8')
    marker='<!-- prompt37-e5af-verification -->\n'+body+'\n<!-- /prompt37-e5af-verification -->\n\n'
    assert '<!-- prompt37-e5af-verification -->' not in text
    assert anchor in text
    path.write_text(text.replace(anchor,marker+anchor,1),encoding='utf-8')
add(REVIEW/'README.md',f'''**2026-10-20 - Independent Prompt 37 verification of committed claude e5af0e7:** **{headline}** in the fresh full relevant run; 104 focused checks pass. Earlier P34-P37 production repairs are integrated in 3fbfbf6. New JRV-37-021 regression passes a real owned child crash/restart through the task queue and actual App/Island/Desk/Tk text consumers: uncertain mock send stays paused, one outbox row, no planner replay, speech sink once. No real account send or audio. New portable test awaits integration; no production behavior changed here. Revised cases: **1 owned mock-send/UI PASS / 25 BLOCKED**. Other verifier/provenance/native/live/training gates and isolated repair_required remain. [Evidence]({packet}/verdict.md) · [Journal]({packet}/ui-restart-journal.json) · [Claude handoff](docs/CLAUDE_HANDOFF.md).''','<!-- prompt37-followup -->')
add(REVIEW.parent/'README.md',f'''**2026-10-20 - Fresh E2E verification at claude e5af0e7:** **{headline}**. The queued mock-send crash/restart journey now passes actual Tk UI readback; full acceptance still has 25 blocked cases. [Evidence](app/{packet}/verdict.md) · [Claude handoff](app/docs/CLAUDE_HANDOFF.md).''','<!-- prompt37-followup -->')
handoff=REVIEW/'docs/CLAUDE_HANDOFF.md'
text=handoff.read_text(encoding='utf-8')
section=f'''## Prompt 37 - independent committed-source continuation at e5af0e7

**2026-10-20:** pin `{PIN}`, fresh isolated checkout. Claude integrated the prior reviewed P34-P37 production changes at `{INTEGRATION}`; P99-R1 is resolved for those earlier repairs. The old review checkout is retained separately; its historical a9b4ce1 statuses are not the current integration verdict. [Packet](../{packet}/verdict.md), [26 cases](../{packet}/tests.jsonl), [source hashes](../{packet}/source-hashes.json), [new portable test patch](../{packet}/new-test.patch).

Fresh full relevant run: **{headline}**. Focused baseline: 104 pass, including 66 new P34 dependency-repair cases; overlapped counts not summed. Three API/skill/memory and simulated send/cloud journals pass. P34-R1/R2/R3 original code cases independently pass with intercepted commands/requests; live registry/Ollama and real approved rebuild/rollback/console-script gates remain NOT RUN.

**JRV-37-021 PASS in the specified mock-send/UI scope.** Actual child process exits 27 after one temporary mock-outbox row and durable uncertain checkpoint. Fresh Actions reloads interrupted state; queued resume refuses planner/external replay. Real App.report/drain, Island/Desk consumers and Tk Text/StringVar read back Task paused. Speech sink called once, planner zero, outbox one, marker retained. [Journal](../{packet}/ui-restart-journal.json), [test](../tests/test_prompt37_ui_restart.py). Fake send/speech transports; no account send, microphone, physical playback or desktop capture. Portable regression is new and awaits Claude integration; production files unchanged in this continuation.

**Remaining:** 25 revised cases still BLOCKED. Keep global host verifier/replay receipt and selected target authority, semantic cloud provenance, native hook lifetime, real voice/TTS/GPU/preemption, account/app/engine/services, training and all flag/rollback gates open. IR-004/V2-003 long process-cwd remains OPEN P2; use shorter explicit owned lab_root. Isolated launcher repair_required; no install/download to clear it. Do not interpret one actual mock/UI journey as full real-user acceptance. No merge/deployment. Keep all historical sections below.

'''
assert '## Prompt 37 - independent committed-source continuation' not in text
handoff.write_text(text.replace('## Prompt 37 follow-up -',section+'## Prompt 37 follow-up -',1),encoding='utf-8')
recovery=REVIEW/'docs/CRASH_RECOVERY.md'
body=recovery.read_text(encoding='utf-8')
note=f'''## Uncertain-send UI restart verification - 2026-10-20

At claude e5af0e7, the owned mock-send journey now verifies an actual child crash, fresh TaskState/Actions reload, queued resume and real App/Island/Desk/Tk readback of Task paused. The planner is not invoked and the mock outbox remains one row. This proves that bounded UI path; it does not authorize replay or certify real account delivery/physical speech. [Evidence](../{packet}/ui-restart-journal.json) and [remaining blockers](CLAUDE_HANDOFF.md).

'''
assert '## Uncertain-send UI restart verification' not in body
recovery.write_text(body.replace('## Demonstration and uncertain task completion',note+'## Demonstration and uncertain task completion',1),encoding='utf-8')
subprocess.run(['git','diff','--check'],cwd=REVIEW.parent,check=True)
dump('validation.json',{'pinned_source':PIN,'fresh_full':full,'fresh_baseline_pass':104,'portable_UI_test_pass':1,
    'revised_case_pass':1,'revised_case_blocked':25,'production_edits':0,'test_overlay_sha256':sha(portable),
    'git_diff_check':'PASS','earlier_P34_P37_integration_verified':True})
print(headline)
