# Prompt 30 changes and keep/revert decisions

- Serialize each client's request/response lifecycle using a reentrant lock with cancellable waits; keep one authoritative stdio response consumer. This is not a cross-client TaskState lease.
- Bound JSON protocol input before launch, cap responses, buffer at most eight messages, validate outer envelopes/progress, classify dead workers promptly even with a missing EOF signal, and reject late cancelled results.
- Share typed optional planner settings; reject malformed objects, strings-as-booleans, nonfinite/bool/out-of-range deadlines, invalid model text and unknown selector identifiers. Include enabled Harness model/default in required local model inventory.
- Validate nonstring/unhashable tool actions and malformed history/budgets; reject exact duplicate, completed and failed action keys before execution. Plan responses cannot inject approval/completion metadata. This rejects a repeated key rather than silently removing a potentially meaningful step; ambiguous workflows must replan with fresh state.
- Validate read-only Harness final/call fields and exact call arguments against both the advertised catalogue and AgentSession's read-only tool set. No upstream executor is exposed.
- In-memory runtime opt-out joins the effective cancellation predicate; discard optional results after disable and preserve native routing on the next explicit request. This does not add a disk-config watcher; documented file edits still require restart.
- Missing Laya checkpoint returns an explicit clarification; missing package/file returns unavailable. Validate candidate identities and selected keys; keep the independent decision/permission gate. Other native inference no longer depends on Laya model presence.
- Tighten Harness composition shape/budget checks. Replace three generic deep copies with one JSON encoding plus independent C-backed decoded branches; no mutable branch sharing and no cache of user context.


Keep the schema-copy CPU optimization with an explicit memory tradeoff. For 50 replan-schema copies per batch, warm p50/p95 24.2095/25.4175 → 13.9932/14.9647 ms; peak temporary Python allocation 17884 → 76564 bytes. The additional 58,680 bytes are bounded temporary allocation on a 32 GB host; no VRAM claim. All returned schemas match the saved implementation exactly, and branches/input remain independently mutable. Five initial+20 warm batches, not cold planner processes. Do not enable a harness based on this microbenchmark: it has no live outcome-accuracy measurement. Current planner flags/models/checkpoints and dependency pins remain unchanged.

- `docs/deepseek-harness.md`
- `docs/hermes-agent.md`
- `docs/hermes-skills-and-comparison.md`
- `jarvis/brain.py`
- `jarvis/brain_worker.py`
- `jarvis/harness.py`
- `jarvis/harness_worker.py`
- `jarvis/hermes.py`
- `jarvis/model_selection.py`
- `README.md`
- `../README.md`
- `scripts/verification/audit_catalog.py`
- `tests/test_audit_result_accounting.py`
- `jarvis/planner_settings.py`
- `tests/test_harness_planners_audit.py`
- `scripts/verification/verify_harness_planners_audit.py`
- `scripts/verification/report_harness_planners_audit.py`
- `scripts/verification/verify_harness_planners_artifacts.py`

Generated module/global artifacts are listed in generated-files.json. No commit/reset or unrelated cleanup occurred. Existing dirty work and historical reports are preserved.
