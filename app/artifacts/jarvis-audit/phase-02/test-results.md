# Phase 2 — Commands, results and classifications

Run from `app/` on 2026-10-17 IST with `.venv/Scripts/python.exe` (Python 3.10.6), branch `claude`.

## Commands

```powershell
# Pre-upgrade baseline (before any Phase 2 source change)
.venv/Scripts/python.exe -m pytest tests/test_brain.py tests/test_capabilities.py tests/test_tools.py tests/test_tool_registry_audit.py tests/test_execution_router.py tests/test_desktop_actions.py tests/test_desktop_control_audit.py tests/test_browser_playwright_audit.py tests/test_toolkits.py tests/test_agent_runtime.py tests/test_documents.py tests/test_independent_cursor.py tests/test_jarvis_pointer.py tests/test_visual_fallback.py tests/test_utility_skills.py tests/test_phase01_baseline.py -q --junitxml=artifacts/jarvis-audit/phase-02/pre-upgrade-relevant.xml
.venv/Scripts/python.exe scripts/verification/phase_baseline.py --label phase02-before --out artifacts/jarvis-audit/phase-02/metrics-before.json
# Dependencies (separate utility environment only)
.venv-skills/Scripts/python.exe -m pip install --isolated openpyxl==3.1.5 python-docx==1.2.0
# Phase 2 tests and measurements
.venv/Scripts/python.exe -m pytest tests/test_phase02_execution_strategy.py -q
.venv/Scripts/python.exe scripts/verification/phase02_execution_benchmark.py --out artifacts/jarvis-audit/phase-02/execution-benchmark.json
.venv/Scripts/python.exe scripts/verification/phase_baseline.py --label phase02-after --out artifacts/jarvis-audit/phase-02/metrics-after.json
# Regression
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe -m pytest tests -q --junitxml=artifacts/jarvis-audit/phase-02/full-regression.xml
```

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Pre-upgrade relevant suites | 390 passed / 4 skipped | [pre-upgrade-relevant.log](pre-upgrade-relevant.log) |
| `tests/test_phase02_execution_strategy.py` | 30 passed (see per-test real/mock labels in the module docstring and test names) | full-regression XML |
| Full regression after Phase 2 | Run 1: 3,220 passed / 147 skipped / **3 failed** (all `trace_contract` strict event-list assertions not expecting `tool.outcome` rows; [run1 log](run1-full-regression.log)). Helper corrected (lifecycle rows checked exactly; outcome rows must correlate). Run 2: **3,223 passed / 147 skipped / 0 failed**, 631 s | [full-regression.log](full-regression.log), [xml](full-regression.xml) |
| Launcher `--check` | **ready**; Docker 29.8.2; Ollama models present; Groq optional, not live-checked | [launcher-check.json](launcher-check.json) |
| Execution benchmark | all 7 methods MEASURED | [execution-benchmark.json](execution-benchmark.json) |

## Required-test classification (Phase 2 brief)

| # | Requirement | Status | Basis |
| --- | --- | --- | --- |
| 1 | Edit XLSX, values/formulas survive | **PASS (real)** | P02_01 (openpyxl), P02_07 (native Excel, chart preserved, values recalculated) |
| 2 | Modify DOCX, verify structure | **PASS (real)** | P02_02 (python-docx), P02_02c (native Word), P02_02b refusal |
| 3 | Process PDF, verify output | **PASS (real)** | P02_03 text, merge/extract/rotate, sources unchanged, no overwrite |
| 4 | Blender disposable scene | **PASS (real Blender 4.4.3)** | P02_04, P02_04b |
| 5 | Browser DOM on controlled page | **PASS (real headless Chrome)** | P02_05 loopback page fill + click + DOM readback |
| 6 | Structured UIA on disposable Windows app | **PASS (real UIA)** | P02_06 disposable Win32 window; UFO provider; pointer not used |
| 7 | API failure → safe fallback | **PASS (mock handlers) + PASS (real feature-based fallback)** | P02_07c/07d/07e mock; P02_07 real |
| 8 | Permissions, secrets, privacy, non-idempotent writes | **PASS** | P02_08, 08b, 08c, 08d, 07e |
| 9 | Cyan cursor still usable | **PASS (mock geometry)** + existing pointer/cursor suites in full run | P02_09/09b/09c, `test_jarvis_pointer.py`, `test_independent_cursor.py`; no live on-screen tap performed |
| 10 | Latency and step count vs Phase 1 | **MEASURED** | [measurements.md](measurements.md); GUI path step count is an authored plan (NOT RUN live) |
| — | Unreal editor Python on a project | **BLOCKED** | no disposable project; see findings U1 |
| — | VS Code `open` live | **NOT RUN** | would open a window in the user's session |
| — | Real macro-enabled Office file | **BLOCKED** | requires changing the user's VBA trust setting (U3) |
