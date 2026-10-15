# Prompt09 — risk, approval and world-model audit

2026-10-15 IST. **31 catalog PASS /1 BLOCKED (JRV-09-006),0 FAIL/SKIPPED/NOT RUN.** All PASS entries have executed assertions; scope is isolated production boundaries, not live account or universal security acceptance.

Repo `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`. Windows/Python3.10.6, Ryzen7/32GB target, RTX3050 Laptop4GB from prior native observations; this module does not load a GPU/model. app/ is canonical; InsTAREELS alias not edited separately. Existing uncommitted work preserved. No external send/account write, personal delete, OS setting change, credentials, ability install, package/model download, commit or deployment.

## Source-map claims checked against actual implementation

| Claim | Actual source / stable entry points | Proof / limitation |
| --- | --- | --- |
| Risk and proposal policy | [deliberation.py](../../../../jarvis/deliberation.py):classify_risk/form_opinion/decide | Deterministic command-effect/text policy; confidence cannot lower risk; English ambiguity pauses planning; advisory rather than action authorization |
| Prediction and reconciliation | [cognition.py](../../../../jarvis/cognition.py):predict/evaluate/consolidate | Existing Beta posterior and failure lessons reused, not retrained; incorrect outcome appended to ledger without rewriting original decision |
| Action consent | [actions.py](../../../../jarvis/actions.py):_approve/_handle_opinion_feedback/_form_task_opinion | LiteralTrue per-action callback, qualified consent not approval, bare refusal cancels; fake file recycling and WhatsApp/Gmail transports |
| Card lifecycle | [island_desk.py](../../../../jarvis/island_desk.py):Approval.decide | Lock-protected one-shot response, cancellation,180s expiry/backward-clock rejection; actual GUI/human-origin acceptance not run |
| Owned opinion worker | [brain.py](../../../../jarvis/brain.py):BrainClient._request_once | Request deadline consumed before JSON wire, no shared timeout mutation; fake-clock expiry closes owned worker; no universal shared-transport serialization proof |
| Recovery | [task_recovery.py](../../../../jarvis/task_recovery.py), [gmail_writes.py](../../../../jarvis/gmail_writes.py), task_state.py | Persisted uncertain send refuses restart/replay; explicitly read-only retry capped at5 |
| Draft versus send | [gmail_api.py](../../../../jarvis/gmail_api.py), [whatsapp.py](../../../../jarvis/whatsapp.py) | Independent MIME oracle for draft-only and fake WhatsApp edit/preview/approve/readback journey; no live accounts |
| Unknown-program research | knowledge_acquisition/planner research tools | Advisory research exists; no deterministic mandatory gate for all unfamiliar programs. JRV-09-006 BLOCKED |


Dependency order: worker schema/effect taxonomy → proposal policy → action/card consent → journals/recovery → fault/concurrency → complete regression/readiness. Existing docs read: system-map.md, deliberation-engine.md, cognitive-architecture.md; candidate runtime sources all exist. A guessed task-recovery.md document is absent and is not treated as architecture evidence. Actual recovery implementation/tests supply proof. The seven-key active deliberation configuration retains its existing defaults; no user configuration was changed. Stable method/tool names remain compatible. No dependency added.

## Executed evidence

Baseline **47 PASS**,2.79s,[XML](existing-baseline.xml). New pre-fix regression **24 failing variants**,[XML](reproduced-failures.xml). Initial contract runs also exposed one missing re import (fixed), two incomplete fixture setups and over-specific filename error expectations (corrected, without weakening no-side-effect assertions); historical failure artifacts retained.

Final targeted **204 PASS /1 explicit BLOCKED skip**,13.21s,[XML](cases-and-contracts.xml). Full **2271 PASS /8 explicit BLOCKED skips**,343.28s,[XML](full-regression.xml),[actual completion output](full-run-completion.txt). Suites overlap; do not sum. Launcher **ready**,[redacted result](readiness.json). See [commands](commands.txt), [all32 catalog IDs/assertions](tests.jsonl). One existing pywinauto STA COM warning occurred; it is not classified as success. Readiness is configuration/service health, not live consent or production certification.

Safe applicable journeys: actual file-delete dispatcher refuses denied approval and changed fixture target with zero recycler calls; fake WhatsApp chooses a contact, revises a preview and sends exactly once only after approval, while denial types/sends nothing; Gmail draft MIME readback verifies no send. Crash/restart exercises persisted uncertain-write refusal. Five simultaneous ledger requests×20 rounds produce100 unique IDs and200 correlated rows; one shared card grants one decision among five callers. This does not prove arbitrary concurrent BrainClient requests safe.

The actual Models.predict/generate opinion path is exercised with fake installed-model discovery and local chat, cloud enabled, synthetic credential/email context, and a Groq dispatcher spy: private content reaches only fake local chat; Groq calls0; saved fields redact recognized markers. The worker-added model_used label remains compatible and advisory. Both successful and failed outcomes correlate with their original UUIDs. A late envelope test initially had incomplete discovery setup; preserved worker-metadata-reproduced.xml/worker-fixture-incomplete.xml are fixture failures, not additional baseline bugs. Inspection also caught overly strict rejection of worker metadata introduced during this audit; it was corrected before final acceptance, and worker-envelope-final.xml proves the actual boundary. An intermediate full run was interrupted to correct that fixture; only the final complete XML is the release evidence.

## Same-machine before/after

| Fixture | Samples | p50 ms | p95 ms | Peak traced Python bytes |
| --- | --- | --- | --- | --- |
| before_cold | 5 | 2.6669 | 2.9654 | 157587 |
| before_warm | 20 | 2.5702 | 2.8398 | 171498 |
| after_cold | 5 | 2.7349 | 22.1865 | 213370 |
| after_warm | 20 | 2.7286 | 3.0444 | 169871 |

[Raw50 samples](benchmarks.csv), [summary](benchmark-summary.json):500-row temporary rotating ledger;5 cold engine instances and20 warm writes/version, same input and interpreter. Final measurement ran after regression completed; initial and during-regression CSV/summary files are retained separately, not pooled or cherry-picked. Cold is not cold OS/model cache. Tracemalloc covers the operation, not whole host RAM. No model/audio work: TTFT, first audio and VRAM are not applicable, not zero. External side effects0; temporary ledger writes excluded from that count.100 additional writes/version verify500-row retention; redundant in-memory ID cache before=94,after=0. The before timestamp IDs may collide; after uses UUIDs.

Warm p952.840→3.044ms; cold p952.965→22.186ms. **No latency improvement claimed.** Keep validation/redaction/UUID correctness despite measured overhead; remove the unused unbounded cache. Streaming retention modestly reduces warm transient allocation, but cold import/allocation and tail latency increase. No broad RAM/GPU speedup claim; future optimization needs a fresh baseline.

## Limits and resume

JRV-09-006 requires a defined familiarity detector and a deterministic research-before-action policy before any general guarantee. The current planner can choose research; that is not proof. No unfamiliar program installed/executed. Live Windows consent provenance, spoofed-UI resistance, authenticated account sends, broad multilingual risk accuracy and model calibration were not executed; fixture results must not be used as those claims. English regex classification is conservative and incomplete. Recognized redaction patterns cannot identify all personal data; old local ledger rows are retained. Ledger errors expose only their exception class and do not grant permission. Shared process transport and multiple independent Deliberation writers are not certified by the single-instance concurrency fixture.

[Failures](failures.md), [changes](changes.md), [compatibility/current official sources](compatibility.md), [rollback](rollback.md), [exact changed files/hashes](files-changed.json), [scoped patch](source.patch). Production acceptance remains open.
