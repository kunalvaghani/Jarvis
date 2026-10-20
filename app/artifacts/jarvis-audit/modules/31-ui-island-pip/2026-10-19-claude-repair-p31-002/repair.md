# P31-002 repair — one-time request receipts (Claude, 2026-10-19 IST)

Branch `claude`, base `ddf3247`. This responds to Codex's continuation audit (`codex-review` worktree, packet
`modules/31-ui-island-pip/2026-10-19-independent-ddf3247/`). That audit verified P31-001 fixed and found P31-002:
both final requesters accepted a replayed earlier receipt for a new request with identical text, because the receipt
digest covered only kind and detail. No Codex re-review of this repair exists yet. Prompt 31 stays BLOCKED until
Codex verifies it; Prompt 32 was not started.

## Repair (follows Codex's proposed contract)

| Contract item (Codex handoff) | Implementation |
| --- | --- |
| Unpredictable request id created before the card is enqueued and kept by the requester | `App.request_approval` and `AbilityForge.ask` call `new_request_id()` (128-bit `secrets`) and keep the id and an issue time in local variables; the id is also sent in the answer object |
| UI preserves the id | `Approval` reads `answer['request']` once at creation; later edits to the answer cannot re-target the card. Its digest covers kind, detail and request id |
| Accept only the exact still-pending request, once | `receipt_valid(answer, kind, detail, request, issued, cancelled)`: approved, digest equals the digest of the requester's *own* kind, detail and locally held id, within `APPROVAL_TTL` of the requester's own issue time, and not cancelled. Each requester waits for exactly one answer per request |
| Deny/lapse semantics preserved | Denied and lapsed cards write no digest; lapse still returns None for learned abilities |
| Same protocol for App and learned-ability cards | Both use `jarvis/approval_receipt.py`. The card uses the same `APPROVAL_TTL` |
| Existing approved-scope executor checks | Unchanged (learned-ability `_approval_digest`, evolution seals, adapter target checks) |

Files: [`jarvis/approval_receipt.py`](../../../../../jarvis/approval_receipt.py), [`jarvis/island_desk.py`](../../../../../jarvis/island_desk.py),
[`main.py`](../../../../../main.py), [`jarvis/repo_abilities.py`](../../../../../jarvis/repo_abilities.py),
[`tests/test_prompt31_receipt_replay.py`](../../../../../tests/test_prompt31_receipt_replay.py).

## Verification

| Check | Result |
| --- | --- |
| Codex's `test_receipt_replay.py`, **unmodified** ([log](codex-original-unmodified.log)) | 2 FAIL / 3 PASS. Both failures are the attack-setup line `assert card.digest == saved['digest']`, which held only in the vulnerable design. The digests now differ, so the replayed receipt can no longer match. |
| Same tests in `tests/test_prompt31_receipt_replay.py` with only that setup line changed to `!=` (documented in the file); every security assertion unchanged | 5 PASS: replayed receipt refused for App and learned-ability requests, the new card receives no decision, only the first simulated effect happens, cancelled request refused, expired card issues no receipt, old UI token refused for an identical-text card |
| Added tests: genuine repeated identical requests each need and accept their own decision; forged, missing, wrong, swapped-id and other-kind receipts (×2 requesters); delayed receipts past the requester's own lifetime, a clock moving backwards, cancellation, an empty id; the id read once at creation; deny/lapse write no receipt | 13 PASS |
| P31-001 tests (Codex's original 4 + Claude's 5) | 9 PASS |
| All approval tests ([log](approval-tests.log)) | 27 PASS |
| Full regression run 1 (15:05–15:22 IST, Jarvis running) | **3,420 passed / 1 failed / 147 skipped** — [log](full-regression-run1.log). The failure was `test_P06_gate_discards_nondeterministic_results`: random noise in the fixture's nondeterministic candidate happened to look like a significant gain, so a later check *rejected* it instead of *discarding* it (it was still refused). Unrelated to approvals, but a real flake in a Phase 6 test (D-P31-F1). |
| Gate repair for D-P31-F1 | `evolution_eval/gate.py`: a computed (non-`timing`) benchmark whose repeats disagree is discarded as nondeterministic *before* any improvement check. `policy.json` marks `dag_makespan` as `timing`. The test now also asserts the reason. Phase 6 file: 25/25 on three consecutive runs. This changes the evaluator seal, so any earlier evolution proposal must be re-evaluated (the Phase 6 DAG proposal was already stale). |
| Full regression run 2 (after the gate repair, 15:32–15:50 IST) | **3,421 passed / 0 failed / 147 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |

## Not addressed (still open in Prompt 31)

- The receipt binds kind, displayed detail text and a one-time id. A host-owned canonical digest of every tool's
  executed arguments, plus skill version and generation, is still not a uniform part of `Actions._approve`. Where a
  caller's detail text omits arguments it will execute, binding is only as strong as that text. Existing executor
  scope checks remain the second line.
- An attacker with code execution inside the Jarvis process could read the id and forge a digest; that threat model
  is outside the UI/receipt seam (such code could call executors directly).
- Baseline instability (transient Tcl/Tk start-up error), launcher `repair_required` in Codex's sandbox, the isolated
  utility-runtime path, and secure-field, DPI, microphone, training, UI-crash and verified-terminal acceptance remain
  BLOCKED or NOT RUN.
