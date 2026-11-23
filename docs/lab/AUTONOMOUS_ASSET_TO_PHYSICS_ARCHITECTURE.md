# Asset-to-physics integration architecture — 6 November 2026 IST

Status: audit complete; extension of the implemented conditional workflow is in progress. The user's newly required real-asset A1/A2 acceptance is **UNMET**. This document distinguishes reused implementations from pending integration.

## Reuse decisions

| Concern | Existing implementation to retain | New work justified by audited gap |
|---|---|---|
| Router / execution | Neural compiler/dispatcher, typed neurons, existing grouped scheduler | Real-asset workflow contracts with actual download/import completion gates; no parallel planner |
| Durable state | Existing Journal and StageJournal claim/checkpoint/fingerprint pattern | Versioned general mechanical-object phase state and stage-specific validators |
| Browser | Existing authenticated ExtensionRunner/native host; ControlService fallback hierarchy | Bounded read-only link/href inspection for Jarvis-owned research tabs; no new browser or extension permission |
| Acquisition | Source, AssetCandidate, LabMemory, existing confined file helpers | Rights-bound inert binary downloader, staging/completion/hash/type checks and bounded safe archive inventory |
| Geometry | ComponentGraph/parameters, actual GLB authoring/readback, installed CPU mechanics tools | Import-time hierarchy/transform/units/connectivity inventory and original/derived lineage; unsupported formats explicit |
| Physics | Qualified fixed CPU Chrono and MuJoCo workers; existing grants/budgets | Source-derived assembly binding and independent supported maneuver configurations, not a new solver installer |
| Presentation | Existing app/brain UI and TaskState/report bus | Version-bound assembly inspection/playback and validated edits; static diagnostics remain evidence, not interactive acceptance |
| Memory / reuse | LabMemory Source/Component/RunArtifact and existing skill system | Retain acquired asset and verified assembly/workflow revisions for fresh-session reuse; never grant permission from history |

LangGraph is not selected: Journal/dispatcher/task DAG already provide persistence and guarded execution. Adding another controller would not acquire an asset or fix the missing geometry/physics handoff.

## Boundary contracts

The general phase sequence is research, candidate selection, rights verification, download, file validation, inspection, disassembly, reconstruction, assembly, physics configuration, simulation, independent verification and report. Every accepted phase requires durable artifacts and an independent validator; output text or a successful network request alone is insufficient.

An acquisition specification must retain the original target/constraints, candidate/provider identity, source/creator, exact rights evidence and attribution, format, expected or bounded bytes, source locator, intended use and allowed download path. A download result must bind actual completed bytes/hash/type to that specification, retaining original separately from derivatives. No viewer extraction, credentials copied from browser storage, signed executable, macro or downloaded script is eligible.

A geometry inventory must reference the acquired file hash and expose actual nodes/meshes, transforms, declared or unknown units, bounding boxes, connected components, topology checks and parser limitations. Labels from filenames are proposals. A mesh boundary is not proof of a joint or hidden suspension. Unsupported CAD/mesh encodings must identify the missing importer rather than claim import succeeded.

A mechanical assembly must share stable component IDs with geometry, but retain separate physical bodies, hardpoints, frames, constraints, normalized axes, mass/inertia, material/force models, parameter ranges and per-property provenance. Existing ComponentGraph supplies dependency invalidation; solver-native JSON/MJCF stays a derived artifact.

An experiment binds one immutable assembly revision and scenario revision to a typed solver-supported maneuver, seed/time grid, controls, parameter diff, worker/version hash, resource admission and actual invocation/result receipts. Parameter comparisons keep the scenario fixed except explicitly requested scenario branches. The eight requested maneuvers require separate evidence; the previous combined 13-second road test cannot stand in for all eight.

## Technology evaluation

- Existing Blender scripts/MCP remain available for qualified modeling/visualization. Asset scripts/macros are never executed. A Blender connection is not CFD or vehicle-dynamics evidence.
- Trimesh 5.2.0 was installed with the approved isolated mechanics setup. Its [typed scene-loading API](https://trimesh.org/trimesh.exchange.load.html) exposes remote loading separately; any qualified importer must keep remote resolution disabled and validate all referenced files. Installation is not parser qualification or an OS security sandbox.
- FreeCAD/OpenCascade/CadQuery are optional importer/reconstruction adapters, not assumed installed. STEP cannot be advertised as imported solely because the license gate recognizes its extension. No new install is authorized here.
- [PartField](https://github.com/nv-tlabs/PartField) is a research candidate, not a qualified local dependency. Its weights/runtime/hardware/license are not yet proven on this 4 GB GPU, so it is not selected for the routine CPU path.
- Official provider APIs are permitted where safer than UI downloads. [GitHub's content API](https://docs.github.com/en/rest/repos/contents) documents expiring download URLs and size-dependent behavior; fresh resolution, commit/file identity and actual asset rights must be checked. A repository's code license alone is not evidence that all included third-party models are covered.
- WebMCP remains optional and page-bound. No website is presumed to expose it; existing browser methods remain eligible fallback.

## Progress, recovery and security

Keep the existing report bus/TaskState checkpoints live. A phase fingerprint includes stage, typed arguments, upstream artifact hashes and model revision. Bounded unchanged reads may select a different eligible strategy; uncertain writes/download completion are reconciled before retry. Partial staging data never becomes an imported asset. Failure records remain available to the next session.

Preflight tools, permissions, source rights, formats, resource reservations and checkpoints before each stage. Respect the shared grant and Journal daily admission; separate fresh processes cannot reset either. Default to CPU, no paid services, no global Lab flag activation, no old campaign restart and no physical device actions.

The localhost native host is retained. Do not introduce an unauthenticated download/file server or broaden the extension into arbitrary script/host filesystem access. Model/parser failures cannot disable existing policy, tests or independent acceptance gates.

## Verification and deliverable map

[Risk register](AUTONOMOUS_ASSET_TO_PHYSICS_AUDIT.md) and [failure matrix](FAILURE_PREVENTION_MATRIX.md) are complete as an audit. Implementations and their focused/fault/live results must be added as they land. Existing [Scenario A workflow report](SCENARIO_A_WORKFLOW.md) covers the conditional solver/controller work only. Acquisition policy, decomposition, mechanical binding, interactive controls, new live acceptance, regression/recovery and final handoff will document real implemented behavior; no placeholder document certifies those missing features.


## Implemented acquisition-to-geometry increment — 6 November 2026

- `adapters/browser_research.py` uses the existing ToolRegistry and owned browser link observations. Browser extension source0.3.2 adds fixed read-only link/href probes; no new permission. Runtime reload/live proof remains open.
- `provider_metadata.py`, `asset_rights.py`, `asset_transport.py`, `asset_files.py` and `asset_acquisition.py` enforce cached public sources, nonrefundable per-project read admission, per-file rights, pinned revision/file identity, bounded HTTPS originals and inert file checks. Sketchfab authenticated downloads remain blocked. GitHub root code licenses alone are insufficient under this adapter's current supported rights rules; per-asset manifests/REUSE declarations qualify. Other lawful declarations need a reviewed qualification adapter, not a presumption of illegality.
- `asset_inspection_worker.py` loads bounded GLB/glTF/OBJ/STL data using installed Trimesh5.2.0 with remote resolution disabled, source/world transforms, connected geometric pieces and decimated actual-source previews. Original files remain intact. Mass, inertia and joints remain unresolved. STEP/FBX/Blend, unsupported extensions and ambiguous archive entrypoints remain explicit importer blockers.
- `asset_inspection.py` uses the existing shared mechanics50-call ledger, current combined-source golden proof, Journal budget, 1GiB committed-memory/18s user-CPU/30s wall bounds. Actual process peaks are retained as committed memory, not mislabeled RSS. Two golden calls passed on each of two reviewed revisions (9 total mechanics calls now used). A changed worker invalidates qualification. Retained results are rehashed and bound to the dispatch ledger; pass booleans alone do not qualify the worker.
- `asset_pipeline.py` and its typed `model/asset_pipeline.py` reuse `scenario_journal.StageJournal` through an optional workflow contract. Historical Scenario A defaults/keys are retained. The general subtask researches, selects rights-qualified downloadable candidates, acquires originals, inspects geometry and verifies retained receipts. Lost publication/fresh-process inspection reuse is tested without redispatch. Unknown effect outcomes stay blocked; supplied read-only reconcilers never replay the original operation.
- `discovery.assets.acquire_geometry@v1` and `discovery.verify.acquired_geometry@v1` are registered through existing BrainService with owned descriptors and `asset-to-geometry/SKILL.md`. Acquisition is classified local_write/write and retains the existing dispatcher approval gate; browser actions retain their own policy. Both require Lab enabled/sim/research. No new top-level assistant, scheduler, model router or database exists. No new native command or complete natural-language vehicle route is advertised by this increment.

Qualification scope remains parser/controller boundaries. Actual asset acquisition, source-informed assembly, physics binding, eight independent experiments, interactive controls and new autonomous full A1/A2 are not yet qualified. Do not invoke the earlier surrogate route as a substitute. Final whole-regression/readiness results must name their exact source and scope. No claim of perfect autonomous repair or arbitrary self-modifying production code is made.


## Full A route/live-browser repair — 6 November 2026

`scenario_project.inspect_asset` now calls the registered acquisition subtask for the full non-surrogate goal, with a separate acquired-visual-asset verifier and source inspection reference. It no longer merely asks for surrogate permission after metadata. Its neuron now advertises local_write/write. A source-acquired branch does not fall through to procedural proxy geometry; mechanical binding must qualify first. The scratch acceptance runner supports an explicit, recorded owned-vehicle-project grant; it denies all other approval scopes. This is test authorization, not a shipped policy change.

The actual signed-in Chrome extension is used for unconfigured non-headless personal control. Explicit legacy/shadow/agent-browser settings and environment rollback choices win. Headless profiles remain isolated. `browser_state()` snapshots tab membership because page-title reads can pump callbacks that mutate the tab dictionary. Tests cover this real race and selector preservation.

Provider corrections: Sketchfab license objects use canonical `uri` identities; no UID field is invented. Conflicting identifiers fail. Search reads24 bounded results, filters named model years before detail retrieval, and keeps wrong-era rejections. Source object identity remains separate from creator licensing and engineering validity.

`asset_browser_download.py` now observes the admitted source in the existing ToolRegistry/control route, uses interactive-only control reads (full-page truncation hid the actual login modal), makes one official download-dialog opening click, re-observes after uncertain reply, and never clicks login/authentication or final file-format controls. Private screenshots bind actual viewport bytes to model UID/source/hash, use fixed3MB admission and retain conservative resource charges because browser CPU is unmeasured. Signed URLs stay ephemeral; all stored locator evidence contains hashes only. Model screenshots are private because account UI may be present.

The extension's fixed selected-model helpers are deliberately narrow: viewport capture; canonical per-model download-JSON observation; bounded documented Download API JSON fallback using the already authorized browser session; exact UI format/size observation. No request headers, cookies, browser storage, arbitrary endpoints, binary response extraction, viewer geometry ripping or generic network rewriting is exposed. Temporary network observation is disabled after reading and cleaned when the owned tab closes. Manifest permissions are unchanged. Runtime0.3.6 is active. The API fallback returned401; normal browser login does not establish OAuth authorization. No OAuth/account grant was created.

A1 supporting attempts22–33 retain real stage/browser/approval/error receipts privately, not autonomous success. Attempt24 verified the browser bridge; attempt29 showed the login screen; user sign-in was completed before attempt30; attempt30 showed the actual free/CC Attribution download modal. No full A1 or A2, acquired model, physical assembly or eight-maneuver qualification is claimed. Current original-file admission is20MB and Journal daily disk admission50MB; do not silently raise or reset these bounds for a dense asset.


## Current acquisition checkpoint — 6 November 2026 (supersedes earlier pending/20MB notes)

Explicit user approval activated the exact frozen `FULL_A_ASSET_RUNTIME_PLAN.md` scope. Its original proposed text/hash is preserved; do not edit it to record activation. The private authorization is at `app/.jarvis-runtime/discovery/asset-authorizations/full-a-2026-11-06/authorization.json`. Two globally consumed transfer pairs remain charged; defaults for other projects, CPU admission and shipped flags did not change. No installs, OAuth/account grants, paid calls or source-code execution were added.

Both real official UI downloads completed without the expected archive-event response. A1 attempt34 and A2 attempt9 preserve those uncertainties and actual private screenshots. Extension0.3.8 adds an owned-window archive-event alternative, but the working live path is the separately labelled UI/file reconciliation, not an invented observed URL. `browser_handoff.py` matches one file against the retained pre-click claim, public source slug and provider title, currently observed format/rounded size, Windows creation/modification window and global resource pair. It rejects ambiguous, pre-existing, changed, linked, unrelated or oversized files. Windows Known Folder resolution works in the existing stripped worker environment. Copying is bounded, cancellable and rehashed; original Downloads files remain untouched. `asset_acquisition` verifies that lineage and publishes the preserved original through existing Journal/unified memory. No operator file path or source answer is passed into the live goal.

The fixed importer remains bounded at500 geometric output records and5000 preview triangles. Dense disconnected source nodes are labelled aggregates, reserving space for later source nodes; this is not physical part separation. A2 retains499 records including10 aggregates. Missing mechanical roles, mass, inertia and joints remain unresolved. Qualified parser/workflow revisions invalidate only derived source evidence after rechecking originals and historical output hashes. Old files, states, attempts, worker results and budget rows remain retained. New parser alternatives have distinct action identities; the same unknown dispatch is never repeated. Current combined worker hash is `3dfcf46ae07b06d0369433790210c25fbbd979efde9f5b668c707635525040ac`; default and approved-profile analytic goldens both passed.

`geometry_preview.py` draws three orthographic views from actual sampled vertices, reserves/measures CPU and output bytes through the same Budget, and publishes an existing media-card event. Rendered diagnostics are not screenshots, editable authoring files, rigs or physical results. A1 and A2 have different apparent longitudinal source axes; a future physical binder must resolve frames from data rather than hardcode an asset orientation. Attribution: shungi's MCL39-inspired concept and Qvist_Designs' 2026 concept, both CC BY4.0. Source/licensing links and original hashes are in [the evidence report](evidence/scenario-a-acquisition-checkpoint-2026-11-06.json).

Final source `68701341a8c07d31dd0893a44d70cca44ce4934ff9bb5d2904f6343644a1e75a`:135 relevant guarded regressions passed, zero failures/errors/skips; strict configured typing79 files; normal-access read-only readiness ready, no service starts. A1 attempt40 and A2 attempt15 reverified five source stages and stopped **blocked** at the explicitly unimplemented source-informed mechanical assembly. Final resumes used no new download, model call or numerical invocation. Mechanics28/50; Chrono27/50. The older v4 whole-project regression remains historical.

**Required next implementation:** general source/frame and functional-component resolution; editable native authoring and explicit uncertain physical binding; independent verification of source-to-body/joint transforms; eight separate dynamics maneuvers with controlled inputs, constraints, numerical checks and meaningful baseline/candidate metrics; trajectory-driven interactive visualization and autonomous rechecks. Existing `generate_parametric_surrogate` is only the historical stage name: its acquired-source branch currently blocks and has no qualified mechanical implementation. Do not remove that guard merely to substitute the earlier class proxy or claim full A.
