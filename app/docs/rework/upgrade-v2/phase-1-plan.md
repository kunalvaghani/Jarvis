# Upgrade v2, Phase 1: quick wins and app APIs first (plan, awaiting approval)

Date: 2026-10-31. Branch `claude_ControlArchitect`, after Phase 0 (`6ef4977`). Every change below is behind a flag that ships off unless it is marked **fix**: a repair of existing behaviour that fails today, needing no new capability. With the flags off, Phase 0's parity holds (S1/S2/S4 9/9).

## 0. What the evidence says (measured 2026-10-31)

| Finding | Evidence |
|---|---|
| Planner prompts are re-read in full on every step | 63 of 67 recorded 9B planner calls were fresh conversations. All of them ran at a constant ~440 prompt tokens/s: median 6,362 tokens, 14.4 s. That is zero reuse, even between consecutive calls sharing the same 7,455-char system prompt and the same 16 tool schemas (~4.3k tokens). The 4 continued calls took 1.0 s. |
| Continuation rarely fits | Conversations start at ~6.4k tokens and the scheduler caps the context at 8,192, so a continued call (+ update + 1,600 reply) almost never fits. |
| Ollama *can* reuse a shared start, partly, on qwen3.5 | Same ~5.3k-token start, different ending: qwen2.5:0.5b re-read 0.17 s; qwen3.5:0.8b (hybrid attention) 5.9 s instead of 29 s. So reuse exists for the hybrid model but is coarse, and something stops it for the 9B planner. |
| The 9B stays loaded during tasks | Scheduler log: in the parity runs the 9B kept 10 GPU layers at 8,192 context with no unloads. But each step interleaves a different-prompt 9B call (decide/verify, role `execution`) between planner calls. |
| `screen` is the largest prompt part | 3.5–5.1k characters per planner call. `web_read`/`web_open` default to `filter='all'`, which includes many nameless wrapper nodes (`generic "" [ref_N]`). |
| Failing live cases | S3: Notepad list typed as bare lines (23 runs, the list rule not applied). H2: `blender_task` failed, then the planner was blocked from retrying it. H3: the coder loop repeated an unchanged proposal against a wrong frozen test. |

## 1. Work items

### 1.1 `speed.cache_order`: experiment first, then the fix the data supports

**E1 (measurement, no code change).** Replay two consecutive recorded planner requests to the local 9B with the live options (10 GPU layers, 8,192 context, native tools), reading `prompt_eval_count`/`prompt_eval_duration` for these variants:
- (a) back-to-back, nothing in between;
- (b) with one decide/verify call between them, as in real tasks;
- (c) with tool schemas in a fixed order and an identical tool set;
- (d) with the user JSON reordered: stable parts first (`capability_context`, `apps`, route guidance), live parts last (`completed`, `last_result`, `screen`, `goal`).

About 10–16 9B calls, all local.

**Build, behind `speed.cache_order`**, according to E1:
- **If a stable start is reused when nothing intervenes:**
  - A task keeps one tool set (the first step's 14 tools, fixed order).
  - The user JSON goes stable → live. The `FIT_ORDER` trimming keeps the stable head intact.
  - Verify/decide calls go to the 2B execution model when `model_hierarchy` allows, so they stop overwriting the 9B planner's cache. This is only where that model already handles the operation; nothing new is routed to it.
- **If the 9B cannot reuse a shared start at all:** the flag instead makes the planner's step update fit a continued conversation. A compact per-step update (with compact reads, 1.3) lets steps 2+ continue the cached conversation, which was measured at 1.0 s instead of 14.4 s. The system prompt, tools and goal are never trimmed.

**Measure:** ledger prompt tokens and `prompt_s` per planner call, before/after, on S1/S2/S3.

### 1.2 `control.compact_reads`

`web_read`/`web_open`/`app_read` output drops nameless container nodes. These are generic/group/none/section roles with no name, no value and no ref the planner could use; their children are kept and lifted one level. Text, headings, table cells, links and controls all stay, refs are unchanged, and `filter='interactive'` is unchanged.
- Measure characters and tokens on recorded reads: D1 pages and the herokuapp tables page.
- Target: at least 40% fewer characters, with every named node kept.

### 1.3 `control.event_waits`: new `control/waits.py`

- `until(probe, timeout, interval)` condition waits replace the six fixed `ledger.pause` sites in `control/service.py`:

  | Site | Wait until |
  |---|---|
  | Notepad notice | it is gone |
  | ctrl+n | a new empty tab is selected |
  | Typed read-back | the field text equals the text sent, or is stable for 2 reads |
  | Settled window read | 2 equal reads, polled at 0.1 s instead of 0.4 s |
  | Save As dialog | its File-name field and Save button exist (UIA `WindowOpened` event when available, else 0.1 s polling) |
  | File written | it exists on disk |

- Browser route: navigation and click waits use Playwright's load-state events where the route still sleeps.
- Every timeout keeps today's upper bound, so a wait can only end earlier, never later.
- **Measure:** ledger `wait_s` per task on S2 and S3.

### 1.4 `vision.tight_escalation`

When the 2B's coarse pass found a box but its refine pass or read-back refused, the 4B grounds only on that tighter crop. It skips its own full-screen coarse pass and the 2B → 4B swap of a full pass. When the 2B found nothing, the 4B runs as today.
- **Gate** (`benchmarks/vision_grounding.py`, D1, 32+3 targets): at least 30/32 hits, 0 wrong clicks, 0 clicks on absent targets, and p95 below the recorded 25.6 s.

### 1.5 Shared Save-dialog recipe (`control.shared_save`, new flag)

A new `control/save_dialog.py` holds today's `app_act save_as` logic: the UIA Save As dialog, refusal to overwrite, and on-disk proof. `save_file` uses it first and falls back to its existing visual (UI-TARS) path only when no UIA dialog appears. Overwrite still needs approval.

### 1.6 API routes for the failing tasks

| Case | Change | Kind |
|---|---|---|
| S3 | Find why the user's list rule (titled list of points) does not reach the typed content. When the goal asks for a list, the text typed into the app goes through the existing `writing` list formatter. | **fix** |
| H2 | Diagnose the `blender_task` failure from its run log. Add a headless-bpy template for primitive objects (add, size, place, name, save) run with `blender -b --python`. The saved file then opens in Blender's window, because the request names Blender, and it is checked by the sealed `blender_object` verifier. | template behind `control.api_routes` (new flag); repair of the retry block is a **fix** |
| H3 | A small single-file project ("folder + main.py that prints …") skips the multi-file coder loop. It creates the folder and file through the file tools, runs the file in a sandbox (`python -I`, as the sealed `python_project` verifier does), and opens the folder with `code <folder>`. Bigger projects keep the coder. | behind `control.api_routes` |

Office COM (H5) is not in this phase's gate.

## 2. Tests (written before the code)

| File | Covers |
|---|---|
| `test_cache_order.py` | Flag off: payload byte-identical to today's (recorded fixture). On: stable keys precede live keys, `goal` last, tool set and order fixed within a task, `FIT_ORDER` trimming never removes the stable head. Continuation path: an update that fits continues, one that does not starts fresh. |
| `test_compact_reads.py` | On recorded AX trees (D1 forms/tables/modal, herokuapp tables): every named node and ref survives; nameless wrappers are removed; output ≥ 40% shorter; S1's table rows (Jason Doe, jdoe@hotmail.com) present. Off: identical output. |
| `test_control_waits.py` | `until` returns as soon as the probe passes, never later than the old fixed bound, and reports a timeout. Each service site, with fake UIA reads, behaves as before on success and on timeout. Off: the same fixed pauses as today. |
| `test_control_vision.py` (added cases) | Tight escalation crops around the 2B's box, never clicks without read-back, and falls back to the full pass when the 2B found nothing. Off: today's chain. |
| `test_save_dialog.py` | The shared recipe refuses overwrite, proves the file on disk, and reports a missing dialog. `save_file` uses it first and falls back to vision only without a UIA dialog. Off: today's paths. |
| `test_api_routes.py` | Blender template: parameters validated (finite sizes, a safe name, path inside approved roots), the script contains no user text as code, and it is run headless and then verified. Scaffold: a single-file request goes to scaffold, a multi-file one to the coder; folder path in scope; `code` CLI opened on the folder only. The S3 list fix: typed text for a list goal is a titled list; non-list text is unchanged. |
| `test_flags.py` | Adds `control.shared_save` and `control.api_routes`, both off. |

## 3. Gate

1. Full suite: no failures beyond the 39 baseline. `mypy --strict` on new and touched control/telemetry files. `launcher --check` ready. `control.health`.
2. Flags off: S1/S2/S4 × 3 shuffled still pass.
3. **Phase 1 flags on: S1, S2, S3, S4, H2, H3 each pass 3 consecutive shuffled runs.**
4. Vision benchmark as in 1.4.
5. **Measure before/after with the ledger** on those 6 cases: p50/p95 task time, model/tool/wait split, planner prompt tokens and `prompt_s`, 9B calls and steps per task. The "before" run is the 6 cases × 3 with flags off and `--telemetry`, about 1.5–2.5 h.

## 4. Close-out

Commit; ADR 0006 (cache-order findings and decision, compact reads, waits, API routes); PROGRESS, handoff and both READMEs; a plain-language report saying which flags are ready to promote.
