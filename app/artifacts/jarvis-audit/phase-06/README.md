# Upgrade Phase 6 of 8 — DGM + autoresearch + EEVEE controlled self-evolution

Date 2026-10-19 IST. Branch `claude` (commits in [commit.txt](commit.txt)). `main` was not modified.
No Codex review evidence exists for this phase.

**Verdict: PASS for every locally executable check. One candidate qualified as a proposal and is not deployed
(deployment needs the user's approval card).**

## What changed

| Part | Where | Summary |
| --- | --- | --- |
| Mutation surfaces | [`jarvis/evolution_surfaces.py`](../../../jarvis/evolution_surfaces.py) and named dict literals in `dag_execution`, `capabilities`, `reasoning_bank`, `cognition`, `task_recovery`, `prompt_router` | Seven bounded literal-only surfaces; defaults equal the previous constants. Protected sources can never be targeted. |
| A. DGM archive | [`jarvis/evolution_archive.py`](../../../jarvis/evolution_archive.py) | SQLite archive with lineage, mutation type and files, source and lab commits, values, fitness, gate report, failure reason, diversity, seed and environment. `score_child_prop` parent selection, Pareto retention of neutral non-winners, run checkpoints and crash recovery. |
| Lab isolation | [`jarvis/evolution_lab.py`](../../../jarvis/evolution_lab.py) | Separate Git repository; the canonical repository is only read (`rev-parse`, `archive`). `cand/<id>` branches and detached worktrees exist only in the lab. |
| B. Autoresearch | [`jarvis/autoresearch.py`](../../../jarvis/autoresearch.py) | The 10-step loop: evidence → bottleneck → parent → falsifiable hypothesis → bounded mutation → static checks and domain unit tests → fixed-budget train pre-screen → sealed gate → results.tsv/archive → keep or discard. Idle hook in `SelfEvolution.research_maintenance` (≤1 per day). |
| C. EEVEE | [`jarvis/prompt_router.py`](../../../jarvis/prompt_router.py), [`jarvis/prompt_evolution.py`](../../../jarvis/prompt_evolution.py) | Six task slots; a deterministic router (voice commands bypass it); empty slot prompts by default (no production change). Router and prompt phases with validation halves, annealing, a Pareto front and an empty-prompt floor. |
| D. Retention gate | [`evolution_eval/`](../../../evolution_eval/) (sealed) | Refuses unless its files equal the committed blobs. Runs an independent literal-only check, a paired seeded bootstrap on held-out data, ten domain suites (security is hard PASS), cross-benchmark regression checks, memory and time limits, and post-run tree integrity. |
| E. Promotion | [`jarvis/evolution_promotion.py`](../../../jarvis/evolution_promotion.py) | Tools `evolution_status` / `evolution_promote` / `evolution_rollback`. Promotion needs an approval card, a release snapshot, staged health checks and automatic rollback; the CLI rollback works without Jarvis running. |

Design, upstream provenance and safety model: [design-and-safety.md](design-and-safety.md).
Real experiments: [experiments.md](experiments.md). Rollback and checklist: [rollback-and-codex-checklist.md](rollback-and-codex-checklist.md).
Diff: [source.patch](source.patch), [files-changed.txt](files-changed.txt).

## Results (2026-10-19)

| Check | Result | Classification | Evidence |
| --- | --- | --- | --- |
| Preflight related suites | 257 passed / 4 skipped | PASS | [pre-upgrade-relevant.log](pre-upgrade-relevant.log) |
| Phase 6 tests: archive, ancestry, diversity, isolation (fixture and real repo), simulated improve/regress/test-fail/resource-exhausted/nondeterministic/malicious/evaluator-tampering candidates, recovery, reproducibility, approval, health rollback, stale refusal, independent rollback, EEVEE phases, tools, idle gating | 25 passed / 0 skipped | PASS | [full-regression.xml](full-regression.xml) |
| Full regression | **3,340 passed / 147 skipped / 0 failed** (18 min 37 s) | PASS | [full-regression.log](full-regression.log) |
| `python -m jarvis.launcher --check` | `ready` | PASS | [launcher-check.json](launcher-check.json) |
| Real autoresearch (4 surfaces, 15 candidates, 2 generations) | 1 qualified, others discarded or retained as neutral | PASS (pipeline) | [experiments.md](experiments.md) |
| Real DAG candidate: held-out makespan | 363.3 → 308.1 ms (−15.2 %), 95 % CI [28.8, 81.5] ms; reproduced (−15.1 %) | PASS on synthetic DAGs; real-task benefit NOT RUN | [experiments/candidates.json](experiments/candidates.json) |
| Real EEVEE prompt phase with local models | No prompt beat the empty-prompt floor (4/4) | PASS (pipeline); no improvement | [experiments.md](experiments.md) |
| Active repository untouched by experiments | branches, worktrees and HEAD unchanged | PASS | test + [experiment-log.txt](experiments/experiment-log.txt) |
| Deployment of the qualified proposal | not performed — requires the user's approval | NOT RUN (by design) | — |

## Measurements

Phase 1 harness, [metrics-before.json](metrics-before.json) → [metrics-after.json](metrics-after.json):

| Measure | Before | After |
| --- | --- | --- |
| Intent routing | 2,400/2,400; p50 0.48 ms | 2,400/2,400; p50 0.49 ms |
| Privacy routing | 15/16, 0 private marked public | unchanged |
| DAG execution | success 1.0, p50 12.2 ms | success 1.0, p50 12.5 ms |
| Tool catalog | 94 tools, p50 0.49 ms | 97 tools (+3 evolution tools), p50 0.47 ms |
| Skill context | 20/20 goals, p50 3.38 ms | 20/20, p50 3.34 ms |

Latency differences are within run-to-run noise. Gate cost in the real run: a qualified candidate took 4–5 minutes,
almost all of it in the ten domain suites (each child process stayed at or below ~700 MB RSS). Discarded candidates
took 20–55 s.

## Limitations

- Held-out data for tool selection, lessons, routing, salience and prompt slots is **authored in this phase** (see
  `evolution_eval/generate_data.py`), not mined from user history. Saturated benchmarks (routing, salience) only guard
  against regressions.
- The DAG improvement is measured on synthetic DAGs with sleeping tools; benefit on real Jarvis plans is unmeasured.
- Candidates are bounded literal mutations. Free-form code self-modification (as in DGM) is intentionally not enabled.
- The gate deselects three environment-bound tests inside the lab (reasons are in `policy.json`); the production full
  regression still runs them.
- `SafeEvolutionManager.evaluate` (pre-existing) still adds a detached worktree to the active repository when called
  explicitly; Pillar C does not use it.
- An evaluated proposal applies only to the commit it was evaluated on. After new commits the experiment must be
  re-run (stale proposals are refused).
