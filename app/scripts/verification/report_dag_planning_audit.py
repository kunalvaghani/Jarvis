"""Publish Prompt10 from executed XML, paired measurements and saved preimages."""
from collections import Counter
import contextlib
import difflib
import hashlib
import io
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
ROOT=BASE/'artifacts/jarvis-audit';OUT=ROOT/'modules/10-dag-planning'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module10-pre'
RUNTIME=('jarvis/dag_execution.py','jarvis/hierarchical.py','jarvis/task_state.py')
FILES=(*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py',
       'scripts/verification/verify_dag_planning_audit.py','scripts/verification/report_dag_planning_audit.py',
       'tests/test_dag_planning_audit.py','README.md','docs/hierarchical-execution.md','docs/hierarchical-benchmarks.md','docs/system-map.md')
SOURCES=[
 {'url':'https://docs.python.org/3.10/library/concurrent.futures.html','checked':'2026-10-15 IST via Firecrawl','release_date':None,
  'finding':'Running futures cannot be forcibly cancelled by cancel_futures or a wait timeout. Thread draining remains cooperative; page identifies Python3.10.22.'},
 {'url':'https://sqlite.org/changes.html','checked':'2026-10-15 IST via Firecrawl','release_date':'2026-10-09','version':'3.54.0',
  'finding':'Official current release page mentions WAL-reset corruption fixes. Local bundled3.37.2 is older. Applicability of a particular CVE/fix to this runtime was not inferred; no binary upgrade.'},
 {'url':'https://docs.ollama.com/capabilities/structured-outputs','checked':'2026-10-15 IST via Firecrawl','release_date':None,
  'finding':'Local format schema and independent response validation; no permission-granting claim. Existing local transport retained.'},
 {'url':'https://www.python.org/downloads/release/python-31022/','checked':'Same-day Prompt09 official Firecrawl check retained','release_date':'2026-10-01','version':'3.10.22',
  'finding':'Security/source-only release; installed3.10.6 is older. Interpreter migration needs separate native/GPU environment compatibility testing.'},
]


def write(path,value):path.write_text(value,encoding='utf-8')


def result(name):
    tree=ET.parse(OUT/name);nodes=list(tree.iter('testcase'))
    assert nodes and not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    skipped=[n for n in nodes if n.find('skipped') is not None]
    assert all('BLOCKED:' in n.find('skipped').get('message','') for n in skipped)
    return {'passed':len(nodes)-len(skipped),'blocked':len(skipped),'seconds':float(next(tree.iter('testsuite')).get('time',0))}


def main():
    baseline=result('existing-baseline.xml');targeted=result('cases-and-contracts.xml');full=result('full-regression.xml')
    for name in RUNTIME:assert (OUT/'full-regression.xml').stat().st_mtime >= (BASE/name).stat().st_mtime
    repro=list(ET.parse(OUT/'reproduced-failures.xml').iter('testcase'))
    assert sum(n.find('failure') is not None for n in repro)==7
    assert sum(n.find('failure') is not None for n in ET.parse(OUT/'restore-dependency-reproduced.xml').iter('testcase'))==1
    modules=json.loads((ROOT/'module-map.json').read_text())
    modules[9].update(status='FIXTURE COMPLETE / LIVE ACCEPTANCE UNVERIFIED',
      reason='32 catalog fixture PASS; scoped DAG/cache/restore fixes, measured fingerprint tradeoff, full regression/readiness. No native model/account/UI or automatic partial rollback certification.',
      sources=[*RUNTIME,'jarvis/brain.py','jarvis/task_recovery.py','jarvis/tools.py','docs/hierarchical-execution.md','docs/hierarchical-benchmarks.md'],
      test_candidates=['tests/test_dag_planning_audit.py','tests/test_hierarchical.py','tests/test_task_graph.py','tests/test_task_state.py','tests/test_task_recovery.py'])
    write(ROOT/'module-map.json',json.dumps(modules,indent=2)+'\n')
    from scripts.verification.audit_catalog import reconcile
    with contextlib.redirect_stdout(io.StringIO()):reconcile()
    rows=[json.loads(s) for s in (ROOT/'test-results.jsonl').read_text().splitlines()]
    cases=[r for r in rows if r['id'].startswith('JRV-10-')]
    assert len(cases)==32 and all(r['status']=='PASS' for r in cases)
    for row in cases:row['scope']='Production policy/scheduler/cache/checkpoint boundaries with isolated local data and fake external transports.003 generic fake mail dependency/approval fixture plus preservation of specialized production mail, not a production DAG mail adapter.021 exercises actual dag_plan local worker private transport with fake discovery/chat and cloud enabled, plus opinion privacy. No live account, GUI, GPU/model quality or arbitrary rollback claim.'
    write(OUT/'tests.jsonl',''.join(json.dumps(r)+'\n' for r in cases));write(OUT/'remaining-case-ids.txt','')
    summary=json.loads((ROOT/'summary.json').read_text());assert sum(summary['catalog_counts'].values())==1184
    bench=json.loads((OUT/'benchmark-summary.json').read_text())['results']
    ready=json.loads((PRE/'readiness-private.json').read_text(encoding='utf-8-sig'));assert ready['status']=='ready'
    assert not ready.get('missing') and not ready.get('incomplete')
    write(OUT/'readiness.json',json.dumps({'date':'2026-10-15 IST','command':'.venv/Scripts/python.exe -m jarvis.launcher --check','status':ready['status'],
        'exit_code':0,'scope':ready.get('scope'),'services':{k:v['status'] for k,v in ready.get('services',{}).items()}},indent=2)+'\n')
    write(OUT/'upstream-checks.json',json.dumps(SOURCES,indent=2)+'\n')
    patch='';hashes={}
    for name in (*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py'):
        path=BASE/name;old=PRE/Path(name).name
        patch+=''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),path.read_text(encoding='utf-8').splitlines(True),fromfile='module10-pre/'+name,tofile=name,n=1))
        hashes[name]={'before':hashlib.sha256(old.read_bytes()).hexdigest(),'after':hashlib.sha256(path.read_bytes()).hexdigest()}
    write(OUT/'source.patch',patch);write(OUT/'source-hashes.json',json.dumps(hashes,indent=2)+'\n')
    files=[{'path':'app/'+name,'sha256':hashlib.sha256((BASE/name).read_bytes()).hexdigest()} for name in FILES]
    files.append({'path':'README.md','sha256':hashlib.sha256((BASE.parent/'README.md').read_bytes()).hexdigest()})
    write(OUT/'files-changed.json',json.dumps({'scope':'Prompt10 scoped files; pre-existing dirty work preserved, no commit or deployment.','files':files,
        'artifacts_directory':'app/artifacts/jarvis-audit/modules/10-dag-planning',
        'shared_artifacts':['final-report.md','module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt']},indent=2)+'\n')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=BASE,text=True).strip()
    matrix='''| Claim | Real implementation / stable entry points | Executed boundary and limit |
| --- | --- | --- |
| Typed DAG/dependencies | [dag_execution.py](../../../../jarvis/dag_execution.py):validate_plan/references/resolve | Unknown/cyclic plans rejected, three reads synchronize concurrently, downstream waits for typed result, wrong type fails before use |
| Serial effects and consent | Executor.run/work + existing tool authorize/call | Per-graph writes serialize even without resource labels; fresh admission/worker checks; fake draft→approval→send ordered/denied; actual mail stays specialized |
| Restore/recovery | Executor.run restored, [task_state.py](../../../../jarvis/task_state.py):update_dag, [task_recovery.py](../../../../jarvis/task_recovery.py) | Exact-step/resolved-argument SHA256 binding and fresh verification; disk restart reuses safe read, changed input reruns; any uncertain effect refuses replay |
| Task ownership | [hierarchical.py](../../../../jarvis/hierarchical.py):run/scoped_authorize/checkpoint | Current UUID bound to DAG updates/authorization; stale task cannot overwrite newer task state; optional legacy API callers must opt in |
| Verified templates | MacroMemory.lookup/remember, fingerprint | Deleted tool changes signature, corrupt/oversized JSON is miss, candidate revalidated; read-only only, recognized credential templates omitted; old rows retained |
| Fingerprint reuse | implementation_hash/fingerprint | File identity/size/mtime/ctime checked, content digest reread after change, bounded64-entry lock-protected cache; not anti-tamper against metadata forgery; Windows ctime is creation time |
| Resource/replan bounds | hierarchical.run + Executor | Low-RAM fixture serializes, nonzero GPU reservation rejected, failed read replans once then pauses, three read retries capped; worker/thread cleanup,100 five-way requests |
| Public integration | [brain.py](../../../../jarvis/brain.py), tools.py, existing specialized workflows | Existing actual Actions/ToolRegistry local-file/cache/repair/summary fixture reused; synthesis transport faked, no native model quality claim |
'''
    metrics='\n'.join(f'| {key} | {v["samples"]} | {v["p50_ms"]:.4f} | {v["p95_ms"]:.4f} | {v["peak_python_bytes"]} |' for key,v in bench.items())
    commands='''.venv/Scripts/python.exe -m pytest tests/test_hierarchical.py tests/test_task_graph.py tests/test_task_recovery.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/10-dag-planning/existing-baseline.xml
.venv/Scripts/python.exe scripts/verification/verify_dag_planning_audit.py
.venv/Scripts/python.exe -m pytest tests/test_dag_planning_audit.py tests/test_hierarchical.py tests/test_task_graph.py tests/test_task_state.py tests/test_task_recovery.py tests/test_cognition_and_routing.py tests/test_deliberation_audit.py tests/test_audit_result_accounting.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/10-dag-planning/cases-and-contracts.xml
.venv/Scripts/python.exe -m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/10-dag-planning/full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check'''
    write(OUT/'commands.txt',commands+'\n')
    write(OUT/'inventory.md',f'''# Prompt10 — hierarchical DAG and verified plan-cache audit

2026-10-15 IST. **32 catalog fixture PASS;0 FAIL/BLOCKED/SKIPPED/NOT RUN.** Live acceptance remains unverified. Module completion is not whole-system production certification.

Repo `{commit}`, branch `{branch}`; Windows/Python{platform.python_version()}, bundledSQLite{sqlite3.sqlite_version}; Ryzen7/32GB/RTX3050 Laptop4GB target from earlier native observations. No new GPU/model work here. app/ is canonical; InsTAREELS alias not separately edited. Existing dirty changes preserved. No account send/write, personal deletion, OS mutation, ability install, credential setup, package/model download, commit or deployment.

## Source map, graph and execution order

{matrix}

Read docs/system-map.md, hierarchical-execution.md and hierarchical-benchmarks.md; historical linked measurements retained as historical, not rerun claims. Sources and current registrations/configuration were inspected. Run order: schema/effect contracts → checkpoint ownership/restore → cache → failure/consent boundaries → repeated/concurrent fixtures → matched fingerprint benchmark → full regression/readiness. Actual brain.hierarchical_execution defaults retained: enabled/parallel_reads/macro_cache true, concurrency3, max_seconds300, repairs/replans1. Unknown keys now rejected. No new dependency/service/tool name. Existing launch/stop/recovery path retained.

## Executed results

Baseline **{baseline['passed']} PASS**,{baseline['seconds']:.2f}s,[XML](existing-baseline.xml). Before-fix regressions **7 FAIL/1 PASS**,[XML](reproduced-failures.xml): effect overlap, stale argument restore, corrupt cache JSON, exception-secret persistence, missing guarded task update, recursive JSON encoding, credential template retention. Final review reproduced **one additional stale-descendant failure** when upstream readback changed,[XML](restore-dependency-reproduced.xml),and fixed it: descendants require currently verified prerequisites. **8 reproduced defects fixed in total.** NaN config was already rejected; not counted as a new fix. A later catalog invocation had one missing fixture subdirectory, corrected without changing product behavior; [retained failure](catalog-first-fixture-error.xml).

Final targeted **{targeted['passed']} PASS/{targeted['blocked']} existing explicit BLOCKED skip**,{targeted['seconds']:.2f}s,[XML](cases-and-contracts.xml). Full **{full['passed']} PASS/{full['blocked']} explicit BLOCKED skips**,{full['seconds']:.2f}s,[XML](full-regression.xml),[actual completion chunk](full-run-completion.txt). Counts overlap; do not sum. One existing pywinauto STA COM warning remains. Launcher **ready**,[redacted check](readiness.json). [Commands](commands.txt),[32 case IDs/assertions/scopes](tests.jsonl).

Safe journeys use actual file/registry/cache/repair/summary boundaries with controlled inference, a persisted read checkpoint/new TaskState, low-RAM serial admission, two bounded failed-read plans, and fake compose/preview/approve/send. Five independent DAG requests×20 rounds assert100 unique traces/task isolation/thread cleanup. Generic fake mail tools are not enabled production adapters. No approval or world effect is inferred from model/tool claims. Partial successful work is retained; there is no automatic undo of irreversible changes.

Final boundary assertions cover cancellation during result verification and actual Models.predict dag_plan private context with cloud enabled: fake local chat receives the synthetic payload and Groq calls0. They do not certify live native model output. The first full run passed before those final assertions and the stale-descendant correction; an intermediate rerun was interrupted for that correction. Preserved prior full XML is historical; only final full-regression.xml represents accepted code/tests.

## Paired component measurement and keep decision

| Fingerprint mode | Samples | p50 ms | p95 ms | Peak traced Python bytes |
| --- | --- | --- | --- | --- |
{metrics}

[Raw50 samples](benchmarks.csv),[scope/summary](benchmark-summary.json). Saved pre-change algorithm versus current algorithm on the same current source bytes and machine. Before hashes6 files each call; after checks8 files/model labels with cached content digests. Five cleared digest-cache calls and20 warm calls/version; cold is not cold OS/model state. Tracemalloc covers operation allocations, not whole-host RAM. No model/tool/network dispatch or external side effects; TTFT/first audio/VRAM not applicable, not zero. Initial during-workload measurements are preserved separately when the final quiet rerun exists.

Warm p95 **{bench['before_warm']['p95_ms']:.3f}→{bench['after_warm']['p95_ms']:.3f}ms**, cold p95 **{bench['before_cold']['p95_ms']:.3f}→{bench['after_cold']['p95_ms']:.3f}ms**. Retain avoided repeated source reads and lower warm transient allocation with tested invalidation; cold metadata/source checks cost more. A small timing difference is not a statistically established whole-task speedup. Safety fixes are retained for correctness; no faster unsafe writes, no native-model or voice latency claim.

## Remaining risks and exact scope

Cancellation is cooperative and drains owned work; an uncooperative backend waits for its timeout. Serial effects are per graph, not a global cross-process lock. Automatic rollback is not provided; partial progress is checkpointed. Native model planning/semantic accuracy, live approval provenance/accounts/UI, physical GPU contention and multi-hour soak were not run. The checkpoint binding is a consistency hash, not an authentication signature. Fresh local read verification and current task policy remain necessary. File metadata reuse is not protection against an actor restoring or forging timestamps; Windows ctime is creation time. New recognized credentials are omitted from templates; arbitrary personal data may remain in local task results/templates, and old rows are not scrubbed. Categorical errors trade detail for privacy. Optional task_id remains backward-compatible; unguarded legacy callers do not gain the new identity guarantee. No broad security or production certificate.

[Changes](changes.md),[failures](failures.md),[upstream/compatibility](compatibility.md),[rollback/resume](rollback.md),[exact files/hashes](files-changed.json),[scoped patch](source.patch). Earliest global blockers remain in the main catalog; no Prompt10 fixture case is pending.
''')
    write(OUT/'failures.md','''# Reproductions and corrections — 2026-10-15 IST

[Before-fix XML](reproduced-failures.xml):7 failures,1 existing NaN-config pass. Effects without resource labels overlapped; restored rows were not bound to changed arguments; corrupt cache JSON escaped; raw exception messages persisted synthetic secrets/email; update_dag lacked a task-bound guard; deep graphs reached recursive JSON encoding; credential templates were stored. [Additional reproduction](restore-dependency-reproduced.xml) exposed a stale restored descendant after upstream readback changed; descendants now require currently verified prerequisites and resolve from current verified rows. Total8 reproduced defects fixed.

Corrections serialize all per-graph effects, bind exact steps/resolved arguments with fresh verification, treat bounded malformed cache as miss, store categorical errors/trace IDs, require current UUID in the production checkpoint/authorization path, pre-bound JSON structure, and omit recognized credential templates. Tests assert no denied dispatch, no uncertain replay, read-only bounded retry/replan and independent state readback. One catalog setup omitted a fixture directory; corrected and recorded separately, not counted as a product defect.

No known failure remains in final executed assertions. Live model/account/UI/GPU acceptance, multi-process write locking, uncooperative-thread containment and arbitrary effect rollback remain unverified/unsupported, not inferred from passing mocks. Local private results remain local; redaction/template screening is heuristic.
''')
    write(OUT/'changes.md','''# Scoped retained changes

- dag_execution.py: bounded JSON before encoding, safe malformed reference types, exact read-restore binding, per-graph write serialization, categorical errors and run UUIDs.
- hierarchical.py: current task-bound authorization/checkpointing, invalid template revalidation/fallback, bounded corrupt-cache miss, recognized credential-template exclusion; bounded source digest reuse with file identity/change invalidation, additional state/privacy sources and model labels in fingerprint; unknown configuration keys rejected.
- task_state.py: optional keyword-only task_id guard for update_dag under its existing lock. Existing callers/tool names remain valid; the production DAG supplies the guard.
- tests/test_dag_planning_audit.py:32 mapped catalog cases and11 supplemental assertions, including changed-upstream restore propagation, using fake transports/isolated state. Existing real-file/cache/repair/summary regression reused. Accounting authorizes this reviewed dedicated catalog class.
- Manifest, README overview and linked guides updated with dated fixture/measurement limits. No dependency/service/config/model install, UI layout/screenshot change, real account action or new public mail capability. No commit; prior dirty work preserved.

See [exact files](files-changed.json),[before/after hashes](source-hashes.json),[scoped patch](source.patch). Keep source digest reuse for reduced repeated I/O/allocation; cold fingerprint overhead is explicit, not hidden behind a universal speedup claim.
''')
    write(OUT/'compatibility.md',f'''# Official current checks and compatibility — 2026-10-15 IST

Firecrawl retrieved [Python futures](https://docs.python.org/3.10/library/concurrent.futures.html), [SQLite release history](https://sqlite.org/changes.html) and [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs). [Machine-readable checks](upstream-checks.json).

Python futures: running threads are not forcibly cancelled by Future.cancel/shutdown cancel_futures or wait timeouts; current docs identify3.10.22, page date unavailable. Existing stdlib cooperative drain is retained. Ollama documents local format schema plus independent response validation; no permission-granting claim, no page release date. No inference provider or model change.

Official SQLite latest observed **3.54.0,2026-10-09**, mentioning WAL-reset corruption fixes; installed bundled version **{sqlite3.sqlite_version}** is older. A specific vulnerability/applicability is not inferred without an advisory audit. Do not drop an untested SQLite DLL into the Windows native environments. Official [Python3.10.22](https://www.python.org/downloads/release/python-31022/) was checked in same-day Prompt09 (**2026-10-01**,security/source-only); installed **{platform.python_version()}** is older and3.10 support ended. Python/native Whisper/F5/brain migration requires separate compatibility work, not automatic package installation. No new dependency or paid API introduced.
''')
    write(OUT/'rollback.md','''# Rollback and resume

Before-change files are preserved in ignored `.jarvis-runtime/jarvis-audit/module10-pre/`; [hash pairs](source-hashes.json) and [scoped patch](source.patch) isolate this module from older dirty work. Compare current hashes and newer user changes before restoring only reviewed hunks; do not reset Git, overwrite unrelated edits or remove personal files. App/root README and guide preimages are also retained. Existing flag rollback: brain.hierarchical_execution.enabled=false restores the legacy path after normal restart; parallel_reads/macro_cache independently disable those features. This audit did not change user configuration.

Reproduce from app/ using [commands.txt](commands.txt), then `.venv/Scripts/python.exe scripts/verification/report_dag_planning_audit.py`. The reporter requires executed successful XML newer than runtime source; it does not run tests or authorize actions. Restored legacy rows without exact binding rerun read observations; effectful rows still require inspection, never automatic replay. No automatic effect undo is performed.

All32 Prompt10 fixture IDs complete. Resume the next requested module11 prompt and exact NOT RUN IDs from the global ledger; earlier acoustic/GPU/mandatory-program-research blockers remain separate. Live authenticated account/UI/model/physical-contention acceptance requires its prerequisites and applicable per-action approval.
''')
    previous=ROOT/'final-report-before-module10.md'
    if not previous.exists():previous.write_bytes((ROOT/'final-report.md').read_bytes())
    module_table='\n'.join(f'| {m["number"]:02} | {m["module"]} | {m["status"]} |' for m in modules)
    next_id=next((r['id'] for r in rows if r['status']=='NOT RUN'),'none')
    write(ROOT/'final-report.md',f'''# Jarvis audit through Prompt10 — 2026-10-15 IST

**Prompt10:32 catalog fixture PASS,0 FAIL/BLOCKED/SKIPPED/NOT RUN.** Targeted **{targeted['passed']} PASS/{targeted['blocked']} existing explicit BLOCKED skip**; full **{full['passed']} PASS/{full['blocked']} explicit BLOCKED skips**,{full['seconds']:.2f}s. [Targeted XML](modules/10-dag-planning/cases-and-contracts.xml),[full XML](modules/10-dag-planning/full-regression.xml),[completion output](modules/10-dag-planning/full-run-completion.txt). Suites overlap. Launcher **ready**,[redacted result](modules/10-dag-planning/readiness.json); one existing pywinauto COM warning. Whole-system production acceptance remains open.

Repo `{commit}`,branch `{branch}`; Windows/Python{platform.python_version()},SQLite{sqlite3.sqlite_version},Ryzen7/32GB/RTX3050 Laptop4GB target. No new GPU/model test. Existing dirty work preserved; no account send, personal deletion, OS/config mutation, ability/install/download, credentials, commit or deployment.

## Changes, source map and measurements

Per-graph serial effects, exact bound read restoration/fresh verification, task UUID checkpoint/authorization guards, bounded invalid-cache fallback, credential-template exclusion, categorical errors/run traces and source digest reuse with metadata invalidation. Baseline32 PASS;8 reproduced failures fixed. [Source-map/dependency/entry-point evidence matrix](modules/10-dag-planning/inventory.md),[failures](modules/10-dag-planning/failures.md),[files/hashes](modules/10-dag-planning/files-changed.json),[scoped patch](modules/10-dag-planning/source.patch),[rollback](modules/10-dag-planning/rollback.md).

Fingerprint warm p50/p95 **{bench['before_warm']['p50_ms']:.3f}/{bench['before_warm']['p95_ms']:.3f}→{bench['after_warm']['p50_ms']:.3f}/{bench['after_warm']['p95_ms']:.3f}ms**; cold p95 **{bench['before_cold']['p95_ms']:.3f}→{bench['after_cold']['p95_ms']:.3f}ms**. Warm peak traced allocation **{bench['before_warm']['peak_python_bytes']}→{bench['after_warm']['peak_python_bytes']} bytes**; operation scope, not total RAM. [50 paired samples](modules/10-dag-planning/benchmarks.csv),[measurement limits](modules/10-dag-planning/benchmark-summary.json). Cold checks cost more; no whole-task/model/voice speed claim. Earlier per-module baselines/metrics remain in [preserved through09 report](final-report-before-module10.md) and linked predecessors.

Official [upstream/compatibility checks](modules/10-dag-planning/compatibility.md): Python thread cancellation is cooperative; SQLite3.54.0 released2026-10-09 versus local{sqlite3.sqlite_version}; Python3.10.22 security/source release2026-10-01 versus local{platform.python_version()}. No untested runtime/library upgrade performed. Structured outputs still need validation and do not grant authority.

## Risk and exact catalog accounting

Per-graph serialization is not a global write lock. Generic fake mail journey is not a production DAG mail adapter; specialized approval paths are preserved. Partial progress is retained, not automatically rolled back. Native GUI/accounts, model quality, physical GPU contention and multi-hour soak were not tested. Metadata cache is not protection against restored or forged metadata; hashes bind consistency, not human identity. Local private results/old templates may remain. Prior acoustic/shared-speech-lease/mandatory-program-research blockers persist. No universal security/production or two-second response certificate.

1184 unique IDs: **{summary['catalog_counts']}**. [Exact case/assertion ledger](test-results.jsonl),[tier/category/run totals](summary.json),[32 Prompt10 cases/scopes](modules/10-dag-planning/tests.jsonl),[remaining IDs](remaining-case-ids.txt). No PASS inferred from merely reading JSONL.

| Module | Name | Status |
| --- | --- | --- |
{module_table}

Earliest global unresolved **{summary['next_case']}**; next NOT RUN **{next_id}**. No Prompt10 fixture case pending. Read the next requested module prompt before proceeding; this report does not claim all37 modules are complete.
''')
    print(json.dumps({'module10':dict(Counter(r['status'] for r in cases)),'targeted':targeted,'full':full,'catalog':summary['catalog_counts'],'next_notrun':next_id},indent=2))


if __name__=='__main__':main()
