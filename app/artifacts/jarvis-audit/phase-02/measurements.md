# Phase 2 — Measurements

## Phase 1 metric harness before vs after Phase 2

Single runs of `scripts/verification/phase_baseline.py` (real components, synthetic fixtures): [before](metrics-before.json) was recorded before any Phase 2 source change, [after](metrics-after.json) after it. Single-run timing differences are noise unless large; the catalog grew by the nine new tools.

| Metric | Before | After |
| --- | --- | --- |
| intent accuracy | 1.0 | 1.0 |
| intent p50 ms | 0.5032 | 0.4891 |
| privacy private->public | 0 | 0 |
| DAG success rate | 1.0 | 1.0 |
| DAG steps/run | 9 | 9 |
| DAG p50 ms | 11.6924 | 11.5284 |
| registry catalog size (fixture actions) | 85 | 94 |
| registry catalog p50 ms | 0.4457 | 0.4759 |
| registry search p50 ms | 3.0948 | 3.635 |
| contract error rate | 0.0 | 0.0 |
| skill context p50 ms | 3.1549 | 3.0143 |

## Execution methods (real software, disposable fixtures)

From [execution-benchmark.json](execution-benchmark.json), measured 2026-10-16T19:24:40+00:00. Latency includes process start and the independent readback; it is wall time for a whole verified operation.

| Method | Status | Runs | p50 ms | max ms |
| --- | --- | --- | --- | --- |
| strategy_execute -> xlsx.openpyxl (API) | MEASURED | 5 | 2677.2 | 2796.2 |
| xlsx.excel_com (structured, native Excel) | MEASURED | 3 | 8284.4 | 8335.8 |
| docx.python_docx (API) | MEASURED | 5 | 471.7 | 479.7 |
| docx.word_com (structured, native Word) | MEASURED | 2 | 7726.7 | 8393.6 |
| pdf.pypdf compose (API) | MEASURED | 5 | 1671.3 | 1690.7 |
| blender.background create + readback (API) | MEASURED | 2 | 2142.5 | 2175.7 |
| windows.uia fill_text (structured, disposable window) | MEASURED | 5 | 78.2 | 125.2 |

## Step count

* API path: measured [2] `ToolRegistry` calls per spreadsheet edit (outer `strategy_execute` + nested adapter), independently verified.
* GUI path: 8 steps in an **authored reference plan** (open budget.xlsx, observe window, select Name Box, fill_text B2, observe selection, type_text 42, shortcut ctrl+s, observe save state). It was **not executed**; no GUI latency is claimed.
* Phase 1 baseline had no document-edit path to compare against (its DAG fixture used synthetic read/write tools: 9 steps, p50 above).

## Interpretation limits

* The API spreadsheet edit (~2.7 s p50) is dominated by four short-lived `.venv-skills` worker processes (pre-read, write, independent readback, plan feature check). This is a deliberate trade of latency for independent verification; it is not optimised in this phase.
* Native Office paths (~8 s) include starting a new hidden Office instance per operation.
* Registry search p50 rose from 3.09 to 3.64 ms (single runs) with nine more tools to rank; catalog p50 is unchanged within noise.
* No GPU/VRAM measurement was taken; none of these methods uses the GPU.
