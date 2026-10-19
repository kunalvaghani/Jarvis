# Stage 2–3 — Pillar and upgrade verification matrix

Status legend: **VERIFIED** = real code exercised by passing tests or recorded real runs on this machine;
**PARTIAL** = verified with a stated gap; **BLOCKED** = needs hardware, credentials or software not available;
**NOT RUN** = not executed in this upgrade. Test names refer to files in `app/tests/`.

## Pillar A — OpenSpace + Alita (Phase 3)

| Claim | Evidence | Status |
| --- | --- | --- |
| Skill metrics correct and persistent (once per task, retries/crash-safe) | `test_phase03_living_skills.py::test_P03_selection_and_outcomes_are_counted_once_per_task`, `..._failure_cause_and_fallback_are_recorded`, `..._corrupt_store_is_preserved_and_replaced` | VERIFIED |
| Ranking uses validated reliability evidence | `..._ranking_uses_verified_reliability_within_relevant_skills` | VERIFIED |
| CAPTURED / FIX / DERIVED | `..._captured_keeps_only_verified_steps_with_provenance`, `..._fix_repairs_degraded_skill_minimally_and_rolls_back`, DERIVED tests; cross-pillar flow A (`test_phase08_integration.py`) | VERIFIED (FIX/DERIVED text authored by a MOCK model callable; validation is real) |
| Versioning, trust levels, rollback | `..._provisional_becomes_trusted_only_after_independent_verified_uses`, rollback in the FIX test | VERIFIED |
| New MCP adapters generated and validated safely | Phase 3 MCP synthesis tests with Docker `jarvis-mcp-runtime:1` and the official MCP SDK | VERIFIED where Docker is available; otherwise skipped as BLOCKED |
| ToolRegistry remains execution authority | architecture audit tests; every new tool is a `toolkits.TOOLS` entry (inventory regenerated: 120 registry entries) | VERIFIED |
| Previously working skills still function | full regression (bundled skills load: 10, errors 0) | VERIFIED |

## Pillar B — SEAgent + ReasoningBank + OpenViking (Phase 4)

| Claim | Evidence | Status |
| --- | --- | --- |
| Exploration stays inside isolated environments | Phase 4 tests (headless browser on loopback, background Blender sandbox) | VERIFIED; desktop GUI exploration **BLOCKED** (no verified VM, deliberately disabled) |
| App knowledge extracted and reusable | Phase 4 exploration → lessons tests | VERIFIED (sandboxed apps only) |
| Winning strategies and anti-patterns stored | Phase 4 ReasoningBank tests; flow A | VERIFIED |
| Retrieval relevant and scoped | Phase 4 precision@1 0.583 → 0.917 (authored oracle); held-out lexical precision 0.90 (Phase 6 benchmark, re-measured in Phase 8) | VERIFIED with authored oracles |
| Hierarchical indexing works | Phase 4 real OpenViking server tests (`test_P04_vault_index_*`) and the real-vault run (46/49 verified links) | VERIFIED on 2026-10-18; re-run in the final regression when `.venv-openviking` + Ollama are available |
| Obsidian files and memories intact | vault hash before/after real indexing (Phase 4); static write-site check (Phase 8 red team) | VERIFIED |
| Idle exploration does not disrupt tasks | idle gating + preemption tests in `test_self_evolution*.py`, Phase 4 | VERIFIED |

## Pillar C — DGM + autoresearch + EEVEE (Phase 6)

| Claim | Evidence | Status |
| --- | --- | --- |
| Experimental variants isolated | `test_P06_lab_never_touches_the_canonical_repository`, `..._real_repository_snapshot_is_read_only`, flow C | VERIFIED |
| Multiple lineages and fitness persist | archive tests; real run: 4 surfaces, 15 candidates, generation 2 | VERIFIED |
| Mutations bounded and reproducible | surface tests; DAG candidate re-evaluated: −15.18 % → −15.09 %, same decision | VERIFIED |
| Compared against real baselines | paired held-out comparisons vs parent and the approved seed | VERIFIED |
| Gate cannot be modified by a candidate | seal + tree-hash tests; evaluator tampering → refused | VERIFIED |
| Cross-domain regression checks enforced | `test_P06_gate_rejects_cross_domain_benchmark_regression`, domain-test failure rejection; flow C | VERIFIED |
| Approval and rollback | promotion tests (deny writes nothing; health failure auto-rollback; independent rollback refuses later edits) | VERIFIED |
| Production cannot be silently self-modified | promotion requires a card; protected sources; no automatic deploy path | VERIFIED |
| EEVEE router/prompt co-evolution | `test_P06_eevee_*` (SIMULATED solver) and the real local-model run (no prompt beat the empty floor) | PARTIAL: runs offline from the experiment script; the idle loop mutates the router surface only by generic perturbation (D8-2) |

## Pillar D — Absolute Zero (Phase 7)

| Claim | Evidence | Status |
| --- | --- | --- |
| Synthetic problems have valid independent answers | oracle self-checks (400/400 abduction references; deduction from simulation; induction references executed in the sandbox) | VERIFIED |
| Deduction / abduction / induction correct | `test_phase07_azr_training.py` (multiple correct plans accepted, missing dependency / cycle / goal miss rejected) | VERIFIED |
| Rewards reflect verified outcomes | composite reward tests; proposer answer ignored | VERIFIED |
| Unsafe code cannot escape | static screen + container + per-program RLIMIT tests (recursion, 10¹⁰ allocation, C-level loop, file access) | VERIFIED where Docker is available |
| Training and held-out separated | leakage 0 ids / 0 signatures; held-out families unseen | VERIFIED |
| LoRA training and resume | real runs: exact resume (loss diff 0.0), preemption at step 3, main run 9.6 min | VERIFIED on the RTX 3050 (recorded) |
| Candidates benchmarked before promotion | sealed model gate: adapter rejected (latency), merged qualified_experimental; registry experimental | VERIFIED |
| Existing fallbacks and routing compatible | existing PC adapter still loads; no config or endpoint changed; full regression | VERIFIED |
| GGUF/Ollama export | no converter installed | BLOCKED |
| RLVR/GRPO | feasibility probe only (no reward variance) | NOT RUN beyond the probe |

## Additional upgrades

| Upgrade | Evidence | Status |
| --- | --- | --- |
| API/code first, GUI last (Phase 2) | `test_phase02_execution_strategy.py` (real openpyxl/python-docx/pypdf, native Word COM on a temporary copy, background Blender, real UIA fixture, cursor last); flow A | VERIFIED (Excel COM chart fallback and Word COM ran with the installed Office); Unreal: engine manifest read only, editor Python on a project **BLOCKED** (no disposable `.uproject`; Phase 2 finding U1) |
| Method choice by reliability, permissions, cost, fidelity | strategy ranking tests (measured reliability demotion, eligibility reasons, features such as charts/macros/signatures) | VERIFIED |
| Cloud architect escalation (Phase 5 + Phase 8 repair) | privacy adversarial tests (9/9 refused, 0 sent), eligibility tests, sandboxed advice, D8-1 entry-point tests | VERIFIED with a SIMULATED provider; live Groq **BLOCKED** (no authorization for a real call) |
| Show Me Once | real WH_MOUSE_LL hook classification, real UIA capture/replay on the fixture, consent, password/outside/injected filtering, provisional CAPTURED skill | VERIFIED; a physical human click is NOT RUN (UIA Invoke stands in) |
