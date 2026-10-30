# Control-layer rework: progress

Live checklist for the browser + PC control rebuild. Update after every phase and repair iteration. Source of truth: [control architecture](../architecture/control-architecture.md). Layout decisions: [ADR 0001](../adr/0001-control-layer-layout.md).

Branch `claude_ControlArchitect`, starting revision `7e7a39a`. Rollback: [rollback.md](rollback.md).

## Phase status

| Phase | Status | Gate evidence |
|---|---|---|
| 0 Audit, contract, baseline | **PASS** (2026-10-30) | [audit](audit.md), [dependency map](migration-dependency-map.md), [integration contract](integration-contract.md), [rollback](rollback.md), [baseline.json](../../benchmarks/results/baseline.json), pytest log (local, gitignored: `benchmarks/results/baseline-pytest-2026-10-30.log`) |
| 1 Core contracts | **PASS** (2026-10-30) | `jarvis/control/` 13 modules; 79 passed / 1 skipped on Python 3.10.6 and 3.11.9; line coverage **100%** (969 statements); `mypy --strict` clean ([mypy.ini](../../mypy.ini)). Skip = symlink creation needs a privilege this account lacks; the junction-escape test covers the same attack and passes. |
| 2 Route executors | **IN PROGRESS** | Route 2 browser: built ([ADR 0003](../adr/0003-browser-route-cdp-refs.md)), 11/11 integration tests on real installed Chrome vs the [D1 site](../../benchmarks/sites/d1/), stable over 5 repeat runs, 3.10 and 3.11. Latency (headless, warm, n=30, 2026-10-30): ref click+verify p50 **84.6 ms** / p95 95.8 ms (target p50 ≤ 400 ms); form_input+readback p50 80.3 ms; local navigate p50 45.7 ms; cold start 1.3 s ([route-latency.json](../../benchmarks/results/route-latency.json)). Headful latency not yet measured. **Route 3 UIA: PASS on the real desktop** (2026-10-30, user present, Notepad closed): `test_control_uia.py` 4/4, three consecutive runs. Covers Notepad type, save and read back from disk; Calculator by AutomationId through InvokePattern, then keyboard `escape 7` verified by display read-back; the title guard refusing keys for the wrong document; Explorer confined to the approved folder; and policy refusals. `jarvis/control/routes/uia.py` uses comtypes `IUIAutomation` with cache requests, not the `uiautomation` package (that package forces DPI v1 on import). It detects elevated targets, the secure desktop, a protected window in front, and Chromium windows with accessibility off. An earlier run, with the user idle 43 min and a protected `GameInputServiceWindow` in front, showed Windows dropping all injected input; that case is now reported, never silent. Repair made in this pass: the keyboard test now waits on a `probe_equals` expectation (Calculator applies keys asynchronously; a single immediate read was a test race). **Route 4 vision: built** ([ADR 0004](../adr/0004-vision-route-grounding.md)). It uses local `qwen3-vl:2b`, escalating to `qwen3-vl:4b` only on a refusal (one model on the GPU at a time); coarse-then-crop grounding, label read-back and a pre-click screen-change check. 21 unit tests. Benchmark (2026-10-30, 32+3 D1 targets, [vision-grounding.json](../../benchmarks/results/vision-grounding.json)): **93.8% hits, 0 wrong clicks, 0 clicks on absent targets**, p50 3.2 s, p95 25.6 s, peak VRAM 2.76 GB. Without escalation, 2B alone scored 81.2%. Live desktop click on a real Chrome canvas: 3/3. **Route 1 API: core built** (`jarvis/control/routes/api.py`). It has a typed adapter registry with risk tiers and approval for every Tier-2 call, calls each adapter exactly once, and reports a failure after a write started as uncertain. A `FileAdapter` confined to the approved roots does atomic create (never overwrites) and replace-by-expected-hash (approval required), each read back by hash; there is no delete. 9 tests, 91% line coverage. Wrapping the existing app, Office COM and Gmail adapters is Phase 5. |
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
2. Two browser profiles: clean test profile `.jarvis-runtime/test-browser-profile` (created empty, for benchmarks), personal profile `.jarvis-runtime/personal-browser-profile` copied from the user's Chrome `Default` ("Person 1") on 2026-10-30 with Chrome closed, caches excluded (3,355 files, 1.15 GB, 0 failures). **Finding:** 4,004 of 4,108 cookies use Chrome's app-bound (`v20`) encryption, which by design does not work in a copied profile; plain `chrome.exe` on the copy read 31 and deleted the rest from the copy. The source profile is untouched. Carried over: history (8,104 URLs), autofill (824), 16 extensions, settings. Not carried: website sign-ins and account-stored passwords and bookmarks; they need the user to sign in to Chrome inside the Jarvis profile once (sync).
3. Installed and pinned: mss 10.2.0, dxcam 0.3.0, uiautomation 2.0.29, mypy 2.4.0, coverage 7.16.2, pytest-cov 7.1.0.
4. Move to Python 3.11 side by side: `.venv311` (3.11.9) built with the **identical 120-package set** of `.venv`. Full-suite comparison running; launcher switch only after parity.
5. Gmail-in-Chrome becomes a router-selected app adapter (API connector first, send always approved, excluded from automated benchmarks).

## Python 3.11 migration

| Step | Status |
|---|---|
| `.venv311` created from Python 3.11.9 with the identical package set | DONE |
| Control-layer tests on 3.11 | PASS (79/1 skip) |
| Full suite on 3.11 vs 3.10 baseline | **PASS**: identical 39 pre-existing failures, none new (after fixing the SQLite handle leak) |
| Launcher check on 3.11 | **PASS** (`ready`) |
| Switch | **DONE**: `.venv` rebuilt as 3.11.9 with the identical package set; 3.10 kept at `.venv310`; no launcher edits needed. Final full run on the switched `.venv`: 4617 passed / 39 failed (same set) / 156 skipped |
| Remove `.venv311` | **DONE** (2026-10-30, user-approved; nothing referenced it) |
| Secondary venvs (brain, f5, harness, openviking, skills, training) | TODO, one at a time |

## Regression after routes 3 and 4 (2026-10-30)

Full suite on `.venv` 3.11.9: **4637 passed / 39 failed / 156 skipped** in 1242 s. The 39 failures are the same set as the Phase 0 baseline, with the same per-file distribution; nothing new fails. Launcher check: `ready`.

Re-run after the vision escalation and the Gmail status messages (2026-10-30): **4646 passed / 39 failed / 156 skipped** in 1251 s. Same 39 failures, same per-file distribution. Launcher check: `ready`.

## Open issues

- Vision grounding: resolved for D1 by the 2B→4B escalation (93.8%, 0 wrong clicks). Task-level accuracy will be measured in Phase 7. The escalation p95 is about 25 s.
- **Gmail by voice (user decision 5), 2026-10-30.** The voice workflow (`gmail_workflows.run_gmail`, read, draft, send with per-send approval, trash, label) uses the Gmail API, which the user had connected. It stopped working for two reasons:
  1. `gmail_api.py` changed after its 2026-10-10 verification, so `configured()` correctly refuses.
  2. Google now rejects the saved refresh token with `invalid_grant` (expired or revoked; a Testing-mode OAuth app expires sign-ins after 7 days).

  **Done:**
  - Reviewed the adapter diff since the verified version `b54c0c1`: hardening plus a draft-only attachment helper, with the same scopes and no new send path.
  - Jarvis now names the cause and the one fix (`gmail_api.status()` / `unavailable()`), instead of "not available".
  - Gmail tests: 114 passed.

  **User action:** run `launchers/Connect Jarvis Gmail API.cmd` once and approve the Google sign-in.

  **Chrome path:** the `gmail_chrome` fallback never passed validation ("Invalid Gmail extension readback", 2026-10-10). All utility tools are currently inactive because their validation report is stale. Re-validating it needs a live draft in the user's own Chrome, so it is not used as an automatic fallback.

- Playwright `context.route` does not see redirect hops (verified 2026-10-30). Document navigations are therefore fetched hop by hop with redirects off; **subresource redirects are not hop-checked** (only the first URL is). Residual SSRF-by-subresource-redirect risk is recorded for Phase 6.
- Python 3.11: first full run showed 28 extra failures. All were one real bug: SQLite connections in `catalog.py`, `folder_lookup.py` and `repository_skills.py` were never closed (`with sqlite3.connect()` only commits). Fixed with the repo's existing `closing(...)` / contextmanager idioms; the 43 affected tests now pass on 3.10 and 3.11. Full 3.11 re-run pending.
- No emergency stop for in-flight control exists today (only proactive-awareness stop).
- Owned browser has no URL policy/request hook; refuses multi-tab.

- Real-desktop finding (2026-10-30): with a protected or elevated window in front, Windows (UIPI) silently drops all injected keys and clicks. The new layer now detects that up front, and confirms a SendInput pointer move landed before pressing, so this is reported as `elevated_target` with "click your desktop once", never as a silent success.

## Integration, island UI and connection check (2026-10-30)

- **Connection check:** `python -m jarvis.control.health`, also the planner tool `control_check`. It runs 10 checks with live island progress. Live result on this PC: **8 ready, 2 need the user**: one Chrome sign-in in the personal profile, and a Gmail reconnect.
- **Island:** [island_control.py](../../jarvis/island_control.py) adds four animated route tiles (browser, Windows apps, vision, apps & files), outcome glyphs, a determinate step bar and a header badge that stays visible while the task workspace is open. 44 render/animation tests.
- **Integration:**
  - `Actions.control()` owns the routes, with host approval cards and island progress.
  - New planner tools: `web_open`, `web_read`, `web_act`, `app_open`, `app_read`, `app_act`, `screen_act` and `control_check`.
  - Website requests ("open example.com and …") now reach the planner instead of the app opener.
  - The planner prompt and the `browse` description now steer reading and acting on pages to `web_*`.
  - Jarvis's stop now reaches long control waits.
- **End-to-end smoke check** (typed request → planner → `web_open` → `web_read`, island cards streamed): it ran, but the final answer was not verified, because `web_open` returns only interactive elements and so not the heading text. This is a known defect for the live loop.
- **Regression:** 4704 passed / the same 39 baseline failures after refreshing the architecture tool inventory (prior table preserved), plus 1 inventory test fixed in place. Launcher check: `ready`. `mypy --strict`: clean (23 files).
- **Live acceptance plan:** [live-acceptance-plan.md](live-acceptance-plan.md), 13 cases. **Awaiting user approval; none executed.**

## Next step

Wait for the user's approval of the live acceptance plan, then run it with the no-assistance rules in that plan.
