# Rollback and next work

Private preimages `.jarvis-runtime/jarvis-audit/module01-pre/{launcher.py,agent_events.py,main.py,runtime_manifest.json,README.md}` preserve this module's start state, including earlier dirty changes. Stop the owned Jarvis app intentionally before rollback. Copy only those selected files back to matching app paths after preserving any newer edits. Use `source.patch` to review the change. Do not git reset/clean, restore the entire earlier audit snapshot or delete user files. The new config_contract module is harmless when both entrypoints stop importing it; no removal is required. No schema/data/config-value migration occurred.

The targeted Buddy fixture preimage is `module01-pre/test_buddy.py`; restore it only to revert the test-isolation repair. It includes the prior audit's fixed calendar fixture and must not be replaced with HEAD, which would lose earlier work.

For newer large/deep config, rollback relaxes validation and metadata privacy; retain the hardening unless diagnosing a confirmed incompatibility. Unknown fields currently warn rather than broaden permissions. Test-only scripts can remain for evidence. Reconcile the catalog after rerunning assertions; a failed parameter cannot be masked by another passing parameter.

Run from app: `.venv/Scripts/python.exe -m pytest tests/test_architecture_audit.py tests/test_agent_runtime.py tests/test_tools.py -q`; full `-m pytest tests -q`; `-m jarvis.launcher --check`. `-m scripts.verification.verify_architecture --inventory --dependencies` is read-only. Benchmark commands refuse overwriting initial phase files; preserve them before a repeat. Paired profiling uses captured trusted code, no checkout mutations.

All32 module01 catalog IDs now have owned-fixture proof. Next incomplete catalog ID is recorded in the top-level summary/remaining-case-ids.txt; continue module02 next. Security module19/35 host isolation and module34 interpreter migration remain release blockers and must not be bypassed by claiming inventory counts are capabilities.
