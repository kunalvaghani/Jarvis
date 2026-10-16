# Phase 1 — Commands, results and classifications

All runs from `app/` on 2026-10-16/17 IST, Windows 11 (10.0.26200), Python 3.10.6 (`.venv`), branch `claude`.
Logs and JUnit XML in this folder are the primary evidence; nothing below is estimated.

## Commands

```powershell
# Baseline (before any fix) — 2026-10-16 23:35:15 → 23:45:24 IST
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --junitxml=artifacts/jarvis-audit/phase-01/baseline-full-regression.xml
# Static checks
.venv/Scripts/python.exe -m compileall -q jarvis scripts tests main.py jarvis_bootstrap.py
<python with scratch pyflakes 3.2.0> -m pyflakes jarvis scripts main.py jarvis_bootstrap.py   # tool not added to the project
<scratch import_all.py>  # imports each jarvis module in its own subprocess → module-imports-*.json
<scratch except_census.py>  # AST census → silent-exception-census.json
# Metrics (real components, synthetic fixtures)
.venv/Scripts/python.exe scripts/verification/phase_baseline.py --label phase01-before --out artifacts/jarvis-audit/phase-01/metrics-before.json
.venv/Scripts/python.exe scripts/verification/phase_baseline.py --label phase01-after  --out artifacts/jarvis-audit/phase-01/metrics-after.json
# Targeted
.venv/Scripts/python.exe -m pytest tests/test_phase01_baseline.py -q
.venv/Scripts/python.exe -m pytest tests/test_architecture_audit.py tests/test_skill_selection_audit.py tests/test_browser_playwright_audit.py -q
# After fixes — launcher readiness, then full regression (2026-10-17 00:03:20 → 00:13:00 IST)
.venv/Scripts/python.exe -m jarvis.launcher --check > artifacts/jarvis-audit/phase-01/launcher-check.json
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --junitxml=artifacts/jarvis-audit/phase-01/after-full-regression.xml
```

## Results

| Check | Kind | Result | Evidence |
| --- | --- | --- | --- |
| Full regression, baseline | regression | 3,321 collected: **3,173 passed / 147 skipped / 1 failed** (602 s) | [log](baseline-full-regression.log), [xml](baseline-full-regression.xml) |
| Full regression, after fixes | regression | 3,340 collected: **3,193 passed / 147 skipped / 0 failed** (577 s) | [log](after-full-regression.log), [xml](after-full-regression.xml) |
| `tests/test_phase01_baseline.py` | unit/integration (real components, temp dirs) | **19 passed** | after-run XML |
| Phase 1 tests against original code (fixes stashed) | defect reproduction | D1 ×4, D3, D4 ×2, D5 **failed as expected**; D2 ×2 passed (no behaviour change) | console, see [defects.md](defects.md) |
| `test_JRV_29_012` under CPU load | flake reproduction | original: 1/6 fail at 1× load, 2/2 fail at 3×; fixed: 6/6 pass at 1× | [defects.md](defects.md) D6 |
| Agent-event related suites | regression | 119 passed / 3 skipped | console |
| Launcher `--check` | readiness (dependencies + configured services) | **ready**, 2 m 18 s; Docker 29.8.2 available; Ollama required models present; Groq `optional_not_live_checked` | [launcher-check.json](launcher-check.json) |
| compileall | static | 0 errors | — |
| Module imports | static/runtime | 229/231 before; 230/232 after (new module imports); the 2 failures are separate-interpreter modules by design | [before](module-imports-before.json), [after](module-imports-after.json) |
| Tracked artifacts unchanged by test run | evidence preservation | PASS after D5 (`git status` clean outside intended changes) | git status after run |

Baseline run caveat: the first source edit (`jarvis/tools.py`, 23:44:06) landed ~78 s before the baseline run finished.
pytest imports in-process modules at collection (23:35), so in-process tests used original code; a late subprocess-based
test could in principle have loaded the edited file. The baseline failure (D6) is a Node fixture unrelated to that file.

## Classification for the phase mandate

| Mandate item (Phase 1 brief, Step 4) | Status | Basis |
| --- | --- | --- |
| Voice/intent routing and deterministic commands | PASS (fixture) | 2,400/2,400 authored phrasings; existing intent suites in full run |
| DAG planning, references, dependencies, cancellation | PASS (fixture) | metrics DAG section (20 runs, 1 effect dispatch/run, cancellation) + existing `test_dag_planning_audit.py`, `test_hierarchical.py` |
| ToolRegistry discovery, permissions, execution | PASS (fixture) | D1 fix + `test_tool_registry_audit.py`, metrics |
| Desktop UIA, browser automation, tool fallbacks | PASS (fixture) / live BLOCKED | existing `test_desktop_control_audit.py`, `test_browser_playwright_audit.py` (owned headless browser); no live desktop acceptance this phase |
| Memory, skills, repo learning, self-evolution | PASS (fixture) | existing suites + D4; no live vault/model run |
| Groq privacy isolation and local fallback | PASS (fixture) / live NOT RUN | 0/16 private→public; `test_groq.py`, `test_model_routing_audit.py` with fake transport; no live cloud call |
| Recovery, idempotency, worker health, checkpoints | PASS (fixture) | `test_recovery.py`, `test_crash_resume.py`, `test_task_recovery.py`; launcher ready |
| Resource scheduling and foreground responsiveness | PASS (fixture) / live BLOCKED | `test_gpu_scheduler*.py`; no GPU workload run (would compete with the user's session) |
| 147 pre-existing skips | BLOCKED (pre-existing) | every skip message begins `BLOCKED:`; reasons recorded by earlier prompts (catalog contracts, live GPU/voice gates, plugin namespace) |

**Phase gate:** all mandatory locally executable checks pass (0 failures, launcher ready). Live account, microphone,
GPU-contention and desktop acceptance checks are BLOCKED/NOT RUN as listed — they are not claimed.
