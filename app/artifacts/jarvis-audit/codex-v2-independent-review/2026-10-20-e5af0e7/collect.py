"""Final V2 packet; run only after candidate regression has completed."""
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
APP=OUT.parents[3]
PIN=Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')
CANDIDATE=Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-v2-mutants-e5af0e7/app')
SHA='e5af0e700517bac5fb48dcebc8f6cc9c9df9a369'
PRIOR=OUT.parent/'2026-10-20-a9b4ce1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,text):(OUT/name).write_text(text.strip()+'\n',encoding='utf-8')
def dump(name,data):write(name,json.dumps(data,indent=2))
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def records(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
assert APP.name=='app'
assert all(sha(PIN/name)==digest for name,digest in read('source-hashes.json').items())
assert all(sha(CANDIDATE/name)==digest for name,digest in read('candidate-source-hashes.json').items())
parents=read('parent-evidence-index.json')
assert all(sha(APP/name)==row['sha256'] for name,row in parents.items())
runs={};executed=[]
for label in ['final-full','candidate-final','prior-findings','model-paths-before','model-paths-after','deep-lab']:
    root=ET.parse(OUT/(label+'.xml'))
    rows=[]
    for case in root.findall('.//testcase'):
        failure=case.find('failure');error=case.find('error');skip=case.find('skipped')
        status='FAIL' if failure is not None or error is not None else 'SKIPPED' if skip is not None else 'PASS'
        rows.append({'id':case.get('name'),'classname':case.get('classname'),'status':status,
            'seconds':float(case.get('time',0)),'run':label,'xml':label+'.xml',
            'detail':skip.get('message','') if skip is not None else failure.get('message','')[:800] if failure is not None else error.get('message','')[:800] if error is not None else ''})
    runs[label]={s:sum(row['status']==s for row in rows) for s in ['PASS','FAIL','SKIPPED']}
    runs[label]['seconds']=sum(float(s.get('time',0)) for s in root.findall('.//testsuite'))
    executed+=rows
assert runs['candidate-final']['FAIL']==0
assert runs['model-paths-before']['FAIL']==27 and runs['model-paths-after']['FAIL']==0
assert runs['deep-lab']['FAIL']==1
final={status:runs['candidate-final'][status]+runs['deep-lab'][status] for status in ['PASS','FAIL','SKIPPED']}
headline=f"{final['PASS']} PASS / {final['FAIL']} FAIL / {final['SKIPPED']} SKIPPED"
write('03-executed-results.jsonl','\n'.join(json.dumps(row) for row in executed))
dump('run-summary.json',{'runs':runs,'final_distinct_candidate_checks':final,
    'counting':'candidate-final plus distinct unchanged-production deep-lab repro; overlapping targeted/prior runs not summed',
    'full_live_assistant_E2E':0,'owned_simulated_journals':3,'revised_37_full_acceptance':{'PASS':1,'BLOCKED':25},
    'original_797_planned_not_execution':True,'performance_runtime_comparison':'NOT VALID: test scope/load differ; paired guard microbenchmark reported separately'})
links={}
for row in executed:
    if row['run']=='candidate-final':
        for a,b in re.findall(r'JRV[-_](\d{2})[-_](\d{3})',row['id']):links.setdefault(f'JRV-{a}-{b}',[]).append(row)
coverage=[]
for row in records(OUT/'mapped-corpus.jsonl'):
    full='BLOCKED' if int(row['id'].split('-')[1])>=31 else 'NOT RUN'
    if row['id']=='JRV-37-021' and row['variant']=='revised':full='PASS'
    coverage.append({**row,'full_acceptance_status':full,
        'fresh_name_linked_checks':[{'id':r['id'],'status':r['status']} for r in links.get(row['id'],[])],
        'link_limit':'Name links do not prove expected behavior. Only revised mock-send/UI 37-021 has a scoped acceptance PASS.'})
write('04-coverage.jsonl','\n'.join(json.dumps(row) for row in coverage))
dump('case-accounting.json',{'imported_id_behavior_variants':len(coverage),'original_catalog_ids':1184,
    'original_checkpoint_planned':797,'fresh_name_links':len(links),'full_specification_statuses':
    {s:sum(row['full_acceptance_status']==s for row in coverage) for s in ['PASS','BLOCKED','NOT RUN']},
    'specifications_and_pytest_counts_are_separate':True})
ledger=list(csv.DictReader((PRIOR/'05-findings-ledger.csv').open(encoding='utf-8')))
for row in ledger:
    finding=row['finding']
    row['pinned']=SHA
    if finding=='IR-004' or 'V2-003' in finding:
        row.update(status='OPEN P2 / reproduced WinError267',candidate_fix='none',fresh_evidence='deep-lab.xml FAIL; prior-findings.xml short lab PASS',follow_up='Use explicitly configured shorter owned lab_root; no OS setting change or silent relocation.')
    elif finding.startswith('IR-'):
        row.update(status='RETAINED bounded repair; live scope incomplete',candidate_fix='historical committed repair retained',fresh_evidence='prior-findings.xml (33 PASS); candidate-final.xml',follow_up='Do not infer full physical privacy/GPU acceptance.')
    elif finding.startswith(('P34-','P35-','P36-','P37-')):
        row.update(status='INTEGRATED bounded repair independently reverified',candidate_fix='3fbfbf6; e5af0e7 for P34-R1/R2/R3',fresh_evidence='candidate-final.xml; model-paths-after.xml',follow_up='Read case-level scope and remaining runtime/principal/concurrency gates; new model-path repair is separate.')
    elif finding.startswith(('P31-','P32-','P33-')):
        row.update(status='RETAINED bounded boundary repair',candidate_fix='historical committed repair',fresh_evidence='candidate-final.xml',follow_up='Native/live identity and concurrency acceptance remain incomplete.')
    else:
        row.update(status='RETAINED audit/test compatibility repair',candidate_fix='3fbfbf6',fresh_evidence='candidate-final.xml',follow_up='Harness path overrides are explicit; isolated default readiness is still repair_required.')
ledger.append({'finding':'V2-004 / P99-R8','status':'P1 FIXED IN LOCAL CANDIDATE; NOT IN CLAUDE',
    'pinned':SHA,'candidate_fix':'source-only.patch / codex-review proposal, commit null',
    'fresh_evidence':'model-paths-before.xml 27 FAIL/4 PASS; model-paths-after.xml 97 PASS; candidate-final.xml',
    'follow_up':'Review model alias validation at authorization and transport boundaries, integrate accepted patch on claude and rerun; approved/configured malformed alias required.'})
with (OUT/'05-findings-ledger.csv').open('w',newline='',encoding='utf-8') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(ledger[0]));writer.writeheader();writer.writerows(ledger)
mutants=read('mutation-results.json')
assert len(mutants['mutants'])==6 and all(row['killed'] and row['restored_control']['returncode']==0 for row in mutants['mutants'])
environment=read('environment-readback.json')
assert all(row['pip_check_returncode']==0 for row in environment['environment_results'])
bench=read('guard-benchmark-summary.json')
cleanup=list(csv.DictReader((OUT/'benchmarks.csv').open(encoding='utf-8')))
cleanup_summary={}
for revision in ('pinned','current'):
    rows=[row for row in cleanup if row['revision']==revision];values=sorted(int(row['elapsed_ns']) for row in rows)
    cleanup_summary[revision]={'n':len(rows),'p50_ns':statistics.median(values),'p95_ns':values[math.ceil(.95*len(values))-1],
        'sample_variance_ns2':statistics.variance(values),'cleanup_successes':sum(row['cleanup_before_harness']=='True' for row in rows)}
dump('benchmark-summary.json',{'new_guard':bench,'historical_repair_a9_vs_e5af_observer':cleanup_summary,
    'no_end_user_gain_claim':True,'concurrent_background_regression_load':'May affect timing; paired inputs/order controlled, host not claimed idle.'})
write('01-source-audit.md',f'''# Independent source review — 2026-10-20
Pinned Claude `{SHA}`. Actual tested source is separate detached checkout; live Claude remains untouched except its pre-existing user config modification. Candidate is the same parent plus a two-file proposal authored in retained codex-review and tested in a second detached checkout. No candidate commit invented. [Revisions](review-revisions.json), [exact patch manifest](patch-manifest.json), [source graph](source-graph.json), [claims/call paths](claim-evidence-map.json).
560 production Python files parse at pin and candidate; 266 top-level Jarvis modules, 120 actual ToolRegistry specs. Registry existence is not live functionality. Pinned tracked configuration flags are captured with credentials/paths omitted. Main map, Phase 1–8 reports and prior audit reports/results/patches were reopened; {len(parents)} earlier artifacts remain byte-identical. [Historical report index](historical-phase-reports.json).
This is bounded source/call-path and regression review, not exhaustive line-by-line vulnerability or formal type verification. No type checker installation/run claimed. [Candidate AST check](candidate-static-checks.json).
''')
write('02-corpus-inventory.md','''# Corpus provenance
Original Master and all 37 prompt documents found under the recorded Jarvis test pack; exact `00_MASTER_CONTRACT.md` is unavailable. Seven revised downloads and Prompt 99 read/imported; unrelated EDITH master excluded.
1,184 original stable IDs become 1,346 ID+expected-behavior variants after revised cases. [Provenance/hashes](corpus-provenance.json), [mapped specifications](mapped-corpus.jsonl), [coverage](04-coverage.jsonl). Per row: severity, source imports, legacy path, pillar seam and supported environment. Static grouping is explicitly weaker than semantic proof.
The checked-out older catalog hash differs from supplied companion catalog; supplied pack is the imported specification. Planned IDs and the old 797-row checkpoint never become executed PASS by inference. Most full acceptance remains BLOCKED/NOT RUN, even where fixture checks pass.
''')
write('06-failures-and-fixes.md',f'''# Reproductions and repairs
**V2-004 / P99-R8 P1 — approved model alias escapes model store.** Pin `{SHA}` validates digest/budgets but does not constrain model name syntax. `approved_pull` joins a colon-split tag directly into a manifest path. Owned fake-registry case `fixture:../../../../../escaped` publishes a manifest outside its store. Requires a malformed explicitly approved/configured alias, not an unauthenticated remote exploit. No real network/model/account/file was used.
Fresh before: 27 failed guard assertions and 4 valid controls passed. Those are variants of one root cause, not 27 defects. Shared model_reference rejects traversal, absolute paths, backslashes, extra colons, empty tags, URL fragments and unsupported namespace depth. Both final authorization and direct transport call it before HTTP. Resolved manifest destination also must remain within the store.
After: 97 targeted/P34 checks pass; final relevant candidate regression passes. Proposal only; exact two-file diff applies against pin. The candidate checkout has only those two tracked modifications; codex-review retains earlier history plus proposal. [Before XML](model-paths-before.xml), [after XML](model-paths-after.xml), [source patch](source-only.patch).
**IR-004 / V2-003 OPEN P2:** >260-character owned lab cwd still fails before Git at WinError267. Short lab independently passes. Earlier extended-cwd and short-cwd Git -C attempts remain historical failed alternatives; no new OS mutation/relocation attempted. Caller can explicitly choose a shorter owned lab_root; transparent deep-cwd support is unresolved.
One pinned-full pywinauto STA COM warning is retained in final-full.txt. Final skip reasons are preserved per testcase; no warning/skip suppression.
''')
write('07-security-findings.md','''# Security and integrity
New model-store confinement defect is repaired only in proposed candidate. New failing-before/passing-after cases exercise final grant checks and actual downloader with recording fake HTTP; independent file readback proves the old escape and valid control manifests.
Six safety mutants (denied policy, false tool success, stale UIA selector, disabled Verify, held-out tamper, duplicate write) all killed by assertion failures, without collection/runtime errors; controls and restored controls pass. All mutated bytes restored before proposing the two-file fix. Guard fix does not modify those six mutation surfaces. [Mutation results](mutation-results.json).
Global verifier/replay receipt authority and native target/status/hook lifetime remain OPEN P1 (P99-R2). Caller-declared public/synthetic provenance remains OPEN P1 semantic privacy gap (P99-R3). Fake-provider outbound tests do not prove arbitrary private language cannot leak. No real cloud request/private data/account action/native input/model download/install performed.
No deployment readiness while these safety gates remain open.
''')
write('08-performance-benchmarks.md',f'''# Bounded measurements
New guard: 200 randomized warm pairs, fixed valid grant/disk/RAM; one first-call value each. Pin p50/p95 {bench['pinned']['p50_ns']/1e6:.4f}/{bench['pinned']['p95_ns']/1e6:.4f} ms; candidate {bench['candidate']['p50_ns']/1e6:.4f}/{bench['candidate']['p95_ns']/1e6:.4f} ms. [Raw pairs](guard-benchmarks.csv), [variance/bootstrap interval](guard-benchmark-summary.json). Threshold candidate p95 <= pinned p95+1ms passes; no model/task/foreground speed claim. Concurrent regression load may affect timing; host was not claimed idle. Privacy correctness cannot be offset by a timing win.
Separate 30 pairs a9b4ce1/e5af0e7 observer-exception cleanup: 0/30 → 30/30; synthetic fake hook, no physical hook or measured user latency. Those describe earlier integrated repair, not this candidate's gain. [Raw](benchmarks.csv), [provenance](benchmark-provenance.json), [summary](benchmark-summary.json).
Runner-only interim RSS/OS lifetime peaks in interim-memory.json; not aggregate child/assistant/GPU peak. Live TTFT, cold model costs, GPU/RAM full workload, intent precision/recall, domain retention and foreground preemption remain NOT RUN. Full-suite duration differs in scope/load and is not a comparative performance result.
''')
write('09-four-pillars-verification.md','''# Pillar and addition verdicts
| Area | Fresh bounded evidence | Remaining real acceptance |
|---|---|---|
| A | SQLite telemetry/CAPTURED/FIX/DERIVED and generated-MCP contract tests; real owned workbook flow | Live generated server/container/voice invocation and native principal/concurrency |
| B | Failure learning, retrieval to serialized BrainClient request; workbook readback honestly unchanged with fake planner | Actual planner/outcome loop, fresh semantic embeddings/OpenViking/source lifecycle, exploration VM |
| C | Owned Git lab, sealed held-out gate and tamper mutant; short cwd preserved | Deep cwd FAIL; real multi-domain candidate/approval/rollback retention |
| D | Oracle/reward/split/checkpoint/admission fixtures | Fresh training/inference compatibility and resource/preemption; old phase training files remain historical |
| API-first | Actual openpyxl worker readback A1=9/formula preserved, strategy/skills/store | Native app fidelity/signatures/macros/version rollback |
| Cloud | Recording fake consent/privacy/quota/advice-only/dedupe checks | Trusted semantic provenance OPEN P1; real outbound/account not run |
| Show Me Once | Fake hook cleanup/cancel/status and promotion/replay contracts | Physical hook/target binding/global host receipt authority OPEN P1 |
All PARTIAL/BLOCKED at full feature scope. No module wins compensate for another domain's privacy failure.
''')
write('10-legacy-retention.md','''# Legacy and revised modules
Final selection includes deterministic commands, cognition, DAG/tools, desktop/DOM contracts, question/cloud routing, voice/speech ownership fixtures, cyan pointer boundaries, memory/documents/coding, weather/media/email/WhatsApp/God's Eye audit fixtures, UI/Pip and startup/recovery. Exact selected/excluded nodes: candidate-full-selection.json; exact actual outcomes: candidate-final.xml and 03-executed-results.jsonl.
Modules 31–37 bounded regressions run on candidate. Reconfirmed original IR fixes: 33 fresh checks pass. P34-R1/R2/R3 digest-bound transport, final-path venv rebuild/rollback and frozen lock pass intercepted-operation tests; real approved install/download/CDN/Ollama publication remains NOT RUN.
Revised P37: one scoped mock-send/UI acceptance PASS (actual child crash/TaskState/Actions queue/App event consumers/Tk readback, fake outbox/speech); other 25 remain BLOCKED. ReasoningBank seam passes but fake planner deliberately repeats error, so no claimed task improvement or full case closure. Original/revised same-ID behaviors are not conflated.
Full live assistant/account/voice E2E completed: 0. Missing Docker/Ollama and isolated environments/models produce repair_required, without automatic repair. All skip reasons remain explicit. Dated Phase 1–8 screenshots/training/native results are historical, not fresh acceptance.
''')
write('11-mutation-quality.md','''# Mutation quality
Six paired controls/mutants/restored controls: permission deny, false tool success, stale selector, disabled Verify, altered held-out files and duplicate write. 6/6 killed with assertion failures; zero error-only kills. Every prior source byte restored in disposable checkout before candidate patch. Six mutated modules match pinned/candidate hashes, so the later two-file fix does not invalidate this scope.
New model-path suite separately fails on unmodified pin and passes with guard. Neither tests nor mutants establish complete semantic/privacy/hostile-code coverage. [Raw results](mutation-results.json).
''')
write('12-code-fixes-and-diffs.md','''# Concrete Claude proposals
Review/apply source-only.patch against e5af0e7: only jarvis/repair_authorization.py and scripts/setup/setup_brain.py. Add new-test.patch (31 model path variants). Earlier UI and memory regressions remain separately proposed; combined-new-tests.patch includes all three new files (34 test cases total). No source commit/merge/deploy performed.
Exact SHA-256 manifests identify uncommitted candidate. Prior codex-review repairs already integrated at 3fbfbf6 must not be reapplied wholesale; since-prior-v2.patch/since-original-review.patch are lineage, not new proposals. Review only source-only.patch and new tests for this delta. Preserve user config and historical evidence.
''')
write('13-unresolved-blockers.md','''# Remaining Claude handoff
1. P99-R1 earlier production integration RESOLVED for 3fbfbf6/e5af0e7. New V2-004/P99-R8 model-path patch and three portable regression files remain local proposals; integrate accepted diff, commit on claude, independently reverify SHA. No auto-merge.
2. P99-R2 OPEN P1: global independent verifier/receipt/replay authority, native target binding, truthful completion and hook/process acceptance beyond bounded fixtures.
3. P99-R3 OPEN P1: independently establish trusted synthetic/public provenance and adversarial semantic private-context outbound oracle. Caller assertion/regex is insufficient.
4. P99-R4: real approved model/CDN/Ollama visibility and venv rebuild/rollback/console scripts, immutable artifact/concurrency gates, complete advisory/license reachability, principal/service/native-engine/WSL checks. Original P34-R1/R2/R3 code cases now committed and fixture-verified, but real operations NOT RUN.
5. P99-R5: real mic/TTS/native UI/account/GPU/preemption/training/OpenViking/service/version rollback and all feature-off combinations; zero full live assistant E2E. 25 revised P37 cases BLOCKED.
6. P99-R6: 1,184 original IDs/1,346 variants not all semantically implemented/live-proved. No exhaustive vulnerability proof/type checker/complete resource/soak benchmark. See coverage and skip reasons.
7. P99-R7 / V2-003 / IR-004 OPEN P2: deep cwd WinError267; shorter explicit owned lab_root workaround, transparent long-cwd support unresolved.
Do not install, download, use private accounts/data, change OS settings or retry uncertain external actions to clear these without required authorization. Continue all separately safe work; do not certify release from partial fixtures.
''')
write('14-rollback-and-reproduction.md','''# Reproduction and rollback
Pin e5af0e7 in a separate checkout; use existing main interpreter and existing dependency environments read-only. run_suite.py records installed dependency overrides and exclusions. run_candidate_suite.py adds model-path test. Set JARVIS_E2E_DEPENDENCY_APP to original app, JARVIS_E2E_EVIDENCE_DIR to new owned evidence directory; run runner with --root isolated-app --mode full -q --junitxml=new-output.xml. Never rerun old collectors into immutable parent packets.
First run new path test on unmodified pin: 27 fail/4 pass. Apply exact source-only.patch and new tests, run path/P34 neighbors, original-finding checks and full candidate selection. Deep-lab failure is distinct and retained. Benchmark script uses fake resources/no transport.
Rollback new proposal by retaining pinned source or omitting exact two-file diff; no runtime installation/migration happened. Once integrated, revert only this reviewed delta in a normal reviewed commit. Never reset the retained dirty review branch or live config. Temporary owned model/workbook/lab fixtures contain synthetic data. New disposable candidate checkout is retained for reproducibility, not installed as runtime.
''')
write('15-final-verdict.md',f'''# NOT READY FOR DEPLOYMENT — 2026-10-20
Audited Claude `{SHA}`. Review branch remains codex-review at historical a9b4ce1 with preserved earlier changes plus exact current proposal; candidate has parent e5af0e7 and uncommitted two-file patch, no fabricated SHA. [Revisions](review-revisions.json), [manifest](patch-manifest.json), [new source diff](source-only.patch).
**Final distinct candidate checks: {headline}.** Full relevant candidate suite {runs['candidate-final']['PASS']} PASS / 0 FAIL / {runs['candidate-final']['SKIPPED']} SKIPPED; one separate deep-cwd failure on unchanged evolution source. Pin full {runs['final-full']['PASS']} pass/{runs['final-full']['SKIPPED']} skip. Pin new path reproduction 27 fail/4 pass; after repair targeted 97 pass. Prior 33 pass overlaps; counts not summed. [All run counts](run-summary.json), [executed rows](03-executed-results.jsonl).
One new scoped P1 model-path escape reproduced and repaired in candidate, awaiting Claude integration; earlier production repairs independently retained. IR-004/V2-003 remains OPEN P2. Global verifier/native target and cloud provenance remain OPEN P1. [Ledger](05-findings-ledger.csv), [security](07-security-findings.md), [all blockers](13-unresolved-blockers.md).
6/6 valid safety mutants killed with passing/restored controls. 10/10 installed environment consistency checks pass. 560 Python files parse; 120 registered tools do not imply 120 live integrations. 200 paired guard samples meet bounded CPU threshold; no end-user performance claim.
Full live assistant E2E: **0**. Three fresh owned/simulated workflow journals plus actual hidden Tk mock-send restart and workbook/memory seam readbacks are bounded evidence. One revised mock-send/UI case passes its stated scope; 25 revised P37 cases blocked. Pillars A–D, API-first, Cloud and Show Me Once all PARTIAL at full feature scope. Launcher repair_required.
1,184 original planned IDs / 1,346 ID+behavior variants remain separately accounted; the old 797 planned IDs are not called executed passes. Earlier {len(parents)} artifacts unchanged. Review/apply exact patches, return committed SHA and stage approved disposable live acceptance. No merge, install, cloud/account action or deployment performed. STOP at review boundary.
''')
# Consolidate new portable tests, while preserving earlier packet bytes.
patches=[OUT/'new-test.patch',APP/'artifacts/jarvis-audit/modules/37-e2e/2026-10-20-independent-e5af0e7/new-test.patch',
         APP/'artifacts/jarvis-audit/modules/37-e2e/2026-10-20-memory-e5af0e7/new-test.patch']
(OUT/'combined-new-tests.patch').write_bytes(b'\n'.join(path.read_bytes() for path in patches))
for name in ['source-only.patch','new-test.patch','combined-new-tests.patch']:
    subprocess.run(['git','apply','--check','--cached',str(OUT/name)],cwd=PIN.parent,check=True)
marker='<!-- prompt99-e5af-review -->'
for path,prefix in [(APP/'README.md',''),(APP.parent/'README.md','app/')]:
    text=path.read_text(encoding='utf-8')
    if marker not in text:
        first,rest=text.split('\n',1)
        block=f'''\n{marker}
**2026-10-20 independent final review — NOT READY FOR DEPLOYMENT:** Claude `e5af0e7`; candidate full {runs['candidate-final']['PASS']} pass/{runs['candidate-final']['SKIPPED']} skip plus one separate unresolved deep-cwd failure. New proposed fix rejects malformed model aliases at authorization and direct downloader boundaries, preventing manifest path escape; supported `name[:tag]` and `namespace/name[:tag]` retain digest-bound transport. Failing-before/passing-after fixtures, 6/6 safety mutants and 10 environment consistency checks recorded. No live assistant certification/install/merge. [Verdict]({prefix}artifacts/jarvis-audit/codex-v2-independent-review/2026-10-20-e5af0e7/15-final-verdict.md), [Claude handoff]({prefix}docs/CLAUDE_HANDOFF.md).\n'''
        path.write_text(first+'\n'+block+rest,encoding='utf-8')
handoff=APP/'docs/CLAUDE_HANDOFF.md'
text=handoff.read_text(encoding='utf-8')
heading='## Prompt 99 - committed e5af0e7 independent re-audit and model-path repair'
if heading not in text:
    section=f'''{heading}

**2026-10-20:** [fresh verdict](../artifacts/jarvis-audit/codex-v2-independent-review/2026-10-20-e5af0e7/15-final-verdict.md), [two-file source proposal](../artifacts/jarvis-audit/codex-v2-independent-review/2026-10-20-e5af0e7/source-only.patch), [three new test files](../artifacts/jarvis-audit/codex-v2-independent-review/2026-10-20-e5af0e7/combined-new-tests.patch), [ledger](../artifacts/jarvis-audit/codex-v2-independent-review/2026-10-20-e5af0e7/05-findings-ledger.csv).

Pin `{SHA}`; full candidate {runs['candidate-final']['PASS']} PASS / 0 FAIL / {runs['candidate-final']['SKIPPED']} SKIPPED plus distinct IR-004 deep-cwd FAIL (WinError267), so {headline} distinct checks. Original 33 finding checks pass; 6/6 safety mutants killed with controls/restored controls; 10 environments consistent. Prior integration P99-R1 resolved at 3fbfbf6/e5af0e7 for earlier production proposals. Historical evidence immutable; no live config edit.

**V2-004/P99-R8 P1 fixed locally:** malformed explicitly approved/configured model alias could publish a manifest outside its model store. Actual owned fake-registry file readback reproduced; 27 failing path variants/4 valid controls before, 97 targeted/P34 pass after. Proposed shared alias parser at final authorization and downloader, plus resolved manifest containment. Only two production files differ from e5af0e7; exact patch applies to pin. This is not an unauthenticated remote exploit. Review/integrate source proposal and model-path/UI/memory tests on claude, commit and independently rerun.

**Still open:** global verifier/replay/native target P1; semantic cloud provenance P1; deep cwd P2; full principal/concurrency/transport/native/voice/account/GPU/training/service/version rollback/feature-off acceptance. Revised P37 remains one scoped mock UI PASS/25 BLOCKED; real ReasoningBank planner loop NOT RUN. [All remaining gates](../artifacts/jarvis-audit/codex-v2-independent-review/2026-10-20-e5af0e7/13-unresolved-blockers.md). No installs/downloads/OS mutations/auto-merge/deploy. STOP at independent review boundary.

'''
    text=text.replace('## Prompt 37 - ReasoningBank repeat continuation at e5af0e7',section+'## Prompt 37 - ReasoningBank repeat continuation at e5af0e7',1)
    handoff.write_text(text,encoding='utf-8')
dump('validation.json',{'parent_artifacts_unchanged':len(parents),'source_hashes_verified':560,
    'candidate_production_files_changed':2,'patches_apply_to_pinned_index':True,'fresh_counts':final,
    'new_tests_in_combined_patch':3,'prior_production_repairs_already_integrated':True})
print(json.dumps({'final':final,'packet':str(OUT)}))
