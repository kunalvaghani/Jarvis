# Phase D — typed neuron and scientific memory integration

2026-11-04 IST. Task branch `lab/phase-d-integration`. This implements row D of the integration plan. D2's external report/Sheets/portal/scout/job/choice adapters remain separate work. Shipped Lab flags remain false. The repair campaign remains PAUSED_BY_USER. No package, model, remote service, quota, privacy policy or control default was changed.

## What changed

The existing Registry/CapabilityGraph, compiler, dispatcher, hard eligibility, Journal and LabMemory remain authoritative. Two new explicit neurons register only with `lab.enabled`: `discovery.integration.audit@v1` and `discovery.verify.integration@v1`. This brings the built-in source inventory to 27, with all relevant Lab flags enabled only in the private proof. Shipped flags remain off. Learned qualified wrappers are inspected against their reviewed base descriptor; descriptors cannot create/register arbitrary code or grant permission.

[Owned typed descriptors](../../app/jarvis/discovery/neurons/integration.json) reconcile each registered neuron's actual ports/provider with its declared capability prerequisites, existing handler, memory kinds, model hint, test and skill. The audit detects missing/unmapped neurons, missing handlers, contract drift, dangling/cyclic prerequisites, invalid synapse ports/types, missing owned files and registry errors. Concrete execution dependencies remain in the existing compiler's per-goal DAG. Twenty-three representative command templates compile and pass the existing DAG/type checks without executing their adapters, reading their placeholder files or invoking a model/solver.

Model routing is unchanged: only the existing C3 proposal path uses the local router. The D audit is deterministic CPU work. Native Blender writes retain `needs_approval`; current eligibility is computed by the existing hard policy for the inspection context; dispatch recomputes it for each actual future goal. A test path/hash is a pointer to a check, never evidence that it ran.

## Using it

With the existing brain on and Lab enabled in an authorized scope:

```text
lab audit integration
lab memory wire
```

The first command reads the live registered contracts/handlers and typed records, saves a content-addressed snapshot in the same Journal, and compares its inventory with the previous audit there. The second reconciles resolvable forward references into the same existing edge index. It preflights integrity/missing/kind/cycle checks, then appends idempotent links; a crash leaves an inspectable prefix and never causes an external effect replay. No schema/table or Lab import is introduced by the flags-off path. Recognized D commands refuse when the Lab or brain is off, rather than falling through to the general planner.

A **verified inspection** can truthfully report **passed=false** with defects. The goal verifier checks receipt provenance, a fresh reconstruction and the diff; it does not turn a failed audit into a healthy integration. Inspect the result's `passed`, `inventory.issues`, `memory.issues`, `pending_links`, notices and template checks. Historical snapshots/records are retained; no audit changes a capability status, approval, scientific evidence tier or physical claim.

## One typed memory

[Memory reference projection](../../app/jarvis/discovery/memory_graph.py) reads all bounded record revisions and checks record/edge artifact hashes, index identity, endpoint kinds, missing references, cycles and Journal-backed RunArtifact contents. Up to2000 record revisions and 10000 edges are inspected; exceeding either bound yields an explicit incomplete failure. External/native paths are not followed or validated by this audit.

New LabMemory writes add resolvable declared links. `source_ids` and experiment artifact IDs map to typed `requires` dependencies; component parents also map to `requires`, tool references to `uses_tool`. Authored `supports`, `contradicts` and `derived_from` evidence links remain separate and immutable. Inline Scenario/Experiment parameters stay inline typed values rather than being duplicated as new records. Existing captured target revisions remain fixed when a source later changes. Missing/wrong-kind targets are never fabricated. Forward references can be reconciled by `lab memory wire`. A failed/gap learning episode may retain an unregistered tool identifier as a visible gap notice; it cannot qualify a capability.

`LabMemory.resolve(query, kind)` reuses `jarvis.names.rank` against existing typed IDs and names, preserves source/evidence context, and returns all ambiguous candidates. It invents no aliases and does not mix scientific records into personal facts or strategy induction.

For a claimed VERIFIED learned capability, the audit checks the existing reviewed base/wrapper contract and requirements, current actual golden receipt, a promoted LearningEpisode, and at least three distinct verified Journal goals with the expected independent verifier events. It rejects unsupported/manual promotions, weakened wrappers, duplicate use counts and stale/missing evidence. The qualification lookup examines at most 200 latest learning episodes; absent proof within that bounded lookup fails verification rather than being assumed. It never promotes a neuron itself. Existing LearningGate remains the promotion owner.

## Executed proof and checks

[Actual text-ingress proof](evidence/d-brain-proof.json) runs Engine → Actions → existing brain → audit adapter → independent verifier → Journal on an owned SQLite backup of the real C4 proof history. The original source is opened read-only and its hash remains unchanged. The first accurate audit reports 12 unresolved forward-link projections; wiring appends those 12 links and passes. A fresh process reopens the same Journal, passes with zero inventory changes and zero pending links. All 27 contracts/handlers are covered. Native write approval remains required. A separate fresh flags-off process observes no Lab imports, neurons or tables; a flags-off command is refused before generic planning. No new model, simulation/native solver or application call occurs in this proof. It is operator-assisted text acceptance, not live microphone/UI or autonomous scientific discovery.

Pre-change focused baseline: **208 passed**, 60.55 s (61.953s including setup), on the exact prior C4 fingerprint. Final host focused run: **228 passed / zero failures/skips**, 74.67 s (75.984s including setup), source unchanged. [Focused receipt](evidence/d-focused-host.json). The new D domain adds 20 cases, including 8 feature combinations, actual approved Pint golden+three verified uses, duplicate/forged proof rejection, source/artifact corruption, dependency cycles, ambiguity, revision capture and real ingress. The pure D domain run passed 20. An initial restricted combined run passed227 and failed an existing Tk fixture; the complete host repeat above passed it. A pyreadline3 console-finalizer warning followed one successful domain process; exit status and all test outcomes were successful. No unrelated UI code was changed.

Repository-configured strict neural mypy passes 18 files. Actual read-only host `python -m jarvis.launcher --check` reports ready without starting/changing services. **Final Phase D regression: 5,301 passed / same 42 existing failed / 161 skipped**, 1,567.485 s including runner setup. Exact previous failing IDs retained; zero new failures, zero Discovery failures, and unchanged expanded source fingerprint. [Terminal comparison](evidence/d-full-final.json). This isolated regression is not live voice/UI/control or full scientific/release acceptance. The harness fingerprint now also covers Lab descriptor JSON and built-in skill files; prior receipt hashes used the earlier Python/config/requirements-only scheme. Exact test-ID comparison remains the regression criterion.

Full scientific/live acceptance remains open: prior42 unrelated regression defects, G/H, current flags-on/off PC/browser latency and accuracy, live microphone/approval UI, exact CAD/meshing/FEM/CFD/vehicle/HDL/physical validation and D2. No stable release, paid fallback, production rollout or blanket scientific verification is claimed.

## Reproduction and rollback

```powershell
app/.venv/Scripts/python.exe -B docs/lab/run_checks.py --receipt d-repeat.json tests/test_discovery_wiring.py
# From app/: .venv/Scripts/python.exe -B -m mypy --config-file mypy.ini jarvis/neural
# From app/: .venv/Scripts/python.exe -B -m jarvis.launcher --check
```

The [proof driver](run_d_proof.py) is one-shot and refuses an existing marker. Do not delete markers/history to manufacture another first run. The commands above can inspect an authorized existing Journal without repeating prior solver/model work. Roll back by disabling `lab.enabled`; retain immutable memory and audit history. No second planner, scheduler, model router or database was created. Existing modified seams are LabMemory's ready-reference hook/name API, brain source/compiler/adapter composition, and Actions' D route/refusal; other phase files and mixed existing user work are preserved. Runtime manifest and both READMEs are updated in the same change. No commit/push was made from the mixed working tree.
