# Prompt07 routing, quotas and privacy — 2026-10-15 IST

**32 catalog PASS; 0 FAIL/BLOCKED/SKIPPED/NOT RUN within module07 fixture scope. Live cloud acceptance is BLOCKED separately.** No whole-system production certificate.

Repo `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; Windows/Python3.10.6, Requests2.34.2, pytest8.4.2; Ryzen7/32GB target and RTX3050 Laptop4GB. Existing dirty work preserved; edits use app/, not its InsTAREELS alias. No account/real cloud request, personal deletion, OS-setting change, dependency/model install or deployment. One heavyweight local model probe at a time.

## Source map and claims

| Claim | Real entry point | Executed evidence / boundary |
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

System-map, Groq hybrid/architecture, GPU priority and crash-recovery guides inspected. Groq*.py candidates resolve to groq_adapter.py plus cloud_policy/cloud_quota/hybrid_inference; no standalone model router is invented. Package defaults disable cloud, but current local config has enabled/free/confirmed flags and auto routing with live_tests_enabled=false. Those flags are user attestations; no real API key was read/printed or entitlement inferred. Config/account preferences were preserved.

## Actual checks

Existing baseline: **67 PASS**,12.08s,[XML](existing-baseline.xml). New baseline: **11 FAIL/1 PASS**,[XML](reproduced-failures.xml), plus bare-key persistence **1 FAIL**,[XML](memory-reproduced.xml). These are retained historical reproductions. The first catalog harness had three errors (minute-window exhaustion, incorrect test class, duplicate keyword argument); corrected using a fake61s advance between rounds and verified class/config helpers. A later collection command named nonexistent test_memory.py: [collection error](collection-error.xml), no assertions counted; corrected to test_obsidian_memory.py.

Final targeted/neighbor run: **238 PASS / 0 BLOCKED**, 37.36s,[XML](cases-and-contracts.xml). Full `python -m pytest tests -q --tb=short`: **2173 PASS/5 explicit BLOCKED skips**, 337.55s,[XML](full-regression.xml). Runs overlap; do not sum. Launcher `python -m jarvis.launcher --check`: **ready**, [redacted check](readiness.json). Warning context remains in XML/console; no warning is treated as a failed assertion.

Targeted command: `.venv/Scripts/python.exe -m pytest tests/test_model_routing_audit.py tests/test_groq.py tests/test_conversation_context.py tests/test_question_speed.py tests/test_answer_stream.py tests/test_questions_context_audit.py tests/test_gpu_scheduler.py tests/test_obsidian_memory.py tests/test_audit_result_accounting.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/07-model-routing/cases-and-contracts.xml`.

Five-way mixed public/private requests repeated20 times assert40 expected fake cloud calls and zero private crossover; fake clocks avoid exceeding minute budgets. No uncertain external write or tool action is performed. Stable reservation IDs survive crashes; partial output never triggers duplicate inference. [Exact case ledger](tests.jsonl).

## Matched benchmark and decision

Same machine/input, simulated20ms metadata readiness, exhausted quota. Five cold gateway samples/build include feedback SQLite initialization;20 warm samples/build reuse gateway. Old route code imports the common current policy: this A/B isolates route ordering on an unchanged public question, not an entire historical dependency build. Separate classification compares saved pre-change/current policies over500 identical benign/public/private requests per version. Baseline correctness is asserted in both builds; new key-format acceptance has its own failing-before/passing-after tests.

| Build/mode | Samples | p50 ms | p95 ms | Peak traced Python bytes |
| --- | ---: | ---: | ---: | ---: |
| before_cold_gateway | 5 | 31.1614 | 42.3105 | 25674 |
| before_warm_gateway | 20 | 31.6769 | 41.9681 | 4974 |
| after_cold_gateway | 5 | 1.7070 | 8.5172 | 22446 |
| after_warm_gateway | 20 | 0.2198 | 1.6341 | 15846 |

[50 route samples](benchmarks.csv), [classification/summary](benchmark-summary.json). Retain early refusal: matching local result, fewer blocking readiness calls, warm p95 **41.9681→1.6341ms**. Warm traced allocation increased **4974→15846 bytes**, including UUID/background-refresh Mock accounting; no RAM reduction claimed. No process peak RSS/VRAM, real cloud TTFT, first audio, broad semantic precision or two-second target measured here. Deterministic filtering remains fast on these fixtures; a new tiny router adds no demonstrated privacy/accuracy benefit and is not installed.

## Applicable journey and remaining gaps

Actual `handle_request`: fake loopback Groq429 → full conservative reservation retained → existing installed-model fallback for deliberately missing model → real cached local9b answer in **15.172s**. [Reply and quota readback](local-fallback-journey.json). Exactly one fake cloud call, zero real cloud calls, no external write. This verifies fallback plumbing and a coherent authored example, not provider billing, model access, global accuracy or voice latency.

Live Groq/free entitlement, organization peers' consumption, paid-account detection, exact provider limits and real throughput remain **BLOCKED** by absent live-test opt-in and independently verified entitlement. No credentials or account changes were attempted. Secret patterns remain heuristic; multilingual/unknown wording stays local but universal sensitive-data detection is not certified. Current supported Groq model is preview. Prior acoustic/shared STT–F5 acceptance blockers remain.

[Failures](failures.md), [changes](changes.md), [compatibility/upstream URLs](compatibility.md), [rollback/resume](rollback.md), [exact files](files-changed.json), [scoped patch](source.patch), [source hashes](source-hashes.json).
