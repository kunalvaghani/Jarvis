# Commands executed for the final verification (from `app/`, 2026-10-19)

```powershell
# Stage 1: re-audit
.venv\Scripts\python.exe -c "<import every jarvis module>"            # -> module-import-check.json (260/262; 2 by-design workers)
.venv\Scripts\python.exe scripts\verification\module_dependency_map.py --out artifacts\jarvis-audit\final-codex-handoff
.venv\Scripts\python.exe -c "import verify_architecture as v; v.inventory()"   # Prompt 01 inventory regenerated (120 entries);
                                                                       # previous copy: prompt01-source-inventory-before-phase08.json
# Stage 4/6/7: Phase 8 tests (cross-pillar flows, red team, D8-1, D8-5)
.venv\Scripts\python.exe -m pytest tests\test_phase08_integration.py -q
.venv\Scripts\python.exe -m pytest tests\test_documents.py tests\test_rag_documents_audit.py -q
.venv\Scripts\python.exe -m pytest tests\test_toolkits.py::ToolkitTests::test_all_toolkit_operations_dispatch_from_autonomous_plans tests\test_architecture_audit.py tests\test_capabilities.py tests\test_deliberation.py tests\test_deliberation_audit.py tests\test_brain.py tests\test_phase05_escalation_demonstration.py -q

# Stage 5: measurements
.venv\Scripts\python.exe scripts\verification\phase08_final_benchmarks.py --out artifacts\jarvis-audit\final-codex-handoff\benchmarks

# Final launcher check and full regression (skip reasons included with -rs)
.venv\Scripts\python.exe -m jarvis.launcher --check > artifacts\jarvis-audit\final-codex-handoff\launcher-check.json
.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider -rs --junitxml=artifacts\jarvis-audit\final-codex-handoff\full-regression.xml

# Manifests and diff against the pre-upgrade baseline 5b52737
git diff --stat 5b52737 HEAD -- <source dirs>        > changed-files-source.txt
git diff --name-status 5b52737 HEAD                  > changed-files-all.txt
git diff 5b52737 HEAD -- <source dirs> (no held-out/train data) > source-since-baseline.patch
git log 5b52737..HEAD                                 > commits.txt
.venv\Scripts\python.exe -m pip freeze                 > environment\pip-freeze-venv.txt   (and .venv-training, .venv-openviking)
```

Per-phase commands and logs are in each phase packet (`../phase-01` … `../phase-07`).
