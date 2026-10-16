# Retained changes — Prompt 29

UUID session IDs remove same-second collisions. Session-scoped exclusive lock files prevent cross-process overlap and retain crash evidence; a process RLock serializes local operations. Append-only, fsync-backed ledger updates preserve notes without rereading/copying the entire ledger. Ledger append is bounded but not a transactional journal: a disk failure can leave a partial untrusted note.

Configuration now rejects malformed objects, empty/invalid allowlists, nonfinite/bool/invalid timeouts and input limits. Configured timeout range stays 10–3600 seconds; max_input_mb is explicitly 1–200. JSON tool input is bounded before parsing. Session checkpoints have typed identity/state/count validation and a 64 KiB limit. Target/session/evidence/ledger/program ancestors reject symlinks and Windows reparse points. UTF-8 surrogate text is rejected before writes.

Analysis rechecks cancellation, paths and program size/mtime after approval. It atomically persists attempt_id/attempted before launching; errors/cancellation set uncertainty, with generic TaskState uncertainty for caught failures. Successful evidence and ledger are saved before marking completed. Attempted/uncertain/crash-lock sessions refuse a new execution. A hard crash before the catch remains protected by the durable attempt and lock. No cache bypasses a fresh approval or reuses stale analysis.

Node stdout uses a temporary file with periodic size checks and a 200,000-byte accepted readback cap; this is not a hard disk quota between checks. JSON must be a nonempty finite object. Nonzero, offline, malformed, oversized, cancellation and worker-disconnect fixtures never claim success. Windows OwnedJob closes only the tested owned process tree. NODE_PATH is no longer inherited; other user-profile paths remain for existing dependencies and do not provide privacy confinement. A separate actual owned Node fixture read back null for fake GROQ_API_KEY, OPENAI_API_KEY, NODE_PATH and NODE_OPTIONS and REA_DISABLE_TELEMETRY=1. This proves environment filtering, not that third-party REA honors the telemetry flag or lacks network/profile access. Outputs explicitly state untrusted and behavior unverified. Tool names and natural-language routing remain stable.


Keep append optimization with bounded, serialized durable writes: One synthetic 1 MB ledger append: warm p50/p95 15.66780/18.52820 → 7.62825/9.49900 ms; peak temporary Python allocation 13011648 → 12004 bytes. Identical prefix and note readback are asserted for every sample. Security checks/fences are included in the after timing; no analysis cache is introduced because deterministic target freshness is unproven. Five initial and 20 warm samples per version, not cold analyzer processes. No rejected runtime optimization was retained.

- `docs/rea-reverse-engineer-clone.md`
- `jarvis/rea_tools.py`
- `README.md`
- `../README.md`
- `scripts/verification/audit_catalog.py`
- `tests/test_audit_result_accounting.py`
- `tests/test_reverse_engineering_audit.py`
- `scripts/verification/verify_reverse_engineering_audit.py`
- `scripts/verification/report_reverse_engineering_audit.py`
- `scripts/verification/verify_reverse_engineering_artifacts.py`

Generated module/global artifacts are listed in generated-files.json. Existing dirty work was preserved; no commit/reset or deployment occurred.
