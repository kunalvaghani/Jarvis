# Prompt06 question/context audit — 2026-10-15 IST

**32 catalog PASS; 0 FAIL/BLOCKED/SKIPPED/NOT RUN in this module.** These are bounded case proofs, not a whole-system production certificate.
Repository `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; Windows, Python 3.10.6, target Ryzen7/32GB + RTX3050 Laptop4GB. Existing dirty work preserved. No install/model download/account write/personal delete/system setting change/deployment. One native model probe at a time, no microphone or speaker use.

| Architecture claim | Actual implementation | Executed evidence / limit |
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

Actual flow: Knowledge prepares memory/selector context and direct answers before QuestionClient; the old map had the selector/client order reversed. ContextHub is a separate cognition projection, not this question transport. Existing natural-conversation, session-context, fast-conversation, file-buddy and Groq guides inspected; historical performance claims are not reused as fresh proof.

## Executed checks

Corrected existing baseline: **85 PASS in 6.42s**, [XML](existing-baseline-corrected.xml). An earlier invocation named two nonexistent test files; [collection-error XML](existing-baseline.xml) is not counted as a run of assertions.
New fault baseline: **13 FAIL / 2 PASS**, [XML](reproduced-failures.xml); exact recent-recall repro: **1 FAIL**, [XML](recall-reproduced.xml). Failures are historical reproductions, not current failures.
Final targeted: **206 PASS / 0 BLOCKED**, 25.54s, [XML](cases-and-contracts.xml). Full `python -m pytest tests -q --tb=short`: **2126 PASS / 5 explicit BLOCKED skips**, 324.09s, [XML](full-regression.xml). Suites overlap; do not sum them. See console/XML for warnings. Launcher `--check`: **ready**, [redacted result](readiness.json).
One pywinauto STA COM warning was reported. The captured-native evidence identity check was changed from filesystem timestamps to a portable SHA256 comparison while the full suite ran; the final targeted rerun verifies that assertion. Application runtime source remained unchanged throughout the full run.

Command from app: `.venv/Scripts/python.exe -m pytest tests/test_questions_context_audit.py tests/test_question_speed.py tests/test_answer_stream.py tests/test_conversation_context.py tests/test_quick_answers.py tests/test_knowledge.py tests/test_runtime_health.py tests/test_groq.py tests/test_audit_result_accounting.py tests/test_documents.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/06-questions-context/cases-and-contracts.xml`.

## Matched projection benchmark

Same Python/machine/oversized authored input, 20 warm + 5 first-projection samples per version. Tracemalloc includes serialization. Cold here means fixture projection, not fresh process/model loading.

| Build | Warm p50 ms | Warm p95 ms | Payload bytes | Peak traced Python bytes |
| --- | ---: | ---: | ---: | ---: |
| before | 5.7632 | 6.0890 | 787592 | 2350018 |
| after | 0.2075 | 0.2175 | 12308 | 49374 |

[CSV](benchmarks.csv), [summary](benchmark-summary.json). Zero external writes and GPU allocations in this CPU microbenchmark. No inference, retrieval-precision, process RSS/VRAM or first-audio improvement inferred. Retain bounded projection: schema/identity tests pass and payload/CPU/allocation costs fall; no model quality settings changed.

## Actual local checks and limits

Cached default `qwen3.5:9b`, Ollama0.40.0 through the existing GPU scheduler: beginner explanation first content **3.109s**, complete **14.343s**; synthetic retrieved injection first content **1.844s**, complete **12.516s**. [Actual authored prompts/replies](native-default.json). It explicitly refused the attack; mentioning its marker while refusing was initially misclassified by the test, then the rubric was corrected. No tools exist on this answer path. Two examples do not prove general prompt-injection resistance or factual accuracy.

The CPU0.8B pilot initially failed its quantum-content assertion, then passed on rerun (first content0.515s/complete2.921s); invented-term prompt requested verification instead of fabricating a definition. [Helper sample](native-local.json). This cold/warm variation remains a limitation; no guaranteed two-second answer or acoustic target is claimed. Original pilot failure had no raw response capture; no cause is invented.

[Cases](tests.jsonl), [changes](changes.md), [failures](failures.md), [compatibility](compatibility.md), [rollback](rollback.md), [exact file hashes](files-changed.json), [scoped preimage diff](source.patch).
