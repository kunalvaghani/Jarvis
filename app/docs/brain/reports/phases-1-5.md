# Brain phases 1–5: implementation report

Date: 2026-11-02. Branch `brain/phase-1-registry`, which holds all five phases. The user asked to "do all testing later after implementing the brain with neurons and everything". This report therefore covers the implementation and its unit evidence; every phase's **live gate is still open**.

## What was built (`app/jarvis/neural/`, 17 modules, mypy clean)

| Module | Role | Brain analogy |
|---|---|---|
| `contracts.py` | `Neuron`, `Synapse` and `Signal` (pydantic); 43 data types; stable ids `kind.name@vN` | neurons, synapses, spikes |
| `catalog.py` | explicit port contracts for 86 neurons, plus a name heuristic for the rest (labelled `derived`) | |
| `registry.py` | live registry: ToolSpec, METHODS, MCP allowlist and live `tools/list`, core neurons; `propose` and `approve` growth | neurogenesis, under rules |
| `graph.py` | sparse typed wiring (rustworkx), versioned snapshots, typed path search, local neighbourhoods | connectome |
| `journal.py` | SQLite WAL: graph versions, proposals, goals, signals, outbox, artifacts, shadow routes, route statistics | hippocampus (episodes) |
| `policy.py` | hard eligibility: status, unknown effects, allowlist, secrets present, privacy, request safety, exfiltration | inhibition (not learnable) |
| `router.py` | deterministic stimulus match (the fixed-route matchers) plus `rank_tools` (reused), then gate, then Beta-Bernoulli preference | basal ganglia |
| `execution.py` | per-goal acyclic plans; repair is the only way back | working memory |
| `dispatcher.py` | event waves; outbox before side effects; idempotency; crash resume; bounded repair; deadline; cancel; desktop lock | motor control |
| `adapters.py` | bridges to existing modules (ToolRegistry, model worker, `fast_routes.grounded`, small_program safety, sealed verifiers) | |
| `compiler.py` | request to plan, by deterministic templates: research, bug fix, exact text file | cortex (simple intents) |
| `learning.py` | verified-only outcomes, off/shadow/on, replay, consolidation into proposed neurons | plasticity |
| `projection.py`, `viewer.py` | Obsidian one-way export; local live neuron view | |
| `service.py`, `__main__.py` | one service per process; shadow and on hooks; CLI | |

Changes to existing files are kept small:
- `Actions.execute` now wraps the old body, renamed `_execute_audited`, with the brain hooks.
- `ToolRegistry.execute` records the tool name for the shadow log.
- `cases.py` gains `--brain` and writes each oracle's verdict to the journal.
- With `neural.mode` `off` (as shipped), the hooks return at once and nothing is built.

## Measurements (this PC, the real config)

| Measure | Value |
|---|---|
| Neurons / active / explicit contracts | 267 / 267 / 86 |
| Neurons denied until reviewed (`unknown` side effect) | 8 |
| Synapses: dataflow / feedback / declared conditional | 223 / 5 / 1 (32 two-way pairs) |
| Wired neurons, mean out-degree | 64, 3.58 (sparse: 229 synapses where all-to-all would be 71,022) |
| Registry and graph build | about 0.9 s once per process, CPU only, no model calls |
| Route a request (warm) | 0.4–3 ms; first call about 35 ms (imports) |

## Test evidence

- New tests:
  - `test_neural_registry.py` (28);
  - `test_neural_runtime.py` (19);
  - `test_neural_learning.py` (6);
  - `test_neural_viewer.py` (4);
  - `test_neural_mode.py` (9).
  - **66 passed.**
- They cover every verification-matrix item that can run without live apps:
  - schema validity of every neuron; disallowed MCP tools refused; incompatible bindings and cycles rejected;
  - no auto-wiring into destructive or external writes; feedback only as Verdict repair paths;
  - unknown side effects never eligible; learning never makes a route eligible; secret exfiltration refused for the whole goal; secret-looking outputs never stored or passed on;
  - approval once per scope; a denial writes nothing; patches that touch tests or contain unsafe code refused;
  - folders outside the approved roots refused;
  - repairs bounded, with the verdict fed back; deadline and cancel are stop reasons;
  - crash before a write leaves `uncertain`, with no replay; a crash in a read-only step resumes without re-running finished steps;
  - causal signal order; every lit neuron in the view is a journaled signal; no payloads in the view.
- Two real bugs were found and fixed by these tests:
  - Folder parsing swallowed `calc.py in the calc-bug`; the pattern now tries overlapping matches.
  - After a repair, a downstream check reused its cached result. Idempotency keys now carry the repair generation, and restart replays repairs in order.
- Full regression: see the commit message for the final number. It must equal the Phase 0 baseline of 39 known failures and no new ones.

## Open risks and what the live tests must show

1. **Shadow agreement.** Run `cases.py all --full --brain shadow`, then `python -m jarvis.neural replay`. This shows how often the brain's first choice matches a tool legacy used on verified runs.
2. **On-mode parity.** B07 (bug fix), the research questions and the exact-file cases must pass with `--brain on` at least as often as legacy (baseline 28/90). Other cases must be unchanged, because they fall back to legacy.
3. **Approvals.** On-mode bug fixes ask once through the island card; the live run must confirm the card appears and that "no" writes nothing.
4. **Tool neurons keep legacy approval rules.** Creating a new file has no card, as in legacy. Changing that is the user's decision, so it was not changed.
5. **Coverage.** Only three workflows run in the brain today. The rest is the legacy planner neuron. More templates (Blender wireframe first, then build; browser forms; media) come after the live gates show the slices are sound.

## Go / no-go

Implementation complete for phases 1–5 behind `neural.mode=off`. **No-go for `on` by default** until the live gates above pass. **GO** for the live test round the user asked for.
