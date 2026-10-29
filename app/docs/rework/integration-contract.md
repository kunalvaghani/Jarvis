# Integration contract (Phase 0)

Date: 2026-10-30, revision `7e7a39a`. Every consumer below currently works through the interface listed. The new control layer must satisfy each row, either directly or through a temporary façade, until the consumer is migrated (see [dependency map](migration-dependency-map.md)).

## 1. Consumers and the interface they expect

| Consumer | Calls today | Contract the new layer must keep |
|---|---|---|
| Voice / typed commands (`actions.Actions.execute(Command, cancelled)`) | `_browser().request`, `_ui().execute`, `screen_awareness`, `youtube_chrome.open_requested` | Returns a speakable string; raises `ValueError` with a user-facing message on refusal; never replays after an uncertain dispatch. |
| Planner (`brain.Brain`) | `tools.ToolRegistry.execute(step, cancelled, activate)`, `_ui().runner`, `_ui()._activate`, `visual_fallback.*`, `observe()`, `visual_screen()` | Step dicts `{action, value, content?, folder?, platform?}` validated by `tools.validate_arguments`; result `tools.ToolResult(tool, backend, evidence, attempted, call_id)`. `TaskFailure(attempted=…)` distinguishes "nothing sent" from "uncertain". Observation is `(handle, snapshot)` where snapshot has `controls`, `signature`, `context`, `is_dialog`, `title`. |
| Tool registry (`tools.py`) | `SPECS`, `validate_arguments`, `redact`, `check_policy`, `agent_events.event`, `execution_strategy.observe` | Tool names in `SPECS` stay stable (`browser_inspect`, `browser_navigate`, `browser_click`, `browser_fill`, `select`, `fill_text`, `type_text`, `scroll`, `shortcut`, `open_menu`, `handle_dialog`, `save_file`, …) — the planner prompt and trained checkpoints reference them. New metadata is added to `ToolSpec`, not a second registry. |
| Durable tasks (`task_state`, `task_queue`, `task_ingress`, `workflow_graph`) | `TaskState.require_identity`, checkpoints | Actions carry the task ID; restart resumes from checkpoints with fresh observation, never persisted refs/coordinates. |
| Direct / fast workflows (`direct_execution`, `fast_workflows`) | `_ui()._activate`, `_ui().pending`, `_browser().request` | No model inference for exact requests (latency path). |
| Media (`media_player`, `media_ui`) | `_browser().request('search'/'play_video'/'control')`, `_ui().runner('media_*')` | Verified player state dicts (`verified`, `state`, `message`). |
| God's Eye (`gods_eye`) | `_browser().request('gods_eye', actions=…)` | Loopback-only page (`127.0.0.1:4173`); needs an explicit loopback allowlist entry in `url_policy`. |
| Screen awareness (`screen_awareness`) | `UIControls`, `window_focus` | Read-only observations of the foreground app. |
| Dynamic Island (`island*`, `ui_events`) | `actions.report('tool', …)`, approvals | Status/reply cards keep receiving redacted progress text. |
| Launcher / recovery (`launcher`, `recovery`) | `healthy()`, `repair()`, `close()` on `browser_automation`, `ui_controls`; `visual_fallback.readiness` | Each long-running owned service exposes health and bounded repair; recovery is silent and never replays an action. |
| Messaging (`whatsapp`, `messengers`) | `jarvis_pointer.tap`, `window_focus` | Out of acceptance scope (real accounts). Only the shared input primitive changes under them. |
| Coding agent (`development_browser`, `codex_browser_check`, `pcide`, …) | Playwright directly | Not migrated; must not regress (Phase 7 regression covers it). |

## 2. Request/response shapes kept by the façades

### Browser (`_browser().request(operation, cancelled, **args)`)

Operations (from `browser_worker.validate_request`): `windows_commands`, `reset`, `inspect`, `read_text`, `navigate`, `search`, `play_video`, `gods_eye`, `select_video`, `control`, `click`, `fill`. Responses are dicts with at least `url` and `title` for page operations, `verified: bool` and `message: str` for actions, `owned: True`, `untrusted: True`. `click`/`fill` require the freshly observed `url`.

### Windows (`_ui().runner(request)` → `ui_worker.perform`)

Operations: `ping`, `folder`, `list`, `activate`, `fill_text`, `scroll`, `shortcut`, `open_menu`, `media_key`, `media_range`, `media_search_field`, `windows_commands`. `list` returns `{controls, signature, context, is_dialog, target_pid, thumbnails, foreground_handle, title}`. Control rows: `{name, role, id(runtime_id), rect, focused?, selected?, value?, href?, toggle_state?, context?, password?}`. Action responses: `{message, trace_id, provider, operation, dispatched, verified, evidence, execution_ms}`; uncertain dispatch raises `UncertainAction` with a receipt.

## 3. Invariants every consumer relies on

1. One external action per dispatch; after dispatch, only read-only observation (AGENTS.md rule; `execution_router.execute`).
2. No replay of clicks, shortcuts, typing, file writes or shell commands after an uncertain failure.
3. Password fields are never filled generically.
4. Page/window text is untrusted (`untrusted: True`, `contract` string in browser observations).
5. Approval claims inside a proposal are stripped (`tools.APPROVAL_CLAIMS`).
6. Receipts store metadata only, never typed text, titles or screenshots (`ui_worker.routed.record`).
7. Deliberately closed browser/apps are not restarted.

## 4. New obligations added by the rework

Typed action records (prompt §7), tab-scoped refs, `url_policy` + request hook, risk tiers with per-action approval inside batches, per-stage timings, exclusive foreground-input lock, emergency stop for in-flight control, coordinate module.

## 5. Configured models, quotas and privacy

Read from `config/config.json` on 2026-10-30 (secrets redacted; nothing assumed beyond what is configured).

| Role | Configured |
|---|---|
| Planner / decision / coder | `qwen3.5:9b` (local, Ollama) |
| Execution model (hierarchy) | `qwen3.5:2b` |
| Screen / visual grounding | `screen_model` = `qwen3.5:9b` in config; `brain_worker` uses `qwen3-vl:4b` as the image default (`brain_worker.py:435,457`). Installed VLMs: `qwen3-vl:2b`, `qwen3-vl:4b`. |
| Selector | `convaiinnovations/laya` |
| Cloud: Groq | enabled, free tier, `qwen/qwen3.8-27b`, 1000 req/day, 200k tok/day, 30 req/min, 8k tok/min, **`allow_sensitive_data: false`**, `live_tests_enabled: false` |
| Cloud: Gemini | enabled, free tier, `gemini-3.8-flash`, 5 req/min, 20 req/day |
| Coding cloud | enabled, `dry_run_verified: false`, ≤8 cloud calls/task |
| Anthropic / OpenAI | **not configured** |
| Visual fallback | enabled, `minimum_confidence` 0.95 |
| Physical clicks (touch pointer) | `cursor.physical_clicks: true` |
| Desktop provider order | `structured_first` |
| GPU | RTX 3050 4 GB; `gpu_scheduler` reserves 1024 MB for speech, 512 MB general, context 8192 |

Consequence: screenshots must not go to Groq (sensitive data disallowed). No cloud vision provider is configured, so Route 4 runs locally; the Claude `computer_toolset` adapter stays unconfigured unless the user adds a key and allows it.
