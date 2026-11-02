# Brain adapter map (DRAFT, Phase 0)

Date: 2026-11-02. Read-only survey of branch `claude_ControlArchitect` at `c64f570`. Each row: where the subsystem lives today, how it is entered, what it reads and writes, its side effects and guards, and which brain component it becomes. **Nothing here has been changed.** Paths are relative to `app/`.

Reuse rule: the brain wraps these modules with adapters at their existing entry points. Rows marked **reuse as-is** must not be rebuilt inside the brain.

## 1. Request path today (entry to result)

| Step | Module(s) | Entry point | Brain component |
|---|---|---|---|
| Voice capture, wake word, VAD, STT | `audio.py`, `whisper_backend.py` (faster-whisper medium.en), `voice_runtime.py` | microphone loop → final transcript | **Sensor neurons**: `sensor.speech.final` emits `goal.created` |
| Typed input | `main.py`, `ui_transport.py`, `ui_worker.py` | typed text → same command path | **Signal Gateway** input |
| Parse and split | `engine.py` (`Engine.feed`, `split_commands`), `commands.py` (`parse`) | `Engine(actions.submit).feed(text)` | **Intent classify (deterministic)** |
| Chat or task | `conversation_intent.py` (`quick_kind`, `model_kind` on qwen3.5:0.8b) | `Actions._route_unparsed` | **Intent classify (LLM fallback)** |
| Safety screen | `request_safety.py` | before execution | **Policy** (hard deny) |
| Queue admission | `task_ingress.py` (`TaskIngress`), `task_store.py` (SQLite WAL), `task_scheduler.py` (`ScheduledQueue`: priorities, dependencies, locks, lanes, cancel), `workflow_graph.py` | `Actions.submit` → ingress | **Goals / Project DAG Scheduler: reuse as-is**, the system of record for goals |
| Execution | `actions.py` (`Actions.execute` → `_execute`, 2,214 lines) | per command kind | **Durable dispatcher** wraps this |
| Fixed routes (upgrade v2 Phase 1) | `fast_routes.py`, `small_program.py`, `small_edit.py`, `web_app.py`, `blender_live.py` | `Brain._run` and `Coder.run` hooks | **Deterministic fast-path neurons** (already verified routes) |
| Planning | `brain.py` (`Brain.run`, 1,980 lines), `native_tools.py` (9B tool-calling planner), `hierarchical.py` (bounded DAG, ≤40 nodes), `adaptive_planning.py`, `route_guide.py`, `execution_strategy.py` | `Brain.run(goal)` | **Cortex**: planner / execution-graph compiler (wrap, then migrate) |
| Tool dispatch | `tools.py` (`ToolRegistry.execute`: schema, scope, approvals, cancellation), `toolkits.py`, `agent_tools.py`, `app_adapters.py` | `ToolRegistry.execute(step)` | **Motor neurons**: one node per ToolSpec |
| Step and goal verification | `brain.py` verify calls, `learning/verifiers/` (sealed: text file, Blender object and scene, Python project) | after each step and at goal end | **Independent verifier** (sealed verifiers reuse as-is) |
| Results, UI, speech | `island_*.py`, `glass_ui.py`, `ui_events.py`, `speech.py` (Kokoro saved; Piper, F5) | reports and transcript | **Projections** (read-only), `motor.speech.say` |

## 2. Subsystems

| Subsystem | Files | Entry / I/O | Side effects and guards | Becomes |
|---|---|---|---|---|
| Model router, local | `brain_worker.py` (separate process; per-operation model, token and timeout settings; `web_coder` for whole files), `small_model.py` (`route`), `gpu_scheduler.py` (residency, partial offload, speech headroom), `inference_limits.py` | `BrainClient.request(op, **data)` → JSON | GPU, RAM; no external side effects | **Model neurons** (`model.plan`, `model.verify`, `model.write_code`, `model.vision`), router policy stays in the worker |
| Model router, cloud | `hybrid_inference.py` (`HybridGateway`), `groq_adapter.py`, `gemini_adapter.py`, `cloud_policy.py`, `coding_cloud_policy.py`, `coding_cloud_routes.py` | privacy and quota checked before dispatch | network, quota ledger (SQLite) | **Model neurons** with `privacy` tags; quotas and policy **reuse as-is**, never learnable |
| Vision grounding | `control/routes/vision.py` (Qwen3-VL 2B→4B) | screenshot → box | local only (loopback enforced) | `sensor.screen.ground` |
| Voice | `audio.py`, `whisper_backend.py`, `voice_runtime.py`, `speech.py` | events | mic, speakers | sensor and motor neurons; TTS stays progressive |
| Planner / researcher / coder / tester | `brain.py`, `native_tools.py`; research: `autoresearch.py`, `deerflow.py`, `firecrawl_tools.py`, `reference_research.py`, `reference_images.py`; coding: `coder.py`, `native_coding.py`, `codex_workload.py`, `coding_files.py`; tests: `native_coding` checks, `development_browser.py`, `web_app.check` | goal → steps / patch / report | worktrees in `codex_workload.py`; writes via approved create/modify | composite **skill neurons**: `skill.research`, `skill.code.patch`, `skill.code.test` |
| Queue, grouping, DAG | `task_ingress.py`, `task_store.py`, `task_scheduler.py`, `workflow_graph.py`, `island_queue.py`, project grouping in `project_requirements.py` / project intelligence | SQLite WAL `.jarvis-runtime/task-queue.sqlite3` | admission, locks, cancellation | **reuse as-is**; the brain compiles a per-goal graph **beneath** each scheduled task |
| Tool registry | `tools.py` (`ToolSpec`, `REQUIRED`/optional args, `ToolRegistry.catalog`, `limit_tools`), `toolkits.py`, `agent_tools.py`, `execution_strategy.py` (`Method` records: tier, domain, operations, verification, latency, cost, unsafe) | catalog → planner | per-tool approval inside adapters | **Capability registry seed**: ToolSpec + `Method` → node descriptors |
| MCP / connectors | `mcp_bridge.py` (stdio JSON-RPC, `tools/list`, `tools/call`), `mcp_persistent.py` (Spotify persistent child), `mcp_contract.py`, `mcp_synthesis.py` (generated tools, Docker), `.jarvis/mcp.json` (youtube 5 tools, spotify 86 tools, allowlisted), `integrations/jarvis-connectors/` | `mcp_status`, `mcp_list_tools`, `mcp_call` | server start/call need host approval; never auto-retried | **MCP neurons** from `tools/list` × allowlist |
| Blender | `app_adapters.blender_task` (background templates), `blender_live.py` + `templates/` (visible live builds), `blender_host.py`, `blender_jobs.py` | JSON request → .blend + readback | approval per write; scripts disabled on inspect | motor neurons `blender.create`, `blender.live_build`; verifier `blender_scene` |
| Browser control | `control/routes/browser.py` (Playwright, Chrome accessibility refs), `control/service.py` (`web_open/read/act`), older `browser_*` tools | refs → actions | policy: no passwords, consequential targets need approval | motor neurons `browser.open/read/act` |
| PC control | `control/routes/uia.py` (UI Automation), `control/input.py`, `control/locks.py`, `control/save_dialog.py` | window refs → actions | focus/title checks; protected windows refuse | motor neurons `app.open/read/act/save_as` |
| Files and shell | `tools.py` core tools, `desktop_tasks.py` (`modify_text_file`), `actions.py` (`create_in_folder`, `delete_in_folder` with approval and Recycle Bin, `run_command` with approval) | exact paths in scoped roots | approvals; deletion always approved | motor neurons with `side_effect_class: write|destructive` |
| Memory and intelligence | `conversation_memory.py`, `obsidian_memory.py`, `viking_memory.py` (nomic-embed-text), `memory_index.py`, `memory_curator.py`, `skill_memory.py`, `experience_memory.py`, `experience.py`, `reasoning_bank.py`, `learning_memory.py`, `code_memory.py`, `ui_memory.py`, `capabilities.py` (self-model) | retrieval → planner context | writes to vault and SQLite stores | **Hippocampus**: `memory.search`, `memory.read_verified`, `memory.commit_episode`; skill and experience stats seed **Phase 4 priors** |
| Obsidian | `obsidian_memory.py` (`ObsidianMemory`), external vault | reads notes; daily summaries | writes summaries | **Projection target** (one-way export), plus memory source |
| Approvals | `control/policy.py` (`ApprovalGate`), `Actions._approve`, `approval_receipt.py`, `request_safety.py` | per action | blocks until user answers | **Policy / Human Approval Gate: reuse as-is**; the brain may only call into it |
| Worktrees | `codex_workload.py` (per-task workspaces, combined with LocalGithub) | coding workloads | git worktrees | adapter for `skill.code.patch` |
| Docker sandbox | `docker_runtime.py`, `repo_sandbox.py`, `azr_sandbox.py`, `deerflow_sandbox.py`, MCP runtime image `jarvis-mcp-runtime:1` | containerised runs | engine currently **stopped** on this PC | adapter with `requirements: [docker_available]` |
| UI | Native Python/Tk **Dynamic Island**: `glass_ui.py`, `island.py`, `island_*.py` (control, queue, mind, media, desk), `island_control.py` (route cards), `notch_widgets.py`, `ui_events.py` (`UIEventBuffer`), `ui_transport.py` | event buffer → island | display only | **Projection**; Phase 5 UI must live here (no Electron/React app exists) |
| Logging and telemetry | `agent_events.py` (`event`, `task_trace`), `telemetry/ledger.py` (timing ledger), `telemetry/shadow.py` (shadow decisions), `.jarvis-runtime/logs/`, transcript | JSONL | none | **Journal inputs**; the shadow log is the Phase 1 shadow channel |
| Crash recovery | `recovery.py` (`Watchdog`, `OllamaService`, silent repairs), `task_recovery.py` (`retry_read` for reads only, `TaskFailure`), `task_state.py` (checkpoints), `launcher.py`, `jarvis_bootstrap.py` | supervisor | never replays uncertain actions | **reuse as-is**; the brain journal adds idempotency keys |
| Feature flags | `flags.py` (upgrade v2: on/off and off/shadow/suggest/act modes) | `flags.enabled/mode(config, ...)` | none | home of the brain mode flag |

## 3. Static inventory sources (for `inventory/*.yaml`)

1. `ToolSpec` declarations in `tools.py`, `toolkits.py`, `agent_tools.py`, `app_adapters.TOOLS`, `firecrawl_tools.py`, `deerflow.py`, `repo_tools.py`, `rea_tools.py`, `gmail_api.py`, `cloud_architect.py`, `evolution_promotion.py`, `development_api.py`.
2. `execution_strategy.METHODS`: tiers, verification and cost per method.
3. MCP allowlists in `.jarvis/mcp.json` (youtube 5, spotify 86), schemas from a live `tools/list` (needs the servers started: host approval).
4. Fixed routes and verifiers added in upgrade v2 Phase 1.

## 4. Open questions for the user

See the Phase 0 report in the chat of 2026-11-02 (conflicts list).
