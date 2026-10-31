# ADR 0006: Upgrade v2 Phase 1 — continuation cache, compact reads, condition waits, app routes

Date: 2026-10-31. Status: accepted (Phase 1 of upgrade v2). Plan: [phase-1-plan.md](../rework/upgrade-v2/phase-1-plan.md). Every item is behind a flag that ships off, except the fixes marked **fix**.

## Context and measurements (2026-10-31, this PC)

- **The planner re-read every prompt in full.** Of 67 recorded 9B planner calls, 63 were fresh conversations, all at a constant ~440 prompt tokens/s: median 6,362 tokens, 14.4 s. Only 4 continued a conversation, at 1.0 s.
- **Experiment E1** used real `native_tools.plan()` payloads on qwen3.5:9b with 10 GPU layers and an 8,192 context:

  | Call | Prompt reading |
  |---|---|
  | Identical prompt | 0.24 s |
  | Same system prompt and tools, different ending | 10.7 s (no reuse) |
  | Same, with stable-first JSON order | 10.8 s (no help) |

- **Continuations, by contrast:**

  | Call | Prompt reading |
  |---|---|
  | Fresh 5.0k-token prompt | 11.4 s |
  | Continued conversation | 1.16 s |
  | Continued conversation after a different-prompt verify call on the same model | 1.15 s |

  Continuations failed only because they did not fit: a ~6.4k-token start, plus the update, plus a fixed 1,600-token reply reserve, is more than the scheduler's 8,192 context.

## Decisions

1. **`speed.cache_order` means continuation-first, not prompt reordering.** E1 showed that reordering gives the 9B nothing.
   - Mechanics: with the flag, the brain adds `cache_order` to planner requests, and the worker passes it to `native_tools.plan`.
   - The continuation check reserves the real reply budget (≥500 tokens) instead of 1,600.
   - Fresh prompts keep `CONTINUATION_ROOM` = 2,000 tokens free by trimming the existing `FIT_ORDER` parts sooner. The goal, screen, completed steps and route guidance are never trimmed.
   - A continued step's tool result is capped at 2,000 characters instead of 4,000.
   - With the flag off the payload is byte-identical (tested).
2. **`control.compact_reads`** (`control/compact.py`) drops nameless containers without state, and text or image lines that repeat their parent's name. Children move up one level; every named node and ref is kept.
   - Measured on full reads in headless Chrome: 18,941 → 12,685 characters (33%); the herokuapp tables page 44.6%; D1 pages 19–43%; no named node lost on any page.
   - The plan's ≥40% target is met on the real-world page only.
3. **`control.event_waits`** (`control/waits.py`, `until()`) turns the six fixed pauses into condition waits.
   - Polling loops get shorter intervals inside unchanged deadlines.
   - **Deviation from the plan's "never later" rule:** after typed text or keys, the read-back now waits for the window to *settle* (two equal reads), capped at 2 s.
   - Why: in live S2 (2026-10-31) the fixed 0.3 s read caught Calculator mid-calculation ("69104 Minus ( 7"). The planner pressed Equals again and Calculator repeated the subtraction (67,526 instead of 68,315).
   - The wait runs longer only while the app is still changing; an unchanged window costs about the old 0.3 s.
4. **`vision.tight_escalation`:** when the 2B found the target in the overview but a later check refused, the 4B grounds only the close-up around that box. The agreement check and label read-back are unchanged.
5. **`control.shared_save`:** `save_file` uses the existing UIA Save-As recipe (`ControlService._save_as`) through `control/save_dialog.py`. This applies only for a new file in a known app window, and that is decided before any key is sent. After the shortcut there is no fallback, per the never-replay rule. The recipe stayed in place rather than moving, to avoid churn.
6. **`control.api_routes`:**
   - **Blender, Excel, Word:** a verified document opens in the app the user named, by its exact path (`app_routes.py`). The planner's `open cylinder.blend` failed because the file catalog did not know the new file. Background Blender (`blender_task`) already existed.
   - **Small programs:** single-file, print-only requests skip the multi-file coder (`small_program.py`). Its model hand-typed a wrong FizzBuzz list into a frozen test, and H3 failed every run because no correct program could pass. The new check runs the file and an independently written reference program isolated; they must print the same non-empty output. One retry, else nothing is written. Writing goes through the normal create command.
7. **Fix, S3 list rule:** text the planner types into an app for a list goal becomes a titled list of points (`list_format.py`). The text route guidance now asks for the whole text in one `type` step, then `save_as`, and no retyping after a verified read-back.
8. **Oracle tightened (H2):** a visible Blender window is now required, not only a `blender.exe` process, which background Blender also satisfies. Earlier H2 receipts used the process check.
9. **Runner:** `--enable section.key,...` turns flags on for test runs only, and `config.json` is untouched.

## Known limits

- The ledger does not see the multi-file coder's model calls (`codex_workload` calls Ollama directly). Its time lands in "other".
- S3 still depends on the planner following the type-then-save sequence. Phase 2 replay recipes are the structural fix.
