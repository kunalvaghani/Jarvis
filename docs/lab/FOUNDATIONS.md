# Discovery Lab foundations candidate

## B6 bounded ngspice proof — 2026-11-04 IST


Current final focused verification: **177 passed / zero failures / zero skips**, 54.15 s (55.828 s including runner setup), source hash unchanged during the run. It covers divider, foundations, neural registry/mode/learning, flags, refusal, DAG, skills, sandbox and launcher fixtures. Strict neural mypy passes on 18 files; actual readiness reports ready. [Regression receipt](evidence/ngspice-regression.json). These checks do not execute a new full suite, microphone or live control benchmark.

The user separately approved Linux preparation and up to 20 sandbox divider invocations. Official hash-pinned Debian **libngspice0 44.2+ds-1** and **libgomp1 14.2.0-19** were extracted into a private tool folder: **2,641,104 archive bytes**, **9,405,810 extracted bytes**. Copyright/exception files are retained. No package manager or maintainer script ran; no host/core install, PATH change, Docker pull/build or image replacement. Release 44.2 is a compatibility pin, not Windows release 47.

New bounded adapters compile only an ideal DC resistor divider. They use the existing non-root RepositorySandbox and its network/process seccomp restrictions, immutable image, read-only mounts and resource limits. Numeric vectors are independently checked against Ohm/Kirchhoff equations; actual solver receipts are required. Failed or missing outputs have no analytic substitution. Each attempt consumes a durable slot before dispatch, across Journals/restarts.

**Operator-assisted proof passed:** three actual golden cases, three independent verified text-ingress → Actions → brain → sandbox goals, code-checked promotion, and fresh-process reuse without requalification. Final qualification: **19.407 s**; final fresh-process reuse: **3.313 s**. There are 21 immutable Experiment/RunArtifact pairs in the scratch brain Journal. The earlier implementation's qualification was degraded after file-size and invalid-request refusal improvements changed its hash; final source was requalified. [Current learning receipt](evidence/ngspice-brain-learn.json) · [Fresh-process receipt](evidence/ngspice-brain-reuse.json) · [Runtime summary](evidence/ngspice-runtime-summary.json).

**24/24 approved attempts used:** 22 successful calls and two failed initial attempts. The user explicitly approved four additional attempts to requalify the final invalid-request refusal fix. The cap is exhausted and a no-dispatch exhaustion check passed; no further execution is authorized by this batch. The native failure was localized to the pre-init no-spinit API; it remains recorded/charged. Empty private initialization paths resolved it without loosening isolation. Initial successful receipts remain separately labeled historical. The existing Google credential-output incident and all unrelated regression failures remain unresolved as previously recorded.

Shipped Lab flags remain false; production scientific memory was not populated. Six reviewed built-in Lab manifests now include divider execution/verification; learned promotion exists only in the scratch proof Journal. Supported opt-in text: `lab simulate divider 10 V 1000 ohm 1000 ohm`. This models ideal DC resistors only: no temperature response, arbitrary circuit, physical validation or hardware action. The scoped qualification does not grant additional execution beyond the exhausted approved batch. A recognized invalid divider request now remains in the brain and is refused by the typed adapter before solver dispatch, rather than falling back to the general planner.

**B6 remains partial:** actual microphone/spoken acceptance and autonomous research/install/adapter authoring were not performed. This operator-assisted harness is not autonomous G acceptance. Full scientific A–H, current whole-project flags-on/off/live-control comparison and release acceptance remain open. The preceding 5,181/42/161 full-suite result predates this solver extension; do not present it as a fresh whole-suite result for this source. Focused regression and readiness receipts below provide the current verification. Paused repair campaign stays paused.


2026-11-04 IST, `lab/phase-b-foundations`. The user approved proceeding with the current integration plan and making unavoidable minimal changes. **The Lab remains off in shipped configuration.** This is a foundations implementation, not completion of the universal simulation lab.

## What is implemented

- Four default-off flags use the existing configuration mechanism: `lab.enabled`, `lab.sim`, `lab.research`, `lab.learning`.
- New domain code lives in `app/jarvis/discovery/`. Six reviewed manifests map onto existing Neuron contracts, including the bounded DC divider and verifier. The existing brain, compiler, dispatcher, journal, verifiers, lifecycle, policies and model settings remain the execution infrastructure.
- Strict Pydantic records cover Claim, Source, Hypothesis, Component, Parameter, Scenario, Experiment, RunArtifact, Capability, Tool, Skill and LearningEpisode. Unknown numbers remain null; known numbers require a source/measurement/solver/deterministic origin and reference. Non-finite values, extra fields and invalid bounds are rejected.
- `LabMemory` indexes immutable scientific artifacts in the **existing brain Journal**, with typed relations and endpoint checks. Reversible deactivation preserves history. An optional reference-only index uses the existing ReasoningBank connection; scientific text is not inserted into personal facts or reasoning strategies.
- Pint runs through its approved isolated environment and owned worker. Pins are checked, input/output bounded, child execution/network denied by a CPython audit hook, process time measured, and each routed conversion reserves resources in the same Journal. This worker is not a general OS sandbox for arbitrary scripts.
- The golden runner has a closed list of reviewed evaluators. A caller-created pass artifact grants no qualification: promotion checks the evaluator-run record, current implementation/environment fingerprint and Python version. Failed cases are retained.
- The learning gate qualifies only the reviewed Pint adapter and the explicitly approved, bounded ngspice DC divider. Its candidate stays proposed while three actual independently verified goals use that adapter. Duplicate finish events do not increase the count. After promotion, the wrapper survives a service rebuild/restart and reuses the same reviewed adapter. Changed qualification evidence blocks reuse and can retire the learned node through the existing Registry lifecycle path.
- Read-only readiness, queue/checkpoint adapters, bounded journal resource reservations and two namespaced guides are available. Discovery guides are loaded through the existing SkillMemory validations only when the Lab opt-in is supplied.

No separate database, planner, executable registry, scheduler, approval service, model router, notification service or always-on Lab server was added.

## How to use the current candidate

The shipped `app/config/config.json` contains:

```json
"lab": {"enabled": false, "sim": false, "research": false, "learning": false}
```

For a deliberately enabled test session, use a private configuration copy with `enabled` and `sim` true and the existing neural mode on. Then the current supported text commands are:

- `lab status`
- `what can you do in the lab?`
- `lab convert 1 km to m`
- `lab convert 0 degC to kelvin`
- `lab convert 180 degree to radian`

Known Lab questions/unparsed text become ordinary existing tasks at Actions intake; the brain compiles and verifies them. Unit results carry `MODEL_CONSISTENT` and a justification. Status queries read current registry/memory records and show verification/eligibility. A registered active node is not automatically scientifically VERIFIED.

The `research` flag provides a scoped configuration helper enabling web scouts for a Lab read without changing global control settings; no literature workflow is implemented yet. The `learning` flag gates the qualification API; there is not yet a general natural-language “research, install and learn any solver” command. Pint qualification demonstrates foundations. The separate ngspice proof above exercises a bounded solver, but is operator-assisted; full autonomous battery/tool acceptance G remains open.

Diagnostics from `app/`:

```powershell
.venv/Scripts/python.exe -B -m jarvis.discovery --check
.venv/Scripts/python.exe -B -m jarvis.discovery --golden pint_si_and_temperature
```

These explicit diagnostics do not start the UI, microphone, models or connectors. Real scientific requests continue through the existing brain. To roll back Lab behavior, set `lab.enabled=false`; keep existing brain/control settings. Scientific history remains preserved. No package removal, database deletion or service restart is required by the Lab rollback.

## Reuse and unavoidable edits

Existing Registry source injection, Report/Verdict ports, compiled Plan/Step, dispatcher/outbox, Journal transactions/artifacts, skill history, approval paths and queue/checkpoints are reused. Foundation payloads have strict scientific schemas beneath existing Report ports, so no weakening or replacement of the closed neural contract was needed. Minimal guarded hooks connect those new modules. The [modification log](MODIFICATIONS.md) records every existing file touched.

P0-4 also corrects real Google metadata: six existing file tools gain explicit contracts; only Drive search/read enter the DAG read set. Four writes remain external, approval-gated operations. This independent correction remains even with Lab flags off. It does not add a Google executor, publish OAuth, write files remotely or send email.

## Verification and boundaries

Fresh pre-change full suite: **5,160 passed / 45 failed / 161 skipped**, 1,531.30 seconds. This is the current comparison baseline, distinct from historical 39-failure reports. [Counts and failing IDs](evidence/phase-b-baseline.json) contain no assertion payloads.

Final compatible focused regression: **218 passed / one skipped / zero failures**, 37.0 seconds. It covers real Pint definitions, nulls/dimensions, immutable records and rollback, secrets/dangling edges, existing neural/skill/DAG/security behavior, text ingress → actual Actions.execute → brain, proposed/qualified growth and learned reuse. The skip is an existing environment-gated fixture; full follow-up results are tracked separately. These are controlled tests, not voice/UI or scientific acceptance A–H.

`mypy --strict jarvis/neural` passes on 18 source files. The mandatory launcher check reports **ready** outside the restricted sandbox. The initial restricted check reported unavailable Docker/Ollama; that was not a whole-machine service diagnosis, and no service was started/restarted. The existing reviewed Linux Docker image is available, but a bounded no-network/no-host-mount probe found none of ngspice/PyBaMM/Pint/SymPy/SciPy inside it. No image was pulled or changed.

The terminal full post-change regression recorded **5,181 passed / 42 failed / 161 skipped**, 1,508.30 s, with no new failing IDs against the baseline and unchanged source during execution. See [receipt](evidence/foundations-full.json). Production credential files and external/model/Blender traffic were denied; this is not live or flags-on H acceptance. The live control A/B and Google/email live suites are not executed in this phase. B6, the complete autonomous learning loop, advanced solvers, source ingestion/aliases, component DAG, scientific UI, and A–H acceptance remain open.

## Credential-output incident

An existing full-suite failed mock assertion printed OAuth credential fields; the agent accidentally included that assertion during inspection. The generated baseline log was sanitized to counts/test IDs, and subsequent runs deny production credential-file access and omit assertion/capture payloads. The displayed tool output cannot be retracted. No authorization was revoked/reset and credential validity was not recertified; rotating/reconnecting that Google authorization remains a user-controlled action. No credential material belongs in public evidence.

## Next step

The approved Linux ngspice proof has completed and its 24-attempt cap is exhausted. Preserve the records and shipped-off flags. Spoken-input and general autonomous research/install/adapter authoring remain unexecuted; the remaining scientific and live-control acceptance gates are open. Windows release-47 executables remain unexecuted. Keep the application-repair campaign paused.
