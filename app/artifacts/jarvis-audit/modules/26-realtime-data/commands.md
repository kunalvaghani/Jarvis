# Executed commands

From app/, .venv/Scripts/python.exe:
- `-m pytest tests/test_realtime.py tests/test_memory_weather.py -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/baseline.xml`
- `-m pytest tests/test_realtime_audit.py -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/reproduction.xml`
- Combined realtime/weather subsets in neighbors.xml and neighbors-iteration2.xml.
- `-m pytest tests/test_realtime_audit.py tests/test_realtime.py tests/test_memory_weather.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/cases-and-contracts.xml` (preserved main in focused-main-final.xml)
- `-m pytest scripts/verification/test_realtime_audit.py -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/catalog-supplements.xml`
- `scripts/verification/verify_realtime_data_audit.py`
- Freeze390 runtime/tests SHA256 using verify_whatsapp_audit.freeze with OUT set to modules/26-realtime-data.
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/full-regression.xml` (full-regression.log)
- `-m jarvis.launcher --check` (readiness.json)
- `scripts/verification/report_realtime_data_audit.py`; `scripts/verification/verify_realtime_data_artifacts.py`
Outside-sandbox fixture execution supports temporary atomic files, owned child crash and existing isolated process/browser checks; no live feeds, geolocation, speech or notifications. Supplement is independent, not part of full tests-directory count.
