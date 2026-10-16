"""Evidence-only Prompt13 report; never infer a pass from catalog text."""
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
ROOT=BASE/'artifacts/jarvis-audit';OUT=ROOT/'modules/13-desktop-control'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module13-pre'
RUNTIME=('jarvis/execution_router.py','jarvis/execution_adapters.py','jarvis/jarvis_pointer.py','jarvis/independent_cursor.py','jarvis/ui_transport.py')
DOCS=('docs/execution-providers.md','docs/independent-cursor.md','docs/windows-commands.md','docs/system-map.md')
FILES=(*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py','tests/test_desktop_control_audit.py',
       'scripts/verification/verify_desktop_control_audit.py','scripts/verification/report_desktop_control_audit.py','README.md',*DOCS)


def write(path,text):path.write_text(text,encoding='utf-8')


def result(name):
    tree=ET.parse(OUT/name);nodes=list(tree.iter('testcase'));assert nodes
    assert not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    skips=[n for n in nodes if n.find('skipped') is not None]
    if name=='cases-and-contracts.xml':assert all('BLOCKED:' in n.find('skipped').get('message','') for n in skips)
    if skips:write(OUT/(name.removesuffix('.xml')+'-skip-reasons.json'),json.dumps([{'node':n.get('classname')+'::'+n.get('name'),'reason':n.find('skipped').get('message','')} for n in skips],indent=2)+'\n')
    return dict(passed=len(nodes)-len(skips),blocked=len(skips),seconds=float(next(tree.iter('testsuite')).get('time',0)))


def prepend(path,text):
    old=path.read_text(encoding='utf-8');marker='<!-- prompt13-audit -->';endmarker='<!-- /prompt13-audit -->'
    if marker in old:
        a=old.index(marker);b=old.index(endmarker,a)+len(endmarker);old=old[:a]+old[b:].lstrip('\n')
    head,body=old.split('\n',1);write(path,head+'\n\n'+marker+'\n'+text+'\n'+endmarker+'\n\n'+body.lstrip('\n'))


def main():
    baseline=result('existing-baseline.xml');targeted=result('cases-and-contracts.xml');full=result('full-regression.xml')
    assert all((OUT/'full-regression.xml').stat().st_mtime>=(BASE/n).stat().st_mtime for n in (*RUNTIME,'tests/test_desktop_control_audit.py'))
    followup=result('accounting-followup.xml')
    assert (OUT/'accounting-followup.xml').stat().st_mtime>=(BASE/'scripts/verification/audit_catalog.py').stat().st_mtime
    assert sum(n.find('failure') is not None for n in ET.parse(OUT/'reproduced-failures.xml').iter('testcase'))==6
    assert sum(n.find('failure') is not None for n in ET.parse(OUT/'malformed-frame-reproduced.xml').iter('testcase'))==1
    assert sum(n.find('failure') is not None for n in ET.parse(OUT/'native-denial-reproduced.xml').iter('testcase'))==1
    ready=json.loads((PRE/'readiness-private.json').read_text(encoding='utf-8-sig'))
    assert ready['status'] in {'ready','repair_required','check_incomplete'}
    ready_label=ready['status']
    readiness_gaps={'missing':ready.get('missing',[]),'incomplete':[{'component':r.get('component'),'error_type':r.get('error_type')} for r in ready.get('incomplete',[]) if isinstance(r,dict)]}
    write(OUT/'readiness.json',json.dumps(dict(date='2026-10-15 IST',status=ready['status'],exit_code=0 if ready_label=='ready' else 1,gaps=readiness_gaps,command='.venv/Scripts/python.exe -m jarvis.launcher --check',scope=ready.get('scope'),services={k:v['status'] for k,v in ready.get('services',{}).items()}),indent=2)+'\n')
    modules=json.loads((ROOT/'module-map.json').read_text())
    modules[12].update(status='30 FIXTURE PASS / 2 BLOCKED; LIVE DESKTOP ACCEPTANCE UNVERIFIED',
      reason='Provider/admission/physical-coordinate/focus/readback/uncertainty/protocol/privacy fixtures; live150%DPI and UAC require authorized isolated desktop. No real clicks/app launches/settings changes.',
      sources=[*RUNTIME,'jarvis/ui_worker.py','jarvis/ui_controls.py','jarvis/visual_fallback.py','jarvis/desktop_actions.py',*DOCS],
      test_candidates=['tests/test_desktop_control_audit.py','tests/test_execution_router.py','tests/test_ui_controls.py','tests/test_jarvis_pointer.py','tests/test_visual_fallback.py','tests/test_automation_upgrade.py'])
    prior=list(ET.parse(ROOT/'modules/12-tool-registry/cases-and-contracts.xml').iter('testcase'))
    assert len(prior)==37 and not any(n.find('failure') is not None or n.find('skipped') is not None for n in prior)
    modules[11].update(status='32 FIXTURE PASS; LIVE ACCEPTANCE UNVERIFIED',reason='Existing37-assertion dedicated XML and current full regression reviewed; omitted catalog namespace now authorized, with fresh accounting/registry check. Original module12 source/evidence preserved.')
    write(ROOT/'module-map.json',json.dumps(modules,indent=2)+'\n')
    from scripts.verification.audit_catalog import reconcile
    with contextlib.redirect_stdout(io.StringIO()):reconcile()
    rows=[json.loads(s) for s in (ROOT/'test-results.jsonl').read_text().splitlines()]
    assert len(rows)==len({r['id'] for r in rows})==1184
    cases=[r for r in rows if r['id'].startswith('JRV-13-')]
    assert Counter(r['status'] for r in cases)=={'PASS':30,'BLOCKED':2}
    for row in cases:row['scope']='Isolated fake UIA/Win32/provider/pipe fixture, not real Notepad/Calculator or physical screen-lock/privilege/DPI validation. Simulated HWND/focus/physical coordinates and independent fake-native value readback. Actual router/provider/transport/policy/checkpoint boundaries where stated in test code. Pressure is injected MemoryError, not physical GPU stress.'
    write(OUT/'tests.jsonl',''.join(json.dumps(r)+'\n' for r in cases))
    write(OUT/'remaining-case-ids.txt','\n'.join(r['id'] for r in cases if r['status']!='PASS')+'\n')
    assert sum(r['id'].startswith('JRV-12-') and r['status']=='PASS' for r in rows)==32
    summary=json.loads((ROOT/'summary.json').read_text());next_id=next(r['id'] for r in rows if r['status']=='NOT RUN')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip();branch=subprocess.check_output(['git','branch','--show-current'],cwd=BASE,text=True).strip()
    bench=json.loads((OUT/'benchmark-summary.json').read_text())['results']
    metrics='\n'.join(f'| {k} | {v["samples"]} | {v["p50_ms"]:.5f} | {v["p95_ms"]:.5f} | {v["peak_python_bytes"]} |' for k,v in bench.items())
    matrix='''| Documented claim / entry | Checked implementation | Executed proof / limit |
| --- | --- | --- |
| Ordered providers | execution_adapters.PROVIDERS → execution_router.execute | Actual order jarvis-pointer → UFO → Windows-MCP → CUA → OpenComputerUse → Agent-S; five adapted ports, not five installed frameworks; only preparation fallback, deny/dispatch failure stops |
| Existing app/keyboard path | actions.Desktop.capture/type, Actions._execute, window_focus.focus_app | Existing executable/focus checks and per-character foreground/SendInput checks retained; no typing-speed change/live Notepad proof. App focus helpers can select the first matching executable/Z-order window; not general duplicate-window disambiguation |
| UIA target/focus | UIControls._handle → UITransport → ui_worker.perform/routed.guard | Explicit HWND/PID/foreground/visible/enabled/runtime ID/name/role/rectangle; fake changed foreground/lock0 refuses input, duplicate labels clarify; no live app launch certification |
| Touch/coordinates | JarvisPointer.prepare → jarvis_pointer.tap | Temporary physical-pixel DPI context restored; exact runtime ID/geometry/focus/hit-test repeated after idle and immediately before touch; fake150% geometry injects one down/up at300,225, moved target gets0 touches |
| Visual-point fallback | independent_cursor.at_point/activate_point | Existing window/PID/coverage guard now passed into tap admission; no whole-scene capture during every idle wait, so same-window scene races remain possible |
| Readback and no replay | execution_router + direct_execution.run + TaskState | Exact fake-native field value, no-op fresh state, failed/hung dispatch sent once, no next provider, direct runner pauses on unverified result; postcondition observations are bounded but COM itself can block |
| IPC failure ownership | UITransport.request/_stop_process/_backoff/close | Malformed/mismatched frames stop only owned worker, no replay;100 requests over5 threads×20 rounds have unique serial IDs; cancellation/backoff/intentional Stop preserved |
| Privacy/authority | categorical router errors/trace UUIDs, ui_worker.record, ToolRegistry policy | Synthetic secret excluded from new router receipt/message; existing journal omits labels/text. Current registry approval/allowlist still authoritative; not a general personal-data scrubber |
| Source/dependency truth | integrations/execution-primitives/source-manifest + retained licenses | Pinned selected sources; Windows-MCP pattern subset runs existingPython3.10.6, full Python3.14 server not installed; licenses preserved; no package/model/service added |
'''
    write(OUT/'inventory.md',f'''# Prompt13 — desktop-control audit, 2026-10-15 IST

**30 catalog fixture PASS / 2 BLOCKED / 0 FAIL / 0 SKIPPED / 0 NOT RUN.** JRV-13-004 live150% DPI and JRV-13-007 real UAC/secure desktop are blocked without an authorized isolated live setup. Fake coordinate/permission assertions execute separately. No personal display change, elevation, screen lock, mouse click, real app launch, typing, send, account mutation, install or deployment occurred. Fixtures are not production desktop acceptance.

Repo `{commit}`, existing branch `{branch}` retained, Windows/Python{platform.python_version()}, Ryzen7/32GB/RTX3050 Laptop4GB target (prior observed machine). app/ canonical; InsTAREELS alias not separately edited. Existing user/Prompt12 work preserved. No commit/reset or heavyweight GPU/model work.

## Source-map evidence and dependency/run order

{matrix}

Read system-map, execution-providers, windows-commands execution contract, independent-cursor and retained primitive source/license documentation. Historical images/live checks are preserved with dates and attribution, not fabricated new validation. Source files/config/registrations/tests inspected; [static source census](source-census.json) confirms current order, all five pinned revisions and matching text-normalized retained/runtime Windows-MCP pattern copies. Order: real entry points/permissions/recovery → baseline → isolated fault reproductions → scoped router/target/protocol fixes →32 catalog assertions + neighboring visual/direct/task tests → matched component profile → full regression/readiness → ledger/docs. Deviation from suggested UIA-first upgrade: preserve the user's existing pointer-first setting/order; improve admission rather than silently change click behavior. No new language/vision/model reranker, framework server or learned ability.

## Executed results

Baseline **{baseline['passed']} PASS**, {baseline['seconds']:.2f}s,[XML](existing-baseline.xml). **Eight reproduced defects**: six in [initial failure XML](reproduced-failures.xml), plus [malformed worker frame](malformed-frame-reproduced.xml) and [native COM denial](native-denial-reproduced.xml). Earlier2422-pass full result is retained separately; only accepted full-regression.xml includes the native denial correction. First fixes passed146 neighboring tests before catalog expansion. Final targeted **{targeted['passed']} PASS / {targeted['blocked']} skips**, {targeted['seconds']:.2f}s,[XML](cases-and-contracts.xml). Full **{full['passed']} PASS / {full['blocked']} skips**, {full['seconds']:.2f}s,[XML](full-regression.xml),[actual completion](full-run-completion.txt). Suites overlap. Launcher **{ready_label}**,[redacted check](readiness.json). [Commands](commands.txt),[all32 IDs/assertions](tests.jsonl). Readiness is a separate check: Docker Linux engine/Ollama unavailable and F5 import check timed out in this run; no services were started or personal settings changed. Existing COM warning, if emitted, is retained in completion output.

Applicable journey is simulated Notepad field admission and exact hello readback through the actual router, changed HWND/foreground rejection through ui_worker.routed, duplicate choices, real provider→tap exercised entirely on fake user32/UIA, temporary transports/direct TaskState fixtures and zero model calls for exact direct grammar. No actual Notepad→Calculator journey claimed. Case003 proves existing foreground-HWND binding and duplicate-control refusal; app focus helpers still select a first matching executable/Z-order window and do not provide general duplicate-window clarification. Network outage fixture proves local routing makes0 network calls; MemoryError fixture proves pre-dispatch fallback, not physical RAM/VRAM resilience. Mocked secure-desktop denial is not live UAC proof. Five-way100-request protocol load is bounded concurrency, not a multi-hour soak. Screen/PC content did not go to cloud; public upstream research is separate.

## Same-machine component profile and keep decision

| Algorithm/fixture | Samples | p50 ms | p95 ms | Peak traced Python bytes |
| --- | --- | --- | --- | --- |
{metrics}

[50 raw trials](benchmarks.csv),[scope](benchmark-summary.json): saved old router versus current router, same six synthetic factories/first provider success/native fake readback, one fake dispatch every trial and0 real effects.5 fresh per-call fixtures labelled cold,20 repeated labelled warm; not OS/model/COM cold. Lazy construction creates1 provider instead of6 on first success; original fixed order preserved. New strict text validation and UUID carry overhead: warm p95 **{bench['before_warm']['p95_ms']:.5f}→{bench['after_warm']['p95_ms']:.5f}ms**. Warm median increases slightly; these short timings do not establish a general latency win. Retain reduced unused construction/warm allocation and correctness/privacy changes; no full desktop, TTFT, first-audio or VRAM speed claim. Physical re-admission adds native calls not measured by this synthetic router profile. Tracemalloc measures transient component allocations, not whole-process memory.

## Limits and blockers

Live150% DPI/multi-monitor and real secure desktop/elevated/locked-session trials remain blocked. Shared focus/keyboard and physical cursor compatibility restoration remain shared resources. Admission and Windows input are not atomic; a target/user mouse can still change after the final check. Visual-only points recheck window/PID/coverage, not the whole image during every idle wait. COM providers can block; one-second verification means observation deadline, not forced COM cancellation; outer owned-worker deadline is the containment boundary. Touch injection failure after DOWN remains uncertain, never fallback/replay. Freshly successful UIA readback does not establish an arbitrary app/business outcome. Categorical router errors reduce diagnostics; other pre-existing task logs retain their established behavior. Existing app-opening/focus helpers can choose the first matching executable/Z-order window; foreground-bound fixture disambiguation does not certify every ambiguous app-opening request. No broad security/production certificate.

[Changes](changes.md),[failures](failures.md),[upstream/pins](compatibility.md),[rollback/resume](rollback.md),[exact files/hashes](files-changed.json),[source diff](source.patch). Earliest global unresolved **{summary['next_case']}**, next catalog NOT RUN **{next_id}**. Other module work is preserved. Existing Prompt12 assertions were fully reviewed and rerun in a focused registry/accounting check; the omitted reviewed namespace is now included in global totals, without changing Prompt12 product code.
''')
    write(OUT/'failures.md','''# Reproductions and fixes — 2026-10-15 IST

Six initial failures: PermissionError preparation fell through; arbitrary provider exception payload was copied into uncertain-action messages/receipts; oversized target strings reached guard/provider; malformed/nonboolean pointer config enabled physical input; target guard could not run after up-to1.5s mouse-idle wait; thread DPI override was never restored. A seventh reproduced fault let a non-object worker frame raise AttributeError without stopping/backing off the owned worker. Final review reproduced an eighth defect: native COM E_ACCESSDENIED fell through despite the Python PermissionError fix. Shared COM HRESULT/Win32 denial classification now halts both router fallback and pointer preparation. All have executed regressions. The earlier full result2422 PASS/21 skips is preserved separately; the accepted full XML is rerun after this last correction.

Corrections halt on permission denial, bound text before guard, use categorical errors/UUIDs, fail closed on malformed/missing config file (valid omitted option still defaults on), scope/restore DPI context, re-admit semantic target/hit-test/geometry after idle and before DOWN, propagate visual-point window guard, and reject malformed response/ID/result/error envelopes through existing no-replay cleanup. First targeted146 PASS. Initial expanded catalog had two fixture class-name errors (UIControlTests versus actual UITests), corrected without product behavior changes. The first baseline command referenced absent test_ui_transport.py; no tests ran in that invocation, then the actual baseline paths ran118 assertions; transport tests live in test_automation_upgrade.py. These are audit setup errors, not additional product defects.

Final assertions have0 FAIL. Live DPI and UAC are two explicit BLOCKED catalog IDs; mocks do not certify them. Time-of-check/input races, visual-only same-window scene changes and uncooperative COM are practical limits, not claimed solved by these fixtures.
''')
    write(OUT/'changes.md','''# Retained scoped changes

- execution_router.py: strict bounded request text before guard/preparation; COM/Win32/Python permission denial halts; exception text categorized; trace UUID per route; construct providers lazily in the unchanged priority order.
- execution_adapters.py: physical-pointer preparation uses temporary physical-pixel context; its admission closure repeats HWND/foreground/visible/enabled/runtime ID, exact geometry and control-centre hit-test after idle and immediately before touch. No stale coordinate is automatically retried or substituted.
- jarvis_pointer.py: temporary/restored DPI context; optional read-only admit callback after idle/before DOWN; malformed/missing/oversized config fails closed and only boolean values enable touch. Valid omitted physical_clicks keeps its existing default true. Existing touch-UP cleanup and user's cursor restoration preserved.
- independent_cursor.py: existing visual-point window/PID/coverage guard propagates through tap's delayed admission. This does not add a new whole-image check after idle.
- ui_transport.py: malformed/non-object frames, boolean/noninteger IDs, invalid results/errors trigger existing owned-worker cleanup/backoff, no replay. No changes to shared services/process ownership.
-32 dedicated catalog assertions +10 supplemental regressions, reviewed BLOCKED accounting, source preimages/paired benchmark/report. A catalog allowlist omission for the reviewed existing Prompt12 class was corrected with a fresh registry/accounting check; no module12 product source was changed. Runtime manifest and READMEs/docs updated; no new dependency/service/tool/public capability/model/download/install/setting mutation. Existing app behavior and artwork remain; no new UI screenshot.
''')
    write(OUT/'compatibility.md','''# Official current checks — 2026-10-15 IST

Firecrawl retrieved official [UFO v3.0.10](https://github.com/microsoft/UFO/releases/tag/v3.0.10) (date not shown), [Windows-MCP v0.8.8](https://github.com/CursorTouch/Windows-MCP/releases/tag/v0.8.8) (10 Oct01:33;year not printed), [Cua cua-spaces-v0.9.2](https://github.com/trycua/cua/releases/tag/cua-spaces-v0.9.2) (date not shown), [OpenComputerUse v1.2.0](https://github.com/opensymph/open-computer-use/releases/tag/v1.2.0) (Aug25;year not printed), [Agent-S v0.3.2](https://github.com/simular-ai/Agent-S/releases/tag/v0.3.2) (2025-12-16). Raw extracted findings/status/canonical URLs: [upstream-checks.json](upstream-checks.json). Cua's latest release is Spaces, not proof of a new Windows driver API. Missing dates were not invented. Windows-MCP notes describe COM/UIA thread-affinity changes; Jarvis retains its existing isolated single-thread worker rather than installing the full server.

[Microsoft SetThreadDpiAwarenessContext](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setthreaddpiawarenesscontext) documents returning the prior context for restoration. That page does not document input privilege limits; UAC bypass is neither inferred nor attempted. [Microsoft COM error codes](https://learn.microsoft.com/en-us/windows/win32/com/com-error-codes-1) identifies E_ACCESSDENIED as0x80070005, general access denied; [actual extracted check](native-denial-upstream.json). Signed/unsigned HRESULTs use this shared classification before fallback. Local selected source revisions remain exactly those in integrations/execution-primitives/source-manifest.json. Existing Windows-MCP vendored pattern subset is compatible with mainPython3.10.6; pinned full server's Python3.14 requirement remains excluded. Existing pywinauto/COM/pywin32 only. Retained licenses/attribution unchanged, no upstream pulls/framework installs/models/paid requirement. No latest-release performance or complete compatibility claim from reading notes; small local admission/transport fixes were regression-tested instead.
''')
    write(OUT/'rollback.md','''# Rollback and deterministic resume

Preserve the existing dirty tree. Review source.patch/source-hashes.json, then reverse only Prompt13 hunks; never git reset/clean or replace the whole checkout with older files. Ignored local preimages: .jarvis-runtime/jarvis-audit/module13-pre/<relative-path-with-__>. Root overview is root-README.md. app/ canonical; InsTAREELS alias must not be separately patched. Preserve later/user/Prompt12 changes. No commit/deployment/package/model/settings change to undo; public patch is a portable scoped rollback aid.

Run commands.txt with the existing main environment and isolated fixtures; benchmark generation precedes the catalog assertion that checks its measurements. Keep <=2 small test workers and no parallel heavy GPU tests. Read the selected next module prompt before continuing; global remaining-case-ids.txt has exact unresolved IDs. JRV-13-004 needs an authorized isolated desktop at150% DPI/multi-monitor; JRV-13-007 needs an authorized secure-desktop/UAC fixture. Do not change personal display settings, elevate, lock the session or generate real input to satisfy those blockers without permission. Existing full XML and readiness must correspond to accepted source; report script refuses failed/stale evidence. No blanket production sign-off.
''')
    commands='''.venv/Scripts/python.exe -m pytest tests/test_execution_router.py tests/test_desktop_actions.py tests/test_ui_controls.py tests/test_visual_fallback.py tests/test_independent_cursor.py tests/test_jarvis_pointer.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/13-desktop-control/existing-baseline.xml
.venv/Scripts/python.exe scripts/verification/verify_desktop_control_audit.py
.venv/Scripts/python.exe -m pytest tests/test_desktop_control_audit.py tests/test_execution_router.py tests/test_desktop_actions.py tests/test_ui_controls.py tests/test_visual_fallback.py tests/test_independent_cursor.py tests/test_jarvis_pointer.py tests/test_automation_upgrade.py tests/test_audit_result_accounting.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/13-desktop-control/cases-and-contracts.xml
.venv/Scripts/python.exe -m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/13-desktop-control/full-regression.xml
.venv/Scripts/python.exe -m pytest tests/test_tool_registry_audit.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/13-desktop-control/accounting-followup.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe scripts/verification/report_desktop_control_audit.py'''
    write(OUT/'commands.txt',commands+'\n')
    blurb=f'''**Desktop-control audit — 2026-10-15 IST:** Eight reproduced defects fixed:
COM/Win32/Python permission denial stops fallback; delayed touch rechecks target/window admission;
DPI context is restored; malformed pointer settings and IPC frames fail closed;
request text is bounded and router errors carry categories/UUIDs.
Provider order stays pointer → UFO → Windows-MCP → CUA → OpenComputerUse → Agent-S.
[Assertions, measured tradeoffs and rollback](artifacts/jarvis-audit/modules/13-desktop-control/inventory.md).
Verification: **{full['passed']:,} regression PASS / {full['blocked']} blocked skips**;
**{targeted['passed']} targeted PASS / {targeted['blocked']} blocked skips**; Prompt13 **30 PASS / 2 BLOCKED**,
launcher **{ready_label}** (Docker/Ollama unavailable; F5 check timed out). Live150% DPI and secure desktop remain unverified; no live
Notepad/Calculator or production desktop success is claimed.'''
    prepend(BASE/'README.md',blurb);prepend(BASE.parent/'README.md',blurb.replace('](artifacts/','](app/artifacts/'))
    notice='''**2026-10-15 desktop-control audit:** Current pointer-first order is preserved.
Delayed touch re-admits target geometry/focus/hit-test and visual-point window
guards; thread DPI context is restored. Malformed pointer settings and worker
responses fail closed. Provider errors are categorical and traceable; uncertain
actions are never replayed. [Executed fixture scope, live blockers and tradeoffs](../artifacts/jarvis-audit/modules/13-desktop-control/inventory.md).
Historical images/results below keep their dates; no new live desktop check.'''
    for name in DOCS:prepend(BASE/name,notice)
    p=BASE/'docs/system-map.md';s=p.read_text(encoding='utf-8').replace('UIA via providers **UFO → Windows-MCP → CUA → Open Computer Use → Agent-S**','UIA/touch via providers **Jarvis pointer → UFO → Windows-MCP → CUA → Open Computer Use → Agent-S**');write(p,s)
    previous=ROOT/'final-report-before-module13.md'
    if not previous.exists():shutil.copyfile(ROOT/'final-report.md',previous)
    module_table='\n'.join(f'| {m["number"]:02} | {m["module"]} | {m["status"]} |' for m in modules)
    stats=''
    for group in ('tier','category'):
        stats+='\n| '+group+' | PASS | FAIL | BLOCKED | SKIPPED | NOT RUN |\n| --- | --- | --- | --- | --- | --- |\n'
        stats+='\n'.join('| '+k+' | '+' | '.join(str(v.get(state,0)) for state in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN'))+' |' for k,v in summary['by_'+group].items())+'\n'
    write(ROOT/'final-report.md',f'''# Jarvis audit — Prompt13 follow-up, 2026-10-15 IST

**Prompt13:30 catalog fixture PASS / 2 BLOCKED / 0 FAIL.** Full **{full['passed']} PASS / {full['blocked']} skips**, {full['seconds']:.2f}s; targeted **{targeted['passed']} PASS / {targeted['blocked']} BLOCKED skips**. Launcher **{ready_label}**. [Full XML](modules/13-desktop-control/full-regression.xml),[targeted XML](modules/13-desktop-control/cases-and-contracts.xml),[actual completion](modules/13-desktop-control/full-run-completion.txt),[redacted readiness](modules/13-desktop-control/readiness.json). Counts overlap. These are fixture/regression checks. Readiness failed: Docker/Ollama unavailable, F5 check timed out; no service start attempted. Whole-system/live production acceptance remains open.

Repo `{commit}`, existing branch `{branch}`, Windows/Python{platform.python_version()}, Ryzen7/32GB/RTX3050 Laptop4GB target; CPU-only mocked desktop work. Existing dirty/Prompt12 work preserved, no new checkout/reset/commit/deploy/install/account write/personal setting/delete/model/real input. [Environment/run order/inventory](modules/13-desktop-control/inventory.md).

## Source map, changes and measurement

{matrix}

Eight reproduced faults fixed; [before failures](modules/13-desktop-control/failures.md),[scoped changes](modules/13-desktop-control/changes.md),[exact files and SHA256s](modules/13-desktop-control/files-changed.json),[source patch](modules/13-desktop-control/source.patch),[rollback/resume](modules/13-desktop-control/rollback.md). Baseline118 PASS. Current order remains pointer-first, not the older UIA-first map claim. Late pointer guards cover semantic target/window admission; visual same-window scene and final-check/input races remain limits. Malformed protocol cleanup respects owned worker/backoff/no replay.

Paired synthetic router warm p50/p95 **{bench['before_warm']['p50_ms']:.5f}/{bench['before_warm']['p95_ms']:.5f}→{bench['after_warm']['p50_ms']:.5f}/{bench['after_warm']['p95_ms']:.5f}ms**; cold p95 **{bench['before_cold']['p95_ms']:.5f}→{bench['after_cold']['p95_ms']:.5f}ms**. [50 trials](modules/13-desktop-control/benchmarks.csv),[peak allocation/scope](modules/13-desktop-control/benchmark-summary.json). First-success provider construction6→1; warm median increases slightly and tail timings vary; no speedup claim.0 real effects, one fake dispatch/readback each. No native COM/desktop/GPU/TTFT/audio measurement. Prior per-module results/metrics remain in [preserved previous report](final-report-before-module13.md) and linked predecessors; pre-existing [Prompt12 evidence](modules/12-tool-registry/inventory.md) is preserved independently, reconciled after review and a fresh [registry/accounting check](modules/13-desktop-control/accounting-followup.xml).

Firecrawl official current pages: UFOv3.0.10(no displayed date), Windows-MCPv0.8.8(10Oct01:33,no year printed), CuaSpacesv0.9.2(no date), OpenComputerUsev1.2.0(Aug25,no year printed), Agent-Sv0.3.2(2025-12-16); [exact URLs/findings](modules/13-desktop-control/upstream-checks.json),[compatibility and Microsoft DPI guidance](modules/13-desktop-control/compatibility.md). Pinned ports/full-server separation and licenses retained; no untested upstream/runtime upgrade.

## Risks, blockers and exact accounting

Live150%DPI/multi-monitor and real UAC/secure-desktop tests blocked; no personal OS state changed. Physical admission/input is not atomic; visual-point idle wait lacks full-image recapture. Shared keyboard/focus/pointer compatibility restoration remains. Uncooperative COM can block until owned worker timeout; verification deadline is not forcible cancellation. Arbitrary model/GUI/business-task correctness, all elevated apps, long soak and physical GPU contention remain unverified. Existing acoustic/shared-speech-lease/unfamiliar-program-research/PDF blockers persist. Existing executable/Z-order app-focus selection is not general duplicate-window clarification. No production/security or universal two-second certificate.

1184 unique catalog IDs: **{summary['catalog_counts']}**. [All IDs/assertions](test-results.jsonl),[all32 Prompt13 IDs](modules/13-desktop-control/tests.jsonl),[remaining IDs](remaining-case-ids.txt),[machine-readable totals](summary.json). No pass inferred from JSONL ingestion. Existing module12 dedicated37 assertions were reviewed/rerun in a focused follow-up, resolving a missing catalog namespace;32 fixture cases now counted. This reporting-only change followed the final application full run; [fresh follow-up XML](modules/13-desktop-control/accounting-followup.xml) verifies it independently.

{stats}

| Module | Name | Status |
| --- | --- | --- |
{module_table}

Earliest unresolved **{summary['next_case']}**; next NOT RUN **{next_id}**. Prompt13 unresolved **JRV-13-004/JRV-13-007**. Read the next requested prompt before continuing; all37 modules are not complete.
''')
    patch='';hashes={}
    for name in (*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py'):
        old=PRE/name.replace('/','__');current=BASE/name
        patch+=''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),current.read_text(encoding='utf-8').splitlines(True),fromfile='module13-pre/'+name,tofile=name,n=2))
        hashes[name]=dict(before=hashlib.sha256(old.read_bytes()).hexdigest(),after=hashlib.sha256(current.read_bytes()).hexdigest())
    write(OUT/'source.patch',patch);write(OUT/'source-hashes.json',json.dumps(hashes,indent=2)+'\n')
    files=[dict(path='app/'+name,sha256=hashlib.sha256((BASE/name).read_bytes()).hexdigest()) for name in FILES]
    files.append(dict(path='README.md',sha256=hashlib.sha256((BASE.parent/'README.md').read_bytes()).hexdigest()))
    write(OUT/'files-changed.json',json.dumps(dict(scope='Scoped Prompt13 dirty-preimage diff, not all git changes; app/ canonical. No commit/deploy.',files=files,artifact_directory='app/artifacts/jarvis-audit/modules/13-desktop-control',shared_artifacts=['final-report.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt']),indent=2)+'\n')
    print(json.dumps(dict(module13=dict(Counter(r['status'] for r in cases)),targeted=targeted,full=full,catalog=summary['catalog_counts'],next_notrun=next_id),indent=2))


if __name__=='__main__':main()
