# Scoped rollback and deterministic resume

No commit/reset, personal deployment or install. Preserve inherited Prompt21/user edits. Compare current hashes and source.patch before restoring only this module from ignored .jarvis-runtime/jarvis-audit/module22-pre. Preimages use /→__ and root-README.md for the parent. Do not erase the checkout or overwrite later edits. Restoring old browser code reopens token URL/malformed plan/service-worker/WebSocket gaps; keep untrusted previews stopped pending review. No live server was left running by these tests.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_web_development_audit.py (immutable original preimage benchmark; never regenerate it from changed code).
2. -m pytest tests/test_web_development_audit.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/22-web-development/cases-and-contracts.xml
3. Neighbor tests: -m pytest tests/test_development.py tests/test_development_tools.py tests/test_development_api.py tests/test_development_projects.py tests/test_development_learning.py tests/test_development_design.py tests/test_development_knowledge.py -q (distinct output).
4. Freeze jarvis/*.py and tests/test_*.py SHA256, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/22-web-development/full-regression.xml. Do not edit runtime/tests during accepted run.
5. -m jarvis.launcher --check read-only; raw local output remains ignored, publish redacted summary. Run report_web_development_audit.py and verify_web_development_artifacts.py; git diff --check.

Fixture prerequisites: installed Chrome/Playwright, existing trusted artifacts/projects/development-dashboard with its pinned tsc/Vite/axe tree. Do not install automatically if absent; record concrete blockers instead. Full test builds only that authored fixture output and starts/stops owned temporary loopback servers. The mocked remote API makes no external request. Do not replay failed project/server/build code automatically; inspect state and request explicit continuation.

Missing current IDs JRV-22-002/004/008/010/011/018/019/021/023/025/026/027/030/032. Next NOT RUN JRV-23-001; earliest older unresolved JRV-04-001. All exact pending IDs remain in artifacts/jarvis-audit/remaining-case-ids.txt. HMR, host confinement, upgrades, crash continuation and diagnostic redaction need separate scoped contracts, not a production certificate from fixture success.
