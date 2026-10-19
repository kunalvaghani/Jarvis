# Phase 6 — Controlled self-evolution: design, provenance and safety model

Date 2026-10-19 IST. Branch `claude`. No Codex review evidence exists for this phase.

## Pre-upgrade inspection (verified from source)

| Item | Finding |
| --- | --- |
| Existing self-evolution | `self_evolution.py`: idle `SelfEvolution` (gap detection → repository learning), `skill_maintenance` (Phase 3), `memory_maintenance` (Phase 4) and `SafeEvolutionManager` (propose → test → approve → deploy/rollback for one source file). `SafeEvolutionManager.evaluate` adds a **detached worktree inside the active repository**. It is left unchanged (no caller starts it automatically); the new Pillar C path never creates worktrees or branches in the active repository. |
| Canonical source repository | `D:\Kunals GitHub Repo\Jarvis` (Git top level; app under `app/`). `LocalGithub` is a **separate** repository (`brain.localgithub_path`, used by `codex_workload` for assembly) and is not the Jarvis source. |
| Mutation targets | Hard-coded constants in `cognition.py` (salience/decay), `capabilities.py` (ranking boosts), `reasoning_bank.py` (retrieval weights), `task_recovery.py` (read-retry backoff), and DAG ready-step admission in `dag_execution.py` (plan order only, no critical-path awareness). `brain.py` itself stays out of scope; its DAG executor heuristic lives in `dag_execution.py`. |
| Approvals | `Actions._approve(kind, detail, cancelled)` → `main.request_approval` → Dynamic Island approval card. Reused unchanged for `evolution_promotion` and `evolution_rollback`. |
| GPU scheduler / launcher / recovery | Not mutation targets (protected). Candidate work runs at below-normal priority and only while `SelfEvolution` reports idle with free resources. |
| Baseline | [metrics-before.json](metrics-before.json) on clean `b909e92`; related suites 257 passed / 4 skipped ([log](pre-upgrade-relevant.log)). The preflight suite ran while the first behaviour-preserving surface edits were being made; the clean baseline is the metrics file. |
| Previous-phase defects | None open from Phases 1–5. |

## Upstream study (what was adopted and what was redesigned)

| Upstream | Licence | Adopted | Redesigned for Jarvis |
| --- | --- | --- | --- |
| Darwin Gödel Machine, `jennyzzt/dgm` (arXiv 2505.22954) | Apache-2.0 | Open-ended archive; parent selection `score_child_prop` = sigmoid(10·(score−0.5)) × 1/(1+children); per-generation checkpoint and resume (`continue_from`); staged evaluation (cheap subset first) | DGM lets a coding agent rewrite its own code with frontier-model APIs, evaluated on SWE-bench/Polyglot inside Docker. Here candidates are **bounded literal mutations** of declared surfaces, the archive is SQLite, and evaluation is the sealed multi-domain gate. No DGM code copied. |
| `karpathy/autoresearch` | MIT | One idea per experiment; fixed budget; `prepare.py`/`evaluate_bpb` read-only; `results.tsv` log; keep/discard; crash → log and move on; timeouts kill the run | Keep/discard happens in a separate lab repository (never `git reset` on a user branch); hypotheses are stated and falsifiable; the metric is a held-out paired comparison, not one run. No code copied. |
| EEVEE, `Princeton-AI2-Lab/EEVEE` (arXiv 2606.11182) | Apache-2.0 | Router + K prompt slots; alternating router/prompt phases; half of the training partition as validation; annealed router objective (balance → accuracy); per-example Pareto front of prompts; empty-prompt floor; reflection on failures | Router is a deterministic weighted keyword classifier (microseconds, reproducible) instead of an LLM router prompt; deterministic voice commands bypass routing; slot prompts start empty and only reach the planner after gate + approval; guidance is advisory text and is separate from security rules. No code copied. |

## Architecture

```
production (read-only for experiments)          isolated lab (.jarvis-runtime/evolution/lab/repo)
 jarvis/*.py ──git archive (read)──────────────► baseline/<commit>  ── cand/<id> commits (one per candidate)
 evolution_eval/ (sealed, never exported)              │ detached worktrees per evaluation (removed after)
        │                                              ▼
        └──── RetentionGate (runs from production) ── parent tree vs child tree
                    │ seal check → integrity → target paired benchmark → 10 domain suites → other benchmarks → post-integrity
                    ▼
 archive.sqlite3 (lineage, fitness, gate report, environment) + results.tsv
                    │ qualified → proposal only
                    ▼
 EvolutionPromotion: approval card → release snapshot → literal patch → staged health checks → auto-rollback
                     independent rollback: python -m jarvis.evolution_promotion rollback <release>
```

### Mutation surfaces (`jarvis/evolution_surfaces.py`)

| Surface | File / symbol | Domain | Held-out benchmark |
| --- | --- | --- | --- |
| `dag_scheduling` | `dag_execution.SCHEDULING` | DAG planning | `dag_makespan` (real Executor, sleeping tools; ms, lower is better; 5 repeats) |
| `tool_ranking` | `capabilities.RANKING` | Skill/MCP registry | `tool_selection` (real `ToolRegistry.search`, reciprocal rank) |
| `lesson_retrieval` | `reasoning_bank.RETRIEVAL` | Memory | `lesson_retrieval` (ReasoningBank precision@1, lexical path) |
| `percept_salience` | `cognition.SALIENCE` | Voice/cognition | `salience_retention` |
| `read_retry_backoff` | `task_recovery.BACKOFF` | Recovery | `retry_recovery` (simulated time) |
| `prompt_router` | `prompt_router.ROUTER` | Prompt routing | `prompt_routing` |
| `prompt_slots` | `prompt_router.SLOT_PROMPTS` | Prompt routing | `prompt_slots` (local Ollama model, temperature 0, seed 7) |

Defaults equal the previous hard-coded values, so production behaviour is unchanged (verified by the existing suites
and `test_P06_production_surfaces_match_modules_and_evaluator_policy`). Retry **attempt bounds**, the read-only
requirement, effect serialization and verification are policy and are not part of any surface.

**Protected (never surfaces):** tests, config, requirements, `evolution_eval/`, security/credential/permission/approval/
auth/token code, `cloud_policy`, `cloud_architect`, the evolution machinery itself, `self_evolution`, `tools.py`,
toolkits, `actions.py`, launcher, `recovery.py`, `gpu_scheduler`, `deliberation`. Prompt text is ASCII, at most 600
characters, and refused if it tries to widen authority (ignore/bypass approval or safety, auto-approve, credentials).

### Candidate validity is checked twice, independently

1. The mutation worker (`render` / `verify_bounded`) only writes the surface literal and checks the syntax tree.
2. The gate re-implements the rule (`literal_only_change`) with the **evaluator's own bounds** from `policy.json`,
   compares every file hash of child vs parent tree (exactly one changed file allowed) and re-hashes the child tree
   after its tests ran.

Nothing is imported from a candidate before both checks pass. The lab is **not** a hostile-code sandbox; it is safe
because a candidate can only be a set of in-bound literal values.

### Retention gate policy (`evolution_eval/policy.json`, sealed)

* **Seal:** every evaluator file must equal its committed blob (same line-ending conversion as a commit); otherwise
  the gate refuses to evaluate. Thresholds, held-out data, benchmarks and domain lists therefore cannot be changed
  by a candidate or by an uncommitted edit.
* **Target:** paired comparison child vs parent on held-out cases, interleaved repeats (≥2; 5 for timing), seeded
  percentile bootstrap (2,000 resamples). Qualifies only if relative improvement ≥ 2 % **and** the 95 % CI lower bound
  is > 0; also required against the approved baseline when the parent is not the baseline.
* **Ten domain suites** (voice routing, privacy/cloud isolation [security, hard PASS → quarantine on failure],
  DAG planning, coding/files, desktop UIA/browser, skill/MCP registry, memory, recovery/idempotency, CPU/RAM/VRAM
  scheduling, integrations/backward compatibility) must all pass. Three environment-bound tests are deselected in the
  lab with recorded reasons (sibling LocalGithub checkout ×2, production `.venv` path, git-ignored Hermes install);
  they still run in the production full regression.
* **Other benchmarks:** a regression > 2 % with a CI entirely below zero rejects the candidate.
* **Limits:** each child process has wall-time and memory caps (benchmarks 2 GB, tests 4 GB) and runs at below-normal
  priority with a minimal environment (no credentials). Exceeding memory → quarantine; timeout → reject;
  cancellation → interrupted.

### Promotion and rollback

Qualified → proposal. `evolution_promote` (ToolRegistry, `approval: user`, never replayed) requires: an approval
card, an unchanged evaluator seal, production `HEAD` equal to the evaluated source commit, and the production surface
at its approved baseline values. It writes a release snapshot (original bytes, hashes, known-good commit), replaces
only the literal, then runs staged health checks (import readback, target-domain suite, privacy suite). Any failure
restores the snapshot automatically. Rollback (`evolution_rollback` or the CLI) refuses to overwrite a file edited
after deployment. Changes take effect after Jarvis restarts.

## Safety findings

| ID | Finding | Status |
| --- | --- | --- |
| S1 | Candidate cannot modify tests, evaluator, policy, held-out data, permissions or config: excluded from the lab, outside the surface, and detected by tree-hash comparison | PASS (tests) |
| S2 | Malicious code (extra statements, function-call values, non-literal edits) is rejected before execution | PASS (tests) |
| S3 | Tampering with the evaluator (policy edit, held-out edit, extra file) makes the gate refuse | PASS (tests) |
| S4 | Resource-exhausting candidate killed and quarantined; nondeterministic candidate cannot qualify | PASS (tests) |
| S5 | Active repository: no branch, worktree, ref or file created by experiments (checked on the fixture and on the real repository) | PASS (tests and real run) |
| S6 | Promotion without approval writes nothing; failed health check restores the snapshot; rollback refuses to overwrite later edits | PASS (tests) |
| F1 | The gate's seal initially ran git without the system config, so CRLF working files looked modified. Fixed: read-only seal queries use the repository's own conversion. | Fixed (`40278f9`) |
| F2 | Lab snapshots initially differed from the production checkout (mixed LF/CRLF working tree; a pinned catalog hash). Fixed: unchanged files take production bytes. | Fixed before commit |
| L1 | `SafeEvolutionManager.evaluate` (pre-existing) still uses detached worktrees in the active repository when explicitly invoked | Documented; not used by Pillar C |
