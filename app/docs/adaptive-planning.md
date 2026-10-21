# Adaptive planning controller — 2026-10-21

The sequential Brain executor now admits planning from evidence, continues fully specified file chains, and requires a separate whole-goal verification after an incremental planner says done. This is a local architectural repair, not certification of every Jarvis integration.

## Execution trace and diagnosis

| Layer | Actual path and finding |
| --- | --- |
| Commands and queue | `engine.py` preserves whole task clauses; `Actions.submit` queues generation-bound commands and `Actions._run` owns execution. `task_queue.py` selects cancellation targets; it is not the planner. |
| Task routing | `Actions._execute` tries configured direct execution and fast workflows, then `Brain.run`. Brain routes Gmail, Python generation, project coding and eligible hierarchical DAGs before its sequential executor. These specialized paths keep their existing contracts. |
| Sequential planning | `Brain.planning_request` prepares acquisition/context, then `propose_plan` and `BrainClient.request`. Incremental sessions translate planning into `next_step`; full plans use `plan`/`replan`. Invalid file scope gets one inference-only correction. |
| Native function calling | `native_tools.plan` makes one advertised tool proposal, with one bounded schema-correction inference before dispatch. It retains a compact conversation and existing load/prompt/generation timers; it does not execute tools inside a hidden recursive agent loop. |
| Providers | `BrainClient._request` attaches selected memory, skills and conditions and routes configured native/Qwen, Harness or Hermes backends. Worker failures retry inference only. No extra model or evaluator is introduced by this controller. |
| Inference/scheduling | `brain_worker.Models` selects configured models; `gpu_scheduler` owns GPU admission. Existing inference idle/total limits and action safety budgets remain. The controller adds no thinking duration or iteration limit. |
| Tools | `ToolRegistry.execute` retains argument validation, discovery, approval, provider dispatch and result contracts. Brain independently observes after dispatch. `execution_router.py` retains guarded desktop dispatch and uncertain-action receipts. |
| Redundant work found | Sequential adaptive execution previously replanned after every verified step, even when the remaining literal file operands were ready. Four deterministic-planner/real-file cases made 40 planning calls. |
| Completion defect found | Incremental `planner_done` could generate `goal_verified` from the planning response itself and skip the separate final verifier. That shortcut is removed. |
| Existing recovery | `recover_task` records failures, observes fresh state, rejects failed/completed actions and refuses uncertain writes. `TaskState` uses UUID ownership and atomic checkpoints; startup marks running tasks interrupted. Those protections remain. |
| DAGs | `hierarchical.py` and `dag_execution.py` already validate dependencies, serialize effects, verify each result, revalidate restored reads and preserve successful independent nodes during targeted replans. They retain their own planner/recovery path. |
| Coding and other routes | `coder.py` validates generated content and checks file identity before writes, but syntax/readback alone does not establish application behavior. Direct commands, fast workflows, Gmail and hierarchical response synthesis do not acquire this sequential controller's completion authority. Their wider acceptance gates remain open. |
| Memory | Workflow/experience/skill context is historical guidance, not permission. Controller metadata uses the existing TaskState checkpoint and stores hashes of action identities instead of another replay queue or reasoning transcript. |
| Exact navigation recipes | `step_planning.replay` can bypass model planning for an exact verified recipe; each transition is freshly grounded and checked. It retains its existing dispatch budget/no-replay contract and does not acquire the sequential controller's authority. |
| Supervisor | `launcher.py`, `recovery.py` and model recovery retain owned-process, intentional stop, silent repair and inference-only retry rules. No new service, dependency, manifest entry, model download or launcher change is needed. |
| Owned metadata repair | Broad regression exposed Windows rename failures in forge registry/staging, Gmail write receipts and repository snapshots, plus evolution state assertions. `checkpoint_io.py` now guards those metadata commits. Only an unchanged owned source/target can retry a known-failed rename; content fingerprints, containment, link/depth/size guards and caller shutdown checks close recovery on uncertainty. No ability, send, installation, Git acquisition, source deployment or output delivery is repeated. |

The measured defect is redundant orchestration, not proven slow model inference or memory retrieval. Baselines use simulated model responses. No live inference timing, GPU scheduling delay or account integration latency is inferred from these measurements.

## Behavior and state

`jarvis/adaptive_planning.py` implements UNDERSTAND, PLAN, EXECUTE, OBSERVE, VERIFY, REPLAN, COMPLETE and BLOCKED. Its ledger lives at `current.adaptive` inside the existing `.jarvis-runtime/state/task_state.json`:

- Original objective, whole-request acceptance and numbered clauses.
- Verified action and remaining-step identities; full arguments/results stay in `current.plan` and checkpoints.
- Bounded decision summaries, planning cycles, meaningful verified changes, proposal oscillations, repeated contexts, planning-call duration and time to first admitted action.
- Goal-verification evidence digest and unresolved blocker. No full thinking transcript or screenshots are added.

Planning contexts ignore conversation growth and cosmetic changes to expected text or unused tool fields. The same context requests a fresh read-only observation instead of another model call. An unchanged/revisited observation blocks precisely; it never invents a click or shell action. New evidence and distinct correction/dependency contexts remain admissible without a count or duration cutoff. Forty retained decision/request records are a storage bound, not a reasoning budget.

The relative-benefit rule is deliberately narrow: after verified/confirmed progress, a nonvisual, nonincremental sequence of literal `create_file`, `modify_file` and `read_file` steps can continue without regenerating its global plan. Every pending step must have a target, folder and expected result; modifications need an exact old-text operand. Failed/completed actions are excluded. Existing dependency/scope validation, tool approvals, disk readback and final verification still execute. UI, browser, MCP, ambiguous, unknown and unconfirmed actions continue using their existing planning path.

A planning completion claim is a proposal to verify. The final verifier must accept the whole original goal, with no retained work. Recognized numbered literal create/replace/read clauses also require matching verified actions in request order; a model verdict cannot overrule an omitted literal clause. Other natural-language criteria still depend on the existing verifier and available evidence. `TaskState.finish` downgrades managed sequential tasks lacking this completion proof to paused.

`Brain.run` rejects simultaneous entry on the same worker before its mutable sessions can overlap. Each persistent update carries the captured task UUID. Late updates cannot overwrite a replacement task. Restart keeps the ledger and verified plan as context; executable steps are never automatically replayed. Existing resume blockers still control uncertain effects.

The existing Cognitive Loop panel receives a bounded state/count summary (verified, remaining, planning calls). Rendering is not yet certified by a fresh screenshot; no older UI image is presented as proof of the new indicator.

Queued task history now uses the durable task outcome, so a paused task is not displayed as done. Restart marks an active ledger BLOCKED and retains its interrupted state. An uncertain-write checkpoint overrules even an otherwise completed controller verdict.

The shared metadata guard allows four attempts only for Windows errors 5/32/33 while source and target remain unchanged, and revalidates them after backoff before another commit. It preserves pending files/directories on failure. Fingerprinting refuses links/reparse points, more than 5,000 nodes, depth over 32, files over 32 MiB or total file bytes over 64 MiB. Repository snapshots retain their stricter existing 2,000-file / 1 MB-per-file / 20 MB-source admission limits. These are storage/commit guards, not reasoning budgets. Source-code deployment continues its existing approval-bound single write; the metadata retry helper is not used for it. Repair summaries go to `.jarvis-runtime/repairs.jsonl` and the existing transcript callback when connected, without file contents, popups, speech or service restarts. Optional diagnostic failures cannot replay an action.

## Reproduce safely

Use the existing environment, with a workspace-local TEMP/TMP directory when the Windows sandbox denies atomic replacement in its default temp directory:

```powershell
New-Item -ItemType Directory -Force .jarvis-runtime/adaptive-tests | Out-Null
$env:TEMP = (Resolve-Path .jarvis-runtime/adaptive-tests).Path
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m pytest tests/test_adaptive_planning.py tests/test_plan_execution.py tests/test_task_state.py tests/test_task_recovery.py tests/test_step_planning.py tests/test_task_graph.py -q
.\.venv\Scripts\python.exe -m scripts.verification.verify_adaptive_planning --output .jarvis-runtime/adaptive-after.json
.\.venv\Scripts\python.exe -m scripts.verification.verify_adaptive_live --output .jarvis-runtime/adaptive-live.json
.\.venv\Scripts\python.exe -m jarvis.launcher --check
```

The benchmark only creates owned temporary files and uses a deterministic planner and independent disk/action-order oracle. It performs no live account action or model inference. Some existing broad tests require permitted local loopback/subprocess access outside the sandbox. Do not disable security assertions to make them pass.

## Evidence and limits

See the [dated evidence packet](../artifacts/jarvis-audit/adaptive-planning/2026-10-21/README.md) for raw before/after cases, final test counts and readiness. Baseline revision: `0199c16`. This change is on `codex/adaptive-planning`; no publication or activation is implied.

Live offline/cloud model quality, real desktop/browser/Blender/Unreal/YouTube/Spotify workflows, UI rendering, process-kill/power-loss acceptance and global completion authority across specialized routes remain separate acceptance gates. Existing configured transport/action watchdogs have not been replaced with a global thinking cutoff. A new observation admits reasoning but cannot guarantee that a model's private reasoning is useful; the controller evaluates observable progress only.
