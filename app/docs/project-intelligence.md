# Project Intelligence & Requirement Awareness Engine (PIRAE)

PIRAE is a candidate implemented 2026-10-24 IST on `claude/cognitive-awareness`. It sits on top of the [Cognitive Awareness Engine](cognitive-awareness.md). It lets you direct a project in conversation. Jarvis:

- asks only the questions worth asking;
- keeps a versioned requirement specification;
- plans the work into the **existing** durable queue;
- updates only the affected work when you change your mind mid-build;
- reports progress from recorded evidence.

It is deterministic and does not call a model; implementation uses the existing coding agent and planner. Full release acceptance remains open. See [Verification](#dated-verification-2026-10-24-ist) and [Open gates](#limitations-and-open-gates).

## Example

```
You:    Jarvis, create a new desktop application.
Jarvis: What should the desktop application do?
You:    Monitor system performance and help optimize my PC.
Jarvis: Where should I save it? Is there an existing project I should use as reference? I'll treat it as read-only.
You:    Save it in my Projects folder. Use the old monitoring app as reference, but don't modify it.
Jarvis: Saving it in …\Projects\monitor-system-performance. Using OldMonitoringApp as a read-only reference (3 files, Python).
        Project Monitor System Performance registered with 9 requirements (spec v9). Plan: Setup, Architecture, Features,
        Verification. Queued 6 task(s) in dependency order; setup starts now and later steps wait for their prerequisites.
You:    Also add battery optimization.
Jarvis: Added R10: Add battery optimization (spec v10). Queued 1 new task(s). Tasks updated in place: …
You:    Actually, use no cloud services.
Jarvis: Recorded constraint R12: Use no cloud services (spec v12). Compatible work continues.
```

This transcript is from the automated test fixture, which uses temporary folders and a fake coding agent. It is not a recording of a live session.

## Reuse, not duplication

| Need | Existing component | PIRAE adds |
|---|---|---|
| Execution, locks, lanes, approvals, overnight mode, recovery | `TaskIngress` / `ScheduledQueue` / tool approvals | Admission-time dependencies (`submit(dependencies=…)`) and `WorkflowGraph.create_workflow`. Nothing else |
| Project/goal grouping, DAG, result invalidation | `WorkflowGraph` groups, edges, `invalidate` | One workflow group per project |
| Implementation | `code_task` (existing coder) with the workspace as an absolute path; `In folder …, …` tasks for non-software projects | Instructions that cite the current spec version and constraints |
| Project discovery | `projects.project_paths`, configured `project_roots` | A read-only reference snapshot (size and SHA-256 per file) |
| 20-second routine choices | `DecisionManager` + Queue view | Technology choice before any code is written |
| Proactive reasoning | Cognitive Awareness Engine | Requirement conflicts and gaps sent to it as observations |
| Memory | Obsidian `memory.record` | A project summary on creation; `ProjectStore` is authoritative |

There is no second executor, project queue, memory authority or approval manager. A small `project_step` command kind runs on the existing action worker. It does two things:

- creates the isolated workspace, writing new files or files Jarvis generated itself;
- runs acceptance checks.

## How it works

1. **Routing.** `commands.parse` sends three kinds of utterance to `project`: explicit project starts (the head noun must be something a project produces, so "create a new branch" is excluded), project-scoped restrictions ("don't modify that file", "don't change the database"), and "show the design/plan/requirements". Everything else that `Actions` receives as free text (`task`/`ask`) is offered to `ProjectIntelligence.claims()`. That check classifies the shape of the sentence against the active project. Anything that is not a project utterance follows the normal routing, unchanged. The hook runs after cognition has perceived the user's words, on the ingress thread, so voice capture never waits for it.
2. **Classification** recognises: new project; reference; location; add, modify or remove a requirement; constraint; priority; progress, remaining, completed, blockers, why, design, missing, "better way"; pause, resume, switch, revert, overnight; permission; "accept recommendation"; and answers to an open question. Patterns use the sentence's grammar ("add X", "make the Y more Z", "don't use X", "X instead"), not a list of example sentences. Conversational lead-ins ("Actually,", "Okay,") are ignored.
3. **Requirements** live in a versioned store:
   - Each has a category (explicit, inferred, recommendation, assumption, unknown, confirmed, rejected), a kind, a polarity (require or prohibit), a status and its source evidence.
   - Each change writes an immutable spec snapshot (v1, v2 …), so "I changed my mind" can revert the last change.
   - The objective's own clauses become **inferred** functional requirements. Software projects get inferred test and README deliverables, and a reference project's main language becomes an inferred preference.
4. **Clarification policy.** `Priority = U · (0.4·Impact + 0.3·Rework + 0.3·Risk)` per open slot (objective, location, references, technology, …). The weights and slot values are tunable heuristics, not calibrated probabilities.
   - Score ≥ `ask_threshold` (0.4): ask now. A cheap related question (references) rides along with a question that has to be asked anyway.
   - Score ≥ `default_threshold` (0.2): a provisional default, offered as a 20-second routine choice where reversible.
   - Below that: a silent safe default, recorded as a decision.
   - The technology choice is reversible before any code exists. Silence picks it after 20 s, only after the question is actually shown.
   - Authorization is checked separately from the score. With no destination and no configured `default_workspace`, nothing is created.
5. **Context resolution:**
   - **Locations:** "my Projects folder" is resolved by name under `project_roots`, `search_roots` and (if `search_home`) your home and Documents folders. If there isn't exactly one match, Jarvis asks.
   - **References:** they are matched by name tokens and treated as **read-only** unless you say "you can modify …". A registration snapshot records the size and SHA-256 of up to 2,000 files, and nothing is written into the reference folder. Reusable components are suggested as copy-and-adapt, never edited in place.
6. **Planning** is proportional to the project: Setup → (Architecture when there is more than one feature) → one task per functional or interface requirement → Tests (software) → Verification. Constraint conformance reviews and change follow-ups are added later. Each task is admitted to the queue with its prerequisites as graph edges, in the project's workflow group. Tasks that need a pending decision stay planned until it is made, while setup continues.
7. **Live changes** (`_impact`) touch only work that is linked to the changed requirement or overlaps its concepts:
   - **Unstarted** tasks are updated in place. They keep the same task identity and dependencies, and the command is refreshed in both the store and the scheduler. Nothing is duplicated.
   - **Running** compatible tasks finish, and a follow-up task applies the change.
   - **Running** incompatible tasks (a new prohibition) are paused at their cooperative checkpoint. Completed effects are preserved and never replayed.
   - **Completed** work gets a follow-up task.
   - Tests and verification are retargeted to wait for new work, and rerun when the spec version moves past their evidence.
   - **Stale writes are refused:** before any project task executes, `Actions.execute` calls `dispatch_guard`. A task that is no longer the current revision of its plan entry, or that was superseded or paused, is cancelled before it can write. The workspace step itself refuses a non-empty folder, and generated files are replaced only if they still have the content Jarvis last wrote.
8. **Conflicts.** A new requirement with the opposite polarity on a shared concept triggers one of two responses:
   - If the other requirement is an inference or assumption of Jarvis's own, it is superseded (and recorded).
   - If it is an explicit requirement, both are marked *conflicting* and Jarvis explains the conflict and asks "keep R10 or keep R11". Affected tasks are held while unrelated work continues. The loser becomes *rejected*.
   - Examples of opposite polarity on a shared concept: "no cloud services" against "sync through a cloud API", or "everything must run offline" against "upload to a remote server".
9. **Failures.** A failed implementation task gets at most `max_repair_attempts` (default 2) new diagnostic attempts. Each attempt is a new task that includes the failure and asks for fresh inspection; the original is not replayed. Tasks with an uncertain effect are never retried automatically. After that the task is **blocked** and shown under blockers.
10. **Verification and traceability.** Each requirement is traced through the chain *requirement → planned tasks → task states → artifacts → acceptance check → status*. Status is never "verified" just because a tool ran. The acceptance step records its method with every result:

    | Requirement | Check | Method |
    |---|---|---|
    | "Do not modify the reference …" | Pass/fail | Size and SHA-256 comparison with the registration snapshot |
    | Prohibitions on the network concept | Pass/fail | **Static** scan for network/cloud client imports and remote URLs. This is not a network-disabled runtime test, and is reported as "verified (static check)" |
    | Location | Pass/fail | The folder exists |
    | Functional | `evidence` / `not checked` | Static keyword trace in the source (not behavioral) |
    | Tests | Test files present | The test files are not executed by this check |
11. **Proactive reasoning** (`_evaluate`) finds:
    - missing tests;
    - unmeasurable requirements ("faster", "better");
    - reusable reference components;
    - excessive scope;
    - open conflicts.

    These are stored as **recommendations**, not requirements, until you say "accept recommendation N". New findings are sent to the awareness engine as `project.requirement.*` observations, and its attention and interruption policy decides whether to say anything.
12. **Continuity.** Projects, requirements, versions, decisions, questions and plans persist in `.jarvis-runtime/projects.sqlite3`. After a restart the active project, its decisions and its open plan are reloaded, and the queue's own recovery rules apply to the tasks. The ingress maintenance loop calls `reconcile()` (throttled to every 5 s) to fold finished tasks back into plans and queue newly unblocked work. A morning report gains a `.projects.json` companion. It lists completed and remaining features, files, verification, automatic decisions, failed or blocked tasks, decision reasons and next steps.

## Commands

| Say | Effect |
|---|---|
| "Create / start a new *app / tool / report / Blender scene / project* …" | Starts discovery. A descriptive request ("a Blender scene of a foggy forest at dawn") is already its objective |
| "Use *X* as reference" / "Save it in *my Projects folder* / *D:\path*" | Read-only reference / destination |
| "Also add …", "It should …", "Include …" | New requirement, plus new tasks |
| "Make the … more …", "Use … instead", "Change …" | Modifies the most related requirement (asks if two are equally related) |
| "Remove that feature", "Drop …" | Removes it; its unstarted task is cancelled |
| "Don't use / modify / change …", "Use no …", "Everything must run offline", "Stop editing that module", "Keep the old implementation" | Constraint; incompatible work stopped at a safe point; a conformance review is queued |
| "Prioritize … first", "Make this the highest priority" | Raises matching tasks (now, or when they are queued) / the project group |
| "Explain your current progress", "What's left?", "What have you completed?", "What are the blockers?", "Why did you choose that architecture?", "Show me the current design / plan / requirements" | Answers from the store, queue and verification records |
| "Check whether something important is missing", "Can you think of a better way?", "Accept recommendation 2" | Proactive findings; accepting one makes it a confirmed requirement |
| "I changed my mind" | Reverts the last requirement change as a new spec version |
| "Pause / resume the project", "Continue where you stopped", "Switch to the … project" | Group pause/resume and active-project switch |
| "You can modify the reference" | Grants edits to a registered reference; existing file approvals still apply |
| "Finish the safe remaining work overnight" | The existing queue's overnight mode; approvals, the locked-desktop gate and the 20-second policy still apply |

The Island **Mind** view has a project strip showing:

- active project, status, spec version and done/total tasks;
- the current task and its milestone;
- any question waiting for you;
- the last requirement change;
- check results, blocked tasks and the next step.

Its buttons are Next project, Requirements, Plan, What's left, Blockers, Pause/Resume and Open folder. Routine choices appear in the existing Queue view.

## Configuration and rollback

```json
"project_intelligence": {
  "enabled": true, "default_workspace": null, "ask_threshold": 0.4, "default_threshold": 0.2,
  "max_repair_attempts": 2, "search_roots": [], "search_home": true
}
```

- Set `default_workspace` to a folder to skip the location question; projects are then created inside it.
- No package, model or service is added.
- **Rollback:** stop Jarvis normally, set `enabled` to `false`, and restart. Keep `projects.sqlite3`. The parse rules then return "Project intelligence is off" for project starts and project-scoped restrictions; everything else routes as before.

## Dated verification (2026-10-24 IST)

[Evidence index](../artifacts/project-intelligence/README.md). The tests use the real `TaskIngress`, scheduler, workflow graph and `DecisionManager`, temporary project roots and a **fake coding agent** that writes files. One test drives real `Actions` with its ingress and action worker threads through the conversation; only `code_task` is a fixture there. **The real coding agent, live voice, the native UI on screen, account connectors and a real overnight run were not exercised.**

- [`tests/test_project_intel.py`](../tests/test_project_intel.py): **48 passed**. They cover:
  - vague start, minimal questions, safe default destination, no files without a destination, no overwrite;
  - ambiguous and read-only references, with reference tampering detected;
  - DAG in one group, safe work during a pending 20-second choice;
  - in-place updates without duplicates, add/modify/revert/remove;
  - explicit conflicts held and resolved, inferences superseded, running incompatible work paused;
  - stale-task refusal, priority (immediate and deferred), multiple projects and groups;
  - bounded diagnostic retries then blocked; questions while a task runs; restart continuity;
  - traceability, verification and report;
  - unseen project types and injected text staying as data;
  - proactive gaps sent to awareness; disabled mode; the native Mind-view strip; the real-Actions end-to-end run.
- The first focused run after integration had **4 failures** in the 800-scenario intent testbook. "Create a new branch …" was being taken as a project start, and "never delete file notes" stopped being a no-op. Both rules were narrowed; that receipt is kept, and the testbook now passes.
- **A real defect in the previous awareness change was found and fixed here.** `Actions._submit` assigned `cognition` only for user-originated commands, so any generated `code_task` failed at admission. The awareness investigations had used a different path.
- Complete suite on the final code: **4,189 passed / 150 gated skips / 0 failures** in 18 m 24 s ([receipt](../artifacts/project-intelligence/full-regression.txt)).
- Launcher: **ready** ([receipt](../artifacts/project-intelligence/launcher-check.txt)).

[Benchmark](../artifacts/project-intelligence/benchmark.json) (`python scripts/project_intel_benchmark.py`, temporary roots, home search off):

| Measurement | Result |
|---|---|
| Acceptance conversation per utterance | 2–46 ms, except the objective answer at 428 ms (first plan and inference) |
| 40 live requirement additions (plan growing to 49 tasks), median / p95 / max | 22.9 / 28.3 / 38.1 ms |
| Status questions, median / p95 | 7.9 / 13.2 ms |
| Read-only reference snapshot, 2,000 files | 1.15 s |

With `search_home` on, resolving "my Projects folder" also lists your home and Documents folders. That took ~0.9 s once on this PC. All of this runs on the ingress thread, never the microphone or UI thread.

## Acceptance scenario status

The full scenario in the request runs end to end in tests, through the real queue and real `Actions` threads, with a fake coder:

- discovery questions;
- registration with read-only reference and destination;
- inferred requirements;
- plan → tasks;
- battery, futuristic UI and no-cloud updates;
- overnight;
- the report.

Not verified: real code quality from the coding agent, whether a real build passes, a network-disabled runtime test of "offline", battery behavior, and an actual overnight run.

## Limitations and open gates

- Classification is pattern-based. Unusual phrasing may fall through to ordinary conversation, and Jarvis asks only when two requirements are equally related. Pronouns other than "that feature/module" are not resolved.
- Conflict detection relies on concept families (network, interface, power, performance, storage, testing, security, documentation) plus shared words. It is not semantic understanding.
- Functional "verification" here is static keyword evidence or the presence of test files. Behavioral verification needs a test task that runs the tests (subject to existing approvals), and the system reports this honestly as "implemented, not verified".
- Removal of already-implemented features is planned as a follow-up coding task, not an automatic rollback.
- Pause, resume and verification rely on the coding agent honouring cooperative cancellation.
- Live voice/UI and real-agent acceptance have not been run, and no screenshot of the project strip exists.
