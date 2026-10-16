# Commands and scope

From app/, using .venv/Scripts/python.exe:

- `-m pytest tests/test_gods_eye.py tests/test_gods_eye_view.py tests/test_gods_eye_cameras.py -q --junitxml=artifacts/jarvis-audit/modules/27-gods-eye/baseline.xml`
- `-m pytest tests/test_gods_eye_audit.py -q --junitxml=artifacts/jarvis-audit/modules/27-gods-eye/reproduced.xml`
- Repair runs in targeted-first.xml and targeted-second.xml.
- `-m pytest tests/test_gods_eye_audit.py tests/test_gods_eye.py tests/test_gods_eye_view.py tests/test_gods_eye_cameras.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/27-gods-eye/cases-and-contracts.xml`
- `scripts/verification/verify_gods_eye_audit.py` (paired before/after 25 iterations each; no full suite competing).
- Freeze 391 runtime/test files with verify_whatsapp_audit.freeze, OUT set to modules/27-gods-eye.
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/27-gods-eye/full-regression.xml` (full-regression.log).
- `-m jarvis.launcher --check` (readiness.json).
- `scripts/verification/report_gods_eye_audit.py`; `scripts/verification/verify_gods_eye_artifacts.py`.

From integrations/gods-eye-view-src/gods-eye-view-main: `node --test src/data/aircraftNearbyPolicy.test.mjs src/cctvFocusPolicy.test.mjs src/cctvFocusRequest.test.mjs`, output frontend-unit.log. Pure fixtures/source reads, no WebGL/GUI journey. The interrupted earlier full run is excluded. Outside-sandbox fixture runs allowed temporary atomic journal replacement, an owned child crash and existing isolated process/browser tests; no live notification or feed.
