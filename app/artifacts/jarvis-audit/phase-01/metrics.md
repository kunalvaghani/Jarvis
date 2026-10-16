# Phase 1 — Before/after measurements

Single runs of `scripts/verification/phase_baseline.py` on this machine (real Jarvis components, synthetic fixtures, no model/network/desktop). Before: [metrics-before.json](metrics-before.json) (pre-fix source). After: [metrics-after.json](metrics-after.json). Timing differences between single runs are within run-to-run noise and are **not** claimed as improvements; the functional change is the malformed-proposal contract (D1). [metrics-before-initial-disabled-skill-path.json](metrics-before-initial-disabled-skill-path.json) is preserved: its skills section measured a disabled short-circuit and was superseded before any source fix.

| Metric | Before | After |
| --- | --- | --- |
| intent accuracy | 1.0 | 1.0 |
| intent p50 ms | 0.5087 | 0.495 |
| intent p95 ms | 10.7323 | 10.5111 |
| privacy correct/16 | 15 | 15 |
| private->public | 0 | 0 |
| DAG success rate | 1.0 | 1.0 |
| DAG steps/run | 9 | 9 |
| DAG p50 ms | 13.1532 | 11.8528 |
| DAG p95 ms | 18.3378 | 12.4418 |
| DAG cancel return ms | 112.399 | 112.047 |
| registry catalog p50 ms | 0.4805 | 0.4604 |
| registry search p50 ms | 3.264 | 3.1561 |
| malformed outcomes | {'unexpected:TypeError': 2, 'ValueError': 4, 'ToolArgumentError': 6} | {'ToolArgumentError': 10, 'ValueError': 2} |
| contract error rate | 0.166667 | 0.0 |
| malformed dispatched | 0 | 0 |
| skills loaded | 10 | 10 |
| skill cold load ms | 19.592 | 18.681 |
| skill context p50 ms | 3.2494 | 3.0605 |
| DAG peak traced bytes | 385850 | 386446 |
| registry peak traced bytes | 345602 | 296275 |
| process RSS start / end (bytes) | 20439040 / 45912064 | 20623360 / 46206976 |

Full regression wall time: 602.2 s before, 576.6 s after (JUnit suite time; different test counts).

Peak traced bytes come from `tracemalloc` per section; RSS from psutil for the metrics process. No GPU/VRAM measurement was taken in Phase 1.
