# Unified intelligence evidence — 2026-10-21 IST

Candidate branch: `codex/unified-intelligence`; baseline commit:
`d5ed6eda72ce439122856a0e34fd5f99f7e5dbe0`.

- [Architecture, diagnosis and reproduction](../../../../docs/unified-intelligence.md).
- [Before](before.json), [initial indexed run](after-index.json), [final run](after.json):
  warm Python microbenchmarks, 100 samples after ten warmups, fixed available-tool
  fixture. Seven queries per sample; all selected tool names match. No model or
  desktop latency claim. Final search p50 13.754 → 1.3348 ms; p95 14.6415 → 2.9228 ms.
- [Actual local-read summary](local-read-trace-final/summary.json) and
  [metadata trace](local-read-trace-final/trace.jsonl): twenty real ToolRegistry
  reads and exact disk matches of an owned synthetic public fixture. p50 15.28765 ms,
  p95 18.2548 ms. No model, GUI, account access, private content or write replay.
- [Final source hashes](source-hashes.json) and [initial integration hashes](initial-source-hashes.json)
  distinguish the later generated-MCP metadata-sharing repair.
- [Single live local-model observation](live-inference.json), reproduced by
  [the opt-in probe](live_inference_probe.py): correct public arithmetic response
  through existing GPU admission in 2.544 s, including Ollama-reported 2.193 s
  loading, 0.155 s prompt evaluation and 0.013 s generation. Installed 0.5B model,
  no download/cloud/tool dispatch. One sample under regression load; not a paired
  model, voice or task-success benchmark.
- [Targeted regression](targeted.xml): intermediate 194 passed / 4 platform skips.
  [Final learning/navigation regression](learning-regression.xml): 147 passed,
  including 92 new checks; overlapping counts are not summed.
- [Initial full regression](full-suite.log), [XML](full-suite.xml): **3,887 passed,
  150 skipped, 3 failed, 1 warning**, 1207.04 s. Two evolution-lab fixtures correctly
  refused the ordinary in-repository scratch directory; [host-temp rerun](evolution-host-temp.xml)
  passed both in 55.24 s. The registry-contention case hit intermittent Windows
  access denial; [isolated rerun](registry-rerun.xml) passed, then production was
  hardened using the existing unchanged-metadata commit guard.
- [Final affected suite](final-relevant.xml), [log](final-relevant.log): **303 passed,
  4 skipped**, 32.15 s, including injected registry sharing failure and unchanged
  metadata recovery. Overlapping results are not added together.
- [Final complete regression](full-suite-final.log), [XML](full-suite-final.xml):
  **3,889 passed / 150 skipped / 2 failed / 1 warning**, 1140.78 s, with final
  production source and normal host temporary storage. All three earlier failures
  cleared. Two native demonstration cases observed an occluded/outside fixture
  point and therefore recorded no expected step; both [isolated reruns](demonstration-rerun.xml)
  passed in 20.19 s. The fixture now explicitly admits its own foreground window
  and current point, gating unavailable desktop conditions. The unchanged recorder
  assertions still check injected/outside/password rejection and restart consent.
- [Complete demonstration module after fixture correction](demonstration-final.xml),
  [log](demonstration-final.log): **38 passed / zero skips**, 60.34 s. Production
  source remained unchanged. No whole-suite rerun after this test-only correction;
  **do not label the complete run all green**.
- [Machine-readable final summary](final-summary.json) preserves both failures,
  focused rerun results, source hashes and the incomplete release verdict.
- [Final-source host launcher check](launcher-check-final.log): exit 0 / **ready**, Docker 29.8.2 and
  required local models available. Optional Groq inference was not live-checked.
  The restricted-sandbox check had exit 1 with unavailable local endpoints;
  the host read-only check resolved that environment limitation without repairs.

The first trace harness attempt preserved a one-read journal under
`local-read-trace`; its assertion expected LF while Windows text output wrote
CRLF. The corrected byte fixture passed in a fresh directory. Temporary-folder
atomic-replace denials in exploratory tests were resolved by using the writable
repository scratch directory. Interrupted development regression runs are not
acceptance results.

Live microphone/TTS, native GUI sequences, new connector principal/schema health,
cross-application outcomes, general learned procedure transfer, quality-preserving
model/GPU tuning and sustained idle CPU/RAM/GPU/battery measurements were not
established by this packet. The release watcher is opt-in and tested with fake
release responses; no live background polling configuration was enabled.
