# Phase 4 — Measurements

Phase 1 metric harness: [before = Phase 3 after](../phase-03/metrics-after.json) (same commit `6f88033`, recorded just before Phase 4 work); [after](metrics-after.json) (written from the final Phase 4 source by the trailing step of a run that was stopped for the Docker restart; the source did not change afterwards).

| Metric | Before | After |
| --- | --- | --- |
| intent accuracy | 1.0 | 1.0 |
| DAG success rate | 1.0 | 1.0 |
| registry search p50 ms | 3.7967 | 3.6329 |
| contract error rate | 0.0 | 0.0 |
| skill context p50 ms | 3.2245 | 3.3445 |

Phase 4 specific measurements (lesson retrieval, exploration, real vault index, RSS) are in [findings-and-limitations.md](findings-and-limitations.md), with raw data in [memory-benchmark.json](memory-benchmark.json) and [real-vault-index.json](real-vault-index.json).

Full regression wall time: Phase 3 759 s → Phase 4 887 s (21 new tests incl. real browser, Blender and OpenViking server runs).
