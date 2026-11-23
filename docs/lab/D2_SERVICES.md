# D2 existing-service adapters — 4 November 2026 IST

<!-- D2 CURRENT BEGIN -->
## Current terminal status

Final frozen-source whole-project regression: **5,328 passed / 42 failed / 161 skipped**, 1592.656 s including setup; 0 new failure IDs, 0 resolved IDs and 0 Discovery failures against the pre-D2 baseline. The exact failure comparison and unchanged source hashes are retained in the terminal receipt. This does not make the pre-existing defects green.

Focused:255 passed, 109.532 s including setup; source `7e0d7d5206cd8642a6ef08ef5ec05547c893646f608e61ae0552fa67b15560f9`. [Focused receipt](evidence/d2-final-focused.json) · [Static/choice evidence](evidence/d2-static-and-choice.json) · [Terminal comparison](evidence/d2-full-final.json)
<!-- D2 CURRENT END -->

D2 adds 15 typed neurons to the existing Neural Execution Brain, bringing the built-in Lab inventory to 42. It reuses Google Files, ExtensionRunner, deterministic scouts, public research search, local Laya and ScheduledQueue. It adds no planner, router, database, queue, package, model or always-on service. Shipped Lab flags remain false; the existing act/learning-shadow and legacy control defaults remain unchanged. The autonomous repair campaign remains PAUSED_BY_USER.

Implementation and controlled checks are complete. Actual approved Google creation/readback, scoped long reading, public owned-browser reading and resident CPU choice have passed. Final regression results are recorded below when terminal. **Microphone/spoken acceptance, authenticated scientific portals and long overnight operation are unexecuted.** This is service transport qualification, not full scientific or release acceptance.

## Contracts and reuse

| Capability | Existing owner and behavior |
|---|---|
| `discovery.source.from_drive` | Existing C1 Drive source adapter and Google Files; source context and content hashes in existing LabMemory/Journal |
| `discovery.literature.portal_read` | Existing extension, public HTTPS policy, fresh owned session, AX frame snapshot, bounded text and one owned-session cleanup attempt |
| `discovery.literature.read_long` | Existing deterministic scouts over a scoped UTF-8 text file; explicit partial coverage, no model synthesis |
| `discovery.literature.background` | Existing public search plus at most two bounded owned-session page reads; extractive unreviewed snippets/excerpts with citations |
| `discovery.choose.option` | Existing exact name matching, otherwise existing already-resident CPU Laya; at most eight options, threshold 0.9, no cloud backup |
| `discovery.jobs.queue/status/pause/resume/cancel` | Existing C4 Studies and ScheduledQueue/TaskStore; selected study and owned tasks only |
| `discovery.export.prepare` | Typed local export payload from a stored report or checked solver/code metric; full preview before approval |
| `discovery.report.to_doc`, `discovery.table.to_sheet` | Existing Google Files; new files only in an explicitly selected existing folder |
| `discovery.export.inspect`, `discovery.verify.d2` | Known-ID read-only reconciliation and independent receipt/full-content verification |

All contracts are listed in [the descriptor file](../../app/jarvis/discovery/neurons/integration.json). [D2 composition](../../app/jarvis/discovery/d2.py) plugs into the existing compiler/dispatcher. New domain code lives in model/delivery.py and adapters/delivery.py, lab_reads.py and lab_jobs.py. The [service skill](../../app/jarvis/skills/discovery/service-delivery/SKILL.md) documents these bounds. Runtime dependencies remain unchanged.

The 15 new Capability memory records default to `UNVERIFIED`. Transport goal verification and the controlled golden harness do not automatically promote them through the existing learning lifecycle or establish a scientific claim. The 38 known workflow templates include the composed background-to-Doc path.

The additive `discovery_deliveries` and owned-task index tables live in the same Journal. Delivery states are PREPARED → SENT → CREATED → VERIFIED, with UNCERTAIN retained on ambiguous failure. Payload hashes prevent duplicate creation even through copied request files. A lost creation response with no returned ID cannot be retried. Known IDs can be inspected without creating or overwriting anything. Reports, request hashes and actual handler receipts bind verification to the executed request; caller-provided success text is insufficient.

## Commands and inputs

Run through existing text/voice intake with the brain active and the applicable Lab flags enabled in an explicitly scoped configuration. These examples do not authorize changing shipped settings.

```text
lab export report "examples/discovery/d2-report.json"
lab export table "examples/discovery/d2-table.json"
lab export inspect "delivery-<64 hex characters>"
lab source drive "your document query"
lab source drive-id "known-file-id"
lab portal read "https://mujoco.readthedocs.io/en/stable/overview.html"
lab read long "examples/discovery/d2-long.json"
lab background "public research topic"
lab background doc "examples/discovery/d2-background-doc.json"
lab choose "examples/discovery/d2-choice.json"
lab jobs status "study-<32 hex characters>"
lab jobs queue "study-<32 hex characters>"
lab jobs pause "study-<32 hex characters>"
lab jobs resume "study-<32 hex characters>"
lab jobs cancel "study-<32 hex characters>"
```

Replace placeholder artifact/experiment and existing Drive parent IDs before exporting. Report requests contain title, parent_id and a stored artifact_id; table requests contain title, parent_id, experiment_ids, metric and source_path. The prepared complete payload is stored under `.jarvis-runtime/discovery/deliveries/` and shown before the existing approval gate. There is no folder creation, sharing, deletion or update operation.

Long requests contain source_file, question and budget (1,000–9,000 characters). Supported scoped input types are JSON, TXT, Markdown, CSV and HTML; credential paths are refused. Choice requests contain intent and 1–8 bounded option IDs/labels. Background Doc requests contain query, title and parent_id; search/read → source verification → prepared preview → approval → create → readback is one guarded brain path. The composed path is controlled-tested; no additional background Doc was created during qualification.

Raw source content remains untrusted. Portal/long excerpts omit whole credential-like lines, retain other lines unchanged with input spans, and explicitly mark partial coverage. The shared credential guard remains unchanged. Derived retained excerpts have an explicit hash scope; they do not stand for a complete paper. Portal operations never read user tabs, enter login data, upload/download or bypass challenges. An uncertain browser operation is not automatically replayed. Jobs never unpause the global queue; started/uncertain dispatch cannot be silently resumed.

## Actual qualification and retained failures

The user approved exactly two creates and readback, in My Drive root, using the [prepared payload](evidence/d2-live-prepared.json). Both slots are consumed; no repeat creation is authorized by that grant.

- [Google Doc: Jarvis D2 qualification report 2026-11-04](https://docs.google.com/document/d/1MlR8MOHjs2kYyaT2eqqopeEu0suxi_1GZ3qPUfxelUE/edit) — complete retained conditional C4 report read back; also read as a Drive source through the neuron.
- [Google Sheet: Jarvis D2 qualification sheet 2026-11-04](https://docs.google.com/spreadsheets/d/1to1tbmtKwRHQZYSpLko3jx2cWUKQqCv427Zw3MEX7TU/edit) — periods 1.4248997019994853 s and 2.012098142789198 s, literals and the generated SUM's computed result checked against CSV readback. The existing Drive export returns computed values; native formula-expression introspection is not implemented. These are retained model results, not physical measurements or a new solver run.

[Google receipt](evidence/d2-google-live.json). Initial Doc creation succeeded but Google import added an empty paragraph; strict readback correctly failed. [Diagnosis](evidence/d2-doc-readback-diagnosis.json) is retained. The compatibility fix normalizes CRLF, outer whitespace and repeated empty paragraph separators while comparing every content line. A known-ID read-only reconciliation then passed, with no repeated create. Tail corruption still fails tests.

[Existing-service receipt](evidence/d2-services-live.json): real scoped long-read 0.313 s; exact choice 0.062 s. The already-resident CPU Laya branch selected `red` at 0.9848 confidence in 0.968 s. One five-unit CPU admission reservation is retained because separate-process CPU is unknown. No model was loaded/started or switched; no cloud backup or C3 scratch grant was used.

The initial public portal goal `g-da010af21bbe43fe` reached/read/closed its owned session, then the Journal refused credential-like page text. That uncertain goal remains unchanged. The fix extracts unchanged safe lines and keeps omissions visible instead of weakening the credential guard. A separately recorded corrected read verified in 2.421 s, closed its owned session and retained a partial 20,000-character excerpt with three unsafe lines omitted. [Corrected receipt and source spans](evidence/d2-portal-corrected.json). No Google write or model call occurred in the corrected read.

All live checks used operator-assisted final text ingress through Engine/Actions/brain; **the microphone was not used**. Browser and CPU service were already connected/running. No service restart, install/download, paid API, folder creation, sharing, deletion or global activation occurred. Free-local counters remain SciPy22/50, Blender16/50 and ngspice37/50. Earlier C3 grants remain exhausted and must not be reset.

## Verification and remaining gates

The privacy-final domain/wiring run passed 47 tests. Controlled transports exercise the real brain, approval and Journal paths: denial/input mutation, unknown-write no-retry across reopen, known-ID reconciliation, full Doc/Sheet/formula checks, solver/version/design/scenario/value consistency, source paths, secret filtering, scoped browser cleanup/login refusal, CPU health/confidence/NaN/abstention, budget retention, owned job controls/uncertain resume, default-off refusal, composed background export and final-STT-text normalization. Controlled mocks are not presented as live provider evidence.

Repository-configured neural mypy passes all 18 files. Frozen-source focused/full regressions and readiness are summarized in the current progress/handoff entries and terminal evidence receipts. Reproduce from the repository root using the existing environment:

```powershell
app/.venv/Scripts/python.exe -B docs/lab/run_checks.py --receipt d2-recheck.json tests/test_discovery_delivery.py tests/test_discovery_wiring.py
app/.venv/Scripts/python.exe -B docs/lab/run_checks.py --receipt d2-regression-recheck.json tests
```

These guarded regressions deny production credential reads and external/model/Blender traffic. They cannot prove live voice/UI/control accuracy/latency. The pre-D2 baseline has 42 known failures; compare exact IDs rather than treating the whole suite as green. Prior defects, G/H, full A–H science, native CAD/meshing/FEM/CFD/vehicle/HDL and physical validation remain open. D2 does not promote a scientific capability or claim experimental support merely because a transport verifier passes. No commit or push was made from the mixed working tree.

Terminal receipts and exact-ID comparison are complete: 5,328 passed, the same 42 existing failed, 161 skipped; zero new or Discovery failures, matching focused/full source fingerprints. Next: separately scoped live spoken/approval-UI, signed-portal and durable long-run qualification. Keep the two-create ledger and remote IDs intact; inspect existing outputs instead of recreating them.
