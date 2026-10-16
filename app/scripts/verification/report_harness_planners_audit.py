"""Publish Prompt 30 executed evidence and preserve incomplete optional-model contracts."""
from collections import Counter
from contextlib import redirect_stdout
import difflib,io,json,re,sys
from pathlib import Path
import xml.etree.ElementTree as ET
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
from scripts.verification import report_whatsapp_audit as common
from tests.test_harness_planners_audit import GATES
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/30-harness-planners';PRE=BASE/'.jarvis-runtime/jarvis-audit/module30-pre'
common.MOD=MOD;read,sha,write,stats=common.read,common.sha,common.write,common.stats

def marker(path,text):
    s=path.read_text(encoding='utf-8');s=re.sub(r'\n<!-- prompt30-audit -->.*?<!-- /prompt30-audit -->\n','',s,flags=re.S)
    first,rest=s.split('\n',1);path.write_text(first+'\n\n<!-- prompt30-audit -->\n'+text+'\n<!-- /prompt30-audit -->\n'+rest,encoding='utf-8')

def main():
    from scripts.verification import audit_catalog
    from jarvis.harness import SDK_VERSION
    from jarvis.hermes import REVISION
    baseline,target,full=(stats(n) for n in ('baseline.xml','cases-and-contracts.xml','full-regression.xml'))
    assert baseline['PASS']==49 and target['PASS']==236 and target['SKIPPED']==10
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0
    frozen=read(MOD/'full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    bench,env,ready,optional,config=(read(MOD/n) for n in ('benchmark-summary.json','environment.json','readiness.json','optional-runtime.json','configured-routes.json'))
    assert bench['equivalent'] and ready['status']=='ready'
    assert config['hermes']['enabled'] is False and config['harness']['enabled'] is True
    current=read(BASE/'config/config.json')['brain'];assert all(current.get(k)==v for k,v in config.items())
    modules=read(OUT/'module-map.json');modules[29].update(sources=['jarvis/brain.py','jarvis/hermes.py','jarvis/harness.py','jarvis/harness_worker.py','jarvis/brain_worker.py','jarvis/model_selection.py','jarvis/planner_settings.py','jarvis/hermes_ollama.py','jarvis/hermes_skills.py','jarvis/agent_session.py','jarvis/tools.py','docs/hermes-agent.md','docs/deepseek-harness.md','docs/hermes-skills-and-comparison.md'],test_candidates=['tests/test_harness_planners_audit.py','tests/test_hermes.py','tests/test_harness.py','tests/test_model_selection.py','tests/test_hermes_skills.py'],status='PARTIAL',reason='22 catalog fixture PASS / 10 incomplete acceptance contracts; no live model outcome comparison or production privacy/trace certification')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    with redirect_stdout(io.StringIO()):audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()];cases=[r for r in catalog if r['id'].startswith('JRV-30-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':22,'BLOCKED':10}
    assert {int(r['id'][-3:]) for r in cases if r['status']=='BLOCKED'}==set(GATES)
    summary=read(OUT/'summary.json');write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases));write('remaining-case-ids.txt','\n'.join(f'JRV-30-{n:03}' for n in GATES))
    gates='\n'.join(f'- **JRV-30-{n:03} BLOCKED:** {reason}' for n,reason in GATES.items())
    scope=('Deterministic planner/provider mocks; actual scoped reads of synthetic source; hash-checked public Hermes guide reads; five concurrent fixture requests × 20 rounds; actual owned Python JSONL worker echo, crash/restart and 100 response-isolation checks. '
           'No optional planner model inference, generated script installation, paid API, real desktop action, account operation, private recording or GPU workload ran. Model and SDK proposals remain distinct from real action or outcome proof. Launcher readiness may boot its already-installed owned check-only SDK transport; it is not a model accuracy test.')
    matrix='''| Documented claim | Source/entry and executed evidence | Limit |
| --- | --- | --- |
| Planner selection | BrainClient.request/_request → HarnessClient before HermesClient for plan/replan and scoped development code_plan | next_step, ordinary code_plan, code_edit, choose, decide and verify retain native routes; enabled Harness is not proof every task uses it |
| Hermes opt-in and guides | hermes.settings/validate_proposal + HermesSkills manifest/hashes | Disabled planner yields no HermesClient calls; 210 public guides remain discoverable/readable within explicit budgets; no helper script is executed |
| Trust boundary | validate_proposal → validate_plan → ToolRegistry; validate_agent_response → AgentSession | Unknown/unadvertised tools, duplicate/failed/completed action keys and invalid read calls refuse before dispatch; all execution stays with Jarvis |
| Configuration | planner_settings.settings → client and Harness worker; model_selection.required_models | Strict boolean flags, finite deadlines 10–180 Hermes / 10–300 Harness, bounded model names and recognized selector; enabled Harness model now included in readiness requirements |
| Laya | BrainClient._request_once choose + brain_worker.Models.predict | Missing checkpoint asks clarification without launch; missing import/file returns unavailable; unrelated native inference no longer requires Laya checkpoint. No new ranking-accuracy test |
| Concurrency and shutdown | Per-client request RLock; cancellable wait; bounded stdio reader | One response queue owner per client; eight pending messages and 8M-character protocol cap; dead worker detected even if EOF sentinel was dropped under backpressure. Separate clients lack shared task lease |
| Runtime disable | Effective cancel callback and flag recheck before returning optional result | In-flight disabled result discarded/cancelled; next explicit request takes current route; no new fallback executor |
| Recovery | Existing bounded one inference retry; original _on_code guard; TaskState pending uncertainty | Owned worker crash retries only inference; simulated uncertain external effect remains pending/paused. No external effect is executed by the fixture worker |
| Prompt/data boundary | Restricted Harness agent catalogue, profile IDs, structured parse, real readback | Malicious source remains data in tested read session; forged approval cannot expand read-only scope. Full cloud/log/semantic-accuracy oracle remains incomplete |
| Upstream isolation | harness_worker ACTIVE profile + OwnedJob; Hermes submit_jarvis_plan only; local Ollama adapters | Installed check-only readiness is narrower than model/SDK end-to-end privacy, trace and host-environment confinement |'''
    graph='''```mermaid
flowchart LR
    Input[Jarvis request] --> Route{Operation and opt-in flags}
    Route -->|plan/replan/development plan| Harness[Harness priority when enabled]
    Route -->|plan/replan if Harness off| Hermes[Hermes when enabled]
    Route -->|other operations| Native[Native brain / Laya]
    Harness --> Proposal[Untrusted structured proposal]
    Hermes --> Proposal
    Native --> Proposal
    Proposal --> Validate[Caller validation and current tool catalogue]
    Validate --> Registry[Jarvis registry / approvals / checkpoints]
    Registry --> Readback[Independent observation]
```'''
    metric=f"For 50 replan-schema copies per batch, warm p50/p95 {bench['before']['p50_ms']:.4f}/{bench['before']['p95_ms']:.4f} → {bench['after']['p50_ms']:.4f}/{bench['after']['p95_ms']:.4f} ms; peak temporary Python allocation {bench['before']['peak_python_bytes']} → {bench['after']['peak_python_bytes']} bytes."
    fixes='''- Serialize each client's request/response lifecycle using a reentrant lock with cancellable waits; keep one authoritative stdio response consumer. This is not a cross-client TaskState lease.
- Bound JSON protocol input before launch, cap responses, buffer at most eight messages, validate outer envelopes/progress, classify dead workers promptly even with a missing EOF signal, and reject late cancelled results.
- Share typed optional planner settings; reject malformed objects, strings-as-booleans, nonfinite/bool/out-of-range deadlines, invalid model text and unknown selector identifiers. Include enabled Harness model/default in required local model inventory.
- Validate nonstring/unhashable tool actions and malformed history/budgets; reject exact duplicate, completed and failed action keys before execution. Plan responses cannot inject approval/completion metadata. This rejects a repeated key rather than silently removing a potentially meaningful step; ambiguous workflows must replan with fresh state.
- Validate read-only Harness final/call fields and exact call arguments against both the advertised catalogue and AgentSession's read-only tool set. No upstream executor is exposed.
- In-memory runtime opt-out joins the effective cancellation predicate; discard optional results after disable and preserve native routing on the next explicit request. This does not add a disk-config watcher; documented file edits still require restart.
- Missing Laya checkpoint returns an explicit clarification; missing package/file returns unavailable. Validate candidate identities and selected keys; keep the independent decision/permission gate. Other native inference no longer depends on Laya model presence.
- Tighten Harness composition shape/budget checks. Replace three generic deep copies with one JSON encoding plus independent C-backed decoded branches; no mutable branch sharing and no cache of user context.
'''
    decisions='\n\nKeep the schema-copy CPU optimization with an explicit memory tradeoff. '+metric+' The additional 58,680 bytes are bounded temporary allocation on a 32 GB host; no VRAM claim. All returned schemas match the saved implementation exactly, and branches/input remain independently mutable. Five initial+20 warm batches, not cold planner processes. Do not enable a harness based on this microbenchmark: it has no live outcome-accuracy measurement. Current planner flags/models/checkpoints and dependency pins remain unchanged.\n\n'
    write('inventory.md','# Prompt 30 optional-planner audit — 2026-10-16 IST\n\n**PARTIAL: 22 catalog fixture PASS / 10 BLOCKED.**\n\n'+scope+'\n\n'+matrix+'\n\n'+graph+'\n\n'+gates+'\n\n[Report](../../final-report.md) · [Case assertions](cases-and-contracts.xml) · [Diff](source.patch)')
    write('failures.md','# Reproductions and repairs\n\nBaseline 49 passed. Initial 12 failures reproduced duplicate acceptance, unhashable actions, eight invalid config/backend combinations, overlapping shared-client requests and an unadvertised read-only tool call. [Initial assertions](reproduction.xml), [log](reproduction.txt). First repaired subset 61 passed; native/context/inference expansion 138 passed. Expanded fixture had one guide read-budget failure (oversized guide was correctly refused); fixture now requests the explicit 60,000-byte maximum. Subsequent fixture mistakenly called nonexistent AgentSession.turn instead of run, then a byte-exact source assertion exposed Windows CRLF writing; write_bytes now preserves the exact synthetic LF payload, and parsed durable events are checked for source-body absence. These were fixture errors, not excuses to weaken product assertions.\n\nAn EOF/backpressure probe reproduced a dead worker being classified as timeout when no EOF sentinel reached the queue. It now detects process exit after an empty queue, with a dedicated regression. A superseded full run was stopped around 15 percent before the fix; its log/hashes are retained and excluded from completed evidence. Final focused 236 PASS / 10 explicit blocked skips. Full final run and frozen-source verification are recorded in final-report.md.\n\n'+gates)
    write('compatibility.md','''# Official sources checked — 2026-10-16 IST

[Hermes latest official release](https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.2) is v0.22.2, published 2026-10-15T08:21:32Z. The local source remains the reviewed cbc569e23cb045b58b067f37cf5514feb44e0828 (git HEAD readback matches); distribution metadata reports 0.0.0, which is not useful release identity. Optional Python 3.14.7 remains unchanged. No upgrade or compatibility claim for v0.22.2 follows from these fixtures. Its existing high-context planning costs and historical timeouts remain documented in the preserved comparison guide.

[Official PyPI SDK metadata](https://pypi.org/pypi/deepseek-harness-sdk/json) still lists 0.1.5rc1, wheel uploaded 2026-09-10T05:55:48. Installed SDK and bundled runtime both 0.1.5rc1 match the pin. GitHub's /releases/latest endpoint returned404, but [official tags](https://github.com/deepseek-ai/deepseek-harness/tags) expose newer source prereleases: dsh-v0.2.1-alpha.5 at 1517a4dbca0a2789ff1d41ba439600f8547d23fa, [commit dated 2026-10-16T11:02:34Z](https://github.com/deepseek-ai/deepseek-harness/commit/1517a4dbca0a2789ff1d41ba439600f8547d23fa). Repository tags are not the published Python SDK/runtime API. Retain the matched installed pair and restricted inference profile; no upgrade/install ran. Historical reviewed source 639ed015397290b3745d163aafe02ffee4aa3f84 remains historical.

[Official Laya package metadata](https://pypi.org/pypi/laya/json) lists 0.4.8, uploaded 2026-10-15; local brain environment remains 0.3.5 / transformers 4.57.6. [Model metadata](https://huggingface.co/api/models/convaiinnovations/laya) reports main 7b928d828b7b0e022f929d9bd2e44165aa270148, modified 2026-10-03. Jarvis keeps reviewed English checkpoint 1c5edc17a7acd8701df6fc341c0d179f1c62c982. [Current model card](https://huggingface.co/convaiinnovations/laya) describes a Router that may download checkpoints on first use; it is not assumed equivalent to the installed fixed-local-checkpoint adapter. No model, alternate language checkpoint or package was downloaded. No GPU/host-memory superiority claim.

Firecrawl retrieved public primary sources only; upstream-checks.json preserves status/cache provenance and release dates. Optional-runtime.json records read-only package metadata. Current installed integration stays opt-in with native permissions and fallback/clarification routes. Keep/revert decisions are based on executed schema and transport tests, not external benchmark marketing. No paid API or new Python dependency is required.
''')
    write('rollback.md','# Scoped rollback and deterministic resume\n\nPreimages are in `.jarvis-runtime/jarvis-audit/module30-pre/`, application-relative paths flattened with __; root-README.md denotes the parent README. Check source-hashes.json before restoration. Merge specific source.patch hunks if files changed later; never reset this dirty checkout, erase user work or restore unrelated module changes. New files are listed in files-changed.json. Preserve all task/session/effect checkpoints; rolling back a planner is not permission to replay an uncertain action. No dependency, model, personal config or service installation needs reversal.\n\nResume at JRV-30-007 (oldest module blocker), followed by exact IDs in remaining-case-ids.txt. Build a full SDK/private-data oracle and cross-client generation lease, then matched live outcome/latency, context-overflow, semantic-negation, stale-target, resource and trace tests against authorized owned fixtures. Keep Hermes disabled until a representative outcome evaluation justifies opting in. Follow commands.md, freeze final sources, run focused/full/readiness, reconcile and verify artifacts. Actual account/desktop writes, installations and model downloads retain separate approval.')
    write('commands.md','''# Reproduce from app/ in PowerShell

Tests use synthetic files, mocked model responses and source-owned protocol workers. Ordinary Windows fixture permissions were used for atomic TaskState files and owned process tests; there are no real sends, installs or desktop actions.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_hermes.py tests/test_harness.py tests/test_model_selection.py tests/test_hermes_skills.py -q --junitxml=artifacts/jarvis-audit/modules/30-harness-planners/baseline.xml
.venv/Scripts/python.exe -m pytest tests/test_harness_planners_audit.py tests/test_hermes.py tests/test_harness.py tests/test_model_selection.py tests/test_hermes_skills.py tests/test_brain.py tests/test_conversation_context.py tests/test_inference_limits.py tests/test_agent_runtime.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/30-harness-planners/cases-and-contracts.xml
.venv/Scripts/python.exe scripts/verification/verify_harness_planners_audit.py
.venv/Scripts/python.exe -c "from pathlib import Path; import scripts.verification.verify_whatsapp_audit as v; v.OUT=Path('artifacts/jarvis-audit/modules/30-harness-planners'); v.freeze()"
.venv/Scripts/python.exe -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/30-harness-planners/full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe scripts/verification/report_harness_planners_audit.py
.venv/Scripts/python.exe scripts/verification/verify_harness_planners_artifacts.py
```

Capture corresponding stdout/stderr logs/readiness.json. Preserve historical baseline/reproduction artifacts when resuming; do not overwrite them as current proof. The benchmark requires the saved preimage; --baseline was run before the schema-copy upgrade. Each timing batch checks50 identical schema outputs. Initial samples are not cold SDK/model requests. Optional runtime metadata inspection used importlib.metadata, not model loading. Never interpret fixture PASS as live model/desktop accuracy.
''')
    write('source-inventory.json',json.dumps({'reviewed_hermes_revision':REVISION,'sdk_version':SDK_VERSION,'configured_routes':config,'guides':210,'entry_chain':['BrainClient.request','BrainClient._request','HarnessClient/HermesClient/native worker','caller validators','ToolRegistry/AgentSession'],'missing_acceptance_case_ids':[f'JRV-30-{n:03}' for n in GATES]},indent=2))
    marker(BASE/'README.md',f'''**2026-10-16 — Prompt 30 optional-planner audit: PARTIAL.** {target['PASS']} focused assertions passed; 10 explicit catalog blockers. Full regression {full['PASS']} passed /{full['SKIPPED']} skipped / 0 failures; launcher ready. Shared-client serialization, bounded protocol/backpressure, strict optional settings, duplicate/unknown/read-only proposal checks and safe Laya degradation added. {metric} This is schema-copy CPU time with higher temporary allocation, not model/voice latency. Planner flags, model pins and dependencies unchanged. [Evidence and limits](artifacts/jarvis-audit/modules/30-harness-planners/inventory.md) · [Audit report](artifacts/jarvis-audit/final-report.md).''')
    marker(BASE.parent/'README.md','''**2026-10-16 — Optional planner audit (Prompt 30): partial.** Hermes/Harness proposal and worker boundaries now have stronger configuration, concurrency, cancellation and replay checks; Laya can ask safely when unavailable. Live accuracy/privacy/resource/trace acceptance remains incomplete. [Application details](app/README.md) · [Audit evidence](app/artifacts/jarvis-audit/final-report.md).''')
    for name in ('hermes-agent.md','deepseek-harness.md','hermes-skills-and-comparison.md'):
        path=BASE/'docs'/name;text=path.read_text(encoding='utf-8');text=re.sub(r'\n## Prompt 30 audit — 2026-10-16.*','',text,flags=re.S)
        text+='\n## Prompt 30 audit — 2026-10-16\n\n'+fixes+'\n'+metric+'\n\nTemporary allocation rises by 58,680 bytes in the measured batch peak; this bounded tradeoff is retained for CPU overhead, without claiming faster model or speech output. Existing dated live results above stay historical. Current Hermes planner is off, Harness remains opt-in, and next_step/native coding/decision routes retain their existing selection. All 210 public Hermes guide references remain independent of planner enablement. No package/model/profile preference was installed or changed. Strict timeout validation now rejects values outside the documented ranges instead of coercing them. Exact duplicate keys are rejected for replanning, not silently removed. Separate-client task leases, full secret/log isolation and matched live outcome comparisons remain incomplete. [Current evidence and 10 blockers](../artifacts/jarvis-audit/modules/30-harness-planners/inventory.md).\n'
        path.write_text(text,encoding='utf-8')
    changed=[];pairs=[];patches=[]
    for old in sorted(PRE.iterdir()):
        if not old.is_file():continue
        rel='../README.md' if old.name=='root-README.md' else old.name.replace('__','/');now=BASE/rel
        if sha(old)==sha(now):continue
        changed.append(rel);pairs.append({'path':rel,'before':sha(old),'after':sha(now)})
        patches.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),now.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
    for rel in ['jarvis/planner_settings.py','tests/test_harness_planners_audit.py','scripts/verification/verify_harness_planners_audit.py','scripts/verification/report_harness_planners_audit.py','scripts/verification/verify_harness_planners_artifacts.py']:
        changed.append(rel);patches.extend(difflib.unified_diff([], (BASE/rel).read_text(encoding='utf-8').splitlines(True),fromfile='/dev/null',tofile='after/'+rel))
    write('source.patch',''.join(patches));write('source-hashes.json',json.dumps(pairs,indent=2));write('files-changed.json',json.dumps([{'path':p,'sha256':sha(BASE/p)} for p in changed],indent=2));write('changes.md','# Prompt 30 changes and keep/revert decisions\n\n'+fixes+decisions+'\n'.join('- `'+p+'`' for p in changed)+'\n\nGenerated module/global artifacts are listed in generated-files.json. No commit/reset or unrelated cleanup occurred. Existing dirty work and historical reports are preserved.')
    write('full-regression-skip-reasons.json',json.dumps([{'node':n.get('classname','')+'::'+n.get('name',''),'reason':n.find('skipped').get('message','')} for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if n.find('skipped') is not None],indent=2))
    table='| Module/evidence | Status | PASS | BLOCKED | NOT RUN |\n| --- | --- | ---: | ---: | ---: |\n'
    for m in modules:
        c=Counter(r['status'] for r in catalog if int(r['id'][4:6])==m['number']);label=f"{m['number']:02}-{m['module']}";link=f'modules/{label}/inventory.md'
        if (OUT/link).is_file():label=f'[{label}]({link})'
        table+=f"| {label} | {m['status']} | {c['PASS']} | {c['BLOCKED']} | {c['NOT RUN']} |\n"
    report=f'''# Jarvis audit — Prompt 30, 2026-10-16 IST

**PARTIAL: 22 optional-planner catalog fixture PASS / 10 BLOCKED; no production or live model accuracy certification.**

Preserved dirty branch audit/12-tool-registry, commit 9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6, canonical app/. Main Python {env['python'].split()[0]}, {env['platform']}, RAM {env['ram_bytes']} bytes. Target Ryzen 7 5800H / RTX 3050 Laptop 4 GB from the [historical hardware census](../../docs/MODEL_AUDIT.md); no GPU workload. [Current environment](modules/30-harness-planners/environment.json), [optional package/Python metadata](modules/30-harness-planners/optional-runtime.json), [actual configured routes](modules/30-harness-planners/configured-routes.json).

{scope}

## Source-map-to-code evidence

{matrix}

{graph}

## Actual test commands and outcomes

Baseline **49 PASS**. Twelve initial failing assertions reproduced and repaired; later EOF/backpressure failure repaired. Focused **{target['PASS']} PASS /{target['SKIPPED']} explicit blocked skips / 0 FAIL**. Final full tests-directory suite **{full['PASS']} PASS /{full['SKIPPED']} SKIPPED / 0 FAIL**, JUnit suite duration {full['seconds']:.3f}s; console wall time and warnings are in the saved log. Launcher dependency/configuration readiness **{ready['status']}**. All {len(frozen)} frozen runtime/test files match after the full run. The superseded interrupted run is not counted.

{metric} [Raw samples](modules/30-harness-planners/benchmarks.csv), [pre-upgrade baseline](modules/30-harness-planners/baseline-benchmarks.csv), [summary/scope](modules/30-harness-planners/benchmark-summary.json). Keep CPU overhead improvement with 58,680 bytes higher temporary peak allocation; no shared mutable branches or private-context cache. These 50-copy batches do not establish planner inference speed, tool-selection accuracy, cold SDK/RSS/VRAM, TTFT or first-audio performance. No optional planner was enabled based on them.

[Focused XML](modules/30-harness-planners/cases-and-contracts.xml) · [full XML](modules/30-harness-planners/full-regression.xml) · [full log](modules/30-harness-planners/full-regression.log) · [source freeze](modules/30-harness-planners/full-start-source-hashes.json) · [failures](modules/30-harness-planners/failures.md) · [commands](modules/30-harness-planners/commands.md) · [changes](modules/30-harness-planners/changes.md) · [exact files](modules/30-harness-planners/files-changed.json) · [diff](modules/30-harness-planners/source.patch) · [official upstream URLs/dates](modules/30-harness-planners/compatibility.md) · [retrieval provenance](modules/30-harness-planners/upstream-checks.json) · [rollback](modules/30-harness-planners/rollback.md).

## Exact 1,184-case accounting

All 1,184 unique case IDs retained: **{json.dumps(summary['catalog_counts'])}**. All 32 Prompt 30 IDs have executed assertions or concrete blockers; a narrow fixture pass cannot override a missing full-case contract. Prior modules remain dated evidence, not new live checks.

{table}

Tier totals:
```json
{json.dumps(summary['by_tier'],indent=2)}
```
Category totals:
```json
{json.dumps(summary['by_category'],indent=2)}
```

## Remaining contracts and risk

{gates}

Per-client serialization does not grant task authority across independent clients. Prompt/output validation does not prove semantic intent, private-data non-disclosure, freshness or action success. Optional workers remain trusted host programs; local event logs/profile environments need full privacy/retention work. Eight queued text messages and an 8M-character cap are bounded backpressure, not a measured host-memory admission policy. There is no automatic switch to paid/cloud inference and no external-action retry added. Start/Stop/bootstrap/recovery/manifest interfaces remain compatible; no dependency or new service was declared. Shared source/profile/model upgrades need separately reviewed compatibility and resource tests. Existing historical slow/failed model comparisons remain valid context; native routes remain available.

## Deterministic resume

Next incomplete module case **JRV-30-007**; next untouched module **31/JRV-31-001**; oldest global unresolved **{summary['next_case']}**. [Module IDs](modules/30-harness-planners/remaining-case-ids.txt), [all remaining IDs](remaining-case-ids.txt). Implement privacy/cloud/log oracles, cross-client task-generation ownership, context-overflow recovery, matched live accuracy/latency, semantic negation/stale state and resource/trace acceptance. Follow commands.md, freeze, rerun focused/full/readiness, reconcile and verify. Never replay uncertain external actions. No installation or live account/system write is authorized by a fixture result. [Prior Prompt29 report](final-report-before-module30.md) preserves earlier metrics and limits.
'''
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    generated={p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file()};generated.update((OUT/n).relative_to(BASE).as_posix() for n in ('final-report.md','final-report-before-module30.md','module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt'));generated.update((MOD/n).relative_to(BASE).as_posix() for n in ('generated-files.json','artifact-verification.json'));write('generated-files.json',json.dumps(sorted(generated),indent=2))
    print(json.dumps({'module30':Counter(r['status'] for r in cases),'focused':target,'full':full,'global_catalog':summary['catalog_counts']},indent=2))
if __name__=='__main__':main()
