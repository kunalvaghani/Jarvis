# Spec-to-code mapping

2026-11-04 IST. Planning classifications, **not implementation claims**. All paths are under `app/` unless specified. Source spec sections 0–20 were reviewed; master-prompt precedence is retained. Existing source/API evidence: [audit](AUDIT.md), [source index](evidence/source_index.json), [registry](evidence/registry.json).

## Integration rows: every §4A.1 row

| Spec ref | Item | Classification | Existing module | Planned action / new files | Possible existing-file modification | Risk |
|---|---|---|---|---|---|---|
| 4A.1 | Request understanding / step choice | EXISTS-EXTEND | neural registry/router/compiler; legacy Brain | New discovery neuron source and compiled workflows | registry/service/compiler hooks only where an extension is missing | Neural mode currently off; never bypass legacy/approval policy |
| 4A.1 | Unified memory | CONFLICT | ObsidianMemory, ReasoningBank, SkillMemory, journals | New facade over existing ownership; additive scientific schema migration in existing DB | Public migration/transaction API in existing owner if needed | No existing general unified typed graph established; no second store |
| 4A.1 | LLM choice | EXISTS-EXTEND | hierarchical/model_selection/brain/cloud policy | New hints translated into existing selection path | Optional per-neuron metadata/hint plumbing | Paid/secret routes must fail closed; no LLM metrics |
| 4A.1 | Approvals / notifications | EXISTS-EXTEND | Actions._approve, approval receipts, task decisions, Island | New Lab approval descriptions/event payloads | Existing allowlists only if needed | Permission is never learned |
| 4A.1 | Long jobs | EXISTS-EXTEND | TaskStore/ScheduledQueue/WorkflowGraph | Experiment-trial job handler, checkpoint contracts, Tasks polling wrapper | Existing handler registration | Never replay uncertain writes or resume paused campaign |
| 4A.1 | Desktop apps | EXISTS-WRAP | ControlService, Blender live/custom connector | New domain adapters; CLI first; existing control for GUI | None until a proven missing hook | Connector activation separate; custom server differs from spec |
| 4A.1 | Learn unknown tools | EXISTS-EXTEND | Acquisition, RepositorySkills, SkillMemory/Store, ReasoningBank | New golden gate and isolated env orchestration | Existing post-verification registration hooks | Reuse history/policy; no second learner/trust authority |

## Schema, paths and behavioral conflicts

| Spec ref | Item | Classification | Evidence / resolution |
|---|---|---|---|
| 4A.2 / 12.2 | `jarvis/brain/` package | CONFLICT | Existing planner is brain.py; execution brain is neural/. Extend neural/, do not create a shadow brain package |
| 4A.2 | VERIFIED etc. in `status` | CONFLICT | Current `status` is active/proposed/disabled/denied. Keep activation and scientific verification independent; add optional evidence metadata with backward compatibility |
| 4A.2 | Semantic edges | EXISTS-EXTEND | Current synapses have dataflow/feedback/dependency/conditional modes, type/port/permission checks. Keep those; add semantic relation metadata, not arbitrary renamed edges |
| 4A.2 | Lab input/output types | EXISTS-EXTEND | DATA_TYPES is closed and Neuron has extra=forbid. Add reviewed schema fields/types to the existing contract; never weaken validation |
| 4A.3 / Stage 2 | Promotion after golden vs golden + N real uses | CONFLICT | Use stricter golden + N successful code-checked real uses; propose N=3, retaining LEARNED_UNVERIFIED until then. Failed golden produces episode only, no executable neuron |
| 4A.4 / 12.2 | Nested jarvis/skills/discovery | CONFLICT | SkillMemory loads app/skills/*/SKILL.md, 8KB max, not nested jarvis/skills. Extend root discovery narrowly for namespaced Lab skills; keep byte/identity checks |
| 12.5 | Which Blender MCP | CONFLICT | Repo supplies a custom Jarvis BaseConnector catalog; retain it. No replacement by community or official server; no simultaneous port owners |
| 12.5 | MCP compatibility/Tasks | EXISTS-WRAP | mcp_bridge.VERSION is 2025-11-25 and rejects other returned versions. New negotiated 2026 transport/Tasks wrapper; leave existing servers on old transport |
| Phase A / 16H | Read-only baseline vs live writes | CONFLICT | Live cases mutate desktop/files/drafts/settings and invoke inference. Plan a scoped live window separately; never call oracle fixtures a live benchmark |
| 1.3 / 4A | Existing brain as single router | CONFLICT | neural.mode is off and compiled workflows are limited. Implement opt-in Lab routing within it; changing production activation is separate from implementation |
| 8.3 | Example unknown mass `0.0` | CONFLICT | Master prompt and schema prose require null for unknown. Null wins; zero is valid only with explicit numeric provenance |
| Working rules | codex/ task branch | CONFLICT | Existing user working branch named `codex` blocks child refs `codex/...`. Preserve branch topology and work on current codex; no rename/delete |

## Module-by-module §12.2 mapping

All new domain modules would live in `jarvis/discovery/`; they are not created in Phase A.

| Spec ref | Item(s) | Classification | Existing module / planned action | New files | Possible modifications | Risk |
|---|---|---|---|---|---|---|
| 12.2 | discovery manifests: intent, units, decompose, reality_classify | MISSING-BUILD | Register in existing Registry, not a parallel registry | discovery/neurons/*.json or YAML in existing contract format | neural contract/source hook | Intent collisions |
| 12.2 | asset_search, reconstruct, rig_mechanical, rig_electrical manifests | EXISTS-EXTEND | Wrap Blender and source research, add domain contracts | discovery/neurons/* | Same source hook | Availability != permission |
| 12.2 | sim_mujoco, sim_chrono_vehicle, sim_ngspice, sim_cocotb manifests | MISSING-BUILD | Only expose verified installed adapters; declared unavailable otherwise | discovery/neurons/* | Same source hook | No decorative solver outputs |
| 12.2 | lit_search, lit_qa, hypothesis_tournament, skeptic manifests | EXISTS-EXTEND | Existing research/grounding/model router | discovery/neurons/* | Existing route integration | Citation/model dependence |
| 12.2 | optimize_optuna, evolve_program, evidence_gate, report manifests | EXISTS-EXTEND | Existing jobs, verifiers, reporting | discovery/neurons/* | Existing registration hook | Evaluator gaming |
| 12.2 | brain learning gate | EXISTS-EXTEND | knowledge_acquisition, RepositorySkills, SkillStore | discovery/learning.py, golden.py | Narrow existing learning hook | No trust bypass |
| 12.2 | memory/schemas/discovery | EXISTS-EXTEND | Existing memory ownership, see MEMORY_MODEL | discovery/memory.py, migrations.py, contracts.py | Existing owner API if needed | Migration/rollback |
| 12.2 | model router hints | EXISTS-EXTEND | Existing hierarchy/cloud policy | discovery/model_hints.py | Existing hint seam if absent | Budget/privacy |
| 12.2 | pc_control | EXISTS-REUSE | ControlService/agent backends, accessibility refs | Domain skills only | None planned | Verify saved output |
| 12.2 | scheduler experiment_trial | EXISTS-EXTEND | ScheduledQueue/WorkflowGraph | discovery/jobs.py | Handler registration | Cancellation/uncertainty |
| 12.2 | approvals and notifications | EXISTS-EXTEND | Actions._approve and Island | discovery/events.py, approval descriptions | Existing schema allowlists if necessary | Physical actions remain forbidden here |
| 12.2 | skills/discovery | EXISTS-EXTEND | SkillMemory existing loader | jarvis/skills/discovery/*/SKILL.md | Explicit namespaced root hook | No third-party import without review/approval |
| 12.2 model | component_graph.py | EXISTS-WRAP | Reuse rustworkx; domain graph differs from execution graph | discovery/model/component_graph.py | None | Stable identities/cycles |
| 12.2 model | parameter_registry.py | MISSING-BUILD | No scientific parameter invalidation registry established | discovery/model/parameter_registry.py | None | Wrong downstream recomputation |
| 12.2 model | units.py | MISSING-BUILD | Existing weather units are not general dimensional analysis | discovery/model/units.py using pint | Requirements only after approved install | Unknown vs zero |
| 12.2 model | provenance.py | EXISTS-WRAP | Source observation/research evidence/artifact hashes | discovery/model/provenance.py | None | Source ≠ proof |
| 12.2 model | uncertainty.py | MISSING-BUILD | Typed bounds/sensitivity/convergence records | discovery/model/uncertainty.py | None | No fabricated confidence |
| 12.2 adapters | blender_bridge.py | EXISTS-WRAP | Existing Blender host/jobs/live and safe scoped adapter | discovery/adapters/blender_bridge.py | None unless proven blocker | Preserve connector approval |
| 12.2 adapters | freecad_mcp.py | MISSING-BUILD | No configured FreeCAD integration established | discovery/adapters/freecad_mcp.py | None | Sandbox/RPC loopback |
| 12.2 adapters | cadquery_gen.py | MISSING-BUILD | No core-environment CadQuery | discovery/adapters/cadquery_gen.py | None | Native dependencies |
| 12.2 adapters | gmsh_mesh.py | MISSING-BUILD | No established mesher adapter | discovery/adapters/gmsh_mesh.py | None | Mesh quality |
| 12.2 adapters | mujoco_adapter.py | MISSING-BUILD | No core-environment MuJoCo | discovery/adapters/mujoco_adapter.py | None | CPU-only golden mechanics |
| 12.2 adapters | chrono_vehicle.py | MISSING-BUILD | No core-environment PyChrono | discovery/adapters/chrono_vehicle.py | None | Tires/aero assumptions |
| 12.2 adapters | kicad_ipc.py | MISSING-BUILD | No configured KiCad adapter | discovery/adapters/kicad_ipc.py | None | PCB vs schematic support |
| 12.2 adapters | kicad_cli.py | MISSING-BUILD | No KiCad CLI on shell PATH | discovery/adapters/kicad_cli.py | None | Independent ERC/DRC |
| 12.2 adapters | ngspice_adapter.py | MISSING-BUILD | No ngspice on shell PATH | discovery/adapters/ngspice_adapter.py | None | Proven component models |
| 12.2 adapters | cocotb_runner.py | MISSING-BUILD | No core cocotb / PATH Verilator | discovery/adapters/cocotb_runner.py | None | Simulator compatibility |
| 12.2 adapters | paperqa_adapter.py | MISSING-BUILD | Existing research isn't PaperQA integration | discovery/adapters/paperqa_adapter.py | None | LLM provider budget |
| 12.2 adapters | openalex.py | MISSING-BUILD | Existing Firecrawl is research access, not metered OpenAlex client | discovery/adapters/openalex.py | None | Free budget cannot spill into prepaid funds |
| 12.2 adapters | semantic_scholar.py | MISSING-BUILD | No dedicated cached adapter established | discovery/adapters/semantic_scholar.py | None | Shared-pool throttling |
| 12.2 adapters | arxiv.py | MISSING-BUILD | Wrap existing HTTP/source tools with official API policy | discovery/adapters/arxiv.py | None | Preprint labeling |
| 12.2 adapters | mcp_tasks_client.py | EXISTS-WRAP | Existing persistent transport remains for old servers | discovery/adapters/mcp_tasks_client.py | Minimal protocol hook if needed | Negotiated extension only |
| 12.2 verification | geometry_checks.py | EXISTS-WRAP | learning/verifiers/blender_object, blender_scene | discovery/verification/geometry_checks.py | None | Appearance vs engineering checks |
| 12.2 verification | electronic_checks.py | MISSING-BUILD | New actual ERC/SPICE/HDL assertions | discovery/verification/electronic_checks.py | None | No 3D-board substitute |
| 12.2 verification | physics_checks.py | MISSING-BUILD | Analytic/conservation reference tests | discovery/verification/physics_checks.py | None | Domain limitations |
| 12.2 verification | convergence_checks.py | MISSING-BUILD | Time/mesh sensitivity and tolerances | discovery/verification/convergence_checks.py | None | Convergence != validation |
| 12.2 verification | evidence_gates.py | MISSING-BUILD | Code-enforced evidence vocabulary/status | discovery/verification/evidence_gates.py | None | No LLM promotion |
| 12.2 visualization | pyvista_bridge.py | MISSING-BUILD | No core PyVista | discovery/visualization/pyvista_bridge.py | None | Visualization only |
| 12.2 visualization | comparison_views.py | EXISTS-WRAP | Existing Island/events/report surface | discovery/visualization/comparison_views.py | Existing UI seam only if needed | No fabricated screenshots |
| 12.2 sandbox | env_manager.py | EXISTS-WRAP | repo/deerflow/utility isolation and process ownership | discovery/sandbox/env_manager.py | None until gap proven | Per-tool env is not a security sandbox by itself |
| 12.2 sandbox | policy.py | EXISTS-WRAP | Request safety/approval/ownership existing policy | discovery/sandbox/policy.py | No separate approval authority | Fail closed |
| 12.2 sandbox | budget.py | EXISTS-WRAP | GPU scheduler, inference limits, cloud quota | discovery/sandbox/budget.py | Existing admission interface if needed | Reserve/reconcile costs before actions |
| 12.2 tests | unit/integration/golden_numerical/end_to_end/regression | EXISTS-EXTEND | Existing pytest, sealed verifiers, live runner | tests/discovery/* and golden fixtures | Existing CI entry point | Unit pass != live acceptance |

## Every scientific node and relation

| Spec ref | Item | Classification | Planned attachment |
|---|---|---|---|
| 13.3 / master B2 | Claim | MISSING-BUILD | Typed cited statement in existing memory owner; locator/retraction/evidence |
| 13.3 / master B2 | Source | EXISTS-EXTEND | Existing source/path/hash context, add stable scientific source kind |
| 13.3 / master B2 | Hypothesis | MISSING-BUILD | Explicit assumptions/null alternative and falsifiable predictions |
| 13.3 / master B2 | Component / parts | MISSING-BUILD | Stable identity/variant, three representations, aliases |
| master B2 | Parameter | MISSING-BUILD | Nullable value, units/bounds/provenance, downstream dependencies |
| 13.3 / master B2 | Scenario | MISSING-BUILD | Immutable environment revision and input signals |
| 13.3 / master B2 | Experiment / simulations | EXISTS-EXTEND | Existing task/artifact IDs linked to typed scientific run |
| 13.3 / master B2 | RunArtifact / artifact versions | EXISTS-EXTEND | Reuse journal artifact hashes with solver/input/source references |
| master B2 / D | Capability | EXISTS-EXTEND | One scientific memory capability record per existing registry neuron; no second executable registry |
| master B2 / D | Tool | EXISTS-EXTEND | Version/license/install/env/OS metadata; installed doesn't mean verified |
| master B2 / D | Skill | EXISTS-EXTEND | Existing SkillStore identity and source hash referenced in scientific memory |
| 13.3 / master B2 | LearningEpisode | EXISTS-EXTEND | Existing success/failure learning history plus gap/tool/golden/promotion evidence |
| 13.3 | outcomes, uncertainty | MISSING-BUILD | Strict run/claim fields, not undifferentiated personal facts |
| 13.3 / master B2 | derived_from, supports, contradicts, assumes, requires, affects, simulated_by, tested_in, supersedes | EXISTS-EXTEND | Typed relations in existing memory; retain reason/source/version |
| master B2 | implemented_by, learned_in, uses_tool | EXISTS-EXTEND | Capability/Tool/Skill/LearningEpisode references in same authoritative owner |

## Every §5.9 starting tool

Target versions below come from the user spec. Except MCP protocol and OpenAlex pricing, this audit has **not** recertified catalog versions, licenses or Windows support. Do not install from this table without the per-tool gate.

| Spec ref | Tool / requested target | Classification | Existing evidence / planned action | Risk |
|---|---|---|---|---|
| 5.9 group 1 | Existing Blender / 5.2 LTS | EXISTS-WRAP | D:\blender.exe discovered; custom integration retained; fresh version test pending | Add-on/API compatibility |
| 5.9 group 1 | CadQuery / verify and pin | MISSING-BUILD | Not in core .venv; headless CAD adapter | Isolated native dependencies |
| 5.9 group 1 | FreeCAD / 1.1.x | MISSING-BUILD | PATH miss only; discover install before proposing install | OS/version |
| 5.9 group 1 | Gmsh / verify and pin | MISSING-BUILD | New meshing adapter and golden geometry | Solver fidelity |
| 5.9 group 1 | MuJoCo / 3.12 CPU | MISSING-BUILD | Core distribution absent; analytic mechanics golden | CPU runtime |
| 5.9 group 1 | PyVista / verify and pin | MISSING-BUILD | Core distribution absent | Rendering != physics |
| 5.9 group 1 | SymPy / installed 1.14.0 | EXISTS-WRAP | Already installed; no scientific neuron yet | Symbolic assumptions |
| 5.9 group 1 | SciPy / installed 1.15.3 | EXISTS-WRAP | Already installed; analytical-special-case checks needed | Tolerance/convergence |
| 5.9 group 1 | pint / verify and pin | MISSING-BUILD | Core distribution absent | Dimensional correctness |
| 5.9 group 1 | Pydantic / installed 2.14.2 | EXISTS-REUSE | Existing neural contracts | Do not upgrade core for Lab |
| 5.9 group 1 | Optuna / verify and pin | MISSING-BUILD | Core distribution absent; existing scheduler owns trials | Fixed scenario/evaluator |
| 5.9 group 1 | PaperQA2 / reviewed CalVer | MISSING-BUILD | Core paper-qa absent; existing model router must provide LLM | Approved cloud or local compatibility |
| 5.9 group 1 | OpenAlex / current API | MISSING-BUILD | Official $1/day free allowance verified; no key provisioned | Meter global key spend; stop before prepaid drawdown |
| 5.9 group 1 | arXiv / API | EXISTS-WRAP | Existing web research/source capabilities; dedicated API wrapper missing | Cache/rate/terms |
| 5.9 group 1 | Semantic Scholar / unauthenticated | MISSING-BUILD | Dedicated cached adapter missing | Throttle/availability |
| 5.9 group 2 | PyChrono / 10 | MISSING-BUILD | Core distribution absent; discover conda/pixi availability | Download/native solver/license |
| 5.9 group 2 | FastF1 / 3.8.x | MISSING-BUILD | Dedicated telemetry adapter missing | Public telemetry cannot reveal internals |
| 5.9 group 2 | KiCad / 10 IPC | MISSING-BUILD | No configured adapter / CLI PATH hit | PCB API scope |
| 5.9 group 2 | kicad-cli / bundled target | MISSING-BUILD | Independent ERC/DRC/export adapter | Version-specific commands |
| 5.9 group 2 | ngspice / verify and pin | MISSING-BUILD | CLI not on PATH; learn/golden target | Circuit model provenance |
| 5.9 group 2 | Verilator / >=5.036 | MISSING-BUILD | CLI not on PATH | Native toolchain/WSL |
| 5.9 group 2 | cocotb / 2.x | MISSING-BUILD | Core distribution absent | Async API/toolchain compatibility |
| 5.9 on demand | Remaining §5 catalog | DEFER | No bulk installations, MCP servers, GPU training or skill-pack imports | Reverify each candidate on demand |

## Acceptance §16: every case

| Spec ref | Case | Classification | What must actually run through Jarvis |
|---|---|---|---|
| 16.1 | A1 2025 F1 | MISSING-BUILD | Licensed identity-audited native asset, actual PyChrono dynamics, angle diff under identical scenario, raw outputs |
| 16.1 | A2 2026 F1 | MISSING-BUILD | Separate aero coefficient sets and zone-driven front/rear modes, +2 degree Corner change, fixed track/power model, assumptions |
| 16.2 | B reconstruction | EXISTS-EXTEND | Existing Blender reconstruction plus lawful references, scale/silhouette QA, actual load solver |
| 16.3 | C hybrid invention | MISSING-BUILD | Proven sourced motors/batteries, parametric folding wing, energy/structure/dynamics, separate speculative branch |
| 16.4 | D time-travel theory | EXISTS-EXTEND | Existing research + SymPy/SciPy wrapper, independent analytic cross-check, driven visualization, no unsupported physical conclusion |
| 16.5 | E electronics/digital | MISSING-BUILD | Native schematic/netlist or HDL; independent ERC/SPICE or cocotb/Verilator traces |
| 16.6 | F optimize/resume/approval | EXISTS-EXTEND | Existing durable queue with immutable design/scenario, failed trial retention, reviewed interruption and budget gate |
| 16.6A | G learn/reuse | MISSING-BUILD | Genuine initial gap, researched/approved isolated tool, golden curve, failure episode/no failed neuron; fresh-session no-research reuse and measured timing |
| 16.6B | H no regressions | EXISTS-EXTEND | Full flags-on/off suite and comparable live accuracy/mean task time, idle servers/VRAM observations |
| 16.7 | Scored rubric | DEFER | Score only executed E2E evidence, not source existence; G/H are independent pass/fail gates |

## Remaining sections

§0/§1/§14: hard policy, one infrastructure path, CPU-first, no paid/hardware actions, provenance and no regressions: EXISTS-EXTEND through existing policy/resource controls. §2/§3: recursive real/speculative identity and component resolution: MISSING-BUILD. §4: clusters inside existing brain: EXISTS-EXTEND. §5.1–5.8 and §6/§20: sources/references, verify at acquisition; nonessential tools DEFER. §7: existing web/file/Blender paths EXISTS-WRAP; suitability/licensing/cache and reference reconstruction checks MISSING-BUILD. §8/§9: domain schemas, SI ports, immutable scenarios, affected-only invalidation and coupling MISSING-BUILD over existing graph/job primitives. §10/§11: existing research/learning/queue EXISTS-EXTEND; hypothesis/golden/optimizer/evidence gates MISSING-BUILD; generated-code evolution DEFER until evaluator reviewed. §12.3–12.5: typed contracts and interoperability covered above. §13.1: synchronized scientific workbench MISSING-BUILD; §13.2 notifications EXISTS-EXTEND. §15/§17: follow audited phases and master prompt precedence. §18: intent phrasings are future fixtures, not proof of routing. §19: keep all limitations and unresolved decisions visible in the integration plan.
