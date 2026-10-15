"""Publish Prompt11 only from executed assertions, measured data and source preimages."""
from collections import Counter
import contextlib
import difflib
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
ROOT=BASE/'artifacts/jarvis-audit';OUT=ROOT/'modules/11-skill-selection'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module11-pre'
RUNTIME=('jarvis/capabilities.py','jarvis/skill_memory.py','jarvis/hermes_skills.py','jarvis/utility_profiles.py','jarvis/agent_tools.py')
DOCS=('docs/skills-and-learning.md','docs/runtime-capabilities.md','docs/hermes-skills-and-comparison.md','docs/utility-skills.md','docs/system-map.md')
FILES=(*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py',
       'tests/test_skill_selection_audit.py','scripts/verification/verify_skill_selection_audit.py','scripts/verification/report_skill_selection_audit.py','README.md',*DOCS)


def write(path,text):path.write_text(text,encoding='utf-8')


def result(name):
    tree=ET.parse(OUT/name);rows=list(tree.iter('testcase'));assert rows
    assert not any(r.find('failure') is not None or r.find('error') is not None for r in rows)
    skips=[r for r in rows if r.find('skipped') is not None]
    assert all('BLOCKED:' in r.find('skipped').get('message','') for r in skips)
    return dict(passed=len(rows)-len(skips),blocked=len(skips),seconds=float(next(tree.iter('testsuite')).get('time',0)))


def prepend(path,text):
    old=path.read_text(encoding='utf-8');marker='<!-- prompt11-audit -->'
    if marker in old:
        start=old.index(marker);end=old.index('<!-- /prompt11-audit -->',start)+len('<!-- /prompt11-audit -->')
        old=old[:start]+old[end:].lstrip('\n')
    head,body=old.split('\n',1)
    write(path,head+'\n\n'+marker+'\n'+text+'\n<!-- /prompt11-audit -->\n\n'+body.lstrip('\n'))


def main():
    baseline=result('existing-baseline.xml');targeted=result('cases-and-contracts.xml');full=result('full-regression.xml')
    assert all((OUT/'full-regression.xml').stat().st_mtime>=(BASE/n).stat().st_mtime for n in (*RUNTIME,'tests/test_skill_selection_audit.py','scripts/verification/audit_catalog.py'))
    repro=list(ET.parse(OUT/'reproduced-failures.xml').iter('testcase'))
    assert sum(r.find('failure') is not None for r in repro)==8
    ready=json.loads((PRE/'readiness-private.json').read_text(encoding='utf-8-sig'))
    assert ready['status']=='ready' and not ready.get('missing') and not ready.get('incomplete')
    write(OUT/'readiness.json',json.dumps({'date':'2026-10-15 IST','command':'.venv/Scripts/python.exe -m jarvis.launcher --check',
        'status':ready['status'],'services':{k:v['status'] for k,v in ready.get('services',{}).items()},'exit_code':0},indent=2)+'\n')
    census=json.loads((OUT/'census.json').read_text());bench=json.loads((OUT/'benchmark-summary.json').read_text())['results']
    modules=json.loads((ROOT/'module-map.json').read_text())
    modules[10].update(status='31 FIXTURE PASS / 1 BLOCKED; LIVE ACCEPTANCE UNVERIFIED',
        reason='Bounded guide/provenance/ranking/isolation/activation assertions; arbitrary PDF edit unavailable and utility validation stale. No new abilities/providers/helpers executed.',
        sources=[*RUNTIME,'jarvis/tools.py','jarvis/agent_events.py','jarvis/deerflow.py',*DOCS],
        test_candidates=['tests/test_skill_selection_audit.py','tests/test_capabilities.py','tests/test_skill_memory.py','tests/test_hermes_skills.py','tests/test_utility_skills.py','tests/test_deerflow.py'])
    write(ROOT/'module-map.json',json.dumps(modules,indent=2)+'\n')
    from scripts.verification.audit_catalog import reconcile
    with contextlib.redirect_stdout(io.StringIO()):reconcile()
    rows=[json.loads(s) for s in (ROOT/'test-results.jsonl').read_text().splitlines()]
    assert len(rows)==len({r['id'] for r in rows})==1184
    cases=[r for r in rows if r['id'].startswith('JRV-11-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':31,'BLOCKED':1}
    for row in cases:
        row['scope']='Isolated local guides/vaults, real registry/policy and fake transports. Public checked-out guide census/readback. No live model, accounts, desktop or arbitrary PDF editor certification. Timeout/outage cases prove offline discovery independence; GPU pressure case proves bounded metadata only, not VRAM stress.'
    write(OUT/'tests.jsonl',''.join(json.dumps(r)+'\n' for r in cases))
    write(OUT/'remaining-case-ids.txt','\n'.join(r['id'] for r in cases if r['status']!='PASS')+'\n')
    summary=json.loads((ROOT/'summary.json').read_text());next_id=next(r['id'] for r in rows if r['status']=='NOT RUN')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=BASE,text=True).strip()
    metrics='\n'.join(f'| {k} | {v["samples"]} | {v["p50_ms"]:.3f} | {v["p95_ms"]:.3f} | {v["peak_python_bytes"]} |' for k,v in bench.items())
    commands='''.venv/Scripts/python.exe -m pytest tests/test_capabilities.py tests/test_skill_memory.py tests/test_custom_skills.py tests/test_hermes_skills.py tests/test_utility_skills.py tests/test_deerflow.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/11-skill-selection/existing-baseline.xml
.venv/Scripts/python.exe scripts/verification/verify_skill_selection_audit.py
.venv/Scripts/python.exe -m pytest tests/test_skill_selection_audit.py tests/test_capabilities.py tests/test_skill_memory.py tests/test_custom_skills.py tests/test_hermes_skills.py tests/test_utility_skills.py tests/test_deerflow.py tests/test_cognition_and_routing.py tests/test_audit_result_accounting.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/11-skill-selection/cases-and-contracts.xml
.venv/Scripts/python.exe -m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/11-skill-selection/full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe scripts/verification/report_skill_selection_audit.py'''
    write(OUT/'commands.txt',commands+'\n')
    matrix='''| Claim / entry point | Actual checked-out evidence | Proven boundary / limitation |
| --- | --- | --- |
| Native/custom/personal guides | skills/, custom-skills/, skill_memory.SkillMemory.refresh/context | 10 bundled; bounded50/source; builtin > custom > personal deterministic collision reporting; hot reload uses path/mtime/size, not adversarial metadata forgery protection |
| Tool discovery | capabilities.rank_tools/runtime_context → ToolRegistry.search/catalog | Existing handlers only, prerequisites/scope/provider filters retained; unknown names diagnostic, not executable |
| Trust/provenance | refresh → skill_read folder=@jarvis | Origin, relative path, SHA256 and untrusted_guidance label; registry policy/current authorization remain authoritative; hash is consistency, not authenticity |
| Hermes references | hermes_skills.HermesSkills → skill_list/read folder=@hermes | 210 indexed SKILL.md contents verified,1090 indexed resources; unique bounded metadata, indexed exact resource/read budget, hashes checked; helpers not run |
| DeerFlow references | deerflow.status/search_skills/read_skill → folder=@deerflow | 23 public guides present; existing neighboring fixture suite, no provider readiness inferred from guide availability |
| Utility activation | utility_profiles.availability/tools → toolkits/registry | Separate environment exists but validation already stale before this update:0 offered. Missing/malformed/stale states fail closed. No arbitrary PDF-edit adapter offered |
| Learned procedures | SkillMemory.record/context | Existing verified recipe preserved after failure; new success/attempt counts, relevance then smoothed rate then recency; historical missing failures not reconstructed |
| Builtin and lifecycle policy | commands.py immutable dispatch; ToolRegistry.execute → check_policy/_execute/event | Existing builtin wins; denied/cancelled tools never dispatched in fixtures; categorical UUID metadata excludes payloads; no replay/helper queue |
'''
    write(OUT/'inventory.md',f'''# Prompt11 — skill selection audit

2026-10-15 IST. **31 catalog fixture PASS / 1 BLOCKED / 0 FAIL / 0 SKIPPED / 0 NOT RUN.** JRV-11-002 is blocked: no validated arbitrary PDF-edit adapter is offered. Markdown-to-PDF creation is not arbitrary PDF editing. Optional utility validation was stale before this change; it remains disabled rather than rewriting proof hashes. This is not whole-system production certification.

Repo `{commit}`, branch `{branch}`; Windows/Python{platform.python_version()}, Ryzen7/32GB/RTX3050 Laptop4GB target from prior native observations. CPU metadata-only work here; no GPU/model acquisition. app/ canonical, existing dirty work preserved, no commit/reset/install/provider setup/personal deletion/account write/OS mutation/deployment. No GUI change or new screenshot.

## Source map, dependency graph and safe order

{matrix}

Read system-map and linked skill/learning/runtime/Hermes/utility/DeerFlow documents; historical counts and live trials remain dated historical evidence. Actual order: source/registration/policy inventory → existing baseline → defect reproductions → smallest bounded fixes → catalog/fault/concurrency/security journeys → paired ranking benchmark/public census → full regression/readiness → accounting/docs. Dependencies: source metadata → bounded catalog → relevance/tool binding → current registry scope/provider/policy → per-action approval/executor → fresh readback → verified procedure history. External guidance never skips execution gates. No semantic model reranker added: deterministic bounded scoring is sufficient for the verified fixtures and avoids extra inference/VRAM/latency; general semantic quality remains unmeasured.

## Executed assertions and actual census

Baseline **{baseline['passed']} PASS**, {baseline['seconds']:.2f}s,[XML](existing-baseline.xml). Eight before-fix regression failures reproduced,[XML](reproduced-failures.xml);12 incidental imported unittest passes in that first run are not extra new tests. The import was moved inside a helper to avoid duplicate collection. Final targeted **{targeted['passed']} PASS / {targeted['blocked']} BLOCKED skip**, {targeted['seconds']:.2f}s,[XML](cases-and-contracts.xml). Full **{full['passed']} PASS / {full['blocked']} explicit BLOCKED skips**, {full['seconds']:.2f}s,[XML](full-regression.xml),[actual completion](full-run-completion.txt). Counts overlap. Launcher **ready**,[redacted check](readiness.json). Existing pywinauto STA COM warning is retained. [Commands](commands.txt),[all32 catalog IDs/assertions](tests.jsonl).

Read-only public-source census: **{census['builtin_guides']} bundled, {census['hermes_manifest_rows']} Hermes/{census['hermes_guides_verified']} hash-verified guides, {census['hermes_resource_entries']} indexed resources, {census['deerflow_public_guides']} DeerFlow public guides**.0 census errors. [Census](census.json). Supporting resources were counted, not all executed or live-certified. No real personal vault sync or synthetic procedure insertion in the real vault. Existing utility environment present, **{census['utility_availability']}**, **{census['utility_offered']} offered**. Historical38-local/3-mock claims do not describe current activation.

Journeys include native browser guidance+real registered navigation selection, guide hot reload/delete, builtin/custom/personal duplicate precedence, malformed/unknown binding diagnostics, policy denial despite forged approval text, reserved-source readback, five threads×20 rounds of independent bounded contexts, cancellation before dispatch, temporary vault restart, stale guide hashes, Unicode/CRLF, unavailable prerequisites/upstream isolation,50-guide cap, repeated discovery without effects and payload-free UUID events. No test executes newly learned helpers or performs real account operations. Network outage/timeout fixtures assert discovery calls no network; they do not certify a live remote timeout. Pressure fixture bounds metadata/context, not physical VRAM. Negation fixture proves retrieval is not dispatch, not all-language intent accuracy. The positive utility fixture uses an empty executable sentinel and fake validation hashes solely for discovery/scope assertions, never as real installation evidence.

## Matched component measurement and keep decision

| Version/cache | Samples | p50 ms | p95 ms | Peak traced Python bytes |
| --- | --- | --- | --- | --- |
{metrics}

[Raw50 samples](benchmarks.csv),[scope/summary](benchmark-summary.json). Saved pre-change algorithm versus current on identical150 synthetic guide rows/six tool labels and machine; all50 selections identical. Five cleared description-cache calls and20 warm calls/version; cold does not mean cold OS/model.0 helper/tool/network effects. TTFT, first audio and VRAM are not applicable; traced bytes are transient component allocation, not whole-host RAM. Bounded2048 description-token cache does not cache goals and bypasses recognized credential descriptions; other personal metadata may remain in process memory. Cold allocation increases; retain for reduced repeated scoring work and bounded warm allocation, with timing variation explicit. No general precision/voice latency guarantee is inferred.

## Remaining limits

JRV-11-002 needs a reviewed installed/allowed arbitrary PDF-edit adapter and authorized validation. Do not refresh utility hashes without rerunning appropriate reviewed verification; live account/OS checks require separate approval. Guides are local untrusted text; labels/hashes do not prove authorship or prevent every prompt injection. Approval enforcement remains in current tool/action policy. Historical failure counts cannot be reconstructed from legacy procedure rows; the rate is a smoothed observed estimate after a recipe exists. Guide hot reload uses file metadata; malicious same-size timestamp restoration is outside its guarantee. Supporting helpers/providers, native model selection quality, actual desktop execution, physical GPU contention and long soak remain unverified. No catalog case is silently dropped.

[Failures](failures.md),[changes](changes.md),[upstream compatibility](compatibility.md),[rollback/resume](rollback.md),[exact files](files-changed.json),[scoped patch](source.patch). Next module NOT RUN: **{next_id}**; earliest global unresolved **{summary['next_case']}**.
''')
    write(OUT/'failures.md','''# Reproduced failures and corrections — 2026-10-15 IST

Eight failures in reproduced-failures.xml: vault-relative traversal was not explicitly contained; malformed tools metadata silently became unbound guidance; duplicate Hermes names were accepted; oversized Hermes reads opened content before budget rejection; manifest rows could omit SKILL.md; equally relevant procedures ignored observed success rate; a missing utility environment did not prevent activation; malformed validation rows could raise AttributeError. Twelve old unittest cases were inadvertently collected in that initial reproduction and passed; final test helper avoids collecting their imported class.

Fixes are bounded validation/path checks, pre-open resource budgets, deterministic observed-rate ordering, guarded utility availability and categorical diagnostics. A first implementation run exposed CRLF normalization lost by binary reads (10 failures); normalized UTF-8 text restored original behavior and all85 targeted tests passed before catalog expansion. Three later catalog fixture errors used execution_contract instead of the actual contract response key; corrected tests, not production API. A new accounting assertion then exposed omission from the explicit BLOCKED allowlist; corrected with its regression. Initial census runner passed an entry dict instead of the public resource-string API; corrected runner. These transient audit errors are not counted as pre-existing product defects.

Final assertions have no FAIL. JRV-11-002 remains explicitly BLOCKED. Current stale utility proof is pre-existing; no fabricated revalidation or arbitrary PDF editing claim. Source integrity checks do not replace live provider/GUI/model/hardware acceptance.
''')
    write(OUT/'changes.md','''# Retained scoped changes

- capabilities.py shares per-query ranking inputs and caches bounded description tokens; scores tool bindings once, retaining existing intent priorities/prerequisites and deterministic ties. Catalog exposes guide provenance/trust. No semantic inference/model added.
- skill_memory.py bounds UTF-8 reads and tool metadata, normalizes CRLF, records origin/relative source/content hash, constrains vault paths, sanitizes guide diagnostics. Verified recipe reuse tracks observed attempts and sorts equally relevant procedures by smoothed success rate before recency. Legacy rows remain compatible.
- hermes_skills.py validates bounded unique metadata/resources and mandatory SKILL.md, checks budgets before reads and caps binary read size before hash/length validation. No upstream code/version installation.
- utility_profiles.py exposes missing_environment/validation_unavailable/stale_validation/ready states and disables missing/malformed/stale activation; current policy/credentials still apply. Existing historical validation record preserved.
- agent_tools.py local guide readback adds provenance, untrusted label and current-policy execution contract; tool names and workflows preserved.
- Tests add32 catalog scenarios and9 supplemental assertions; reviewed catalog accounting handles the explicit PDF blocker. Runtime manifest and dated linked docs describe contracts/census/limits. No new dependency, service, UI or real external action. Existing user changes retained.

See source.patch, source-hashes.json and files-changed.json. No commit or deployment was performed.
''')
    write(OUT/'compatibility.md','''# Official upstream check — 2026-10-15 IST

Firecrawl read the [Agent Skills integration guide](https://agentskills.io/client-implementation/adding-skills-support), [Hermes v0.22.2](https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.2), and [DeerFlow v2.1.0](https://github.com/bytedance/deer-flow/releases/tag/v2.1.0). Actual returned answers/canonical URLs/status are in [upstream-checks.json](upstream-checks.json). Agent Skills page shows no publication date; it describes metadata/full-body/resource loading and untrusted project skills. Its project-over-user precedence recommendation does not override Jarvis's builtin-first policy. Hermes latest page reports2026-10-15; no skill compatibility change was established. DeerFlow page displays24 Sep10:40/three weeks ago (year not printed in extracted answer;2026 inferred from run date), and describes managed skill projections, package boundaries, review gates and secret/authorization hardening. Release notes are not proof these features are present in Jarvis's pinned adapter.

Local Hermes remains cbc569e23cb045b58b067f37cf5514feb44e0828; DeerFlow remains a5e71751d7a9f8f4a71ca458da3984fc1284d098 (recorded backend2.2.0-dev/harness2.1.0). No checkout, runtime, paid provider, dependency or model upgrade performed. Main Python3.10.6 standard-library implementation remains compatible with its existing separate Hermes/DeerFlow/utility environments. New upstream code is not automatically trusted or installed. Utility interpreter existence is discovery only; current source-bound proof is stale, so0 tools offered. Historical utility package/live results remain historical.

No newer release is assumed faster/better for RTX3050 Laptop4GB. The accepted optimization is bounded CPU metadata reuse measured locally; model/GPU quality, native inference and live account acceptance remain separate work.
''')
    write(OUT/'rollback.md','''# Rollback and deterministic resume

Preserve the current dirty tree first; never git reset/clean or copy whole older trees. Review source.patch and source-hashes.json. Private local preimages are in .jarvis-runtime/jarvis-audit/module11-pre/. Reverse only the reviewed Prompt11 hunks in capabilities.py, skill_memory.py, hermes_skills.py, utility_profiles.py, agent_tools.py, runtime_manifest.json and audit_catalog.py; do not overwrite later/user edits. README/docs preimages are named app-<relative-path-with-__>, plus root-README.md. Other tests/report scripts are additions; preserve evidence rather than deleting personal files. No commit or deployment to roll back. Public patch supplies reproducible scoped code differences if ignored preimages are unavailable.

Re-run commands.txt in order with the existing main environment, <=2 small test processes and no concurrent heavy GPU work. Generate census/benchmark before catalog tests. Full regression/readiness must match current source; reports reject failure XML/stale source. Do not execute utility live validators, account writes, OS mutations, installs or helpers just to turn a blocker green. JRV-11-002 requires a reviewed arbitrary PDF-edit adapter and appropriate authorization/validation. Continue the requested next module by reading its prompt; global remaining-case-ids.txt records every unresolved ID, tests.jsonl every Prompt11 ID. Earlier acoustic, speech GPU lease and research-before-action blockers remain open. No blanket production sign-off.
''')
    blurb=f'''**Skill-selection audit — 2026-10-15 IST:** Bounded guide validation and provenance,
observed procedure reliability and reused description tokens retain existing tool,
policy and approval gates. Census:10 bundled/210 hash-verified Hermes/23 DeerFlow
guides. Utility validation is stale:0 offered; historical activation counts below
are dated results. Arbitrary PDF editing remains blocked.
[Executed assertions, measurements and limits](artifacts/jarvis-audit/modules/11-skill-selection/inventory.md).
Verification: **{full['passed']:,} regression PASS / {full['blocked']} blocked skips**;
**{targeted['passed']} targeted PASS / {targeted['blocked']} blocked skip**; Prompt11 **31 PASS / 1 BLOCKED**,
launcher **ready**. These fixtures do not certify live production acceptance.'''
    prepend(BASE/'README.md',blurb)
    prepend(BASE.parent/'README.md',blurb.replace('](artifacts/','](app/artifacts/'))
    notice='''**2026-10-15 skill-selection audit:** Current checked-out census is10 bundled,
210 hash-verified Hermes guides and23 DeerFlow public guides. Local guide reads
expose source hashes and untrusted-reference contracts. Tool bindings remain
limited to current registered/allowed handlers. Missing utility environment or
malformed/stale source-bound proof disables activation; current proof is stale,
so0 utility tools are offered. Historical counts/live results below retain their
original dates. [Assertions, performance, limits and rollback](../artifacts/jarvis-audit/modules/11-skill-selection/inventory.md).'''
    for name in DOCS:
        if name!='docs/system-map.md':prepend(BASE/name,notice)
    path=BASE/'docs/skills-and-learning.md';text=path.read_text(encoding='utf-8').replace('The nine current Jarvis guides','The ten current Jarvis guides').replace('runtime questions and browser navigation.','runtime questions, browser navigation and reverse-engineer clone.')
    write(path,text)
    path=BASE/'docs/system-map.md';text=path.read_text(encoding='utf-8').replace('| 38 local + 3 mock |','| 0 currently offered: source-bound validation stale (2026-10-15); historical38 local +3 mock |')
    write(path,text)
    table='\n'.join(f'| {m["number"]:02} | {m["module"]} | {m["status"]} |' for m in modules)
    def stats_table(group):
        return '| '+group+' | PASS | FAIL | BLOCKED | SKIPPED | NOT RUN |\n| --- | --- | --- | --- | --- | --- |\n'+'\n'.join(
            '| '+key+' | '+' | '.join(str(counts.get(state,0)) for state in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN'))+' |'
            for key,counts in summary['by_'+group.lower()].items())
    changed='\n'.join('- app/'+name for name in FILES)+'\n- README.md (root overview)'
    write(ROOT/'final-report.md',f'''# Jarvis audit — through Prompt11, 2026-10-15 IST

**Prompt11:31 fixture PASS / 1 BLOCKED; no pending or failed fixture cases.** Arbitrary PDF editing lacks a validated offered adapter. Full **{full['passed']} PASS / {full['blocked']} BLOCKED skips**, {full['seconds']:.2f}s; targeted **{targeted['passed']} PASS / {targeted['blocked']} BLOCKED skip**. [Full XML](modules/11-skill-selection/full-regression.xml),[targeted XML](modules/11-skill-selection/cases-and-contracts.xml),[actual completion](modules/11-skill-selection/full-run-completion.txt),[launcher ready](modules/11-skill-selection/readiness.json). Suites overlap; existing COM warning persists. Whole-system/live production acceptance remains open.

Repo `{commit}`, branch `{branch}`, Windows/Python{platform.python_version()}, Ryzen7/32GB/RTX3050 Laptop4GB target. CPU-only guide work, no new heavyweight/GPU test. Existing dirty work preserved; no commit/deployment, account send/write, personal deletion, system setting, credentials or ability installation. [Environment, dependency/entry-point/source-map evidence matrix and execution order](modules/11-skill-selection/inventory.md).

Eight pre-existing reproduced defects fixed: guide path/metadata validation, Hermes duplicate/missing resource validation/pre-open bounds, observed recipe ordering, missing utility environment and malformed validation handling. [Reproductions](modules/11-skill-selection/failures.md),[exact changed files/hashes](modules/11-skill-selection/files-changed.json),[scoped before/after diff](modules/11-skill-selection/source.patch),[rollback/resume](modules/11-skill-selection/rollback.md). Public source census10 native/210 verified Hermes/23 DeerFlow; utility proof stale before and after,0 offered. No helpers/providers newly activated.

Same-machine metadata ranking warm p50/p95 **{bench['before_warm']['p50_ms']:.3f}/{bench['before_warm']['p95_ms']:.3f}→{bench['after_warm']['p50_ms']:.3f}/{bench['after_warm']['p95_ms']:.3f}ms**; cold p95 **{bench['before_cold']['p95_ms']:.3f}→{bench['after_cold']['p95_ms']:.3f}ms**. [50 measurements](modules/11-skill-selection/benchmarks.csv),[allocation/tradeoffs/scope](modules/11-skill-selection/benchmark-summary.json). All selected rankings identical on the fixture; no general semantic precision, TTFT/audio/VRAM or whole-task speed claim. Bounded cache retains description metadata, not goals; recognized credential descriptions bypass it. Cold allocation cost is explicit. [Earlier per-module metrics/report through10](final-report-before-module11.md) and linked predecessors preserve prior evidence.

Official upstream pages checked today through Firecrawl: [Agent Skills](https://agentskills.io/client-implementation/adding-skills-support) (no date), [Hermes v0.22.2](https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.2) (2026-10-15), [DeerFlow v2.1.0](https://github.com/bytedance/deer-flow/releases/tag/v2.1.0) (page24 Sep;2026 inferred). [Actual answers and compatibility limits](modules/11-skill-selection/upstream-checks.json),[pinned revisions/decision](modules/11-skill-selection/compatibility.md). No upstream/runtime installation assumed compatible without tests.

## Risk and exact accounting

Guidance does not grant permission; current registry, policy, scope, approvals and cancellation remain authoritative. Hashes/provenance establish consistency, not identity; reload metadata is not adversarial tamper-proof. Legacy procedure failure counts unavailable, rate is a smoothed estimate. No real GUI/account/native model/physical GPU/long soak validation in this module. Arbitrary PDF editing and utility revalidation require reviewed implementation/authorized checks; earlier acoustic, shared speech lease and mandatory unfamiliar-program research blockers remain. No whole-system security/production or universal two-second certificate.

All1184 unique catalog IDs accounted: **{summary['catalog_counts']}**. [Exact ledger](test-results.jsonl),[tier/category/run totals](summary.json),[32 Prompt11 IDs/scopes](modules/11-skill-selection/tests.jsonl),[remaining IDs](remaining-case-ids.txt). No pass inferred from JSONL ingestion. Prior reports and failures retained.

{stats_table('Tier')}

{stats_table('Category')}

## Source-map evidence and exact scoped files

{matrix}

Changed files (not the entire pre-existing dirty tree); before/after hashes and artifact inventory are linked above:

{changed}

## Enumerated modules

| Module | Name | Status |
| --- | --- | --- |
{table}

Earliest unresolved **{summary['next_case']}**; next NOT RUN **{next_id}**. Prompt11 unresolved **JRV-11-002**. Read the next requested prompt before proceeding;37 modules are not all complete.
''')
    patch='';hashes={}
    for name in (*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py'):
        old=PRE/Path(name).name;current=BASE/name
        patch+=''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),current.read_text(encoding='utf-8').splitlines(True),fromfile='module11-pre/'+name,tofile=name,n=2))
        hashes[name]={'before':hashlib.sha256(old.read_bytes()).hexdigest(),'after':hashlib.sha256(current.read_bytes()).hexdigest()}
    write(OUT/'source.patch',patch);write(OUT/'source-hashes.json',json.dumps(hashes,indent=2)+'\n')
    files=[{'path':'app/'+name,'sha256':hashlib.sha256((BASE/name).read_bytes()).hexdigest()} for name in FILES]
    files.append({'path':'README.md','sha256':hashlib.sha256((BASE.parent/'README.md').read_bytes()).hexdigest()})
    write(OUT/'files-changed.json',json.dumps({'scope':'Scoped Prompt11 files relative to saved dirty preimages, not total git diff; artifacts and shared catalog reports regenerated. No commit/deployment.','files':files,'artifact_directory':'app/artifacts/jarvis-audit/modules/11-skill-selection','shared_artifacts':['final-report.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt']},indent=2)+'\n')
    print(json.dumps(dict(module11=dict(Counter(r['status'] for r in cases)),targeted=targeted,full=full,catalog=summary['catalog_counts'],next_notrun=next_id),indent=2))


if __name__=='__main__':main()
