# Longer plans and execution checks

Updated 2026-10-04. Restart with Stop Jarvis / Start Jarvis to load these changes.

The executor previously stopped after six actions even when work remained. Its
durable completion list retained only twelve actions, and the native planner saw
only six completed identities. The background prompt scaffold also reported a
completed count capped at six. These constraints could truncate a longer workflow
or make later planning lose track of progress.

Jarvis now uses `brain.max_task_actions` (default **20**, integer **1–40**) across
initial planning, continuation, recovery and resume. It retains forty completed
actions, including their dependencies and arguments. Native prompts carry all
these bounded identities and the last six detailed tool results. The separate
background prompt records the actual completed count. A proposed plan that exceeds
the remaining budget is rejected before dispatch; reaching the limit pauses with
remaining work retained rather than claiming completion. A one-step planner gets
one final read-only completion check, never a 21st dispatched action at the default
limit. Fresh observations, target checks and whole-goal verification still apply.

Task instructions can contain up to **6,000 characters**. Checkpoints retain the
same exact bounded goal, preventing different instruction tails from matching the
same resume task. Instructions and tool actions are not always one-to-one:
opening an app, navigation and other required steps may consume extra actions.
Increase the bounded setting if a known workflow requires more than twenty.

Full-plan JSON generation now requires the `find` field, supports dependency
metadata, permits forty steps and allows 4,000 generated tokens. Genuine streamed
planning activity renews the inactivity deadline (300 seconds HTTP / 330 seconds
worker with the current configuration), within `brain.max_planning_seconds`
(default **900**, finite configured ceiling capped at 3,600). Silence, Stop and the
total deadline still stop the owned worker. This change covers full `plan`/`replan`
JSON; the usual native one-action proposal remains bounded by its existing timeout.
Model inference can still take minutes on CPU; the action-budget fix does not
guarantee completion in seconds.

The optional Hermes/Harness bridges share the same bounded proposal validator
and allow twenty-step plans instead of rejecting anything beyond six; their
planning output allowances are 4,000 tokens. They retain their separately
configured inference deadlines. Bridge scope/budget checks are regression-tested;
the ten live measurements here use the built-in Qwen planner, not those bridges.

A live planning pilot exposed missing `modify_file.find` fields. Before execution,
Jarvis may copy that missing operand only from a unique explicit user instruction
of the form `Modify notes.txt: replace pending with reviewed`, matching the exact
filename and replacement. Ambiguous operands or changed replacement text remain
blocked; this never authorizes a whole-file overwrite. Existing operands remain
unchanged. Plain `.txt` / `.csv` workflows with a subject such as “project” also
stay in the file executor instead of mistakenly entering the coding workflow.

Another live proposal left every file destination blank. Initial and continuation
planning now allow one read-only correction request for that specific defect,
passing runtime feedback with the unchanged goal and completed progress. A still
missing destination remains rejected. Stop prevents accepting the response or
issuing the correction; no file operation is retried. The planner prompt explicitly
requires the user-specified destination and exact replacement operand.

The twenty-step pilot also asked for a destination already specified by the user.
For a literal multiline list headed by an explicit single current-folder scope,
Jarvis now copies that scope into omitted `folder` fields for the listed create,
modify and read operations. It never changes a supplied destination, binds an
unnamed target, or infers a location for mixed-scope/nonliteral instructions.
Normal fresh folder resolution, exact text checks and write verification still
apply. Raw Qwen proposals remain in the records, including any omitted fields;
runtime grounding copies only operands already specified by the user.

The strict checker also exposed that `read_file` identities incorrectly included
an unused `content` field. The dispatcher ignores this operand when reading.
Identity checks now ignore it too, so changing that dummy field cannot bypass
the completed/failed-action guard. Write/append contents and file scopes remain
part of the identity.

An uncertain external effect remains blocked from replay. Resume inspects fresh
state and requires a new safe plan; saved steps are reference data, never a replay
queue. No new dependency, model download or paid API was added.

## Verification and scope

The [file workflow driver](../scripts/verification/verify_plan_execution.py) exercises the production
Brain, ToolRegistry and Actions file operations in isolated owned directories.
Each workflow writes exact text, replaces it in order and reads its final file.
Independent disk contents, completed arguments, ordering and task status determine
success. The ten workflow lengths are **2, 3, 4, 5, 6, 8, 10, 12, 15 and 20**.

The [authored-plan check](../artifacts/reports/plan-execution-fixture-check.json) passed
**10/10**. These are actual file operations with authored plans and deterministic
decision/verification oracles, not measured LLM planning latency. The separate
[native check](../artifacts/reports/plan-native-live-check.json) activated **20 actual
Win32 buttons in exact order**, with fresh accessible-control checks, twenty
retained completed steps and an independent fixture event list, in **64.953 s**.
It used an authored plan and deterministic verifier, with zero model calls.
The [earlier native run](../artifacts/reports/plan-native-live-check-history.json) took
26.078 s. The later run overlapped the regression suite and live Qwen planning;
both are fixture measurements, not general desktop task latency guarantees.

The [live-planner record](../artifacts/reports/plan-execution-live-check.json) stores
actual configured Qwen plans, exact fixture instructions and individual outcomes.
The [earlier pilot](../artifacts/reports/plan-execution-live-check-history.json) preserves
the omitted-operand failures; it was stopped after that common defect was found.
The live driver uses Qwen for full planning and deterministic decision/verification
oracles for executing those plans. It does not claim autonomous model decision
accuracy, arbitrary app compatibility, microphone reliability or desktop speed.

All **10 actual Qwen-generated plans passed** after fixes and retests:

| Workflow | Plan lines / executed actions | Result | Original Qwen + execution time (s) |
| --- | ---: | --- | ---: |
| Notes | 2 | Pass | 101.812 |
| Todo | 3 | Pass | 108.656 |
| Inventory | 4 | Pass | 104.453 |
| Journal | 5 | Pass | 167.750 |
| Schedule | 6 | Pass | 159.032 |
| Budget | 8 | Pass | 176.609 |
| Release | 10 | Pass | 241.657 |
| Travel | 12 | Pass | 261.672 |
| Project | 15 | Pass | 284.062 |
| Audit | 20 | Pass after execution retest | 153.953 |

The twenty-step model proposal already executed correctly with all seven files
matching disk expectations; the checker initially flagged its unused read operand.
The same recorded Qwen proposal was then executed again in a fresh owned fixture
after that identity fix, passing exact order/arguments and disk checks in **1.547 s**
(execution only, no new inference). The original model-inclusive time is retained
above, and the record explicitly identifies the reused proposal and retest date.
These measurements were made on the configured CPU inference path and are not
voice-to-completion promises. Failed pilots remain in the linked history.

[Focused regression tests](../tests/test_plan_execution.py) cover all ten real
file workflows, incremental execution through action twenty, a rejected 21st
action, exact long-goal retention, complete native/scaffold context and streamed
planning deadlines. Injected faults confirm that Stop after seven verified actions
dispatches no eighth action and retains thirteen; a failure after the eighth real
file effect leaves seven verified actions, blocks resume and never repeats the
write or dispatches action nine. Existing recovery tests cover owned-worker
shutdown and retry backoff.

Reproduce from the application directory:

```powershell
.\.venv\Scripts\python.exe -m scripts.verification.verify_plan_execution
.\.venv\Scripts\python.exe -m scripts.verification.verify_plan_execution --live
.\.venv\Scripts\python.exe -m scripts.verification.verify_plan_execution --live --resume
.\.venv\Scripts\python.exe -m scripts.verification.verify_plan_native
.\.venv\Scripts\python.exe -m scripts.verification.verify_plan_execution_regression
```

The native driver temporarily focuses only its own fixture window, closes that
window and restores the previous foreground window. No user app is closed or
restarted. File fixtures remain under `.jarvis-runtime/plan-execution-fixture`;
records contain authored examples, not private recordings or desktop screenshots.
`--resume` retains successes for the exact same authored instructions and reruns
only failed or missing cases. Retained rows identify their source check date;
previous records are archived before a new run, rather than erasing failures.

Full regression/readiness results are saved in the separate
[regression record](../artifacts/reports/plan-execution-regression-check.json). Readiness
checks startup assets and dependencies; it does not execute a spoken task.
On 2026-10-04, **960 tests passed** and launcher readiness returned **`ready`**
with no missing assets or dependencies. This includes optional backend proposal
validation, bounded read-only correction and Stop during that correction.
