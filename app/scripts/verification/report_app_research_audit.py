"""Evidence-only Prompt15 report/accounting. Run after accepted pytest XML exists."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit'
MOD=OUT/'modules/15-app-research'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module15-pre'


def read(name):return json.loads((MOD/name).read_text(encoding='utf-8'))
def write(name,text): (MOD/name).write_text(text.strip()+'\n',encoding='utf-8')
def xml(name):
    rows=list(ET.parse(MOD/name).iter('testcase'))
    return {'passed':sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in rows),
        'skipped':sum(n.find('skipped') is not None for n in rows),
        'failed':sum(n.find('failure') is not None or n.find('error') is not None for n in rows),'nodes':len(rows)}


def main():
    from scripts.verification import audit_catalog
    baseline=xml('baseline.xml'); targeted=xml('cases-and-contracts.xml');full=xml('full-regression.xml')
    assert baseline['failed']==targeted['failed']==full['failed']==0
    freeze=read('full-start-source-hashes.json')
    assert all(hashlib.sha256((BASE/p).read_bytes()).hexdigest()==h for p,h in freeze.items()), 'Source changed during full run'
    journey=read('browser-journey.json'); assert journey['passed'] and journey['capability']['status']=='verified'
    assert read('provenance-journey.json')['passed']
    bench=read('benchmark-summary.json'); assert bench['equivalent']
    readiness=read('readiness.json')
    mapping=json.loads((OUT/'module-map.json').read_text())
    mapping[14]['sources']=['jarvis/knowledge_acquisition.py','jarvis/app_knowledge.py','jarvis/application_discovery.py','jarvis/tools.py','jarvis/browser_worker.py','docs/autonomous-learning.md','docs/learning-validation.md']
    mapping[14]['test_candidates']=['tests/test_app_research_audit.py','tests/test_knowledge_acquisition.py','tests/test_live_app_context.py']
    (OUT/'module-map.json').write_text(json.dumps(mapping,indent=2)+'\n')
    audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-15-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':31,'BLOCKED':1}
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    write('remaining-case-ids.txt','\n'.join(r['id'] for r in catalog if r['status'] not in {'PASS','SKIPPED'}))
    counts=Counter(r['status'] for r in catalog)
    before=bench['before']['warm'];after=bench['after']['warm']
    scope='Isolated fake public transports, temporary app stores and actual production acquisition/registry/DAG/cache paths. The browser journey additionally uses owned headless Chrome and an intercepted synthetic page with all other destinations aborted. No live model, account, third-party action, native GUI, physical GPU load or long soak certification.'
    write('inventory.md',f'''# Prompt15 — autonomous app/site knowledge, 2026-10-16 IST

31 catalog fixture PASS / 1 BLOCKED. Baseline {baseline['passed']} PASS; targeted {targeted['passed']} PASS / {targeted['skipped']} skip; full {full['passed']} PASS / {full['skipped']} skips / 0 FAIL. [Actual XML](cases-and-contracts.xml), [full XML](full-regression.xml), [all 32 IDs](tests.jsonl).

{scope}

| Claim / dependency | Code / active configuration | Executed boundary |
| --- | --- | --- |
| Gap detection | Brain.propose_plan and hierarchical task → Acquisition.assess/prepare; enabled=true, online=true, background_refresh=false | configured exact app or explicit public origin plus allowlisted feature; unknown name may resolve actual configured foreground, never guessed launch |
| Executable / controls | application_discovery.inspect → configured executable / observation_executables → UI runner; browser_inspect → BrowserAutomation → Session | same-named binaries rejected; password surface clears controls, blocks research/mutation hints; native GUI observation is mocked |
| Task ownership | TaskState UUID → prepare cancellation → registry → existing Executor | changed identity drops results and prevents checkpoint attachment; bounded RLock acquisition wait cancellation |
| Safe reads | _scheduled → ToolRegistry allowed-tools/policy → DAG max2, RAM32MB/GPU0 estimates, attempts1 | no learned script/action installation, no arbitrary effect dispatch; exact source authorization remains existing registry |
| TTL/version | AppKnowledge.capabilities / invalidate_capabilities / remember_capability | seven-day boundary, future timestamp, changed version/signature and stale other-feature exclusion; unknown versions explicitly uncertain |
| Sources | local help → configured documentation_url → optional Firecrawl or free web search | configured exact origin outranks title spoofing; discovered origins unverified. Explicit URL major/minor version hints marked stale; no general semantic version detection |
| Application to task | acquired_context + native_tools.step_update + Brain/SkillMemory | declarative names/roles only, no coordinates/password values; no verification promotion without whole-goal proof |
| Background / lifecycle | self_evolution.py existing idle job, default refresh off; manifest lists acquisition modules, no service added | existing cancellation/resource regressions; no service startup/install/config secret change |
| Plugin interface | no plugin identity/version namespace | JRV-15-010 BLOCKED; host controls cannot prove plugin-specific capability |

Order: existing registry/cache baseline, acquisition failure tests, bounded runtime fixes, source/cache A/B, neighboring integration and actual synthetic browser journey, full regression, launcher readiness and evidence reconciliation. Retained dirty audit/12-tool-registry checkout to preserve inherited user/module14 diffs; scoped preimages provide rollback without resetting unrelated changes. Existing TaskState/registry/DAG interfaces retained. All module docs linked by system-map were inspected: autonomous-learning.md → learning-validation.md and relevant source/registration/configuration references; historical native/model/public checks retain their dates.

[Production provenance-path fixture](provenance-journey.json) supplements the ranking unit contract: an empty configured-doc response triggers search; a spoofed docs title loses to the configured exact origin. Actual registry/Executor dispatch and metadata event IDs verified with fake transports, zero external effects.

Warm lookup p50/p95 {before['p50_ms']:.4f}/{before['p95_ms']:.4f} → {after['p50_ms']:.4f}/{after['p95_ms']:.4f} ms; peak Python traced allocation {before['python_peak_bytes']} → {after['python_peak_bytes']} bytes. [Scope/raw samples](benchmarks.csv), [cold/warm summary](benchmark-summary.json). This is bounded lookup, not whole-task/model/audio/network performance.

Readiness: **{readiness['status']}**; [actual redacted output](readiness.json). See [remaining limits](compatibility.md), [fixes](changes.md), [failure history](failures.md), [rollback](rollback.md).
''')
    write('failures.md','''# Reproduction and fixes

[Original new-test run](reproduced.xml): 13 failing nodes / 21 PASS / 1 explicit blocker. Ten failures represent nine runtime/design families: URL document-version uncertainty (002), same-task version bypass (004), title-based provenance (006), login research/control exposure (012), malformed None/dict controls (015 two variants), private version metadata in public query (021), wrong feature reuse (024), unknown configuration keys (029), unbounded goal (031).

Three initial failures were QA setup, not product defects: 001 wrongly expected no implicit actual-foreground fallback (existing intended behavior), 026 used a nonexistent checkpoint helper (corrected to TaskState.checkpoint), 027 benchmark artifact had not yet been generated. These were corrected explicitly, not counted as runtime fixes. The initial root-cwd sandbox baseline also collected the app/InsTAREELS alias twice and hit WinError5 temporary atomic replace restrictions: existing-baseline.xml retained. Accepted baseline used canonical app cwd and approved isolated fixture filesystem access: 29 PASS. No runtime permission check was relaxed.

Subsequent supplemental guards cover exact TTL, changed other-feature invalidation, native password detection, absent-observation nonreuse, pending-lock cancellation and task replacement during readback. No physical resource-pressure or native GUI result inferred from fake boundaries. The final full XML is authoritative for final runtime code; targeted XML predates the last conservative invalidation-shape guard. No failure in accepted final full run.

006 initially reports the absence of the new rank helper, not an executed pre-change malicious scrape. Original title/docs-host sorting is source evidence of the design gap; the additional provenance-journey.json asserts the corrected production prepare/registry/Executor selection after a failed configured-doc read. Task UUID checks cover sampled boundaries; persistence/checkpoint attachment is not an atomic transaction with task replacement.
''')
    write('changes.md','''# Retained changes

knowledge_acquisition.py validates bounded Unicode goals/configuration; serializes task-owned prepare with cancellation-aware wait; refreshes the actual observed surface for each request; binds checkpoint/results to TaskState UUID; fails closed on malformed observations; suppresses research/control hints behind detected login; sanitizes public version to numeric components; ranks sources by configured exact origin, never self-declared title; annotates explicit URL major/minor version mismatch as stale.

app_knowledge.py excludes incompatible unknown/known versions, invalidates other-feature records after an observed surface change and clones only the selected top three rows. Historical proof remains stored as invalidated; no new graph database or executable abilities. Fresh observation adds read latency compared with unsafe context bypass; correctness takes priority. Cache optimization retained on equivalent bounded lookup assertions and measured speed/allocation improvement.

application_discovery.py detects visible password controls before sanitizing, omits controls and returns an authentication_required heuristic. Hidden authentication/SSO detection is not complete. Existing launcher/registry/task/recovery interfaces and manifest dependencies remain unchanged. Added isolated 32-case suite plus supplemental boundary tests, reusable A/B and actual browser journey scripts; catalog recognizes the reviewed test class and explicit blocker. Documentation and exact result accounting updated; no dependency install, service, migration or commit.

See files-changed.json, source.patch and source-hashes.json for exact paths/preimages and hashes. No user modifications discarded.
''')
    write('compatibility.md','''# Compatibility and limits — checked 2026-10-15 UTC / 16 IST

Python3.10.6, installed ddgs9.16.0, requests2.34.2, Playwright1.63.0, psutil7.2.2, pywin32312. Target Windows/Ryzen7/32GB/RTX3050Laptop4GB, same machine before/after. No model/GPU work allocated by this subsystem; VRAM/TTFT/first audio not measured.

Firecrawl plugin retrieved official [scrape contract](https://docs.firecrawl.dev/features/scrape), [Microsoft UIA properties](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-properties-overview), and [PyPI ddgs metadata](https://pypi.org/pypi/ddgs/json); status200 recorded in upstream-checks.json. PyPI latest9.16.0 uploaded2026-08-26T21:52:32Z, requiresPython>=3.10: installed version current; no dependency upgrade. Official [publisher workflow](https://github.com/deedy5/ddgs/actions/workflows/python-publish.yml) indexed release passage independently records v9.16.0 August26. Browser version/release decision remains [module14](../14-browser-playwright/compatibility.md), not a new installation. UIA runtime IDs are not persistent across runs; control hints are semantic references, never durable identity/authorization.

Jarvis uses its existing optional HTTP Firecrawl v2 adapter with separately configured key; Codex connector credentials were not exported. Firecrawl docs describe content retrieval, not trusted execution or correct app-version recipes. No paid API required.

BLOCKED JRV-15-010: no plugin-specific namespace/detector. Exact-origin preference is configuration provenance, not proof of publisher ownership/current instructions; without configured origin discovered sources stay unverified. Version hints only explicit numeric URL paths, not arbitrary document-content reconciliation; unknown stays unknown. Cache invalidation compares bounded surface signatures and cannot prove every app update or policy change. Arbitrary unknown/unconfigured apps and implicit website names remain outside deterministic detection. No universal prompt-injection/privacy guarantee; public/private host screening and UI label filtering remain heuristic. Password detection can conservatively suppress non-login password settings surfaces. Registry per-action approval/fresh observation remains essential; no executable action graph invented from prose. Known acquisition/UI/model historical live evidence is not fresh production acceptance. Native app GUI, real accounts, full SSO, physical GPU/RAM contention and long soak not performed; launcher result is separately reported.
''')
    write('rollback.md','''# Rollback and deterministic resume

No commit made. Existing branch audit/12-tool-registry and inherited dirty diffs preserved. Baseline HEAD/environment in environment.json. Scoped original files are in ignored .jarvis-runtime/jarvis-audit/module15-pre (relative app paths use __); do not use git reset/restore across unrelated changes. Review source.patch and compare current hashes to source-hashes.json before manually copying these originals over only this module's changes. Preserve subsequent user edits. New scripts/tests may be removed only as a reviewed scoped rollback; never remove personal files or the production app store. No data migration or dependency rollback needed. To disable acquisition use existing knowledge_acquisition.enabled=false configuration and normal Stop/Start only when explicitly requested; this audit did not change live settings.

From app/ using .venv/Scripts/python.exe:
1. -m pytest tests/test_app_research_audit.py tests/test_knowledge_acquisition.py tests/test_live_app_context.py tests/test_skill_memory.py tests/test_task_state.py tests/test_tools.py tests/test_toolkits.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/15-app-research/cases-and-contracts.xml
2. scripts/verification/verify_app_research_audit.py (requires preserved preimage; never recreate baseline from modified source).
3. -m scripts.verification.verify_app_research_journey (owned headless intercepted synthetic click only; authored planner).
4. -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/15-app-research/full-regression.xml
5. -m jarvis.launcher --check; preserve full private output locally and publish redacted readiness status.
6. scripts/verification/report_app_research_audit.py after validating unchanged source hashes and saved readiness JSON.

Exact outstanding catalog IDs: remaining-case-ids.txt. Next unrun module:16, JRV-16-001. Earliest older blocker remains JRV-04-001; this pass does not certify earlier acceptance gates. Resolve plugin namespace before claiming 15-010. Future live account writes/install/credential operations still require per-action approval.
''')
    headline=f'''**App/site knowledge audit — 2026-10-16 IST:** Fresh surface/version and task UUID checks prevent stale context reuse; login observations suppress research/control hints; bounded inputs and numeric public versions fail closed. Source preference uses configured origin, with explicit URL version hints marked stale. Cache lookup warm median {before['p50_ms']:.2f}→{after['p50_ms']:.2f} ms on synthetic records.
Verification: **{full['passed']:,} full regression PASS / {full['skipped']} skips**; **31 Prompt15 catalog PASS / 1 BLOCKED** (plugin identity namespace missing). Launcher **{readiness['status']}**. Owned headless browser fixture passed; live accounts/native GUI/model/production readiness remain unverified.'''
    for path,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/15-app-research/inventory.md'),(BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/15-app-research/inventory.md'),(BASE/'docs/autonomous-learning.md','../artifacts/jarvis-audit/modules/15-app-research/inventory.md'),(BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/15-app-research/inventory.md')]:
        s=path.read_text(encoding='utf-8'); s=re.sub(r'\n<!-- prompt15-audit -->[\s\S]*?<!-- /prompt15-audit -->\n','\n',s)
        first,rest=s.split('\n',1);path.write_text(first+'\n\n<!-- prompt15-audit -->\n'+headline+f'\n[Evidence, limits and rollback]({link}).\n<!-- /prompt15-audit -->\n'+rest,encoding='utf-8')
    modules='\n'.join(f"| {m['number']:02d} {m['module']} | "+' / '.join(f'{status}:{count}' for status,count in sorted(Counter(r['status'] for r in catalog if int(r['id'].split('-')[1])==m['number']).items()))+' |' for m in mapping)
    summary=json.loads((OUT/'summary.json').read_text())
    report=f'''# Jarvis audit — Prompt15 follow-up, 2026-10-16 IST

{headline}

{scope}

[Source-map/code/config/test inventory](modules/15-app-research/inventory.md), [full test XML](modules/15-app-research/full-regression.xml), [targeted XML](modules/15-app-research/cases-and-contracts.xml), [32 case assertions](modules/15-app-research/tests.jsonl), [readiness](modules/15-app-research/readiness.json), [actual synthetic browser journey](modules/15-app-research/browser-journey.json).

Repo/commit/environment: [exact baseline](modules/15-app-research/environment.json); branch retained audit/12-tool-registry, HEAD e1a33a0944b5cd725e1a76a72eda228513e45963, no audit commit, Windows/Python3.10.6, Ryzen7/32GB/RTX3050Laptop4GB target. Inherited module14/user diffs preserved, no new dependency/service/config setting or production cache changed. {len(freeze)} source/test hashes unchanged during accepted full run. [Exact changed files](modules/15-app-research/files-changed.json), [scoped diff](modules/15-app-research/source.patch), [source hashes](modules/15-app-research/source-hashes.json).

Nine failure families reproduced/fixed, with QA setup errors distinguished in [failure history](modules/15-app-research/failures.md). [Before/after changes and tradeoffs](modules/15-app-research/changes.md). Baseline29 PASS; targeted {targeted['passed']} PASS / {targeted['skipped']} blocked skip. Tests overlap and are not summed as unique catalog results. Full skip reasons remain explicit in XML. No failure hidden by catalog reconciliation.

Warm lookup p50/p95 {before['p50_ms']:.4f}/{before['p95_ms']:.4f}→{after['p50_ms']:.4f}/{after['p95_ms']:.4f} ms; peak traced Python allocations {before['python_peak_bytes']}→{after['python_peak_bytes']} bytes. Five fresh-store and20 warm lookups/version, identical24-record fixture; independent copied results asserted. [Raw samples](modules/15-app-research/benchmarks.csv), [cold/warm scope](modules/15-app-research/benchmark-summary.json). Cold is fresh in-memory object, excludes disk load; no full-task/VRAM/model/audio speed claim. Synthetic headless user journey {journey['seconds']:.3f}s, authored planner and independent DOM oracle. Earlier per-module measurements preserved in [report through14](final-report-before-module15.md).

Firecrawl official current-source and release checks: [evidence URLs/dates](modules/15-app-research/upstream-checks.json), [compatibility rationale](modules/15-app-research/compatibility.md). Installed ddgs9.16.0 matches PyPI latest release2026-08-26, Python>=3.10; retained with measured internal cache optimization. Connector key not exported. No installation or paid requirement.

## Open gates and risk

JRV-15-010 plugin-specific identity/version scoping missing. Exact-origin preference depends on configured documentation URL, not authenticated publisher discovery; explicit URL hints are not semantic document reconciliation. Unknown versions remain uncertain. Authentication, names, sensitive host screening and signature invalidation are bounded heuristics; hidden/SSO/custom plugin surfaces can require clarification. Native GUI/accounts/live model, physical resource contention and long soak not certified. Launcher status above is actual readiness, not a feature check. Existing earlier acoustic/native-model/GPU/PDF/download/tab and unfamiliar-program approval gates remain catalog blockers; no whole-system production/security certification. Recovery still only repeats observations; no uncertain external effect replay. [Rollback/resume](modules/15-app-research/rollback.md).

1184 catalog IDs: **{dict(counts)}**. [Exact ledger](test-results.jsonl), [totals by tier/category](summary.json), [all remaining IDs](remaining-case-ids.txt). Next NOT RUN: **JRV-16-001**. Earliest unresolved: **JRV-04-001**.

## Modules

| Module | Catalog status counts |
| --- | --- |
{modules}

## Tier/category statistics

```json
{json.dumps({k:summary[k] for k in ('by_tier','by_category')},indent=2)}
```
'''
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    files=['jarvis/knowledge_acquisition.py','jarvis/app_knowledge.py','jarvis/application_discovery.py','scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py','tests/test_app_research_audit.py','scripts/verification/verify_app_research_audit.py','scripts/verification/verify_app_research_journey.py','scripts/verification/report_app_research_audit.py','README.md','docs/system-map.md','docs/autonomous-learning.md']
    changed=[{'path':f,'sha256':hashlib.sha256((BASE/f).read_bytes()).hexdigest()} for f in files]
    changed.append({'path':'../README.md','sha256':hashlib.sha256((BASE.parent/'README.md').read_bytes()).hexdigest()})
    write('files-changed.json',json.dumps(changed,indent=2))
    pairs=[];patch=[]
    for f in files:
        old=PRE/f.replace('/','__')
        new=BASE/f
        if old.exists():
            pairs.append({'path':f,'before':hashlib.sha256(old.read_bytes()).hexdigest(),'after':hashlib.sha256(new.read_bytes()).hexdigest()})
            patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),new.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+f,tofile='after/'+f))
        else:
            patch.extend(difflib.unified_diff([],new.read_text(encoding='utf-8').splitlines(True),fromfile='/dev/null',tofile='after/'+f))
    old=PRE/'root-README.md';new=BASE.parent/'README.md'
    pairs.append({'path':'../README.md','before':hashlib.sha256(old.read_bytes()).hexdigest(),'after':hashlib.sha256(new.read_bytes()).hexdigest()})
    patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),new.read_text(encoding='utf-8').splitlines(True),fromfile='before/root-README.md',tofile='after/root-README.md'))
    write('source-hashes.json',json.dumps(pairs,indent=2));write('source.patch',''.join(patch))
    print(json.dumps({'module15':dict(Counter(r['status'] for r in cases)),'full':full,'catalog':dict(counts)},indent=2))


if __name__=='__main__':main()
