# Control-layer audit (Phase 0)

Date: 2026-10-30. Starting revision `7e7a39a9b4c0226e2c9ec89235476be5f17999a7` on branch `claude_ControlArchitect`.
Source of truth: [control architecture](../architecture/control-architecture.md) (SHA-256 `4790067c…0fdcc`, copied from the user's download).

This audit reads implementations and call sites, not file names. Every classification below cites the code it is based on. No behaviour was changed in Phase 0.

## 1. Summary

Jarvis already has a working, safety-conscious control stack, but it is spread across about 25 modules with no shared contract:

- **Browser**: one Playwright worker process (`browser_worker.py`) that owns a persistent Chrome profile, plus separate paths for the user's own Chrome (`youtube_chrome.py`, `gmail_chrome_worker.py` via UIA), a development-preview browser (`development_browser.py`) and a coding-validation browser (`codex_browser_check.py`). The worker exposes **labels, not refs**: `click`/`fill` resolve `get_by_role(name=label, exact=True)` at action time. There is no ref registry, no tab model (actions refuse when more than one tab is open), and no request hook or URL policy beyond `browser.url_for`.
- **Windows UIA**: a pywinauto worker process (`ui_worker.py`) that collects a flat control list keyed by UIA `runtime_id`, plus a provider cascade (`execution_router.py` + `execution_adapters.py`) with six "providers" that are all thin wrappers over the same UIA patterns. Strong guards exist (identity, rect, focus and foreground checks before each dispatch; no replay after uncertain dispatch).
- **Vision**: `visual_fallback.py` asks the local `qwen3-vl:4b` model for a UI-TARS-format click, parses it with a vendored UI-TARS parser, and dispatches via `visual_worker.py`. It is restricted to `save_file` and a few step types, requires confidence ≥ 0.95, and refuses Tier-2 words. Capture is `PIL.ImageGrab`; there is no dxcam/mss path, no crop-then-ground and no ground-truth evaluation.
- **Input**: four different low-level injectors: touch injection (`jarvis_pointer.py`), raw `SendInput` (`visual_worker.py`, `actions.py`, `push_to_write.py`), `keybd_event` (`whatsapp.py`), pywinauto `type_keys`, and pyautogui (`windows_command_desktop.py`).
- **Coordinates/DPI**: `main.py` sets process DPI awareness through `display.enable_high_dpi()` before Tk. `jarvis_pointer.physical_pixels` switches the *thread* to per-monitor-v2 temporarily. The visual worker sets awareness independently. There is no single coordinate module and no multi-monitor/negative-origin handling beyond what Win32 returns.
- **Routing**: no capability-aware router. The planner (`brain.py`) picks tool names from `tools.py` `SPECS`; the tool name decides the backend. Route escalation exists only inside the UIA provider cascade and in `save_file` (native → vision).
- **Verification**: present but uneven. UIA patterns read back state when the pattern exposes it; browser `fill` verifies the value; browser `click` explicitly returns `verified: False`; media controls verify player state.
- **Emergency stop**: only `awareness_control stop` for proactive tasks (`intent_catalog.py:172`, `awareness.py:1104`). There is **no** stop that halts in-flight browser/desktop control.

## 2. Inventory and classification

Classes: **KEEP** (unchanged, used by the new layer), **REFACTOR** (logic reused inside the new layer), **REPLACE** (new layer supersedes it), **REMOVE AFTER MIGRATION**, **INVESTIGATE**.

### 2.1 Browser

| Module | Lines | What it actually does (evidence) | Class |
|---|---|---|---|
| `browser_worker.py` | 603 | Playwright `launch_persistent_context` on `.jarvis-runtime/browser-profile`, `--force-renderer-accessibility` (l.141-150). `SUMMARY` JS collects up to 120 controls by tag/role, no refs (l.63-85). `click`/`fill` by exact accessible name; refuses with >1 tab (l.552-580). YouTube search/play/player control with real state verification (l.179-502). God's Eye page driver (l.312-398). | **REPLACE** generic ops (`inspect`, `navigate`, `read_text`, `click`, `fill`) with Route 2. **REFACTOR** YouTube player/search and God's Eye into site adapters on top of Route 2 (they are API-like, verified, and worth keeping). |
| `browser_automation.py` | 62 | Parent-side controller; JSON-lines transport to the worker; YouTube profile restriction; `owns_handle` maps an HWND to the owned profile (l.43-53). | **REPLACE** by Route 2 executor; `owns_handle` logic **REFACTOR** into locks/ownership. |
| `browser_cursor.py` | 46 | Draws a fake cursor in the page, then `element.click()` via Playwright (CDP); never moves the OS mouse. | **REFACTOR** (visual cue is a UX feature; keep as optional presentation layer). |
| `browser.py` | 46 | `url_for` / `browser_args` / `music_search_url`; opens URLs in an installed browser without shell. | **KEEP** (Route 1 "open in user's browser" primitive; `url_for` to be checked against new `url_policy`). |
| `windows_command_browser.py` | 60 | Pinned DOM recipes for `windows_commands`. | **REFACTOR** onto Route 2 refs. |
| `youtube_chrome.py` | 223 | Opens YouTube in the user's own Chrome profile (not automated), falls back to the Jarvis browser. | **KEEP** (user-browser launch, not automation). Route-selection policy must call it, not bypass it. |
| `gmail_chrome_worker.py` | 239 | Drives Gmail compose in the **user's existing Chrome** through UIA named controls. | **INVESTIGATE**: conflicts with the rule "never silently take over normal browsing". Keep disabled for acceptance tests; needs an explicit user decision. |
| `development_browser.py`, `codex_browser_check.py`, `pcide.py`, `exploration.py`, `design_intel.py`, `development_learning.py`, `coding_programs.py`, `codex_validation.py` | — | Playwright used by coding/validation workflows against loopback previews. | **KEEP** (coding-agent subsystem, not user-facing control). Out of scope for replacement; must not regress. |
| `webmcp.py` | 205 | Experimental page-bound WebMCP adapter, disabled by default, no importers. | **KEEP** (deferred). |

### 2.2 Windows UIA

| Module | Lines | Evidence | Class |
|---|---|---|---|
| `ui_worker.py` | 350 | pywinauto UIA `descendants(cache_enable=True)` flat collection of 15 roles, identity = `runtime_id` + rect + name (l.11-84). `routed()` guards foreground/identity before every dispatch, writes metadata-only receipts to `.jarvis-runtime/execution-receipts.jsonl` (l.87-153). Media and Explorer-folder special cases. | **REPLACE** the collection/dispatch core with Route 3 (tree with refs, `AutomationId` > `Name`, control patterns, events). **REFACTOR** the guard rules and receipt redaction into `verify.py`/`audit.py`. |
| `ui_transport.py` | 145 | Warm worker subprocess, deadline, no replay after dispatch, exponential cooldown. | **REFACTOR** (generic worker transport; reuse for executors that must stay out-of-process for COM threading). |
| `ui_controls.py` | 383 | Voice-label matching, `UNSAFE_INFERRED` regex, parent-side UIA client. Imported by 10 modules. | **REFACTOR**: matching/label code stays; the worker client moves behind Route 3. |
| `execution_router.py` | 115 | "One external action then observations only"; tries providers in order; preparation failure may fall through, dispatch failure never does (l.35-115). | **REFACTOR** into `recovery.py`/`router.py` semantics (this rule is exactly doc §8). |
| `execution_adapters.py` | 314 | Six providers (UFO, Windows-MCP, Cua, Open Computer Use, Agent-S, JarvisPointer). Five of them call the same UIA patterns with different wrappers (l.61-227). | **REPLACE** the five duplicated pattern providers with one Route 3 pattern dispatcher. **KEEP** the vendored attribution (`integrations/execution-primitives/`). |
| `upstream_windows_patterns.py` | 293 | Vendored Windows-MCP pattern wrappers (yinkaisheng). | **REMOVE AFTER MIGRATION** if Route 3 calls patterns directly; licence notice retained. |
| `desktop_actions.py` | 95 | Shortcut allowlist, desktop step validation, explicit regex plans, `apply_control`. Imported by 6 modules. | **REFACTOR** (shortcut allowlist → `policy.py`; explicit plans stay with the planner). |
| `desktop_tasks.py` | 171 | Close app, write/modify text file in a named folder. | **KEEP** as Route 1 file operations, re-checked against path confinement. |
| `window_focus.py` | 96 | Foreground a just-launched app. | **REFACTOR** into Route 3 window management with focus-stealing detection. |
| `windows_commands.py`, `windows_command_desktop.py` | 316 / 146 | Pinned reference recipes; desktop adapter uses **pyautogui**. | **REFACTOR** recipes onto Route 3; remove pyautogui from this path. |
| `media_ui.py` | 235 | Spotify/YouTube app controls via UIA + `type_keys`. | **REFACTOR** into an app adapter over Route 3. |
| `whatsapp.py`, `messengers.py` | 1155 / 133 | Messaging apps via UIA, `keybd_event`, touch pointer. Consequential (send). | **INVESTIGATE**: real accounts; excluded from all testing by the safety rules. Migrate only their input calls to the shared input module. |

### 2.3 Vision and input

| Module | Lines | Evidence | Class |
|---|---|---|---|
| `visual_fallback.py` | 397 | qwen3-vl:4b via `brain.client.request('visual_ground')`, UI-TARS click parse, confidence ≥ 0.95, Tier-2 word block, save-as flow with disk readback. | **REFACTOR** into Route 4 (keep safety checks; add crop-then-ground, ground-truth evaluation, coordinate module). |
| `visual_worker.py` | 209 | Fresh-capture check (≤5 s), identity/geometry/focus/held-modifier checks, image-unchanged check before input, `SendInput` unicode typing; physical mouse injection disabled (l.81-83). | **REFACTOR** checks into Route 4 pre-dispatch admission. |
| `screen_worker.py` | 92 | Capture one visible window for a screen question. | **REFACTOR** into the capture module. |
| `screen_awareness.py` | 481 | Proactive suggestions about the foreground app. | **KEEP** (consumer; re-point its observations to the new layer). |
| `jarvis_pointer.py` | 129 | Touch-injection tap that restores the user's cursor; waits for idle mouse; thread-level physical-pixel context. | **REFACTOR** into the single input module as the "independent pointer" method. |
| `independent_cursor.py` | 196 | Visible cyan cursor cue + `activate_point`. | **KEEP** as presentation; input calls go through the input module. |
| `display.py` | 48 | Process DPI awareness via `SetProcessDpiAwarenessContext`, before Tk. | **KEEP**; becomes the one DPI initialiser the coordinate module asserts. |
| `push_to_write.py` | 202 | Low-level keyboard hook + `SendInput` dictation. | **KEEP** (user-driven dictation, not agent control). |
| `actions.py` (SendInput at l.100) | 2169 | Central command dispatcher; `_ui()` and `_browser()` lazily create the controllers (l.1050-1067). | **REFACTOR**: the dispatcher stays; its control branches route through the new layer. |

### 2.4 Shared subsystems the new layer must reuse

| Subsystem | Where | Notes |
|---|---|---|
| Tool registry | `tools.py` `ToolRegistry`, `SPECS`, `validate_arguments`, `redact` | Tools have name/backend/description/approval only; no schemas, risk tiers, timeouts or verification hooks. Extend `ToolSpec` rather than adding a parallel registry. |
| Planner | `brain.py` `Brain` (plan/replan/recover, `validate_plan`, max 20 steps), `brain_worker.py` | Planner model `qwen3.5:9b`, execution model `qwen3.5:2b`. |
| Durable tasks | `task_state.py`, `task_queue.py`, `task_ingress.py`, `workflow_graph.py`, `task_recovery.py` | Checkpointing and "never replay uncertain actions" already enforced. |
| Policy / audit | `agent_events.check_policy`, `agent_events.event` (`.jarvis-runtime/agent-events.jsonl`), `execution_strategy.observe` | Reuse for audit; extend with route/timing fields. |
| MCP | `mcp_bridge.py` (opt-in stdio client, approval for every server start), `mcp_persistent.py`, `mcp_contract.py` | Reuse for Phase 3. |
| Approvals | `approval_receipt.py` (request-bound digests), `ToolSpec.approval` | Per-action approval exists for `delete_file`, `run_command`, toolkit tools. |
| UI | `island*.py` Dynamic Island, `ui_events.py` | Status/reply cards. |

## 3. Duplicated functionality

1. **Five UIA "providers"** wrapping the same patterns (`execution_adapters.py` l.61-227) — one pattern dispatcher is enough.
2. **Five input injectors** (touch, SendInput ×3, keybd_event, pywinauto `type_keys`, pyautogui).
3. **Three DPI setups** (`display.py`, `jarvis_pointer.physical_pixels`, `visual_worker.__main__`).
4. **Two browser-observation formats**: worker `SUMMARY` controls and UIA `collect` rows for Chromium windows.
5. **Two capture paths**: `screen_worker.py` and `visual_worker.WindowsInput.screenshot` (both `PIL.ImageGrab`).

## 4. Gaps against the target architecture

| Requirement (prompt §/doc §) | Current state |
|---|---|
| Stable tab-scoped refs, staleness errors (doc §2.3) | Absent. Labels resolved at action time. |
| Multi-tab | Refused when >1 tab. |
| `url_policy` + request hook, SSRF/private-IP blocking (doc §4, §13) | Absent in the owned browser. `url_for` only normalises. |
| Capability-aware router with measured success | Absent; tool name selects backend. `execution_strategy.observe` records outcomes but nothing reads them for routing. |
| Unified typed action record (prompt §7) | Absent; dict steps + `ToolResult(evidence: str)`. |
| Coordinate module, multi-monitor, negative origins (prompt §9) | Absent. |
| Vision crop-then-ground, ground-truth metrics | Absent. |
| Emergency stop for control | Absent. |
| Per-stage timing | Only total `execution_ms` in UIA receipts. |
| UIA events instead of polling | Absent (50 ms polling, l.94 `execution_router.py`). |
| Risk tiers 0/1/2 | Implicit (regex blocks + `approval="user"`). |

## 5. Environment facts that constrain the plan

| Fact | Evidence | Impact |
|---|---|---|
| Runtime interpreter is **Python 3.10.6** (`.venv`) | `.venv/Scripts/python.exe --version` | Prompt asks for 3.11+. Changing the interpreter affects every subsystem; needs a user decision. New code will be written to run on 3.10. |
| Installed: playwright 1.63.0, pywinauto 0.6.9, comtypes 1.4.17, pywin32 312, PyAutoGUI 0.9.54, pillow 12.3.0, onnxruntime 1.23.2, pytest 8.4.2 | `pip list` | Routes 2/3 can be built without installs. |
| **Not installed**: `anthropic`, `uiautomation`, `mss`, `dxcam`, `pydirectinput`, `mypy`, `coverage`/`pytest-cov` | `pip list` | Phase 1 gate needs `mypy` and coverage → install approval needed. Vision capture needs `mss` or `dxcam`. |
| No Anthropic/OpenAI credentials configured | `config.json` has `groq` and `gemini` only | The Claude toolset adapters (doc §12.5/12.6) stay optional and unconfigured. |
| Owned browser profile contains `Login Data`, `Cookies`, `Web Data` | `.jarvis-runtime/browser-profile/Default` | Cannot be used as the "dedicated test profile without signed-in accounts". A fresh profile is needed. |
| Docker engine unavailable | handoff readiness | Not needed for this work. |

See [model and privacy inventory](integration-contract.md#5-configured-models-quotas-and-privacy).
