# Adaptive planning evidence — 2026-10-21 IST

Candidate: `codex/adaptive-planning`, based on `0199c16`. This packet separates local implementation checks from full release acceptance. Nothing was installed, downloaded, published or activated by this change.

## Before/after evidence

Four deterministic-planner cases exercise **37 actual owned-file actions** (2/5/10/20 steps) with independent disk content and exact action-order/count oracles. [Before](before.json) was recorded before production edits; [final candidate](after.json) uses the same cases. [Initial candidate sample](after-initial.json) is retained separately. Each JSON includes the raw case results and timing values.

The final timing sample preceded the last silent repair-reporting/backoff-revalidation delta; its [source snapshot](source-manifest-before-logging.json) is retained. Final-source regression evidence is separate. Earlier timing samples are preserved rather than overwritten or selected for speed.

| Metric | Before | Candidate |
| --- | ---: | ---: |
| Planning calls | 40 | 7 |
| Redundant retained-plan calls removed | — | 33 (82.5% of baseline calls) |
| Verified complete outcomes | 4/4 | 4/4 |
| Exact action order/arguments and final content | 4/4 | 4/4 |
| Total measured fixture execution | 6.499 s | 13.109 s |
| Mean time to first dispatch (proxy for useful action start) | 0.6625 s | 0.9450 s |
| Time inside simulated planning callbacks | 2.7493 ms | 5.6629 ms |
| Safe cancellation/uncertain-write recovery | 4/4 | 4/4 |

The extra durable checkpoints increase measured local overhead. These single four-case runs include startup and concurrent machine load; they have no latency confidence interval and do **not** establish a live speed improvement. First dispatch is not a measured timestamp of first verified output. A live-model request saved by the continuation rule has not been timed directly. Completion quality here means the authored file/content/order oracle, not general response quality.

[Recovery baseline](recovery-before.json) is a retrospective rerun of pinned `0199c16` task-state/Brain/Actions source loaded in an isolated Python process without changing the checkout; [recovery candidate](recovery-after.json) uses current code. Four real-file cases inject uncertain effects and cancellation in full/incremental modes. Both retain one verified action, stop before further dispatch, and preserve blockers for uncertain effects. This is safe checkpointing, not automatic completion of a blocked task.

## Verification

- [Final combined relevant suite](final-combined-tests.txt): **595 passed / 19 gated skips / zero failures**, 177.11 s. This covers final controller/task state/queue/UI/DAG/model-routing/recovery code, silent repair logging and backoff-state-change faults, and all six original broad-run failure areas. It supersedes the overlapping selected runs below, without adding their counts. The [pre-logging combined run](combined-before-logging.txt) is retained separately (593 pass / 19 skip).
- [Pre-edit focused baseline](baseline-tests.txt): **73 passed** using a workspace TEMP directory. The initial default sandbox TEMP run produced 38 filesystem-denial failures and 35 passes; that was not a valid functional baseline.
- [Relevant controller/queue/UI/model-routing/DAG/recovery regression](relevant-tests.txt): **362 passed / 7 gated skips**. This preceded the later owned-forge rename repair; overlapping runs are not added.
- [Earlier forge/recovery regression](forge-recovery-tests.txt): **178 passed / 7 gated skips**. [Controller suite after the shared helper](controller-tests.txt): **33 passed**. The controller suite adds an actual executor case where both the plan and verifier omit a requested literal operation; it still pauses, and a fake Gmail acknowledgement fault cannot resend the message. Overlapping runs are not added.
- [One real local Qwen plan](live-local.json): **PASS**, 2/2 owned-file actions, **58.781 s**, initial `qwen3.5:9b` planning call. Decisions and final disk/action-count verification use deterministic oracles. This is not a voice/vision/native-tool/cloud/application acceptance result.
- [Permitted launcher check](launcher.txt): **ready**; Docker, Ollama required models and local Git are available. Optional Groq is not live checked. Earlier sandbox `repair_required` reflected denied local-service access.
- [Full regression before final repairs](full-regression-before-final-repairs.txt): **3,777 passed / 150 skipped / 6 failed / 1 warning**, 1,636.29 s. It started before the final acceptance/UI and owned-metadata repair deltas. Three failures explicitly reported Windows Access denied on rename; two were forge/evolution state assertions and one was a Tk file-read/setup error. The Tk file existed when checked afterward; no Python/Tk installation was changed.
- [All six failure areas after repair](failure-areas-final.txt): **254 passed / 12 skipped**, 87.12 s. The targeted tests include all original failing assertions. An [intermediate affected run](intermediate-failure-areas.txt) passed 251 cases but a benchmark case returned failure fields and the old benchmark raised `KeyError: planner_calls`; the underlying case error was not retained, so its cause cannot be established from that log. Benchmark aggregation now preserves the case and reports an unknown call count instead of hiding the error. The later affected run is clean. This is not a rerun of the full suite on final source.

## Remaining gates and next action

The new controller manages sequential Brain execution. Specialized direct/fast/Gmail/coding/DAG paths retain separate contracts. Uniform independent semantic completion authority across all tools, voice/vision, configured cloud models, real desktop/browser/Blender/Unreal/YouTube/Spotify journeys, fresh UI screenshots and real process-kill/power-loss recovery remain unaccepted. No fixed thinking duration or new planning-iteration cutoff was added; existing transport/action safety budgets remain.

Native Windows reads/renames failed intermittently in the broad run. The candidate adds a shared bounded commit guard for contained forge, Gmail receipt, repository-snapshot and evolution metadata; source/target/content changes, links, unsupported sizes/depth, uncertain movement and caller shutdown stop recovery. It never reruns ability code, sends, installation, acquisition, source deployment or delivery. Fault injection and affected integration tests pass separately.

Final repair-reporting checks also inject a source change during backoff and verify no second rename. Retry/recovered summaries use `repair` transcript events and `.jarvis-runtime/repairs.jsonl`; no metadata contents or spoken/pop-up repair announcements are emitted.

An existing real OpenViking test fixture logged repeated cross-event-loop errors and eventually moved on with gated skips. No upstream environment/package/model was modified. Readiness is not certification of that journey.

Review the [architecture and reproduction guide](../../../../docs/adaptive-planning.md), local diff and final logs. Resolve any remaining broad-suite failures and complete the live acceptance gates before claiming a full Jarvis upgrade/release acceptance. The [cumulative handoff](../../../../docs/CLAUDE_HANDOFF.md) retains earlier blockers.

[Source manifest](source-manifest.json) records the baseline revision, final candidate file hashes, Python/platform and test-run lineage. All 475 local links in the root/application READMEs and the new guide/evidence README resolved when first checked; no unrelated historical links were changed.
