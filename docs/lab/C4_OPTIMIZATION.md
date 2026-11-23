# C4 bounded optimization and C3 worker repair

2026-11-04 IST. Branch `lab/phase-c4-optimization`. Implemented additive domain modules and minimal existing integration seams. Shipped Lab flags remain false. Existing brain, model router/GPU arbitration, Journal/LabMemory, ScheduledQueue/TaskStore/WorkflowGraph and TaskState remain authoritative. The unrelated application repair campaign stays PAUSED_BY_USER.

## Working C4 scope

An explicit study declares all eight baseline physical fields, length bounds, period target/tolerance, maximum gravitational moment and CPU admission budget. Deterministic grid search evaluates 2–12 candidates with the existing SciPy pendulum solver. Only length changes. Independent trajectory/period checks precede objective and hard-constraint evaluation. Failed, infeasible, blocked and uncertain trials remain recorded. No Optuna package was installed; general program evolution and coupled optimization remain future work.

Two explicit neurons, `discovery.optimization.advance@v1` and `discovery.verify.optimization@v1`, register in the existing brain only with the master/simulation flags. Their Capability records remain UNVERIFIED pending broader learning/release qualification; individual verified brain outcomes do not silently promote the capability. The [isolated source inventory](evidence/c4-neuron-inventory.json) contains25 registered Lab neurons and7 skills; its fresh Capability records are UNVERIFIED (it does not inherit scratch qualification from other Journals). Shipped flags off expose none of these new Lab routes. The built-in procedure is [bounded-optimization](../../app/jarvis/skills/discovery/bounded-optimization/SKILL.md).

Commands from `app/`, after deliberately enabling the Lab in an authorized scope:

```text
lab optimize "examples/discovery/pendulum-study.json"
lab optimize queue "<returned-study-id>"
lab optimize status "<returned-study-id>"
lab optimize pause "<returned-study-id>"
lab optimize resume "<returned-study-id>"
lab optimize cancel "<returned-study-id>"
```

`queue` submits all remaining trials as an idempotent dependency chain to the existing queue. It requires that real queue to be attached to Actions. `step` executes one trial when a queue is unavailable. After an explicit resume, submit `queue` again if earlier paused no-op jobs have drained: new task IDs preserve those terminal records and schedule only unattempted trial indices. No automatic reopening of failed/paused scheduler tasks or external effects is introduced. Completed/cancelled/budget-stopped studies cannot reopen; new source or solver hashes require a new study rather than altered history. Disabling Lab flags refuses queued optimization commands before generic planner fallback.

## Actual numeric, queue and interruption proof

[Current proof](evidence/c4-brain-proof.json) uses actual Actions → brain → adapters → independent verifier, the existing queue and an isolated TaskState. An operator harness consumes the queue; this is not live microphone/UI or unattended overnight acceptance. Three trials are persisted, one before process exit and two after a fresh-process queue restore. The first content-addressed result is unchanged and is not repeated.

| Length | Measured period | Absolute error from 2 s | Gravitational moment | Decision |
|---|---:|---:|---:|---|
| 0.5 m baseline | 1.424899702 s | 0.575100298 s | 0.974473068 N m | Feasible |
| 1.5 m | 2.463624397 s | 0.463624397 s | 2.923419203 N m | Rejected above 2.5 N m |
| 1.0 m | 2.012098143 s | 0.012098143 s | 1.948946135 N m | Feasible, within 0.02 s tolerance |

The fixed scenario hash is checked for every result. [Runtime versions, source hashes and memory counts](evidence/c4-runtime-summary.json) pin SciPy1.15.3, NumPy2.2.6 and Pydantic2.14.2 without a new install. These values are solver outputs under the ideal-pendulum assumptions, not measurements. A gravitational-moment constraint does not validate structural strength, peak actuator torque, fatigue, materials or manufactured safety.

Fault proof: an owned child exits with code23 after persisting a trial intent/admission but before a solver receipt. After waiting21 real seconds for its20-second lease, a fresh process marks that trial UNCERTAIN, keeps its charge, skips its index and runs the next candidate. No lease timestamp was edited. Zero-CPU study budget stops before solver dispatch; pause/resume/cancel are exercised. Unit tests also reject source/scenario tampering and concurrent active leases. Existing task checkpoints carry Experiment references. A [read-only checkpoint audit](evidence/c4-checkpoint-audit.json) resolves all three real Experiment checkpoints and confirms SQLite integrity and the retained5-unit uncertain reservation. The harness deliberately leaves its owner TaskState interrupted on process exit; queue/study completion is verified separately, and live TaskIngress whole-goal completion is not claimed. No shared process was killed.

The initial proof remains [historical evidence](evidence/c4-brain-proof-initial.json); the final proof follows the explicit-requeue fix. The two proof batches together consume10 shared SciPy admissions: current SciPy22/50, Blender16/50; ngspice remains37/50. Test fixtures do not consume these global slots. No quota reset, native solver download, install, paid inference, external write, persistent service or GPU workload was added by C4.

## C3 repaired worker and bounded qualification

The old proposer requested broad tool rules, larger context and nested JSON. Firecrawl documentation research supported a smaller direct schema: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [context length](https://docs.ollama.com/context-length), and [generation options](https://docs.ollama.com/modelfile). This diagnosis is an inference from the implementation and documentation; it does not establish that context size alone caused every historical timeout.

The C3-only worker now requests direct JSON,2048 context tokens and320 output tokens at temperature0. It emits two short qualitative alternatives. Code adds the null baseline, binds only source IDs actually shown, and invokes the unchanged skeptic/source checks. Model text never supplies numerical results or proof. Ordinary worker paths retain their behavior. The wire schema is standard-library-only because the isolated brain interpreter lacks Pydantic; parent-side strict Pydantic validation remains in place.

The first approved compact batch failed before inference on that missing dependency. Both consumed slots and110 admission units remain retained, alongside the older290. The user then approved scratch420→530 while preserving 400, for exactly one quick20s/25s call and one configured90s/95s call. Both passed through the actual existing BrainClient and brain verification:

| Installed local model | Wall time | Outcome |
|---|---:|---|
| qwen3.5:0.8b, explicit quick | 17.797 s | Verified goal; three qualitative hypotheses including one null |
| qwen3.5:9b, configured route | 52.531 s | Verified goal; three qualitative hypotheses including one null |

[Corrected-worker receipt](evidence/c3-compact-wire-proof.json) · [Fresh-process stored-proposal skeptical replay](evidence/c3-wire-replay.json). Replay makes zero new model calls. Both cite the actual DOI record from the retained provider review. Citations identify context, not established entailment. Hypotheses remain UNVERIFIED_SPECULATION. The new `discovery.hypotheses.propose@v2` Capability stays UNVERIFIED; historical v1 DEGRADED records remain intact. This is two successful bounded requests, not a general reliability rate, autonomous discovery, a full-text review or the mandatory unknown-tool learning gate G.

Eight historical/current model admission reservations total 510 units and remain conservatively charged uncertain: actual worker CPU/GPU accounting is unavailable. Wall time is measured separately. Default product allowance stays120. The scratch-only530 grant and both two-slot ledgers are exhausted; no further inference is authorized by them. Existing GPU arbitration still governs C3 local inference; it is not described as CPU-only. No model/package was downloaded or paid fallback invoked.

Firecrawl used one successful search (2 plan credits) and one successful scrape (1), total3. Feedback attempts failed400/409 and obtained no refund; no purchase occurred. Source content was treated as untrusted reference data. [Research/cost receipt](evidence/c3-firecrawl-research.json).

## Verification and remaining gates

Final focused checks: **208 passed / zero failed / zero skipped**,59.97 s (61.438 s including runner), unchanged source fingerprint. The correct repository-configured neural mypy gate passes 18 files; actual read-only host launcher readiness reports ready. [Focused receipt](evidence/c4-final-focused.json) · [Static/default-flag/link checks](evidence/c4-static-checks.json). **Final C4 regression: 5,281 passed / 42 existing failed / 161 skipped**, 1,568.422 s including runner setup. The exact42 previous failing IDs remain, with zero new failures, zero Discovery failures and an unchanged source fingerprint. [Terminal comparison](evidence/c4-full-final.json). This isolated regression is not live voice/UI/control, physical validation or full scientific/release acceptance. Final focused, typing, readiness and full-suite receipts are recorded in [progress](PROGRESS.md) and [acceptance](ACCEPTANCE_RESULTS.md). A restricted full-run attempt was stopped after widespread host-access failures; host execution repeats the previous baseline's credential/network/model guards. A preliminary broad mypy invocation used the wrong working-directory configuration and traversed untyped legacy modules; the correct repository-configured18-file neural gate is the relevant result. These harness failures remain separate from product acceptance.

General CAD/meshing/FEM/CFD, vehicle active aero, broader electronics/HDL, program evolution, physical validation, portal/Sheets/full-text research and live voice/UI remain unexecuted. G/H and full A–H/release acceptance remain open. No stable release, physical qualification or production rollout is claimed. Existing unrelated42 regression defects remain in the cumulative handoff; they are not silently waived by focused Lab successes.

## Reproduction

```powershell
app/.venv/Scripts/python.exe -B docs/lab/run_checks.py --receipt c4-repeat-focused.json tests/test_discovery_optimization.py tests/test_discovery_research.py
# From app/: .venv/Scripts/python.exe -B -m mypy --config-file mypy.ini jarvis/neural
# From app/: .venv/Scripts/python.exe -B -m jarvis.launcher --check
```

Focused fixtures use actual SciPy numerics with an injected trial-ledger reservation and do not spend approved native/model slots. The guarded full suite uses the same runner with `tests` and the prior host-access context. Live proof driver `run_c4_proof.py` is one-shot: its persistent started marker refuses duplicate batches. Do not remove markers/ledgers or blindly invoke individual phases; inspect saved receipts and obtain the applicable execution scope before a new live batch. C3 qualification drivers are exhausted and refuse new inference. Product text commands above use the existing explicit permissions and shared remaining local admission limits.
