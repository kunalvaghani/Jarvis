# Explicit future resume procedure

**Do not execute a production resume now.** The user temporarily paused the entire campaign on 2026-10-29. Resume requires a new explicit request naming this campaign. A normal Jarvis start, idle event, dependency completion or unrelated coding request is insufficient.

## 1. Locate and verify the saved state

Read [the pause report](AUTONOMOUS_REPAIR_PAUSE.md), [compatibility baseline](AUTONOMOUS_REPAIR_COMPATIBILITY.md), [acceptance matrix](autonomous-repair-acceptance.md) and [cumulative handoff](CLAUDE_HANDOFF.md). Discover the latest named checkpoint rather than assuming no versioned successor exists. The current checkpoint is:

`app/.jarvis-runtime/campaign-checkpoints/autonomous-repair-pause-2026-10-29`

Its immutable `checkpoints/*.json` and `receipt.json` identify archives, manifests, database backups, committed Git bundle, original patches, compatibility data and frozen hashes. Do not rely only on a conversation summary or an old helper's hard-coded source/configuration hashes.

From `app/`, run the implemented read-only verifier:

```powershell
.venv/Scripts/python.exe -m jarvis.campaign_pause status
.venv/Scripts/python.exe -m jarvis.campaign_pause verify --checkpoint ".jarvis-runtime/campaign-checkpoints/autonomous-repair-pause-2026-10-29" --compare-current
git bundle verify ".jarvis-runtime/campaign-checkpoints/autonomous-repair-pause-2026-10-29/git/baseline.bundle"
```

Read `verification.json` and the comparison output. Corruption, an unreadable newer checkpoint, changed frozen bytes or missing artifacts must stop resume. `REVIEW_REQUIRED` is expected after relevant Jarvis upgrades; investigate it rather than restoring old source over new features.

## 2. Preserve newer features and review compatibility

Inspect the current branch, HEAD, status, staged changes and commits since `087a7393a74cf833a3bc558f06f07ddcbf6f39e9`. Preserve newer work in its own reviewed checkpoint first. The saved campaign had mixed uncommitted ownership, so no WIP commit was forced. Its pre-pause source ZIP and staged/unstaged patches preserve those exact changes.

For new feature development, the paused working tree can remain in place with its narrow guards active. An isolated Git worktree from a chosen committed baseline is another option. A clean worktree from the saved HEAD does **not** contain the uncommitted campaign repairs; carry across only reviewed changes. Do not stash/reset/clean the original paused tree or apply an old whole-tree archive over later upgrades.

Compare the actual callable signatures, native tool schema, task/DAG/SQLite structures, requirement versions, checkpoint shapes, approval/ownership rules, memory records, context/resource policy and cloud interfaces in `compatibility-baseline.json`. Review package/runtime changes as well. Preserve original artifacts. If migration is necessary, create a versioned successor checkpoint and test a migration or adapter on isolated copies. Do not pin unrelated Jarvis features to old code indefinitely.

## 3. Validate environment, credentials and quota

Use the supported readiness check. Confirm local Qwen availability and current resource settings; the saved effective context was 8,192 with 10 observed GPU layers, not a promise about a future environment. Docker was unavailable at pause. Resolve or accurately classify prerequisites for the selected next gate.

Credentials were deliberately excluded from archives. Confirm their current local presence without printing them. Revalidate Gemini's model/project/key and free-only billing eligibility and current AI Studio limits. Saved project/model attestation is historical evidence, not a guarantee that future account limits are unchanged.

Use **current live** Groq/Gemini ledgers, including later outside-task usage where visible. Never replace them with checkpoint copies or refund uncertain attempts. The old logical repair ID is `f8069ac88f454d27898b1422f7952be1`; it retained four uncertain Gemini attempts and nine Groq attempts at pause. The ordinary Gemini allocation is three. A fifth-call exception was unfinished work, not a completed or authorized live request during pause. Its task ceiling/time limit and stricter daily/provider limits require fresh review.

`coding_cloud.dry_run_verified` was false before pause. The old 110-test certificate does not cover later priority-policy and pause edits. After explicit resume authorization, run focused zero-token routing/quota/compatibility tests before permitting any new cloud inference. Do not use real requests to test counters. Respect project-wide limits, Pacific reset, headroom, concurrency, 429/cooldowns and missing/changed keys.

## 4. Select only unfinished canonical work

The current GUI snapshot is the checkpoint named in `artifacts/autonomous-repair/gui-producer-progress-checkpoint-provenance.json`. It has eight exact source files; six must remain frozen. The CLI and scoped notes-search acceptance sources have separately preserved hashes. Confirm all bytes before importing evidence.

GUI acceptance remains core 6/6, frozen GUI 2/6 and independent 1/8. The last two trials did not save code. Do not call them PASS or repeat independent checks of the same unchanged source merely to create more logs. Investigate the remaining ineffective proposals and worker/representation strategy first. Do not supply a supervisor-authored calculator solution.

The archives retain all task IDs, project versions, workload receipts, dependencies and counters from 133 historical trials. Many are obsolete alternatives. Do **not** restart them all. Select the canonical latest requirement/repair path and reuse only verified compatible results. Preserve successful CLI/search evidence and do not unnecessarily repeat completed actions.

## 5. Validate isolated DAG restoration before releasing the pause

Restore selected database/artifact copies into a new isolated recovery directory. Keep the originals immutable. Review task commands, requirement/result versions, owned paths, dependencies, leases and any checkpoint containing `dispatch_at` or `uncertain`. There are 27 historical uncertain tasks; never automatically replay them. Existing `ScheduledQueue.control('resume', identity)` deliberately refuses already-dispatched/uncertain work.

Existing supported state APIs are `TaskStore.setting`, `TaskStore.recover`, `WorkflowGraph.update_group`, `ScheduledQueue.restore` and `ScheduledQueue.control`. Validate copied state with these APIs and mocked handlers. Keep per-store `autonomous_repair_pause`, queue pause and group pause protections in place until review completes. Use a versioned path/schema migration for isolated copies where needed; retain completed/failed results and dependency links.

For a never-dispatched, still-relevant task, explicit future release may use the existing per-store setting and group/queue controls after compatibility review. Do not clear pauses on every historical queue. Already-dispatched or uncertain tasks require reconciliation and a newly planned, explicitly controlled continuation rather than reusing an old action checkpoint.

## 6. Explicit release and controlled production continuation

Only after the user explicitly requests resume and the isolated compatibility checks pass:

1. Preserve the exact current pause control as a new immutable resume-audit record. Record the user's authorization, comparison/migration evidence, selected unfinished tasks and current quota decision.
2. Archive the active `.jarvis-runtime/autonomous-repair/pause.json` by an atomic move into that versioned audit directory. Do not delete the only pause record. This is the explicit release boundary; the pause module intentionally exposes no automatic unpause command.
3. Release only the reviewed isolated queue/group markers using the existing state APIs. Keep obsolete historical queues paused. Do not restore the old main queue, memory or quota backups over current live state.
4. For the GUI, use the real production runner with the explicit existing snapshot, original parent repair goal, strict progress/frozen guards and compatible validation/independent observations. Do not blindly run an old `launch-*.py` helper or `--resume-run`; old helpers carry stale fingerprints, and a generic resume goal must not replace the original acceptance requirements.
5. Use local/deterministic tools for simple work and eligible cloud workers only under a reviewed current quota/privacy decision. Keep all earlier charges and uncertain reservations.
6. Independently launch and test any validated model-produced source gain. Mark GUI PASS only after all required frozen and independent criteria pass. Then continue the remaining original application campaign, retaining previous passing results.

Actual production resume was intentionally **NOT_RUN** during pause. Read-only verification and isolated pause/restart/dependency behavior were tested; this document does not claim a future migration or live resume has already passed.

## 7. If resume fails

Cooperatively pause only the selected recovery workers using the existing scheduler control and cancellation tokens. Wait for safe operation boundaries, retain uncertain effects and do not kill shared services. Recreate a versioned `PAUSED_BY_USER` control from the preserved record and reapply the selected per-store/group pauses. Preserve failed-resume logs and make a successor checkpoint.

Never reset the repository, overwrite newer features, replace live quota counters, discard frozen tests, or replay a completed/uncertain file or external action as rollback. Return to read-only root-cause and compatibility analysis with the original pause checkpoint intact.
