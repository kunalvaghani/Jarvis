# Control-layer rework: progress

Live checklist for the browser + PC control rebuild. Update after every phase and repair iteration. Source of truth: [control architecture](../architecture/control-architecture.md). Layout decisions: [ADR 0001](../adr/0001-control-layer-layout.md).

Branch `claude_ControlArchitect`, starting revision `7e7a39a`. Rollback: [rollback.md](rollback.md).

## Phase status

| Phase | Status | Gate evidence |
|---|---|---|
| 0 Audit, contract, baseline | **PASS** (2026-10-30) | [audit](audit.md), [dependency map](migration-dependency-map.md), [integration contract](integration-contract.md), [rollback](rollback.md), [baseline.json](../../benchmarks/results/baseline.json), pytest log (local, gitignored: `benchmarks/results/baseline-pytest-2026-10-30.log`) |
| 1 Core contracts | **PASS** (2026-10-30) | `jarvis/control/` 13 modules; 79 passed / 1 skipped on Python 3.10.6 and 3.11.9; line coverage **100%** (969 statements); `mypy --strict` clean ([mypy.ini](../../mypy.ini)). Skip = symlink creation needs a privilege this account lacks; the junction-escape test covers the same attack and passes. |
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

## User decisions (2026-10-30) — [ADR 0002](../adr/0002-user-decisions-phase0.md)

1. Test directory `D:\Phython Project\TestCodes`; automation confined to `TestCodes\jarvis-control-tests\`.
2. Two browser profiles: clean test profile for benchmarks, personal profile seeded from the user's Chrome. **Open:** which Chrome profile (`Profile 1` folder is stale from 2024; `Default`/"Person 1" is the active one), and a moment when Chrome may be closed for the copy.
3. Installed and pinned: mss 10.2.0, dxcam 0.3.0, uiautomation 2.0.29, mypy 2.4.0, coverage 7.16.2, pytest-cov 7.1.0.
4. Move to Python 3.11 side by side: `.venv311` (3.11.9) built with the **identical 120-package set** of `.venv`. Full-suite comparison running; launcher switch only after parity.
5. Gmail-in-Chrome becomes a router-selected app adapter (API connector first, send always approved, excluded from automated benchmarks).

## Python 3.11 migration

| Step | Status |
|---|---|
| `.venv311` created from Python 3.11.9 with the identical package set | DONE |
| Control-layer tests on 3.11 | PASS (79/1 skip) |
| Full suite on 3.11 vs 3.10 baseline | RUNNING |
| Launcher check on 3.11 | TODO |
| Switch `Start Jarvis.cmd` / bootstrap / manifest; keep `.venv` as rollback | TODO (after parity) |
| Secondary venvs (brain, f5, harness, openviking, skills, training) | TODO, one at a time |

## Open issues

- No emergency stop for in-flight control exists today (only proactive-awareness stop).
- Owned browser has no URL policy/request hook; refuses multi-tab.

## Next step

Finish the 3.11 parity comparison. Then Phase 2: Route 2 (browser) executor on the clean test profile against a local test site, then Route 3 (UIA) against Notepad/Calculator/Explorer in the test folder.
