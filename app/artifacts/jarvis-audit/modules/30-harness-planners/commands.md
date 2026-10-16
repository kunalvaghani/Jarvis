# Reproduce from app/ in PowerShell

Tests use synthetic files, mocked model responses and source-owned protocol workers. Ordinary Windows fixture permissions were used for atomic TaskState files and owned process tests; there are no real sends, installs or desktop actions.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_hermes.py tests/test_harness.py tests/test_model_selection.py tests/test_hermes_skills.py -q --junitxml=artifacts/jarvis-audit/modules/30-harness-planners/baseline.xml
.venv/Scripts/python.exe -m pytest tests/test_harness_planners_audit.py tests/test_hermes.py tests/test_harness.py tests/test_model_selection.py tests/test_hermes_skills.py tests/test_brain.py tests/test_conversation_context.py tests/test_inference_limits.py tests/test_agent_runtime.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/30-harness-planners/cases-and-contracts.xml
.venv/Scripts/python.exe scripts/verification/verify_harness_planners_audit.py
.venv/Scripts/python.exe -c "from pathlib import Path; import scripts.verification.verify_whatsapp_audit as v; v.OUT=Path('artifacts/jarvis-audit/modules/30-harness-planners'); v.freeze()"
.venv/Scripts/python.exe -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/30-harness-planners/full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe scripts/verification/report_harness_planners_audit.py
.venv/Scripts/python.exe scripts/verification/verify_harness_planners_artifacts.py
```

Capture corresponding stdout/stderr logs/readiness.json. Preserve historical baseline/reproduction artifacts when resuming; do not overwrite them as current proof. The benchmark requires the saved preimage; --baseline was run before the schema-copy upgrade. Each timing batch checks50 identical schema outputs. Initial samples are not cold SDK/model requests. Optional runtime metadata inspection used importlib.metadata, not model loading. Never interpret fixture PASS as live model/desktop accuracy.
