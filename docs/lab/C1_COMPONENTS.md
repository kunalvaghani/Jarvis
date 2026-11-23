# C1 component and asset foundations

## Current continuation — 2026-11-04 IST

C1 has since passed the B6/C1 whole-suite comparison (5,230 passed / same 42 failed / 161 skipped), and the combined final C2 focused suite passes 225 tests. C2 now executes a bounded explicit pendulum length-change workflow using this planner and persists actual native parts/scenario/dependency snapshots in the same Journal. C1 standalone plan commands still do not execute changes. Generated C2 component JSON was inspected/planned through actual C1 ingress; source stayed unchanged and ngspice usage stayed 37/50. [C2 report](C2_PENDULUM.md) · [Bridge evidence](evidence/c2-c1-readback.json). Live Drive/provider/source corroboration remains open. Earlier C1-only counts and 24-call exhaustion below are historical.

Final verification: **204 focused tests passed**, strict neural mypy passes (18 files), actual launcher readiness reports ready. [Scoped regression](evidence/c1-regression.json) · [Actual text-ingress proof](evidence/c1-brain-proof.json). Whole-project/live acceptance remains open.


2026-11-04 IST, `lab/phase-c1-components`. The user authorized moving to the next plan step. **Local C1 implementation; shipped Lab flags remain off.** This does not close the earlier spoken/autonomous B6 gates or scientific A–H.

New domain modules reuse the existing rustworkx/Pydantic stack, approved isolated Pint worker, brain Registry/compiler/dispatcher, scoped-path helper, skill loader and Journal/LabMemory. No package was installed, no model/asset downloaded, no credential read, no service started and no ngspice call made.

## Current behavior

- Component assemblies have stable IDs, explicit parents and separate physics-dependency edges. Cycles, dangling references, duplicate paths/IDs and scenario/design identity collisions are rejected. Assembly membership alone never invalidates all downstream work.
- Mutable design parameters require explicit bounds. Set/delta changes are unit-checked with Pint; affine-unit deltas subtract the converted zero offset. Unknown baselines cannot be incremented. The fixed scenario is preserved. The result lists only affected computations in dependency order and says `PLANNED_NOT_EXECUTED`.
- Project snapshots and typed components/parameters/scenarios/source context remain in the existing Journal. Immutable revisions cannot be rewritten. Plans do not edit the supplied file, regenerate geometry, run solvers or apply an optimized design.
- Local asset dossiers distinguish authoritative-CAD declarations, replicas, concepts, comparable objects and visual-only material. Identity includes variant/year/rule set. Missing or unsupported confirmed reuse rights, mandatory origin/hash or required attribution veto reuse regardless of suitability score. The actual local file hash must match before inspection/cache success.
- The optional small-asset cache stores inert bytes, source/license/credit and lineage in existing Journal artifacts, capped at 500 KB. Repeated caching is idempotent. No embedded script, macro, CAD file or plugin runs. Larger/native asset storage remains open.
- `drive_sources.py` accepts the existing `google_files.Files` client and only calls its search/read methods. Text stays untrusted; its hash explicitly covers the returned excerpt, with truncation reported. Author/license are unresolved unless independently supplied. No new account/client/credential path or remote write is added. This boundary is mock-tested, not live-Drive accepted.

Asset license and identity flags are supplied dossier evidence, not independent legal/engineering validation. `FOUND_EXACT` means the declared authoritative identity matches requested fields; it does not establish calibrated geometry or physics. Local metadata-only examples must never be described as real downloaded F1 models.

## Opt-in text requests

Use a deliberately enabled private configuration (`lab.enabled=true`; parameter plans also require `lab.sim=true`) and the existing brain mode. Quoted paths are relative to `Actions.base`, the current application workspace; parent traversal, linked/reparse paths and sensitive paths are rejected. No broader filesystem permission is granted.

```text
lab inspect project "examples/discovery/wing-study.json"
lab plan parameter "examples/discovery/wing-study.json" wing.angle delta 3 degree
lab inspect asset "examples/discovery/asset-dossier.json"
```

The [wing study](../../app/examples/discovery/wing-study.json), [asset dossier](../../app/examples/discovery/asset-dossier.json) and [visual metadata](../../app/examples/discovery/synthetic-visual.json) are explicitly synthetic, inert JSON examples. They contain no engineering mesh, real vehicle data or physics output. The 3-degree plan invalidates wing geometry → mesh → aero → handling while leaving unrelated chassis thermal work untouched. No stage in that list is actually executed.

Four new explicit neurons register only with the existing Lab flag: `discovery.components.inspect@v1`, `discovery.parameters.plan@v1`, `discovery.assets.inspect_local@v1`, `discovery.verify.c1@v1`. Their adapters use the existing brain. The C1 verifier checks scoped input hashes and deterministic integrity calculations; it does not certify physics. Capability records remain scientifically unverified. No second planner, database, scheduler, approval service or model router exists.

## Reproduction and remaining gates

From the repository root, after the previously approved isolated Pint environment is present:

```powershell
app/.venv/Scripts/python.exe -B docs/lab/run_c1_proof.py
app/.venv/Scripts/python.exe -B docs/lab/run_checks.py --receipt c1-checks.json tests/test_discovery_components.py
```

The proof uses actual text ingress → Actions → brain → adapters → verifier with a scratch Journal and configuration. It checks three supported requests plus invalid-bound refusal, unchanged source files and zero additional ngspice slots. [Proof receipt](evidence/c1-brain-proof.json). Re-running this C1 proof does not authorize or consume ngspice calls.

Current regression/readiness results are recorded in [progress](PROGRESS.md). Earlier failed registration/fixture attempts remain private test receipts, not hidden passes. Whole-project flags-on/off and live desktop comparison have not been repeated for C1. Voice, live Drive/catalog retrieval, source-origin/license corroboration, large-asset caching, reconstruction, CAD/rigging/physics and scientific A–H remain open. The exhausted 24-call ngspice proof is unchanged.

Rollback: `lab.enabled=false`; preserve the Journal and source files. The paused autonomous repair campaign remains paused. No stable release tag or full scientific acceptance is claimed.
