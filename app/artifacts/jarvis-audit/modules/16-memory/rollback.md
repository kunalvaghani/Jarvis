# Rollback and resume

No audit commit. Preserve inherited dirty branch audit/12-tool-registry. Scoped preimages in ignored .jarvis-runtime/jarvis-audit/module16-pre (app relative paths use __; root README named root-README.md). Compare source-hashes.json with current files and review source.patch before manually restoring only these changes; never git reset/restore all changes. No production memory data altered, no schema migration/dependency rollback. Keep any later user edits; do not delete personal files or overwrite real vaults from fixtures.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_memory_audit.py uses the preserved preimage, never regenerate a baseline from upgraded source.
2. scripts/verification/verify_memory_journey.py uses temporary vault/SQLite and forbids network, authored local response.
3. -m pytest tests/test_memory_audit.py tests/test_memory_weather.py tests/test_obsidian_memory.py tests/test_memory_index.py tests/test_skill_memory.py tests/test_experience_memory.py tests/test_experience.py tests/test_knowledge.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/16-memory/cases-and-contracts.xml
4. -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/16-memory/full-regression.xml (capture matching source hashes before run).
5. -m jarvis.launcher --check; preserve raw output locally, publish only redacted readiness status.
6. scripts/verification/report_memory_audit.py after source-freeze validation and saved readiness JSON.

No account write, erase of user data, credentials, package/interpreter/model install, service start or external action is authorized by this verification. For blockers design/verify scoped erase, durable outbox, document provenance/freshness and correlated lifecycle contracts in fixtures before any real-vault migration/erase. All exact remaining IDs in remaining-case-ids.txt. Next NOT RUN JRV-17-001; earliest older unresolved JRV-04-001.
