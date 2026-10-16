# Scoped rollback and deterministic resume

No audit commit. Retained inherited dirty audit/12-tool-registry branch, never reset/restore all. Saved preimages: .jarvis-runtime/jarvis-audit/module17-pre/ (app paths use __; root README is root-README.md). Review source.patch/source-hashes.json against current later edits before manually restoring only this module's changes. Do not regenerate old preimages or overwrite prior module/user changes. No production document/vault data modified, no dependency/schema migration rollback, no personal file deletion.

From app/ using existing .venv/Scripts/python.exe:
1. scripts/verification/verify_rag_documents_audit.py: exact immutable old-source versus current BM25 A/B.
2. scripts/verification/verify_rag_documents_journey.py: synthetic drop→command→readback→restart, network/account writes forbidden.
3. -m pytest tests/test_rag_documents_audit.py tests/test_documents.py tests/test_buddy.py tests/test_audit_result_accounting.py tests/test_phase2_gpu_models_voice_ui.py -q --junitxml=artifacts/jarvis-audit/modules/17-rag-documents/cases-and-contracts.xml
4. Freeze runtime/test hashes, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/17-rag-documents/full-regression.xml
5. -m jarvis.launcher --check (read-only), preserve private raw output locally; publish redacted readiness.json.
6. scripts/verification/report_rag_documents_audit.py; scripts/verification/verify_rag_documents_artifacts.py.

Next NOT RUN module/case JRV-18-001; earlier unresolved JRV-04-001. Exact remaining IDs in remaining-case-ids.txt. Prompt 17 blockers003/005/012/032 need designed conflict/semantic validation, hard parsing process resource guard and operation trace contract, then executable assertions. Separately review pypdf 6.20.1 installation/security regression under explicit dependency authorization; no installation/send/account-write/deploy is authorized by verification steps.
