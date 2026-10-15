# Scoped changes

- `jarvis/cognition.py`: bounded typed percept admission without arbitrary serialization, surrogate replacement, finite numeric/boolean configuration checks, stale-window invalidation and race filtering, tick/error/overrun/stall metadata, payload-free persistence errors, avoid copying the drained inbox, and distinguish unexecuted proposals from attempted failures using task-start readback.
- `tests/test_perception_cognition_audit.py`: owned scenario, fault, concurrency, security and lifecycle assertions; no live sends or OS mutations. Existing `tests/test_cognition_and_routing.py`: expect private-safe disk error type.
- `scripts/verification/verify_perception_cognition.py`, `report_perception_cognition.py`: paired measurements, assertion-derived evidence and rollback patch. `audit_catalog.py`: explicitly authorize this reviewed test module's case IDs; parameter failures still dominate passes.
- `config/runtime_manifest.json`, app/root README, docs index and cognitive guide: behavior, diagnostics, limitations and dated verification. All prior changes remain in place. No dependency changes.
- `docs/system-map.md` links diagnostic limits; `artifacts/jarvis-audit/security-findings.md` updates only the repaired proposal-learning boundary while retaining broader open risks. Catalog ledgers, summary, module map and final report regenerated from executed assertions; previous final report archived.

The heap candidate was reverted. Final performance differences are small; correctness fixes are retained without claiming a model, audio or universal latency improvement. Review [scoped runtime diff](source.patch) and [hashes](source-hashes.json).
