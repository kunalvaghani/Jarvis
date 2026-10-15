# Scoped retained changes

- dag_execution.py: bounded JSON before encoding, safe malformed reference types, exact read-restore binding, per-graph write serialization, categorical errors and run UUIDs.
- hierarchical.py: current task-bound authorization/checkpointing, invalid template revalidation/fallback, bounded corrupt-cache miss, recognized credential-template exclusion; bounded source digest reuse with file identity/change invalidation, additional state/privacy sources and model labels in fingerprint; unknown configuration keys rejected.
- task_state.py: optional keyword-only task_id guard for update_dag under its existing lock. Existing callers/tool names remain valid; the production DAG supplies the guard.
- tests/test_dag_planning_audit.py:32 mapped catalog cases and11 supplemental assertions, including changed-upstream restore propagation, using fake transports/isolated state. Existing real-file/cache/repair/summary regression reused. Accounting authorizes this reviewed dedicated catalog class.
- Manifest, README overview and linked guides updated with dated fixture/measurement limits. No dependency/service/config/model install, UI layout/screenshot change, real account action or new public mail capability. No commit; prior dirty work preserved.

See [exact files](files-changed.json),[before/after hashes](source-hashes.json),[scoped patch](source.patch). Keep source digest reuse for reduced repeated I/O/allocation; cold fingerprint overhead is explicit, not hidden behind a universal speedup claim.
