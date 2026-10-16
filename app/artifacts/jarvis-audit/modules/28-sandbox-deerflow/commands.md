# Commands and evidence

From app/, .venv/Scripts/python.exe:

- `-m pytest tests/test_docker_sandbox.py tests/test_deerflow.py -q --junitxml=artifacts/jarvis-audit/modules/28-sandbox-deerflow/baseline.xml`
- `-m pytest tests/test_sandbox_deerflow_audit.py -q --junitxml=artifacts/jarvis-audit/modules/28-sandbox-deerflow/reproduced.xml` (approved fixture permission after restricted-token attempt).
- Repair subsets: targeted-first.xml and targeted-second.xml.
- `-m pytest tests/test_sandbox_deerflow_audit.py tests/test_docker_sandbox.py tests/test_deerflow.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/28-sandbox-deerflow/cases-and-contracts.xml`
- `scripts/verification/verify_sandbox_deerflow_audit.py` — paired inventory A/B, no Docker/model workload.
- `scripts/verification/verify_sandbox_deerflow_container.py` — three explicitly owned, installed-image offline synthetic jobs, inspected cleanup; no engine startup, pull/build, account or personal input.
- `scripts/verification/verify_sandbox_deerflow_renderers.py` — six remaining installed offline recipes, sequential synthetic fixtures and inspected cleanup; stock narration CPU only, no audible playback.
- Freeze 392 runtime/test hashes using verify_whatsapp_audit.freeze with OUT set to modules/28-sandbox-deerflow.
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/28-sandbox-deerflow/full-regression.xml` (full-regression.log).
- `-m jarvis.launcher --check` (readiness.json).
- `scripts/verification/report_sandbox_deerflow_audit.py`; `scripts/verification/verify_sandbox_deerflow_artifacts.py`.

Read-only engine/image inspection and optional Python package metadata are recorded separately. Full tests-directory execution uses isolated fixtures; it does not rerun the real-container script. No blanket live research/GPU/media/production acceptance.
