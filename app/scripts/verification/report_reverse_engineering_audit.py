"""Publish executed Prompt29 evidence; incomplete acceptance contracts stay blocked."""
from collections import Counter
from contextlib import redirect_stdout
import difflib,hashlib,io,json,re,sys
from pathlib import Path
import xml.etree.ElementTree as ET
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
from scripts.verification import report_whatsapp_audit as common
from tests.test_reverse_engineering_audit import GATES
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/29-reverse-engineering';PRE=BASE/'.jarvis-runtime/jarvis-audit/module29-pre'
common.MOD=MOD
read,sha,write,stats=common.read,common.sha,common.write,common.stats

def marker(path,text):
    s=path.read_text(encoding='utf-8');s=re.sub(r'\n<!-- prompt29-audit -->.*?<!-- /prompt29-audit -->\n','',s,flags=re.S)
    first,rest=s.split('\n',1);path.write_text(first+'\n\n<!-- prompt29-audit -->\n'+text+'\n<!-- /prompt29-audit -->\n'+rest,encoding='utf-8')

def main():
    from scripts.verification import audit_catalog
    from jarvis import rea_tools
    baseline,target,full=(stats(n) for n in ('baseline.xml','cases-and-contracts.xml','full-regression.xml'))
    assert baseline['PASS']==41 and target['PASS']==131 and target['SKIPPED']==13
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0
    frozen=read(MOD/'full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    bench,env,ready=(read(MOD/n) for n in ('benchmark-summary.json','environment.json','readiness.json'))
    assert bench['equivalent'] and ready['status']=='ready'
    probe=read(MOD/'environment-fixture.json');assert probe['values']==dict.fromkeys(['GROQ_API_KEY','OPENAI_API_KEY','NODE_PATH','NODE_OPTIONS']) and probe['telemetry']=='1'
    modules=read(OUT/'module-map.json');modules[28].update(sources=['jarvis/rea_tools.py','jarvis/toolkits.py','jarvis/commands.py','jarvis/task_state.py','jarvis/harness_process.py','skills/reverse-engineer-clone/SKILL.md','skills/project-coding/SKILL.md','docs/rea-reverse-engineer-clone.md','integrations/rea-upstream/source-manifest.json'],test_candidates=['tests/test_reverse_engineering_audit.py','tests/test_rea_tools.py'],status='PARTIAL',reason='19 catalog fixture PASS / 13 explicit incomplete acceptance contracts; no current general REA/clone fidelity certification')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    with redirect_stdout(io.StringIO()):audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()];cases=[r for r in catalog if r['id'].startswith('JRV-29-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':19,'BLOCKED':13}
    assert {int(r['id'][-3:]) for r in cases if r['status']=='BLOCKED'}==set(GATES)
    summary=read(OUT/'summary.json');write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    write('remaining-case-ids.txt','\n'.join(f'JRV-29-{n:03}' for n in GATES))
    gates='\n'.join(f'- **JRV-29-{n:03} BLOCKED:** {reason}' for n,reason in GATES.items())
    scope=('Isolated local files, mocked REA output/approval transports and fault injection; five concurrent ingests and five note writes × 20 rounds; actual owned Node observation and timeout/descendant-cleanup fixtures; actual Python checkpoint-crash child and restart refusal. '
           'No new dependency, external REA analysis, generated clone, GUI, account action, cloud request, GPU/model job or private source collection ran. Approval mocks exercise the transport boundary; they are not authorization to execute third-party analysis. The installed Node runtime only executes source-owned test scripts.')
    matrix='''| Documented claim | Actual entry and evidence | Practical limit |
| --- | --- | --- |
| Five REA tools | toolkits.TOOLS registration → rea_tools.execute; commands.command reflex mapping | Sensitive rea_analyze requires Actions._approve; other tools are local bookkeeping |
| Source isolation | _target + _unlinked → absolute nonruntime local path or public_url validation | Link/reparse ancestors reject; no sandbox or complete recursive secret/permission scanner |
| Ingest and iterations | ingest → UUID session/session.json/ledger; record → bounded exclusive append | Records instructions only; no automatic implementation or fidelity proof |
| Analysis | analyze/_analyze → exact approval detail → _run_rea with argv and shell=False | Existing allowlist retained; no required-field schema for every REA command; flags need user review |
| Bounded faults | _run_rea temporary output sink, deadline, cancel, OwnedJob | Real Node timeout reaps tested parent/child on Windows; launch-to-job attachment is not an atomic containment boundary |
| Recovery | exclusive .operation.lock + attempted/uncertain checkpoint; TaskState checkpoint on caught uncertainty | Crash leaves a fence; never auto-clear or auto-replay. Failed storage/cleanup requires manual inspection |
| Evidence | nonempty finite JSON object, 200,000 UTF-8 bytes, exclusive evidence creation, attempt ID | untrusted=True, verified_behavior=False; evidence may contain private local text; no semantic truth guarantee |
| Working data | 64 KiB typed session read; 16,384-character tool input; 2 MiB ledger; 1,000-entry inventory and analysis limit | Legacy sessions accepted when fields are valid; no automatic migration/deletion; old temporal observations are not fresh proofs |
| Clone/iterate | reverse-engineer-clone guide → existing project-coding workflow | Bridge has no mandatory button/screenshot/layout acceptance receipts; do not infer that a clone was generated |
| Runtime lifecycle | Existing Start/Stop, launcher, recovery and manifest remain compatible | No new service/dependency; one module RLock serializes operations; cross-process session fences fail busy rather than queue |'''
    metric=f"One synthetic 1 MB ledger append: warm p50/p95 {bench['before']['p50_ms']:.5f}/{bench['before']['p95_ms']:.5f} → {bench['after']['p50_ms']:.5f}/{bench['after']['p95_ms']:.5f} ms; peak temporary Python allocation {bench['before']['peak_python_bytes']} → {bench['after']['peak_python_bytes']} bytes."
    fixes='''UUID session IDs remove same-second collisions. Session-scoped exclusive lock files prevent cross-process overlap and retain crash evidence; a process RLock serializes local operations. Append-only, fsync-backed ledger updates preserve notes without rereading/copying the entire ledger. Ledger append is bounded but not a transactional journal: a disk failure can leave a partial untrusted note.

Configuration now rejects malformed objects, empty/invalid allowlists, nonfinite/bool/invalid timeouts and input limits. Configured timeout range stays 10–3600 seconds; max_input_mb is explicitly 1–200. JSON tool input is bounded before parsing. Session checkpoints have typed identity/state/count validation and a 64 KiB limit. Target/session/evidence/ledger/program ancestors reject symlinks and Windows reparse points. UTF-8 surrogate text is rejected before writes.

Analysis rechecks cancellation, paths and program size/mtime after approval. It atomically persists attempt_id/attempted before launching; errors/cancellation set uncertainty, with generic TaskState uncertainty for caught failures. Successful evidence and ledger are saved before marking completed. Attempted/uncertain/crash-lock sessions refuse a new execution. A hard crash before the catch remains protected by the durable attempt and lock. No cache bypasses a fresh approval or reuses stale analysis.

Node stdout uses a temporary file with periodic size checks and a 200,000-byte accepted readback cap; this is not a hard disk quota between checks. JSON must be a nonempty finite object. Nonzero, offline, malformed, oversized, cancellation and worker-disconnect fixtures never claim success. Windows OwnedJob closes only the tested owned process tree. NODE_PATH is no longer inherited; other user-profile paths remain for existing dependencies and do not provide privacy confinement. A separate actual owned Node fixture read back null for fake GROQ_API_KEY, OPENAI_API_KEY, NODE_PATH and NODE_OPTIONS and REA_DISABLE_TELEMETRY=1. This proves environment filtering, not that third-party REA honors the telemetry flag or lacks network/profile access. Outputs explicitly state untrusted and behavior unverified. Tool names and natural-language routing remain stable.
'''
    write('inventory.md','# Prompt 29 REA audit — 2026-10-16 IST\n\n**PARTIAL: 19 catalog fixture PASS / 13 BLOCKED.**\n\n'+scope+'\n\n'+matrix+'\n\n'+gates+'\n\n[Report](../../final-report.md) · [Assertions](cases-and-contracts.xml) · [Diff](source.patch)')
    write('failures.md','# Reproduction and repair evidence\n\nBaseline: 41 passed. Eight initial assertions failed: same-second concurrent session collision; four malformed configurations; invalid analysis output accepted; uncertain analysis replayed; oversized checkpoint accepted. [Reproduction](reproduction.xml), [log](reproduction.txt). First repairs: 17 passed. Expanded matrix first had 73 passed / 13 skips / 2 fixture setup errors: pytest used a 200 KB parameter value as an environment-variable test ID, exceeding Windows 32,767 characters. Short explicit parameter IDs repair this test-harness issue without weakening assertions. Next targeted run: 104 passed / 13 blocked skips. Expanded neighboring TaskState/recovery run: 127 passed / 13 blocked skips. Additional direct wrong-kind-list input reproduced an unhandled TypeError; kind validators now reject list/object/bool/number with ValueError. Four new regression variants pass. Final focused result: 131 passed / 13 blocked skips. The superseded full run was stopped at roughly 66 percent before this fix; its log/hash snapshot are preserved and do not count as completed validation. A fresh frozen full run validates final source.\n\nFull-test skips are recorded separately; a full-regression pass does not waive any catalog blocker.\n\n'+gates)
    write('compatibility.md','''# Official upstream review — 2026-10-16 IST

[REA 6.5.0 release](https://github.com/morluto/rea/releases/tag/rea-agents-6.5.0) was published 2026-10-14T12:32:45Z at revision 3b79af28e80785afce9f5998d8f03289402a1847; its changelog section is dated 2026-10-13. [Release notes](https://github.com/morluto/rea/blob/rea-agents-6.5.0/CHANGELOG.md) describe selected JavaScript source scope, retained evidence and partial observations. [Official npm metadata](https://registry.npmjs.org/rea-agents/latest) independently reports 6.5.0, MIT, engines ^22.19.0 || ^24.11.0 || >=26.0.0, CLI scripts/rea.mjs. [Dispatcher source](https://github.com/morluto/rea/blob/rea-agents-6.5.0/scripts/rea.mjs) routes dist/mcp/main.js specifically for MCP; it is not an interchangeable CLI entry. The guide is corrected accordingly. An initial guessed v6.5.0 tag URL returned 404; the actual tag is rea-agents-6.5.0.

Local configured REA remains 6.4.0 and Node remains v24.14.0. The existing integration manifest records the historical 6.4.0 review, not a 6.5.0 certification. No npm install, source update or optional native/browser engine ran. No claim of current live 6.5.0 compatibility or upstream Windows clone fidelity follows from Python mocks.

[Node's official release index](https://nodejs.org/dist/index.json), checked today, lists v24.22.0 and v26.12.0 dated 2026-10-14. Installed v24.14.0 satisfies REA's engine range but is older than current 24.x; [its release page](https://nodejs.org/en/blog/release/v24.14.0) is dated 2026-02-24. Platform patch currency remains unresolved; no personal system update was made. Firecrawl retrieval provenance/cache dates are in upstream-checks.json; cached sources are not a live package installation test. No paid API is required.
''')
    write('rollback.md','# Scoped rollback and resume\n\nPreimages are preserved in `.jarvis-runtime/jarvis-audit/module29-pre/` (paths relative to app, flattened with __; root-README.md is the parent README). Verify source-hashes.json before any restoration; if files changed since this audit, merge the specific source.patch hunks. Do not reset the dirty checkout, erase user work, delete sessions/evidence or run a bulk restore. New test/verification files are listed in files-changed.json; disable only their new audit registrations if intentionally reverting.\n\nRetain session attempt/uncertainty records and .operation.lock after a crash. Inspect the exact program, target and evidence before any human-approved new session; a new session is not permission to replay an uncertain external action. Never automatically clear a stale lock or mark attempted effects completed. The append format is compatible with old ledgers; partial disk-failure notes are untrusted. No dependency/service or personal config was changed.\n\nResume at JRV-29-001 with an authorized owned interactive demo and current analyzer accuracy oracle, then the exact IDs in remaining-case-ids.txt. Follow commands.md and freeze runtime/tests before full validation. Incomplete privacy/schema/freshness/clone acceptance work requires implementation and reproof, not a status edit.')
    write('commands.md','''# Reproducible commands (PowerShell from app/)

These tests use isolated owned fixtures. Atomic checkpoints and owned process tests ran with approved ordinary Windows permissions because restricted-token temp-file replacement is not a valid simulation of the installed runtime. No third-party REA command runs.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_rea_tools.py tests/test_toolkits.py -q --junitxml=artifacts/jarvis-audit/modules/29-reverse-engineering/baseline.xml
.venv/Scripts/python.exe -m pytest tests/test_reverse_engineering_audit.py tests/test_rea_tools.py tests/test_toolkits.py tests/test_audit_result_accounting.py tests/test_task_state.py tests/test_task_recovery.py -q --junitxml=artifacts/jarvis-audit/modules/29-reverse-engineering/cases-and-contracts.xml
.venv/Scripts/python.exe scripts/verification/verify_reverse_engineering_audit.py
.venv/Scripts/python.exe scripts/verification/verify_reverse_engineering_audit.py --environment
.venv/Scripts/python.exe -c "from pathlib import Path; import scripts.verification.verify_whatsapp_audit as v; v.OUT=Path('artifacts/jarvis-audit/modules/29-reverse-engineering'); v.freeze()"
.venv/Scripts/python.exe -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/29-reverse-engineering/full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe scripts/verification/report_reverse_engineering_audit.py
.venv/Scripts/python.exe scripts/verification/verify_reverse_engineering_artifacts.py
```

Capture stdout/stderr to the corresponding report logs/readiness.json. Baseline and reproduction artifacts preserve historical pre-fix results; do not overwrite them when resuming. Benchmark needs the preserved preimage. Five initial iterations do not represent cold-process analyzer runs. No TTFT/audio applies to ledger writes; no full model/RSS/VRAM latency claim.
''')
    config=read(BASE/'config/config.json').get('rea',{});entry=Path(config.get('entry',''));package=entry.parent.parent/'package.json';installed=read(package).get('version') if package.is_file() else None
    write('source-inventory.json',json.dumps({'configured_settings':config,'entry_exists':entry.is_file(),'tools':list(rea_tools.TOOLS),'entry_chain':['commands.command','toolkits.execute','rea_tools.execute','analyze','_run_rea'],'configured_rea_version':installed,'current_upstream':'6.5.0','external_engines_exercised':False},indent=2))
    decisions='\n\nKeep append optimization with bounded, serialized durable writes: '+metric+' Identical prefix and note readback are asserted for every sample. Security checks/fences are included in the after timing; no analysis cache is introduced because deterministic target freshness is unproven. Five initial and 20 warm samples per version, not cold analyzer processes. No rejected runtime optimization was retained.\n\n'
    marker(BASE/'README.md',f'''**2026-10-16 — Prompt 29 REA audit: PARTIAL.** {target['PASS']} focused assertions passed; 13 explicit catalog blockers. Full regression: {full['PASS']} passed / {full['SKIPPED']} skipped / 0 failures; launcher readiness ready. Session collision, malformed config/output, uncertainty replay and oversized checkpoint defects fixed; owned Node timeout/child cleanup and checkpoint-crash restart tested. {metric} No current third-party REA/clone/GUI fidelity or complete source/privacy isolation claim. [Evidence and limits](artifacts/jarvis-audit/modules/29-reverse-engineering/inventory.md) · [Latest audit](artifacts/jarvis-audit/final-report.md).''')
    marker(BASE.parent/'README.md','''**2026-10-16 — REA bridge audit (Prompt 29): partial.** Bounded configuration/evidence handling, concurrent session/ledger safety and durable no-replay fences now have regression coverage. Interactive clone fidelity, remote freshness and complete privacy isolation remain blocked. [Application details](app/README.md) · [Audit evidence](app/artifacts/jarvis-audit/final-report.md).''')
    guide=BASE/'docs/rea-reverse-engineer-clone.md';g=guide.read_text(encoding='utf-8')
    g=g.replace('`scripts/rea.mjs` (published packages also ship `dist/mcp/main.js`).','`scripts/rea.mjs`. The published `dist/mcp/main.js` is the MCP server entry, not a CLI replacement.')
    g=g.replace("REA's CLI entry (`scripts/rea.mjs` or a published dist entry)","REA's CLI dispatcher (`scripts/rea.mjs` or a separately reviewed compatible CLI wrapper)")
    g=re.sub(r'\n## Prompt 29 audit — 2026-10-16.*','',g,flags=re.S)
    guide.write_text(g+'\n## Prompt 29 audit — 2026-10-16\n\n'+fixes+'\n'+metric+'\n\nFull regression/readiness are fixture and dependency checks, not current live REA/clone acceptance. Installed REA 6.4.0 / Node 24.14.0 remain unchanged; official current versions checked are REA 6.5.0 / Node 24.22.0 on the installed major line. The older live 2026-10-12 result above remains historical. [Current evidence and 13 blockers](../artifacts/jarvis-audit/modules/29-reverse-engineering/inventory.md).\n',encoding='utf-8')
    changed=[];pairs=[];patches=[]
    for old in sorted(PRE.iterdir()):
        if not old.is_file():continue
        rel='../README.md' if old.name=='root-README.md' else old.name.replace('__','/');now=BASE/rel
        changed.append(rel);pairs.append(dict(path=rel,before=sha(old),after=sha(now)))
        patches.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),now.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
    for rel in ['tests/test_reverse_engineering_audit.py','scripts/verification/verify_reverse_engineering_audit.py','scripts/verification/report_reverse_engineering_audit.py','scripts/verification/verify_reverse_engineering_artifacts.py']:
        changed.append(rel);patches.extend(difflib.unified_diff([], (BASE/rel).read_text(encoding='utf-8').splitlines(True),fromfile='/dev/null',tofile='after/'+rel))
    write('source.patch',''.join(patches));write('source-hashes.json',json.dumps(pairs,indent=2));write('files-changed.json',json.dumps([{'path':p,'sha256':sha(BASE/p)} for p in changed],indent=2))
    write('changes.md','# Retained changes — Prompt 29\n\n'+fixes+decisions+'\n'.join('- `'+p+'`' for p in changed)+'\n\nGenerated module/global artifacts are listed in generated-files.json. Existing dirty work was preserved; no commit/reset or deployment occurred.')
    write('full-regression-skip-reasons.json',json.dumps([{'node':n.get('classname','')+'::'+n.get('name',''),'reason':n.find('skipped').get('message','')} for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if n.find('skipped') is not None],indent=2))
    table='| Module/evidence | Status | PASS | BLOCKED | NOT RUN |\n| --- | --- | ---: | ---: | ---: |\n'
    for m in modules:
        counts=Counter(r['status'] for r in catalog if int(r['id'][4:6])==m['number']);label=f"{m['number']:02}-{m['module']}";link=f'modules/{label}/inventory.md'
        if (OUT/link).is_file():label=f'[{label}]({link})'
        table+=f"| {label} | {m['status']} | {counts['PASS']} | {counts['BLOCKED']} | {counts['NOT RUN']} |\n"
    report=f'''# Jarvis audit — Prompt 29, 2026-10-16 IST

**PARTIAL: 19 REA catalog fixture PASS / 13 BLOCKED; no general production certification.**

Preserved dirty branch `audit/12-tool-registry`, commit `9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6`, canonical app/. Python {env['python'].split()[0]}, {env['platform']}, RAM {env['ram_bytes']} bytes, Node {env['node']}. Target RTX 3050 Laptop 4 GB from prior census; no GPU workload. [Environment](modules/29-reverse-engineering/environment.json).

{scope}

## Source map and implementation evidence

{matrix}

## Executed tests and measurements

Baseline **41 PASS**; eight initial regression failures reproduced and repaired. Focused **{target['PASS']} PASS / {target['SKIPPED']} explicit blocked skips / 0 FAIL**. Full tests-directory suite **{full['PASS']} PASS / {full['SKIPPED']} SKIPPED / 0 FAIL**, JUnit suite duration {full['seconds']:.3f}s; console wall time and warning detail are in [full log](modules/29-reverse-engineering/full-regression.log). Launcher dependency/config readiness **{ready['status']}**. {len(frozen)} frozen runtime/test files unchanged throughout full run. The generic full run does not supply missing acceptance assertions.

{metric} [Raw samples](modules/29-reverse-engineering/benchmarks.csv), [scope/summary](modules/29-reverse-engineering/benchmark-summary.json). Keep this narrow ledger improvement. Five initial samples are not cold process starts; no analyzer/GUI/model/RSS/VRAM speed claim.

[Focused assertions](modules/29-reverse-engineering/cases-and-contracts.xml) · [full XML](modules/29-reverse-engineering/full-regression.xml) · [source freeze](modules/29-reverse-engineering/full-start-source-hashes.json) · [owned Node environment readback](modules/29-reverse-engineering/environment-fixture.json) · [failures](modules/29-reverse-engineering/failures.md) · [commands](modules/29-reverse-engineering/commands.md) · [changes](modules/29-reverse-engineering/changes.md) · [exact files](modules/29-reverse-engineering/files-changed.json) · [diff](modules/29-reverse-engineering/source.patch) · [upstream URLs and release dates](modules/29-reverse-engineering/compatibility.md) · [rollback](modules/29-reverse-engineering/rollback.md).

## Exact catalog accounting

All **1,184 unique case IDs** retained: **{json.dumps(summary['catalog_counts'])}**. Full-case blockers override narrower passing variants. Module 29 has no unaccounted IDs. Earlier module results remain dated evidence, not new live acceptance.

{table}

Tier statistics:
```json
{json.dumps(summary['by_tier'],indent=2)}
```
Category statistics:
```json
{json.dumps(summary['by_category'],indent=2)}
```

## Known flaws, blockers and risk

{gates}

REA is an approved host subprocess, not a filesystem/network sandbox. Profile/appdata access and raw local evidence may contain secrets; no general confidentiality guarantee. Link/stat checks are not atomic handle-based defenses against a hostile concurrent host mutation. Process assignment follows launch; tested cleanup is not an escape-proof launch barrier. Ledger append has bounded durable writes but a disk failure can leave a partial note. The subprocess temporary output sink is checked periodically, so fast output can exceed the evidence limit transiently; no hard host storage quota is supplied. Stale locks and uncertain checkpoints intentionally stop automation and require inspection. Installed REA/Node are behind current official releases and were not upgraded. Existing tool/launcher/configuration contracts are retained; no new service/dependency was introduced.

## Deterministic resume

Next incomplete module case **JRV-29-001**; next untouched module **30/JRV-30-001**. Oldest unresolved global case **{summary['next_case']}**. [Module remaining IDs](modules/29-reverse-engineering/remaining-case-ids.txt), [all remaining IDs](remaining-case-ids.txt). Implement the missing accuracy, clone interaction/visual, freshness, schema and privacy contracts against an authorized owned demo, preserving current assertions. Follow commands.md, rerun focused/full/readiness, reconcile and verify artifacts. Do not install/update REA/Node, run invasive collection or execute new third-party abilities without the separately required approval. [Prior Prompt28 report](final-report-before-module29.md) preserves historical results and metrics.
'''
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    generated={p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file()};generated.update((OUT/n).relative_to(BASE).as_posix() for n in ('final-report.md','final-report-before-module29.md','module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt'));generated.update((MOD/n).relative_to(BASE).as_posix() for n in ('generated-files.json','artifact-verification.json'));write('generated-files.json',json.dumps(sorted(generated),indent=2))
    print(json.dumps({'module29':Counter(r['status'] for r in cases),'focused':target,'full':full,'global_catalog':summary['catalog_counts']},indent=2))
if __name__=='__main__':main()
