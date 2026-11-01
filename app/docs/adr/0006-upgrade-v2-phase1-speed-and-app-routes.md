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

## Additions after the first gate runs (2026-10-31 to 2026-11-02)

The first live gate failed, and the user then asked for a different task on every run, live Blender modelling, varied apps and image references. Each item below came from a failed live run; all of it is behind `control.api_routes` unless named otherwise.

10. **`cache_order` room only from low-value context.** Freeing 2,000 tokens from every optional part dropped learned skill and memory context, and the planner's Blender arguments went wrong in 3 of 3 runs. `ROOM_DROPS` limits it to reasoning lessons, experience and realtime context. A shortened read now says so (with `cache_order` only).
11. **`control.arg_repair` (new flag).** `app_act` with the arguments in the operation slot (`{"content": {"text": "..."}}`, 6 of 6 S2 runs) becomes a `type` step. Nothing else is guessed.
12. **Small programs and small edits.** The route hooks `Coder.run`, the single entry for both the code-task and planner paths. Programs get a stated rule first (the 9B swapped Fizz and Buzz in about half its programs, once in both at the same time), a static safety check (safe-module imports only; the earlier reference program ran shell commands), and the program part of the request only. `small_edit.py` edits one existing file: the output must match an independent reference, or the current output when the request says to keep it; a named one-argument function must agree with an independent version on 66 inputs.
13. **Fixed routes (`fast_routes.py`).** Clear Calculator arithmetic (typed once, display checked against an exact value), website questions (page read in full, every number in the answer must appear on the page) and Blender requests skip the planner. Deterministic routing for unambiguous requests is the usual remedy for small tool-calling models.
14. **Live Blender (`blender_live.py`, templates `blender_live.py`, `blender_house.py`, `blender_human.py`).** A visible Blender opens a factory scene and a fixed template builds live; no model-written code runs in Blender. Morphs turn the default cube into the requested shape. Houses follow a plan from a reference (below): walls with Boolean-cut openings, framed glazed windows, door, floors, partitions, stairs, furniture per room, roof by type, procedural brick, plaster, wood, stone, tile, slate and glass materials. Humans start from Blender Studio's *Human Base Meshes* (CC0, downloaded with the user's approval) and add a skin shader (tone variation, subsurface, pores, faint veins), patterned irises, glossy sclera and particle hair (scalp, eyebrows, eyelashes, beard, body). Each saved file is read back by a separate Blender, and the sealed `blender_scene` verifier checks the geometry (shape surfaces, openings, furniture on floors, eyes, hair strands, vertex counts). The skin check tests for a warm hue, never brightness, after it wrongly failed darker skin.
15. **References (`reference_research.py`, `reference_images.py`, flag `learning.cloud_research`).** Wikipedia article introductions for the style (DuckDuckGo returned a bot check), then Wikimedia Commons photos browsed and scrolled in Jarvis's own browser window and read by the local Qwen3-VL 4B. Photos that are not houses are skipped; readings are voted and colour names mapped to real colours. Only the search words leave the PC. The installed Qwen3-VL builds think before answering even with `think=false`; starting the answer with its first field fixes it (6–15 s per photo). The vision model is unloaded afterwards to free the 4 GB GPU for Blender, and a network failure falls back to built-in style notes.
16. **Animated web apps (`web_app.py`).** One `index.html` with GSAP or anime.js from cdnjs (the user chose CDN loading, no install). Headless Chrome checks for console and page errors, that the animation library is used (any method, counted after the page was used) and that every button and text box changes the page; problems go back to the model for up to three repairs. Whole-file writes may use 6,000 output tokens and `brain.web_coder` (`qwen3-coder:30b`, measured 19 tokens/s against 5 for the 9B on this PC).
17. **Routing fixes found by varied tasks.** A question naming a website is a task, not chat; "Use the Calculator app: add ..." is not a coding request; "then multiply the result" stays one command; a question is never "already done" before it is answered; "in a new folder called X in my Y folder" creates X inside Y; "open VS Code and build/design/develop a landing page" is a coding task; VS Code always opens a project in a new window (`--reuse-window` replaced the user's open project).
18. **Live suite.** `--vary` runs a different variant on every repeat (39 tasks: websites, sums, lists, refusals, Blender shapes, humans, cars, houses, code edits and web apps); oracles check the real file, display, geometry or page behaviour.

## Known limits

- The ledger does not see the multi-file coder's model calls (`codex_workload` calls Ollama directly). Its time lands in "other".
- Program agreement uses two programs from the same local model; stating the rule first makes a shared mistake much less likely but cannot exclude it.
- Live models are procedural (templates and base meshes), not photo-real sculpting; Commons photos inform the plan's floors, roof, materials and colours, not exact geometry. Cars are still the earlier untextured original design.
- The web-app route needs the internet for the CDN library.
