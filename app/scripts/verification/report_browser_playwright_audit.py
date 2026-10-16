"""Publish Prompt14 from executed XML, matched measurements and saved preimages."""
from collections import Counter
import contextlib
import difflib
import hashlib
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
ROOT=BASE/'artifacts/jarvis-audit';OUT=ROOT/'modules/14-browser-playwright';PRE=BASE/'.jarvis-runtime/jarvis-audit/module14-pre'
RUNTIME=('jarvis/browser_worker.py','jarvis/browser_automation.py','jarvis/browser_cursor.py')
DOCS=('docs/automation-upgrade.md','docs/system-map.md')
FILES=(*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py','tests/test_browser_playwright_audit.py','tests/test_questions_context_audit.py',
       'scripts/verification/verify_browser_playwright_audit.py','scripts/verification/verify_browser_dialog_audit.py','scripts/verification/report_browser_playwright_audit.py','README.md',*DOCS)


def write(path,text):path.write_text(text,encoding='utf-8')


def result(name):
    tree=ET.parse(OUT/name);nodes=list(tree.iter('testcase'));assert nodes
    assert not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    skips=[n for n in nodes if n.find('skipped') is not None]
    if name=='cases-and-contracts.xml':assert all('BLOCKED:' in n.find('skipped').get('message','') for n in skips)
    if skips:write(OUT/(name.removesuffix('.xml')+'-skip-reasons.json'),json.dumps([dict(node=n.get('classname')+'::'+n.get('name'),reason=n.find('skipped').get('message','')) for n in skips],indent=2)+'\n')
    return dict(passed=len(nodes)-len(skips),skipped=len(skips),seconds=float(next(tree.iter('testsuite')).get('time',0)))


def prepend(path,text):
    old=path.read_text(encoding='utf-8');start='<!-- prompt14-audit -->';end='<!-- /prompt14-audit -->'
    if start in old:
        a=old.index(start);b=old.index(end,a)+len(end);old=old[:a]+old[b:].lstrip('\n')
    head,body=old.split('\n',1);write(path,head+'\n\n'+start+'\n'+text+'\n'+end+'\n\n'+body.lstrip('\n'))


def main():
    baseline=result('existing-baseline.xml');targeted=result('cases-and-contracts.xml');full=result('full-regression.xml')
    assert all((OUT/'full-regression.xml').stat().st_mtime>=(BASE/n).stat().st_mtime for n in (*RUNTIME,'tests/test_browser_playwright_audit.py','scripts/verification/audit_catalog.py'))
    for name,count in [('reproduced-failures.xml',7),('semantic-target-reproduced.xml',1),('wait-url-reproduced.xml',1)]:
        assert sum(n.find('failure') is not None for n in ET.parse(OUT/name).iter('testcase'))==count
    ready=json.loads((PRE/'readiness-private.json').read_text(encoding='utf-8-sig'));assert ready['status'] in {'ready','repair_required','check_incomplete'}
    readiness=dict(date='2026-10-15 IST',status=ready['status'],exit_code=0 if ready['status']=='ready' else 1,command='.venv/Scripts/python.exe -m jarvis.launcher --check',scope=ready.get('scope'),
        missing=ready.get('missing',[]),incomplete=[{'component':r.get('component'),'error_type':r.get('error_type')} for r in ready.get('incomplete',[]) if isinstance(r,dict)],services={k:v['status'] for k,v in ready.get('services',{}).items()})
    write(OUT/'readiness.json',json.dumps(readiness,indent=2)+'\n')
    frozen=json.loads((OUT/'full-start-source-hashes.json').read_text())
    changed=[name for name,digest in frozen['files'].items() if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=digest]
    assert not changed,changed
    modules=json.loads((ROOT/'module-map.json').read_text())
    modules[13].update(status='30 FIXTURE PASS / 2 BLOCKED; LIVE SITE ACCEPTANCE UNVERIFIED',reason='Actual isolated headless Chrome DOM/forms/SPA/delayed controls/redirect/download readback plus fake transport/policy faults. Production verified-download and explicit tab selection adapters absent; no new capability installed.',
        sources=[*RUNTIME,'jarvis/ui_transport.py','jarvis/windows_command_browser.py','jarvis/tools.py','jarvis/app_knowledge.py',*DOCS],test_candidates=['tests/test_browser_playwright_audit.py','tests/test_automation_upgrade.py','tests/test_independent_cursor.py','tests/test_windows_commands.py'])
    modules[5].update(status='30 CURRENT FIXTURE PASS / 2 NATIVE ACCEPTANCE BLOCKED',reason='Existing native qwen9b proof source hash became stale after external phase1 knowledge_worker change. Ollama unavailable on read-only probe; historical proof preserved, fresh synthetic inference required. Current module06 fixtures re-executed with Prompt14.')
    write(ROOT/'module-map.json',json.dumps(modules,indent=2)+'\n')
    from scripts.verification.audit_catalog import reconcile
    with contextlib.redirect_stdout(io.StringIO()):reconcile()
    rows=[json.loads(s) for s in (ROOT/'test-results.jsonl').read_text().splitlines()]
    assert len(rows)==len({r['id'] for r in rows})==1184
    cases=[r for r in rows if r['id'].startswith('JRV-14-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':30,'BLOCKED':2}
    for row in cases:row['scope']='Installed headless Chrome/Playwright isolated nonpersistent contexts; synthetic pages/intercepted traffic and one owned loopback redirect server. Native controller/worker/cursor/registry/transport paths with fakes at fault boundaries. No user profile/live account/public-site send, headed GUI/handoff or arbitrary transactional safety certification. Download bytes verified only in harness; multi-tab production mutation fails closed.'
    write(OUT/'tests.jsonl',''.join(json.dumps(r)+'\n' for r in cases));write(OUT/'remaining-case-ids.txt','\n'.join(r['id'] for r in cases if r['status']!='PASS')+'\n')
    summary=json.loads((ROOT/'summary.json').read_text());next_id=next(r['id'] for r in rows if r['status']=='NOT RUN')
    bench=json.loads((OUT/'benchmark-summary.json').read_text())['results']
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip();branch=subprocess.check_output(['git','branch','--show-current'],cwd=BASE,text=True).strip()
    metrics='\n'.join(f'| {k} | {v["samples"]} | {v["p50_ms"]:.3f} | {v["p95_ms"]:.3f} | {v["peak_python_bytes"]} |' for k,v in bench.items())
    matrix='''| Claim / entry | Actual implementation and boundary | Executed proof / limitation |
| --- | --- | --- |
| Owned browser/controller | BrowserAutomation.request → UITransport(module=browser_worker) → Session.perform/open | Fixed controller executable settings override caller settings; validate before open; existing separate persistent production profile retained. Tests use fresh nonpersistent contexts, not that profile |
| Semantic actions | Session.perform click/fill → get_by_role(exact) → visible wait → uniqueness → browser_cursor.click | CSS classes irrelevant; delayed element uses built-in wait; exact observed URL rechecked after wait/before fill/readback; pinned node compared to current semantic locator after cue |
| DOM discovery | Session.inspect → one SUMMARY evaluate → validate_summary | HTML/ARIA labels, bound5000 visited nodes/120 controls, no field values/cookies, hidden/inert disabled filtering; metadata marked untrusted. This is an approximate accessible-name summary, not a complete accessibility tree |
| Authentication/redirect | bounded DOM summary flag → navigate message | Owned loopback302→signin plus visible password detection; no credential entry. Heuristic not general OAuth/SSO/session validity proof |
| Forms/dialogs | exact fill/input_value, generic sensitive-target refusal, existing registry scope/approvals | Exact Unicode value and0 fixture submits; no Enter from generic fill. Site input/autosave handlers can still issue requests; generic click labels are not a complete transaction policy |
| Tabs/downloads | bound Session.page/open_tabs; generic click/fill refuses >1 owned tab | Original page not silently retargeted. No production explicit tab-selection or verified-download/save adapter. Harness alone verifies suggested filename and exact synthetic PDF-marker bytes |
| Fault/recovery/handoff | UITransport lock/serial/deadline/owned process/backoff; BrowserAutomation.owns_handle |100 fake IPC requests over5 threads×20 rounds, timeout/cancel/malformed response no replay, intentional Stop. Existing owned-browser versus desktop routing preserved; no new live Windows handoff trial |
| Authority/privacy | untrusted summary contract, ToolRegistry allowlist, metadata-only agent events | Injection labels do not override known tools/scope/approvals; fake private field values absent from summary; UUID events omit payload. Not a general personal-text scrubber or prompt-injection proof |
| Existing neighboring paths | windows_command_browser.perform, media workflows, app_knowledge profiles | Existing scoped recipes/media/AppKnowledge remain; their historical live results are not rerun as general site/account acceptance |
'''
    commands='''.venv/Scripts/python.exe -m pytest tests/test_automation_upgrade.py tests/test_independent_cursor.py tests/test_windows_commands.py tests/test_hermes_skills.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/14-browser-playwright/existing-baseline.xml
.venv/Scripts/python.exe scripts/verification/verify_browser_playwright_audit.py
.venv/Scripts/python.exe scripts/verification/verify_browser_dialog_audit.py
.venv/Scripts/python.exe -m pytest tests/test_browser_playwright_audit.py tests/test_automation_upgrade.py tests/test_independent_cursor.py tests/test_windows_commands.py tests/test_hermes_skills.py tests/test_audit_result_accounting.py tests/test_questions_context_audit.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/14-browser-playwright/cases-and-contracts.xml
.venv/Scripts/python.exe -m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/14-browser-playwright/full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe scripts/verification/report_browser_playwright_audit.py'''
    write(OUT/'commands.txt',commands+'\n')
    write(OUT/'inventory.md',f'''# Prompt14 — browser/Playwright audit, 2026-10-15 IST

**30 catalog fixture PASS / 2 BLOCKED / 0 FAIL / 0 SKIPPED / 0 NOT RUN.** JRV-14-007 lacks a production verified-download/save adapter; JRV-14-009 lacks explicit tab selection. Their negative boundaries and a harness download readback are tested, not promoted into new abilities. No account/send/personal file deletion/OS setting/credential setup/package or browser install/deployment occurred. No real user tabs/profile used.

Current repo `{commit}`; baseline `bdcb15a52bbf23101950cd1625f249a564e647ee`, existing branch `{branch}` retained; Windows/Python{platform.python_version()}, installed Playwright1.63.0/Chrome, Ryzen7/32GB/RTX3050 Laptop4GB target. Headless browser fixture scope is module; it closes before unrelated tests. [Exact read-only environment and concurrent HEAD note](environment.json). No heavyweight model/GPU inference tests added, no new dependencies/services. app/ canonical; existing dirty work and InsTAREELS alias preserved.

## Source map, dependency and safe run order

{matrix}

Read system-map, automation-upgrade, existing execution/Windows command/browser cursor contracts, source registrations/config/tests and AppKnowledge metadata boundaries. Run order: ownership/permission/no-replay inspection → existing baseline → isolated failure assertions → bounded fixes → actual controlled headless journeys and32 catalog IDs → matched metadata benchmark → full regression/readiness → accounting/docs. Existing tools and UI preserved. No generic remote browser or autonomous new adapter installed. Screenshots/full Playwright traces not enabled automatically because they can retain private DOM/field data; metadata-only lifecycle traces stay in existing logs. A concurrent phase1 commit changed knowledge_worker source. Initial full run2 FAIL/2536 PASS/29 skips were stale native-proof hash assertions, retained in full-regression-stale-native.xml. Current cached proof remains untouched; two live native cases explicitly BLOCKED because Ollama is unavailable. [Read-only prerequisite probe](native-refresh-status.json),[stale/FAIL classification assertions](stale-native-proof-gate.json). Fresh native validation, not a rehash, is required. The QA freshness classification was updated separately from product code, then all fixtures/full suite rerun. Full-start source/test hashes are checked for concurrent mutations. No new UI screenshot; historical artwork/live evidence retains labels/dates/attribution.

## Executed results and scoped journeys

Baseline **{baseline['passed']} PASS**, {baseline['seconds']:.2f}s,[XML](existing-baseline.xml). Nine reproduced browser failures: [initial7](reproduced-failures.xml),[renamed button during cue](semantic-target-reproduced.xml),[URL changes during wait](wait-url-reproduced.xml). First fixes69 PASS before catalog expansion. Final targeted **{targeted['passed']} PASS / {targeted['skipped']} explicit BLOCKED skips**, {targeted['seconds']:.2f}s,[XML](cases-and-contracts.xml). Full **{full['passed']} PASS / {full['skipped']} skips**, {full['seconds']:.2f}s,[XML](full-regression.xml),[completion](full-run-completion.txt). Counts overlap. Launcher **{ready['status']}**,[current redacted result](readiness.json); this is separate from headless fixture success. [All32 IDs/assertions](tests.jsonl),[commands](commands.txt),[skip reasons](full-regression-skip-reasons.json). Existing COM warning, if emitted, retained in completion.

Actual headless journeys fill labelled forms with Unicode and assert exact DOM value/0 submits, change CSS/SPA routes, wait for delayed controls without arbitrary target sleeps, reject duplicate labels/sensitive controls/stale URL, detect owned loopback302 sign-in, refuse changed semantic target during cursor cue, report extra tabs without retargeting, and verify harness suggested filename/exact temporary synthetic PDF-marker payload. The payload tests bytes/headers, not PDF rendering. [Additional actual confirm-dialog fixture](dialog-fixture.json) observed default dismissal and0 synthetic submits; [reproducer](../../../../scripts/verification/verify_browser_dialog_audit.py). General dialog/authentication or arbitrary account behavior is not certified. Generic cursor's intentional240ms cue delay remains; no universal sleep-free claim. Fault tests use fake pipes/registry/policy and injected outages; concurrency covers serialized IPC, not concurrent use of Playwright's thread-affine sync API. No user recording, cookie or real desktop screenshot in artifacts.

## Matched before/after component measurement

| Version/context | Samples | p50 ms | p95 ms | Peak traced Python bytes |
| --- | --- | --- | --- | --- |
{metrics}

[Raw50 trials](benchmarks.csv),[scope](benchmark-summary.json). Saved pre-change inspect versus current inspect, same80 explicit-ARIA buttons/video, installed Chrome and machine. Five first-summary measurements in fresh isolated contexts and20 warm summaries/version; page load/browser launch excluded. Browser round trips4→1. Common name/role/href projection is identical (absent href normalized to None), new metadata/labels measured separately by assertions. Python allocation only, not Chrome/whole-host RAM; TTFT/audio/VRAM not applicable. Warm p50 **{bench['before_warm']['p50_ms']:.3f}→{bench['after_warm']['p50_ms']:.3f}ms**, p95 **{bench['before_warm']['p95_ms']:.3f}→{bench['after_warm']['p95_ms']:.3f}ms**. Keep fewer IPC round trips and bounded useful metadata. This small synthetic fixture does not establish every page's speed/precision, overall answer/voice latency or a2-second guarantee. No real external mutation in benchmark.

## Risks, blockers and next work

Production verified download/save and explicit tab-selection contracts remain missing; adding them requires scoped review/authorization. Multiple tabs are intentionally refused for generic click/fill. Authentication flag is a heuristic, not a credential/SSO detector. A fill can run site oninput/autosave code; label keyword screening is not universal write protection. Dedicated account adapters/current approvals remain required. The DOM may change between final guard and actual input; checks are not atomic. Summary naming/visibility approximates native accessibility and can omit controls beyond limits, shadow DOM or iframes; generic role locators remain separate. Page content/URLs remain private local task context; new untrusted labels do not replace core cloud policy. Error messages in other established paths retain existing redaction behavior. No live public-site account, real login, headed desktop handoff, GPU contention or long soak validation. Whole-system production acceptance remains open.

[Changes](changes.md),[failure history](failures.md),[official compatibility](compatibility.md),[rollback/resume](rollback.md),[files/hashes](files-changed.json),[scoped diff](source.patch). Earliest unresolved **{summary['next_case']}**, next NOT RUN **{next_id}**.
''')
    write(OUT/'failures.md','''# Reproductions and corrections — 2026-10-15 IST

Seven initial failures: immediate count rejected a late target before waiting; malformed request could reach browser lifecycle operations; caller settings replaced controller executable settings; non-object controller reply raised AttributeError; HTML label names absent from summaries; no sign-in flag; malformed summary accepted. Initial fixes passed69 tests. Review then reproduced renamed Continue→Submit during240ms cue being clicked; pinned node must now match current exact role/name locator before dispatch. A ninth reproduction showed URL change during target wait could fill another page; URL is rechecked after wait/before fill/with readback.9 product defects covered by executed assertions.

First catalog run had two audit fixture errors: benchmark compared absent href to None as different schemas, and intercepted302 handling let the synthetic .example redirect attempt DNS and fail. Corrected benchmark compares common name/role/href semantics; redirect now uses an owned loopback-only server and blocks other destinations. No user data/account sent. Missing benchmark output consequently failed its dependent catalog assertion; corrected after generation. These are fixture errors, not extra product defects.

Initial full run2 FAIL/2536 PASS/29 skips is retained as full-regression-stale-native.xml: phase1 changed knowledge_worker while cached native9b proof retained old SHA. After read-only Ollama probe failed, the audit now marks that stale native proof BLOCKED, never PASS or a fabricated new hash. Historical proof unchanged, fresh inference required. Final accepted assertions have0 FAIL. Cases007/009 explicitly BLOCKED, not skipped silently. Fixture download is exact bytes/filename only, not a production adapter or PDF rendering claim. Same-window/page races, arbitrary site autosave and general transaction classification remain limits.
''')
    write(OUT/'changes.md','''# Retained scoped changes

- browser_worker.py: request validation before browser open/reset; strict boolean new-task/headless and bounded literal Unicode/URL; one evaluated bounded summary with HTML/ARIA labels, private field-value exclusion, hidden/inert filtering, sign-in heuristic and untrusted contract; typed summary errors. Visible wait before strict uniqueness, URL rechecks around waiting/fill/readback; pinned semantic node guard after cue. Extra owned tabs reported and generic mutation refused.
- browser_automation.py: trusted controller settings win over caller settings; validation before transport; malformed replies rejected before touched/last_url updates. Intentional close/recovery ownership preserved.
- browser_cursor.py: optional read-only final admission callback before one pinned-element click; existing visual cue, URL check, disposal and no-replay preserved.
-32 catalog scenarios +11 supplemental regressions; real isolated headless contexts, loopback302 and synthetic temporary download; fake fault/transport/policy tests. Reviewed accounting class handles explicit blockers. Runtime manifest, READMEs and dated linked docs updated; rollback/source evidence preserved.
- tests/test_questions_context_audit.py: stale native proof now explicitly BLOCKED with required fresh inference, rather than claiming a current native pass after source changes. Historical native-default.json is preserved; no app inference code modified by this browser audit.
+- Existing Playwright1.63.0 retained despite upstream1.64.0 availability; no package/browser/model download, service, new public tool/ability, credential setup, account operation or UI artwork change.
''')
    write(OUT/'compatibility.md','''# Official current checks and compatibility — 2026-10-15 IST

Firecrawl retrieved [Playwright actionability](https://playwright.dev/python/docs/actionability), [locator guide](https://playwright.dev/python/docs/locators), [downloads](https://playwright.dev/python/docs/downloads), and [official PyPI metadata](https://pypi.org/pypi/playwright/json). [Actual returned answers/status/URLs](upstream-checks.json). The locator page extraction returned no useful details; no unsupported quote is attributed to it. Actionability documents uniqueness/visibility/stability/event-receiving/enabled checks for clicks, and visibility/enabled/editable for fill; auto-wait is bounded by timeout. This does not prove a whole business outcome or prevent site event-handler writes. Downloads are temporary and context-close cleanup applies; save_as is separate explicit persistence. No full trace or screenshot upload enabled.

PyPI reports1.64.0 uploaded2026-10-13T23:35:20Z, Python>=3.10. Local1.63.0 is older, not described as latest. Main Python3.10.6 and installed Chrome are verified by isolated actual fixture runs; this does not certify1.64.0 compatibility with every existing integration. User contract excludes dependency/browser installs, so existing pin retained and independent bounded design fixes tested. No newer-library speed claim, paid API or giant model. Documentation pages show no publication date. Existing licenses and historical source/artwork attribution retained.
''')
    write(OUT/'rollback.md','''# Scoped rollback and deterministic resume

Preserve the current dirty tree and existing user work. Review source.patch/source-hashes.json, reverse only Prompt14 hunks; never git reset/clean or replace the whole checkout. Ignored preimages .jarvis-runtime/jarvis-audit/module14-pre/<relative-path-with-__>, root overview root-README.md. app/ canonical, InsTAREELS alias not separately edited. No commit/deploy/install/browser download to undo. Preserve completed evidence and later edits.

Run commands.txt with existing main environment/installed Chrome; benchmark before catalog. <=2 small workers, no concurrent heavy model/GPU work. Headless contexts are temporary, all generic fixture traffic intercepted/aborted; redirect fixture allows only its owned loopback origin. Never use the production profile or real account to make a fixture pass. JRV-14-007 requires a reviewed scoped download/save/verification adapter; JRV-14-009 needs explicit scoped tab selection. Both are new capability work requiring appropriate review/authorization. Current authentication/form/autosave limits remain. Exact global remaining IDs are in ../../remaining-case-ids.txt; read the next requested prompt first. Full evidence must match accepted source; reporter rejects failed/stale XML. No blanket production certificate.
''')
    blurb=f'''**Browser/DOM audit — 2026-10-15 IST:** Nine reproduced defects fixed: validate
before opening, preserve controller settings, wait for semantic targets, report
labels/sign-in and reject malformed replies, stale URLs and renamed click targets.
DOM summaries use one browser round trip and omit field values.
[Executed cases, measurements, limits and rollback](artifacts/jarvis-audit/modules/14-browser-playwright/inventory.md).
Verification: **{full['passed']:,} regression PASS / {full['skipped']} skips**;
**{targeted['passed']} targeted PASS / {targeted['skipped']} blocked skips**; Prompt14 **30 PASS / 2 BLOCKED**.
Launcher: **{ready['status']}**; [current check](artifacts/jarvis-audit/modules/14-browser-playwright/readiness.json).
Verified downloads and explicit tab selection remain missing production adapters.
Headless fixtures do not certify live accounts, arbitrary autosave or production readiness.'''
    prepend(BASE/'README.md',blurb);prepend(BASE.parent/'README.md',blurb.replace('](artifacts/','](app/artifacts/'))
    notice='''**2026-10-15 browser audit:** Current DOM summaries include bounded label names,
sign-in heuristics and untrusted metadata; generic role targets wait then require
uniqueness, fresh URL and pinned semantic identity after the cue. Multiple owned
tabs block generic mutations. Download/save and explicit tab selection are not
implemented production capabilities. [Actual headless assertions, metrics and limits](../artifacts/jarvis-audit/modules/14-browser-playwright/inventory.md).
Playwright1.63.0 retained;1.64.0 upstream release recorded without installation.
Historical live measurements below retain original dates; no new public account/GUI trial.'''
    for name in DOCS:prepend(BASE/name,notice)
    previous=ROOT/'final-report-before-module14.md'
    if not previous.exists():shutil.copyfile(ROOT/'final-report.md',previous)
    table='\n'.join(f'| {m["number"]:02} | {m["module"]} | {m["status"]} |' for m in modules)
    stats=''
    for group in ('tier','category'):
        stats+='\n| '+group+' | PASS | FAIL | BLOCKED | SKIPPED | NOT RUN |\n| --- | --- | --- | --- | --- | --- |\n'
        stats+='\n'.join('| '+k+' | '+' | '.join(str(v.get(state,0)) for state in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN'))+' |' for k,v in summary['by_'+group].items())+'\n'
    write(ROOT/'final-report.md',f'''# Jarvis audit — Prompt14 follow-up, 2026-10-15 IST

**Prompt14:30 catalog fixture PASS / 2 BLOCKED / 0 FAIL.** Full **{full['passed']} PASS / {full['skipped']} skips**, {full['seconds']:.2f}s; targeted **{targeted['passed']} PASS / {targeted['skipped']} BLOCKED skips**. Launcher **{ready['status']}**. [Full XML](modules/14-browser-playwright/full-regression.xml),[targeted XML](modules/14-browser-playwright/cases-and-contracts.xml),[actual completion](modules/14-browser-playwright/full-run-completion.txt),[readiness/gaps](modules/14-browser-playwright/readiness.json),[skip reasons](modules/14-browser-playwright/full-regression-skip-reasons.json). Counts overlap; fixture success is separate from service readiness/live production acceptance.

Current repo `{commit}`; baseline `bdcb15a52bbf23101950cd1625f249a564e647ee`, existing branch `{branch}`; Windows/Python{platform.python_version()}, installed Playwright1.63.0/Chrome, Ryzen7/32GB/RTX3050 Laptop4GB target. Isolated actual headless browser contexts and synthetic/loopback data; no production profile/user tabs/account writes/personal deletions/OS settings/credentials/install/browser download/model/deploy/commit. Existing changes preserved. HEAD advanced through an external phase1 commit during this run; this audit made no commit. Saved scoped preimages and final hashes define its changes. [Environment](modules/14-browser-playwright/environment.json), [Inventory/dependency/run order](modules/14-browser-playwright/inventory.md).

## Source map, fixes and measured change

{matrix}

Nine reproduced defects corrected. Baseline62 PASS; [failure history](modules/14-browser-playwright/failures.md),[retained changes](modules/14-browser-playwright/changes.md),[exact files/hashes](modules/14-browser-playwright/files-changed.json),[scoped source patch](modules/14-browser-playwright/source.patch),[rollback/resume](modules/14-browser-playwright/rollback.md). Boundaries retain current registry approvals, browser/profile ownership and no replay. No new generic download or tab capability.

Same-machine headless summary benchmark warm p50/p95 **{bench['before_warm']['p50_ms']:.3f}/{bench['before_warm']['p95_ms']:.3f}→{bench['after_warm']['p50_ms']:.3f}/{bench['after_warm']['p95_ms']:.3f}ms**, cold-context p95 **{bench['before_cold']['p95_ms']:.3f}→{bench['after_cold']['p95_ms']:.3f}ms**;4→1 browser round trips. [50 raw samples](modules/14-browser-playwright/benchmarks.csv),[allocations/scope](modules/14-browser-playwright/benchmark-summary.json).80 common name/role/href rows equivalent; absent href normalized to None. New HTML-label behavior separately asserted. Page load excluded, no real external effects; no universal site/model/audio/VRAM or2-second claim. Previous per-module metrics and reports preserved [through13](final-report-before-module14.md).

Firecrawl official [actionability](https://playwright.dev/python/docs/actionability)/[downloads](https://playwright.dev/python/docs/downloads)/[PyPI metadata](https://pypi.org/pypi/playwright/json): upstream1.64.0 uploaded2026-10-13T23:35:20Z, Python>=3.10; local1.63.0 retained under no-install contract. [Actual extraction results](modules/14-browser-playwright/upstream-checks.json),[compatibility decision](modules/14-browser-playwright/compatibility.md). No current-version or untested upgrade claim.

## Risks, blockers and exact accounting

JRV-14-007 verified-download/save and JRV-14-009 explicit tab selection are missing production adapters. Auth detection/accessible-name summary are heuristics; iframe/shadow/very large DOM coverage limited. A fill can invoke site autosave; label filtering is not universal transaction protection. DOM guard/input not atomic; existing240ms cursor cue retained with final admission. Other established logs retain their redaction policy. Headed browser/desktop handoff, real accounts/logins, general live sites, physical GPU contention and long soak not certified. Two prior native9b proofs are now stale after the concurrent knowledge_worker change; Ollama unavailable, so fresh validation is BLOCKED without modifying old proof hashes. Earlier acoustic/GPU/research/PDF/DPI/UAC catalog acceptance gates remain unrevalidated here. Current Phase2 documentation supersedes older implementation claims about absent speech leases; retained historical skip labels are not a fresh assertion that those leases are missing. Initial full2 failures were stale live-evidence hash checks, retained separately; they are now explicit native-prerequisite blockers, not new inferred passes. Current Phase2 speech/GPU changes are not re-audited by this browser module; their earlier catalog gates remain acceptance gaps, not fresh missing-implementation claims. No whole-system production/security certificate.

1184 unique IDs: **{summary['catalog_counts']}**. [Exact ledger](test-results.jsonl),[32 module14 IDs/assertions](modules/14-browser-playwright/tests.jsonl),[remaining IDs](remaining-case-ids.txt),[machine totals](summary.json). No pass inferred from reading JSONL.

{stats}

| Module | Name | Status |
| --- | --- | --- |
{table}

Earliest global unresolved **{summary['next_case']}**, next NOT RUN **{next_id}**. Prompt14 unresolved **JRV-14-007/JRV-14-009**. Read the next requested prompt before continuing;37 modules are not all complete.
''')
    patch='';hashes={}
    for name in (*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py','tests/test_questions_context_audit.py'):
        old=PRE/name.replace('/','__');current=BASE/name
        patch+=''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),current.read_text(encoding='utf-8').splitlines(True),fromfile='module14-pre/'+name,tofile=name,n=2))
        hashes[name]=dict(before=hashlib.sha256(old.read_bytes()).hexdigest(),after=hashlib.sha256(current.read_bytes()).hexdigest())
    write(OUT/'source.patch',patch);write(OUT/'source-hashes.json',json.dumps(hashes,indent=2)+'\n')
    files=[dict(path='app/'+name,sha256=hashlib.sha256((BASE/name).read_bytes()).hexdigest()) for name in FILES]
    files.append(dict(path='README.md',sha256=hashlib.sha256((BASE.parent/'README.md').read_bytes()).hexdigest()))
    write(OUT/'files-changed.json',json.dumps(dict(scope='Scoped Prompt14 preimage diffs, not total dirty tree; no commit/deploy.',files=files,artifact_directory='app/artifacts/jarvis-audit/modules/14-browser-playwright',shared_artifacts=['final-report.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt']),indent=2)+'\n')
    print(json.dumps(dict(module14=dict(Counter(r['status'] for r in cases)),targeted=targeted,full=full,catalog=summary['catalog_counts'],next_notrun=next_id),indent=2))


if __name__=='__main__':main()
