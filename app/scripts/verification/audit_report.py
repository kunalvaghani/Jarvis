"""Build reports from measured artifacts; pending work never becomes a pass."""
from collections import Counter
import csv
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];OUT=BASE/'artifacts/jarvis-audit'

def write(name,text): (OUT/name).write_text(text.strip()+'\n',encoding='utf-8')
def load(name): return json.loads((OUT/name).read_text(encoding='utf-8'))

def main():
    env=load('environment.json');modules=load('module-map.json');summary=load('summary.json')
    before=load('benchmark-before.json');after=load('benchmark-after.json')
    cases=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    private=BASE/'.jarvis-runtime/jarvis-audit/pre-change'
    # This task's exact source delta, independent of pre-existing dirty changes.
    changed=['jarvis/cognition.py','jarvis/deliberation.py','jarvis/engine.py','jarvis/self_evolution.py',
        'tests/test_knowledge.py','tests/test_media_routes.py','tests/test_natural_names.py','tests/test_codex_validation.py']
    differences=[]
    for name in changed:
        old=private/'dirty-files/app'/name
        if not old.exists():
            old.parent.mkdir(parents=True,exist_ok=True)
            source=subprocess.run(['git','show','HEAD:app/'+name],cwd=BASE.parent,capture_output=True)
            if source.returncode:raise RuntimeError('Cannot establish rollback source: '+name)
            old.write_bytes(source.stdout)
        differences.extend(difflib.unified_diff(old.read_text(encoding='utf-8-sig').splitlines(True),
            (BASE/name).read_text(encoding='utf-8-sig').splitlines(True),fromfile='pre-audit/'+name,tofile='app/'+name))
    write('scoped-source.patch',''.join(differences))
    hashes={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in changed}
    write('changed-source-hashes.json',json.dumps(hashes,indent=2))
    for original,new in [('learning-website.json','browser-journey.json'),('learning-native-current.json','native-journey.json')]:
        if not (OUT/new).exists(): shutil.copy2(BASE/'artifacts/reports'/original,OUT/new)
    readiness=json.loads((BASE/'.jarvis-runtime/jarvis-audit-launcher.log').read_text(encoding='utf-8').strip().splitlines()[-1])
    write('readiness.json',json.dumps(readiness,indent=2))
    # Local static import edges are evidence of dependencies, not runtime cycles.
    graph={k:[v.split('.')[0] for v in item.get('imports',[]) if v.split('.')[0] in env['modules']] for k,item in env['modules'].items()}
    write('dependency-graph.json',json.dumps(graph,indent=2))
    visited=set();stack=[];cycles=set()
    def visit(node):
        if node in stack:
            cycle=stack[stack.index(node):]+[node];cycles.add(' -> '.join(cycle));return
        if node in visited:return
        visited.add(node);stack.append(node)
        for target in graph[node]:visit(target)
        stack.pop()
    for node in graph:visit(node)
    write('static-import-cycles.json',json.dumps(sorted(cycles),indent=2))
    links=[]
    for label,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',(BASE/'docs/system-map.md').read_text(encoding='utf-8')):
        target=target.strip('<>')
        if not target.startswith(('http','mailto:')):
            resolved=(BASE/'docs'/target.split('#')[0]).resolve()
            links.append({'label':label,'target':target,'exists':resolved.exists()})
    write('system-map-links.json',json.dumps(links,indent=2))
    matrix=['| Module | Real candidates / missing names | Executable regression paths | Catalog evidence | Status |', '| --- | --- | --- | --- | --- |']
    for module in modules:
        n=module['number'];rows=[r for r in cases if r['module']==module['module']]
        counts=Counter(r['status'] for r in rows)
        matrix.append('| '+str(n).zfill(2)+' '+module['module']+' | '+', '.join('`'+s+'`' for s in module['sources'])+
            ('; unresolved: '+', '.join(module['unresolved_candidates']) if module['unresolved_candidates'] else '')+' | '+
            ', '.join('`'+s+'`' for s in module['test_candidates'])+' | '+str(dict(counts))+' | PARTIAL |')
    write('inventory.md',f'''# Reality inventory — 2026-10-14 IST

Commit `{env['commit']}`; branch `{env['branch']}`. The initial dirty work is preserved in the private rollback snapshot. See [environment](environment.json), [37-module map](module-map.json), [catalog provenance](catalog-provenance.json), and [system-map link census](system-map-links.json). Both supplied and checkout maps were read; byte equality is reported in provenance (line ending differences need not mean changed claims).

Observed: {len(env['modules'])} Python modules, {len(env['environment'])} interpreter environments, {len(env['integrations'])} integration folders, 82 registered realtime entries. These are census counts, not proof of 82 healthy live endpoints. Each module's real candidate paths and existing assertion suites are below. Missing inferred filenames are recorded, not silently invented. Catalog candidate mapping is a work queue; it does not mean those cases ran.

Actual config/service evidence: Cognition/Actions/Brain are imported and instantiated by `main.py`/`actions.py`; ToolRegistry in `jarvis/tools.py` executes fixed names and scope/policy gates; UIA provider order includes the JarvisPointer before UFO/Windows-MCP/CUA/OpenComputerUse/AgentS (`execution_adapters.PROVIDERS`). Browser uses owned Playwright transport; the fresh local DOM journey passed. LocalGithub is a real local git checkout. Ollama /api/version returned 0.40.0, /api/tags and /api/show were read; configured required Qwen tags are installed. Hermes planner is disabled, DeepSeek Harness enabled. F5 is selected and has its separate CUDA torch environment. Configured does not imply a worker currently running. Launcher `ready` covers dependencies/configured services, not all live feature operations.

Memory, coding, Gmail/WhatsApp, adapters, God's Eye, DeerFlow, Hermes/Harness and REA have executable regression candidates and actual modules, with the boundaries in [security findings](security-findings.md). Account-backed and third-party live actions were not run. Native UIA smoke was blocked by Windows foreground denial. No universal autonomous app control is proven.

## Dependency order and deviations

```mermaid
flowchart LR
  Inventory --> Policy[Permissions and recovery]
  Policy --> Core[Cognition, intent, voice, model admission]
  Core --> Planning[Deliberation, DAG, registry, skills]
  Planning --> Workflows[Desktop, browser, memory, coding, accounts, data]
  Workflows --> Integration[Learning, sandbox, harnesses, REA, UI]
  Integration --> Gates[Security, soak, benchmarks, E2E]
```

The 37 prompts arrived after a narrow cognition audit was underway, so repaired core faults and an initial regression preceded pack ingestion. Full regression exercised the existing suites in pytest order; catalog-specific cases remain dependency ordered for continuation. [Static import graph](dependency-graph.json) and [static cycles](static-import-cycles.json) include lazy imports; cycles are candidates for review, not proof of runtime circular-import failures. No dead-code/duplicate-code completeness claim is made.

'''+ '\n'.join(matrix))
    with (OUT/'benchmark-before-after.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.writer(handle);writer.writerow(['scope','metric','before','after','unit','samples_before','samples_after','interpretation'])
        for key in ('tick_ms','interval_ms','ingress_21_ms','decay_2000_ms'):
            for statistic in ('p50','p95','max'):
                writer.writerow(['cognition fixture' if key!='decay_2000_ms' else 'unchanged memory decay',key+'.'+statistic,before[key][statistic],after[key][statistic],'ms',before[key]['n'],after[key]['n'],'single bounded A/B run; OS/background-load variance'])
        writer.writerow(['intent','accuracy',before['intent']['accuracy'],after['intent']['accuracy'],'fraction',2400,2400,'Authored 800-scenario/2400-phrasing oracle'])
        writer.writerow(['attention','fresh_window_rank1',before['fresh_window_rank1'],after['fresh_window_rank1'],'boolean',1,1,'Fixed stale voice starvation'])
    write('compatibility.md','''# Compatibility and upstream checks — 2026-10-14 IST

Actual interpreter/package versions and requirements text are in [environment.json](environment.json). Main Python 3.10.6: NumPy 2.2.6, SciPy 1.15.3, faster-whisper 1.2.1, CTranslate2 4.6.0, Playwright 1.63.0, pytest 8.4.2. F5 Python 3.10.6: f5-tts 1.1.21, torch 2.6.0+cu124. DeerFlow Python 3.12.14, Hermes Python 3.14.7; environments are intentionally separate. Node v24.14.0, Docker client/server 29.8.2, GPU driver 610.74. Package metadata was read without loading all models.

Official sources retrieved through Firecrawl, not inferred from installed tags:

| Source | Observed contract / date | Decision |
| --- | --- | --- |
| [Python 3.10 threading](https://docs.python.org/3.10/library/threading.html) | Document title 3.10.22; RLock/Thread synchronization; publication date not supplied | Use existing RLock for state transitions; no Python runtime upgrade |
| [Python time](https://docs.python.org/3/library/time.html) | Monotonic clock cannot be set; search excerpt, release date not supplied | Existing tick deadlines retained; wall-time attention age clamped |
| [SciPy betaincinv](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.betaincinv.html) | Positive a,b; observed doc version 1.18.0, build June 19 2026 | Normalize invalid counts; retain installed 1.15.3 API |
| [SciPy 1.15.3 release](https://github.com/scipy/scipy/releases/tag/v1.15.3) | Bug-fix release May 8 2025 | No unsupported blind major upgrade on Python 3.10 |
| [pytest collection](https://docs.pytest.org/en/stable/example/pythoncollection.html) | Naming/discovery rules; release date not supplied | Fix imports and alias imported helper, preserve all real assertions |
| [F5 official repository](https://github.com/SWivid/F5-TTS) | Python 3.10+, MIT code and CC-BY-NC pretrained models; release date not established | Preserve voice environment; commercial deployment/license review unresolved |

No dependencies installed, downloaded or upgraded in this audit. A complete current-release/CVE/license review for every integration is NOT RUN, not a clean bill of health. Official sources are contract checks relevant to the retained changes; package tags and docs versions are not assertions of latest installed-compatible releases. Full provider live contracts, model quality, CUDA peak load and switching costs remain unverified.
''')
    write('failures-and-fixes.md','''# Failures and fixes — 2026-10-14 IST

Baseline: `python -m pytest tests/test_audit_resilience.py -q --junitxml=artifacts/jarvis-audit/baseline-tests.xml` ran 16 assertions: 8 failed, 8 passed. [Baseline XML](baseline-tests.xml) contains exact repro traces. Local paths in traces refer to owned synthetic fixtures.

| Fault | Cause / fix | Proof / rollback |
| --- | --- | --- |
| Attention overflow / amplification on clock rollback | `Percept.weight` allowed positive exp; clamp negative ages to zero | Four numeric-boundary assertions; restore pre-audit cognition.py |
| Fresh window blocked by 200 stale voices | Admission used raw salience while attention used age decay; both now use effective weight plus deterministic timestamp tie-break | Independent fresh-window rank changed false to true; stale-window fixture |
| Invalid statistics crash explanation/deliberation/idle gaps | Prediction normalized rows but other consumers bypassed it; shared locked validated copy now used | Four corrupt-history variants and 133 neighboring tests |
| Stop/reset races with feed | Only feed held lock; reset and activate now use same RLock | Barrier-controlled race test and no-dispatch-after-reset |
| Full pytest collection errors | Three legacy top-level sibling imports, then imported production `test_evidence` helper collected as test | Package fixture imports and helper alias; [collection failures](collection-failures.xml), [first full run](full-first-tests.xml), [final full run](full-tests.xml) |

Catalog fixture corrections: first order assertion assumed title-case names although production intentionally canonicalizes them; volume validation is in the executor, not parser; learned hook is `parse_learned`, not `parse`. Tests were corrected to assert the actual safety contract without weakening executor constraints. First attempts are preserved in catalog-first-tests.xml and private logs. These are test authoring mistakes, not claimed production fixes.

Native smoke failed before task execution: Windows `SetForegroundWindow` refused focus. [Native journey](native-journey.json) remains blocked, not passed. No OS security restriction was bypassed. Scoped source delta is [scoped-source.patch](scoped-source.patch), separate from the pre-existing dirty cognition upgrade.
''')
    write('security-findings.md','''# Security findings and limits — 2026-10-14 IST

Passed executed boundaries include private-context Groq exclusion, forged learned-command precedence, unsupported tool/scope rejection, volume validation without audio mutation, negated-command non-dispatch, bulk destructive task proposal, and uncertain external-write non-replay. Existing Docker repository isolation tests execute only authored throwaway fixtures and assert non-root/read-only mounts, network/process denial and resource limits. No real accounts or private captures were used.

Open release concerns:

1. **AbilityForge host isolation (module 19/35):** `repo_abilities._execute` starts `ability_runner.py` in a host venv subprocess. Python audit hooks/static checking differ from `repo_sandbox.py` kernel isolation. Standard-library generated self-tests can run before activation approval. No live learned code was executed during this audit and no exploit/escape was demonstrated. Arbitrary learned-code host execution is not certified; a bounded Docker migration needs its own compatibility, approval and regression pass. This prevents an all-system security release claim.
2. **Cloud provenance:** regex/NFKC privacy guards pass the authored corpus but cannot prove arbitrary quoted private prose safe. Approved private/screen/file/account material must stay local. No live Groq/private-payload test was sent; live provider contract remains NOT RUN.
3. **Audit traces:** lifecycle events omit arguments/responses, but repository-wide exception/repair-log redaction is not comprehensively proven. No actual credential is stored in this bundle; environment credential flags report presence only. Synthetic exception traces remain. Full adversarial secrets census is pending.
4. **Ground-truth learning:** pending deliberation proposals may still be scored as successful textual task results by `Cognition.act`; terminal task verification reconciliation needs a separate typed-outcome test/repair. No claim of calibrated task success beyond current statistics validation.
5. **Licensing and hardware:** commercial pretrained F5 licensing, human voice similarity/pronunciation, long GPU contention, unattended self-patching and live external account workflows are not release-certified.

No unapproved external writes were performed by this audit. Passing finite fixtures is not a proof of universal absence of leaks. Catalog red-team cases remain visible in test-results.jsonl and remaining-case-ids.txt.
''')
    write('upgrade-decisions.md',f'''# Keep / defer decisions — 2026-10-14 IST

Retain the four localized runtime repairs: observed baseline faults now pass. No registry names, provider order, model pins or approval permissions changed. A/B results in [CSV](benchmark-before-after.csv) used the same 2400 parser oracle and six-second sensor fixtures on this host. Accuracy stayed 2400/2400; fresh-window rank improved false → true. Tick p95 {before['tick_ms']['p95']:.3f} → {after['tick_ms']['p95']:.3f} ms; interval p95 {before['interval_ms']['p95']:.3f} → {after['interval_ms']['p95']:.3f} ms. Ingress p95 {before['ingress_21_ms']['p95']:.3f} → {after['ingress_21_ms']['p95']:.3f} ms: correct age-aware admission costs about {after['ingress_21_ms']['p95']-before['ingress_21_ms']['p95']:.3f} ms per 21-event burst. Retained for correctness; this is an ingress microbenchmark regression, not a universal speed improvement. It remains small relative to the 250ms tick budget. Repeated long production-load equivalence is NOT RUN.

Unchanged decay timing also varied between runs; no speedup is attributed to this audit's unchanged experience.py. Cold parser values include imports and differ with OS cache. No first-token/audio or GPU throughput win is claimed.

Modules 02/09/16/20 share validated statistics/attention improvements; direct-command concurrency module03 improved Stop consistency. Module34/test infrastructure now supports complete pytest collection. Other modules have census/regression evidence but no isolated new baseline/improvement selection; they are **deferred**, not declared already optimal. No-safe-improvement exceptions are not asserted without profiling. Per-module contracts remain pending, as recorded in modules/*/changes.md.

No blind dependency/model upgrades. No new framework or service. Existing launcher, bootstrap, manifest and recovery contracts remain intact; read-only launcher check is ready. No heavyweight model tests ran concurrently (none were launched). Idle learning was never started in fixtures; no running user service was stopped or reconfigured for benchmarking.
''')
    write('rollback.md','''# Rollback and deterministic continuation

Branch `codex/jarvis-prove-fix-audit` preserves the pre-existing dirty work. Do not reset/rebase/clean the checkout. Private snapshot: `.jarvis-runtime/jarvis-audit/pre-change/`; configuration copies and initial dirty-file versions stay local. No config/schema migration occurred. Scoped patch and hashes distinguish this task's runtime/test repairs from prior changes.

To roll back, first stop the owned Jarvis app deliberately, then compare `scoped-source.patch` and copy only each chosen pre-audit file from `pre-change/dirty-files/app/...` to the matching app path using PowerShell `Copy-Item -LiteralPath`. Preserve any newer user edits separately first. Do not restore config unless you changed it independently: this audit did not. Restore the four test-only fixture imports/alias only if returning to unittest-only discovery. Keep evidence and newly authored tests for diagnosis; no recursive deletion is needed.

Resume: read final-report.md, summary.json and remaining-case-ids.txt; verify current source hashes before editing. The source pack is `D:/Phython Project/Jarvis test`. Run from app with `.venv/Scripts/python.exe`. `-m scripts.verification.audit_catalog --reconcile` recomputes exact status from executed dedicated catalog XML. For each remaining ID, implement its own assertion or a reviewed complete equivalent, then run `-m pytest tests/test_audit_catalog.py -q --junitxml=artifacts/jarvis-audit/catalog-tests.xml`. Never mark cases from merely similar regression names. Preserve old benchmark JSON before a repeat (`audit_benchmark` refuses overwrites). Run full pytest and launcher check after repairs. For module19 begin with host isolation/approval reconciliation; do not execute untrusted learned code while investigating.
''')
    count=summary['catalog_counts'];runs=summary['runs']
    report=f'''# Jarvis audit — bounded implementation pass, 2026-10-14 IST

**Not an all-system production-ready certification.** The supplied 37 prompts were read, all 1,184 unique case IDs were ingested and mapped, actual repairs and tests ran, and the exact remaining IDs are preserved. The full catalog and per-module upgrade loop are incomplete. No pending case is called a pass.

Repo `{env['commit']}`, branch `{env['branch']}`. Main Python 3.10.6; 8 physical / 16 logical CPUs; {env['hardware']['ram_total_bytes']/2**30:.2f} GiB RAM; actual NVIDIA RTX3050 Laptop 4096MiB, driver610.74. Node24.14.0, Docker29.8.2 Linux, Ollama0.40.0. Hardware CPU brand was not independently captured. Credential values/recordings are excluded. [Full inventory and source-map evidence](inventory.md), [versions/upstream dates](compatibility.md), [dependencies](dependency-graph.json).

## Executed tests and catalog accounting

Catalog totals: **{count}** over all **1184**. Missing keys have count zero; no cases were silently skipped. All unimplemented cases stay NOT RUN because most can use fixtures; absent live validation does not justify skipping an offline assertion. [Exact ID ledger](test-results.jsonl), [remaining IDs](remaining-case-ids.txt), [tier/category totals](summary.json). Next incomplete module/case: **{summary['next_case']}** (architecture-inventory).

Executed test run totals (separate from catalog): {runs}. Neighbor run:133 passed/17.15s. New resilience baseline:8 failed/8 passed; repaired assertions pass in the neighbor/full suite. See [JUnit full run](full-tests.xml), [catalog run](catalog-tests.xml), [baseline](baseline-tests.xml), [individual executed test ledger](executed-tests.jsonl). Do not add overlapping runs as unique tests.

Fresh owned browser DOM journey passed in2.875s, with independent page readback and authored planner; [browser evidence](browser-journey.json). Native UIA journey **BLOCKED** by Windows foreground refusal before execution; [native evidence](native-journey.json). Launcher dependency/configured-service readiness **ready**; [readiness](readiness.json). [30-second synthetic soak](soak.json) records actual memory/cycles/shutdown assertions. No real Gmail/WhatsApp sends/deletes, personal document ingestion, arbitrary learned scripts, credential changes, OS mutations, installs or publishing occurred.

## Changes and measurements

Runtime changed: {', '.join('`'+n+'`' for n in changed[:4])}. Test infrastructure changed: {', '.join('`'+n+'`' for n in changed[4:])}. Added `tests/test_audit_resilience.py`, `tests/test_audit_catalog.py`, verification `audit_snapshot.py`, `audit_catalog.py`, `audit_benchmark.py`, `audit_soak.py`, `audit_report.py`; report bundle and README/doc index updates. [Exact source delta](scoped-source.patch), [hashes](changed-source-hashes.json), [failure causes](failures-and-fixes.md), [keep/defer decisions](upgrade-decisions.md), [rollback](rollback.md).

Comparable oracle accuracy remained100%; age-aware admission fixed stale-voice starvation. Tick p95 {before['tick_ms']['p95']:.3f}→{after['tick_ms']['p95']:.3f}ms and interval p95 about265ms in both runs. Ingress p95 {before['ingress_21_ms']['p95']:.3f}→{after['ingress_21_ms']['p95']:.3f}ms is the explicit correctness/performance tradeoff. [Before/after CSV](benchmark-before-after.csv) and JSON preserve sample counts. These are bounded fixture measurements, not exact250ms hard-real-time, universal 2-second replies, speech quality, task success rate or GPU efficiency certification.

## Release gate and remaining risks

Scoped repaired assertions/regressions passed: final full XML has1851 PASS, no failed/error/skipped tests. Seven additional reviewed catalog equivalents were executed after that full run, passing in the27-test catalog suite; its extra assertions did not change runtime code. No observed privacy/approval/non-replay regressions in executed fixtures. All-system release gates remain **INCOMPLETE**:1165-ish pending catalog cases (use summary for exact count), module19 host ability isolation, full secrets/redaction adversarial audit, task outcome reconciliation, live account/provider and GUI coverage, human voice quality, current advisories for all dependencies and repeated cold/warm GPU/TTFT/switch/restart benchmarks. See [security findings](security-findings.md). No measured upgrade is claimed for each of all37 subsystems.

## Commands actually run

From app: `-m scripts.verification.audit_snapshot`; `-m scripts.verification.audit_benchmark --phase before` and `--phase after`; targeted pytest for resilience/cognition/deliberation/self-evolution/commands; `-m scripts.verification.audit_catalog --pack "D:/Phython Project/Jarvis test"`; catalog pytest; `-m pytest tests -q --junitxml=artifacts/jarvis-audit/full-tests.xml`; `-m scripts.verification.verify_learning_website`; `-m scripts.verification.verify_learning_native --implicit-current-app`; `-m scripts.verification.audit_soak`; `-m jarvis.launcher --check`. Failed first attempts are retained. Use [rollback/continuation](rollback.md) to continue with exact remaining IDs; no background work is promised.
'''
    report=report.replace('1165-ish pending catalog cases (use summary for exact count)',str(count.get('NOT RUN',0))+' pending catalog cases')
    if any(OUT.glob('modules/*/scoped-report.json')):
        # This historical baseline generator must not erase later scoped reports.
        write('baseline-report-rebuild.md',report)
    else:
        write('final-report.md',report)
    # Each requested module directory records actual evidence and pending scope.
    for module in modules:
        prefix=f"{module['number']:02}-{module['module']}";directory=OUT/'modules'/prefix;directory.mkdir(parents=True,exist_ok=True)
        if (directory/'scoped-report.json').exists():
            continue  # Detailed follow-up reports are authoritative; preserve their evidence.
        own=[r for r in cases if r['module']==module['module']]
        content={'inventory.md':module['title']+'\n\nPARTIAL. Sources: '+str(module['sources'])+'\n\nMissing inferred candidates: '+str(module['unresolved_candidates'])+'\n\n[Whole inventory](../../inventory.md)',
            'tests.jsonl':''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in own),
            'failures.md':'# Status\n\n'+str(dict(Counter(r['status'] for r in own)))+'\n\n[Observed faults and repros](../../failures-and-fixes.md). Remaining catalog cases are NOT RUN, not presumed healthy.',
            'changes.md':'# Scope\n\n'+('Shared cognitive resilience repairs retained; [exact delta](../../scoped-source.patch).' if module['number'] in (2,3,9,16,20) else 'No runtime change retained for this module in this bounded pass; independent baseline/upgrade selection pending.')+'\n\nExisting full regression evidence is separate from completing this module contract.',
            'compatibility.md':'# Compatibility\n\n[Observed versions and checked official contracts](../../compatibility.md). A current upstream/CVE review for every dependency of this module is incomplete.',
            'rollback.md':'# Rollback / resume\n\n[Scoped restoration and exact ID continuation](../../rollback.md). Preserve user changes and credentials.',
            'benchmarks.csv':'module,status,evidence\n'+module['module']+',"'+('SHARED MEASUREMENT' if module['number'] in (2,3,9,16,20) else 'NOT RUN')+'",../../benchmark-before-after.csv\n'}
        for name,text in content.items():(directory/name).write_text(text+'\n',encoding='utf-8')
    print('Wrote audit bundle and 37 module ledgers; remaining',count)

if __name__=='__main__':main()
