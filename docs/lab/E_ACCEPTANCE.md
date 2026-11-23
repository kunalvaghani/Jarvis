# Phase E — actual acceptance evidence, 4 November 2026 IST

<!-- E CURRENT BEGIN -->
## Current terminal verification

Final guarded whole-project regression: **5,342 passed / 42 failed / 161 skipped**, 1621.000 s including setup. Exact-ID comparison with D2: 0 new, 0 resolved, 42 remaining failures; 0 Discovery failures. Source hashes unchanged. This is not live H acceptance.

[Focused receipt](evidence/e-focused-final.json) · [Current frozen-oracle replay](evidence/e-current-audit.json) · [Terminal exact-ID comparison](evidence/e-full-final.json)
<!-- E CURRENT END -->

The Phase E harness and independent oracles are implemented. **Full Phase E acceptance is UNMET.** Current Jarvis can execute the bounded clock, DC divider and ideal-pendulum study checks below, but those checks do not satisfy the entire A1–H specification. No full-acceptance points are certified: **0/100 certified**, with mandatory **G and H unmet**. This is a conservative certification result, not a claim that the working numerical checks have zero accuracy. No 90-point, autonomous-science, physical-validation or release success is claimed.

This phase adds new benchmark/oracle files and a runtime-manifest declaration. It adds no product neuron, planner, memory store, scheduler, router, service or dependency. The existing inventory remains 42 built-in Lab neurons and 38 templates. All shipped Lab flags remain false; existing act/learning-shadow, legacy control defaults and PAUSED_BY_USER repair state are unchanged. Branch: `lab/phase-e-acceptance`, retaining the earlier mixed work; no commit/push or stable-release tag claimed.

## Required cases and current result

| Case | Result | Evidence and remaining requirement |
|---|---|---|
| A1 — 2025 F1 | UNMET | No registered vehicle/Chrono/aero assembly workflow. No real asset-acquisition or vehicle case was executed. The pendulum cannot substitute. |
| A2 — 2026 F1 | UNMET | No zone-driven, two-state front/rear active-aero workflow. No 2026 vehicle result is claimed. |
| B — reference reconstruction | UNMET | Authored pendulum geometry is not reconstruction from lawful multi-view references; scale/silhouette and load-case acceptance are unexecuted. |
| C — hybrid invention | UNMET | No sourced flying-car/propulsion/folding-wing workflow or isolated levitation investigation was executed. |
| D — time travel | PARTIAL | Three real conditional SR clock goals, independent analytic/Decimal checks and actual traces passed. Full cited forward/backward research, appropriate theoretical branches and numerical visualization remain unmet. |
| E — electronics | PARTIAL | Two real ngspice DC goals, native netlists, supply change and independent Ohm/Kirchhoff checks passed. A sourced controller/HDL, ERC/testbench and temperature-dependent model case remain unmet. |
| F — optimize/resume/approval | PARTIAL | Real bounded ideal-pendulum study, hard rejection, fresh-process checkpoint reuse, zero-budget stop and denied write gates passed. General autonomous design, in-flight interruption coverage and live approval UI remain unmet. |
| G — learn and reuse | UNMET | Earlier reviewed installed-tool qualification is operator-assisted. It does not prove autonomous acquisition of a previously unknown tool, adapter/skill generation and faster fresh-session reuse. |
| H — no regressions | UNMET | Frozen-source guarded regression comparison is recorded separately. Paired current live PC/browser accuracy/latency and measured idle-resource acceptance are unexecuted. |

The missing cases are **implementation/acceptance gaps**, not invented hardware or licensing failures. No new asset search, download or installation was performed to imply those gates passed. A real bounded subcheck is kept distinct from the broader case. The fixed rubric weights are classification15, provenance10, editable geometry15, appropriate solver20, V&V15, parameter control10, bounded autonomy10 and durability/regressions5. No category earns full-case certification while its required case evidence is missing. G/H cannot be overridden by a score or caller-provided pass flag.

## What actually ran through Jarvis

[Live harness](../../app/benchmarks/live/discovery_lab.py) follows the existing live benchmark's request/intake/independent-oracle pattern. It uses Engine final-text intake → Actions → existing BrainService/compiler/dispatcher → existing adapters → independent verifier. It constructs a scoped Actions shell to avoid the full live runner's shared-service and user-memory ownership. **No microphone was used**, and the fixtures are operator-prepared; this is not evidence of unrestricted natural-language autonomous discovery.

The benchmark instantiates the existing Journal and ScheduledQueue implementations in a dedicated qualification directory. It does not drain the user's production queue or add a parallel production scheduler/memory system.

[Acceptance oracles](../../app/jarvis/discovery/acceptance.py) inspect the actual compiled producer/verifier binding, fired/completed signals, completed outbox, content-addressed artifacts and passed verdict. They then independently check the saved numerical results. A supplied JSON report or pass boolean is insufficient. This is an audit of trusted local code/Journal records, not cryptographic attestation against an attacker who controls both the code and database. The oracles do not promote capabilities or scientific claims.

**Conditional clocks (D subset):** three `lab theory dilation` goals hold the coordinate interval at100 s and change beta from0 to0.6 to0.8. Actual proper times are100,80 and approximately60 s. The existing model compares an inertial SR clock with a Newtonian null and marks backward time travel unsupported; it assumes flat spacetime, constant subluminal speed, no gravity/acceleration/wormholes. These are conditional deterministic calculations, not newly measured clock experiments or a GR solver.

**DC circuit (E subset):** `lab simulate divider 5 V 1000 ohm 1000 ohm` and the same request at9 V ran in the existing reviewed non-root, network-disabled Docker sandbox. Actual outputs are2.5 and4.5 V. Source-current sign and Kirchhoff balance are independently checked. Native [5 V netlist](evidence/e-divider-0.cir) and [9 V netlist](evidence/e-divider-1.cir) are retained. Only supply changed; ideal resistor values stayed fixed. There is no temperature model, PCB/HDL result or physical measurement.

**Bounded study (F subset):** existing C4 Studies, TaskStore, ScheduledQueue and TaskState evaluated lengths0.5,1.5 and1.0 m under the same scenario. The1.5 m trial was retained as REJECTED_CONSTRAINT. The1.0 m candidate improved absolute error from0.5751002980005147 s to0.012098142789198185 s for the2 s target; its period is2.012098142789198 s. The owned first worker exited23 **after committing the first completed trial/checkpoint**, and the fresh worker completed only the two remaining queue tasks. This does not test an in-flight solver kill. Existing C4 fault-injection tests retain that separate coverage. A separate zero-budget study stopped at BUDGET_STOP. Existing approval gates denied prepared exports before any client access during the local run.

The one-shot stage markers are non-refundable. A stage with an uncertain outcome cannot be automatically replayed. Original goals, failed states, queue history and rejected candidates are preserved in the same qualification Journal. No new model calls, package/model downloads, paid service, image changes or shared-service starts occurred. Retained free-local counts are **SciPy25/50, Blender16/50, ngspice39/50**. Exhausted C3 grants remain untouched.

[Resource accounting](evidence/e-resource-accounting.json) retains eight settled records totaling1.813414747 CPU-seconds and180,347 result bytes. This is solver/process accounting, excluding full application/container startup overhead; it is not an end-to-end latency or VRAM measurement. The earlier denied study-only report preview remains PREPARED and uncreated; the separate two-create grant covers only the complete audit Doc and study Sheet.

## Approved Google outputs

The user separately approved exactly two creates and readback using [the complete prepared payloads](evidence/e-final-export-prepared.json). The full Doc contains the partial A1–H audit and explicitly says full acceptance/G/H are unmet; the Sheet contains the three recorded conditional pendulum periods and a SUM.

- [Jarvis Phase E partial qualification 2026-11-04](https://docs.google.com/document/d/1Yhe_Mb9zQxWbSTBmlzKrxZb-HrIDLrfz-NHN82FUX7k/edit)
- [Jarvis Phase E conditional study 2026-11-04](https://docs.google.com/spreadsheets/d/1t_NxqV_lMHYAfY7UoPmJrbGlz8uwJcFeDgc5qyHJNUw/edit)

[Successful create/readback receipt](evidence/e-google-reconciled.json). Both deliveries are VERIFIED. Google Doc readback compares all content lines with the documented import paragraph normalization. Sheet CSV readback checks literals, values and the SUM's computed result; it does not inspect native formula expressions. Destinations are My Drive root. No folder creation, sharing, deletion, paid use or new solver/model call was involved. Both Phase E create slots are consumed; D2's older grant was not reused.

[Initial export failure](evidence/e-google-live.json) remains retained: the helper incorrectly used the scratch folder as the credential base. Both Files constructors failed before the ledger's SENT boundary, with no Drive request or remote ID; deliveries stayed PREPARED. The helper was corrected to use the existing app account and scoped relative request paths. The original slots and uncertain goals were preserved, and exclusive known-not-started recovery markers recorded the inspected boundary before the same two authorized creates. This recovery is **not** permission to replay an ambiguous provider write. No credentials were copied, printed or reconnected.

The approved Doc is a fixed qualification snapshot. Subsequent regression summaries belong to the local terminal report; the remote content is not silently updated.

## Reproducible evidence

- [Complete bounded assessment and traces](evidence/e-local-acceptance.json): requests, neuron paths, source/input hashes, actual outputs, verdicts, evidence labels, queue/checkpoint/denial observations, original executed harness/oracle hashes.
- Exact [executed harness snapshot](evidence/e-harness-executed.py.txt) and [executed oracle snapshot](evidence/e-oracle-executed.py.txt). The oracle snapshot was recovered by reversing two later fail-closed checks in memory and accepted only after matching the original receipt's SHA-256; no application source was changed or executed during recovery. [Current frozen-code audit](evidence/e-current-audit.json) separately records the later replay.
- [Portable raw outputs and inputs](evidence/e-portable-outputs.json): eight original content-addressed result bodies, byte hashes and owned synthetic inputs, including all three SciPy trajectories.
- Native `.cir` sources above. Initial Windows capture used CRLF; the offline checker normalizes line endings only and compares every line with the solver's canonical LF netlist. It does not alter the captured files or substitute expected values for solver outputs.

From the repository root, using the existing environment:

```powershell
# Re-audit actual Journal receipts and numerical outputs; no new solver/model/API calls.
app/.venv/Scripts/python.exe -B app/benchmarks/live/discovery_lab.py --inspect
# Audit the portable outputs independently of the original Journal; no live rerun.
app/.venv/Scripts/python.exe -B docs/lab/reproduce_e.py --verify
# Guarded controlled regressions, not live provider/scientific acceptance.
app/.venv/Scripts/python.exe -B docs/lab/run_checks.py --receipt e-recheck.json tests/test_discovery_acceptance.py
```

The portable audit verifies captured bytes, clock arithmetic, circuit equations/native netlists, pendulum numerical checks and fixed-scenario comparisons. It cannot authenticate remote execution without the original receipts. `--run-local` is intentionally one-shot for the current owned run: do not reset its markers to obtain a second run. A new numeric qualification requires a separately named owned run and remaining authorized invocation capacity; do not overwrite this history.

No scientific render was generated. No plotting package was installed; tabular diagnostics do not substitute for the required native models/visualizations in unmet cases.

## Verification and next work

Pre-E focused baseline:255 passed on the exact D2 source. New oracle tests:14 passed, including altered artifacts, missing/forged traces, verifier rebinding, changed inputs, duplicate trials, failed subcheck visibility and mismatched regression evidence. Final focused suite: **269 passed / zero failures/skips**,115.266 s including setup. Strict neural mypy18 files and actual read-only host readiness pass. A post-success pyreadline console-finalizer warning appeared in the small oracle invocations; the test exit codes and receipts remain0, not a hidden test failure.

The final whole-project comparison is complete:5,342 passed, the same42 existing failure IDs and161 skipped; zero new or Discovery failures, no collection/setup errors, and unchanged focused/full source hashes. Guarded regression evidence does not make H pass. The original live snapshot retains its earlier exact oracle hash and a current audit rechecks the retained outputs without rerunning solvers.

A [local source/evidence checkpoint manifest](evidence/e-checkpoint.json) records the exact Phase E files and archive checksum. It excludes credentials, personal memory, runtime databases and unrelated working-tree files; it is not a full repository backup or Git release.

Next: implement the missing A1/A2 vehicle, B reference reconstruction and C hybrid workflows; extend D to a cited investigation and E to a sourced controller/logic case; then execute full cases, autonomous unknown-tool G and paired live H under concrete permissions. Keep the current working bounded paths, all invocation ledgers, remote IDs and pause state intact. Do not label the Lab complete merely because the acceptance harness runs.
