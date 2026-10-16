"""Publish executed Prompt18 evidence; no inferred passes or live-certification claims."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/18-repo-learning';PRE=BASE/'.jarvis-runtime/jarvis-audit/module18-pre'
def read(name):return json.loads((MOD/name).read_text(encoding='utf-8'))
def write(name,value):(MOD/name).write_text(value.strip()+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def stats(name):
    nodes=list(ET.parse(MOD/name).iter('testcase'))
    return {'PASS':sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in nodes),'SKIPPED':sum(n.find('skipped') is not None for n in nodes),'FAIL':sum(n.find('failure') is not None or n.find('error') is not None for n in nodes)}

def main():
    from scripts.verification import audit_catalog
    baseline=stats('baseline.xml');target=stats('cases-and-contracts.xml');full=stats('full-regression.xml')
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0
    frozen=read('full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    bench=read('benchmark-summary.json');journey=read('repository-journey.json');env=read('environment.json');ready=read('readiness.json')
    assert bench['equivalent'] and journey['passed'] and journey['network_calls']==journey['repository_code_executions']==0
    skips=[{'node':n.get('classname','')+'::'+n.get('name',''),'reason':n.find('skipped').get('message','')} for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if n.find('skipped') is not None]
    write('full-regression-skip-reasons.json',json.dumps(skips,indent=2))
    modules=json.loads((OUT/'module-map.json').read_text())
    modules[17].update(sources=['jarvis/repo_learning.py','jarvis/repo_acquisition.py','jarvis/repo_analysis.py','jarvis/repository_skills.py','jarvis/repo_tools.py','jarvis/toolkits.py','jarvis/agent_context.py','jarvis/actions.py','docs/repo-learning.md','docs/repo-abilities.md','docs/repository-skills.md'],test_candidates=['tests/test_repo_learning_audit.py','tests/test_repo_learning.py','tests/test_repo_abilities.py','tests/test_repository_skills.py','tests/test_repository_skill_isolation.py','tests/test_toolkits.py'],status='PARTIAL',reason='30 catalog fixture PASS /2 missing behavior/crash-checkpoint contracts BLOCKED; live validation separate')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-18-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':30,'BLOCKED':2}
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    write('remaining-case-ids.txt','\n'.join(r['id'] for r in catalog if r['status'] not in {'PASS','SKIPPED'}))
    counts={s:sum(r['status']==s for r in catalog) for s in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN')}
    isolation=[n for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if 'test_repository_skill_isolation' in n.get('classname','')]
    iso_pass=sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in isolation);iso_skip=sum(n.find('skipped') is not None for n in isolation)
    summary=json.loads((OUT/'summary.json').read_text());before=bench['before']['warm'];after=bench['after']['warm'];cold=bench['after']['cold']
    measured=f"Saved-memory relevance warm p50/p95 **{before['p50_ms']:.4f}/{before['p95_ms']:.4f} → {after['p50_ms']:.4f}/{after['p95_ms']:.4f} ms**, identical scores/top3 names on 500 repositories with 80 keywords each."
    scope=f'Synthetic public metadata, fake GitHub/archive/model transports and temporary vault/cache fixtures. Actual command/background worker, trusted Git init/commit/read/local snapshot and refused file-transport clone ran on owned data. Final full suite: {iso_pass} owned Docker kernel fixtures passed /{iso_skip} skipped; Docker availability changed after the initial unavailable baseline without a service-start action by this audit. No live GitHub clone, private repository/vault, native LLM/GPU, GUI/voice trial, real account write, dependency/ability installation or downloaded-third-party-code execution.'
    blockers='JRV-18-003: static symbols/test-file presence and untrusted labels do not behaviorally validate arbitrary README claims; no authorized general sandbox test oracle. JRV-18-019: completed knowledge reopens, but in-flight learning jobs have no durable checkpoint/process-crash restart contract.'
    headline=f"""**Repository-learning audit — 2026-10-16 IST:** Coding references now pin commits, verify cached excerpt hashes, restrict license-sensitive excerpt transfer, bound downloads/browser checks and screen discovery queries for private markers. Pinned duplicate learning reuses memory; corrupt indexes are preserved. {measured}
Verification: **{full['PASS']:,} full regression PASS / {full['SKIPPED']} skips**; **30 Prompt 18 catalog PASS /2 BLOCKED**. Arbitrary repository behavior validation and durable in-flight job recovery remain incomplete. Derived caching adds cold work/memory; launcher **{ready['status']}**."""
    matrix=f"""| Claim | Actual binding / active configuration | Assertion / boundary |
| --- | --- | --- |
| Coding knowledge | Actions creates RepoLearner with memory enabled; commands.parse → execute → enqueue/start/run/learn; Actions coding tasks call RepoLearner.prepare; agent_context.learned_references/reference_for feed coding_context | command→worker→knowledge/index/note→Stop→restart→offline reference journey; no model training |
| Discovery | repo_learning.search/query/pick; public GitHub metadata API | zero stays empty; malformed items rejected; real Python-Markdown/markdown identity checked through Firecrawl, authored size/star fields; no live Jarvis API census |
| Source provenance | branch resolved once via commit endpoint; archive/tree/raw URLs use40hex SHA | commit stored in index/knowledge/note/reference; old unpinned cache yields metadata only |
| Analysis | Python AST, other-language declaration regex, manifests/test paths | no source execution; model key-module paths must exist; source_trust=untrusted, executed_tests=false; tests present is not tests passed |
| Bounds | archive40MB,20k entries/tree paths, selected source12MB,400KB/file; key-file fallback45 files/2.5MB/2 fetch workers | strict whole-file read budget; pre-append streamed caps; unsafe/link/generated/minified paths excluded; truncated trees refused; parser allocations not a hard process sandbox |
| Cache/concurrency | repo-knowledge files/knowledge.json and Obsidian Jarvis Repos/index.json/notes | SHA256 snippet names/content, tamper refusal, five independent requests×20 rounds preserve identities; serialized first acquisition and duplicate reuse |
| Licensing | permissive SPDX metadata + root license artifact required for snippets | unknown/copyleft/unpinned/platform-specific code omitted; origin/SHA/license/review flag retained. Not target-license legal compatibility proof |
| Platform | SwiftUI/AppKit/Darwin/fcntl static hints | Windows review note suppresses snippets; not complete build/dependency resolution |
| Privacy | local scheduler/knowledge_worker summary; public query guard; exact parsed API token origin and no redirects | fake credentials/private email goal causes0 HTTP calls even with Groq flag; recognized credential assignments/key material redacted before model/cache; heuristic only |
| Persistence/Stop | unique atomic JSON via skill_memory.atomic; rollback a fresh-learning index row on failed canonical write; corrupt-index guard | failed save one attempt; prior index preserved; before-transport/after-model Stop checks; derived notes best effort, multi-file transaction absent |
| Browser backpressure | dwell→verification≤2 workers→queue20; learning serialized | duplicate verifier thread removed; rapid titles admit2 checks; post-Stop observe/enqueue refused; queue not durable |
| Separate executable skills | repo_acquisition/repo_analysis/repository_skills → repo_tools/toolkits | trusted Git local snapshot/unsafe file-clone refusal; missing human approval denies smoke check;final full kernel fixtures:{iso_pass} PASS /{iso_skip} skips |
| Ability proposals | existing repo_abilities on_learned callback | proposal is not install/approval; neighboring fake approval/lifecycle tests retained; no real ability installed |
| Settings | enabled/auto_browse/search_for_coding true;repos_per_task1;min_stars20;dwell8s;refresh30d;max_zip40MB;modelqwen3.5:9b | strict flags/finite bounds; stable config/tool names and manifest/launcher/recovery preserved |"""
    write('inventory.md',f"""# Prompt 18 repository-learning audit — 2026-10-16 IST

**30 PASS /2 BLOCKED /0 FAIL** offline catalog scope. Baseline {baseline}; focused {target}; full {full}. Focused run includes two catalog blockers and neighboring GPU/Docker fixture results; exact skip reasons in XML. [Commands/results](commands.txt), [32 IDs](tests.jsonl), [targeted XML](cases-and-contracts.xml), [full XML](full-regression.xml), [owned journey](repository-journey.json).

{scope}

{matrix}

{blockers}

Read actual map, repo-learning and linked repo-abilities/repository-skills docs and source/config registrations. Candidate repo_tools/toolkits bind the execution pipeline, not the multi-language reference learner. Optional integrations/repository-runtime was not rebuilt. Historical images/live counts retain dates/scope; no new visible UI/screenshot.

Order: preserve dirty audit/12-tool-registry/preimages → baseline → reproduced assertions → narrow fixes → official current upstream → equivalent A/B → targeted/privacy/permissions/concurrency → owned command/Git journey → frozen full regression and read-only launcher check → ledger/report. Existing dirty branch retained because a fresh checkout would omit user/module14–17 work. No reset/commit/install/deploy.

{measured} [50 raw samples](benchmarks.csv), [scope](benchmark-summary.json), [tradeoffs](changes.md), [upstream](compatibility.md), [rollback](rollback.md).
""")
    write('failures.md',f"""# Actual failures and remaining gates

[Baseline](baseline.xml):62 PASS /10 unavailable live skips. [Reproduction](reproduced.xml):27 FAIL /7 PASS. Case027 was missing benchmark artifact sequencing, not a product defect. Other failures exposed missing commit/validation provenance, unrestricted unknown/copyleft snippets, read-budget overshoot, repeated learning, platform/minified gaps, malformed responses, cancellation, origin-prefix credential risk, cache tamper acceptance, raw resource errors, late enqueue, invalid settings, failed-save RAM drift and missing trace/redaction contracts. Overlapping assertions are not distinct bug counts.

[First focused](targeted-first.xml):2 FAIL /43 PASS: benchmark still absent; large-repo fake commit handler overwritten by a later else. Fixed fake protocol control flow, stream/redirect kwargs, pinned raw URL and added synthetic root license. Existing error assertion now expects categorical ConnectionError instead of raw offline payload, preserving failure/readback semantics while preventing diagnostic leakage. [Second focused](targeted-second.xml):124 PASS /10 skips.

Final focused {target}; full {full}, frozen source hashes unchanged. [Exact skips](full-regression-skip-reasons.json). Later supplemental tests cover real independent concurrency, browser caps, redirects/token origin, source redaction/tamper, private queries, corrupt-index preservation and host/GPU resource faults. Case003 static labels are insufficient proof of README behavior;019 completed-record reopen is insufficient proof of in-flight crash recovery.

{blockers}

First full run:1 FAIL /2703 PASS /32 skips in437.75s. Failed full-regression-shared-state.xml and matching source hashes retained. An existing GPU test read state.json during Windows replacement and got PermissionError. Only the fixture observation now retries transient read/share/JSON states for at most1s; permanent failure remains an error. Added transient/permanent regression assertions. No lease liveness, priority assertion, action replay or production scheduler semantics changed. The accepted full rerun uses a new source freeze.

No arbitrary downloaded repository code/postinstall, live GitHub clone or ability install executed. Owned synthetic Docker isolation fixtures executed when the backend became available. Prior module acceptance gates remain separate.
""")
    write('changes.md',f"""# Retained implementation and benchmark decision

repo_learning.py: canonical name/path/settings/index/model guards; private public-search rejection and recognized credential redaction; parsed exact-origin authorization, redirects refused, response closure and streamed pre-append caps; immutable commit for archive/tree/raw; generated/minified/link/traversal exclusion; source-grounded module paths and static/untrusted labels; Windows hints; root license artifacts and conservative excerpt transfer; SHA256 cache filenames/content readback; atomic JSON, fresh-learning canonical-index RAM rollback, corrupt-index guard; serialized pinned dedupe; bounded2-worker browser checks and duplicate-thread fix; Stop guards; record/card/failure trace IDs and categorical errors. No dependency/service/config/tool-name or approval/execution-engine change.

Candidates: immutable commit pinning implemented; derived keyword-set cache improves warm relevance; existing static symbols retained; license evidence and literal transfer limits added. General sandbox behavior validation remains BLOCKED, not replaced by parsing. No embeddings/reranker/model download or arbitrary source execution. Pin resolution adds one metadata API call on first/refreshed learning; pinned duplicates avoid network. Live service latency was not measured.

{measured} Warm peak traced Python allocation {before['python_peak_bytes']}→{after['python_peak_bytes']}B. Cold p50 **{bench['before']['cold']['p50_ms']:.4f}→{cold['p50_ms']:.4f}ms**, peak **{bench['before']['cold']['python_peak_bytes']}→{cold['python_peak_bytes']}B**. Keep derived cache for repeated warm requests on32GB target; roughly4.6MB extra fixture allocation and cold slowdown explicitly retained, not called an overall speed/memory win. No privacy/approval correctness regression accepted. Query cache scales with repository keywords; warm excludes retained cache memory. Construction/disk/download/parse/model/TTFT/audio/VRAM excluded.

Test fakes now supply immutable SHA/root license/stream protocol and categorical errors; old baseline/failure XML preserved. App/root README, repo-learning and system-map updated with dated scope; existing art/attribution preserved. [Implementation/doc files](files-changed.json), [generated output paths](generated-files.json), [preimage hashes](source-hashes.json), [complete scoped diff](source.patch).
""")
    write('compatibility.md',f"""# Official current upstream — 2026-10-16 IST

Firecrawl [retrieved URLs/dates](upstream-checks.json). Installed Python{env['python']}, Requests{env['requests']}, {env['git']}. [Requests PyPI](https://pypi.org/project/requests/) lists **2.34.2,2026-05-14**, Python>=3.10: current installed version retained, implementation improved. [Official redirect/stream documentation](https://requests.readthedocs.io/en/latest/user/quickstart/#redirection-and-history) supports explicit no-redirect and response streaming.

[Git for Windows](https://git-scm.com/install/windows) lists **2.56.0(2),2026-10-05**, newer than installed2.49.1.windows.1. [Official2.56 notes](https://raw.githubusercontent.com/git/git/v2.56.0/Documentation/RelNotes/2.56.0.adoc) reviewed; no installer/system mutation under prompt boundary. Current protected CLI flags/read commands tested; no claim of current Git security level or executed2.56 compatibility. Upgrade remains maintenance work.

[GitHub commit endpoint](https://docs.github.com/en/rest/commits/commits#get-a-commit) documents SHA/ref resolution; retrieved examples show API version2026-03-10. Learner resolves once then uses immutable SHA; existing unversioned API header retained, not a broad API migration. Alternate API-version URL returned404 and was not used as proof. [GitHub licensing](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) supports withholding reuse rights without license. Permissive metadata/root-license presence gates snippets; review attribution/terms/target compatibility remains required, not a legal analyzer.

{blockers}

Limits: regex symbols are approximate; README/model purpose/how_to_run remain untrusted, no semantic behavior certificate. Exact origin/redirect refusal may reduce rename availability. Private-query/credential/PII screening is heuristic and may suppress benign search; no retroactive real-cache scrub. Normal JSON response/ZIP central-directory parsing lacks hard process RAM isolation; ZIP metadata may load before entry-count rejection. Key-file equal per-request caps can omit relevant large files; truncated trees refuse completeness. Platform hints incomplete. Hashes verify snippets, not cryptographic authenticity of all local summary/metadata; root license text is not reconciled semantically with SPDX. Old unpinned references are metadata-only; no purge/migration. Knowledge/index/Markdown are not one transaction or multi-process CAS; later note/callback failure can follow saved canonical knowledge. Stop sampled, no native kernel preemption. Derived relevance cache retained memory/cold cost explicit. Fresh-learning row rollback does not cover all legacy usage-history/forget RAM mutations before their commit. Negative-goal screening covers tested English patterns, not universal multilingual negation. Ability pipeline has independent approval/license/runtime limits.

No live GitHub/model/GPU/RAM stress/GUI/voice trial in this run. Final full owned kernel fixtures:{iso_pass} PASS /{iso_skip} skips; baseline10 were skipped when backend unavailable. No Docker start/repair performed. Resource failures use fakes, not native GPU admission certification. Prior pypdf/security/acoustic/system gates unchanged. Readiness {ready['status']}: {ready['missing']}.
""")
    write('rollback.md',"""# Scoped rollback and deterministic resume

No audit commit. Preserve inherited dirty audit/12-tool-registry and user/module14–17 changes. Compare source.patch/current hashes before manually restoring only module18 changes from ignored .jarvis-runtime/jarvis-audit/module18-pre (app paths use __; root-README.md for parent). Never reset all, regenerate old preimages, delete user data or overwrite real vault/cache. No production data migration or dependency install. Commit/hash fields additive; legacy unpinned metadata readable with snippets suppressed; never invent old commit IDs.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_repo_learning_audit.py (immutable before-source A/B).
2. scripts/verification/verify_repo_learning_journey.py (temporary command/worker/restart/coding context/trusted Git read; no downloaded source execution).
3. -m pytest tests/test_repo_learning_audit.py tests/test_repo_learning.py tests/test_repo_abilities.py tests/test_repository_skills.py tests/test_repository_skill_isolation.py tests/test_toolkits.py tests/test_audit_result_accounting.py tests/test_gpu_scheduler.py tests/test_gpu_scheduler_audit.py -q --junitxml=artifacts/jarvis-audit/modules/18-repo-learning/cases-and-contracts.xml
4. Freeze runtime/test hashes, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/18-repo-learning/full-regression.xml
5. -m jarvis.launcher --check (read-only); retain raw output locally, publish redacted readiness.json.
6. scripts/verification/report_repo_learning_audit.py; scripts/verification/verify_repo_learning_artifacts.py.

Next NOT RUN JRV-19-001; earliest older unresolved JRV-04-001. Exact remaining IDs in remaining-case-ids.txt. Module18 open003/019 require authorized sandbox behavior oracle and durable in-flight job checkpoint contract, with actual faults/crash tests. Missing live services require concrete environment; no ability install/arbitrary script/system upgrade/deployment authorized by verification commands.
""")
    for path,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/18-repo-learning/inventory.md'),(BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/18-repo-learning/inventory.md'),(BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/18-repo-learning/inventory.md'),(BASE/'docs/repo-learning.md','../artifacts/jarvis-audit/modules/18-repo-learning/inventory.md')]:
        text=path.read_text(encoding='utf-8');text=re.sub(r'\n<!-- prompt18-audit -->[\s\S]*?<!-- /prompt18-audit -->\n','\n',text)
        first,rest=text.split('\n',1);path.write_text(first+'\n\n<!-- prompt18-audit -->\n'+headline+f'\n[Evidence, limits and rollback]({link}).\n<!-- /prompt18-audit -->\n'+rest,encoding='utf-8')
    table='\n'.join(f"| {m['number']:02d} {m['module']} | "+' / '.join(f'{k}:{v}' for k,v in sorted(Counter(r['status'] for r in catalog if int(r['id'].split('-')[1])==m['number']).items()))+' |' for m in modules)
    report=f"""# Jarvis audit — Prompt18 follow-up, 2026-10-16 IST

{headline}

{scope}

[Source-map/code/config/assertion matrix](modules/18-repo-learning/inventory.md), [commands/results](modules/18-repo-learning/commands.txt), [all 32 IDs](modules/18-repo-learning/tests.jsonl), [targeted XML](modules/18-repo-learning/cases-and-contracts.xml), [full XML](modules/18-repo-learning/full-regression.xml), [owned journey](modules/18-repo-learning/repository-journey.json), [readiness](modules/18-repo-learning/readiness.json).

HEAD **{env['head']}**, dirty branch **{env['branch']}** retained, no commit, prior work preserved. [Environment](modules/18-repo-learning/environment.json): Windows/Python{env['python']}/Requests{env['requests']}/{env['git']}; target Ryzen7/32GB/RTX3050Laptop4GB. No native GPU/model/audio measurement. {len(frozen)} runtime/test hashes unchanged during acceptance. [Scoped files](modules/18-repo-learning/files-changed.json), [generated outputs](modules/18-repo-learning/generated-files.json), [preimages](modules/18-repo-learning/source-hashes.json), [full scoped diff](modules/18-repo-learning/source.patch).

Baseline {baseline}; focused {target}; full {full}. Counts overlap, not unique catalog totals. [Failure/harness history](modules/18-repo-learning/failures.md), [full skip reasons](modules/18-repo-learning/full-regression-skip-reasons.json). Command/worker/restart/coding-context/trusted-Git journey **{journey['seconds']:.3f}s**,0 real HTTP/downloaded-source executions. Owned Git fixture commit **{journey['git_fixture_commit']}** independently read/snapshotted; unsafe file clone denied. No user GUI/account/model trial.

{measured} Warm traced allocation {before['python_peak_bytes']}→{after['python_peak_bytes']}B; cold p50 {bench['before']['cold']['p50_ms']:.4f}→{cold['p50_ms']:.4f}ms, peak {bench['before']['cold']['python_peak_bytes']}→{cold['python_peak_bytes']}B. [50 raw samples](modules/18-repo-learning/benchmarks.csv), [scope](modules/18-repo-learning/benchmark-summary.json), [keep/tradeoff](modules/18-repo-learning/changes.md). Retain extra cold work/roughly4.6MB derived cache for repeated warm use on32GB target; not an overall memory/end-to-end latency win. Disk/acquisition/source parsing/model/audio/VRAM excluded. Prior module metrics retained [through17](final-report-before-module18.md).

## Open gates, upstream and risk

{blockers}

Firecrawl [official URLs/release dates](modules/18-repo-learning/upstream-checks.json), [compatibility/limits](modules/18-repo-learning/compatibility.md). Requests2.34.2(2026-05-14),Python>=3.10 already current; Git for Windows2.56.0(2)(2026-10-05) newer than installed2.49.1.windows.1, no installer. Static references do not establish arbitrary behavior, legal target-license compatibility, durable job crash resume, universal PII classification, hard parser/process RAM limits or multi-file/multi-process transactions. Existing acoustic/GPU/model/Docker/pypdf/other-module gates remain. Launcher **{ready['status']}**: {', '.join(ready['missing']) or 'no missing prerequisites reported'}; no repair/start/download attempted. No production-ready certificate.

[Rollback/resume](modules/18-repo-learning/rollback.md). Next NOT RUN **JRV-19-001**; earliest unresolved **JRV-04-001**. All 1,184 unique IDs: **{counts}**. [Exact ledger](test-results.jsonl), [tier/category totals](summary.json), [exact remaining IDs](remaining-case-ids.txt). PASS requires dedicated executed assertions; fixture evidence does not silently certify live services.

## Modules

| Module | Catalog statuses |
| --- | --- |
{table}

## Tier/category statistics

"""
    report+=chr(96)*3+'json\n'+json.dumps({k:summary[k] for k in ('by_tier','by_category')},indent=2)+'\n'+chr(96)*3+'\n'
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    files=['tests/test_gpu_scheduler.py','jarvis/repo_learning.py','tests/test_repo_learning.py','tests/test_repo_learning_audit.py','scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py','scripts/verification/verify_repo_learning_audit.py','scripts/verification/verify_repo_learning_journey.py','scripts/verification/report_repo_learning_audit.py','scripts/verification/verify_repo_learning_artifacts.py','README.md','docs/system-map.md','docs/repo-learning.md','../README.md']
    changed=[];pairs=[];patch=[]
    for f in files:
        new=BASE/f;old=PRE/('root-README.md' if f=='../README.md' else f.replace('/','__'))
        changed.append({'path':f,'sha256':sha(new)})
        if old.exists():pairs.append({'path':f,'before':sha(old),'after':sha(new)})
        patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],new.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+f if old.exists() else '/dev/null',tofile='after/'+f))
    write('files-changed.json',json.dumps(changed,indent=2));write('source-hashes.json',json.dumps(pairs,indent=2));write('source.patch',''.join(patch))
    generated=['artifacts/jarvis-audit/'+s for s in ('final-report.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt')]
    generated += [p.relative_to(BASE).as_posix() for p in sorted(MOD.iterdir()) if p.is_file()]
    generated += ['artifacts/jarvis-audit/modules/18-repo-learning/'+s for s in ('generated-files.json','artifact-verification.json')]
    write('generated-files.json',json.dumps(sorted(set(generated)),indent=2))
    print(json.dumps({'module18':dict(Counter(r['status'] for r in cases)),'full':full,'catalog':counts},indent=2))

if __name__=='__main__':main()