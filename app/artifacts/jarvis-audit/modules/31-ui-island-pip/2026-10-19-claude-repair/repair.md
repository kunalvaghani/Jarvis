# P31-001 repair — request-bound island approvals (Claude, 2026-10-19 IST)

Branch `claude`, base `5b56f84` (after the `codex-review` merge). This repair responds to Codex's independent Prompt 31
audit (`codex-review` worktree, packet `modules/31-ui-island-pip/2026-10-19-independent-5b56f84/`, verdict NOT READY /
BLOCKED). No Codex re-review of this repair exists yet; Prompt 32 was not started.

## Defect (confirmed by Codex, reproduced here)

`IslandDesk` bound the Approve/Deny buttons to `lambda: self.decide(True/False)` with no card identity, and
`IslandDesk.decide` popped whichever card was first in the queue. A stale callback, a callback for an expired or
removed card, or an unbound call could therefore approve a *different* queued request. The voice path
(`decision_handler`) had the same flaw, and requesters trusted a bare `answer["approved"]`.

## Repair (minimum safe change)

| Layer | Change |
| --- | --- |
| Card identity | `Approval` gets an immutable random `token` and a SHA-256 `digest` of its exact kind and detail ([`jarvis/approval_receipt.py`](../../../../../jarvis/approval_receipt.py)). An approved answer records both. |
| UI callbacks | `render_approval` rebinds Approve and Deny to the displayed card's token whenever the displayed card changes. `IslandDesk.decide(approved, token)` decides only when the token equals the displayed card's token. It removes that exact card object under a lock; unbound, stale, expired and superseded tokens decide nothing. The buttons are disabled for 600 ms after a new card appears, so a double click cannot land on it. |
| Voice | `App.voice_decision` captures the displayed card's token when the spoken answer is processed. If that card is gone before the UI thread applies it, nothing is decided. |
| Final boundary | `App.request_approval` (all `Actions._approve` callers) and `AbilityForge`'s learned-ability card return True only if the answer carries the digest of *their own* kind and detail. A bare `approved: True` or an approval issued for another request is refused. |

Files: [`jarvis/island_desk.py`](../../../../../jarvis/island_desk.py), [`jarvis/approval_receipt.py`](../../../../../jarvis/approval_receipt.py),
[`main.py`](../../../../../main.py), [`jarvis/repo_abilities.py`](../../../../../jarvis/repo_abilities.py),
[`tests/test_prompt31_approval_binding.py`](../../../../../tests/test_prompt31_approval_binding.py).

## Verification

| Check | Before (Codex, `5b56f84`) | After (this repair) |
| --- | --- | --- |
| Codex reproduction `test_approval_binding.py`, unchanged (stale callback, expired-card callback, unbound decision, positive control) | 3 FAIL / 1 PASS | 4 PASS |
| Added adversarial tests (deny bound to its card, token/digest identity, voice answer after card change, forged/other-request receipts, 16 concurrent stale clicks) | — | 5 PASS |
| Approval tests repeated 3 times | — | 9/9 each run |
| Neighbouring suites (island desk, island, deliberation audit, abilities, UI controls, toolkits, Phases 5/6/8) | — | 294 passed / 1 skipped |
| Ability approval suites | — | 86 passed |
| Full regression (14:21–14:41 IST, Jarvis running at the same time) | — | **3,402 passed / 1 failed / 147 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |
| The one failure: `test_island_desk.py::DeskWidgetTests::test_background_file_visible_in_every_view_and_code_draft_is_not_saved` | — | `tk.Tk()` raised `TclError: couldn't read file .../tcl8.6/auto.tcl` although the file exists; it fails before any approval code runs. The same transient Tcl/Tk lookup appears in Codex's baseline. Re-run in isolation: 5/5 desk widget tests pass, 3 times. Recorded as the open baseline-instability item, not hidden. |
| Approval tests after the full run | — | 9 passed ([log](approval-binding-after.log)) |

The reproduction is now part of the default suite as `tests/test_prompt31_approval_binding.py`. Codex's test functions
are copied unchanged; the five added tests follow below them.

## Scope and remaining gaps (not claimed as fixed)

- The receipt binds the **displayed request text** (kind and detail). Where a requester's detail text does not fully
  describe the arguments it will execute, the binding is only as strong as that text. Executors that already bind
  their own scope (learned abilities: `_approval_digest` over code, version and capabilities; evolution promotion:
  surface values and seal; adapters: exact target paths) keep those checks. A uniform host-owned argument digest for
  every tool, version binding and a verified UI terminal receipt are still open Prompt 31 acceptance items.
- Codex's other blockers are not addressed here: baseline instability triage (one transient Tcl/Tk lookup and one
  demonstration capture returning None), launcher `repair_required` for missing isolated runtimes in its sandbox,
  optional-worker integration, and real secure-field/DPI/cancellation/crash acceptance.
- Codex should independently re-run P31-001 and its adversarial final-executor tests before the stop gate is lifted.
