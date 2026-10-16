"""Publish executed Prompt21 evidence; missing production contracts remain blocked."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/21-native-coding'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module21-pre'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(name,value):(MOD/name).write_text(value.strip()+'\n',encoding='utf-8')
def stats(name):
    tree=ET.parse(MOD/name);nodes=list(tree.iter('testcase'))
    return {'PASS':sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in nodes),
        'FAIL':sum(n.find('failure') is not None or n.find('error') is not None for n in nodes),
        'SKIPPED':sum(n.find('skipped') is not None for n in nodes),
        'seconds':sum(float(s.get('time','0')) for s in tree.iter('testsuite'))}


def main():
    from scripts.verification import audit_catalog
    baseline=stats('baseline.xml');target=stats('cases-and-contracts.xml');full=stats('full-regression.xml')
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0 and target['PASS']==30 and full['PASS']>2790
    frozen=read(MOD/'full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    env=read(MOD/'environment.json');bench=read(MOD/'benchmark-summary.json');ready=read(MOD/'readiness.json')
    assert bench['equivalent'] and bench['external_effects']==0
    modules=read(OUT/'module-map.json')
    modules[20].update(sources=['jarvis/native_coding.py','jarvis/coding_files.py','jarvis/codex_workload.py',
        'jarvis/coding_programs.py','jarvis/coding_processes.py','jarvis/codex_validation.py','docs/native-coding.md'],
        test_candidates=['tests/test_native_coding_audit.py','tests/test_native_coding.py','tests/test_codex_workload.py',
            'tests/test_coding_workflow.py','tests/test_codex_validation.py'],status='PARTIAL',
        reason='27 catalog fixture PASS/5 missing contracts BLOCKED; real local-model coding acceptance not performed')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-21-')]
    blocked={'JRV-21-003','JRV-21-009','JRV-21-010','JRV-21-019','JRV-21-032'}
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':27,'BLOCKED':5}
    assert {r['id'] for r in cases if r['status']=='BLOCKED'}==blocked
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    summary=read(OUT/'summary.json');counts=summary['catalog_counts']
    nodes=list(ET.parse(MOD/'full-regression.xml').iter('testcase'))
    skips=[{'node':n.get('classname','')+'::'+n.get('name',''),'reason':n.find('skipped').get('message','')} for n in nodes if n.find('skipped') is not None]
    write('full-regression-skip-reasons.json',json.dumps(skips,indent=2))
    gates='''- **JRV-21-003 BLOCKED:** Overlapping ownership is rejected; automatic same-function conflict resolution is absent.
- **JRV-21-009 BLOCKED:** Bounded path/import context exists, but no verified large-repository semantic symbol retrieval oracle.
- **JRV-21-010 BLOCKED:** Dependency installs are excluded; no approved lockfile/environment rollout contract.
- **JRV-21-019 BLOCKED:** Worktrees and receipts are retained without replay; no durable crash-resume orchestration protocol.
- **JRV-21-032 BLOCKED:** Local activity journals retain code and raw exception strings; complete credential-redacted observability is absent.'''
    scope='''Tests use owned temporary projects, actual local Git worktrees/merges and Python unit checks, scripted model proposals, fake loopback HTTP and injected failures. Five independent file sessions execute twenty rounds each; no concurrent GPU models. The existing two-worker assembly test exercises the shared workload engine with a fake executor; native single-worker integration also runs in baseline/full regression. This does not prove two live model workers or model-generated code quality. No account sends, personal deletes, OS changes, dependency installs, learned scripts, model downloads, real project promotion or deployment were run.'''
    matrix='''| Documented claim | Implementation / caller | Executed evidence / limit |
| --- | --- | --- |
| Native coding | native_coding.run/infer, coding_backend selection | Typed proposal/schema checks, test-first repair bounded to three rounds, malformed/timeout/disconnect stop; selected local Qwen3.5:9b only; no automatic backend replay |
| File isolation | coding_files.FileSession, claude_code_guard, codex_files.execute | Independent session state, assigned paths, read freshness, immutable tests, exact patches and prevalidation; trusted local fixture execution, not an OS sandbox |
| Uncertain writes | FileSession.uncertain and file-events.jsonl | Unmatched attempted save stops; malformed/oversized journals fail closed; rejected syntax records remain legitimate |
| Assembly | codex_workload.run/workload_contract | At most two workers, exact nonoverlapping ownership, dependency order and combined checks; same-function conflict resolution absent |
| LocalGithub | localgithub public loader; sibling src/local_github/gitops.py | Actual installed public utility creates owned Git worktrees; missing-path error; no private LocalGithub configuration or remote sends |
| Promotion | codex_workload.promote, combined validation hashes | Refuses any prior promotion journal; freezes bounded payloads, binds actual run to tested hashes, checks fresh destination, backs up/readbacks; partial multi-file failure requires review |
| Commands | coding_programs.checked_argv, owned WindowsProcess | Shell delete/inline script/install refused, missing executable explicit, timeout/cancel retains partial state; trusted project tests still execute with host user permissions |
| Privacy | native_coding.infer→knowledge_worker local transport | Fake private payload with Groq enabled makes only loopback /api/show and /api/chat requests, proxy environment disabled; no universal semantic privacy oracle |
| Context / performance | project_files, planner context budget, streamed journal | Bounded file/path context, not semantic retrieval; benchmark covers journal inspection only, not TTFT/build/GPU latency |
| Recovery / diagnostics | owned request/receipt/activity and promotion journal | Correlatable owned run state retained; no automatic uncertain replay; no complete crash continuation/redaction contract |'''
    b=bench['before']['warm'];a=bench['after']['warm']
    measured=f"Journal inspection warm p50/p95 **{b['p50_ms']:.4f}/{b['p95_ms']:.4f} → {a['p50_ms']:.4f}/{a['p95_ms']:.4f} ms**, peak traced allocation **{b['python_peak_bytes']} → {a['python_peak_bytes']} bytes**. Same1,000 paired journal rows,25 samples/version (five initial calls,20 warm); same imported process/cache. Complete and uncertain outcomes match. Cold label means first calls, not fresh-process cold start. No inference/audio/GPU/end-to-end latency claim."
    write('inventory.md',f'''# Prompt21 audit — 2026-10-16 IST

**27 catalog PASS /5 BLOCKED /0 FAIL /0 SKIPPED /0 NOT RUN.** [All32 exact IDs/assertions](tests.jsonl). Baseline {baseline}; final dedicated {target}; full {full}. [Commands/results](commands.txt), [full XML](full-regression.xml), [skip reasons](full-regression-skip-reasons.json).

{scope}

{matrix}

{gates}

Read the Prompt21 contract, app maintenance instructions, system-map and native-coding guide; architecture/model claims were checked against actual callers/configuration. Run order: contract/source trace→baseline→reproduction→narrow fixes→upstream compatibility→equivalent benchmark→focused/full regression→readiness→ledger/docs. Kept inherited dirty branch **{env['branch']}**, HEAD **{env['commit']}** to preserve user/module14–20 work; a fresh checkout would omit it. No audit commit/reset. Initial inspection observed e1a33a0; before the accepted full run the checkout advanced to9bf5528 (added fixes till20), preserved without reset. Frozen source hashes bind the accepted run, not an assumed clean checkout. [Environment](environment.json), [changes](changes.md), [compatibility](compatibility.md), [rollback](rollback.md).

{measured} [Raw samples](benchmarks.csv), [scope](benchmark-summary.json).
''')
    write('failures.md',f'''# Failures and production gates

Baseline74 PASS/0 FAIL in132.77s. New reproduction5 FAIL/74 PASS/5 explicit blockers in83.90s: replaying an earlier promotion attempt, absent tested-hash promotion binding, malformed JSON/signature handling and accepting unknown journal stages. The reproduction accidentally collected imported unittest classes too;74 passing assertions are not74 catalog cases. Failure count is assertions, not five independent defects.

First targeted1 FAIL/26 PASS/5 skips: race fixture mutated on Read instead of Write before payload freezing; fixed that fixture trigger. Subsequent29 PASS/5 skips, then final added existing-file edit/test and500-character path assertions: {target}. Broad focused122 PASS/5 blocked skips in128.97s. One sandbox-only rerun10 FAIL/20 PASS/5 skips in3.20s hit Windows atomic replacement access denial; required-permission rerun passed. No product weakening to hide sandbox errors. Full {full};383 source/test hashes frozen and unchanged.

{gates}

Risk: worktrees and command allowlists do not confine malicious test code. LocalGithub utility Git global hooks/config isolation was not proved. Promotion is per-file atomic, not a transaction across all files; on partial failure keep backups/journals and inspect fresh state. Hash binding/cache remove the tested-source reread gap but do not promise safety against a hostile host changing files concurrently. Final actual assembly passes validation hashes; trusted direct promote callers can omit optional expected_hashes for compatibility. Journals cap8MiB/4096 rows/262144 characters per line and fail closed; inspect over-limit or damaged state rather than deleting journals. Streamed line parsing can allocate up to the bounded file limit. Action signatures/receipts are local trusted metadata, not signed human consent. Logs may contain private source and credentials: retain in ignored local runtime, do not publish live logs.

Readiness **{ready['status']}**: {ready['missing']}. Read-only launcher/configuration checks passed with Ollama reachable; no live model coding/GUI/GPU stress or guaranteed response-time acceptance. Existing Python3.10 end-of-life and older global gates remain. No production-ready certificate.
''')
    write('changes.md',f'''# Changes and keep decision

1. coding_files.py streams bounded action journals; malformed, unsupported or unconfirmed mutation state halts safely. Previously full JSON lists were allocated and malformed state could raise an ordinary repairable exception or be ignored.
2. codex_workload.py refuses prior promotion attempts, binds actual run payloads to combined test hashes, freezes source bytes before destination actions and uses those exact bytes. Preserves per-file backups/readback and stale-destination gates.
3. Dedicated audit tests and explicit reviewed BLOCKED accounting; reproducible benchmark/report/hash verification scripts. README, native guide and system-map updated; no dependency/configuration/UI change. Existing console image and dated upstream artwork remain unchanged.

{measured}

Keep: lower measured allocation/latency plus stricter fail-closed behavior. Frozen promotion payloads add up to160×80KB (12.8MB) plus Python/decoded-text overhead, a deliberate bounded tradeoff on32GB RAM; no claim of universally faster builds. No dependency upgrade/install, live model comparison or energy measurement. Baseline {baseline}; final {target}; full {full}. [Exact files/hashes](files-changed.json), [before/after pairs](source-hashes.json), [scoped diff](source.patch).
''')
    write('compatibility.md',f'''# Compatibility — checked 2026-10-16 IST

Official sources inspected with Firecrawl; [exact URLs/dates](upstream-checks.json). [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) documents local JSON schema use and says Ollama cloud does not currently support this feature. Complete typed responses remain independently validated; schema shape does not prove code correctness. Documentation has no package release date; loopback /api/version returned0.40.0. Official Ollama v0.40.5 release notes display14 Oct19:45 (timezone unstated), while the search excerpt shows an Oct15 signature-verification timestamp. These are recorded separately rather than asserting that signature date as release date. Notes describe larger Nemotron support, cloud and Responses fixes plus llama.cpp/MLX updates; none establishes a local9B/4GB performance win. No runtime upgrade was installed. No live code-generation/model-quality comparison was run.

[Git for Windows](https://git-scm.com/install/windows) reports2.56.0(2), released2026-10-05; installed **{env['git']}** is older. [Official worktree reference](https://git-scm.com/docs/git-worktree) checked for checkout behavior; worktrees share repository metadata and are not a security sandbox. Existing installed Git executed owned fixture integration; newer Git was not installed/tested. LocalGithub public utility was read in the configured sibling checkout; no claim its live remote services or latest release were validated.

Python3.10.6, pytest8.4.2, Requests2.34.2, psutil7.2.2 retained. Prior [module20 compatibility](../20-self-evolution/compatibility.md) records official pytest9.1.1 release2026-06-19 and Python3.10 end-of-life2026-10-01; no claim those issues were resolved. Existing finite command/tool names and manual legacy adapters retained. Model failure stops the owned native run; it does not switch to cloud or replay partial effects.

{gates}

Launcher {ready['status']}; {ready['missing']}. No dependency installation, paid API requirement or model download.
''')
    write('rollback.md','''# Scoped rollback and resume

No audit commit. Preserve inherited dirty checkout. Compare source.patch, files-changed.json and current SHA256 before restoring only Prompt21 changes from ignored .jarvis-runtime/jarvis-audit/module21-pre. App-relative preimage names replace / with __; parent README is root-README.md. Do not reset the checkout, erase user edits or restore unchanged copied test_native_coding.py over later work.

Do not downgrade live uncertain save/promotion state: old code can replay a partial promotion. Retain journals/worktrees/backups, inspect fresh destination and ask for a new reviewed run; never erase a journal to force a retry. No actual personal project promotion occurred in this audit. Per-file backup restore requires checking later edits and explicit approval where applicable.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_native_coding_audit.py (immutable original-preimage A/B; do not overwrite preimages).
2. -m pytest tests/test_native_coding_audit.py -q --junitxml=artifacts/jarvis-audit/modules/21-native-coding/cases-and-contracts.xml
3. Optional neighbors: -m pytest tests/test_native_coding.py tests/test_coding_workflow.py tests/test_codex_workload.py tests/test_codex_validation.py tests/test_audit_result_accounting.py -q (use a distinct XML output).
4. Freeze jarvis/*.py and tests/test_*.py SHA256; -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/21-native-coding/full-regression.xml. No runtime/test edits during accepted run. Windows owned atomic replacements require the execution permissions used here.
5. -m jarvis.launcher --check (read-only); retain private raw output and publish redacted summary only. No automatic repairs.
6. scripts/verification/report_native_coding_audit.py then scripts/verification/verify_native_coding_artifacts.py; git diff --check.

Current incomplete IDs JRV-21-003/009/010/019/032. Next NOT RUN JRV-22-001; earliest older unresolved JRV-04-001. Exact remaining IDs in artifacts/jarvis-audit/remaining-case-ids.txt. Required contracts need bounded implementation/security proof before live model/GUI acceptance; do not treat mock passes as production approval.
''')
    headline=f"**Native coding audit — 2026-10-16 IST:** Promotion now refuses earlier attempts and uses frozen bytes bound to combined test hashes. Damaged or oversized save journals stop safely. **27 Prompt21 fixture PASS /5 BLOCKED**; full regression **{full['PASS']:,} PASS /{full['SKIPPED']} skips**,0 failures. Conflict resolution, semantic retrieval, dependency rollout, crash continuation and credential-redacted journals remain incomplete. Launcher **{ready['status']}**; live local-model coding acceptance was not run."
    for doc,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/21-native-coding/inventory.md'),
        (BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/21-native-coding/inventory.md'),
        (BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/21-native-coding/inventory.md'),
        (BASE/'docs/native-coding.md','../artifacts/jarvis-audit/modules/21-native-coding/inventory.md')]:
        text=doc.read_text(encoding='utf-8');first,rest=text.split('\n',1)
        rest=re.sub(r'<!-- prompt21-audit -->.*?<!-- /prompt21-audit -->\s*','',rest,flags=re.S)
        doc.write_text(first+'\n\n<!-- prompt21-audit -->\n'+headline+'\n[Evidence and rollback]('+link+').\n<!-- /prompt21-audit -->\n\n'+rest.lstrip('\n'),encoding='utf-8')
    table='\n'.join('| '+str(m['number']).zfill(2)+' '+m['module']+' | '+', '.join(f'{k}: {v}' for k,v in Counter(r['status'] for r in catalog if r['id'].startswith(f"JRV-{m['number']:02}-")).items())+' |' for m in modules)
    (OUT/'final-report.md').write_text(f'''# Jarvis audit — Prompt21 — 2026-10-16 IST

{headline}

HEAD **{env['commit']}**, branch **{env['branch']}**, inherited changes preserved. [Environment](modules/21-native-coding/environment.json). Baseline {baseline}; targeted {target}; full {full}. All **{len(frozen)} frozen runtime/test hashes unchanged**. [Full XML](modules/21-native-coding/full-regression.xml), [skip reasons](modules/21-native-coding/full-regression-skip-reasons.json), [readiness](modules/21-native-coding/readiness.json).

{scope}

{measured}

[Source-map-to-code matrix](modules/21-native-coding/inventory.md), [changes/metrics](modules/21-native-coding/changes.md), [exact files](modules/21-native-coding/files-changed.json), [diff](modules/21-native-coding/source.patch), [upstream URLs/dates](modules/21-native-coding/compatibility.md), [known flaws/risk](modules/21-native-coding/failures.md), [rollback/resume](modules/21-native-coding/rollback.md), [commands/results](modules/21-native-coding/commands.txt).

{gates}

All1,184 catalog IDs: **{counts}**. [Exact ledger](test-results.jsonl), [category/tier totals](summary.json), [exact remaining IDs](remaining-case-ids.txt). Next NOT RUN **JRV-22-001**; earliest older unresolved **JRV-04-001**. [Previous Prompt20 report](final-report-before-module21.md) preserves its original context. Overall37-module audit remains incomplete; no production-ready certificate.

## Enumerated modules

| Module | Catalog status |
| --- | --- |
{table}

## Category and tier statistics

```json
{json.dumps({k:summary[k] for k in ('by_category','by_tier')},indent=2)}
```
''',encoding='utf-8')
    files=['jarvis/coding_files.py','jarvis/codex_workload.py','tests/test_native_coding_audit.py',
        'scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py',
        'scripts/verification/verify_native_coding_audit.py','scripts/verification/report_native_coding_audit.py',
        'scripts/verification/verify_native_coding_artifacts.py','README.md','docs/native-coding.md','docs/system-map.md','../README.md']
    changed=[];pairs=[];patch=[]
    for name in files:
        current=BASE/name;old=PRE/('root-README.md' if name=='../README.md' else name.replace('/','__'))
        changed.append({'path':name,'sha256':sha(current)})
        if old.exists():pairs.append({'path':name,'before':sha(old),'after':sha(current)})
        patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],current.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name if old.exists() else '/dev/null',tofile='after/'+name))
    write('files-changed.json',json.dumps(changed,indent=2));write('source-hashes.json',json.dumps(pairs,indent=2));write('source.patch',''.join(patch))
    generated=['artifacts/jarvis-audit/'+s for s in ('final-report.md','final-report-before-module21.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt')]
    generated.extend(p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file())
    generated.extend('artifacts/jarvis-audit/modules/21-native-coding/'+s for s in ('generated-files.json','artifact-verification.json'))
    write('generated-files.json',json.dumps(sorted(set(generated)),indent=2))
    print(json.dumps({'module21':dict(Counter(r['status'] for r in cases)),'full':full,'catalog':counts},indent=2))


if __name__=='__main__':main()

