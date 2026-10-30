# ADR 0005: Upgrade v2 groundwork — flags, timing ledger, shadow log, sealed verifiers

Date: 2026-10-31. Status: accepted (Phase 0 of upgrade v2). Plan: [phase-0-plan.md](../rework/upgrade-v2/phase-0-plan.md).

## Context

Upgrade v2 will add a learn-it-myself loop, a fast path, skill replay and unified memory. Each must arrive without changing what works today. Each must be measurable before and after. And each must be judged by checks it cannot influence.

## Decisions

1. **One flag reader, everything off.** `jarvis/flags.py` lists every v2 flag with its shipped value (`False` or `'off'`). Only a literal JSON `true`, or one of `off`/`shadow`/`suggest`/`act`, counts. Anything else reads as off, so a damaged configuration can only switch features off. Modes are raised only by the user editing `config/config.json`.
2. **`fast_path` instead of `brain` for the System-1 and plan-cache flags.** The `brain` section is sent to the brain worker as `options` with every inference request. Adding keys there would change that payload even with the flags off. The master prompt's `brain.system1` is therefore `fast_path.system1`, and `brain.plan_cache` is `fast_path.plan_cache`.
3. **Hooks are decorators.** The timing ledger attaches to existing code through one decorator line each: `Actions.execute`, `BrainClient._request_once` and `ToolRegistry.execute`. `control/service.py` routes its fixed sleeps through `ledger.pause()`, which sleeps exactly as before. With the flag off, the hooks call straight through: one context-variable read, well under 1 ms. A ledger failure is swallowed.
4. **Token counts come from the result, not the worker.** Native planning results already carry Ollama's `prompt_eval_count`/`eval_count` and timers in `result['inference']`, plus `model_used`. The ledger reads those in the main process; the brain worker is unchanged. Operations without that block are timed only.
5. **Shadow log** (`jarvis/telemetry/shadow.py`) stores proposal and actual side by side, redacted with the existing trace redactor and bounded at 5 MB per decider with one rotation. `agreement()` is the evidence shown before a mode is promoted.
6. **Sealed verifiers** (`jarvis/learning/verifiers/`):
   - **Sealing.** `MANIFEST.json` holds a SHA-256 of each file, with line endings normalised so a CRLF checkout is not tampering. `load()` refuses a changed file. Re-sealing (`python -m jarvis.learning.verifiers --seal`) is a reviewed developer action.
   - **What each verifier reads.** Every verifier declares what it reads. One that reads no real state (file, process, window, page) is weak and is refused.
   - **Verdicts.** `unverifiable` never counts as a pass. An AI-judge verdict is forced to low confidence and marked for re-verification.
7. **Live suite.** It grows to 32 cases (S1–S4, H1–H6, D01–D22). `--repeat`, `--shuffle`, `--seed` and `--telemetry` were added to `benchmarks/live/cases.py`. H1 stays out of automatic batches until the user signs in to Workday.

## Consequences

- Every later phase measures itself with `benchmarks/ledger_report.py` against the Phase 0 baseline.
- The S3, H2 and H3 file checks now come from the sealed verifiers. Tests pin parity with the earlier oracle rules. The Blender verifier now reports "could not look" as `unverifiable` (still a failure) instead of a plain problem.
- New top-level config sections are known to `config_contract`: `telemetry`, `speed`, `control`, `vision`, `recipes`, `fast_path`, `learning`, `memory_v2`, `proactive`. The `control` flags land in `ControlSettings.extra`, so the control defaults are unchanged.
