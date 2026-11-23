# C2: first solver and native geometry adapter

Final post-change regression: **Final post-C2 whole-project regression: 5,250 passed / 42 failed / 161 skipped**, 1553.985 s including runner setup; source fingerprint unchanged. Exactly the same 42 prior failing IDs, zero new failures and zero discovery failures. This is the credential/network/model-isolated regression result, not live UI/microphone/control or scientific release acceptance. [Terminal comparison](evidence/c2-full-final.json).

Remaining phase/gate sequence: [NEXT_STEPS.md](NEXT_STEPS.md).

2026-11-04 IST. Branch `lab/phase-c2-adapters`; changes remain uncommitted alongside preserved earlier work. The user authorized up to **50 free local attempts** and C2 implementation after checking B6/C1. This implements a bounded initial C2 slice, not the entire CAD/meshing/mechanics/electronics catalog. Shipped Lab flags remain false.

## Working result

A text request now runs through existing Engine → Actions → brain Registry/compiler/dispatcher → SciPy → independent numerical verifier → existing approval gate → owned headless Blender build → fresh native readback → Journal/LabMemory/C1 snapshots. Four explicit neurons are added to the same brain:

| Neuron | Role | Scope/status |
|---|---|---|
| `discovery.mechanics.pendulum@v1` | Bounded SciPy solve | Conditional per-run numerical verification |
| `discovery.verify.pendulum@v1` | Independent model/provenance checks | Read-only verifier |
| `discovery.geometry.pendulum@v1` | New native scene and exports | Local write; existing approval required |
| `discovery.verify.pendulum_native@v1` | Fresh Blender readback and artifact checks | Read-only verifier |

These reviewed built-ins are not claimed as autonomously learned/promoted tools. Capability records retain their scientific unverified state; individual passing runs carry `SIMULATION_PASSED_WITH_ASSUMPTIONS` and `physical_validation=false`.

Actual controlled proof: length **1 m → 1.5 m**, fixed gravity 9.81 m/s², initial angle 0.2 rad, zero damping, 8 s duration, 0.02 s samples. The measured period changed **2.0120981428 s → 2.4636243966 s**, a **0.4515262538 s** difference. Nonlinear elliptic-reference periods and energy/ODE checks passed. A counted half-step refinement differed by at most **3.33e-16 rad** on the sampled trace. This establishes numerical consistency for this ideal model, not physical measurement accuracy. [Actual brain proof](evidence/c2-brain-proof.json).

![Actual CPU-rendered pendulum preview](evidence/c2-pendulum-preview.png)

Actual Blender CPU render from the verified 1.5 m candidate, not a Jarvis UI screenshot or physical experiment. Geometry and numerical model are Jarvis-owned procedural outputs; no third-party artwork was imported.

## Model and files

The model is a uniform solid spherical bob on an ideal massless rigid connector with one revolute degree of freedom. Pivot inertia is `m*(L² + 0.4*r²)`. SciPy DOP853 integrates the nonlinear gravity/damping equation with bounded time, sampling and cancellation. Independent checks cover finite SI samples, initial state, rigid length, energy/passive damping, finite-difference ODE residual and a nonlinear undamped period reference. Unobserved periods remain null. No LLM generates result numbers.

Each native build creates a new `.jarvis-runtime/discovery/experiments/pendulum-<id>/` directory containing:

- `pendulum.blend`, editable mesh/anchor/rod/bob, native hinge, keyframes, camera and lights;
- `pendulum.obj` and `pendulum.mtl`, visual surface mesh/material exports;
- `pendulum.png`, actual 480×480 CPU Cycles render;
- `model.json`, `numeric.json`, `trajectory.csv`, `rig.json` and replayable owned `build_source.py`;
- `component-project.json`, the C1 typed component/parameter/scenario/dependency snapshot.

Stable UUIDs connect these representations. Native readback checks closed-manifold mesh, dimensions, mass, hinge topology, gravity/time mapping, source/trace hashes and four positions against solver samples. Output hashes and source/run revisions are retained as typed records in the existing Journal. Source files are not overwritten. C1 read/plan over an actual generated snapshot passed separately, with no additional solver execution. [C1 bridge proof](evidence/c2-c1-readback.json).

**SciPy is authoritative for motion.** Blender's bob is kinematic and displays the computed trajectory. A native hinge exists, but Bullet dynamics, strength/materials, collisions, air resistance, fatigue and manufacturing validity were not tested. Anchor/connector physical properties remain unresolved where not modeled; no fake inferred material is added.

## Use and reproducibility

Use a deliberately enabled configuration with existing brain mode `act` and `lab.enabled=true`, `lab.sim=true`. Production configuration was not activated. Paths are quoted and relative to the app workspace.

```text
lab simulate pendulum "examples/discovery/pendulum.json"
lab build pendulum "examples/discovery/pendulum.json"
lab build pendulum "examples/discovery/pendulum.json" length delta 0.5 m
```

All eight physical inputs must be explicitly supplied in public JSON: length, radius, mass, gravity, damping, initial angle, duration and sampling interval. See [baseline input](../../app/examples/discovery/pendulum.json). Missing values are refused, rather than silently filled with benchmark defaults. Supported design changes are length/radius/mass, set/delta and unit-aware quantities. The C1 Pint planner enforces units/bounds and downstream invalidation; the solver also checks coupled geometric constraints. Environment changes require a separate explicit scenario. This command path keeps gravity and scenario fixed.

C1 commands on a generated snapshot:

```text
lab inspect project ".jarvis-runtime/discovery/experiments/<id>/component-project.json"
lab plan parameter ".jarvis-runtime/discovery/experiments/<id>/component-project.json" <length-parameter-id> delta 0.1 m
```

The C1 plan alone remains `PLANNED_NOT_EXECUTED`; the C2 build workflow explicitly executes its own planned change and records it. The original model JSON stays unchanged.

From the repository root, with existing approved tools/environments present:

```powershell
app/.venv/Scripts/python.exe -B docs/lab/run_c2_proof.py --approved-local-output
app/.venv/Scripts/python.exe -B docs/lab/run_c2_c1_readback.py
app/.venv/Scripts/python.exe -B docs/lab/run_checks.py --receipt c2-domain-recheck.json tests/test_discovery_pendulum.py
```

The proof's approval callback matches only its two explicit owned-output requests and is operator-assisted. It exercises Actions' existing gate, but does not establish live approval-card/UI acceptance. The normal production approval handler is unchanged. Default proof resumption checks existing verified goals and file hashes without replaying native writes. `--new-trial` deliberately consumes new slots and creates new folders; it must not be used as an automatic retry after an uncertain failure. Even default resumption runs a separately counted numerical refinement, so it is not a zero-cost read-only command.

## Installed stack, resource and trust boundaries

Discovered/reused **Blender 5.2.2 LTS**, build `d13f752e3b9c`, at `D:/blender.exe`; no executable was downloaded. Existing discovery helpers already recognized this location despite stale configured paths. Installed SciPy **1.15.3**, NumPy **2.2.6**, Pillow **12.3.0**, Pydantic and previously approved isolated Pint are reused. Their runtime dependencies were already declared; no package, driver, model, WSL distro or system configuration changed. Blender's local copyright/license directory was inspected (GPL/free tool); upstream binaries are not redistributed.

The adapter uses existing hidden owned-process helpers, cancellation and timeout, factory startup, `--offline-mode`, `--disable-autoexec`, two threads and CPU Cycles. It creates only a fixed owned scene from validated numbers, never opens arbitrary user/downloaded assets or mutates the user's live scene. This is trusted-template execution, **not a general OS sandbox** for untrusted code. No GUI connector/server, local model or GPU renderer is started.

User-approved local caps are **50 ngspice calls**, **50 SciPy pendulum attempts** and **50 Blender pendulum attempts**, cumulatively durable/nonrefundable across restart. Current usage: **37 / 12 / 16**, respectively. These are application/proof tool-trial ledgers; isolated deterministic unit-test function calls are reported by pytest separately. Native create and independent inspect count separately. Existing CPU-time/disk admission budgets remain; the default 120 CPU-second daily budget can stop work before the attempt cap. Unknown or paid tools do not inherit these grants. No new paid/metered provider call occurred in this continuation.

ngspice remains the pinned existing **44.2 Linux shared library** in its hardened non-root/network-disabled RepositorySandbox. Windows release 47 remains preparation-only. The 50-call grant preserves all previous attempts, including failures. Requalification/fresh reuse and five real boundary cases passed; a synthetic speech file decoded by the installed offline CPU ASR then reached a verified ngspice goal. [Boundary cases](evidence/ngspice-fifty-edge-cases.json) · [Spoken-file proof](evidence/b6-speech-file-proof.json). Live microphone/UI and autonomous tool research/install/authoring remain open.

## Verification and remaining gates

B6/C1 gate before C2: **205 focused passes**; whole project **5,230 passed / 42 failed / 161 skipped**, with exactly the same 42 prior failing IDs and no new IDs. [Full comparison](evidence/b6-c1-full-gate.json). Final C2 focused integration: **225 passed / zero failures / zero skips**, source fingerprint unchanged; strict neural mypy passes on 18 files; actual read-only launcher check reports ready. [Focused receipt](evidence/c2-final-focused.json) · [Local checks/usage](evidence/c2-local-verification.json). The terminal post-C2 full-suite result is recorded above; passing readiness is not live scientific acceptance.

Tests cover numerical reference, damping, resolution, convergence, source/result tampering, forged provenance, flags-off behavior, quota exhaustion, cancellation, approval denial, source changed while awaiting approval, unknown physical values, parameter bounds and C1 stable identities/world/dependencies. Native proofs use actual Blender processes and reread saved files. First proof-reader failure occurred after native success; its reader was fixed and the verified goal resumed without replay. Earlier private attempts and quota consumption remain retained.

Still open: exact BREP/STEP CAD, FreeCAD/CadQuery and Gmsh integrations, independent rigid-body solver validation, general electronics/robots/F1, reconstruction from lawful references, FEM/CFD, live sources/Drive, autonomous unknown-tool learning, live microphone/approval UI, current control benchmark, advanced scientific A–H and full release acceptance. The known 42 legacy regression failures and credential-output incident remain in the cumulative handoff. Do not resume the paused repair campaign, reset authorization, publish, install or silently activate Lab flags. The next scoped C2 expansion should be selected from actual installed capabilities and pass its own golden/approval/resource gates.
