# Paused campaign compatibility baseline

The campaign is `PAUSED_BY_USER` as of 2026-10-29. New Jarvis features may evolve normally. These safeguards apply when restoring or resuming the saved campaign, not to unrelated development.

The private named checkpoint contains `compatibility-baseline.json`: 47 original critical source/configuration fingerprints plus one native-worker implementation fingerprint (48 total), actual Python callable signatures, the native tool schema, task lifecycle states/edges, SQLite table definitions, dependency versions and 20 accepted CLI/GUI/search artifact hashes. It also captures original requirement/specification files, task/workload receipts and versioned project records in the artifact archive.

The immutable `compatibility-native-worker-supplement-v1.json` adds the actual native-worker source and callable signatures to automatic comparison; the original captured tool schema and 47-file baseline are retained.

## Interfaces to review after upgrades

| Area | Actual source/contracts |
| --- | --- |
| Durable task lifecycle | [task_store.py](../jarvis/task_store.py), commands with `kind/value/extra`, persisted `spec/checkpoint`, validated state edges |
| Scheduling and admission | [task_scheduler.py](../jarvis/task_scheduler.py), [task_ingress.py](../jarvis/task_ingress.py), group pause and per-store pause markers |
| DAG and result versions | [workflow_graph.py](../jarvis/workflow_graph.py), workflow schema setting **1**, node/dependency/result versions |
| Project specifications | [project_requirements.py](../jarvis/project_requirements.py), [projects.py](../jarvis/projects.py), [project_intel.py](../jarvis/project_intel.py); requirement revision numbers are not global serialization versions |
| Worker contracts | [coder.py](../jarvis/coder.py), [codex_workload.py](../jarvis/codex_workload.py), [native_coding.py](../jarvis/native_coding.py) |
| Structured/tool boundaries | [structured_output.py](../jarvis/structured_output.py), [mcp_contract.py](../jarvis/mcp_contract.py), [execution_contract.py](../jarvis/execution_contract.py), saved native `SCHEMA` |
| Ownership and verification | [coding_files.py](../jarvis/coding_files.py), [codex_validation.py](../jarvis/codex_validation.py), [candidate_checks.py](../jarvis/candidate_checks.py), [approval_receipt.py](../jarvis/approval_receipt.py) |
| Checkpoints and effects | [workload_state.py](../jarvis/workload_state.py), [task_state.py](../jarvis/task_state.py), [coding_processes.py](../jarvis/coding_processes.py) |
| Model/context/resource routing | [hybrid_inference.py](../jarvis/hybrid_inference.py), [model_selection.py](../jarvis/model_selection.py), [knowledge_worker.py](../jarvis/knowledge_worker.py), [gpu_scheduler.py](../jarvis/gpu_scheduler.py) |
| Cloud and quota interfaces | [coding_cloud_routes.py](../jarvis/coding_cloud_routes.py), [cloud_quota.py](../jarvis/cloud_quota.py), [gemini_adapter.py](../jarvis/gemini_adapter.py), [groq_adapter.py](../jarvis/groq_adapter.py) |
| Memory records | [code_memory.py](../jarvis/code_memory.py), [code_intel.py](../jarvis/code_intel.py), [conversation_memory.py](../jarvis/conversation_memory.py); consistent private DB backups retained |
| Pause barrier | [campaign_pause.py](../jarvis/campaign_pause.py), pause-control schema **1**, pause-checkpoint schema **1** |

Legacy task/quota SQLite stores and workload JSON do not all declare a public serialization version. Their captured SQL, actual field shapes, source fingerprints and compatibility tests are the baseline; do not invent a version number. SQLite `user_version` and internal schema counters are recorded separately from application protocol versions.

## Required safeguards

1. Preserve the original checkpoint, archives, manifests and historical acceptance reports. Any migration produces a new, named version and works on an isolated copy.
2. Run archive readback and current-source comparison before considering resume. Any critical-file or frozen-artifact difference returns `REVIEW_REQUIRED`. A source difference is a review requirement, not a reason to revert a new feature.
3. Review actual changed interfaces, requirements, tool schemas, dependency/result versions, ownership constraints, approvals, checkpoints, resource policies and provider adapters. Build a versioned adapter or migration only where needed; test it on copied state.
4. Do not restore an old whole working tree over later upgrades. The committed baseline bundle and pre-pause patches are recovery references, not automatic rollback instructions.
5. Never restore archived quota counters over current live ledgers. Other tasks may have consumed capacity while the campaign was paused. Recheck model/project/key binding, free-tier eligibility, current limits, resets, stricter provider feedback and uncertain reservations.
6. Keep the pause control, per-store pause markers and workflow-group pauses in effect until explicit user authorization and successful compatibility validation. Generic queue resume, startup recovery, dependency completion and new normal tasks do not authorize this campaign.
7. Relocated paths, new models, missing credentials, changed packages and changed requirement schemas require explicit review. Archived absolute paths must be migrated on copies, not blindly replayed.
8. Keep completed/failed results and all 27 historical uncertain task checkpoints. A terminal report is not permission to re-execute an action; an uncertain dispatch must be reconciled separately.

## Read-only validation commands

From `app/`:

```powershell
.venv/Scripts/python.exe -m jarvis.campaign_pause status
.venv/Scripts/python.exe -m jarvis.campaign_pause verify --checkpoint ".jarvis-runtime/campaign-checkpoints/autonomous-repair-pause-2026-10-29" --compare-current
.venv/Scripts/python.exe -m jarvis.launcher --check
```

The verifier checks archive/file hashes, auxiliary recovery files and frozen artifacts. It reports differences and restores **zero files**. It never authorizes or starts resume. The readiness command uses the existing supported check; Docker is currently unavailable. No live UI, voice or connector result is implied.

Relevant bounded regression modules include `tests/test_campaign_pause.py`, `tests/test_autonomous_queue.py`, `tests/test_workflow_graph.py`, `tests/test_cloud_coding_quota.py`, `tests/test_workload_state_history.py`, `tests/test_task_recovery.py`, `tests/test_required_observations.py` and `tests/test_launcher_readiness.py`. The saved stabilization runner denies HTTP/socket access. Future feature-specific compatibility testing may add tests; do not run the full application campaign merely to test migration.
