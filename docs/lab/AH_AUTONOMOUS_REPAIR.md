# Autonomous A–H repair — started 4 November 2026 IST

**IN PROGRESS. Full autonomous A–H acceptance remains unmet.** The user requires Jarvis itself to research, select methods, prepare inputs, execute and verify each scenario. Operator-authored case solutions, prepared case-specific experiment JSON, manual adapter calls, model/solver patches during live cases or weaker assertions cannot count as passes. Development fixtures and independent oracles are separate, labeled controlled tests.

Branch `lab/autonomous-ah-repair` preserves mixed earlier work. The old application repair campaign remains PAUSED_BY_USER; this request does not name or resume that campaign. Shipped Lab flags, models, quota/privacy policy and legacy control defaults stay unchanged.

## Fresh baseline and repairs

Requested full rerun: **5,342 passed /42 failed /161 skipped**,1754.797 s including setup, unchanged source `02ee9f4d047fe4eab146426f2b55f789d43060990fd2bdb04f96b86b39997303`. Receipt: `app/.jarvis-runtime/lab-validation/ah-baseline-full.json`. This guarded regression is not live H or autonomous science acceptance.

Persisted fixes:

- Coder/native coder incorrectly assumed optional actor runtime metadata was always path-like. `runtime_scope.optional_actor_base` preserves actual paths, invents no directory and grants no permission. The mandatory project and valid runtime roots are still checked by the existing unmodified pause barrier. Protected projects and corrupt pause metadata still stop before inference/writes.
- The architecture test compared the135-tool registry to an October129-tool snapshot. Existing inventory collection now accepts a fixture destination and returns current metadata. The test retains exact cardinality/state checks against a freshly collected snapshot; historical evidence is untouched. Static inventory is still not live capability proof.
- Restored the generic warning that execution alone does not locate the defect. No application repair body/answer is supplied to the worker.

**194 affected regression/pause tests pass**, no failures/skips,101.172 s including setup; source unchanged at `58facf87500836bd57eb7175e592710fb2b8b163a0c2373db210b78a47ddf769`. Restricted-context callback saving hit WinError5; the same host-context suite passed. Atomic-write safeguards were not weakened. A follow-up recheck passed41/42; the remaining toolkit fixture exposed missing Google create/save/upload intent matching. Specific intents were added while preserving the external-write approval gates. The configured fixture now supplies its OAuth prerequisite; negative provider checks remain intact. Final full-suite and paired live H checks remain open.

## Approved dependency setup

User approved [mechanics plan §1](AH_DEPENDENCY_PLAN.md): new `app/.venv-discovery-mechanics`, MuJoCo3.17.0, Trimesh5.2.0, Matplotlib3.11.2;21 hash-locked wheels,53,396,303 wheel bytes,287,464,991 owned disk bytes. Existing application/Pint environments, PATH, drivers and defaults are unchanged. Fifty bounded CPU calls are authorized;4 have been consumed across initial and final-worker goldens. The final worker passes free fall (maximum position error1.55e-15 m) and rigid-sphere pendulum (period relative error3.34e-9). These are canonical numerical checks, not autonomous A–H acceptance. Host execution of generated scripts is not authorized.

Pins, official URLs/hashes, retained license texts and installation receipt are under `.jarvis-runtime/lab-validation/ah-mechanics-setup`. Bundled exceptions/notices are retained; no uniformly permissive/redistribution claim. PyOpenGL main license text missing from its wheel was retained from official upstream separately. A UTF-8 preparation-helper failure was corrected by reading its already-completed resolution report; the environment was not recreated.

**Chrono planning approval is still pending.** Official metadata lists a527 MB PyChrono10.0.0 Windows package plus CUDA/MKL dependencies. No micromamba/Chrono download/execution/install has occurred. [Concrete planning scope](AH_DEPENDENCY_PLAN.md). Other new packages, including PyBaMM, are not approved or installed.

## Autonomy work

Added `discovery_call` to the existing tool registry/native planner. It delegates supported Lab commands to the same compiler/dispatcher, persists model-authored typed JSON as unverified assumptions, keeps parent task/child goal references and refuses automatic replay after uncertain execution. Help progressively discloses input schemas. Two new primitive-mechanics neurons use strict SI bodies/joints/masses/shape offsets, a fixed owned MuJoCo CPU worker and independent trajectory/source/receipt checks. Inventory is44 owned Lab neurons/39 templates plus the gated core delegation tool. No contacts, actuators, vehicle tires, strength or external meshes are supported by this adapter. Full A–H cases are not yet demonstrated.

The initial integration/repair regression set passed142/142 (93.172s including setup), source e129d05741b85c03a1881c7086850b8495f313a4a9e0f3dfcfe5004a67d47114. Final hardening added bounded worker CPU-loop checks, exact trajectory dimensions/MJCF correspondence/checksum checks and a real conditional-clock child-workflow fixture. Final targeted and full-suite reruns follow. No second brain/router/store/queue, no A–H answer templates or operator-authored solutions.

Then execute raw A1/A2/B/C/D/E/F/G/H requests with actual model/parent/tool/child traces. G needs autonomous gap detection/research/adapter+skill/golden registration and fresh-session reuse; the earlier reviewed installed-tool demonstration cannot substitute. H needs full regressions, paired live control accuracy/latency and observed idle resources. All gates remain open until those checks genuinely pass.

Live counters stay SciPy25/50, Blender16/50, ngspice39/50; no grants reset. C3 scratch grants remain exhausted. D2/E Google create grants are consumed; no new external writes/sharing/deletion. Firecrawl documentation search/scrape reported3 credits; feedback failed validation and no refund is claimed. [Official metadata receipt](evidence/ah-official-dependency-metadata.json) is a compatibility audit, not an install or runtime success.

Next: continue runtime fixes and autonomous verification, maintain cumulative handoff, and rerun the entire source-stable suite after implementation. Do not stop at another operator-assisted demonstration or report full A–H success from unit tests.

## Regression confirmation — 5 November 2026 IST

The source-stable diagnostic whole suite completed **5,418 passed /1 failed /161 skipped**,2020.282s including setup. All42 original failure IDs passed. The sole new failure was `test_tools.py::ToolTests::test_catalog_planner_and_executor_agree`: the delegation tool introduced an unnecessary backend. It now uses the existing toolkit backend, also ensuring its returned scientific data reaches the normal planner instead of requiring desktop verification. [Sanitized diagnostic receipt](evidence/ah-full-diagnostic-2026-11-05.json).

Strict neural typing exposed an annotation redeclaration introduced with the new compiler route. It is corrected; all18 neural files pass. The synthetic control-benchmark World now replaces every reader, including Gmail draft bodies, so an empty-world oracle cannot call a live account reader. No oracle success assertion was removed.

Final affected checks: **80 passed /0 failed/skipped**,78.234s including setup. This includes the ordinary planner consuming an actual child Lab result, with synthetic model proposals explicitly labeled as controlled verification. Source `17d480d0fac19715ff4ce82d1b4e5cfc2e85143f5d1eea7754278e2741a3f4aa` uses the expanded v3 fingerprint (including live benchmark Python and three verification helpers). Earlier v2 hashes remain historical. Full confirmation is running; no full regression or A–H completion is yet claimed.

## Native fixture and source-history follow-up

The first confirmation completed **5,419 passed /1 failed /161 skipped**,1858.656s including setup, source17d480d0fac19715ff4ce82d1b4e5cfc2e85143f5d1eea7754278e2741a3f4aa unchanged. All42 original IDs and the corrected backend check passed. The failure was `test_media_metadata_multiple_sources_and_missing_properties_are_explicit`,15.372s, matching the fixture's15s subprocess deadline. The guarded receipt intentionally omits raw assertions, so this is deadline evidence rather than a full native-cause diagnosis. Six direct checks and20 isolated repeats passed; that alone did not certify the issue resolved. [Retained confirmation diagnostic](evidence/ah-full-confirmation-diagnostic-2026-11-05.json).

The fixture now launches exactly one allowlisted read-only test in isolated Python, waits up to30s for native projections/test imports to announce readiness, then keeps the original15s assertion/clean-exit window. No retry or assertion removal; malformed readiness, startup timeout and nonzero exit are tested. Only the owned child is terminated; Jarvis's live8s media deadline and user playback remain unchanged. A package-import collection error during this repair was corrected and retained as a failed preflight.

A source-history review also found that rewording C3 input provenance could try to overwrite an immutable Source in an older clock project. Matching historical locator/hash records are now reused; mismatches still fail. A real conditional-clock regression verifies the prior source revision remains unchanged.

Final focused checks: **143 passed /0 failed/skipped**,69.469s including setup. Strict neural typing passes18 files. Final frozen source: `d28fbb411653369e7507d25f1e4c6fa705a962bf72681b00dfc40720dd160988`. Full run `ah-full-final-2026-11-05.json` is active; its sanitized progress ledger passed3,400 reports with0 failures, beyond the old failure point. Do not claim completion until the terminal receipt and source comparison pass.


## Certified regression checkpoint and native interface follow-up — 5 November 2026 IST

The terminal source-stable run completed **5,425 passed / 0 failed / 161 skipped**, 1755.281 seconds including setup. All42 original failures are resolved. Source remained `d28fbb411653369e7507d25f1e4c6fa705a962bf72681b00dfc40720dd160988`; matching strict neural typing passes18 files. [Sanitized terminal receipt](evidence/ah-full-final.json). Skipped live/opt-in gates remain unexecuted, not passes. A private code-only checkpoint preserves this certified source without credentials/config contents/runtime data.

The first actual natural-language mechanics probe failed before solver execution: the native model supplied a procedure name as the command and the decision model concluded no solver was available. Four local model calls, zero solver calls; raw v1 trace retained. This exposed a production interface gap beyond the controlled integration tests.

The new stdlib-only native transport uses `operation=help|run`, explicit session-enabled schema topics and a JSON request object. Requests lower to the existing delegated tool/compiler/dispatcher; no new planner or approval grants. Read-only help may use existing prerequisite navigation, while runs retain conservative decision, resource and independent verification gates. Help now reports installed canonical-worker qualification and explicit model limits. Mechanics rejects sample intervals that would omit the final requested time. No case inputs or numerical answers are embedded in these changes.

The real isolated brain interpreter successfully parsed the transport without Pydantic or inference. **95 focused checks pass**, zero failures/errors/skips, source unchanged `82df4c4df44f246303972c791e30898dbcb570d33770bb966c3cbf823bd212b6`; strict neural typing18 files passes. Initial restricted-context checks retained temporary-write errors; the guarded runner now uses unique workspace-owned temporary roots for pytest and unittest. A missing parent-directory preflight was corrected before the passing run.

The live v2 probe could not reach localhost in the tool sandbox (WinError10013); it stopped before inference/solver execution. A read-only check outside the sandbox confirmed the existing Ollama service version0.40.0. A fresh bounded v3 attempt uses the same raw goal and unmodified installed local model, with no prepared case JSON. It does not restart shared services. Its actual outcome and full current-source regression recertification remain pending. Full A–H acceptance remains unmet.


### Native history correction and real primitive-mechanics proof

A second source review found that fresh native conversations reconstructed completed Lab calls using legacy value/content arguments. They now rehydrate through the current stdlib help/run transport; invalid historical calls fail rather than teaching an unexecutable schema. Full bounded Lab schema output is retained instead of a partial1500-character fragment. A regression verifies the exact advertised history call and the final schema field survive. Help includes the actual invocation contract, and transport validation reports the particular missing operation/expected field without weakening strict input checks.

Final focused run: **96 passed /0 failed/skipped**,45.469s including setup, unchanged source28ec73a90165d386e2cc8b52dc31c139739c7b6cf0e43778f746ff36f31b3c61. Actual isolated-brain transport/history import succeeds without Pydantic or inference. [Sanitized live diagnostics and terminal smoke](evidence/ah-native-autonomy-diagnostics.json) preserve all failed attempts separately.

**Live v5 autonomous primitive-mechanics smoke passed**,252.813s, five instrumented local model calls and one actual MuJoCo invocation. Jarvis itself read help, generated the case JSON, executed its existing dispatcher/worker/verifier and reported the result. The independent post-run oracle binds the actual requested inputs to the producer outbox, child verification and solver receipt; final z1.8037999999999998m agrees with the analytic reference. No prepared case JSON, solver/model patch, supervisor numerical answer or external write was supplied. This is a narrow conditional physics smoke, not full Test B or A-H acceptance. Total mechanics calls5/50; no other grant was reset.

Current full-suite recertification is running on frozen source `faaae8308e886fda9a90327b5458c710f26270efc060bdf7804ec4601d0da7ca`; matching strict neural typing18 files passes. Terminal receipt will be `ah-native-full-2026-11-05.json`. Source remains fixed until it finishes. Full autonomous A-H, paired live control/latency and idle-resource gates remain unmet.


### Completed full diagnostic and runner path correction

The full post-interface diagnostic completed **5,439 passed /1 failed /161 skipped**,1818.188s including setup, with unchanged sourcefaaae8308e886fda9a90327b5458c710f26270efc060bdf7804ec4601d0da7ca. All42 original failure IDs passed. The sole failure was `test_cloud_coding_routes.py::CloudCodingRoutes::test_two_local_function_rejections_allow_one_bounded_cloud_handoff`, stopping conservatively when nested candidate checks could not all complete. [Sanitized full diagnostic](evidence/ah-native-full-diagnostic.json).

Controlled isolation reproduced the same failure with a long workspace temporary root (1 failed,2.23s) and passed with a short owned root (1 passed,3.07s), using the test's network-deny doubles. Application guards/assertions were unchanged. The guarded runner now keeps uniquely owned unittest/pytest roots under `app/.jarvis-runtime/t/<run-id>/u` and `/p`, avoiding the long validation-receipt prefix in nested subprocess workspaces. It still denies live credential/network/model/Blender access. Affected short-path checks and a fresh complete source-stable confirmation are required; this diagnostic is not a pass.


The shortened-root affected suite passes **137/137**, zero failures/errors/skips,48.703s including setup, source unchanged `7569cd7960d56ba36c50e6a4620fefebc2e83afa16b37f2904e79e78b800e7c3`. This includes the previously failing handoff fixture, execution-contract candidate checks, typed Lab transport/history, planner access and native tools. Matching strict neural typing18 files passes. Whole-suite confirmation `ah-native-full-confirmation-2026-11-05.json` is running with source fixed; terminal receipt still required.


### Completed confirmation and mouse-event correlation follow-up

The confirmation completed in the background across a turn interruption: **5,439 passed /1 failed /161 skipped**,1797.250s including setup, source7569cd7960d56ba36c50e6a4620fefebc2e83afa16b37f2904e79e78b800e7c3 unchanged. All42 original failure IDs and the short-path candidate fixture passed. The sole failure was `test_P05_real_hook_classifies_injected_input_and_cancellation_stops`, at the assertion that every global captured event was injected. The retained sanitized receipt does not distinguish an empty capture from mixed physical/injected input, so an exact native cause is not asserted. [Confirmation diagnostic](evidence/ah-native-confirmation-diagnostic.json).

The fixture could not correlate its own two injected moves with the global mouse stream. The existing hook protocol now carries ephemeral Windows extra-info metadata, retaining the existing five-field event tuple and legacy four-number packet compatibility. Tags never grant trust or change injection classification; only Windows injection flags classify events. The live fixture tags its own one-pixel out-and-back moves, waits within a3-second bound, and verifies its own tagged events while allowing unrelated user input. Lost foreground focus with no observed owned event is explicitly blocked/unexecuted. No clicks, background service changes, stored extra metadata, consent changes or injection-policy relaxation.

Pure tests cover concurrent physical/injected events, forged tags with non-injected flags (still user input), tuple unpacking, legacy/malformed packets and bounded queue overflow. Initial affected qualification **71 passed /1 skipped**,43.500s including setup, stable sourcef1af55e132c9e7c1c84b04081db0e836bd4073e8a94c248808d501632f7fc066. The actual tagged native hook test passed in2.549s; the skip was the existing opt-in sandbox advice test, not the hook. Final expanded qualification and a full stable-source run remain required.


Final affected hook/native/candidate qualification: **136 passed /1 existing opt-in sandbox skip**, zero failures/errors,81.344s including setup; unchanged source `42c8fda3ba0d6bd5bd7a16223b1204952944af7af55750ff4eae9988d31cd508`. Matching strict neural typing18 files passes. Whole-suite run `ah-hook-full-confirmation-2026-11-05.json` is now running on this fixed source. Do not claim its gate passed until its terminal receipt and source comparison pass.


### Checkpoint durability, legacy hook compatibility and current confirmation

The42c8fda3 whole diagnostic completed **5,425 passed /1 failed /177 skipped**,1703.219s including setup, unchanged source; all42 original IDs passed. The failure was the unchanged20-round shared-job oracle, a PermissionError at the private checkpoint atomic rename. Extra skips occurred while Docker/Ollama were unavailable. [Retained diagnostic](evidence/ah-hook-full-diagnostic.json).

SandboxJob.save now reuses the existing bounded checkpoint commit helper through an owned write wrapper: fsynced pending bytes, root confinement, at most four known Windows sharing-failure commit attempts, rejection if source/target changes, and pending-file retention on failure. No Docker command or sandbox write is replayed. The global SkillMemory writer was left unchanged. Tests inject a transient sharing error, a competing writer, permanent denial and destination escape; the original20-round oracle remains intact.

The internal mouse subprocess protocol now explicitly selects v2 for new readers. Legacy `--hook` emits the original four-number stream so a Jarvis parent loaded before this update can still start its child; new readers accept legacy/current packets. Tags remain correlation data, not authority. Both protocol formats, explicit v2 selection and live tagged input/cancellation are tested.

The user approved the bounded existing-service start plan. Its one-shot procedure found both services already available, launched/restarted nothing, performed no inference, and reported launcher readiness ready in25.875s. Prior unavailable snapshots remain historical; no service-state cause is inferred.

Final affected checks: **227 passed /12 existing opt-in skips**, zero failures/errors,103.610s, unchanged source `e157754d0b3a682d69f61a1124a583fd1c8740f8f91fb2499cfff3af7fa29f87`; strict neural typing18 files passes. Complete confirmation `ah-complete-confirmation-2026-11-05.json` is active on that fixed source. No terminal success is claimed yet. Full A-H/live H remains unmet.


### Shared metadata writer recovery and isolated test ownership

The e157 complete diagnostic was deliberately stopped after two failures in experience-memory context-budget/retention tests. No terminal receipt was written and no whole-suite pass is claimed. Both exact error shapes reproduced with a single controlled Windows sharing denial on Jarvis Experiences.json. [Interrupted diagnostic](evidence/ah-complete-interrupted.json).

The shared SkillMemory.atomic writer now uses the existing guarded owned-metadata commit helper as well as SandboxJob.save. This treats transient sharing failures consistently across memory/projections/caches without replaying any external action. Permanent denial, changed metadata, corrupt indexes and unavailable memory still fail safely. Pending metadata is retained for inspection. Existing checkpoint verification budget is32MiB/file; general asset/source writes are unchanged. Both original experience test methods pass with an injected one-time sharing denial.

Test workspaces now use ignored root `.jtmp/<run-id>/u` and `/p`, outside live application/runtime ancestry. This preserves short Windows paths and avoids synthetic fixtures being attributed to live application roots by recovery/project-discovery helpers. Previously created files/logs were not deleted.

Final affected qualification: **269 passed /12 existing opt-in skips**, zero failures/errors,137.562s including setup, unchanged source `385190a64cc7def723ef285777cf3df93f9292b6fbd964acd24464f3819ffc2c`; matching strict neural typing18 files passes. Full `ah-shared-commit-full-2026-11-05.json` is running on this fixed source. Terminal result and coverage comparison remain required; full A-H/live H remains unmet.


### Complete metadata diagnostic and same-file coordination

The385190 diagnostic completed **5,447 passed /3 failed /161 skipped**,1680.969s including setup, unchanged source; all42 original IDs passed. Remaining failures: deliberation audit case17 (100 decisions/200 rows), fact-store five-writer20-round oracle, and model-routing concurrent metadata commits. [Retained diagnostic](evidence/ah-shared-commit-diagnostic.json). The deliberation loss reproduced under one controlled sharing denial. A first reproduction call used the wrong positional argument order and was corrected; it was not a valid pass/fail qualification.

The separate deliberation/fact JSON/generated-view writers now use the existing guarded metadata helper. Canonical per-file RLocks serialize in-process writers, with weak retention to avoid an unbounded lock registry. Independent files remain concurrent. External-writer changes, permanent denial and uncertain commits still refuse automatic retry. Routing/approval/quota/business decisions are unchanged. The original generated-view failure oracle now injects at its new commit boundary; its primary-fact consistency assertion remains and pending view retention is also checked.

Expanded qualification: **361 passed /17 existing skips**, zero failures/errors,125.703s, unchanged code source1ed3644a43e985a8f3043d3678129e16b822bd5e6a206b915ba6d011afc5e882. Includes original stress oracles, sharing denial on both fact JSON and view, same-file concurrency with one denial per writer, independent-file concurrency, changed-target/permanent-denial refusal, experience recovery and hook interoperability. A nonexistent selector in the first focused preflight was corrected and retained; no tests ran in that failed preflight.

After a descriptive manifest update, fixed source is `ff1c466ffe77bd9788e2440b0227f038802644970787d79fceee56848dbe9146`. Strict neural typing18 files passes; full `ah-serialized-metadata-full-2026-11-05.json` is running. Full gate/coverage and A-H acceptance are not claimed until actual evidence supports each scope.


### Reviewed private-state writer consolidation

The ff1c diagnostic was stopped after `test_P05_restart_recovery_keeps_steps_but_needs_fresh_consent` reported PermissionError. No terminal receipt was written; no complete result is claimed. [Interrupted diagnostic](evidence/ah-serialized-interrupted.json). The private demonstration-session writer was another direct rename path. Remaining reviewed private metadata integrations were consolidated to prevent the same commit mechanism being corrected one caller at a time. Existing payloads/business rules and all non-metadata effects remain unchanged. [Exact scope/exclusions](OWNED_METADATA_COMMIT_AUDIT.md).

A deterministic demonstration save/resume sharing-denial test checks that recovery never grants consent. Failure instrumentation now captures integer errno/winerror and owned source-stack locations only; no messages, locals, assertion values, private paths or desktop content.

Qualification across51 existing directly affected modules: **1,314 passed /30 existing opt-in skips**, zero failures/errors,532.562s including setup; unchanged source `348e252a1d21dadcecf735b1c0ebca91259736c360d98c9117451d21912dd79d`. Strict neural typing18 files passes on the same source. At this intermediate checkpoint, `ah-consolidated-full-2026-11-05.json` was still running on that fixed source, so whole-suite/coverage gates were not yet certified. Its completed result is recorded below; full A-H acceptance remains open.


## Final regression gate — 5 November 2026 IST

**5,456 passed /0 failed /161 skipped**, zero errors/collection errors,1724.485s including setup. Source before/after is `348e252a1d21dadcecf735b1c0ebca91259736c360d98c9117451d21912dd79d`, matching current source and strict neural typing18 files. [Terminal regression](evidence/ah-final-regression.json). All42 original failure IDs resolved. Against the prior5,425-pass checkpoint, no prior pass became failed, skipped or missing;31 new passing IDs, unchanged161 unexecuted opt-in/live skips. [Coverage comparison](evidence/ah-final-coverage.json). Final [read-only readiness](evidence/ah-final-readiness.json) reports ready; no service launch/restart or inference was needed for that check.

Private code-only checkpoint `app/.jarvis-runtime/lab-validation/checkpoints/ah-regression-348e252a1d21` preserves803 files/10,101,510 uncompressed bytes; ZIP SHA256`e586503d360e3d8ceab9fc1ef5ad8f737c26040b389c96990dd78bd92fa1c193`. Configuration contents, credentials, model weights, recordings and runtime/project data are excluded. Inspect manifest and preserve mixed user work before any restore. No commit/push/reset/clean or unrelated-file rollback was performed.

The [metadata audit](OWNED_METADATA_COMMIT_AUDIT.md) defines reviewed integrations, excluded effects and fault tests. The real [autonomous primitive-mechanics smoke](evidence/ah-native-autonomy-diagnostics.json) remains a narrow conditional proof, not Test B or full A-H. Mechanics5/50; no other proof quota reset. Shipped Lab flags remain false and the old campaign remains PAUSED_BY_USER. C3/Google grants remain exhausted; pending Chrono planning approval is unchanged.

**Full A-H/live H/scientific/release acceptance remains OPEN.** Next work must fix Jarvis so it independently performs the actual scenarios with lawful sources/native assets, physically appropriate solvers, controlled comparisons, interruption/resume, gated learning and fresh-session reuse. No supervisor-supplied case JSON/answer or forged acceptance score. G and H remain independent mandatory gates. This regression checkpoint completes the requested repair/testing stage, not the complete Lab.
