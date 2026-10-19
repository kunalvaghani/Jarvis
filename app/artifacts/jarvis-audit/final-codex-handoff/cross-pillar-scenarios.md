# Stage 4 — Cross-pillar end-to-end scenarios

REAL = actual Jarvis code with real local dependencies; SIMULATED = a labelled stand-in for an unavailable
service; RECORDED = a real run on this machine captured earlier, re-checked against its evidence file.

| # | Scenario | How it was exercised | Kind | Status |
| --- | --- | --- | --- | --- |
| 1 | Discover an unknown but permitted capability | `execution_strategy.plan` discovers methods for `budget.xlsx` write (flow A) | REAL | PASS |
| 2 | Choose API over an inferior GUI workflow | selected `xlsx.openpyxl`, API tier ranked first, GUI last (flow A); `Brain.validate_remaining` API-first rejection (Phase 2) | REAL | PASS |
| 3 | Perform the task and verify independently | `office_xlsx` write + readback through ToolRegistry (flow A uses Phase 3 `captured`) | REAL | PASS |
| 4 | Capture as a provisional skill | CAPTURED skill, trust `provisional`, provenance with removed failed step | REAL | PASS |
| 5 | App UI changes; degradation detected | renamed-sheet failures recorded → `degraded()` true | REAL store / synthetic failure events | PASS |
| 6 | FIX proposed and verified | FIX text by a MOCK author callable; validation on the renamed workbook is real | REAL validation / MOCK author | PASS |
| 7 | ReasoningBank records success and earlier failure | `bank.learn` on verified success and failed trajectories | REAL | PASS |
| 8 | OpenViking indexes and retrieves | Phase 4 real-server tests and the real-vault run (search p50 127 ms) | RECORDED (2026-10-18) + in regression when the server can start | PASS (recorded) |
| 9 | Repeated failures → bounded local diagnosis | `FailureRouter`: show_me_once once, then stop_request_guidance (flow A) | REAL | PASS |
| 10 | Eligible abstract problem → optional authorized cloud consultation | `cloud_architect_consult` through ToolRegistry: privacy gate, approval card with exact payload, consent, once per problem, untrusted advice | REAL path, SIMULATED provider | PASS (live Groq BLOCKED) |
| 11 | Demonstrated UI action → replayable verified candidate skill | Phase 5 real hook + UIA capture + structured replay + `promote` | REAL (synthetic click) | PASS (physical click NOT RUN) |
| 12 | DGM planner mutation without touching production | lab snapshot of the real repository, `cand/<id>` with `critical_path_weight=1.0`; production file and branches unchanged (flow C) | REAL | PASS |
| 13 | EEVEE-inspired evaluation detects cross-domain regression | sealed gate rejects a candidate that improves its target but regresses `latency_guard` (flow C) | REAL gate on a fixture repository | PASS |
| 14 | AZR generates and validates a reasoning problem | abduction task + oracle (flow D) | REAL | PASS |
| 15 | Candidate LoRA evaluated against baseline | Phase 7 sealed model gate report (merged: 9/165 vs 0/165, CI > 0) | RECORDED on the RTX 3050 | PASS (recorded) |
| 16 | Survives cancellation, crash and restart | DAG executor crash point after an effect started → restore refuses to replay (flow E); trainer exact resume and preemption (Phase 7); autoresearch recovery (Phase 6) | REAL | PASS |
| 17 | Earlier voice/desktop/memory/coding still available | registry contains the earlier tools; deterministic intent/speech modules import; full regression | REAL | PASS |

Flows A, C, D and E plus the D8-1 tests are in [`tests/test_phase08_integration.py`](../../../tests/test_phase08_integration.py).
