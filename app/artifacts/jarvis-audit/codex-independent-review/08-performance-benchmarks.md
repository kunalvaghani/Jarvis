# Independent Jarvis audit checkpoint — 2026-10-19 IST

Pinned `claude`: `36fbf3ce925080f7f54afa87eaf1d9b88414142d`. Isolated branch `codex-review`. This package reports actual execution, not a certification of the entire assistant.

Paired baseline/candidate measurements use exact baseline source loaded from Git and current repaired source. Each scenario has 500 warm samples per version, alternating order, plus one first-call pair. All data are synthetic. Standard deviation, p95, min/max and first-call observations are in paired-benchmarks.json. No confidence interval or general improvement claim is inferred from a single session.

| Scenario | Baseline median ms | Candidate median ms | Absolute delta ms | Relative delta |
|---|---:|---:|---:|---:|
| state_200_public_elements | 0.032100 | 0.055400 | +0.023300 | +72.59% |
| empty_lease_read | 0.267100 | 0.274350 | +0.007250 | +2.71% |

These are safety-check overhead regressions. The lease first-call candidate includes importing the shared validator and must not be described as warm cost. UIA objects are synthetic; these timings omit COM latency. No 5–10 second assistant response target, training gain, acoustic latency, model throughput, real desktop task speed, sustained throughput or startup target has been proven. Concurrent regression activity and OS scheduling add measurement uncertainty.
