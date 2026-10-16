# Phase 3 — Measurements

Single runs; real components; temporary fixtures. [before](metrics-before.json) recorded before Phase 3 source changes; [after](metrics-after.json) after the full regression.

| Metric | Before | After |
| --- | --- | --- |
| intent accuracy | 1.0 | 1.0 |
| DAG success rate | 1.0 | 1.0 |
| registry search p50 ms | 3.6267 | 3.7967 |
| contract error rate | 0.0 | 0.0 |
| skill cold load ms (bundled, temp vault) | 18.649 | 146.826 |
| skill context p50 ms | 2.9784 | 3.2245 |

The skill cold load and context now include SQLite identity registration and living ranking; the first `context()` in a 5 s window reads all metrics in one query, later calls use the cache.

## Living-skill and MCP measurements ([living-benchmark.json](living-benchmark.json))

| Measurement | First run (per-skill queries) | After single-read fix |
| --- | --- | --- |
| cold SkillMemory load with store, ms | 146.778 | 164.63 |
| event insert p50 / p95 ms (200) | 6.88 / 7.884 | 7.175 / 9.685 |
| duplicate event ignored p50 ms | 6.4 | 6.469 |
| selected_count after 200 + 50 duplicate inserts | 200 | 200 |
| uncached ranked context p50 / p95 ms | 45.796 / 50.841 | 18.182 / 20.189 |
| CAPTURED incl. real 2-step validation, ms | 4147.6 | 3723.0 |
| MCP synthesis end-to-end (generate, screen, Docker tests), ms | 2919.4 | 2550.4 |
| generated MCP call via ToolRegistry incl. container start p50 ms | 2282.631 | 2330.309 |
| leftover containers | 0 | 0 |

Full regression wall time: Phase 2 run 2 631 s → Phase 3 759 s (36 new tests including real Docker and Blender runs).
No GPU/VRAM measurement; Phase 3 paths do not use the GPU.
