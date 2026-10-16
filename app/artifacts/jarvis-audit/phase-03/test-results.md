# Phase 3 — Commands, results and classification

Run from `app/` on 2026-10-17 IST, `.venv/Scripts/python.exe` (Python 3.10.6), branch `claude`.

```powershell
# Preflight baseline (before Phase 3 changes)
.venv/Scripts/python.exe -m pytest tests/test_skill_memory.py tests/test_skill_selection_audit.py tests/test_capabilities.py tests/test_hermes_skills.py tests/test_custom_skills.py tests/test_repository_skills.py tests/test_repository_skill_isolation.py tests/test_repo_abilities.py tests/test_self_evolution.py tests/test_self_evolution_audit.py tests/test_experience_memory.py tests/test_deerflow.py tests/test_tools.py tests/test_tool_registry_audit.py tests/test_phase01_baseline.py tests/test_phase02_execution_strategy.py tests/test_ability_forge_audit.py -q
.venv/Scripts/python.exe scripts/verification/phase_baseline.py --label phase03-before --out artifacts/jarvis-audit/phase-03/metrics-before.json
# Isolated MCP runtime (network only during this build)
.venv/Scripts/python.exe scripts/setup/setup_mcp_runtime.py artifacts/jarvis-audit/phase-03/mcp-runtime-image.json
# Phase 3 tests and measurements
.venv/Scripts/python.exe -m pytest tests/test_phase03_living_skills.py -q
.venv/Scripts/python.exe scripts/verification/phase03_living_benchmark.py --out artifacts/jarvis-audit/phase-03/living-benchmark.json
# Regression
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe -m pytest tests -q --junitxml=artifacts/jarvis-audit/phase-03/full-regression.xml
.venv/Scripts/python.exe scripts/verification/phase_baseline.py --label phase03-after --out artifacts/jarvis-audit/phase-03/metrics-after.json
```

| Check | Result |
| --- | --- |
| Pre-upgrade skill suites | 374 passed / 5 skipped |
| `tests/test_phase03_living_skills.py` | 36 passed (real SQLite, ToolRegistry, openpyxl adapters, Blender 4.4.3, Docker + MCP SDK 2.3.0; fixture authors labelled MOCK) |
| Full regression | **3,257 passed / 147 skipped / 0 failed**, 759 s ([log](full-regression.log), [xml](full-regression.xml)) |
| Launcher `--check` | **ready** ([json](launcher-check.json)) |
| Leftover generated MCP containers after the full run | 0 ([containers-after-regression.txt](containers-after-regression.txt)) |

## Classification against the Phase 3 brief (Step 7)

| Requirement | Status | Evidence |
| --- | --- | --- |
| Skill discovery across existing roots | PASS | P03_identity (bundled, personal vault, evolved), P03_missing_metadata (custom, non-skill folders) |
| Missing or corrupt metadata | PASS | P03_missing_metadata, P03_invalid_sidecar, P03_corrupt_store |
| Duplicate and conflicting skills | PASS | duplicate refused across roots; P03_capture_refuses_workflows_an_existing_skill_already_covers |
| Correct selection and telemetry | PASS | P03_selection_and_outcomes (3× finish → counted once), P03_failure_cause_and_fallback, P03_ranking |
| CAPTURED mutation | PASS (real adapters; MOCK-free default template) | P03_captured_keeps_only_verified_steps, P03_capture_refuses_unverified |
| FIX mutation | PASS (real validation; MOCK author) | P03_fix_repairs…_and_rolls_back, P03_failed_or_oversized_fix, P03_fix_for_bundled_guides_is_only_a_proposal |
| DERIVED mutation | PASS (real Blender 4.4.3 validation) | P03_derived_specializes_with_observed_application_version (5.0 precondition rejected) |
| Rollback after failed evolution | PASS | FIX rollback to v1; rejected FIX keeps previous body; candidate removed if it fails to load |
| MCP generation in restricted environments | PASS (real Docker) | P03_mcp_workflows, P03_generated_server_container_has_no_network_or_host_files |
| Malformed or malicious generated code | PASS | 6 AST cases + mechanism/test-vector validation |
| Registration / unregistration | PASS (real) | registration after approval, end-to-end `mcp_call`, tamper → unhealthy → unregistered |
| Compatibility with Phases 1 and 2 | PASS | Phase 1/2 suites inside the full run |
| Preservation of existing tools and skills | PASS | 116 registry tools unchanged; bundled skills load with stable IDs; full regression |
| ≥ 3 distinct MCP/skill workflows with disposable examples | PASS | (1) CAPTURED ledger workflow, (2) FIX after sheet rename, (3) DERIVED Blender 4.4, (4) MCP sha256, (5) MCP Celsius→Fahrenheit |
| Live local-model authoring of skills/MCP specs | NOT RUN | limitation L1 |
