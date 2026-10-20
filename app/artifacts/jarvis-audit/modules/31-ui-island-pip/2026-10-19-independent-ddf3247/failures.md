# Prompt 31 independent continuation — 2026-10-19 IST

**P31-001: FIXED for the original callback/queue-head defect.** The unchanged original four tests pass; all nine repair tests pass (13 executions, including four duplicate scenarios). Source fix is 1dd3e9c. No claim that these establish the entire approval protocol.

**P31-002: FAIL — final requester does not bind a receipt to a unique pending request. Priority P1 for the mandated authorization acceptance gate; external exploitability UNVERIFIED.** A legitimate approved card A and a later card B have equal kind/detail and equal text digest, but different random tokens. Fault injection delivers A's saved answer into B's response. Both App.request_approval and AbilityForge.ask return True although B.done is False and no decision was made on B. UI rejects A's token when directly used against B; the requester omits that comparison. Two independent parameterized requester cases fail; three cancellation/expiration/UI-identity controls pass. [Fixture](test_receipt_replay.py), [actual failures](receipt-replay.txt), [XML](receipt-replay.xml). No real account/file/shell side effect occurred; optional simulated effect is a local list only.

This is a protocol/fault-injection finding, not proof an attacker can write the in-process response object. Do not claim remote exploitation. It falsifies the requested stale/forged-response rejection at the final acceptance seam and shows text identity alone cannot establish unique request identity.

**Environment failure:** relevant regression 303 PASS / 1 FAIL / 8 SKIPPED. Phase 8 flow A selected no xlsx API because the isolated checkout lacks .venv-skills. With already-installed interpreter paths routed read-only, the same full flow passes (1 PASS); audited source remains in this checkout. No installation or source weakening. Baseline and retest stay distinct. Prior Tcl/UIA instability was not reproduced in this combined run; that does not establish indefinite stability.

Full argument/identity/version/expiry receipts, a verified terminal UI event and physical secure-field/DPI/microphone/process-crash acceptance remain BLOCKED. Stop at Prompt 31; Prompt 32 not started.
