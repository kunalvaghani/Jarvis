# Current Lab user guide

<!-- E CURRENT BEGIN -->
## Phase E evidence audit — 2026-11-04 IST

Use `app/.venv/Scripts/python.exe -B app/benchmarks/live/discovery_lab.py --inspect` from the repository root to audit the dedicated saved Journal. Use `app/.venv/Scripts/python.exe -B docs/lab/reproduce_e.py --verify` to check eight portable outputs and two native netlists without rerunning solvers. These commands grant no installation/model/remote-write permission. `--run-local` is one-shot; never reset its markers. [Current case matrix and output links](E_ACCEPTANCE.md). Full A1–H remains unmet, D/E/F partial, G/H unmet; do not mistake a verified bounded goal for full science acceptance.
<!-- E CURRENT END -->

## C1 local project and asset requests — 2026-11-04 IST

With a deliberately enabled private Lab configuration, use `lab inspect project "examples/discovery/wing-study.json"`, `lab plan parameter "examples/discovery/wing-study.json" wing.angle delta 3 degree`, or `lab inspect asset "examples/discovery/asset-dossier.json"`. Paths are relative to the approved application workspace. Project/asset files are untrusted data; traversal, linked/sensitive paths and invalid schema are refused.

Parameter plans preserve the source file and fixed scenario, enforce units/bounds and list only downstream invalidation. They do not apply CAD edits or run solvers. Example assets are synthetic metadata, not real downloadable vehicles. Declared identity/license suitability is not independent engineering/legal validation. [Detailed schema, scope and reproduction](C1_COMPONENTS.md). Shipped flags remain off; ngspice's exhausted batch is unchanged.


## Optional bounded DC divider — 2026-11-04 IST

With an intentionally enabled private Lab configuration and the approved Linux runtime prepared, `lab simulate divider 10 V 1000 ohm 1000 ohm` means supply voltage, upper resistor, lower resistor. Units are explicitly V/ohm; bounds are ±100 V and 1 to 1e9 ohm. The actual ngspice vectors pass an independent verifier and are saved as Experiment/RunArtifact records in the existing brain Journal. Evidence is SIMULATION_PASSED_WITH_ASSUMPTIONS for ideal linear DC components, with no temperature or physical-hardware validation.

The operator-assisted proof used scratch configuration/Journal and did not activate the shipped Lab or microphone. The user extended the proof batch from 20 to 24 attempts; all 24 are consumed, including two failures. No further solver execution is currently authorized by this batch. Exhaustion blocks execution; it does not permit a host fallback or a new automatic download. [Evidence and limits](FOUNDATIONS.md) · [Approved runtime plan](NGSPICE_RUNTIME_PLAN.md). General arbitrary-circuit and autonomous acquisition commands remain unimplemented.


2026-11-04 IST. Foundation candidate only; [scope and verification](FOUNDATIONS.md).

Lab flags ship off. After deliberately enabling a private test configuration with the existing brain on, `lab status` lists current registered capabilities and verification state. `lab convert 1 km to m` runs Pint and a code verifier through that brain. Temperature and angle examples: `lab convert 0 degC to kelvin`, `lab convert 180 degree to radian`.

Unknown properties stay null. `MODEL_CONSISTENT` on a unit result means a deterministic mathematical conversion, not physical measurement. `LEARNED_UNVERIFIED` means a golden-qualified candidate still lacks enough independently checked uses; `VERIFIED` in this foundation is qualification for its bounded declared calculation, not general scientific truth.

The existing approval system remains responsible for installs, paid compute, changed constraints and external writes. Pint's separate installation was explicitly approved. No arbitrary script, new solver, cloud service or hardware operation is authorized by that approval. The local resource meter retains uncertain reservations and refuses paid/GPU admission; it does not replace existing quota or GPU policy.

The general “learn a battery solver,” vehicle simulation, circuit design, optimization and job-resume commands are not implemented yet. Queue/checkpoint and learning APIs are foundations, not accepted autonomous workflows. Do not interpret their presence as a completed experiment.

Disable `lab.enabled` to roll back feature activation while retaining scientific history. Existing queue controls remain the route for actual jobs; the Lab adds no second queue. Current explicit diagnostics are `python -m jarvis.discovery --check` and `python -m jarvis.discovery --golden pint_si_and_temperature` in the main app environment. Never clear old task/stop markers or resume the paused repair campaign as part of Lab setup.
