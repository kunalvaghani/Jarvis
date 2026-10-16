"""Reconcile actual Prompt16 assertions and publish scoped evidence, never inferred passes."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit'
MOD=OUT/'modules/16-memory'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module16-pre'


def read(name):return json.loads((MOD/name).read_text(encoding='utf-8'))
def write(name,text):(MOD/name).write_text(text.strip()+'\n',encoding='utf-8')
def stats(name):
    rows=list(ET.parse(MOD/name).iter('testcase'))
    return {'PASS':sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in rows),
        'SKIPPED':sum(n.find('skipped') is not None for n in rows),
        'FAIL':sum(n.find('failure') is not None or n.find('error') is not None for n in rows)}


def main():
    from scripts.verification import audit_catalog
    baseline=stats('baseline.xml');targeted=stats('cases-and-contracts.xml');full=stats('full-regression.xml')
    assert baseline['FAIL']==targeted['FAIL']==full['FAIL']==0
    frozen=read('full-start-source-hashes.json')
    assert all(hashlib.sha256((BASE/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
    bench=read('benchmark-summary.json');journey=read('memory-journey.json');ready=read('readiness.json');environment=read('environment.json')
    assert bench['equivalent'] and journey['passed']
    assert read('durability-reproduction.json')['passed']
    modules=json.loads((OUT/'module-map.json').read_text())
    modules[15]['sources']=['jarvis/memory_curator.py','jarvis/conversation_memory.py','jarvis/obsidian_memory.py','jarvis/skill_memory.py','jarvis/experience_memory.py','jarvis/experience.py','jarvis/memory_index.py','jarvis/context_hub.py','docs/memory-apis-alerts.md','docs/cognitive-architecture.md']
    modules[15]['test_candidates']=['tests/test_memory_audit.py','tests/test_memory_weather.py','tests/test_obsidian_memory.py','tests/test_memory_index.py','tests/test_skill_memory.py','tests/test_experience_memory.py','tests/test_experience.py','tests/test_knowledge.py']
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-16-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':28,'BLOCKED':4}
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    write('remaining-case-ids.txt','\n'.join(r['id'] for r in catalog if r['status'] not in {'PASS','SKIPPED'}))
    observed=Counter(r['status'] for r in catalog)
    counts={status:observed[status] for status in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN')}
    summary=json.loads((OUT/'summary.json').read_text())
    before=bench['before']['warm'];after=bench['after']['warm']
    scope='Temporary synthetic vaults/SQLite databases, actual file/FTS transaction readback, deterministic model/network fakes. No real vault, personal conversation, Obsidian GUI, cloud account, native LLM/GPU, microphone or external effect was exercised.'
    blockers='JRV-16-004: no cross-store erase/tombstone protocol; fact forgetting does not purge SQLite, summaries/Daily notes or stop paraphrased rehydration. JRV-16-006: no durable unavailable-vault outbox; the bounded model-job queue is not write recovery. JRV-16-011: no general document-versus-memory freshness reconciliation. JRV-16-032: errors are categorical but memory lifecycle operations lack end-to-end correlation IDs.'
    write('inventory.md',f'''# Prompt16 memory audit — 2026-10-16 IST

**28 catalog PASS / 4 BLOCKED / 0 FAIL.** Baseline {baseline['PASS']} PASS; targeted {targeted['PASS']} PASS / {targeted['SKIPPED']} explicit blocker skips; full {full['PASS']} PASS / {full['SKIPPED']} skips. [Catalog assertions](tests.jsonl), [targeted XML](cases-and-contracts.xml), [full XML](full-regression.xml), [actual user journey](memory-journey.json).

{scope}

| Source-map claim | Real binding/configuration | Assertion / boundary |
| --- | --- | --- |
| Durable user facts | memory_curator.parse_command/execute → add/forget → version1 JSON and regenerated Markdown; memory.long_term.enabled=true, learn_facts=true, summarize=true, max_facts500, idle15min | command→canonical readback→reopen→local answer; fsync before replace, precommit failure restores RAM; postcommit derived-note failure retains committed fact |
| Identity/corrections | subject and preference_slot guards before existing lexical overlap | tested explicit simple prefers correction; different named subjects/polarity preserved. Not general semantic entity resolution/conflict arbitration |
| Episodic sessions | Knowledge.attach_conversations → ConversationMemory: sessions/turns/FTS5, timeout1s, connection transaction context | pending/cancelled excluded from recall; temporary exclusive DB lock released then single commit; duplicate finish replaces one FTS row; real reopen |
| Sensitive data | shared obsidian_memory.SENSITIVE + clean; curator.safe; begin/finish import shared matcher | OTP/card/credential fixture markers redacted before clipping and SQLite indexing. Heuristic only, no retroactive real-history scrub |
| Corrupt/legacy store | curator.load caps JSON, validates shapes, skips invalid facts; valid legacy missing-version JSON accepted as version1 | corrupt canonical preserved, new writes require review; malformed model output ignored with categorical error; no new SQL schema/migration |
| Procedural learning | SkillMemory verified records, scoped guides; ExperienceMemory bounded cases and verification scope | existing procedure/case regression assertions, source/payload restrictions and no uncertain replay retained |
| Hotness/decay | experience.hotness/hotness_many cached ISO parse + existing numpy vector path | vector/scalar same for50 mixed stamps; no new vector framework or model download |
| Retrieval | curator.relevant + Obsidian.recall + memory_index; context_hub/Brain/Knowledge consume bounded references | query terms/scoring computed once, identical top8 on500-fact A/B; recent fallback preserved. Existing incremental index remains; no semantic reranker added without benefit proof |
| Idle/Stop | existing background queue max50 and40 current turns; GPU scheduler background inference outside fact lock | typing while fake summary waits remains under100ms; closed observer rejects new jobs, in-flight extraction drops output after Stop; no claim of preempting native model kernels |
| Erase/offline/freshness/traces | partial or missing contracts | {blockers} |

Order: read actual map and linked memory/cognitive docs, preserve dirty audit branch/source preimages, baseline, reproduce, narrow fixes, equivalent A/B, targeted/neighbors/privacy, synthetic command journey, final frozen full run, read-only launcher check, ledger reconciliation. Existing dirty audit/12-tool-registry retained to preserve inherited user/module14–15 diffs; no commit/reset/refactor/new service/dependency/model download. Active manifest/launchers remain compatible through full regression/readiness.

Measured warm p50/p95 **{before['p50_ms']:.4f}/{before['p95_ms']:.4f}→{after['p50_ms']:.4f}/{after['p95_ms']:.4f}ms**; peak traced Python allocation **{before['python_peak_bytes']}→{after['python_peak_bytes']}B**. Small allocation increase retained for faster equivalent results; [50 raw samples](benchmarks.csv), [scope](benchmark-summary.json). Five cold objects are fresh RAM state, not disk startup. No model/voice/VRAM timing claim.

[Paired durability fault proof](durability-reproduction.json): old preimage RAM differed from canonical disk after the injected replacement failure; fixed RAM matched disk. Both made exactly one attempt. Script: scripts/verification/verify_memory_durability.py.

Launcher **{ready['status']}**: [redacted actual result](readiness.json). [Limits/upstream](compatibility.md), [fixes](changes.md), [failure history](failures.md), [rollback/resume](rollback.md).
''')
    write('failures.md','''# Actual failures and fixes

[First dedicated run](reproduced.xml):15 FAIL /19 PASS /2 BLOCKED skips. Twelve failures represented eight runtime/design families: simple explicit preference correction(002), people merged by fuzzy overlap(003), narrower episodic/clean secret screening(005), malformed persisted facts(008 three variants), malformed model fact results(015 three variants), observe after close(018), invalid capacity/flags/NaN idle config(029), unbounded explicit fact(031).

Three initial failures were harness setup, not runtime defects:011 imported nonexistent question_client.payload,021 patched nonexistent knowledge_worker.cloud_answer,027 benchmark artifact not yet generated. Corrected to an explicit missing-freshness blocker, forbidden real network transport and actual A/B output. Not counted as product fixes. 004/006 were already blocked;032 was later honestly blocked because categorical errors alone do not prove lifecycle correlation.

Additional safe fixes: canonical JSON flushed/fsynced before replace; precommit add/forget failure restores RAM and never retries the action, committed facts retained if a later Markdown write fails; unreadable/corrupt canonical not overwritten; full text screened before truncation; summary inputs filtered before model payload; a stopped curator drops a later model extraction/summary result. Existing entity/negation tests retain evidence rather than invent semantic arbitration.

durability-reproduction.json independently executes old saved source and current code against the same injected Path.replace failure: before RAM/disk diverges, after matches, one commit attempt in both. This is an additional reproduced defect beyond the initial eight families.

The first full command never executed because automatic approval review hit an account usage limit. After user continuation a full run started; it was deliberately stopped at about16% when the final Stop/readback guard and honest032 blocker were added. That partial run is not acceptance. The final full-regression.xml and frozen source hashes are authoritative; no source/test changes during that accepted run. Initial failures remain retained, not overwritten with passing XML.

The next full run exposed an existing paused-adapter compatibility failure: observe read self.closed before the paused short-circuit on a lightweight adapter. Pause now returns before lifecycle access. The failed full XML is retained as full-regression-paused-adapter.xml; the corrected focused suite includes tests/test_intent_testbook.py::CuratorTests, followed by a fresh full rerun. No privacy/approval assertion was relaxed.
''')
    write('changes.md',f'''# Retained bounded memory changes

memory_curator.py: strict capacity/idle/boolean and fact-size/Unicode bounds; bounded schema checks for canonical facts/summaries and model output; invalid facts excluded with categorical diagnostics and corrupt/unreadable canonical write guard; named-subject/polarity separation and narrow explicit prefers replacement; scoring once per fact/query; fsync before canonical replace, RAM rollback on failed precommit, preserve RAM after canonical commit even if derived note fails; observe after close and post-model Stop guards; sensitive summary inputs removed before local model call; diagnostic worker exceptions omit message payload.

obsidian_memory.py: shared credential matcher extended to OTP/PIN/CVV/account/card markers and long digit strings, scanning before clipping. This applies to conversation begin/finish/FTS, activity/experience/procedure clean helpers and curator checks through existing imports. Wider screening can over-redact benign words such as PIN; full regression determines compatibility. Existing historical stored text is not rewritten.

No new schema, DB, service, API, paid dependency, vector index, embedding model or arbitrary action graph. SQLite schema/transaction behavior unchanged and directly tested. Learned memories remain guidance under registry permissions; no external effects/replay added. Existing hotness_many already vectorized; kept with equivalence assertion. Lexical optimization retained: warm median {before['p50_ms']:.4f}→{after['p50_ms']:.4f}ms, +{after['python_peak_bytes']-before['python_peak_bytes']}B peak traced allocations on bounded fixture; exact selected results unchanged.

Exact changed files/hashes and preimages: files-changed.json / source-hashes.json; complete scoped new/modified diff: source.patch. app/root README and memory/system docs updated in the same change, preserving dated screenshots/historical measurements. No visible UI change/new screenshot. No commit/deploy/install.
''')
    write('compatibility.md',f'''# Upstream and compatibility — 2026-10-16 IST

Observed Python{environment['python']} / bundled SQLite{environment['sqlite']}; FTS5 compiled and exercised in real temporary DBs. Firecrawl fetched official [SQLite release history](https://sqlite.org/changes.html): current listed **3.54.0,2026-10-09**; [fresh maxAge0 confirmation](sqlite-release-fresh.json). Bundled3.37.2 is older, not called latest. Replacing Python's native SQLite binary or installing a new interpreter/package is outside this prompt's no-install boundary. Retained existing supported parameterized SQL, FTS5 and transaction context semantics; no unverified native upgrade, claim of current security patch level or SQL migration. Upstream/current runtime disparity remains a maintenance risk. [Actual retrieved excerpts](upstream-checks.json).

Official [Python3.10 sqlite3 documentation](https://docs.python.org/3.10/library/sqlite3.html) confirms explicit transaction commit/rollback and connection busy timeout. Fixture uses an exclusive lock then releases it within existing1s timeout; no extra application-level transaction replay. Finish+FTS replacement are one transaction. Python connection initialization/version1 JSON reopen tested; arbitrary older/future DB schema migration is not certified.

{blockers}

Additional limits: canonical facts and regenerated Markdown/summary index are not a multi-file transaction; a derived failure can follow a committed fact and is never automatically replayed. No durable outbox or multi-process compare-and-swap; five writers tested on one locked curator instance. Stop checks occur at sampled boundaries, not an atomic transaction coupling Stop with filesystem commit. Fuzzy/subject/negation rules cover tested English forms, not implicit people, multilingual coreference, arbitrary mutually exclusive facts or model hallucination. Shared secret screening is heuristic, not universal PII detection; no real vault/history scrub performed. Historical summaries/profiles/Daily notes may retain prior content; fact forgetting is not global erase. Local Qwen extraction quality, Obsidian GUI, real account data and long/resource/native-GPU soak not tested. Closing with pending summary may still wait for its bounded local model call; active kernels cannot be forcibly preempted. Four catalog blockers remain open, not waived for performance.
''')
    write('rollback.md','''# Rollback and resume

No audit commit. Preserve inherited dirty branch audit/12-tool-registry. Scoped preimages in ignored .jarvis-runtime/jarvis-audit/module16-pre (app relative paths use __; root README named root-README.md). Compare source-hashes.json with current files and review source.patch before manually restoring only these changes; never git reset/restore all changes. No production memory data altered, no schema migration/dependency rollback. Keep any later user edits; do not delete personal files or overwrite real vaults from fixtures.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_memory_audit.py uses the preserved preimage, never regenerate a baseline from upgraded source.
2. scripts/verification/verify_memory_journey.py uses temporary vault/SQLite and forbids network, authored local response.
3. -m pytest tests/test_memory_audit.py tests/test_memory_weather.py tests/test_obsidian_memory.py tests/test_memory_index.py tests/test_skill_memory.py tests/test_experience_memory.py tests/test_experience.py tests/test_knowledge.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/16-memory/cases-and-contracts.xml
4. -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/16-memory/full-regression.xml (capture matching source hashes before run).
5. -m jarvis.launcher --check; preserve raw output locally, publish only redacted readiness status.
6. scripts/verification/report_memory_audit.py after source-freeze validation and saved readiness JSON.

No account write, erase of user data, credentials, package/interpreter/model install, service start or external action is authorized by this verification. For blockers design/verify scoped erase, durable outbox, document provenance/freshness and correlated lifecycle contracts in fixtures before any real-vault migration/erase. All exact remaining IDs in remaining-case-ids.txt. Next NOT RUN JRV-17-001; earliest older unresolved JRV-04-001.
''')
    headline=f'''**Memory audit — 2026-10-16 IST:** Bounded record/model validation, conservative subject/polarity guards, broader secret screening before clipping and Stop/readback guards added. Canonical facts flush before replacement; failed precommit restores RAM. Equivalent500-fact lexical retrieval warm median {before['p50_ms']:.2f}→{after['p50_ms']:.2f}ms with a small temporary allocation increase.
Verification: **{full['PASS']:,} full regression PASS / {full['SKIPPED']} skips**; **28 Prompt16 catalog PASS /4 BLOCKED**. Global erase, durable unavailable-vault writes, general document freshness and memory lifecycle correlation remain incomplete. Launcher **{ready['status']}**; real vault/model/Obsidian GUI were not tested.'''
    for path,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/16-memory/inventory.md'),(BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/16-memory/inventory.md'),(BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/16-memory/inventory.md'),(BASE/'docs/memory-apis-alerts.md','../artifacts/jarvis-audit/modules/16-memory/inventory.md')]:
        s=path.read_text(encoding='utf-8');s=re.sub(r'\n<!-- prompt16-audit -->[\s\S]*?<!-- /prompt16-audit -->\n','\n',s)
        first,rest=s.split('\n',1);path.write_text(first+'\n\n<!-- prompt16-audit -->\n'+headline+f'\n[Evidence, limits and rollback]({link}).\n<!-- /prompt16-audit -->\n'+rest,encoding='utf-8')
    table='\n'.join(f"| {m['number']:02d} {m['module']} | "+' / '.join(f'{k}:{v}' for k,v in sorted(Counter(r['status'] for r in catalog if int(r['id'].split('-')[1])==m['number']).items()))+' |' for m in modules)
    report=f'''# Jarvis audit — Prompt16 follow-up, 2026-10-16 IST

{headline}

{scope}

[Source-map/code/config/assertion matrix](modules/16-memory/inventory.md), [all32 IDs](modules/16-memory/tests.jsonl), [full XML](modules/16-memory/full-regression.xml), [targeted XML](modules/16-memory/cases-and-contracts.xml), [actual command journey](modules/16-memory/memory-journey.json), [readiness](modules/16-memory/readiness.json).

Repo HEAD **{environment['head']}**, retained branch **{environment['branch']}**, no audit commit, inherited user/module14–15 diffs preserved. [Machine/Python/SQLite environment](modules/16-memory/environment.json). Windows/Ryzen7/32GB/RTX3050Laptop4GB target; actual host/package inventory recorded, no GPU stress claim. {len(frozen)} source/test hashes unchanged during final run. [Exact files](modules/16-memory/files-changed.json), [complete scoped diff](modules/16-memory/source.patch), [preimage hashes](modules/16-memory/source-hashes.json). Existing manifest/launchers/recovery interfaces compatible, no dependency/service/config changes.

Baseline **{baseline['PASS']} PASS**; targeted **{targeted['PASS']} PASS /{targeted['SKIPPED']} BLOCKED skips**. Actual failure history and three harness corrections [retained separately](modules/16-memory/failures.md). Initial review-limit attempt never executed; a superseded partial full run was stopped when final guards changed. Accepted final full0FAIL; skips explicit in XML. Counts overlap and are not unique catalog sums.

Warm retrieval p50/p95 **{before['p50_ms']:.4f}/{before['p95_ms']:.4f}→{after['p50_ms']:.4f}/{after['p95_ms']:.4f}ms**, peak Python allocations **{before['python_peak_bytes']}→{after['python_peak_bytes']}B**. Five fresh objects/20warm lookups per version, identical500facts/returnedtop8, no output change. [50raw samples](modules/16-memory/benchmarks.csv), [cold/warm scope](modules/16-memory/benchmark-summary.json), [keep/tradeoff](modules/16-memory/changes.md). Not disk startup, total task latency, TTFT/audio or VRAM. Command/restart/SQLite journey **{journey['seconds']:.3f}s**, authored local chat and network forbidden, not live inference. Prior module metrics preserved [through15](final-report-before-module16.md).

Firecrawl [official URLs/release dates](modules/16-memory/upstream-checks.json), [compatibility/risk](modules/16-memory/compatibility.md): installed SQLite3.37.2/Python3.10.6, upstream listed3.54.0(2026-10-09); no unapproved native/dependency installation. Existing standard transaction/FTS contracts tested; old bundled engine is not certified latest/security current.

## Open gates and risk

{blockers}

No universal entity/conflict/PII/semantic retrieval proof, global erase, durable offline migration, multi-file/multi-process transaction or whole-system production certificate. Legacy private notes not rewritten. Closing pending summary can wait for bounded model work. No live Obsidian/account/native-model/resource soak. Existing earlier acoustic/native9b/GPU/PDF/browser/plugin acceptance gates remain separate. Memory text is data, not execution or approval; no uncertain action replay added. [Rollback and deterministic resume](modules/16-memory/rollback.md).

1184 unique catalog IDs: **{dict(counts)}**. [Exact ledger](test-results.jsonl), [tier/category totals](summary.json), [all remaining IDs](remaining-case-ids.txt). Next NOT RUN **JRV-17-001**; earliest unresolved **JRV-04-001**.

## Modules

| Module | Exact catalog counts |
| --- | --- |
{table}

## Tier/category statistics

```json
{json.dumps({k:summary[k] for k in ('by_tier','by_category')},indent=2)}
```
'''
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    files=['jarvis/memory_curator.py','jarvis/obsidian_memory.py','scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py','tests/test_memory_audit.py','scripts/verification/verify_memory_audit.py','scripts/verification/verify_memory_journey.py','scripts/verification/verify_memory_durability.py','scripts/verification/report_memory_audit.py','scripts/verification/verify_memory_artifacts.py','README.md','docs/system-map.md','docs/memory-apis-alerts.md']
    paths=files+['../README.md'];changed=[];pairs=[];patch=[]
    for f in paths:
        new=BASE/f;old=PRE/('root-README.md' if f=='../README.md' else f.replace('/','__'))
        changed.append({'path':f,'sha256':hashlib.sha256(new.read_bytes()).hexdigest()})
        if old.exists():
            pairs.append({'path':f,'before':hashlib.sha256(old.read_bytes()).hexdigest(),'after':changed[-1]['sha256']})
        patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],new.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+f if old.exists() else '/dev/null',tofile='after/'+f))
    write('files-changed.json',json.dumps(changed,indent=2));write('source-hashes.json',json.dumps(pairs,indent=2));write('source.patch',''.join(patch))
    print(json.dumps({'module16':dict(Counter(r['status'] for r in cases)),'full':full,'catalog':dict(counts)},indent=2))


if __name__=='__main__':main()
