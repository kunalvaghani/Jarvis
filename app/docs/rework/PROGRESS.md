# Control-layer rework: progress

Live checklist for the browser + PC control rebuild. Update after every phase and repair iteration. Source of truth: [control architecture](../architecture/control-architecture.md). Layout decisions: [ADR 0001](../adr/0001-control-layer-layout.md).

Branch `claude_ControlArchitect`, starting revision `7e7a39a`. Rollback: [rollback.md](rollback.md).

## Phase status

| Phase | Status | Gate evidence |
|---|---|---|
| 0 Audit, contract, baseline | **GATE PASSED, awaiting user answers before Phase 1** | [audit](audit.md), [dependency map](migration-dependency-map.md), [integration contract](integration-contract.md), [rollback](rollback.md), [baseline.json](../../benchmarks/results/baseline.json), [pytest log](../../benchmarks/results/baseline-pytest-2026-10-30.log) |
| 1 Core contracts | NOT STARTED | — |
| 2 Route executors | NOT STARTED | — |
| 3 MCP research/selection | NOT STARTED | — |
| 4 Validation harness | NOT STARTED | — |
| 5 Integration | NOT STARTED | — |
| 6 Security hardening | NOT STARTED | — |
| 7 Controlled benchmark + regression | NOT STARTED | — |
| 8 Live acceptance | NOT STARTED | — |
| 9 Final autonomy demo | NOT STARTED | — |
| 10 Cleanup | NOT STARTED | — |

## Phase 0 results (2026-10-30)

**Existing suite (old system), `.venv` Python 3.10.6, 1318 s:** 4532 passed, **39 failed**, 150 skipped.
All 39 failures are in coding-agent tests (`test_coder` 17, `test_coding_workflow` 7, `test_gui_edits` 5, `test_code_stream` 2, `test_claude_code` 2, `test_agent_runtime` 2, `test_native_coding_audit`, `test_codex_workload`, `test_codex_code`, `test_callback_contract` 1 each). Causes: 34 × `TypeError: expected str … not Mock` and 4 × `SimpleNamespace has no attribute 'base'` (test fixtures behind recent coder changes merged from the paused campaign), and 1 prompt-text assertion. **No browser, UIA, vision or input test failed.** These pre-existing failures are the regression baseline; the rework must not add to them.

**Launcher readiness:** `python -m jarvis.launcher --check` → `ready`, nothing missing (Docker, Ollama, LocalGithub available; Groq not live-checked).

**In-process decisions of the old stack** ([baseline.json](../../benchmarks/results/baseline.json)): explicit-plan regex p50 0.030 ms; argument validation ≤ 0.004 ms; **`execution_adapters.desktop_order` p50 1.13 ms because it re-reads `config.json` on every UIA dispatch** (over the 1 ms routing target on its own).

**Controlled tasks on the old system:** 7 skeleton tasks defined; **0 executed, status BLOCKED** until the test directory and a clean browser profile are approved.

## Open questions for the user (blocking Phase 1+ live work)

1. Approved test directory for file operations.
2. Test browser profile: the owned profile `.jarvis-runtime/browser-profile` has `Login Data`/`Cookies`, so a new empty profile is proposed.
3. Installs: `mypy` and `coverage` (Phase 1 gate), `mss` and/or `dxcam` (vision capture), later `uiautomation`. Nothing installed yet.
4. Python 3.11+ (prompt) vs the current 3.10.6 runtime.
5. `gmail_chrome_worker` drives the user's own Chrome; keep it out of the new routing, or keep it as an explicit opt-in.

## Open issues

- No emergency stop for in-flight control exists today (only proactive-awareness stop).
- Owned browser has no URL policy/request hook; refuses multi-tab.

## Next step

Phase 1: `jarvis/control/` contracts (types, executor, refs, coords, policy, batch, verify, router, recovery, locks, audit, timing) with unit tests, after the user answers the questions above.
