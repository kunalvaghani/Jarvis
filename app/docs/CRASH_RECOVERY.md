# Crash recovery

## Uncertain-send UI restart verification - 2026-10-20

At claude e5af0e7, the owned mock-send journey now verifies an actual child crash, fresh TaskState/Actions reload, queued resume and real App/Island/Desk/Tk readback of Task paused. The planner is not invoked and the mock outbox remains one row. This proves that bounded UI path; it does not authorize replay or certify real account delivery/physical speech. [Evidence](../artifacts/jarvis-audit/modules/37-e2e/2026-10-20-independent-e5af0e7/ui-restart-journal.json) and [remaining blockers](CLAUDE_HANDOFF.md).

## Demonstration and uncertain task completion â€” 2026-10-20

Recording startup/observation failures stop the owned hook and persist failed state. Cancellation stops recording and cannot create a provisional skill; if hook cleanup itself fails, the failure is persisted and the owned reference retained for retry. Fresh cancellation/PID checks occur after consent before observation. Native hook exit and HWND/PID lifetime acceptance remain unverified.

TaskState may downgrade an optimistic task result to paused when an external write is uncertain. Actions now returns that matching durable result to the worker/speech event and decision outcome. Restart must inspect the actual result; no automatic send/click/write replay. This closes the tested mock-send seam, not universal verifier/UI authority. [Prompt 37 evidence](../artifacts/jarvis-audit/modules/37-e2e/2026-10-20-completion-a9b4ce1/verdict.md) Â· [Cumulative handoff](CLAUDE_HANDOFF.md).

## Observability boundary — 2026-10-20

Optional journal failures degrade diagnosis without repeating a tool/consultation or overriding policy. Agent/cloud append caps preserve old files (32/8 MiB); no automatic deletion. Tool rows carry host task/monotonic clock metadata; cloud v2 rows retain categorical decisions and digests, not payload/advice. Skill history stores bounded metadata and reports malformed old evidence. Missing telemetry cannot establish verification or authorize retry.

[Prompt 36 verification](../artifacts/jarvis-audit/modules/36-observability/2026-10-20-completion-a9b4ce1/verdict.md): 631 passed / 0 failed / 5 skipped; remaining whole-pipeline/live/export gates are in the [Claude handoff](CLAUDE_HANDOFF.md). Historical raw logs remain untouched; these changes are not an all-log privacy or live recovery certificate.

## Security diagnostic boundary — 2026-10-20

Learned ability failure reports withhold untrusted exception messages and traceback source. Fixed permission/output-contract guidance and builtin error categories remain available for local repair, so repair can continue without storing arbitrary exception secrets. Tool report redaction now covers colon/JSON credential assignments and complete authorization schemes. Uncertain external writes still cannot be replayed.

The [Prompt 35 verification](../artifacts/jarvis-audit/modules/35-security/2026-10-20-completion-a9b4ce1/verdict.md) records 537 relevant passes/four skips and explicit remaining privacy/verification gates. This is fixture evidence, not a full live recovery or all-log privacy certificate. Keep unresolved work in the [Claude handoff](CLAUDE_HANDOFF.md).

## Dependency recovery boundary — 2026-10-20

Missing imports, environments and model assets report `repair_required`; startup/recovery do not silently install packages or pull models. Explicit repair authorization is single-use and bounded by identity, expiry, artifacts and resources. Invalid/trailing pip options, unsafe IDs and non-boolean network permission are refused; concurrent grant consumers are serialized by a native OS file lock. Persistent lock files carry no ownership after process close/crash.

Approved model transport still needs immutable revision/byte-budget enforcement, and staged venv promotion needs executable relocation validation. Do not treat import-only staging checks as proven rollback or permission to run setup. See the [Claude handoff](CLAUDE_HANDOFF.md) and [independent verification](../artifacts/jarvis-audit/modules/34-dependencies/2026-10-20-completion-a9b4ce1/verdict.md): 227 relevant passes / one live CUDA skip, no real install/download. Full release remains blocked.

Jarvis on Windows uses a virtual environment redirector which can have a different
PID from the actual Python interpreter. Checking its heartbeat against the
redirector PID caused false startup timeouts and repeated restarts.

The supervisor now gives each launch a unique heartbeat file and tracks the
actual interpreter using its process handle. Startup publishes that identity
before loading UI dependencies. Cleanup terminates only the owned interpreter
and its launcher, leaving user applications and shared services alone.

After an unexpected nonzero exit or a supervisor timeout, Jarvis restarts with
task recovery enabled, including after long running sessions. It reloads the
current interrupted goal, saved project and verified progress. The planner observes
fresh state, receives completed actions as context, and cannot repeat them.

If an action was interrupted before verification, or project files were already
written, Jarvis retains the task and reports why it is paused. It requires inspection
and a new instruction for the remaining work rather than blindly replaying the
original goal. Say **resume last task** to continue a retained task that is safe to
replan. Startup without crash recovery announces retained work instead of executing
old failed tasks automatically. Stop, Quit and cancelled tasks are respected.

Microphone failures no longer cancel independent tasks. Model loading has a longer
health grace period; microphone callbacks update liveness even during spoken
answers. Forced audio resource resets are deferred while a task is active.
Restarting audio also preserves the active task's desktop target.

Verification: the regression suite includes injected monitor failures, a simulated
310 second healthy heartbeat with a redirected PID followed by crash recovery,
actual Windows venv interpreter tracking/termination, interrupted task persistence,
safe continuation, completed action replay rejection, and intentional Stop behavior.
