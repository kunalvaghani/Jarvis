# Brain Phase 0 report: audit and baseline

Date: 2026-11-02. Branch `brain/phase-0-audit`. Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md).

## What was built

- Read-only adapter map: [../ADAPTER_MAP.md](../ADAPTER_MAP.md). It covers every subsystem: entry, I/O, guards, and the brain component it becomes.
- Static inventory: [../inventory/](../inventory/), made by `scripts/brain_inventory.py`.
  - 249 draft node descriptors: 129 tools, 19 methods, 91 MCP tools and 10 routes and verifiers.
  - No duplicate IDs.
  - 8 nodes have no derivable side-effect class. They are left as `unknown`, so Phase 1 must deny them by default.
- Mode switch: `neural.mode`, overridable with the environment variable `JARVIS_BRAIN_MODE=off|shadow|on`. It ships `off`. Rollback is in [../MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md). Tested in `tests/test_neural_mode.py`.
- Libraries the user approved and installed: pydantic 2.14.2, networkx 3.6.1, rustworkx 0.18.1.
- Scenarios: the live suite now has 64 cases, made of 32 base cases, 23 variants and 9 brain scenarios (B01–B09):
  - B01 Spotify, B02 YouTube;
  - B03 a stop mid-task, B04 a worker crash mid-task;
  - B05 two orders at once through the real queue;
  - B06 a privacy and exfiltration refusal;
  - B07 a bug fix, B08 a browser form filled but not submitted;
  - B09 a wireframe first, then approval, then the full model.
- Runner metrics: end-to-end time, first action, model calls, wasted retries, peak RAM and VRAM, and engine build time.
  - Summariser: `scripts/brain_baseline.py`.

## Test evidence

- Unit regression: 5,006 passed and 39 failed. The 39 failures are the same as before Phase 0, so Phase 0 introduced no new failure.
- Legacy baseline, run 1: legacy only, all flags off, full mode (cloud as configured, memory read-only), seed 70.
  - The user stopped it after all 63 cases had run at least once (90 receipts in all), to start implementation first.
  - Run 2 was not started. Repeatability is therefore checked later, against the brain run.
  - Summary file: `benchmarks/results/brain-baseline1-partial.json`.

| Metric (legacy, this PC, 2026-11-02) | Value |
|---|---|
| Verified success | 28/90 receipts (31%) |
| End-to-end p50 / p95 | 109 s / 590 s |
| First action p50 / p95 | 34.6 s / 89.1 s (46 runs acted at all) |
| Model calls per task (mean) | 2.2 |
| Peak RAM (Jarvis and children) / peak VRAM | 929 MB / 2,191 MB |
| Engine build (in-process start) p50 / p95 | 0.5 s / 0.8 s |

Without the upgrade-v2 routes, legacy is weakest at:

- small talk taking file and web tasks (D02, D05, D12, D14, H5, B06);
- folder parsing (D01, H3e–H3g);
- Blender builds (H2*);
- code edits (H3b–H3d);
- the new scenarios: stop, crash, parallel, form and wireframe (B04, B05, B08, B09).

B03 (stop mid-task) passed. B02 was hit by a network outage, so it is not a Jarvis failure.

## Open risks

1. The baseline is a single partial run. Before claiming any gain, the brain must be compared on the same seed.
2. Some side-effect classes are heuristic. All `unknown` and `operation_dependent` nodes must be denied by default, or split per operation, in the Phase 1 registry.
3. MCP schemas need a live `tools/list`. Starting a server requires host approval.
4. Docker was stopped during the survey. The user has since started it.

## Go / no-go

GO for Phase 1. The user has asked to implement the brain first and run all live tests afterwards.
