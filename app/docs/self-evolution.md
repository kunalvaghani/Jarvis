# Self-evolution engine — autonomous idle learning & capability expansion

2026-10-15 IST resource follow-up: optional idle learning now defers when psutil or
a RAM/CPU/battery reading fails. Its existing idle, user-busy and configured
threshold gates still apply. This avoids treating unknown capacity as permission
to start background work. [Executed resource checks](../artifacts/jarvis-audit/modules/08-gpu-scheduler/inventory.md).

Jarvis improves itself while idle: it detects its own weaknesses, discovers and learns relevant
GitHub repositories, lets the ability forge turn them into new tested commands, remembers everything,
and — when you authorize it — can even patch its own source under strict gates. It is the
orchestration brain that closes the loop **Discover → Analyze → Learn → Integrate → Remember →
Repeat**, built on the subsystems Jarvis already has rather than duplicating them.

## What is reused vs. what is new

Most of the pipeline already existed and is **reused, not rebuilt**:

- **Discovery / analysis** — `repo_learning.py` (`RepoLearner`: GitHub search/learn, Obsidian
  `Jarvis Repos/`, offline cache), `repo_analysis.py`, `repo_acquisition.py`.
- **Capability extraction → tested commands** — `repo_abilities.py` (`AbilityForge`): a learned repo
  is automatically broken into abilities, generated as `ability.py`, statically checked, tested in a
  per-ability virtualenv, and proposed for registry activation. Standard-library abilities are
  self-tested before the activation approval; third-party/network installation waits for approval.
  Every activation requires approval, and built-in commands win. This host subprocess uses
  Python audit hooks, rather than the Docker kernel isolation used for repository skills;
  [the 2026-10-14 audit](../artifacts/jarvis-audit/security-findings.md) records the remaining boundary.
- **Idle detection style + resources** — `anticipation.py`, `gpu_scheduler.py`.
- **Memory** — Obsidian via `obsidian_memory.py` / `skill_memory.py`.
- **Notifications** — the Dynamic Island (`media_card`), with a dedicated **"Learning"** card.
- **Opinions / risk** — `deliberation.py`.

New in `jarvis/self_evolution.py`:

1. **CapabilityGapDetector** — read-only mining of Jarvis's own records into evidence-backed gaps:
   unreliable action kinds from `cognition.stats`, failed strategies from the deliberation ledger, and
   repeated user requests. It never fabricates a gap.
2. **Improvement backlog** — a persistent, scored, crash-safe queue at
   `.jarvis-runtime/self-evolution/backlog.json` (atomic writes, deduped against already-learned
   repositories, mirrored to an Obsidian *Improvement Backlog* note). Score =
   `usefulness + reuse + performance + relevance − cost − risk` (weights configurable).
3. **SelfEvolution orchestrator** — an owned idle thread that pops the top item, synthesizes a
   discovery query, drives `RepoLearner.search`/`learn` (the forge then auto-builds), records the
   outcome, and shows an island card. Each step checkpoints to disk and is resumable.
4. **SafeEvolutionManager** — gated self-modification of Jarvis's own source.

## What you see on the Dynamic Island

When the engine enters learning mode, the island shows a small animated **Learning** card
(service `evolve`, a pulsing node-and-spokes tile in teal) telling you it is learning **and what**:

- `Learning: <skill>` — *Finding a skill to learn* → *Reading the project* (while it studies, up to a
  15-minute window).
- `Learned: <skill>` — *Building a new capability* (when a repository is understood and the forge
  starts turning it into a command).
- `Learning paused` — *resuming when you're idle* (the moment you give Jarvis a task).

The forge then shows its own card when a new command is actually activated. The card appears from
standby without taking typing focus and disappears on its own; it never interrupts your work.

## When does it actually start? (why idle can look quiet)

The engine is **gap-driven first**: it queues a learning job when `CapabilityGapDetector` finds a real
weakness (a frequently-failing action, a repeated request, a failed deliberated strategy). If there
are no gaps, that part has nothing to do — so a fresh, healthy system can sit idle without learning.

To make a genuinely idle Jarvis keep improving, **exploration** is on by default
(`self_evolution.explore`): when idle with an empty pending backlog, it seeds one topic from
`explore_topics` (Windows automation, speech, local LLM, semantic search, PDF/text tools, …) and
studies it. Real gaps always outrank exploration, exploration respects the daily job cap, and it stops
re-queuing a topic once tried (retried only after the refresh window). Set `explore` to `false` to
learn strictly from detected gaps.

Learning still only begins once **all** idle gates pass, so if you never see it:

- `idle_seconds` (default 90) must elapse since your last command;
- the assistant must not be busy (a task, a pending question, dictation, queued work);
- free RAM must be ≥ `min_available_mb` (default 3072) and CPU ≤ `max_cpu_percent` (default 55) — lower
  these if your machine is constrained and you want it to run more readily;
- the per-day job cap (`max_jobs_per_day`) and `cooldown_seconds` between jobs must allow it.

Any user command calls `note_activity()`, which resets the idle timer and interrupts an in-flight step.

## Idle-only, interruptible, crash-safe

- The orchestrator runs only when **idle** (`idle_seconds` since your last command), **not busy**
  (the shared `anticipation.busy()` signal), and within **RAM/CPU limits** (`min_available_mb`,
  `max_cpu_percent`, via `psutil` when present), respecting a per-job **cooldown** and a
  **daily job cap**.
- Every user command calls `note_activity()`, which preempts and interrupts any in-flight step —
  **your tasks always win**. Heavy work (download, analysis, ability build) runs in the existing
  out-of-process workers, so the idle thread itself holds no model in memory.
- The backlog and a per-job checkpoint are durable and atomic. After a crash or restart, the backlog
  is restored and an interrupted job returns to `pending` to resume on the next idle tick. **Uncertain
  learning writes are never replayed** — the learner and forge own their own idempotent resume.

## Gated self-modification (opt-in)

`SafeEvolutionManager` can change Jarvis's own Python source, but only through a strict pipeline:

**propose → isolate (git worktree) → build → run tests → require explicit approval → deploy with
backup → roll back on regression.**

- `propose(relative, new_source, rationale)` — rejects anything that is not a `jarvis/*.py` file,
  refuses security/permission/approval source outright (`PROTECTED` pattern), and rejects source that
  does not even parse.
- `evaluate(pid)` — checks out the repo in an isolated worktree, applies the patch, and runs the test
  suite there (paths resolved relative to the git root, so a subdirectory `base` works). Deploys
  nothing.
- `deploy(pid)` — only for a patch whose tests passed, and only after `Actions._approve` grants it;
  keeps a timestamped backup.
- `rollback(pid)` — restores the backup.

Defaults are conservative: `self_modification.auto_deploy` is **false** (no unattended core deploys),
and the engine never disables its own checks.

## Configuration (`config.json` → `self_evolution`)

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Master switch for the idle engine. |
| `idle_seconds` | `90` | Quiet time before a learning step may start. |
| `poll_seconds` | `5.0` | Idle-thread tick. |
| `cooldown_seconds` | `600` | Minimum gap between learning jobs. |
| `max_jobs_per_day` | `4` | Daily learning-job cap. |
| `max_backlog` | `200` | Backlog size (rotated). |
| `min_available_mb` | `3072` | Skip learning below this free RAM. |
| `max_cpu_percent` | `55` | Skip learning above this CPU load. |
| `self_modification.enabled` | `true` | Allow proposing core patches. |
| `self_modification.auto_deploy` | `false` | Must stay false; deploys require approval. |

## Continuous learning without retraining

Per the design, "continuous learning" means persistent knowledge, reusable skills/abilities,
registries, decision memory and better routing — **not** retraining the LLM's weights. Jarvis gains
new abilities while the underlying model is unchanged.

## Verification

- Unit/behavioral: `python -m unittest tests.test_self_evolution` — gap detection (and no fabrication
  when empty), backlog scoring/dedup/persistence and crash-safe reload, idle gating and
  preempt-on-activity, the learn job (learns a new repo, skips already-learned, degrades when the
  learner is disabled), and SafeEvolutionManager (protected/non-jarvis/invalid-syntax refusals,
  tests-must-pass, approval-required deploy with backup, and rollback).
- Regression: `tests.test_anticipation`, `tests.test_repo_abilities`, `tests.test_repo_learning`,
  `tests.test_cognition`, `tests.test_deliberation`, then the full suite.
- Readiness: `python -m jarvis.launcher --offline-check`.
- Live: the gated self-modification pipeline was exercised end-to-end against the real git repo
  (propose → isolated-worktree test → approval → deploy → rollback) on a throwaway module. See the
  dated results in [the app README](../README.md#current-validation-and-update-history).

## Honest limits

- The full autonomous idle cycle's network + heavy-model steps (live GitHub learn and the 30B-class
  coder building an ability) are bounded by network and model availability and were not run
  end-to-end in the verification environment; the discover→learn→record orchestration, gap detection,
  backlog persistence/resume and self-modification gates are all verified.
- Background learning consumes real resources while running; the guarantee is preemption and release
  when you return, not zero-cost computation.
- Core self-modification is proposal + approval + rollback only — never autonomous.
