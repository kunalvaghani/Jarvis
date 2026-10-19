# Phase 6 — Real experiment results (2026-10-19 IST)

Driver: [`scripts/verification/phase06_evolution_experiments.py`](../../../scripts/verification/phase06_evolution_experiments.py)
on canonical commit `314fad5`, evaluator seal `a57e489b…` (full values in
[experiments/experiment-record.json](experiments/experiment-record.json)). Raw evidence: every candidate with its gate
report ([candidates.json](experiments/candidates.json)), lineage ([lineage.json](experiments/lineage.json)),
the autoresearch log ([results.tsv](experiments/results.tsv)) and the run log ([experiment-log.txt](experiments/experiment-log.txt)).
Total wall time 17 min. Nothing was deployed: the qualified candidate remains a proposal awaiting user approval.

## 1–2. Evidence and bottleneck (train split, production code)

| Surface | Train score | Headroom | Priority |
| --- | --- | --- | --- |
| read_retry_backoff | 0.470 success-speed | 0.53 | 0.53 |
| tool_ranking | 0.490 MRR | 0.51 | 0.51 |
| dag_scheduling | 309.6 ms makespan | 0.34 (vs. critical-path bound) | 0.34 |
| lesson_retrieval | 0.90 precision@1 | 0.10 | 0.10 |
| percept_salience | 1.00 | 0 | 0 |
| prompt_router | 1.00 | 0 | 0 |

No verified tool-outcome failures were present in the local agent events, so every failure weight was 1.0.
The saturated benchmarks (salience, routing) were used only as regression guards. Their labels are authored by
this phase, so a perfect score is not evidence of real-world routing quality.

## 3–10. Experiments

| Surface | Candidate (gen) | Change | Train parent → child | Held-out gate | Decision |
| --- | --- | --- | --- | --- | --- |
| dag_scheduling | `cand_dc72ef14b5a0` (1) | critical_path_weight 0 → 1.0 | 308.9 → 245.8 ms | makespan **363.3 → 308.1 ms (−15.2 %)**, 95 % CI of improvement [28.8, 81.5] ms, 12 DAGs × 5 interleaved repeats, 9 better / 3 worse; 10/10 domain suites passed; 5 other benchmarks unchanged (Δ 0, CI [0, 0]) | **qualified → proposal** |
| dag_scheduling | `cand_15d249712dee` (2, parent `dc72…`) | weight 1.0 → 1.5 | 246.6 → 246.9 ms | not run (pre-screen) | discarded |
| tool_ranking | 4 candidates (gen 1–2) | route_step_cap 5→6, exact_name_bonus 20→23.5, route_boost 8→5.2, skill_tool_boost 5→7.4 | 0.490 → ≤ 0.490 | not run (pre-screen) | 1 discarded, 3 retained (neutral, non-dominated) |
| read_retry_backoff | `cand_43c3c385cbb5` (1) | max_seconds 1.0 → 0.51 | 0.470 → 0.475 | +0.68 %, CI [0.0, 0.0085] (below the 2 % minimum) | discarded (retained as neutral variant) |
| read_retry_backoff | 3 candidates (gen 2) | base 0.1→0.01, max 0.51→0.1 / 0.265 | no gain | not run | discarded |
| lesson_retrieval | 2 candidates (gen 1–2) | age_cap 0.2→0.25, age_days 365→727 | 0.90 → 0.90 | not run | retained (neutral) |
| prompt_router (EEVEE router phase) | — | 12 mutations | validation accuracy already 1.0 | — | no change accepted |
| prompt_slots (EEVEE prompt phase, slot tool_selection) | — | 3 reflections by local `qwen3.5:4b`, solver `qwen3.5:0.8b` (temperature 0, seed 7) | reflected prompt 2/4 vs empty-prompt floor **4/4** on validation | — | no prompt beat the floor; nothing submitted |

**Only the DAG hypothesis is supported by evidence.** Admitting ready steps with longer downstream chains first
shortened held-out makespan by 15 % on synthetic DAGs with sleeping tools. The hypothesis is *not* shown to help
real Jarvis tasks: real plans are short and mostly sequential, so their benefit has not been measured. The other
hypotheses were falsified or not supported and are recorded as such. "Retained" means a neutral variant that is
non-dominated on train score and stays eligible as a parent (DGM keeps non-winning variants); it is not an improvement.

## Reproducibility

The qualified candidate was re-evaluated from its immutable lab commit: decision **qualified** again; relative
improvement 15.18 % → 15.09 %, CI [28.8, 81.5] → [28.4, 81.4] ms. Seeds (`rng_seed` per candidate, bootstrap seed
1729) and the environment (Python 3.10.6, Windows 10.0.26200, 16 CPUs) are stored with each candidate.

## Isolation evidence

After the run, the active repository still had only its original branches (`claude`, `codex`, `main`) and one
worktree. Its status was unchanged apart from the new packet files. The lab repository held `baseline/314fad5a8821`
plus 12 `cand/<id>` branches. Production `jarvis/dag_execution.py` still has `critical_path_weight: 0.0`.

## How to deploy the proposal (user decision)

Ask Jarvis to "review improvement proposals" (`evolution_status`), then "deploy the improvement proposal
cand_dc72ef14b5a0" (`evolution_promote`, shows an approval card). Deployment is refused unless production `HEAD` is
the evaluated commit `314fad5`. After later commits, re-run the experiment first (by design, nothing evaluated on an
older release is applied to a newer one).
