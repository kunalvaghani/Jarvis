# Review and rollback

Proposals are uncommitted on codex-review, base pinned in review-revisions.json. Review source.patch and the separately hashed new test source. Apply accepted changes on claude; obtain the resulting SHA and rerun before release. Do not merge automatically.

To roll back P37, manually reverse only actions.py/demonstration.py hunks in source.patch after checking current hashes; preserve P34/P35/P36 edits and user changes. No global reset/clean, package uninstall, journal deletion or uncertain-write replay. Persisted terminal demonstration status and uncertain task records remain evidence; reopening does not grant fresh recording consent or write permission. Re-run relevant suites and launcher check after any rollback. Actual version rollback workflow was not run.
