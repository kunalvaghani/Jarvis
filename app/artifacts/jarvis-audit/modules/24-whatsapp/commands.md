From app/, using .venv/Scripts/python.exe:
- `-m pytest tests/test_whatsapp.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/baseline.xml`
- `-m pytest tests/test_whatsapp_audit.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/reproduction.xml`
- `-m pytest tests/test_whatsapp.py tests/test_whatsapp_audit.py tests/test_gmail_writes.py tests/test_documents.py tests/test_task_recovery.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/neighbors-final.xml`
- `-m pytest tests/test_whatsapp.py tests/test_whatsapp_audit.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/cases-and-contracts.xml` (main preserved in focused-final.xml)
- `-m pytest scripts/verification/test_whatsapp_audit.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/catalog-supplements.xml`
- `scripts/verification/verify_whatsapp_audit.py`; then `scripts/verification/verify_whatsapp_audit.py --freeze`
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/full-regression.xml` (full-regression.log)
- `-m jarvis.launcher --check` (readiness.json)
- `scripts/verification/report_whatsapp_audit.py`; `scripts/verification/verify_whatsapp_artifacts.py`
Journal/browser/loopback/owned-child fixtures required outside-sandbox execution after WinError5 in isolated temporary files. No live account or personal-window permissions were used.
