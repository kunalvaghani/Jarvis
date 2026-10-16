# Scoped rollback / resume

Preserve inherited user/module21–22 work; no audit commit/reset. Compare current hashes/source.patch before restoring only this module from ignored .jarvis-runtime/jarvis-audit/module23-pre. Names replace / with __; root-README.md is the parent overview. Do not erase the checkout, token, mailbox, pending journal or later user edits.

Do not downgrade a live uncertain journal without inspection: older code can mishandle damaged markers and stale approval. Retain journal/actual IDs, inspect the mailbox under separately approved live access, then start a new reviewed request. Never remove pending files merely to retry. Source-bound Gmail remains unavailable until reviewed adapter verification; rollback does not automatically reauthorize/reverify it. No real mailbox/token/credential changes need rollback from this audit.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_gmail_audit.py (immutable original preimage A/B).
2. -m pytest tests/test_gmail_audit.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/23-gmail/focused-main-final.xml
3. -m pytest scripts/verification/test_gmail_audit.py -q --junitxml=artifacts/jarvis-audit/modules/23-gmail/catalog-supplements.xml
4. Neighbors: test_gmail_api.py, test_gmail_actions.py, test_gmail_writes.py, test_gmail_workflows.py, test_gmail_commands.py, test_gmail_drafts.py, test_documents.py. Fakes/owned DOM only, never run the historical *_live.py scripts for this audit.
5. Freeze jarvis/*.py and tests/test_*.py SHA256 then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/23-gmail/full-regression.xml. No runtime/test edits during accepted run.
6. -m jarvis.launcher --check read-only; publish redacted summary only. Run report_gmail_audit.py, verify_gmail_artifacts.py and git diff --check.

Current BLOCKED JRV-23-010/012/018/021/025/026/027/032. Next NOT RUN JRV-24-001; earliest older unresolved JRV-04-001. Exact remaining IDs in artifacts/jarvis-audit/remaining-case-ids.txt. Live OAuth/profile/account writes and source activation require separate explicit action approval; do not infer it from passing fixtures.
