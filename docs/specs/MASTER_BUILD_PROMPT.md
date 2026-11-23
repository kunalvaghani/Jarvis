# MASTER BUILD PROMPT — JARVIS Universal Discovery Lab (audit → reuse → build → wire into brain & memory)

> **How to use:** Put the spec file `JARVIS_Universal_Discovery_Lab_v2.md` in the Jarvis repo at `docs/specs/JARVIS_Universal_Discovery_Lab_v2.md`. Then give everything between **BEGIN** and **END** to the coding agent that has the Jarvis repo open (Claude Code or similar). If you want it to run without stopping at the review gates, add this line at the top: `MODE: AUTONOMOUS`. Otherwise it stops at each gate and waits for you.

---

## BEGIN

### 0. Who you are and what you are doing

You are the lead engineer for my **existing** Jarvis, a personal AI assistant running on my Windows 11 PC (Ryzen 7 8-core, 32 GB RAM, RTX 3050 **4 GB VRAM**). Your job is to add the **Universal Discovery, Invention & Simulation Lab** described in `docs/specs/JARVIS_Universal_Discovery_Lab_v2.md` (the "spec").

This is a long, multi-session job. Work in this order and do not skip ahead:

1. **Audit** what Jarvis already has (read-only).
2. **Map** every part of the spec onto what exists.
3. **Build** only what is missing, **reuse** what exists, and **modify existing code only when it is truly needed**.
4. **Wire everything into Jarvis's brain, neurons and memory**, both the new Lab capabilities *and* any existing Jarvis capabilities the audit finds unregistered, so Jarvis can find and use all of it from natural language.
5. **Prove it** with tests, then report honestly.

Read the whole spec before you start. Treat these spec sections as binding: §0 (v2 changes), §1.3 (hard requirements), §4A (brain integration), §5 (verified tool catalog and versions), §11.2 (approvals), §14 (hardware/security/cost), §16 (acceptance tests), §17 (master implementation prompt). Where this prompt and the spec disagree, **this prompt wins**. Where the spec and the real code disagree, **the real code is the truth**: report the mismatch and adapt the plan.

---

### 1. The change policy (apply it to every decision)

Prefer the first option that works, in this order:

| Rank | Action | When | What you must record |
|---|---|---|---|
| 1 | **REUSE as-is** | An existing module already does the job | Which module, and which call/API you used |
| 2 | **WRAP** with a thin adapter in a new file | The capability exists but its interface doesn't fit | Adapter path; the existing code is untouched |
| 3 | **EXTEND** through an existing extension point (registry, plugin folder, config, schema migration, new neuron manifest) | The system was designed to be extended there | Extension point used |
| 4 | **BUILD NEW** in new files/modules | Nothing exists | Why nothing existing fits |
| 5 | **MODIFY existing code** | Only if 1–4 are impossible *or* a real bug or blocker sits in the way | A `MODIFICATION` entry (template §9.3): file, reason, minimal diff, before/after tests |
| 6 | **REPLACE** an existing subsystem | **Never** without my explicit approval | Proposal + rollback plan, then stop and ask |

Rules that follow from this:
- New Lab code lives in **new files**. Every existing file you touch must appear in `docs/lab/MODIFICATIONS.md`.
- Keep a **single** brain, memory, model router, scheduler, approval system and notification path. Do not create parallel versions of any of them, even "temporarily".
- Everything new sits behind **feature flags** (e.g. `LAB_ENABLED`, `LAB_SIM`, `LAB_RESEARCH`, `LAB_LEARNING`). With all flags off, Jarvis must behave exactly as before.
- Do not delete, rename or reformat existing code. Do not "clean up" unrelated things. Do not upgrade dependencies that existing features use unless the audit proves it is required and safe.
- Prior chat descriptions of Jarvis are **context, not proof**. Only trust what you find in the code and what you can run.

---

### 2. Hard constraints (never violate)

- **Hardware:** 4 GB VRAM is shared by the local LLM, the Blender viewport and any GPU solver. Use CPU/local-first tools. Do not run Isaac Sim/Isaac Lab training, TRELLIS.2-class image-to-3D, or GPU-batched MuJoCo Warp/Newton training locally. Before any GPU step, apply VRAM arbitration (spec §4A.6) and log the choice.
- **Money:** no paid API, cloud GPU or paid generation service without my approval. Meter OpenAlex usage (key required; $1/day free allowance) and every coding-agent/LLM call that costs money. Default daily budget: **$0 beyond free tiers** until I set one.
- **Security:** third-party code, downloaded assets, macros, imported skill packs and evolved/generated code run sandboxed: isolated environment, no network unless required, CPU-time cap. Blender and KiCad sockets stay loopback-only. Read every file of a third-party skill pack before importing it. Never store secrets in memory or logs.
- **Physical world:** never order, fabricate, flash firmware, energize hardware or move a robot.
- **Scientific honesty:** no simulation or animation may be presented as physical proof. Every result carries an evidence status (spec §6.2). No number in a result may come from an LLM, only from a solver or deterministic code.
- **Approvals:** follow spec §11.2 (incl. the v2 rows on learning tools and importing skills). Ask before any irreversible or costly action.
- **No regressions:** the existing test suite and the PC-control/browser benchmark (accuracy and average time per task) must not get worse.

---

### 3. Phase A — Audit what already exists (READ-ONLY)

Change no code in this phase. Run the app and tests only in ways that don't modify state.

**3.1 Build a complete inventory.** For each item, record: location (paths), entry points, data formats, how it is called, config, tests, current status (working/partial/broken/unknown), and evidence (the command you ran or the file you read).

| # | Area to audit | What exactly to find |
|---|---|---|
| A1 | Repo map | Top-level structure, languages, package managers, env files, startup path, services/processes |
| A2 | **Neural Execution Brain / capability graph** | Where neurons are defined (code, YAML, DB?), their schema, how routing/activation works, how edges are represented, how a request turns into a neuron path, how new neurons are registered, how unused neurons are pruned, any scoring/learning of edges |
| A3 | **Neurons inventory** | List **every** existing neuron/capability with intents, inputs/outputs, dependencies. Also list capabilities that exist in code but have **no neuron** (tools, scripts, MCP servers, automations Jarvis can't reach through the brain) |
| A4 | **Unified memory** | Stores (DB/vector/graph/files), schemas/node types, ingestion of files/folders → facts with source context, alias/fuzzy name resolution, retrieval API, write API, migrations, retention |
| A5 | Model router | Models available (local via Ollama etc., cloud), routing rules, cost tracking, VRAM handling |
| A6 | PC control & browser | Status of the agent-desktop rework, legacy control path, accuracy/latency benchmark harness |
| A7 | Blender integration | Which MCP server (community *MCP for Blender* / renamed `blender-mcp`, official *Blender Lab* server, or custom), its version, port, safe-mode state; installed Blender version |
| A8 | Other tool integrations | Any MCP clients/servers, CAD, KiCad, Python sci stack, WSL2 availability, conda/pixi/uv presence |
| A9 | Scheduler / long jobs | Queue, persistence, checkpoints, retries, cancel/resume, priorities |
| A10 | Approvals, notifications, UI | Approval types, Dynamic Island, voice/text paths, existing graph/visual memory view |
| A11 | Self-learning | The existing "research an unknown task, then do it next time" mechanism: where learned procedures are stored, how they are reused |
| A12 | Skills/procedures | Any `SKILL.md`, prompt libraries, macros, how they are loaded |
| A13 | Tests & benchmarks | Test framework, coverage, regression suites, golden tests, CI, the PC-control benchmark |
| A14 | Machine | Measured free RAM/VRAM at idle and with the local LLM loaded, disk space, GPU driver, Python versions |
| A15 | Spec overlap | Anything already built that resembles a spec feature (asset search, literature search, simulation, units, graphs, reports) |

**3.2 Run the baseline.** Run the full existing test suite and the PC-control benchmark. Save the results as `docs/lab/BASELINE.md`, keeping pre-existing failures separate from new ones. This is the reference for "no regressions".

**3.3 Produce the Spec-to-Code Mapping Matrix.** Go through the spec section by section (at least: every row of §4A.1, every module in §12.2, every node type in §13.3, every tool in §5.9, every acceptance test in §16) and classify each item:

| Code | Meaning |
|---|---|
| `EXISTS-REUSE` | Already present and fit for purpose |
| `EXISTS-WRAP` | Present; needs an adapter |
| `EXISTS-EXTEND` | Present; needs an extension (new schema type, new neuron, new config) |
| `MISSING-BUILD` | Must be built new |
| `CONFLICT` | Spec assumes something the code contradicts. Explain and propose the resolution |
| `DEFER` | Not needed for the first acceptance tests; acquire later through the learning loop |

**Phase A outputs** (all under `docs/lab/`):
- `AUDIT.md`: inventory (A1–A15) with evidence.
- `NEURON_INVENTORY.md`: every existing neuron, plus a list of unregistered capabilities.
- `MEMORY_MODEL.md`: the current memory schema and APIs, and exactly where the Lab node/edge kinds will attach.
- `MAPPING_MATRIX.md`: the classification table above.
- `BASELINE.md`: test and benchmark results.
- `INTEGRATION_PLAN.md`: ordered work plan, files to create, files that *might* need modification (with reasons), dependencies to install (versions from spec §5), risks, and open questions for me.

**GATE A:** Stop and show me a one-page summary of `INTEGRATION_PLAN.md` and any `CONFLICT` items, unless `MODE: AUTONOMOUS` is set. In autonomous mode, continue, but never cross a rank-6 (replace) or approval-required action without asking.

---

### 4. Phase B — Foundations (additive only)

Build these first, each with tests, each behind `LAB_ENABLED`:

1. **Feature flags** for the Lab, using Jarvis's existing config mechanism.
2. **Memory schema extension**, via a migration in the existing memory system (backward compatible and reversible). Add node kinds `Claim`, `Source`, `Hypothesis`, `Component`, `Parameter`, `Scenario`, `Experiment`, `RunArtifact`, `Capability`, `Tool`, `Skill`, `LearningEpisode`, and edge kinds `derived_from`, `supports`, `contradicts`, `assumes`, `requires`, `affects`, `simulated_by`, `tested_in`, `supersedes`, `implemented_by`, `learned_in`, `uses_tool`. Reuse the existing source-context and alias/fuzzy-resolution features. Do not build a second store.
3. **Neuron manifest format.** If the brain already has a neuron definition format, **use it** and map the spec §4A.2 fields onto it (add only the missing fields). Only if no format exists, create one from spec §4A.2.
4. **Typed contracts and units:** Pydantic models + `pint` for parameters, components, scenarios and experiments (spec §8.3, §12.3). Unknown values stay `null`, never 0.
5. **Skills folder** `jarvis/skills/discovery/` in Agent Skills format (`SKILL.md` + `scripts/` + `references/` + `tests/`), loaded through Jarvis's existing skill/procedure loader. If none exists, add a minimal loader that discovers names and descriptions, then loads full instructions on demand.
6. **Golden-test harness:** a runner that executes a neuron's golden test and records pass/fail with versions.
7. **Learning gate**, extending the existing self-learning mechanism (spec §4A.3): gap detection → research → license/security check → isolated install (uv / pixi / WSL2) → adapter + skill → golden test → register as `LEARNED_UNVERIFIED` → promote to `VERIFIED` only via code-checked passes. Store a `LearningEpisode` for successes *and* failures.
8. **Environment manager:** one isolated environment per external tool, so Lab installs can never break Jarvis's own environment.
9. **Budget & resource meter:** API dollars, CPU time, VRAM, disk, exposed to the router and the approval system.
10. **MCP client upgrade (only if needed):** accept both 2025-11-25 and 2026-07-28 servers, and support the **Tasks** extension for long calls. If Jarvis's MCP client lives in existing code, prefer a wrapper; any change goes in `MODIFICATIONS.md`.

**Proof of foundations:** learn **one** small tool end-to-end through the gate (ngspice or PyBaMM recommended), register its neuron, call it from a natural-language request, and see it in memory. Then turn all flags off and confirm the baseline still passes.

---

### 5. Phase C — Build the Lab capabilities

Build in this order (it matches spec §15). For **every** capability:

- (a) Classify it with the change policy.
- (b) Implement it, or reuse/wrap/extend.
- (c) Write its **neuron manifest**.
- (d) Write its **Agent Skill** if it is a multi-step procedure.
- (e) Write a **golden test** with a known answer.
- (f) Register the neuron and memory `Capability`/`Tool` nodes (Phase D rules).
- (g) Run the regression suite.

| Step | Capability cluster | Key tools (versions per spec §5) |
|---|---|---|
| C1 | Intent parsing, units, part-name resolution, reality/evidence classification, recursive decomposition | Existing router + small local model; `pint`; memory aliases; spec §3 |
| C2 | Component graph, parameter registry, dependency DAG + invalidation | Pydantic, NetworkX (or the brain's own graph library) |
| C3 | Asset search, licensing, identity scoring, perishable-source caching | Sketchfab Download API, Poly Haven, local/user files from memory first |
| C4 | Reconstruction and geometry QA | Existing Blender integration on Blender 5.2 LTS; CadQuery; FreeCAD 1.1; reviewed Blender Agent Studio skills |
| C5 | Functional rigging (mechanical, electrical, digital) | MJCF generation for MuJoCo 3.12; `kicad-cli` + KiCad 10 IPC; Verilator ≥5.036 + cocotb 2.x |
| C6 | Simulation adapters and scenarios | MuJoCo (CPU) + sysid calibration; ngspice; PyVista viz; PyChrono 10 for vehicles; Gmsh |
| C7 | Research | OpenAlex (keyed, metered), arXiv, Semantic Scholar (cached), Crossref; PaperQA2 (pinned CalVer, LLM through the router); hypothesis tournament + independent skeptic |
| C8 | Experiments and optimization | Optuna; OpenMDAO if needed; program evolution (OpenEvolve/ShinkaEvolve) only with a reviewed evaluator; experiments as jobs in the existing scheduler |
| C9 | Evidence gates, reports, notifications | Spec §6.2 vocabulary; existing notification/Dynamic Island path |
| C10 | Vehicles & F1 | PyChrono 10, FastF1 3.8.x; 2025 vs 2026 active-aero mode model (spec §2.1, §16.1) |
| C11 | Theory/speculative | SymPy tensors + SciPy geodesics; EinsteinPy as a cross-check only |

Everything else in spec §5 is `DEFER`: Jarvis acquires it through the learning loop when a request first needs it.

**Tool-access tiers** (spec §4A.5): headless Python/CLI first → MCP server → **agent-desktop** accessibility-tree control for GUI-only steps → screenshots last. Every GUI action is verified by reading the output file.

---

### 6. Phase D — Update Jarvis's brain, neurons and memory with EVERYTHING

This phase is mandatory. Jarvis must be able to **discover, choose and use** every capability from plain language, and to explain what it can do.

**6.1 Neuron coverage.** Register a neuron (in the brain's real format) for:
- every new Lab capability from Phase C;
- every **existing** Jarvis capability that `NEURON_INVENTORY.md` found without a neuron. Wrap it, don't modify it;
- every external tool adapter (Blender, FreeCAD, KiCad, solvers, literature APIs, agent-desktop GUI skills).

**6.2 Edges.** Wire neurons with typed edges (`requires`, `produces`, `verifies`, `fallback_for`, `invalidates`, `costs_approval`) so the brain can compose multi-step paths. Example to verify: "open the front-wing flap 3° more and rerun the same track" must resolve to the path in spec §4A.2 and fire only the downstream neurons.

**6.3 Intent coverage.** Each neuron gets several natural-language intent phrasings (including casual and misspelled ones) and aliases stored in memory, so Jarvis matches "sim the car", "run a lap sim" and "simulate vehicle handling" to the same neuron.

**6.4 Routing hints.** Add per-neuron model hints to the existing router (spec §4A.7): small local model for parsing, strongest model for code generation and critique, different model family for the skeptic when available, **no LLM for numbers**.

**6.5 Memory population.** Write into the existing unified memory, with source context:
- one `Capability` node per neuron (what it does, when to use it, inputs/outputs, cost, risk, status, golden-test result);
- one `Tool` node per external tool (version, install location/env, license, OS notes, known caveats from spec §0.2 and §5);
- one `Skill` node per `SKILL.md`;
- the spec itself as `Source` nodes, chunked by section, so Jarvis can answer "why do we use PyChrono for vehicles?" or "what changed in v2?";
- rules from spec §1.3, §11.2 and §14 as policy facts that the brain consults before acting;
- all `LearningEpisode`s from Phases B–C;
- aliases for parts, tools and capabilities.

Do not write secrets, API keys or personal data into memory.

**6.6 Self-description.** Jarvis must be able to answer "what can you do in the lab?", "which tools are verified vs learned-unverified?" and "how would you do X?" by querying the brain and memory, not from hard-coded text.

**6.7 Consistency checks.** Write automated checks that run in CI:
- every adapter/tool in the repo has a neuron;
- every neuron has a golden test and at least one intent;
- every neuron is reachable from at least one intent and has no dangling `requires`;
- every neuron has a matching `Capability` node in memory, and vice versa;
- no `VERIFIED` neuron has a failing golden test;
- with flags off, the brain does not activate Lab neurons.

Produce `docs/lab/BRAIN_AND_MEMORY_REPORT.md`: neuron counts (new / newly registered existing / external), coverage percentages, the check results and the list of anything left unregistered (with the reason).

---

### 7. Phase E — Prove it

Run the spec's acceptance tests §16 **A1, A2, B, C, D, E, F, G, H** through Jarvis itself (voice/text entry, brain routing), not by calling functions by hand. For each, save: request, neuron path taken, sources, assets, solver inputs/outputs, logs, evidence status, metrics, a reproduction command and a screenshot/render where relevant.

- **G (learn and reuse)** and **H (no regressions)** are pass/fail gates.
- Score the rubric in spec §16.7 honestly. If a test can't pass because of hardware or licensing, mark it `BLOCKED` with the reason. Never fake it, and never hand-code the answer.

---

### 8. Working rules for the whole job

- Small, reviewable commits, each passing the regression suite. Tag a stable checkpoint after every phase.
- After each phase, update `docs/lab/PROGRESS.md` (template §9.4). If a session ends, the next session resumes from `PROGRESS.md` and the brain/memory state, not from scratch.
- Pin versions per neuron. Re-run golden tests after any upgrade.
- When unsure whether something exists, **search the code first**; when unsure whether a change is needed, **don't make it**. Write the question in `INTEGRATION_PLAN.md` instead.
- If the real codebase makes part of the spec a bad idea, say so plainly and propose the better option.

---

### 9. Templates

**9.1 Inventory row (AUDIT.md)**
```
| ID | Capability | Location | Entry point | Status | Has neuron? | Evidence |
```

**9.2 Mapping row (MAPPING_MATRIX.md)**
```
| Spec ref | Item | Classification | Existing module (if any) | Planned action | New files | Files to modify (if any) | Risk |
```

**9.3 Modification entry (MODIFICATIONS.md)**
```
### <file path>
- Why unavoidable (which of ranks 1–4 failed and why):
- Change (minimal diff summary):
- Behaviour with Lab flags OFF: unchanged? how verified:
- Tests before / after:
- Rollback:
```

**9.4 Progress entry (PROGRESS.md)**
```
## <date> — Phase <X> — <status: done / partial / blocked>
- Built:            - Reused:            - Wrapped/extended:
- Modified (link to MODIFICATIONS.md):
- Neurons added/updated:       - Memory nodes added:
- Tests: <pass/fail counts vs baseline>   - Benchmark: <accuracy, avg s/task vs baseline>
- Spend: <$ / API calls>       - Blockers / questions for Adi:
- Next step:
```

---

### 10. Final deliverables

1. All `docs/lab/` reports: `AUDIT`, `NEURON_INVENTORY`, `MEMORY_MODEL`, `MAPPING_MATRIX`, `BASELINE`, `INTEGRATION_PLAN`, `MODIFICATIONS`, `PROGRESS`, `BRAIN_AND_MEMORY_REPORT`, `ACCEPTANCE_RESULTS`.
2. The code, neuron manifests, skills, golden tests and migrations, all behind flags.
3. A short user guide: how I talk to the Lab, approve things, read evidence statuses, resume jobs, and see what Jarvis has learned.
4. An honest summary covering:
   - what works and what is partial or blocked;
   - what was reused vs built vs modified (with counts);
   - measured resource use and spend;
   - the open decisions from spec §19 item 19.

## END