"""Publish Prompt22 executed evidence and incomplete contracts without readiness inflation."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/22-web-development';PRE=BASE/'.jarvis-runtime/jarvis-audit/module22-pre'
BLOCKED={f'JRV-22-{n:03}' for n in (2,4,8,10,11,18,19,21,23,25,26,27,30,32)}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(name,s):(MOD/name).write_text(s.strip()+'\n',encoding='utf-8')
def stats(name):
    t=ET.parse(MOD/name);ns=list(t.iter('testcase'))
    return {'PASS':sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in ns),
      'FAIL':sum(n.find('failure') is not None or n.find('error') is not None for n in ns),
      'SKIPPED':sum(n.find('skipped') is not None for n in ns),'seconds':sum(float(s.get('time','0')) for s in t.iter('testsuite'))}

def main():
    from scripts.verification import audit_catalog
    # Preserve original executed suite attributes; aggregate, never manufacture
    # assertion outcomes or turn partial passing variants into full-case passes.
    combined=ET.Element('testsuites',name='Prompt22 executed main and supplemental suites')
    for name in ('focused-main-final.xml','catalog-supplements.xml'):
        combined.extend(list(ET.parse(MOD/name).getroot()))
    ET.ElementTree(combined).write(MOD/'cases-and-contracts.xml',encoding='utf-8',xml_declaration=True)
    baseline=stats('baseline.xml');target=stats('cases-and-contracts.xml');full=stats('full-regression.xml')
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0 and target['PASS']==50 and full['PASS']>2827
    frozen=read(MOD/'full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    env=read(MOD/'environment.json');ready=read(MOD/'readiness.json');bench=read(MOD/'benchmark-summary.json')
    assert bench['equivalent'] and bench['external_effects']==0
    modules=read(OUT/'module-map.json')
    modules[21].update(sources=['jarvis/development.py','jarvis/development_api.py','jarvis/development_tools.py',
      'jarvis/development_browser.py','jarvis/development_projects.py','jarvis/development_learning.py',
      'jarvis/coder.py','jarvis/agent_tools.py','main.py','docs/web-app-development.md'],
      test_candidates=['tests/test_web_development_audit.py','tests/test_development.py','tests/test_development_tools.py',
        'tests/test_development_api.py','tests/test_development_projects.py','tests/test_development_learning.py'],
      status='PARTIAL',reason='18 catalog fixture PASS/14 incomplete contracts BLOCKED; partial smoke proofs retained separately, actual headless browser/build checks, no native app or autonomous model acceptance')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-22-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':18,'BLOCKED':14}
    assert {r['id'] for r in cases if r['status']=='BLOCKED'}==BLOCKED
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    summary=read(OUT/'summary.json');counts=summary['catalog_counts']
    nodes=list(ET.parse(MOD/'full-regression.xml').iter('testcase'))
    write('full-regression-skip-reasons.json',json.dumps([{'node':n.get('classname','')+'::'+n.get('name',''),
        'reason':n.find('skipped').get('message','')} for n in nodes if n.find('skipped') is not None],indent=2))
    gates='''- **JRV-22-002 BLOCKED:** Production preview uses Vite preview/Next start/exported static files, not a development HMR lifecycle.
- **JRV-22-004 BLOCKED:** Exit status and raw build diagnostics exist; no benign-versus-regression warning classifier.
- **JRV-22-008 BLOCKED:** Watchdog stops owned failed preview and requests explicit continuation; no safe automatic restart contract. Project/server code can have side effects, so it is not silently replayed.
- **JRV-22-010 BLOCKED:** Browser contexts isolate cookies/storage and permissions; project build/server code still runs as host user without filesystem confinement.
- **JRV-22-011 BLOCKED:** Reviewed install/lock guards exist; no reproducible dependency-upgrade API-break compatibility oracle.
- **JRV-22-019 BLOCKED:** Owned child jobs stop on exit; no durable preview crash-resume protocol.
- **JRV-22-032 BLOCKED:** Raw build/browser logs may contain credentials; complete credential-redacted trace contract missing.
- **JRV-22-018 BLOCKED:** Stop/timeout smoke checks do not prove consistent TaskState cancellation during planning and readback.
- **JRV-22-021 BLOCKED:** Token URL refusal does not prove the complete fake-cloud/private-context/log-redaction contract.
- **JRV-22-023 BLOCKED:** Explicit one-file scope does not prove positive-versus-negative development-intent execution semantics.
- **JRV-22-025 BLOCKED:** Injected MemoryError stops launch, but RAM/GPU admission and core-command responsiveness under pressure are unproved.
- **JRV-22-026 BLOCKED:** Repair avoids restart; durable identical-event and uncertain-write deduplication across the complete flow is unproved.
- **JRV-22-027 BLOCKED:** Health microbenchmark is measured; full development request cold-start/RSS/VRAM benchmark is absent.
- **JRV-22-030 BLOCKED:** Pre-launch faults/dead-process checks do not prove active-worker disconnect recovery with durable task provenance.'''
    scope='''Actual existing trusted authored dashboard TypeScript/Vite build, owned temporary static previews, installed headless Chrome desktop/mobile/reduced-motion checks with project-local axe, deliberate overflow/dead-button failures, isolated mock remote API, Unicode DOM readback, cancellation/timeout and owned process cleanup. Five independent status sessions ×20 rounds use no model/GPU. Network/RAM/process faults and planner responses are fakes; these do not prove native memory pressure handling or arbitrary generated applications. No dependency installs, private account/browser-profile reuse, external sends, personal deletes, OS settings, native packaging, model downloads or publication. Build writes only the pre-existing authored acceptance artifact output; generated test projects and snapshots are owned temporary fixtures.'''
    matrix='''| Claim | Real implementation / entry point | Evidence / boundary |
| --- | --- | --- |
| Development selection | Coder.run checks configured backend before legacy development.run; detect_stack/scaffold belong to staged workflow | Configured jarvis uses codex_workload/native and its own checks; these legacy staged browser checks are not automatically applied to every native task. Explicit development_* tools remain registered separately in agent_tools |
| Design/generation | design spec→bounded plan→≤3 files/batch; scoped paths and existing approvals | Baseline batch/cancellation/path assertions; no model-generated app acceptance in this audit |
| Tool registration | development_api.TOOLS→execute; task folder/TaskState and _approve | Status read-only; start/build/install require caller execution approval; forged planner feedback rejected |
| Dependency/build | DevelopmentTools.install/build | Existing npm ci versus reviewed install/hook/source guards; actual installed tsc/Vite ran; no dependency change/install |
| Port/lifecycle | start_preview selects OS port, loopback bind and strictPort; OwnedJob | Actual occupied-port/owned-stop fixture; no unrelated process kill; released-port bind race remains a fail/pause risk |
| Browser admission | tools.inspect exact project/url; development_browser.preview_url | Credential-free root http127.0.0.1:port only; query/fragment/path rejected before browser work without echoing fake secret |
| Auth/network | isolated one-shot Chrome context per view | permissions empty, downloads disabled, service workers blocked; external HTTP blocked and all WebSockets closed; no real account context |
| Browser proof | validate_tests→finite step actions→axe/layout/keyboard/console/scenarios | Strict bounded names/values/counts/JSON; actual dead button/overflow fail; ≥3 assertions and interaction required; screenshots alone not proof |
| Recovery | main watchdog development preview→healthy/repair; stop/close | Failed owned process stops and records status, requires continuation; no automatic build/install/server/click replay |
| Learning | development_learning.record/recall fingerprint | Incomplete or stale code cannot become verified success; versions/framework scope retained |
| Health performance | DevelopmentTools._opener under existing RLock | Reuses proxy-free opener; no per-call construction; network still serialized under lock, not an event-loop latency guarantee |'''
    b=bench['before']['warm'];a=bench['after']['warm']
    measured=f"Health-check overhead warm p50/p95 **{b['p50_ms']:.5f}/{b['p95_ms']:.5f} → {a['p50_ms']:.5f}/{a['p95_ms']:.5f} ms**; peak traced allocation **{b['python_peak_bytes']} → {a['python_peak_bytes']} bytes**. Same fake HTTP200 response and active/dead/closed assertions;25 calls/version in one process. Five initial calls are not fresh-process cold starts. Imports/construction/network/browser/build/GPU excluded. Cached opener retains per-instance memory and moves construction to instance startup; no end-to-end speed or VRAM claim."
    write('inventory.md',f'''# Prompt22 web/app audit — 2026-10-16 IST

**18 catalog PASS /14 BLOCKED /0 FAIL /0 SKIPPED /0 NOT RUN.** [32 exact IDs](tests.jsonl). Baseline {baseline}; combined focused {target}; full tests-directory run {full}. Focused evidence combines the final47 PASS/7 skips and separately executed3 PASS/7 skips; full tests-directory run excludes the additional scripts/verification supplement. All executable assertions passed, while incomplete full-case contracts remain BLOCKED. [Commands](commands.txt), [full XML](full-regression.xml), [exact skips](full-regression-skip-reasons.json).

{scope}

Supplemental executed readback: [actual Vite build served unchanged](built-preview-proof.json), [exact port3000 collision](port3000-proof.json). The first port supplement encountered a Windows temporary-file cleanup lock after process assertions; fresh owned retained fixture rerun passed. File cleanup was not retried and no unrelated state was removed.

{matrix}

{gates}

Read system-map, web-app-development, relevant native guide, linked tooling/build/preview runners and real registration/callers; historic2026-10-02 model/fixture claims remain dated. Branch **{env['branch']}**, HEAD **{env['commit']}**, inherited Prompt21/user diffs preserved. No audit commit or checkout reset; before-image snapshots isolate this module. Order: source/contract trace→baseline→reproduction→small fixes→upstream→A/B→owned build/browser/fault assertions→frozen full/readiness→catalog/docs. [Environment](environment.json), [changes](changes.md), [compatibility](compatibility.md), [rollback](rollback.md).

{measured} [Raw samples](benchmarks.csv), [scope](benchmark-summary.json).

![Actual headless Chrome capture of hand-written owned test page](fixture-desktop.png)

Actual1440×1000 headless Chrome fixture screenshot, not Jarvis UI or a model-generated website. Hand-written local markup, no third-party artwork. [Mobile](fixture-mobile.png), [reduced motion](fixture-reduced-motion.png). Screenshots accompany executable DOM/axe assertions; they are not independent functional proof.
''')
    write('failures.md',f'''# Reproductions and known flaws

Baseline25 PASS in6.74s. Initial new reproduction8 FAIL in2.54s:3 token URL boundary assertions,4 malformed/oversized plan assertions, plus1 fixture failure (worker launched from temporary base without Jarvis module). Corrected fixture uses actual app worker path. Separate actual Chrome reproduction1 FAIL in10.54s: context lacked service_workers/permissions settings. These are assertion counts, not eight product defects.

First expanded49 PASS/2 FAIL/7 skips in75.91s: both remaining failures were test fixture PAGE.write_text using Windows cp1252 for Hindi. Corrected fixture writes UTF-8. First focused46 PASS/7 skips in66.42s. A later read-only malformed-action probe observed TypeError for an action list. After the first full run completed (2854 PASS/48 skips/0 failures in534.14s), added an explicit string-type guard and fifth malformed-input variant. Final focused {target}. Final full {full}; {len(frozen)} runtime/test hashes frozen and unchanged during accepted run. Final full also records build output and screenshots; these evidence-only additions do not weaken assertions. The earlier full run and its hashes are preserved separately as full-before-final.xml/full-before-final-source-hashes.json.

{gates}

Other boundaries: route/service-worker/WebSocket policy is a browser-context guard, not host network or filesystem sandbox. Project code/configuration executes as local user; npm hooks disabled does not make arbitrary packages safe. Explicitly blocked WebSockets are suitable for production inspection and intentionally do not support HMR tests. Unknown warnings are retained, not automatically labelled benign. axe covers a subset of accessibility; no full WCAG certification, real user testing or visual pixel-diff oracle. Deliberate overflow is detected by DOM width and dead controls by independent outcome assertions. Browser test plans generated by models can be wrong; authored fixtures are not autonomous app proof. Context storage is fresh but no hostile-browser exploit testing. URL refusal protects preview URL fields, not arbitrary source/log secrets. No raw live logs published.

Port reservation is released before child bind; another process may win the race. strictPort avoids silent alternate-port drift but no general port transaction/preflight cache was added. Cleanup and concurrent lifecycle races beyond covered cases are not proven. Healthy still holds its existing RLock during≤0.5s network wait. No auto-restart was added because project code can have external effects. No supported Python migration or dependency upgrade performed. Launcher **{ready['status']}**: {ready['missing']}; dependency readiness is not production acceptance.
''')
    write('changes.md',f'''# Changes and keep decision

- development_browser.py rejects non-root/query/fragment/credential-bearing URLs with a categorical error; validates bounded scenario names, JSON size, fields, text/count/key/attribute types before browser execution. Defaults for existing named-role scenarios retained.
- Chrome contexts now explicitly block service workers, grant no permissions and close WebSockets in addition to existing HTTP routing, fresh storage and download policy.
- development_tools.py constructs one proxy-free opener per instance; existing lock serializes use. Command/build/start/stop/tool names and approval behavior retained.
- New owned browser/build/security/fault tests, reviewed catalog accounting, benchmark/report/hash scripts, README/system-map/guide updates. No dependency/configuration/product UI change; historical artwork and acceptance screenshots preserved. New screenshots are actual authored test-page captures only.

{measured}

Keep: removes repeated allocation and closes observed input/network boundaries. Baseline {baseline}; final focused {target}; full {full}. [Exact files](files-changed.json), [before/after hashes](source-hashes.json), [diff](source.patch). No incremental build/cache/HMR optimization claimed without a baseline.
''')
    write('compatibility.md',f'''# Upstream and compatibility — checked2026-10-16 IST

Firecrawl primary-source review: [exact URLs/dates](upstream-checks.json). [Playwright network documentation](https://playwright.dev/python/docs/network) recommends blocking service workers for reliable request interception. [BrowserContext WebSocket route API](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route-web-socket) is available in installed1.63.0. Real Chrome execution verified these APIs. Fresh contexts do not borrow user authentication/storage.

[PyPI Playwright](https://pypi.org/project/playwright/) reports1.64.0, released2026-10-13; installed1.63.0 retained. [Python release notes](https://playwright.dev/python/docs/release-notes) currently lead with1.63; registry release and documentation coverage are recorded separately. No new browser/package downloaded or1.64 acceptance claimed.

[Vite preview options](https://vite.dev/config/preview-options) documents strictPort failure instead of port hopping. [Vite8.3.4 release notes](https://github.com/vitejs/vite/releases/tag/v8.3.4), displayed2026-10-08, describe HMR-default, preload and style fixes; installed fixture8.3.2 was actually built. No new dependency installation or measured version-comparison claim. Production previews remain distinct from HMR.

Node24.14.0/npm11.11.1, TypeScript7.0.2, axe-core4.13.0, Python3.10.6, Playwright1.63.0. Package pins retained; this is not a full npm/transitive advisory census. Prior [module21 compatibility](../21-native-coding/compatibility.md) records older Git/Python lifecycle risks. Chrome channel is the installed browser, not a reproducible bundled revision. GPU inference not used. {ready['status']} launcher snapshot; no native Electron/Expo device or autonomous model-generated website acceptance.
''')
    write('rollback.md','''# Scoped rollback and deterministic resume

No commit/reset, personal deployment or install. Preserve inherited Prompt21/user edits. Compare current hashes and source.patch before restoring only this module from ignored .jarvis-runtime/jarvis-audit/module22-pre. Preimages use /→__ and root-README.md for the parent. Do not erase the checkout or overwrite later edits. Restoring old browser code reopens token URL/malformed plan/service-worker/WebSocket gaps; keep untrusted previews stopped pending review. No live server was left running by these tests.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_web_development_audit.py (immutable original preimage benchmark; never regenerate it from changed code).
2. -m pytest tests/test_web_development_audit.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/22-web-development/cases-and-contracts.xml
3. Neighbor tests: -m pytest tests/test_development.py tests/test_development_tools.py tests/test_development_api.py tests/test_development_projects.py tests/test_development_learning.py tests/test_development_design.py tests/test_development_knowledge.py -q (distinct output).
4. Freeze jarvis/*.py and tests/test_*.py SHA256, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/22-web-development/full-regression.xml. Do not edit runtime/tests during accepted run.
5. -m jarvis.launcher --check read-only; raw local output remains ignored, publish redacted summary. Run report_web_development_audit.py and verify_web_development_artifacts.py; git diff --check.

Fixture prerequisites: installed Chrome/Playwright, existing trusted artifacts/projects/development-dashboard with its pinned tsc/Vite/axe tree. Do not install automatically if absent; record concrete blockers instead. Full test builds only that authored fixture output and starts/stops owned temporary loopback servers. The mocked remote API makes no external request. Do not replay failed project/server/build code automatically; inspect state and request explicit continuation.

Missing current IDs JRV-22-002/004/008/010/011/018/019/021/023/025/026/027/030/032. Next NOT RUN JRV-23-001; earliest older unresolved JRV-04-001. All exact pending IDs remain in artifacts/jarvis-audit/remaining-case-ids.txt. HMR, host confinement, upgrades, crash continuation and diagnostic redaction need separate scoped contracts, not a production certificate from fixture success.
''')
    headline=f"**Web/app audit — 2026-10-16 IST:** Strict preview URL/test-plan validation, service-worker/WebSocket isolation and reused health opener added. **18 Prompt22 fixture PASS /14 BLOCKED**. Full regression **{full['PASS']:,} PASS /{full['SKIPPED']} skips /0 failures**; launcher **{ready['status']}**. Real authored build and isolated headless browser checks passed; HMR, warning classification, safe restart, host confinement, dependency compatibility, crash continuation and complete redaction remain incomplete."
    for doc,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/22-web-development/inventory.md'),
      (BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/22-web-development/inventory.md'),
      (BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/22-web-development/inventory.md'),
      (BASE/'docs/web-app-development.md','../artifacts/jarvis-audit/modules/22-web-development/inventory.md')]:
        text=doc.read_text(encoding='utf-8');first,rest=text.split('\n',1)
        rest=re.sub(r'<!-- prompt22-audit -->.*?<!-- /prompt22-audit -->\s*','',rest,flags=re.S)
        extra='\n\nConfigured `brain.coding_backend=jarvis` routes ordinary coding through native workload validation before the legacy staged workflow described below. Explicit `development_*` tools remain available through the agent registry; do not assume every native coding task receives these legacy framework/axe checks automatically. Current audit screenshots are of a hand-written minimal test page; existing dashboard images below remain historical authored acceptance captures.\n' if doc.name=='web-app-development.md' else ''
        doc.write_text(first+'\n\n<!-- prompt22-audit -->\n'+headline+'\n[Evidence and rollback]('+link+').'+extra+'\n<!-- /prompt22-audit -->\n\n'+rest.lstrip('\n'),encoding='utf-8')
    table='\n'.join('| '+str(m['number']).zfill(2)+' '+m['module']+' | '+', '.join(f'{k}: {v}' for k,v in Counter(r['status'] for r in catalog if r['id'].startswith(f"JRV-{m['number']:02}-")).items())+' |' for m in modules)
    (OUT/'final-report.md').write_text(f'''# Jarvis audit — Prompt22 — 2026-10-16 IST

{headline}

HEAD **{env['commit']}**, branch **{env['branch']}**, inherited changes preserved; no audit commit. [Environment](modules/22-web-development/environment.json). Baseline {baseline}; focused {target}; full {full}. All **{len(frozen)} frozen source/test hashes unchanged**. [Full output](modules/22-web-development/full-regression.xml), [skips](modules/22-web-development/full-regression-skip-reasons.json), [readiness](modules/22-web-development/readiness.json).

{scope}

{measured}

[Source-map evidence matrix and actual fixture captures](modules/22-web-development/inventory.md), [changes/metrics](modules/22-web-development/changes.md), [exact files](modules/22-web-development/files-changed.json), [diff](modules/22-web-development/source.patch), [upstream URLs/dates](modules/22-web-development/compatibility.md), [risk/flaws](modules/22-web-development/failures.md), [rollback/resume](modules/22-web-development/rollback.md), [commands/results](modules/22-web-development/commands.txt).

{gates}

All1,184 catalog IDs: **{counts}**. [Exact ledger](test-results.jsonl), [category/tier totals](summary.json), [remaining IDs](remaining-case-ids.txt). Next NOT RUN **JRV-23-001**; earliest older unresolved **JRV-04-001**. [Previous Prompt21 report](final-report-before-module22.md). Overall37-module audit remains incomplete; no production-ready certificate.

## Enumerated modules

| Module | Catalog status |
| --- | --- |
{table}

## Category and tier statistics

```json
{json.dumps({k:summary[k] for k in ('by_category','by_tier')},indent=2)}
```
''',encoding='utf-8')
    files=['jarvis/development_tools.py','jarvis/development_browser.py','tests/test_web_development_audit.py',
      'scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py','scripts/verification/verify_web_development_audit.py',
      'scripts/verification/report_web_development_audit.py','scripts/verification/verify_web_development_artifacts.py','scripts/verification/verify_web_preview_port.py','scripts/verification/verify_web_built_preview.py','scripts/verification/test_web_development_audit.py',
      'README.md','docs/web-app-development.md','docs/system-map.md','../README.md']
    changed=[];pairs=[];patch=[]
    for name in files:
        p=BASE/name;old=PRE/('root-README.md' if name=='../README.md' else name.replace('/','__'))
        changed.append({'path':name,'sha256':sha(p)})
        if old.exists():pairs.append({'path':name,'before':sha(old),'after':sha(p)})
        patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],p.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name if old.exists() else '/dev/null',tofile='after/'+name))
    write('files-changed.json',json.dumps(changed,indent=2));write('source-hashes.json',json.dumps(pairs,indent=2));write('source.patch',''.join(patch))
    generated=['artifacts/jarvis-audit/'+s for s in ('final-report.md','final-report-before-module22.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt')]
    generated.extend(p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file())
    generated.extend('artifacts/jarvis-audit/modules/22-web-development/'+s for s in ('generated-files.json','artifact-verification.json'))
    write('generated-files.json',json.dumps(sorted(set(generated)),indent=2))
    print(json.dumps({'module22':dict(Counter(r['status'] for r in cases)),'full':full,'catalog':counts},indent=2))

if __name__=='__main__':main()
