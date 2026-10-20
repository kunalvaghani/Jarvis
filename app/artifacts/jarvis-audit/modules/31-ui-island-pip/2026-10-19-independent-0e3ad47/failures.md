# Prompt 31 independent audit — 2026-10-19 IST

**P31-001 FIXED:** stale/unbound callback and voice isolation retain the original passing reproduction. Fix commit 1dd3e9c.

**P31-002 FIXED at the reviewed replay boundary:** source repair 0e3ad47 creates a pending request ID before enqueueing, digests it with text scope, and validates requester-owned issue time/TTL/cancellation. Independent replay now leaves the second card undecided and returns False for both App and learned abilities. The old test's equal-digest setup condition was changed to distinct request IDs/digests; all actual replay-rejection and side-effect assertions are unchanged. See test_receipt_replay.py and approval-reverification.xml. No new P0/P1 runtime defect is claimed by this packet.

Remaining acceptance gaps are BLOCKED, not presumed passing: canonical executor argument/identity/version/generation binding, verified terminal UI receipt, full concurrent restart lifecycle, scoped demonstration display/stop acceptance, native secure-field/DPI, microphone/F5/GPU contention and UI process crash. See remaining-work.md and tests.jsonl. Any actual test FAIL remains visible in XML/summary; zero failures must not be inferred from a planned count.
