"""Publish Prompt 17 evidence from executed XML, immutable preimages and exact catalog IDs."""
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
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/17-rag-documents'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module17-pre'


def read(name):return json.loads((MOD/name).read_text(encoding='utf-8'))
def write(name,value):(MOD/name).write_text(value.strip()+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def stats(name):
    nodes=list(ET.parse(MOD/name).iter('testcase'))
    return {'PASS':sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in nodes),
            'SKIPPED':sum(n.find('skipped') is not None for n in nodes),
            'FAIL':sum(n.find('failure') is not None or n.find('error') is not None for n in nodes)}


def main():
    from scripts.verification import audit_catalog
    baseline=stats('baseline.xml');target=stats('cases-and-contracts.xml');full=stats('full-regression.xml')
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0
    full_seconds=sum(float(s.get('time','0')) for s in ET.parse(MOD/'full-regression.xml').iter('testsuite'))
    skips=[{'node':n.get('classname','')+'::'+n.get('name',''),'reason':n.find('skipped').get('message','')}
           for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if n.find('skipped') is not None]
    write('full-regression-skip-reasons.json',json.dumps(skips,indent=2))
    frozen=read('full-start-source-hashes.json')
    assert all(sha(BASE/p)==h for p,h in frozen.items())
    bench=read('benchmark-summary.json');journey=read('document-journey.json');env=read('environment.json');ready=read('readiness.json')
    assert bench['equivalent'] and journey['passed'] and journey['external_effect_calls']==0
    modules=json.loads((OUT/'module-map.json').read_text())
    modules[16]['sources']=['jarvis/documents.py','jarvis/file_drop.py','jarvis/actions.py','jarvis/commands.py','jarvis/buddy_engine.py','jarvis/island_buddy.py','docs/file-buddy.md','config/config.json','config/runtime_manifest.json','requirements/runtime.txt']
    modules[16]['test_candidates']=['tests/test_rag_documents_audit.py','tests/test_documents.py','tests/test_buddy.py']
    modules[16]['status']='PARTIAL';modules[16]['reason']='28 catalog fixture PASS; 4 missing correctness/resource/trace contracts BLOCKED; live model/account acceptance separate'
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-17-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':28,'BLOCKED':4}
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    write('remaining-case-ids.txt','\n'.join(r['id'] for r in catalog if r['status'] not in {'PASS','SKIPPED'}))
    counts={s:sum(r['status']==s for r in catalog) for s in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN')}
    summary=json.loads((OUT/'summary.json').read_text())
    before=bench['before']['warm'];after=bench['after']['warm']
    scope='Synthetic PDF/DOCX/text, fake local model/HTTP/account transports, temporary session/index readback. Actual owned Tk WM_DROPFILES and child event-loop regression fixtures ran; no Explorer drag, real document/account, live model/GPU, microphone or Obsidian trial.'
    blockers='JRV-17-003: the answer API selects one document; no cross-document conflict arbitration. JRV-17-005: extracted text is capped, but pypdf parses page streams in-process without a hard RAM/time sandbox. JRV-17-012: valid page numbers do not establish semantic entailment; a fake wrong date with a valid page passes. JRV-17-032: document/model/spill operations lack unified redacted operation trace IDs.'
    measured=f"Warm BM25 lookup p50/p95 **{before['p50_ms']:.4f}/{before['p95_ms']:.4f} → {after['p50_ms']:.4f}/{after['p95_ms']:.4f} ms** on 1,500 identical chunks; top5 IDs/pages/text identical; scores match to 10 decimal places."
    headline=f"""**Document audit — 2026-10-16 IST:** Bounded extraction/context, multilingual tokenization, stale-source checks, atomic session writes and drop admission guards added. {measured}
Verification: **{full['PASS']:,} full regression PASS / {full['SKIPPED']} skips**; **28 Prompt 17 catalog PASS /4 BLOCKED**. Cross-document conflicts, semantic citation faithfulness, hard parser resource isolation and operation traces remain incomplete. Launcher **{ready['status']}**. Installed pypdf 6.20.0 predates the 6.20.1 cyclic-tree security fix; no dependency installation performed."""
    write('inventory.md',f'''# Prompt 17 document audit — 2026-10-16 IST

**28 PASS /4 BLOCKED /0 FAIL** catalog classifications, fixture scope only. Existing baseline {baseline['PASS']} PASS /2 native tests deselected; final targeted {target['PASS']} PASS /{target['SKIPPED']} explicit blocker skips; full {full['PASS']} PASS /{full['SKIPPED']} skips. [32 IDs/assertions](tests.jsonl), [targeted XML](cases-and-contracts.xml), [full XML](full-regression.xml).

{scope}

| Advertised/source-map claim | Actual binding/configuration | Evidence and boundary |
| --- | --- | --- |
| Drop file and ask | Actions constructs documents.Library; file_drop.handle → prepare → choice → ask_about/add; doc_ask parse/execute and Actions._answer_document route to Library.answer | actual scripted drop→command→spill→end→restart→load [journey](document-journey.json); owned native WM_DROPFILES tests; real send/draft remain fakes |
| Extraction | PDF pypdf 6.20.0; DOCX zip/XML text; text/HTML bounded reads | exact returned-character/page caps; ZipInfo expansion guard; scanned blank PDF honest no-text; embedded image not inferred. No OCR/complex PDF semantic table reconstruction |
| Chunking | paragraph/page-aware1200 chars, bounded overlap | invalid size/overlap rejected; carry-over no longer exceeds chunk budget; page identity retained |
| LightRAG/GraphRAG | own BM25 + entity co-occurrence; optional local model graph enrichment | NOT upstream libraries, no embeddings/reranker download. Graph names grounded in document text; relation meaning/descriptions still model supplied |
| Active settings | documents.enabled=true, model=qwen3.5:9b, graph_threshold_chars=40000, graph_max_chunks=12, focus_minutes=30 | config validation for booleans, numeric bounds, finite focus. Manifest/requirements retain pypdf 6.20.0; no new service/dependency |
| Retrieval | terms/Document.search/context, precomputed IDF and postings | identical ranked top5 on1500-chunk A/B, scores compared to 10 decimal places; Gujarati/Devanagari combining marks preserved; tested short-question negation sent to model (payload clips at600 chars); lexical English STOP still removes not/no |
| Incremental identity | SHA256 content-derived16hex ID before/after parsing and prepare; session focus updates | changed file rejects stale answer before/after generation; updated file fully rebuilds index, not incremental per-page vector update. Historical disk versions retained |
| Persistence/concurrency | session JSON, per-document index, catalog JSON, optional Markdown note; unique-temp skill_memory.atomic under write lock | crash/reopen, malformed chunks/path IDs, five concurrent documents preserve catalog entries; one spill attempt on failure. Not a multi-file/multi-process transaction |
| Local/private boundary | Library._chat → knowledge_worker.chat configured local model | transport fake asserts local qwen3.5:9b; no requests in offline ingestion/journey. Content remains untrusted data, no executable capability in retrieval; no universal privacy proof for unrelated adapters |
| Citation/absence | supplied excerpt page membership, absent lexical/graph evidence returns no-find before model | invalid p99 refused, page2 grounded authored fixture works; general entailment and graph-only negative answers unproved |
| Drop backpressure | global2-slot nonblocking admission, serialized FLOW_LOCK; native queue8, poll8/frame | ten starts create<=2 threads; excess start visibly refused. Native overflow counted internally, not displayed; direct add/background summary threads not globally bounded |
| Stop/fault | post-model stop/stale checks; no question append on timeout/Stop/stale | sampled boundary checks, no hard cancellation of native model kernel; writes after uncertain failure never automatically replayed by these paths |
| Missing contracts | {blockers} | blocked tests execute prerequisite readback before explicit skip; skips are not passing assertions of missing behavior |

Read actual system map, full file-buddy guide and real source/config registrations. Candidate jarvis/native_tools.py and memory_curator.py do not implement document retrieval; old file_knowledge candidate modules do not exist. Buddy rendering/brain regressions retained, no visible artwork change/new screenshot. Existing README rendered images and historical live measurements remain dated.

Order: preserve inherited dirty branch/preimages → existing baseline → reproduce → focused fixes → exact A/B → targeted/native/accounting → synthetic journey → source-frozen full run with parallel read-only launcher check → ledger/report. No new branch/reset: audit/12-tool-registry already held user/module14–16 work. No commit/install/send/deploy/real-vault mutation.

{measured} Lookup excludes construction, parsing, hashing, enrichment/model/audio and GPU. [50 raw samples](benchmarks.csv), [scope/cold/warm](benchmark-summary.json), [tradeoffs](changes.md), [official compatibility](compatibility.md), [rollback](rollback.md).
''')
    write('failures.md',f'''# Reproduced failures and open gates

Existing [baseline](baseline.xml):30 PASS /2 native deselected. Initial [dedicated reproduction](reproduced.xml):17 FAIL /16 PASS /3 BLOCKED skips. One failure027 was harness sequencing (benchmark artifact not generated), not a runtime defect.

Reproduced runtime/design failures included absent-query model invention, extraction cap overshoot, unbounded drop threads, ASCII-only multilingual lookup, malformed graph mutation (three variants), graph-invented entity, Unicode term splitting, file changes during extraction, context budget overflow, size0 chunk/config handling, DOCX expansion, graph API shape handling. Consult exact node traces in XML; overlapping tests are not distinct bug counts.

[First targeted](targeted-first.xml):3 FAIL /44 PASS /3 skips /3 deselected. Indic mark characters still split, graph stopword entity The defeated absent-query filtering, and a model fixture returned Claire Martin for chunks not containing that name. Fixed token grouping/stopword-only neighbourhood lookup; graph entity provenance now points to actual matching source chunks across the document. It does not establish semantic relation truth. [Second targeted](targeted-second.xml):47 PASS /3 skips /3 deselected.

Final [targeted](cases-and-contracts.xml):{target['PASS']} PASS /{target['SKIPPED']} BLOCKED skips. Case005 changed from an insufficient cap-only pass to explicit BLOCKED: a character count assertion is not hard parser-memory isolation. Simple table assertion strengthened to match each row's label and value, without certifying merged/positioned tables. Supplemental faults cover stale generation, five parallel commits, malformed persisted chunks and eight-per-frame dispatch. Accepted [full suite](full-regression.xml):{full['PASS']} PASS /{full['SKIPPED']} skips /0FAIL in{full_seconds:.2f}s; source/test hashes unchanged during acceptance. [Exact skip reasons](full-regression-skip-reasons.json).

{blockers}

First full run:1 FAIL /2652 PASS /40 skips in405.92s; the new page gate rejected the established [page1] citation spelling. [Failed full XML](full-regression-citation-format.xml) and its matching source hashes are preserved. Restored bracketed page-number support while retaining supplied-page membership checks for both spellings; added invalid bracketed citation regression, reran phase2 neighbors and a fresh frozen full suite. No assertion relaxed or failed evidence overwritten.

These are missing production contracts, not waived failures. Semantic faithfulness can be reproduced by a wrong99December answer citing valid page2; no independent entailment oracle introduced. Security maintenance gate: installed pypdf 6.20.0 lacks upstream6.20.1 cyclic-tree handling fix; no hostile native-parser exploit or installation was run. Earlier acoustic/GPU/account gates remain separate; final targeted run also includes phase2 fixtures and its seven live acceptance gate skips.
''')
    write('changes.md',f'''# Retained changes and upgrade evaluation

documents.py: strict extraction/chunk/config/model/index/input bounds; Unicode NFC/casefold token grouping including combining marks; postings/IDF candidate lookup; stopword-only entity filter; source identity checked around parse/prepare/model; stale same-path RAM index replaced; unique atomic session/index writes and locked catalog read-modify-write; conservative model graph schema/name grounding and real chunk provenance; exact excerpt budgets; stop/invalid citation/answer guards and200-question cap.

file_drop.py: two admitted flow threads globally, nonblocking refusal, existing serialized questions preserved; native callback queue8/poll8 cap; categorical async diagnostics. No Tk call inside native callback. No changes to send/draft approval semantics, service start/recovery, file deletion or action retry.

{measured} Retain postings candidate pruning: scores equal to 10 decimal places, order/output unchanged on fixture and regression suite passes. Warm lookup peak traced temporary allocations {before['python_peak_bytes']}→{after['python_peak_bytes']} bytes; cold lookup2126→2854 bytes. This excludes persistent postings/IDF memory (additional per-term dictionary/list storage), construction overhead, PDF native parser peak and end-to-end model latency. No claim of overall memory reduction or faster spoken answer. A/B benchmark against exact saved preimage, not reconstructed old code.

Upgrade candidates evaluated: existing paragraph/page chunking retained with hard size guards; semantic embeddings, reranking and hierarchical indexes deferred because no local approved embedding/reranker dependency or accuracy/resource baseline exists. Existing lexical+graph hybrid retained, with model names grounded and stopword-only graph hits excluded; no universal relevance/precision estimate from a tiny authored fixture. Incremental update remains full content rehash/reparse for changed source, safer version identity but extra read cost. Citation page-membership gate retained; semantic verification and cross-file arbitration remain blocked. These choices avoid unmeasured model/GPU additions on4GB target.

No dependency/config/manifest/launcher/schema installation or model download. Existing pypdf security disparity remains a release gate, not called current. Exact diff/hashes/files in source.patch/source-hashes.json/files-changed.json. App/root README, system-map and file-buddy docs updated with dated scope; all prior images/attribution retained.
''')
    write('compatibility.md',f'''# Official upstream checks — 2026-10-16 IST

Firecrawl retrieved official sources, [structured findings](upstream-checks.json). Installed Python{env['python']} / pypdf{env['pypdf']}. [PyPI](https://pypi.org/project/pypdf/) lists **6.20.1,2026-10-12**, Python>=3.9, compatible interpreter requirement. [Official6.20.1 release](https://github.com/py-pdf/pypdf/releases/tag/6.20.1) includes cyclic-tree security handling (#4188) and default-appearance color parsing fix (#4158). Installed6.20.0 is older and lacks that release fix. Prompt explicitly forbids dependency installation as test side effect; no package/pin was silently upgraded. Review/install/test that patch separately before treating untrusted PDF processing as production-ready. Current tests validate installed6.20.0 behavior only.

[pypdf extraction documentation](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) states full page streams are parsed, potentially using substantial memory; no OCR or guaranteed semantic table structure. Our strict output cap does not sandbox that native/library work. Blank scan fixture reports unreadable, embedded DOCX image content is never invented. Simple text rows only, not arbitrary table fidelity.

For comparison, official [LightRAG latest v1.5.7](https://github.com/HKUDS/LightRAG/releases/tag/v1.5.7) displays September2 (2026 inferred from current page relative date); [Microsoft GraphRAG v3.3.0](https://github.com/microsoft/graphrag/releases/tag/v3.3.0) October8,2026. Neither is installed/called in this pipeline. Jarvis's own BM25/entity co-occurrence code has no upstream library version to upgrade; adopting them would add model/storage/dependency requirements with no measured4GB benefit. No paid API requirement added.

{blockers}

Other limits: PDF/HTML/text cap may omit later relevant sections; lexical paraphrases/coreference/negation and generated graph relations can be wrong; regex page syntax only, not all citation formats. Missing source file allows historical cached answers; existing file hash checks are sampled and not atomic against concurrent replacement. Content-hash identity shortened16hex, no new collision proof. Cache invalidation preserves historical disk indexes/notes; no erase or incremental page delta. Persistence across index/catalog/Markdown isn't transactional, nor multi-process CAS; individual writes atomic but uncertain failure not replayed. Raw malformed nested graph/legacy metadata shapes beyond tested chunk schema aren't fully certified. Recovery spill loading lacks hard parser process isolation. Drop native overflow is internal telemetry only; direct add summary workers can still accumulate. Stop checks do not forcibly preempt kernels. No general model accuracy, live account/model/GPU, hostile parser resource-soak or whole-system production certificate.
''')
    write('rollback.md','''# Scoped rollback and deterministic resume

No audit commit. Retained inherited dirty audit/12-tool-registry branch, never reset/restore all. Saved preimages: .jarvis-runtime/jarvis-audit/module17-pre/ (app paths use __; root README is root-README.md). Review source.patch/source-hashes.json against current later edits before manually restoring only this module's changes. Do not regenerate old preimages or overwrite prior module/user changes. No production document/vault data modified, no dependency/schema migration rollback, no personal file deletion.

From app/ using existing .venv/Scripts/python.exe:
1. scripts/verification/verify_rag_documents_audit.py: exact immutable old-source versus current BM25 A/B.
2. scripts/verification/verify_rag_documents_journey.py: synthetic drop→command→readback→restart, network/account writes forbidden.
3. -m pytest tests/test_rag_documents_audit.py tests/test_documents.py tests/test_buddy.py tests/test_audit_result_accounting.py tests/test_phase2_gpu_models_voice_ui.py -q --junitxml=artifacts/jarvis-audit/modules/17-rag-documents/cases-and-contracts.xml
4. Freeze runtime/test hashes, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/17-rag-documents/full-regression.xml
5. -m jarvis.launcher --check (read-only), preserve private raw output locally; publish redacted readiness.json.
6. scripts/verification/report_rag_documents_audit.py; scripts/verification/verify_rag_documents_artifacts.py.

Next NOT RUN module/case JRV-18-001; earlier unresolved JRV-04-001. Exact remaining IDs in remaining-case-ids.txt. Prompt 17 blockers003/005/012/032 need designed conflict/semantic validation, hard parsing process resource guard and operation trace contract, then executable assertions. Separately review pypdf 6.20.1 installation/security regression under explicit dependency authorization; no installation/send/account-write/deploy is authorized by verification steps.
''')
    for path,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/17-rag-documents/inventory.md'),(BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/17-rag-documents/inventory.md'),(BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/17-rag-documents/inventory.md'),(BASE/'docs/file-buddy.md','../artifacts/jarvis-audit/modules/17-rag-documents/inventory.md')]:
        text=path.read_text(encoding='utf-8');text=re.sub(r'\n<!-- prompt17-audit -->[\s\S]*?<!-- /prompt17-audit -->\n','\n',text)
        first,rest=text.split('\n',1);path.write_text(first+'\n\n<!-- prompt17-audit -->\n'+headline+f'\n[Evidence, limitations and rollback]({link}).\n<!-- /prompt17-audit -->\n'+rest,encoding='utf-8')
    table='\n'.join(f"| {m['number']:02d} {m['module']} | "+' / '.join(f'{k}:{v}' for k,v in sorted(Counter(r['status'] for r in catalog if int(r['id'].split('-')[1])==m['number']).items()))+' |' for m in modules)
    (OUT/'final-report.md').write_text(f'''# Jarvis audit — Prompt 17 follow-up, 2026-10-16 IST

{headline}

{scope}

[Source-map/code/config/assertion matrix](modules/17-rag-documents/inventory.md), [all 32 IDs](modules/17-rag-documents/tests.jsonl), [targeted XML](modules/17-rag-documents/cases-and-contracts.xml), [full XML](modules/17-rag-documents/full-regression.xml), [actual synthetic journey](modules/17-rag-documents/document-journey.json), [redacted readiness](modules/17-rag-documents/readiness.json).

Repo HEAD **{env['head']}**, retained branch **{env['branch']}**, no commit; inherited user/module14–16 changes preserved. [Actual environment](modules/17-rag-documents/environment.json): Windows/Python{env['python']}, pypdf{env['pypdf']}, RAM{env['host_ram_bytes']}B; target Ryzen7/32GB/RTX3050Laptop4GB. No GPU/model/audio performance claim. {len(frozen)} runtime/test file hashes unchanged during accepted full run. [Implementation/docs files](modules/17-rag-documents/files-changed.json), [generated output files](modules/17-rag-documents/generated-files.json), [complete scoped diff](modules/17-rag-documents/source.patch), [preimage hashes](modules/17-rag-documents/source-hashes.json). No manifest/launcher/recovery or dependency/service interface change.

Baseline **{baseline['PASS']} PASS /2 native deselected**; final targeted **{target['PASS']} PASS /{target['SKIPPED']} BLOCKED skips**; accepted full **{full['PASS']} PASS /{full['SKIPPED']} skips /0FAIL**. Counts overlap and are not unique catalog totals. [Failure history/harness correction](modules/17-rag-documents/failures.md) preserved; no pass awarded merely from reading a catalog row. Actual owned native drop/event-loop and buddy regression fixtures ran; user Explorer drag/live sends were not run. Synthetic drop/command/restart journey **{journey['seconds']:.3f}s**, authored local response, zero network/external-effect calls.

{measured} Warm traced temporary lookup peak {before['python_peak_bytes']}→{after['python_peak_bytes']}B. Five fresh prepared-index queries/20warm per version; [50raw samples](modules/17-rag-documents/benchmarks.csv), [scope](modules/17-rag-documents/benchmark-summary.json), [keep/defer tradeoffs](modules/17-rag-documents/changes.md). Persistent postings memory/index construction/hash/parsing/TTFT/audio/VRAM excluded; no overall end-to-end speed/memory claim. Prior per-module measurements retained [through16](final-report-before-module17.md).

## Open gates and risk

{blockers}

Firecrawl [official URLs/dates](modules/17-rag-documents/upstream-checks.json), [compatibility](modules/17-rag-documents/compatibility.md): pypdf 6.20.1(2026-10-12) adds a cyclic-tree security fix absent from installed6.20.0; Python requirement compatible, no installation under prompt boundary. Upstream LightRAG/GraphRAG are comparison projects, not installed Jarvis dependencies. No untrusted-PDF security certification, complex-table/OCR/semantic entailment, general multi-document or production-readiness claim. Existing acoustic/GPU/account/other module gates remain. Readiness **{ready['status']}**: {', '.join(ready['missing']) or 'no missing dependencies reported'}. No service repair/start or package download attempted.

[Scoped rollback and exact resume](modules/17-rag-documents/rollback.md). Next NOT RUN **JRV-18-001**; earliest older unresolved **JRV-04-001**. All 1,184 unique IDs: **{counts}**. [Exact ledger](test-results.jsonl), [tier/category totals](summary.json), [exact remaining IDs](remaining-case-ids.txt). Missing contracts are explicit BLOCKED, not claimed complete.

## Modules

| Module | Catalog statuses |
| --- | --- |
{table}

## Tier/category statistics

```json
{json.dumps({k:summary[k] for k in ('by_tier','by_category')},indent=2)}
```
''',encoding='utf-8')
    files=['jarvis/documents.py','jarvis/file_drop.py','tests/test_rag_documents_audit.py','tests/test_audit_result_accounting.py','scripts/verification/audit_catalog.py','scripts/verification/verify_rag_documents_audit.py','scripts/verification/verify_rag_documents_journey.py','scripts/verification/report_rag_documents_audit.py','scripts/verification/verify_rag_documents_artifacts.py','README.md','docs/system-map.md','docs/file-buddy.md','../README.md']
    changed=[];pairs=[];patch=[]
    for f in files:
        new=BASE/f;old=PRE/('root-README.md' if f=='../README.md' else f.replace('/','__'))
        changed.append({'path':f,'sha256':sha(new)})
        if old.exists():pairs.append({'path':f,'before':sha(old),'after':sha(new)})
        patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],new.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+f if old.exists() else '/dev/null',tofile='after/'+f))
    write('files-changed.json',json.dumps(changed,indent=2));write('source-hashes.json',json.dumps(pairs,indent=2));write('source.patch',''.join(patch))
    generated=['artifacts/jarvis-audit/'+s for s in ('final-report.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt')]
    generated += [p.relative_to(BASE).as_posix() for p in sorted(MOD.iterdir()) if p.is_file()]
    generated += ['artifacts/jarvis-audit/modules/17-rag-documents/'+s for s in ('generated-files.json','artifact-verification.json')]
    write('generated-files.json',json.dumps(sorted(set(generated)),indent=2))
    print(json.dumps({'module17':dict(Counter(r['status'] for r in cases)),'full':full,'catalog':counts},indent=2))


if __name__=='__main__':main()
