# Changes and keep/revert

Normalization batch1000 warm p50/p95 7.43305/8.42900 → 6.92490/7.84160ms; Python peak 238042→238042B, outputs identical. Precompiled whitespace expression retained: small measured safe win. Five initial samples/version are not cold process trials. No TTFT/audio/RSS/VRAM or live send speed claim. Safety reads, locks and atomic checkpoints add work and may increase actual UI latency; no comparable end-to-end latency baseline. Fail-closed name collisions can refuse the same person listed under both Chats and Contacts. Uncertain checkpoint may precede any actual typing; conservative false blocks require inspection. Journal trusted local filesystem, no power-loss fsync/hostile-user sandbox guarantee, account/phone IDs absent. Final UI read and Enter are not an atomic transaction. File sends/call clicks are outside the new durable text guard.

- `docs/system-map.md`
- `docs/whatsapp.md`
- `jarvis/actions.py`
- `jarvis/whatsapp.py`
- `README.md`
- `../README.md`
- `scripts/verification/audit_catalog.py`
- `tests/test_audit_result_accounting.py`
- `tests/test_whatsapp.py`
- `jarvis/whatsapp_writes.py`
- `tests/test_whatsapp_audit.py`
- `scripts/verification/test_whatsapp_audit.py`
- `scripts/verification/verify_whatsapp_audit.py`
- `scripts/verification/report_whatsapp_audit.py`
- `scripts/verification/verify_whatsapp_artifacts.py`

Generated audit artifacts, including reconciled global ledgers and the preserved prior report, are enumerated in generated-files.json. Source.patch is relative to module24 preimages, not repository HEAD; it preserves inherited user changes.
