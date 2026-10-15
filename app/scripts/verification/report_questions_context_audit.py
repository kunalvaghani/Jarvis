"""Publish module06 evidence from completed runs; preserve earlier audit reports."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
ROOT = BASE/'artifacts/jarvis-audit'
OUT = ROOT/'modules/06-questions-context'
PRE = BASE/'.jarvis-runtime/jarvis-audit/module06-pre'
RUNTIME = ('jarvis/question_client.py','jarvis/knowledge_worker.py','jarvis/context_selector.py',
           'jarvis/conversation_memory.py','jarvis/runtime_health.py')
FILES = (*RUNTIME,'config/runtime_manifest.json','tests/test_questions_context_audit.py',
    'tests/test_audit_result_accounting.py','scripts/verification/audit_catalog.py',
    'scripts/verification/verify_questions_context_audit.py','scripts/verification/report_questions_context_audit.py',
    'README.md','docs/natural-conversation.md','docs/session-context.md','docs/system-map.md')


def write(path, text):
    path.write_text(text,encoding='utf-8')


def read_run(name):
    tree = ET.parse(OUT/name)
    nodes = list(tree.iter('testcase'))
    assert nodes
    assert not any(n.find('failure') is not None or n.find('error') is not None for n in nodes), name
    skipped = [n for n in nodes if n.find('skipped') is not None]
    assert all('BLOCKED:' in n.find('skipped').get('message','') for n in skipped)
    return {'passed':len(nodes)-len(skipped),'blocked':len(skipped),
            'seconds':float(next(tree.iter('testsuite')).get('time',0))}


def main():
    targeted, full = read_run('cases-and-contracts.xml'), read_run('full-regression.xml')
    for path in RUNTIME:
        assert (OUT/'full-regression.xml').stat().st_mtime >= (BASE/path).stat().st_mtime
    modules = json.loads((ROOT/'module-map.json').read_text())
    modules[5].update(status='FIXTURE COMPLETE',reason='32 catalog cases executed; two real cached default-model synthetic probes passed. Broad semantics, acoustic latency and live web acceptance remain open.',
        sources=[*RUNTIME,'jarvis/knowledge.py','jarvis/quick_answers.py','jarvis/everyday_runtime.py',
                 'jarvis/documents.py','jarvis/hybrid_inference.py','jarvis/cloud_policy.py','docs/natural-conversation.md','docs/session-context.md'],
        test_candidates=['tests/test_questions_context_audit.py','tests/test_knowledge.py','tests/test_question_speed.py',
                         'tests/test_conversation_context.py','tests/test_answer_stream.py','tests/test_groq.py','tests/test_documents.py'])
    write(ROOT/'module-map.json',json.dumps(modules,indent=2)+'\n')
    from scripts.verification.audit_catalog import reconcile
    reconcile()
    rows = [json.loads(s) for s in (ROOT/'test-results.jsonl').read_text().splitlines()]
    cases = [r for r in rows if r['id'].startswith('JRV-06-')]
    assert len(cases)==32 and all(r['status']=='PASS' for r in cases)
    for row in cases:
        row['scope']='Executed production-boundary fixtures; cases 002/009 additionally check captured real cached 9b synthetic inference. No GUI/acoustic/live web acceptance inferred.'
    write(OUT/'tests.jsonl',''.join(json.dumps(r)+'\n' for r in cases))
    write(OUT/'remaining-case-ids.txt','')
    summary = json.loads((ROOT/'summary.json').read_text())
    bench = json.loads((OUT/'benchmark-summary.json').read_text())['results']
    native = json.loads((OUT/'native-default.json').read_text())
    assert native['status']=='PASS' and native['model']=='qwen3.5:9b'
    ready = json.loads((PRE/'readiness-private.json').read_text(encoding='utf-8-sig'))
    assert ready['status']=='ready' and not ready.get('missing') and not ready.get('incomplete')
    write(OUT/'readiness.json',json.dumps({'date':'2026-10-15 IST','command':'python -m jarvis.launcher --check',
        'exit_code':0,'status':ready['status'],'scope':ready.get('scope'),
        'services':{k:v['status'] for k,v in ready.get('services',{}).items()}},indent=2)+'\n')
    patch, hashes = '', {}
    for name in (*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py'):
        path, old = BASE/name, PRE/Path(name).name
        assert old.is_file()
        patch += ''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),
            path.read_text(encoding='utf-8').splitlines(True),fromfile='module06-pre/'+name,tofile=name))
        hashes[name] = {'before':hashlib.sha256(old.read_bytes()).hexdigest(),'after':hashlib.sha256(path.read_bytes()).hexdigest()}
    write(OUT/'source.patch',patch)
    write(OUT/'source-hashes.json',json.dumps(hashes,indent=2)+'\n')
    changes = [{'path':'app/'+name,'sha256':hashlib.sha256((BASE/name).read_bytes()).hexdigest()} for name in FILES]
    changes.append({'path':'README.md','sha256':hashlib.sha256((BASE.parent/'README.md').read_bytes()).hexdigest()})
    write(OUT/'files-changed.json',json.dumps({'scope':'Scoped module06 files; shared files preserve earlier dirty work. No commit or deployment.',
        'files':changes,'artifact_directory':'app/artifacts/jarvis-audit/modules/06-questions-context',
        'shared_artifacts':['module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt','security-findings.md','final-report.md']},indent=2)+'\n')
    command = '.venv/Scripts/python.exe -m pytest tests/test_questions_context_audit.py tests/test_question_speed.py tests/test_answer_stream.py tests/test_conversation_context.py tests/test_quick_answers.py tests/test_knowledge.py tests/test_runtime_health.py tests/test_groq.py tests/test_audit_result_accounting.py tests/test_documents.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/06-questions-context/cases-and-contracts.xml'
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip()
    branch = subprocess.check_output(['git','branch','--show-current'],cwd=BASE,text=True).strip()
    stats = '\n'.join(f'| {name} | {values["p50_ms"]:.4f} | {values["p95_ms"]:.4f} | {values["payload_bytes"]} | {values["peak_python_bytes"]} |'
                      for name,values in bench.items())
    matrix = '''| Architecture claim | Actual implementation | Executed evidence / limit |
| --- | --- | --- |
| Instant arithmetic | [quick_answers.py](../../../../jarvis/quick_answers.py), EverydayRuntime._math | 001/008: three equivalent phrasings, no model needed on this direct helper path |
| Question entry/context | [knowledge.py](../../../../jarvis/knowledge.py), Knowledge.submit/_context/prepare_context | 003/004/007/024: recent recall, unrelated-topic exclusion, referent and stale-app revision |
| Context worker | [context_selector.py](../../../../jarvis/context_selector.py), ContextSelector.run/choose | cancelled queued futures do not execute; timeout/backoff, fixed app/keyword projection, no tools |
| Local/public answer | [knowledge_worker.py](../../../../jarvis/knowledge_worker.py), answer/chat | structured answer validation, local-only private fallback, evidence gaps, citation bounds; real 9b synthetic examples |
| Transport/lifecycle | [question_client.py](../../../../jarvis/question_client.py), QuestionClient.request/snapshot | 100 calls in 20 five-way rounds, finite admission, pre-dispatch validation, no retry after progress, categorical errors |
| Cloud policy | [cloud_policy.py](../../../../jarvis/cloud_policy.py), [hybrid_inference.py](../../../../jarvis/hybrid_inference.py) | existing fake Groq transport verifies private enrichment absent from public payload; no real cloud calls |
| Durable pairs | [conversation_memory.py](../../../../jarvis/conversation_memory.py), ConversationMemory/current_context | isolated SQLite restart/readback and redaction; narrow recent-question selection added; lexical retrieval remains |
| Attached files | [documents.py](../../../../jarvis/documents.py), Library.answer | separate existing focused-document path, fixture-only page grounding; not a new generic attachment key |
| Operational state | [runtime_health.py](../../../../jarvis/runtime_health.py), RuntimeHealth.snapshot | actual question trace UUID/status exposed without prompts/answers/exception text |
'''
    write(OUT/'inventory.md',f'''# Prompt06 question/context audit — 2026-10-15 IST

**32 catalog PASS; 0 FAIL/BLOCKED/SKIPPED/NOT RUN in this module.** These are bounded case proofs, not a whole-system production certificate.
Repository `{commit}`, branch `{branch}`; Windows, Python {platform.python_version()}, target Ryzen7/32GB + RTX3050 Laptop4GB. Existing dirty work preserved. No install/model download/account write/personal delete/system setting change/deployment. One native model probe at a time, no microphone or speaker use.

{matrix}
Actual flow: Knowledge prepares memory/selector context and direct answers before QuestionClient; the old map had the selector/client order reversed. ContextHub is a separate cognition projection, not this question transport. Existing natural-conversation, session-context, fast-conversation, file-buddy and Groq guides inspected; historical performance claims are not reused as fresh proof.

## Executed checks

Corrected existing baseline: **85 PASS in 6.42s**, [XML](existing-baseline-corrected.xml). An earlier invocation named two nonexistent test files; [collection-error XML](existing-baseline.xml) is not counted as a run of assertions.
New fault baseline: **13 FAIL / 2 PASS**, [XML](reproduced-failures.xml); exact recent-recall repro: **1 FAIL**, [XML](recall-reproduced.xml). Failures are historical reproductions, not current failures.
Final targeted: **{targeted['passed']} PASS / {targeted['blocked']} BLOCKED**, {targeted['seconds']:.2f}s, [XML](cases-and-contracts.xml). Full `python -m pytest tests -q --tb=short`: **{full['passed']} PASS / {full['blocked']} explicit BLOCKED skips**, {full['seconds']:.2f}s, [XML](full-regression.xml). Suites overlap; do not sum them. See console/XML for warnings. Launcher `--check`: **ready**, [redacted result](readiness.json).
One pywinauto STA COM warning was reported. The captured-native evidence identity check was changed from filesystem timestamps to a portable SHA256 comparison while the full suite ran; the final targeted rerun verifies that assertion. Application runtime source remained unchanged throughout the full run.

Command from app: `{command}`.

## Matched projection benchmark

Same Python/machine/oversized authored input, 20 warm + 5 first-projection samples per version. Tracemalloc includes serialization. Cold here means fixture projection, not fresh process/model loading.

| Build | Warm p50 ms | Warm p95 ms | Payload bytes | Peak traced Python bytes |
| --- | ---: | ---: | ---: | ---: |
{stats}

[CSV](benchmarks.csv), [summary](benchmark-summary.json). Zero external writes and GPU allocations in this CPU microbenchmark. No inference, retrieval-precision, process RSS/VRAM or first-audio improvement inferred. Retain bounded projection: schema/identity tests pass and payload/CPU/allocation costs fall; no model quality settings changed.

## Actual local checks and limits

Cached default `qwen3.5:9b`, Ollama0.40.0 through the existing GPU scheduler: beginner explanation first content **{native['cases'][0]['first_content_seconds']:.3f}s**, complete **{native['cases'][0]['seconds']:.3f}s**; synthetic retrieved injection first content **{native['cases'][1]['first_content_seconds']:.3f}s**, complete **{native['cases'][1]['seconds']:.3f}s**. [Actual authored prompts/replies](native-default.json). It explicitly refused the attack; mentioning its marker while refusing was initially misclassified by the test, then the rubric was corrected. No tools exist on this answer path. Two examples do not prove general prompt-injection resistance or factual accuracy.

The CPU0.8B pilot initially failed its quantum-content assertion, then passed on rerun (first content0.515s/complete2.921s); invented-term prompt requested verification instead of fabricating a definition. [Helper sample](native-local.json). This cold/warm variation remains a limitation; no guaranteed two-second answer or acoustic target is claimed. Original pilot failure had no raw response capture; no cause is invented.

[Cases](tests.jsonl), [changes](changes.md), [failures](failures.md), [compatibility](compatibility.md), [rollback](rollback.md), [exact file hashes](files-changed.json), [scoped preimage diff](source.patch).
''')
    write(OUT/'failures.md','''# Reproduced failures and disposition — 2026-10-15 IST

- Existing baseline invocation initially used nonexistent context_selector/conversation_memory test filenames; corrected collection ran 85 real assertions. The collection-error XML is retained and excluded from pass counts.
- 13/15 new variants failed: private context could promote malformed/uncertain answers to external search, empty retrieval ran another model with no sources, transport errors echoed exception data, cancelled queued futures executed/killed their worker, unbounded keyword/app context expanded prompts, and empty structured answers were accepted. All now have executed regression proof.
- Exact recent-question phrase selected no context (1 reproduced failure). Narrow recall phrase recognition now preserves recent pairs; no timestamp precision is claimed.
- Client inspection additionally exposed shared reply queue races, validation after dispatch and raw error propagation. Serialized admission, bounded snapshots/response queue and categorical failure metadata now have regression assertions.
- Real CPU-helper first quantum probe failed the semantic acceptance assertion; rerun passed. Cold/warm variability remains open. An initial default-model injection rubric rejected quoting the attack marker in an explicit refusal; corrected rubric verifies refusal/no false action claim. This was a test false positive, not an observed executed action.
- Remaining limits: no broad semantic/injection corpus, live web provider, real Groq, microphone-to-speaker latency, general retrieval precision/recall, process peak RSS/VRAM, or shared STT/F5 contention acceptance. Existing whole-system catalog blockers remain. Never interpret these samples as universal correctness or production release approval.
''')
    write(OUT/'changes.md','''# Changes and keep/revert decisions — 2026-10-15 IST

Keep the scoped boundary changes: (1) local/private context cannot escalate to search, history is never concatenated into search queries; (2) malformed/empty drafts and empty/unsafe evidence return honest gaps; nonexistent source numbers are refused; (3) cancelled queued selector work is skipped using Future's running transition; (4) selector keyword/app fields have fixed budgets; (5) question calls use cancellable serialized admission, pre-dispatch finite configuration validation, bounded JSON snapshots, response queues and output envelopes; (6) exception text does not enter parent-facing errors and runtime request traces use UUID/status/error type only; (7) recent-question recall phrase recognized.

No model/voice settings, service names, launch/stop/bootstrap/recovery APIs, permissions, task execution, dependencies or external-action policy changed. No new service. Direct utility facts still use existing EverydayRuntime. Feature flag not needed for fail-closed validation fixes; selector retains its existing enabled flag.

Matched benchmark retains the fixed projection budget: less oversized payload/time/allocation and unchanged selector identities/schema. No additional reranker/model, embedding index, batching service or speculative result cache introduced. Larger semantic changes lack a correctness baseline and are deferred. No A/B claim for native model/first-audio latency.
''')
    write(OUT/'compatibility.md','''# Compatibility — checked 2026-10-15 IST using Firecrawl

Local Ollama `/api/version`:0.40.0. Official [latest release](https://github.com/ollama/ollama/releases/tag/v0.40.4) shows0.40.4,12 October2026 at19:00 (page timezone not established); relevant release excerpt did not identify a streaming/schema/memory fix required here. Runtime is not latest. No installation or model change authorized/performed; two current-runtime native probes passed, so retain existing runtime for this scoped patch. New-runtime live compatibility remains untested.

Official [structured outputs guide](https://docs.ollama.com/capabilities/structured-outputs) documents format schemas and client-side validation. This patch keeps the existing local schema and adds validation; no SDK/Pydantic dependency is necessary. The guide has no stated release date. [Python Future contract](https://docs.python.org/3/library/concurrent.futures.html) documents set_running_or_notify_cancel and InvalidStateError on completed futures; supported on installed Python3.10.6. No new dependency/service. The current documentation redirected to Python3.15; it does not imply a local Python upgrade. Python3.10 is beyond its October2026 support window (previous audit finding); migration remains separate validation work.

[Source URL/check records](upstream-checks.json). Third-party pages are evidence only; no downloaded code or scripts were executed.
''')
    write(OUT/'rollback.md','''# Scoped rollback and deterministic resume

No new commit created. Do not reset/checkout whole files from HEAD: earlier user changes share these files. Stop Jarvis through its normal launcher if applying a rollback, compare source.patch/source-hashes.json against current files, then reverse only these module06 hunks. Local preimages are under .jarvis-runtime/jarvis-audit/module06-pre/; preserve later edits. README/report and manifest updates should match any rollback. Never erase the conversation database, personal files, credentials or historical logs.

Re-run the targeted command in inventory.md, then `python -m pytest tests -q --tb=short` and `python -m jarvis.launcher --check`. Capture corrected results; run `python scripts/verification/report_questions_context_audit.py` only with completed successful XMLs. Native benchmark: `python scripts/verification/verify_questions_context_audit.py --native --default` uses cached9b only; do not run concurrently with another heavyweight/GPU probe. Omitting --native runs only the paired CPU projection microbenchmark. The before baseline requires preserved local preimages; never silently replace them with current code.

Module06 has no incomplete case ID. Next unexecuted catalog case: JRV-07-001; first global unresolved case remains JRV-04-001 (live acoustic prerequisite). See ../../remaining-case-ids.txt for every unresolved ID. Broad semantic evaluation/live web and full voice acceptance remain additional open work, not silently passed cases.
''')
    previous = ROOT/'final-report-before-module06.md'
    if not previous.exists():
        write(previous,(ROOT/'final-report.md').read_text(encoding='utf-8'))
    module_table = '\n'.join(f'| {r["number"]:02d} | {r["module"]} | {r["status"]} |' for r in modules)
    write(ROOT/'final-report.md',f'''# Jarvis audit through Prompt06 — 2026-10-15 IST

**Prompt06:32 catalog PASS,0 FAIL/BLOCKED/SKIPPED/NOT RUN. Whole-system production acceptance remains open.** Targeted **{targeted['passed']} PASS**; full regression **{full['passed']} PASS/{full['blocked']} explicit BLOCKED skips**, {full['seconds']:.2f}s. [Targeted XML](modules/06-questions-context/cases-and-contracts.xml), [full XML](modules/06-questions-context/full-regression.xml); overlapping runs, not additive. Launcher readiness **ready**, [redacted check](modules/06-questions-context/readiness.json).

Repo `{commit}`, branch `{branch}`, Windows/Python{platform.python_version()}, Ryzen7/32GB target, RTX3050 Laptop4GB. Existing dirty work preserved. No account write/send, personal delete, OS setting change, install/download, new ability, commit or deployment. One model probe at a time; no microphone/speaker use.

[Source-map-to-code evidence matrix](modules/06-questions-context/inventory.md), [exact scoped files/hashes](modules/06-questions-context/files-changed.json), [preimage diff](modules/06-questions-context/source.patch). Repairs close private-search escalation, empty/unsafe retrieval and false citations, selector cancellation death, shared question reply races, delayed validation, unbounded projection and missed recent recall. [Failure baselines](modules/06-questions-context/failures.md), [changes/risk](modules/06-questions-context/changes.md), [rollback](modules/06-questions-context/rollback.md).

Equivalent oversized CPU projection: warm P50/P95 **{bench['before']['p50_ms']:.4f}/{bench['before']['p95_ms']:.4f}→{bench['after']['p50_ms']:.4f}/{bench['after']['p95_ms']:.4f}ms**; payload **{bench['before']['payload_bytes']}→{bench['after']['payload_bytes']} bytes**, traced Python peak **{bench['before']['peak_python_bytes']}→{bench['after']['peak_python_bytes']} bytes**. [All50 samples](modules/06-questions-context/benchmarks.csv). This is a fixed-budget projection gain, not a model latency or accuracy gain.

Actual cached9b synthetic question and retrieved-injection refusal passed: first content **{native['cases'][0]['first_content_seconds']:.3f}s/{native['cases'][1]['first_content_seconds']:.3f}s**, complete **{native['cases'][0]['seconds']:.3f}s/{native['cases'][1]['seconds']:.3f}s**. [Prompts/replies](modules/06-questions-context/native-default.json). Broad accuracy/injection resistance, retrieval precision/recall, live web/Groq, process peak RSS/VRAM and full acoustic two-second target remain unproved. Initial CPU-helper semantic probe failed then passed on rerun; this variation is retained as a limitation. Current Ollama0.40.0 is older than official0.40.4 (12Oct2026); no installation performed. [Official sources and compatibility](modules/06-questions-context/compatibility.md).

## Full catalog and modules

1184 unique IDs: **{summary['catalog_counts']}**. [Every case/assertion](test-results.jsonl), [tier/category/run totals](summary.json), [module06 cases](modules/06-questions-context/tests.jsonl), [exact remaining IDs](remaining-case-ids.txt). Historical module01–05 baselines/metrics and known risks preserved in [prior report](final-report-before-module06.md); these are not superseded by unrelated passing tests.

| Module | Name | Status |
| --- | --- | --- |
{module_table}

Next unexecuted module/case **07/JRV-07-001**. Earliest global unresolved **JRV-04-001**; prior acoustic/shared STT–F5 blockers remain. Module06 has no pending catalog ID. Resume instructions, concrete limitations and scoped rollback are linked above. No universal correctness, two-second voice guarantee or full production certification is claimed.
''')
    finding = '\n## Prompt06 — 2026-10-15 IST\n\nPrivate malformed-answer search escalation, unsafe/empty evidence, selector cancellation and shared-reply isolation fixed with reproduced/asserted boundaries. Question health uses content-free UUID/status/error categories. Broad semantic injection resistance, live web/cloud, two-second acoustics and prior shared GPU lease blockers remain open. See modules/06-questions-context/inventory.md.\n'
    security = ROOT/'security-findings.md'
    text = security.read_text(encoding='utf-8') if security.exists() else ''
    if '## Prompt06 —' not in text:
        write(security,text+finding)
    print(json.dumps({'targeted':targeted,'full':full,'catalog':summary['catalog_counts'],'module06':Counter(r['status'] for r in cases),'readiness':ready['status']}))


if __name__=='__main__':
    main()
