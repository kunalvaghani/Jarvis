# Executed commands

From app/, .venv/Scripts/python.exe:
- `-m pytest tests/test_media_player.py tests/test_spotify.py tests/test_media_routes.py tests/test_media_process_ownership.py -q --junitxml=artifacts/jarvis-audit/modules/25-media/baseline.xml`
- `-m pytest tests/test_media_audit.py -q --junitxml=artifacts/jarvis-audit/modules/25-media/reproduction.xml`
- Neighbor subsets in neighbors.xml and neighbors-final.xml add tests/test_whatsapp.py and tests/test_whatsapp_audit.py to media/routes/Spotify assertions.
- `-m pytest tests/test_island_desk.py tests/test_media_audit.py -q --junitxml=artifacts/jarvis-audit/modules/25-media/island-neighbors.xml` after correcting two synthetic source IDs.
- `-m pytest tests/test_media_audit.py tests/test_media_player.py tests/test_spotify.py tests/test_media_routes.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/25-media/cases-and-contracts.xml`
- `scripts/verification/verify_media_audit.py` (before and after ASCII fix)
- Freeze388 jarvis/*.py and tests/test_*.py SHA256 using verify_whatsapp_audit.freeze with OUT set to modules/25-media.
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/25-media/full-regression.xml` (full-regression.log)
- `-m jarvis.launcher --check` (readiness.json)
- `scripts/verification/report_media_audit.py`; `scripts/verification/verify_media_artifacts.py`
Fixture commands ran outside sandbox for Windows COM/owned-child/atomic/loopback constraints. Only this audit's exact owned pytest commands were stopped during incomplete runs. No live audio/OS/account mutations used.
