# Scoped rollback and resume

No audit commit. Preserve inherited dirty checkout. Compare source.patch, files-changed.json and current SHA256 before restoring only Prompt21 changes from ignored .jarvis-runtime/jarvis-audit/module21-pre. App-relative preimage names replace / with __; parent README is root-README.md. Do not reset the checkout, erase user edits or restore unchanged copied test_native_coding.py over later work.

Do not downgrade live uncertain save/promotion state: old code can replay a partial promotion. Retain journals/worktrees/backups, inspect fresh destination and ask for a new reviewed run; never erase a journal to force a retry. No actual personal project promotion occurred in this audit. Per-file backup restore requires checking later edits and explicit approval where applicable.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_native_coding_audit.py (immutable original-preimage A/B; do not overwrite preimages).
2. -m pytest tests/test_native_coding_audit.py -q --junitxml=artifacts/jarvis-audit/modules/21-native-coding/cases-and-contracts.xml
3. Optional neighbors: -m pytest tests/test_native_coding.py tests/test_coding_workflow.py tests/test_codex_workload.py tests/test_codex_validation.py tests/test_audit_result_accounting.py -q (use a distinct XML output).
4. Freeze jarvis/*.py and tests/test_*.py SHA256; -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/21-native-coding/full-regression.xml. No runtime/test edits during accepted run. Windows owned atomic replacements require the execution permissions used here.
5. -m jarvis.launcher --check (read-only); retain private raw output and publish redacted summary only. No automatic repairs.
6. scripts/verification/report_native_coding_audit.py then scripts/verification/verify_native_coding_artifacts.py; git diff --check.

Current incomplete IDs JRV-21-003/009/010/019/032. Next NOT RUN JRV-22-001; earliest older unresolved JRV-04-001. Exact remaining IDs in artifacts/jarvis-audit/remaining-case-ids.txt. Required contracts need bounded implementation/security proof before live model/GUI acceptance; do not treat mock passes as production approval.
