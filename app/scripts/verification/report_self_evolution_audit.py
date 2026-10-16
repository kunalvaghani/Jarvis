"""Publish Prompt20 executed proof and explicit missing contracts; never infer live readiness."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/20-self-evolution';PRE=BASE/'.jarvis-runtime/jarvis-audit/module20-pre'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):return json.loads((MOD/name).read_text())
def write(name,s):(MOD/name).write_text(s.strip()+'\n',encoding='utf-8')
def stats(name):
    tree=ET.parse(MOD/name);nodes=list(tree.iter('testcase'))
    return {'PASS':sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in nodes),
        'FAIL':sum(n.find('failure') is not None or n.find('error') is not None for n in nodes),
        'SKIPPED':sum(n.find('skipped') is not None for n in nodes),
        'seconds':sum(float(s.get('time','0')) for s in tree.iter('testsuite'))}


def main():
    from scripts.verification import audit_catalog
    baseline=stats('baseline.xml');target=stats('cases-and-contracts.xml');full=stats('full-regression.xml')
    assert full['PASS']>2750 and baseline['FAIL']==target['FAIL']==full['FAIL']==0
    frozen=load('full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    env=load('environment.json');bench=load('benchmark-summary.json');ready=load('readiness.json')
    assert bench['equivalent'] and bench['external_effects']==0
    modules=json.loads((OUT/'module-map.json').read_text())
    modules[19].update(sources=['jarvis/self_evolution.py','jarvis/anticipation.py','jarvis/anticipation_worker.py',
        'jarvis/repo_learning.py','jarvis/repo_abilities.py','jarvis/actions.py','main.py','docs/self-evolution.md','docs/anticipation.md'],
        test_candidates=['tests/test_self_evolution_audit.py','tests/test_self_evolution.py','tests/test_anticipation.py',
            'tests/test_repo_learning.py','tests/test_repo_abilities.py','tests/test_gpu_scheduler.py'],
        status='PARTIAL',reason='28 catalog fixture PASS/4 missing production contracts BLOCKED; no production self-patch or live model/GUI acceptance')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-20-')]
    blocked={'JRV-20-002','JRV-20-003','JRV-20-006','JRV-20-011'}
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':28,'BLOCKED':4}
    assert {r['id'] for r in cases if r['status']=='BLOCKED'}==blocked
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    summary=json.loads((OUT/'summary.json').read_text());counts=summary['catalog_counts']
    nodes=list(ET.parse(MOD/'full-regression.xml').iter('testcase'))
    skips=[{'node':n.get('classname','')+'::'+n.get('name',''),'reason':n.find('skipped').get('message','')} for n in nodes if n.find('skipped') is not None]
    write('full-regression-skip-reasons.json',json.dumps(skips,indent=2))
    before=bench['before']['warm'];after=bench['after']['warm']
    measured=f"Next-job selection warm p50/p95 **{before['p50_ms']:.4f}/{before['p95_ms']:.4f}→{after['p50_ms']:.4f}/{after['p95_ms']:.4f}ms**, traced peak **{before['python_peak_bytes']}→{after['python_peak_bytes']}B** on the same1,000 eligible/tied fixture rows. Exact selected signature/tie order preserved. This excludes I/O, inference, audio, GPU, construction and energy measurements."
    gates="""- **JRV-20-002 BLOCKED:** No native game/GPU occupancy sensor or guaranteed kernel preemption. Cooperative busy/activity/resource callbacks are tested; blocking I/O/native kernels may finish before yielding.
- **JRV-20-003 BLOCKED:** Learner writes lack a transactional completion receipt. Durable `needs_review` prevents uncertain replays, but automatic safe continuation through an interrupted repository write is not proved; no dedicated review/resume UI.
- **JRV-20-006 BLOCKED:** No independent semantic privacy oracle, hardened host patch execution sandbox, shadow evaluation or canary/automatic post-deploy rollback. A source worktree is not security isolation.
- **JRV-20-011 BLOCKED:** Only a single eligible Jarvis Python source target is supported; no lockfile/environment migration rollout or reproducible dependency environment test exists. Dependency inputs invalidate receipts, but are not upgraded by this manager."""
    scope="""Owned temporary backlogs/files/Git repositories; fake discovery, learners, approval, CPU/RAM/GPU failures and clock. Actual owned child exits29 during discovery; reload returns that read step to pending and completes with a fake learner. Actual trusted Git worktree→pytest assertion→refused approval→approved owned fixture deploy→readback→explicit rollback ran. No Jarvis source was self-patched, no real ability installed, no dependency installation, account operation, OS setting change, model download or live inference/voice/GUI trial. Native Windows power-saving state was read without changing it. The card image is a rendered fixture preview, not a native screenshot."""
    matrix="""| Claim | Actual source/config/entry point | Evidence and boundary |
| --- | --- | --- |
| Idle evolution | Actions creates SelfEvolution with anticipation.busy; starts/closes owned worker; user commands call note_activity | configured enabled/explore true, idle90s/poll5s/cooldown600s/day4; no event-driven scheduler replacement |
| Resource admission | _idle→_resources_ok; _cancelled rechecks resources with≤1s sampled cache | RAM/CPU/low-battery/Windows saver/unknown capacity defer; default RAM3072MB/CPU55%; game/native GPU admission not proved |
| Public gap discovery | CapabilityGapDetector reads cognition, ledger and bounded command history; run_job calls existing RepoLearner | original topics screened before query synthesis; public_query checked immediately before fake search; local PC gap descriptions remain local |
| Persistent backlog | refresh_backlog/_save/_load plus _write_checkpoint | bounded RAM/file backlog; jobs_today survives restart; discover learning state can reopen pending, unknown/learn state needs review; no fsync/power-loss guarantee |
| Preemption | note_activity/stop_current/close→cooperative cancelled callback | before transport/after discovery/readback checks; paused checkpoint retained; no forced shared process kill or native preemption |
| Failure control | max_attempts default3; existing per-job cooldown and daily cap; categorical outcomes | repeated failed exploration≤3; five concurrent independent requests×20 rounds,100 completions; one active job, others retained pending |
| Knowledge versus ability | learner callback drives separate forge; own card reports knowledge saved | no activation/deploy in run_job; tested owned forge proposal remains awaiting approval; per-action gates from module19 retained |
| Anticipation | explicit request/title signals→budgeted one-shot worker→owned draft→review feedback | existing39 anticipation regressions retained; pause/revoke/expiry/microphone behavior; error diagnostics now categorical to suppress fake credentials |
| Patch API | SafeEvolutionManager attached as self.evolution; propose/evaluate/deploy/rollback are APIs | no automatic patch proposal/deploy in idle loop and no new public self-patch command registered |
| Patch scope | canonical inside-base Py paths; traversal/link rejection; named policy/runtime exclusions | source/input size cap; unrelated file types/named policy modules refused; not semantic behavior confinement |
| Evaluation | clean Git snapshot required, controlled full pytest command, worktree tracked-diff scope, changed-candidate check | preserves dirty user checkout; git hooks/global config disabled for evaluation; worktree execution is on host, not Docker; no malicious downloaded patch run |
| Receipt | process-owned validation hash binds target/original/new source, flat source/tests, requirements and runtime config | forged JSON flag insufficient; changed code/test/neighbor invalidates; receipt lost on restart so re-evaluation required; native environment is not reproduced |
| Consent/deploy | Actions._approve wrapper, fresh binding before/after approval; backup and atomic source replacement | rejects nontrue explicit callback answer; None means wrapper success (raises on denial); trusted API callers, not a signed human event ledger |
| Rollback | explicit API validates target still equals deployed candidate and restores exact bytes | refuses later user edit; no automatic canary or rollback on a privacy regression; deployment interrupted in deploying state requires review |
| Diagnostics/UI | per-engine trace UUID in checkpoint/outcome; secret-bearing transport messages replaced by error class | instance correlation, not distributed tracing; pause card distinguishes pending from needs_review; no claim of safe rendering arbitrary historical private data |"""
    write('inventory.md',f"""# Prompt20 audit — 2026-10-16 IST

**28 catalog PASS /4 BLOCKED /0 FAIL /0 SKIPPED /0 NOT RUN.** Baseline **{baseline}**, final targeted **{target}**, full **{full}**. [32 exact IDs/assertions](tests.jsonl), [commands](commands.txt), [targeted XML](cases-and-contracts.xml), [full XML](full-regression.xml), [exact skips](full-regression-skip-reasons.json).

{scope}

{matrix}

{gates}

Read the actual system-map and linked self-evolution/anticipation/repository guides; mapped source/config/callers and treated historic live claims as dated claims. Retained dirty branch **{env['branch']}**, HEAD **{env['commit']}** to preserve user/module14–19 work; a fresh checkout would omit those changes. Before-source snapshots preserved, no reset/commit/deploy/install in the real checkout. Run order: contracts/approval/recovery→baseline→failure reproduction→narrow fixes→official upstream→equivalent A/B→neighbors/owned journey→frozen full/readiness→ledger/docs. [Environment](environment.json), [changes](changes.md), [compatibility](compatibility.md), [rollback](rollback.md).

{measured} [Raw50 samples](benchmarks.csv), [benchmark scope](benchmark-summary.json).
""")
    write('failures.md',f"""# Actual reproductions and remaining gates

Baseline:96 PASS in26.65s. New deterministic reproduction:20 FAIL/10 PASS/4 explicit blockers in1.48s. Failures overlapped: lost pause checkpoint, stuck learning on restart, JSON-only forged test flag, absent saver gate, unbounded exploration retries, raw exception secrets, malformed candidate crashes, post-close work, private/negative gap discovery, stale patch metadata and unvalidated settings/source size/trace fields. Count is failed assertions, not20 distinct flaws.

First targeted:3 FAIL/87 PASS/4 skips. Two fixture issues: exploration test still had a real gap (one gap plus three exploration attempts); owned Git fixture initially committed with global autocrlf settings while evaluation used a sanitized Git environment, making the snapshot dirty. It now uses the same environment for init/add/commit/evaluation. Product over-filtering also rejected benign local 'organize my windows' gap; retained original-topic privacy screening plus public derived-query screening. Second targeted90 PASS/4 skips. Expanded final focused {target}; full {full}. Runtime/tests unchanged during accepted full run.

Old approval unit fixture now supplies an explicitly fake process-owned evaluation receipt rather than merely editing JSON. Approval rejection, target readback, backup and rollback assertions remain; new forged-JSON and changed-source regressions strengthen the gate. Actual owned Git journey executes a real pytest assertion, refuses initial approval, deploys the hand-written fixture only after fake approval and restores it. No real application patch.

{gates}

Other limits: worktree test command executes host Python and has no hostile-code containment. Tracked Git diff validates promoted file scope; untracked/ignored test side-effects are not a hard confinement boundary. Clean-source requirement may conservatively defer under line-ending/config differences. Receipt covers flat source/tests and declared inputs, not all fixtures/native dependencies or complete environment reproducibility. It is process-local, not a cryptographic human-consent signature. Paths/hashes do not prove a patch preserves privacy. Backlog/checkpoint JSON are separate replacements, not one transaction; no fsync/power-failure or multiprocess CAS proof. Rollback metadata/backup is trusted local state. There is no dedicated review UI for needs_review jobs, durable monotonic cooldown restoration, per-job exponential backoff or event-driven polling replacement. Faults use fakes; no native GPU/game/microphone acceptance. Existing Python3.10 end-of-life and global acoustic/retrieval/vault/security gates remain.

Readiness **{ready['status']}**: {ready['missing']}. No production-ready certificate.
""")
    write('changes.md',f"""# Retained implementation and performance decision

self_evolution.py: validate settings/flags/finite counts, isolate mutable defaults; bound source/backlog parsing and memory retention; screen original private/negative goals and derived public queries. Persist daily budgets, stage/repo/trace and interrupted-state classification; keep paused/uncertain checkpoints, require checkpoint storage before transport. Unknown learning completion becomes needs_review; no replay. Cap retries at max_attempts(default3); recheck CPU/RAM/low battery/Windows saver on cooperative cancellation. One active job with pending concurrent callers. Categorical failures/outcome trace UUID and truthful knowledge/pause cards.

SafeEvolutionManager: canonical/link/traversal/named policy scope; size limit before compile; validated patch ID; clean Git evaluation snapshot, controlled full pytest command and tracked-diff candidate scope; process-owned code/test/dependency-input receipt and fresh revalidation around explicit approval. Exact-byte backup, atomic source replacement, consumed receipt before write, explicit stale-safe rollback. No autonomous install, no model weight training, no new tool name or required dependency. Host sandbox/canary/privacy oracle deliberately not claimed.

anticipation.py: categorical failure diagnostic suppresses exception credential strings. Existing grant/revoke/dismiss/Stop/expiry semantics retained. tests/test_self_evolution.py only changes its fake receipt setup; new audit file supplies fault/concurrency/crash/owned Git assertions; accounting registers reviewed blockers. README/system map/guides updated; historical measurements/art attribution retained. [Rendered fixture card](../../../media/self-evolution-paused-preview.png), not a screenshot.

{measured} Cold p50/p95 **{bench['before']['cold']['p50_ms']:.4f}/{bench['before']['cold']['p95_ms']:.4f}→{bench['after']['cold']['p50_ms']:.4f}/{bench['after']['cold']['p95_ms']:.4f}ms**. Keep min-selection instead of allocating/sorting all pending jobs: equivalent winner/ties, lower temporary allocation. Separate instances for5 cold calls and20 warm calls; construction excluded. No end-to-end latency/TTFT/audio/VRAM/energy win claimed. Added checkpoint writes/hashing/approval intentionally cost I/O/CPU; one-job admission reduces possible throughput to protect foreground work. [Exact files](files-changed.json), [preimages](source-hashes.json), [scoped diff](source.patch), [generated artifacts](generated-files.json).
""")
    write('compatibility.md',f"""# Official upstream — checked2026-10-16 IST

Firecrawl primary sources: [URLs/release dates](upstream-checks.json). Installed Python3.10.6, pytest8.4.2, psutil7.2.2, Requests2.34.2, pip26.2.1, {env['git']}; RAM{env['ram_bytes']}B; target/same-machine RTX3050 Laptop4GB. No environment install or heavyweight inference run.

[Windows GetSystemPowerStatus](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getsystempowerstatus) and [SYSTEM_POWER_STATUS](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-system_power_status) document the saver flag. Added read-only ctypes query, verified it runs on this Windows machine; fake on/unknown states defer. API does not measure game occupancy or guarantee scheduler/native preemption. Documentation has no package release date; checked date is not a fabricated release.

[pytest9.1.1](https://pypi.org/project/pytest/) released **2026-06-19**, Python≥3.10; [official changelog](https://docs.pytest.org/en/stable/changelog.html) inspected. Installed8.4.2 retained and executed; no claim9.1.1 was installed/tested. Source evaluation now uses pytest so pytest-style security/privacy regressions are included; the old unittest-only command omitted them. [Git worktrees](https://git-scm.com/docs/git-worktree) supply source isolation, not OS security. [Git for Windows2.56.0(2)](https://git-scm.com/install/windows) dated **2026-10-05**, newer than installed2.49.1.windows.1; no installer/system mutation. Trusted owned fixture worktree commands verified on installed Git.

Prior [module19 environment/security evidence](../19-ability-forge/compatibility.md) records Python3.10 end-of-life2026-10-01 and the separate voice-forge audit-hook/Docker boundaries. Neither is fixed by this audit. Current implementation improved instead of assuming a dependency upgrade is better on4GB VRAM. No paid API requirement or model download added.

{gates}

Live readiness {ready['status']}: {ready['missing']}. GUI/game/native GPU acceptance, arbitrary patch privacy, canary and lockfile rollout remain incomplete;32 fixture IDs do not certify those systems.
""")
    write('rollback.md',"""# Scoped rollback and deterministic resume

No audit commit. Preserve dirty inherited branch and user/module14–19 changes. Compare source.patch and current hashes before restoring only module20 changes from ignored .jarvis-runtime/jarvis-audit/module20-pre (app-relative paths use __; root-README.md for parent). Never reset all, overwrite a vault or discard user source edits. No real self-patch/ability/dependency installation was performed. New max_attempts default3 is additive; no user config file was modified.

Do not downgrade a live pending-learning backlog without reviewing needs_review entries: older code can lose its uncertain-state guarantees. Discover-only interrupted jobs can return pending; interrupted learner writes require fresh state review and an explicit new request, not automatic retry. Process-owned patch test receipts are intentionally not restored across restart; re-evaluate. Rollback applies only while target bytes still equal the deployed candidate; later user edits block overwrite. Restore only a verified backup after inspecting external state.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_self_evolution_audit.py (immutable original preimage A/B).
2. -m pytest tests/test_self_evolution_audit.py tests/test_self_evolution.py tests/test_anticipation.py tests/test_repo_learning.py tests/test_repo_abilities.py tests/test_gpu_scheduler.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/20-self-evolution/cases-and-contracts.xml
3. Freeze jarvis/*.py and tests/test_*.py hashes, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/20-self-evolution/full-regression.xml. No source edits during accepted full run.
4. -m jarvis.launcher --check (read-only), keep raw output in ignored runtime storage; publish only redacted summary.
5. scripts/verification/report_self_evolution_audit.py then scripts/verification/verify_self_evolution_artifacts.py; git diff --check.

Next unrun module/case JRV-21-001; earliest older unresolved JRV-04-001. Current module incomplete002/003/006/011; exact global pending IDs remain in artifacts/jarvis-audit/remaining-case-ids.txt. Resolve these missing contracts with isolated fixtures before live acceptance. Any real source deployment, runtime installation or account action requires the prompt's separate explicit per-action approval.
""")
    headline=f"**Idle evolution audit — 2026-10-16 IST:** Interrupted discovery is recoverable; uncertain learning writes stay in `needs_review`. Daily budgets and a three-attempt cap persist, saver/resource failures defer, and private/negative topics are screened before public discovery. Patches require fresh code/test-bound evaluation and approval; rollback refuses later edits.\nVerification: **{full['PASS']:,} full regression PASS /{full['SKIPPED']} skips**; **28 Prompt20 fixture PASS /4 BLOCKED**. Native game preemption, safe automatic write resume, privacy/canary and lockfile rollout remain open. Launcher **{ready['status']}**."
    import re
    docs=[(BASE/'README.md','artifacts/jarvis-audit/modules/20-self-evolution/inventory.md'),
        (BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/20-self-evolution/inventory.md'),
        (BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/20-self-evolution/inventory.md'),
        (BASE/'docs/self-evolution.md','../artifacts/jarvis-audit/modules/20-self-evolution/inventory.md'),
        (BASE/'docs/anticipation.md','../artifacts/jarvis-audit/modules/20-self-evolution/inventory.md')]
    for p,link in docs:
        value=p.read_text(encoding='utf-8');first,rest=value.split('\n',1)
        rest=re.sub(r'<!-- prompt20-audit -->.*?<!-- /prompt20-audit -->\s*','',rest,flags=re.S)
        image='\n\n![Rendered fixture preview: interrupted learning requires fresh state review](../artifacts/media/self-evolution-paused-preview.png)\n\nRendered fixture preview,560×126; not a live app screenshot. Existing renderer artwork is preserved.\n' if p==BASE/'docs/self-evolution.md' else ''
        if p==BASE/'README.md':image='\n\n![Rendered fixture preview: learning needs fresh state review](artifacts/media/self-evolution-paused-preview.png)\n\nRendered fixture preview, not a native app screenshot.\n'
        p.write_text(first+'\n\n<!-- prompt20-audit -->\n'+headline+'\n[Evidence, limitations and rollback]('+link+').'+image+'\n<!-- /prompt20-audit -->\n\n'+rest.lstrip('\n'),encoding='utf-8')
    guide=BASE/'docs/self-evolution.md';text=guide.read_text(encoding='utf-8')
    text=text.replace('backup → roll back on regression.','backup → explicit rollback after inspecting fresh state.')
    text=text.replace('after the refresh window','up to max_attempts, subject to cooldown/day limits')
    text=text.replace('After a crash or restart, the backlog\n  is restored and an interrupted job returns to `pending` to resume on the next idle tick. **Uncertain\n  learning writes are never replayed** — the learner and forge own their own idempotent resume.',
        'After a crash or restart, discovery-only interrupted jobs can return to `pending`. Interrupted learner writes remain `needs_review`; there is no transactional completion receipt or automatic write resume. **Uncertain learning writes are never replayed automatically.**')
    text=text.replace('- `rollback(pid)` — restores the backup.','- `rollback(pid)` — explicitly restores the backup only while the target still matches the deployed candidate; refuses later edits.')
    text=text.replace('The backlog and a per-job checkpoint are durable and atomic.',
        'Backlog and checkpoints use separate atomic file replacements, not a cross-file transaction or power-loss guarantee.')
    text=text.replace('- `evaluate(pid)` — checks out the repo in an isolated worktree, applies the patch, and runs the test\n  suite there (paths resolved relative to the git root, so a subdirectory `base` works). Deploys\n  nothing.',
        '- `evaluate(pid)` — requires a clean source snapshot, creates an owned Git worktree and runs the full `pytest tests -q` command there. Checks candidate/tracked-file scope and binds a process-owned receipt to source, tests and declared inputs. Dirty work is preserved; a worktree is not a hostile-code sandbox. Deploys nothing.')
    text=text.replace('- `deploy(pid)` — only for a patch whose tests passed, and only after `Actions._approve` grants it;\n  keeps a timestamped backup.',
        '- `deploy(pid)` — requires the fresh process-owned evaluation receipt and explicit `Actions._approve`; rechecks the binding after approval, preserves exact backup bytes and atomically replaces source. Restart requires re-evaluation; an edited JSON passed flag cannot authorize deployment.')
    if '| `max_attempts` |' not in text:
        text=text.replace('| `max_backlog` | `200` | Backlog size (rotated). |',
            '| `max_backlog` | `200` | Backlog size (rotated). |\n| `max_attempts` | `3` | Maximum attempts per item, persisted in the backlog; cooldown/day limits also apply. |')
    guide.write_text(text,encoding='utf-8')
    table='\n'.join('| '+str(m['number']).zfill(2)+' '+m['module']+' | '+', '.join(f'{k}: {v}' for k,v in Counter(r['status'] for r in catalog if r['id'].startswith(f"JRV-{m['number']:02}-")).items())+' |' for m in modules)
    report=f"""# Jarvis audit — Prompt20 — 2026-10-16 IST

{headline}

HEAD **{env['commit']}**, branch **{env['branch']}**; inherited changes preserved, no audit commit. [Environment](modules/20-self-evolution/environment.json). Baseline {baseline}; targeted {target}; full {full}. All **{len(frozen)} frozen runtime/test hashes unchanged**. [Full output](modules/20-self-evolution/full-regression.xml), [skip reasons](modules/20-self-evolution/full-regression-skip-reasons.json), [readiness](modules/20-self-evolution/readiness.json).

{scope}

{measured}

[Source-map-to-code evidence matrix](modules/20-self-evolution/inventory.md), [changes/metrics](modules/20-self-evolution/changes.md), [exact files](modules/20-self-evolution/files-changed.json), [diff](modules/20-self-evolution/source.patch), [upstream URLs/dates](modules/20-self-evolution/compatibility.md), [risk/known flaws](modules/20-self-evolution/failures.md), [rollback/resume](modules/20-self-evolution/rollback.md), [commands/results](modules/20-self-evolution/commands.txt).

{gates}

No production-ready certificate. All1,184 IDs: **{counts}**. [Exact ledger](test-results.jsonl), [tier/category counts](summary.json), [remaining IDs](remaining-case-ids.txt). Next NOT RUN **JRV-21-001**; earliest unresolved **JRV-04-001**; current missing contracts002/003/006/011. [Previous Prompt19 report](final-report-before-module20.md) preserves its original evidence. The overall37-module production audit remains incomplete.

## Enumerated modules

| Module | Catalog statuses |
| --- | --- |
{table}

## Category and tier statistics

```json
{json.dumps({k:summary[k] for k in ('by_category','by_tier')},indent=2)}
```
"""
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    files=['jarvis/self_evolution.py','jarvis/anticipation.py','tests/test_self_evolution.py','tests/test_self_evolution_audit.py',
        'scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py','scripts/verification/verify_self_evolution_audit.py',
        'scripts/verification/report_self_evolution_audit.py','scripts/verification/verify_self_evolution_artifacts.py',
        'README.md','docs/self-evolution.md','docs/anticipation.md','docs/system-map.md','../README.md','artifacts/media/self-evolution-paused-preview.png']
    changed=[];pairs=[];patch=[]
    for name in files:
        current=BASE/name;old=PRE/('root-README.md' if name=='../README.md' else name.replace('/','__'))
        changed.append({'path':name,'sha256':sha(current)})
        if old.exists():pairs.append({'path':name,'before':sha(old),'after':sha(current)})
        if current.suffix=='.png':patch.append('Binary rendered fixture added: '+name+'\n');continue
        patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],current.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name if old.exists() else '/dev/null',tofile='after/'+name))
    write('files-changed.json',json.dumps(changed,indent=2));write('source-hashes.json',json.dumps(pairs,indent=2));write('source.patch',''.join(patch))
    generated=['artifacts/jarvis-audit/'+s for s in ('final-report.md','final-report-before-module20.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt')]
    generated += [p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file()]
    generated += ['artifacts/jarvis-audit/modules/20-self-evolution/'+s for s in ('generated-files.json','artifact-verification.json')]
    generated.append('artifacts/media/self-evolution-paused-preview.png')
    write('generated-files.json',json.dumps(sorted(set(generated)),indent=2))
    print(json.dumps({'module20':dict(Counter(r['status'] for r in cases)),'full':full,'catalog':counts},indent=2))


if __name__=='__main__':main()
