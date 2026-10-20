# Crash recovery

**Independent audit — 2026-10-19 IST (`0e3ad47`): NOT READY.** Current fault injection found that a matching-session heartbeat can supply a sibling PID which the supervisor then terminates without proving process-tree ownership. Repair logs also retain synthetic secret content. Both are unresolved P1s in the [Prompt 32 evidence packet](../artifacts/jarvis-audit/modules/32-service-recovery/2026-10-19-independent-0e3ad47/verdict.md). The ownership and verification descriptions below record the existing design and historical tests; they do not establish the missing ownership guarantee. No source repair was applied by this audit.

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
