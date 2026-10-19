# Stage 5 — Performance and resources versus the Phase 1 baseline

Measured 2026-10-19 on the same machine (16 logical CPUs, 31.3 GB RAM, RTX 3050 Laptop 4 GB, Windows 11 build 26200)
by [`scripts/verification/phase08_final_benchmarks.py`](../../../scripts/verification/phase08_final_benchmarks.py).
Raw data: [benchmarks/final-benchmarks.json](benchmarks/final-benchmarks.json),
[benchmarks/harness-final.json](benchmarks/harness-final.json). Baseline: Phase 1
[metrics-before.json](../phase-01/metrics-before.json) at commit `5b52737`. Single runs on a desktop in active use;
millisecond-level differences under about 20 % are within the noise seen between phases.

## Paired harness (identical workload before and after)

| Measure | Phase 1 (`5b52737`) | Final (`bd8f837`) | Reading |
| --- | --- | --- | --- |
| Intent routing accuracy (2,400 permutations) | 1.0 | 1.0 | unchanged |
| Intent routing p50 | 0.509 ms | 0.516 ms | unchanged (noise) |
| Privacy routing: private marked public | 0 | 0 | unchanged |
| Privacy classification p50 (model-routing overhead) | 0.034 ms | 0.033 ms | unchanged |
| DAG success rate (fixture DAG ×20) | 1.0 | 1.0 | unchanged |
| DAG run p50 | 13.15 ms | 12.55 ms | unchanged (noise) |
| Cancellation return (requested at 100 ms) | 112.4 ms | 108.6 ms | unchanged |
| Tool catalog size | 85 | 98 | +13 tools |
| Tool search p50 | 3.26 ms | 3.87 ms | **+19 % slower** (more tools and routes) |
| Tool contract error rate (malformed proposals) | 0.167 | 0.0 | **fixed** (Phase 1 D1) |
| Skill goals with a selected skill | 20/20 | 20/20 | unchanged |
| Skill context p50 | 3.25 ms | 3.04 ms | unchanged (noise) |
| Harness process RSS | 43.8 MB | 45.3 MB | +1.5 MB |

## New measurements (no Phase 1 equivalent)

| Measure | Value |
| --- | --- |
| Deterministic command parse (10 phrases) | p50 2.49 ms per command (24.9 ms per batch; first-call max 624 ms) |
| Tool search for an office request (registry, 98 tools) | p50 1.82 ms |
| Held-out tool selection (MRR / hit@5) | 0.598 / 0.790 (authored oracle; no Phase 1 equivalent) |
| Held-out lesson retrieval precision@1 (lexical) | 0.90 |
| ReasoningBank retrieval p50 | lexical 1.19 ms; local embeddings (nomic-embed-text) 102 ms |
| Prompt routing (10 phrases) | p50 0.34 ms per batch |
| AZR abduction oracle (30 tasks, all orders) | 12.4 ms per batch |
| Idle self-evolution thread (20 s, research disabled) | below Windows CPU-time resolution (< ~0.08 % of one core); 17.8 MB process RSS |
| GPU memory when idle | 405 MiB of 4,096 MiB used, 0 % utilisation |

## Recorded results from earlier phases (real runs, cited)

| Measure | Value | Source |
| --- | --- | --- |
| OpenViking search p50 (real vault) | 127 ms | Phase 4 |
| Show Me Once capture / verified replay | 3.9 s / 14.1 s | Phase 5 |
| Cloud privacy gate on a generic problem | 4.6 ms | Phase 5 |
| Gate time per qualified source candidate | 4–5 min (domain suites dominate) | Phase 6 |
| Synthetic DAG makespan (critical-path proposal, not deployed) | 363 → 308 ms | Phase 6 |
| Checkpoint improvement (held-out AZR) | 0/165 → 9/165 merged | Phase 7 |
| Training resources | peak 1,994 MB VRAM, 2.6 GB RSS, 9.6 min for 120 steps | Phase 7 |
| Cancellation / restart correctness | exact resume (loss difference 0.0); preempted at step 3 | Phase 7 |
| Real usage before the upgrade (2026-09-27 → 2026-10-14) | 313 tool calls, 28 failed (8.9 %) | local agent-event log |

## Not measured (and why)

| Measure | Reason |
| --- | --- |
| Voice-to-action latency | needs a live microphone session in the running app |
| Task-planning latency with the live planner model | needs the running brain worker with qwen3.5:9b; not exercised in this phase |
| Verified task completion and failure frequency after the upgrade | Jarvis was not run interactively after the upgrade; there is no post-upgrade user traffic |
| Browser/UIA action count on real sites | not re-measured; Phase 2 records structured-first ordering on fixtures |
| Full application RAM/VRAM | the full UI was not launched; component figures above only |
| Live coding-task success | not repeated; Phase 7 induction accuracy is the only coding-quality figure for the new model |
