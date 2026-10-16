# Reproducible commands (PowerShell from app/)

These tests use isolated owned fixtures. Atomic checkpoints and owned process tests ran with approved ordinary Windows permissions because restricted-token temp-file replacement is not a valid simulation of the installed runtime. No third-party REA command runs.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_rea_tools.py tests/test_toolkits.py -q --junitxml=artifacts/jarvis-audit/modules/29-reverse-engineering/baseline.xml
.venv/Scripts/python.exe -m pytest tests/test_reverse_engineering_audit.py tests/test_rea_tools.py tests/test_toolkits.py tests/test_audit_result_accounting.py tests/test_task_state.py tests/test_task_recovery.py -q --junitxml=artifacts/jarvis-audit/modules/29-reverse-engineering/cases-and-contracts.xml
.venv/Scripts/python.exe scripts/verification/verify_reverse_engineering_audit.py
.venv/Scripts/python.exe scripts/verification/verify_reverse_engineering_audit.py --environment
.venv/Scripts/python.exe -c "from pathlib import Path; import scripts.verification.verify_whatsapp_audit as v; v.OUT=Path('artifacts/jarvis-audit/modules/29-reverse-engineering'); v.freeze()"
.venv/Scripts/python.exe -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/29-reverse-engineering/full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe scripts/verification/report_reverse_engineering_audit.py
.venv/Scripts/python.exe scripts/verification/verify_reverse_engineering_artifacts.py
```

Capture stdout/stderr to the corresponding report logs/readiness.json. Baseline and reproduction artifacts preserve historical pre-fix results; do not overwrite them when resuming. Benchmark needs the preserved preimage. Five initial iterations do not represent cold-process analyzer runs. No TTFT/audio applies to ledger writes; no full model/RSS/VRAM latency claim.
