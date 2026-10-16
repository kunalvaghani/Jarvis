# Scoped rollback and resume

Preimages are preserved in `.jarvis-runtime/jarvis-audit/module29-pre/` (paths relative to app, flattened with __; root-README.md is the parent README). Verify source-hashes.json before any restoration; if files changed since this audit, merge the specific source.patch hunks. Do not reset the dirty checkout, erase user work, delete sessions/evidence or run a bulk restore. New test/verification files are listed in files-changed.json; disable only their new audit registrations if intentionally reverting.

Retain session attempt/uncertainty records and .operation.lock after a crash. Inspect the exact program, target and evidence before any human-approved new session; a new session is not permission to replay an uncertain external action. Never automatically clear a stale lock or mark attempted effects completed. The append format is compatible with old ledgers; partial disk-failure notes are untrusted. No dependency/service or personal config was changed.

Resume at JRV-29-001 with an authorized owned interactive demo and current analyzer accuracy oracle, then the exact IDs in remaining-case-ids.txt. Follow commands.md and freeze runtime/tests before full validation. Incomplete privacy/schema/freshness/clone acceptance work requires implementation and reproof, not a status edit.
