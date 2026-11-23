# Gate A integration plan

2026-11-04 IST. **Reviewable plan; Phase A remains partial. Phase B is not authorized by a passed Gate A yet.** The [master prompt](../specs/MASTER_BUILD_PROMPT.md) explicitly requires stopping at Gate A unless `MODE: AUTONOMOUS` is set; it was not set. The later instruction to continue the audit and mostly create new files is recorded here and does not waive that gate.

## One-page decision summary

Jarvis already owns the difficult infrastructure: voice/text ingress, legacy planner and optional BNEG brain, typed registry/graph, tool dispatcher, scoped approvals, durable scheduler/checkpoints, memory/procedure history, model/cloud routing, GPU admission and Island notifications. **Reuse all of it.** Add domain logic under `app/jarvis/discovery/`, new namespaced discovery skills, new tests/golden fixtures and migrations in the existing memory owner. No second planner, executable registry, memory database, task queue, GPU scheduler, approval system or notification service.

Fresh source snapshot: 306 neurons / 426 synapses; every one of 148 ToolSpecs registered; 91 configured MCP tools; 203 optional Blender catalog actions lack individual neurons. Existing scientific libraries: Pydantic/rustworkx/NumPy/SciPy/SymPy. Core .venv lacks pint, MuJoCo, PyChrono, PyVista, Optuna, paper-qa, CadQuery and cocotb; this is not a whole-machine absence claim. BNEG mode and memory facade flags are off. Six earlier approved speed/control flags are on and must stay as configured.

Three main architectural resolutions are proposed:

1. **Brain:** use `jarvis/neural`, not a new `jarvis/brain/` package. Keep current activation states and port validation; add optional scientific verification/intents/golden/model metadata. Add domain neuron sources/workflow hooks under the current Registry and compiler. No silent production brain activation.
2. **Memory:** add a facade over existing memory ownership, with a reversible scientific-schema extension in the existing ReasoningBank database if scratch migration/retrieval tests confirm fit. Its internal `_add` is not a safe generic public graph API. Keep scientific evidence separate from personal facts and retain IDs back to source/project/procedure/journal records. No live migration until validated; no replacement of existing stores.
3. **Blender/skills:** retain the **custom Jarvis connector** and fast modelling paths. Neither upstream Blender MCP server is a replacement target. Existing 203-tool activation remains approval-gated. Extend SkillMemory only enough to discover explicitly namespaced discovery skills; preserve its identity/size/security checks and existing roots.

Other conflicts: fixed DATA_TYPES / extra=forbid schemas; semantic relation names vs existing edge modes; strict old MCP handshake vs new stateless/Tasks path; null unknown mass vs the spec's example zero; and read-only Phase A vs a mutating live baseline. Resolve them with additive typed metadata, wrappers, and explicit baseline scopes, not relaxed checks. Propose **golden pass + three independent code-checked successful uses** before VERIFIED; failed golden creates only a LearningEpisode, never an executable neuron. See the [full matrix](MAPPING_MATRIX.md).

Verification so far: **72 existing isolated tests pass**. The earlier over-restricted run's failures are retained as harness/environment limitations. Full regression, live accuracy/latency, loaded-model VRAM, protocol health and scientific acceptance are **not run**. Audit-only docs do not establish release acceptance. There is no observed running Jarvis engine to diagnose as hung; stale heartbeat/stop state was preserved.

## Ordered work after Gate A

| Order | Work / new files | Reuse | Evidence required before proceeding |
|---|---|---|---|
| 1 | Finish compatibility-safe full baseline and live benchmark scope; capture exact revision/config and private-safe receipts | Existing tests, runner, oracle suite, owned test roots, account approvals | Separate prior failures, harness limitations and live accuracy/mean task time; preserve campaign pause |
| 2 | discovery/contracts.py, model/units.py, provenance.py, uncertainty.py; default-off Lab flags | Pydantic; pint only in reviewed isolated dependency plan | Units/nulls/ranges/source hashes and strict enums; all flags-off behavior checked |
| 3 | discovery/memory.py and migrations.py against isolated existing-store copy | Existing memory transactions/source/skill IDs; no new DB | Backward-compatible migration, idempotence, rollback, typed retrieval and secret rejection |
| 4 | discovery/neurons/* and metadata adapter, model_hints.py | Registry/Neuron/Synapse/Router/compiler; cloud policy | Dummy neuron fires only with Lab opt-in; off never activates; no dangling dependencies |
| 5 | discovery/golden.py, learning.py, sandbox/env_manager.py, policy.py, budget.py | Acquisition/RepositorySkills/SkillStore/ReasoningBank; existing isolation and GPU/cloud admission | Deterministic golden failure/success records, no failed-neuron registration, bounded/no-network execution, retained failures |
| 6 | One real small-tool learning vertical slice and skill | Existing text ingress, brain path, memory writes, notifications | Research/license/version → authorized isolated environment → actual golden → LEARNED_UNVERIFIED; later N uses → VERIFIED; fresh-session reuse measured |
| 7 | model/component_graph.py, parameter_registry.py, identity and asset adapters | rustworkx, file/project/source search, existing Blender | Local-file-first sourcing, licensing/variant hard rejects, hash cache; stable visual/functional/physical IDs; affected-only invalidation |
| 8 | New CAD/meshing/mechanics/electronics/visualization adapters with native source and skills | Existing custom Blender, ControlService, scoped approvals | Actual installed-tool golden outputs, cancellation, independent file readback; no image/animation as physics |
| 9 | Literature adapters, hypothesis tournament/skeptic, theory and bounded optimization jobs | Existing research/model router, scheduler/queue, event and artifact paths | Citation/contradiction checks; no LLM numbers; immutable scenario, reviewed evaluator, budget stop/resume evidence |
| 10 | New vehicle/active-aero and circuit/logic scenarios; scientific UI | Existing Island/viewer/report path and job state | A1/A2/B/C/D/E/F/G/H through Jarvis; rubric >=90 only after evidence; G/H mandatory |

The master prompt's phase ordering controls: do not skip foundations to manufacture an F1 demo. No install is currently performed or pre-approved by this document. The master prompt is stricter than spec §11.2 on installation; obtain authorization for concrete package/download plans before those actions.

## Possible existing-file modifications, not yet performed

`flags.py` and `config_contract.py` for registered default-off Lab flags; `config/config.json` only for explicit off defaults if required. `neural/contracts.py` for missing strict types/optional metadata; `neural/registry.py`/`service.py` for a minimal discovery-source hook; `neural/compiler.py`/`adapters.py` only for actual opt-in routing. `reasoning_bank.py` for a public migration/typed-record seam if needed. `skill_memory.py` for the namespaced root. Existing requirements/runtime manifest only for actual approved new dependencies or owned services. Existing model/scheduler/UI registration hooks only if wrappers cannot reach them. Every unavoidable edit must first gain a reason, before/after checks and rollback entry in [MODIFICATIONS](MODIFICATIONS.md).

No changes planned to Start/Stop Jarvis, bootstrap, launcher or recovery unless a reproducible incompatibility appears. Compatibility and `python -m jarvis.launcher --check` remain mandatory for actual app upgrades. No new always-on Lab service or MCP server is proposed.

## Dependency plan and resource limits

Use existing versions of Pydantic/rustworkx/NumPy/SciPy/SymPy. Pin new per-tool environments to validated targets from §5.9: Blender 5.2 LTS (discover actual version first), FreeCAD 1.1.x, MuJoCo 3.12 CPU, PyChrono 10, FastF1 3.8.x, KiCad 10 plus ngspice, Verilator >=5.036 plus cocotb 2.x; PaperQA gets a verified canonical CalVer pin. CadQuery/Gmsh/PyVista/pint/Optuna versions are **TBD after official docs, Windows/license and golden compatibility checks**, not guessed. No existing dependency upgrade is justified by this audit.

uv/pixi/conda are not on this shell's PATH. Discover existing environment tools before proposing an installation. WSL listing is access-denied; do not assume absent or install a distro. A venv is dependency isolation, not containment for untrusted code: use the existing sandbox/ownership mechanisms and establish OS/process network/CPU limits before generated scripts run.

Local CPU is default. Before any GPU step, use the existing GPU scheduler and measured admission; capture offload/CPU/remote decision. No driver changes, heavyweight reconstruction/training or remote GPU calls. Daily paid budget **$0**; OpenAlex free allowance must be metered and stop before prepaid drawdown. Cross-session/global key usage and uncertain failed requests must remain charged. Never place keys in logs/memory. No hardware actuation, orders, fabrication, firmware or physical experiments.

## Open decisions and gates

| Decision / gate | Proposed safe default | Status |
|---|---|---|
| Gate A plan approval | Keep audit docs; begin only additive foundations after review | Awaiting user review per master prompt |
| Single-memory schema owner | Existing ReasoningBank owner behind facade, proven on isolated copies | Architectural proposal, not approved migration |
| Learning promotion N | 3 code-checked independent uses after golden | Proposed; never promote on LLM judgment |
| §19.19(a) Blender standard | Retain custom Jarvis connector; evaluate upstream only if a concrete gap remains | No replacement/activation requested now |
| §19.19(b) API budget | $0 paid; free allowances only, metered | Default from master prompt |
| §19.19(c) remote GPU | None; no provider/monthly allowance configured | Deferred, approval required if needed |
| §19.19(d) separate Windows user | Review sandbox ownership options before enabling Lab-driven GUI execution | No account creation/privilege changes |
| §19.19(e) Semantic Scholar key | Cached unauthenticated mode | Institutional key application deferred |
| Full read-only baseline contradiction | Isolated suite review plus separately scoped live window | Unexecuted; no no-regression certificate |
| Exhaustive unregistered capability coverage | Review source-index candidates and real caller paths | Partial; do not register helpers by name |

No stable implementation checkpoint or release tag is claimed. Work remains on the user-designated `codex` branch because its existing ref blocks the default `codex/...` branch namespace. No branch was renamed/deleted and no changes published.
