"""Reconcile Prompt07 from real assertions, matched fixtures and local readback."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
ROOT=BASE/'artifacts/jarvis-audit'
OUT=ROOT/'modules/07-model-routing'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module07-pre'
RUNTIME=('jarvis/cloud_policy.py','jarvis/cloud_quota.py','jarvis/groq_adapter.py',
         'jarvis/hybrid_inference.py','jarvis/obsidian_memory.py')
FILES=(*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py',
       'scripts/verification/verify_model_routing_audit.py','scripts/verification/report_model_routing_audit.py',
       'tests/test_model_routing_audit.py','tests/test_audit_result_accounting.py','README.md',
       'docs/groq-hybrid.md','docs/session-context.md','docs/system-map.md')


def write(path,text):path.write_text(text,encoding='utf-8')


def run(name):
    tree=ET.parse(OUT/name);nodes=list(tree.iter('testcase'))
    assert nodes and not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    skipped=[n for n in nodes if n.find('skipped') is not None]
    assert all('BLOCKED:' in n.find('skipped').get('message','') for n in skipped)
    return {'passed':len(nodes)-len(skipped),'blocked':len(skipped),'seconds':float(next(tree.iter('testsuite')).get('time',0))}


def main():
    focused,full=run('cases-and-contracts.xml'),run('full-regression.xml')
    for name in RUNTIME:
        assert (OUT/'full-regression.xml').stat().st_mtime >= (BASE/name).stat().st_mtime
    modules=json.loads((ROOT/'module-map.json').read_text())
    modules[6].update(status='FIXTURE COMPLETE / LIVE CLOUD BLOCKED',reason='32 catalog fixture cases executed; real cached local fallback passed. Real Groq inference, billing and entitlement acceptance not authorized/verified.',
        sources=[*RUNTIME,'jarvis/knowledge_worker.py','jarvis/brain.py','jarvis/model_selection.py',
                 'jarvis/model_performance.py','jarvis/gpu_scheduler.py','jarvis/cloud_cli.py','jarvis/diagnostics.py','docs/groq-hybrid.md'],
        test_candidates=['tests/test_model_routing_audit.py','tests/test_groq.py','tests/test_gpu_scheduler.py',
                         'tests/test_question_speed.py','tests/test_answer_stream.py','tests/test_obsidian_memory.py'])
    write(ROOT/'module-map.json',json.dumps(modules,indent=2)+'\n')
    from scripts.verification.audit_catalog import reconcile
    reconcile()
    rows=[json.loads(s) for s in (ROOT/'test-results.jsonl').read_text().splitlines()]
    cases=[r for r in rows if r['id'].startswith('JRV-07-')]
    assert len(cases)==32 and all(r['status']=='PASS' for r in cases)
    for row in cases:row['scope']='Executed isolated production-boundary fixture; fake cloud only. Separate cached local9b journey is additional component evidence, not live Groq/GUI/acoustic acceptance.'
    write(OUT/'tests.jsonl',''.join(json.dumps(r)+'\n' for r in cases));write(OUT/'remaining-case-ids.txt','')
    summary=json.loads((ROOT/'summary.json').read_text())
    benchmark=json.loads((OUT/'benchmark-summary.json').read_text())
    native=json.loads((OUT/'local-fallback-journey.json').read_text())
    assert native['status']=='PASS' and native['real_cloud_calls']==0 and native['fake_cloud_calls']==1
    ready=json.loads((PRE/'readiness-private.json').read_text(encoding='utf-8-sig'))
    assert ready['status']=='ready' and not ready.get('missing') and not ready.get('incomplete')
    write(OUT/'readiness.json',json.dumps({'date':'2026-10-15 IST','command':'python -m jarvis.launcher --check',
        'exit_code':0,'status':ready['status'],'scope':ready.get('scope'),
        'services':{k:v['status'] for k,v in ready.get('services',{}).items()}},indent=2)+'\n')
    source_patch='';hashes={}
    for name in (*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py'):
        path,old=BASE/name,PRE/Path(name).name
        assert old.is_file()
        source_patch+=''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),path.read_text(encoding='utf-8').splitlines(True),
            fromfile='module07-pre/'+name,tofile=name,n=1))
        hashes[name]={'before':hashlib.sha256(old.read_bytes()).hexdigest(),'after':hashlib.sha256(path.read_bytes()).hexdigest()}
    write(OUT/'source.patch',source_patch);write(OUT/'source-hashes.json',json.dumps(hashes,indent=2)+'\n')
    files=[{'path':'app/'+name,'sha256':hashlib.sha256((BASE/name).read_bytes()).hexdigest()} for name in FILES]
    files.append({'path':'README.md','sha256':hashlib.sha256((BASE.parent/'README.md').read_bytes()).hexdigest()})
    write(OUT/'files-changed.json',json.dumps({'scope':'Module07 scoped files; existing dirty work preserved. No commit/install/deployment.',
        'files':files,'artifacts_directory':'app/artifacts/jarvis-audit/modules/07-model-routing',
        'shared_artifacts':['final-report.md','module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt','security-findings.md']},indent=2)+'\n')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=BASE,text=True).strip()
    before,after=benchmark['route']['before_warm_gateway'],benchmark['route']['after_warm_gateway']
    bench_table='\n'.join(f'| {key} | {value["samples"]} | {value["p50_ms"]:.4f} | {value["p95_ms"]:.4f} | {value["peak_python_bytes"]} |' for key,value in benchmark['route'].items())
    matrix='''| Claim | Real entry point | Executed evidence / boundary |
| --- | --- | --- |
| Public/private/action classification | [cloud_policy.py](../../../../jarvis/cloud_policy.py):classify/screen_payload | 001–004/020–023/031; typed context, fixed minimal outbound message, common keys, negation, Unicode, size guard |
| Routing/local refusal | [hybrid_inference.py](../../../../jarvis/hybrid_inference.py):HybridGateway.decide/answer | policy/feedback/quota precede metadata wait; cold eligible metadata bounded8s; UNKNOWN/EXHAUSTED refresh expired metadata asynchronously |
| Durable accounting | [cloud_quota.py](../../../../jarvis/cloud_quota.py):QuotaGuardian | atomic reserve, stable IDs, conservative unknown/zero/malformed usage, restarts, provider request/day vs token/minute scopes |
| HTTP/streaming | [groq_adapter.py](../../../../jarvis/groq_adapter.py):GroqAdapter.complete/refresh | normalized HTTP headers, bounded protocol/deadline, no replay after partial output; fake HTTP only |
| Local fallback | [knowledge_worker.py](../../../../jarvis/knowledge_worker.py):handle_request; [model_selection.py](../../../../jarvis/model_selection.py):installed_model | existing installed fallback reused only in enabled hybrid mode; exact manual preference stays exact; actual fake429→cached9b journey |
| Task planning | [brain.py](../../../../jarvis/brain.py):BrainClient._request_once | owned local worker modules; question gateway supplies no PC tool execution authority; no real desktop mutation tested |
| Resource control | [gpu_scheduler.py](../../../../jarvis/gpu_scheduler.py):install/Lease | existing resource/cancel/refusal regressions; no new classifier or GPU model; STT/F5 shared lease gaps remain separate |
| Redaction/storage | [obsidian_memory.py](../../../../jarvis/obsidian_memory.py):SENSITIVE; conversation_memory.begin/finish | synthetic bare keys redacted in new paired records; no migration/deletion of historical user data |
| Traces/feedback/health | HybridGateway.record, PerformanceTracker, cloud_cli, diagnostics.service_status | route UUID equals reservation ID; allowed scalar fields, safe labels; HTTP success never means factual correctness or billing proof |
'''
    write(OUT/'inventory.md',f'''# Prompt07 routing, quotas and privacy — 2026-10-15 IST

**32 catalog PASS; 0 FAIL/BLOCKED/SKIPPED/NOT RUN within module07 fixture scope. Live cloud acceptance is BLOCKED separately.** No whole-system production certificate.

Repo `{commit}`, branch `{branch}`; Windows/Python{platform.python_version()}, Requests2.34.2, pytest8.4.2; Ryzen7/32GB target and RTX3050 Laptop4GB. Existing dirty work preserved; edits use app/, not its InsTAREELS alias. No account/real cloud request, personal deletion, OS-setting change, dependency/model install or deployment. One heavyweight local model probe at a time.

## Source map and claims

{matrix}
System-map, Groq hybrid/architecture, GPU priority and crash-recovery guides inspected. Groq*.py candidates resolve to groq_adapter.py plus cloud_policy/cloud_quota/hybrid_inference; no standalone model router is invented. Package defaults disable cloud, but current local config has enabled/free/confirmed flags and auto routing with live_tests_enabled=false. Those flags are user attestations; no real API key was read/printed or entitlement inferred. Config/account preferences were preserved.

## Actual checks

Existing baseline: **67 PASS**,12.08s,[XML](existing-baseline.xml). New baseline: **11 FAIL/1 PASS**,[XML](reproduced-failures.xml), plus bare-key persistence **1 FAIL**,[XML](memory-reproduced.xml). These are retained historical reproductions. The first catalog harness had three errors (minute-window exhaustion, incorrect test class, duplicate keyword argument); corrected using a fake61s advance between rounds and verified class/config helpers. A later collection command named nonexistent test_memory.py: [collection error](collection-error.xml), no assertions counted; corrected to test_obsidian_memory.py.

Final targeted/neighbor run: **{focused['passed']} PASS / {focused['blocked']} BLOCKED**, {focused['seconds']:.2f}s,[XML](cases-and-contracts.xml). Full `python -m pytest tests -q --tb=short`: **{full['passed']} PASS/{full['blocked']} explicit BLOCKED skips**, {full['seconds']:.2f}s,[XML](full-regression.xml). Runs overlap; do not sum. Launcher `python -m jarvis.launcher --check`: **ready**, [redacted check](readiness.json). Warning context remains in XML/console; no warning is treated as a failed assertion.

Targeted command: `.venv/Scripts/python.exe -m pytest tests/test_model_routing_audit.py tests/test_groq.py tests/test_conversation_context.py tests/test_question_speed.py tests/test_answer_stream.py tests/test_questions_context_audit.py tests/test_gpu_scheduler.py tests/test_obsidian_memory.py tests/test_audit_result_accounting.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/07-model-routing/cases-and-contracts.xml`.

Five-way mixed public/private requests repeated20 times assert40 expected fake cloud calls and zero private crossover; fake clocks avoid exceeding minute budgets. No uncertain external write or tool action is performed. Stable reservation IDs survive crashes; partial output never triggers duplicate inference. [Exact case ledger](tests.jsonl).

## Matched benchmark and decision

Same machine/input, simulated20ms metadata readiness, exhausted quota. Five cold gateway samples/build include feedback SQLite initialization;20 warm samples/build reuse gateway. Old route code imports the common current policy: this A/B isolates route ordering on an unchanged public question, not an entire historical dependency build. Separate classification compares saved pre-change/current policies over500 identical benign/public/private requests per version. Baseline correctness is asserted in both builds; new key-format acceptance has its own failing-before/passing-after tests.

| Build/mode | Samples | p50 ms | p95 ms | Peak traced Python bytes |
| --- | ---: | ---: | ---: | ---: |
{bench_table}

[50 route samples](benchmarks.csv), [classification/summary](benchmark-summary.json). Retain early refusal: matching local result, fewer blocking readiness calls, warm p95 **{before['p95_ms']:.4f}→{after['p95_ms']:.4f}ms**. Warm traced allocation increased **{before['peak_python_bytes']}→{after['peak_python_bytes']} bytes**, including UUID/background-refresh Mock accounting; no RAM reduction claimed. No process peak RSS/VRAM, real cloud TTFT, first audio, broad semantic precision or two-second target measured here. Deterministic filtering remains fast on these fixtures; a new tiny router adds no demonstrated privacy/accuracy benefit and is not installed.

## Applicable journey and remaining gaps

Actual `handle_request`: fake loopback Groq429 → full conservative reservation retained → existing installed-model fallback for deliberately missing model → real cached local9b answer in **{native['seconds']:.3f}s**. [Reply and quota readback](local-fallback-journey.json). Exactly one fake cloud call, zero real cloud calls, no external write. This verifies fallback plumbing and a coherent authored example, not provider billing, model access, global accuracy or voice latency.

Live Groq/free entitlement, organization peers' consumption, paid-account detection, exact provider limits and real throughput remain **BLOCKED** by absent live-test opt-in and independently verified entitlement. No credentials or account changes were attempted. Secret patterns remain heuristic; multilingual/unknown wording stays local but universal sensitive-data detection is not certified. Current supported Groq model is preview. Prior acoustic/shared STT–F5 acceptance blockers remain.

[Failures](failures.md), [changes](changes.md), [compatibility/upstream URLs](compatibility.md), [rollback/resume](rollback.md), [exact files](files-changed.json), [scoped patch](source.patch), [source hashes](source-hashes.json).
''')
    write(OUT/'failures.md','''# Failures and disposition — 2026-10-15 IST

Reproduced 11/12 initial regression variants failing: five bare key formats qualified as public; exhausted quota waited for metadata; mixed-case Retry-After used the default delay; zero/malformed usage refunded reservations; unsafe model metadata persisted. A separate real isolated SQLite readback showed bare keys saved in new conversation pairs. All now have executed assertions. These baseline failures are retained in reproduced-failures.xml and memory-reproduced.xml.

Additional hardened boundaries: response IDs and estimate metadata cannot store credential-shaped/arbitrary objects; route/reservation UUID correlation and allowed metadata fields are asserted. Existing ledger uncertainty, partial-stream non-replay and offline/manual preferences remain tested.

Harness errors retained in catalog-first.xml: 20 rounds exceeded the real fixture minute budget, a GPU test class name was incorrect, and a config helper duplicated a keyword. Corrected the harness (fake minute clock, real class, dictionary override); no product quota was increased. collection-error.xml records a nonexistent memory test filename; corrected invocation executes real assertions. Reporter import/paths and actual commands are reproducible, no collection result counts as a pass.

Unresolved live acceptance: no Groq inference/account mutation authorized by this audit, live_tests_enabled=false, entitlement/billing not independently verified, no org-peer spending visibility, no live web/GUI/microphone-to-speaker journey or shared STT/F5 contention run. New regex coverage is not universal secret detection. Existing historical private records were preserved rather than silently edited. Ollama upgrade/Python lifecycle work remains separately unvalidated.
''')
    write(OUT/'changes.md','''# Changes and keep/revert rationale — 2026-10-15 IST

Keep early policy/manual preference/utility/feedback/quota refusal before metadata waiting. UNKNOWN/EXHAUSTED can refresh expired time metadata asynchronously, preserving clock recovery without inference probes. Metadata refresh honors valid cached availability. Known budget refusal therefore returns locally without the previous metadata delay; authoritative reserve still checks the shared ledger under BEGIN IMMEDIATE. No sticky automatic offline mode or retry loop introduced.

Normalize response headers before backoff/accounting. Retain the reservation when total usage is zero or a supplied usage field has a bad type; zero can be legitimate provider nonbilling, but uncertain charging deliberately overestimates. Optional estimate fields accept bounded integers. Persist only safe response IDs.

Share common credential-key patterns between outbound screening and new conversation/Obsidian redaction. Keep earlier sensitive-word behavior without broadening the memory matcher to redact every ordinary email address. No historical-record migration. Route UUIDs match reservation IDs and preserve supplied stable recovery IDs; allowed scalar route metadata sanitizes model/error labels.

Matched route benchmark proves latency gain for exhausted fixtures; warm traced allocations increase, so no memory claim. Policy classification changes are correctness improvements; tiny timing differences are not a meaningful speedup claim. Keep deterministic filters instead of adding an unvalidated tiny model, paid requirement or download. Existing local inference keep_alive/warmness/GPU policy and manual model preferences remain intact. No new service/dependency/permission, UI layout or screenshot change; feature flags remain existing cloud/selector controls.
''')
    write(OUT/'compatibility.md','''# Compatibility and official sources — 2026-10-15 IST

Installed Requests2.34.2 matches the [official latest release](https://github.com/psf/requests/releases/tag/v2.34.2), dated14May2026. Release excerpt does not state Python compatibility/security fixes; installed-runtime execution on Python3.10.6 is the compatibility evidence, not an invented upstream promise. No dependency installation. [Release check](requests-release.json).

Official [Groq rate-limit documentation](https://console.groq.com/docs/rate-limits) distinguishes organization-level limits, daily-request versus minute-token response headers, and Retry-After seconds on429. Applications can also face separate input/output token limits. Local ceilings remain conservative application settings, not account entitlements or exact free quotas. No publication date stated. The reviewed [Qwen model page](https://console.groq.com/docs/model/qwen/qwen3.8-27b) still marks it preview; live availability was not tested. [Source checks](upstream-checks.json).

Ollama local0.40.0 completed the cached9b fallback journey. Same-day module06 [release check](../06-questions-context/upstream-checks.json) identified official0.40.4 dated12Oct2026; runtime is not latest. No install/download authorized/performed; no compatibility claim for an untested newer runtime. Python3.10 support-window concern from the prior audit remains. Existing Requests/Ollama APIs passed the local/fixture scope; no new SDK or dependency needed. Upstream code was not downloaded/executed.
''')
    write(OUT/'rollback.md','''# Scoped rollback and deterministic resume

No new commit. Do not git-reset/checkout entire shared files: prior user work is dirty. If rollback is needed, Stop Jarvis normally, inspect source.patch and source-hashes.json, reverse only module07 hunks, and reconcile documentation/manifest. Local preimages are .jarvis-runtime/jarvis-audit/module07-pre/. The patch uses one context line to avoid unrelated personal configuration. Preserve subsequent edits, quota SQLite/history, conversations, credentials and personal files; never clear reservations to restore availability.

Re-run the exact targeted command in inventory.md, then `python -m pytest tests -q --tb=short` and `python -m jarvis.launcher --check`. `python scripts/verification/verify_model_routing_audit.py` runs matched CPU fixtures using preserved preimages. `--local-journey` additionally runs fake loopback Groq429 and installed cached local9b through the real worker function, without live cloud/accounts/GUI/speech; run no other heavyweight GPU test concurrently. No missing model is downloaded. `python scripts/verification/report_model_routing_audit.py` publishes only successful completed XML/readiness/route evidence.

Module07 has no incomplete fixture case ID. Next unexecuted module/case:08/JRV-08-001. Earliest global unresolved remains JRV-04-001; ../../remaining-case-ids.txt enumerates every remaining ID. Live Groq entitlement/billing and inference are separately blocked; do not enable them from test code or treat local flags as provider proof.
''')
    archive=ROOT/'final-report-before-module07.md'
    if not archive.exists():write(archive,(ROOT/'final-report.md').read_text(encoding='utf-8'))
    table='\n'.join(f'| {m["number"]:02d} | {m["module"]} | {m["status"]} |' for m in modules)
    write(ROOT/'final-report.md',f'''# Jarvis audit through Prompt07 — 2026-10-15 IST

**Prompt07:32 fixture catalog PASS,0 FAIL/BLOCKED/SKIPPED/NOT RUN. Live cloud acceptance remains BLOCKED.** Targeted **{focused['passed']} PASS**; full regression **{full['passed']} PASS/{full['blocked']} existing explicit BLOCKED skips**, {full['seconds']:.2f}s. [Targeted XML](modules/07-model-routing/cases-and-contracts.xml), [full XML](modules/07-model-routing/full-regression.xml); overlapping scopes, not additive. Launcher **ready**, [redacted check](modules/07-model-routing/readiness.json). Whole-system production acceptance remains open.

Repo `{commit}`, branch `{branch}`; Windows/Python{platform.python_version()}, Requests2.34.2, Ryzen7/32GB target and RTX3050 Laptop4GB. Existing dirty work preserved; no commit/deploy, installation/download, real cloud/account write, personal delete or OS-setting change. One heavyweight cached local probe at a time. [Source-map-to-code evidence matrix and active-policy limits](modules/07-model-routing/inventory.md), [exact changed files](modules/07-model-routing/files-changed.json), [scoped preimage diff](modules/07-model-routing/source.patch).

Repairs cover unrecognized key formats and new-record redaction, quota refusal before metadata waits, HTTP header casing, conservative zero/malformed usage and safe routing metadata with UUID/reservation correlation. [Reproduced failures](modules/07-model-routing/failures.md), [keep/revert decisions](modules/07-model-routing/changes.md), [risk/rollback](modules/07-model-routing/rollback.md).

Identical exhausted-quota/20ms-simulated-metadata fixtures,20warm/5cold per build: warm p50/p95 **{before['p50_ms']:.4f}/{before['p95_ms']:.4f}→{after['p50_ms']:.4f}/{after['p95_ms']:.4f}ms**. [All50 samples](modules/07-model-routing/benchmarks.csv). Warm traced allocation increased **{before['peak_python_bytes']}→{after['peak_python_bytes']} bytes**; no RSS/VRAM/throughput gain claimed. Deterministic classification remains fast in the small identical fixture; no unvalidated model router added.

Actual real worker-function journey: loopback fakeGroq429 → retained uncertain quota charge → verified installed fallback → cached local9b answer in **{native['seconds']:.3f}s**, [answer/readback](modules/07-model-routing/local-fallback-journey.json). Zero real cloud calls or account actions. Live Groq entitlement, billing, org-peer consumption, preview-model availability, throughput and two-second acoustic acceptance remain unverified/blocked. Regex matching is heuristic and old private records are preserved. Requests2.34.2 matches official14May2026 release; local Ollama0.40.0 predates official0.40.4 (12Oct2026), without upgrade/install. [Official sources, dates and compatibility](modules/07-model-routing/compatibility.md).

## Catalog and enumerated modules

1184 unique IDs: **{summary['catalog_counts']}**. [Every case/assertion](test-results.jsonl), [tier/category statistics](summary.json), [module07 cases](modules/07-model-routing/tests.jsonl), [exact remaining IDs](remaining-case-ids.txt). Earlier module01–06 baselines, metrics and live blockers remain in [preserved prior report](final-report-before-module07.md); no unrelated regression pass certifies a catalog case.

| Module | Name | Status |
| --- | --- | --- |
{table}

Next unexecuted **08/JRV-08-001**; earliest unresolved global **JRV-04-001**. No module07 fixture case remains. Live cloud prerequisites and previous acoustic/shared STT–F5 blockers remain open. No universal correctness, free-billing guarantee, two-second voice promise or production release certification is claimed.
''')
    security=ROOT/'security-findings.md';prior=security.read_text(encoding='utf-8') if security.exists() else ''
    if '## Prompt07 —' not in prior:
        write(security,prior+'\n## Prompt07 — 2026-10-15 IST\n\nCommon bare-key outbound and new-record redaction, exhausted-quota wait, mixed-case backoff, zero/malformed usage and unsafe model metadata repaired with failing-before/passing-after assertions. Route UUIDs correlate reservations. Live cloud entitlement/billing/inference remains blocked; regex matching is heuristic and historical records are preserved. See modules/07-model-routing/inventory.md.\n')
    print(json.dumps({'targeted':focused,'full':full,'module07':dict(Counter(r['status'] for r in cases)),
        'catalog':summary['catalog_counts'],'readiness':ready['status']}))


if __name__=='__main__':main()
