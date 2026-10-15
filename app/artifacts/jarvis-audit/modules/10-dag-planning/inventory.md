# Prompt10 — hierarchical DAG and verified plan-cache audit

2026-10-15 IST. **32 catalog fixture PASS;0 FAIL/BLOCKED/SKIPPED/NOT RUN.** Live acceptance remains unverified. Module completion is not whole-system production certification.

Repo `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; Windows/Python3.10.6, bundledSQLite3.37.2; Ryzen7/32GB/RTX3050 Laptop4GB target from earlier native observations. No new GPU/model work here. app/ is canonical; InsTAREELS alias not separately edited. Existing dirty changes preserved. No account send/write, personal deletion, OS mutation, ability install, credential setup, package/model download, commit or deployment.

## Source map, graph and execution order

| Claim | Real implementation / stable entry points | Executed boundary and limit |
| --- | --- | --- |
| Typed DAG/dependencies | [dag_execution.py](../../../../jarvis/dag_execution.py):validate_plan/references/resolve | Unknown/cyclic plans rejected, three reads synchronize concurrently, downstream waits for typed result, wrong type fails before use |
| Serial effects and consent | Executor.run/work + existing tool authorize/call | Per-graph writes serialize even without resource labels; fresh admission/worker checks; fake draft→approval→send ordered/denied; actual mail stays specialized |
| Restore/recovery | Executor.run restored, [task_state.py](../../../../jarvis/task_state.py):update_dag, [task_recovery.py](../../../../jarvis/task_recovery.py) | Exact-step/resolved-argument SHA256 binding and fresh verification; disk restart reuses safe read, changed input reruns; any uncertain effect refuses replay |
| Task ownership | [hierarchical.py](../../../../jarvis/hierarchical.py):run/scoped_authorize/checkpoint | Current UUID bound to DAG updates/authorization; stale task cannot overwrite newer task state; optional legacy API callers must opt in |
| Verified templates | MacroMemory.lookup/remember, fingerprint | Deleted tool changes signature, corrupt/oversized JSON is miss, candidate revalidated; read-only only, recognized credential templates omitted; old rows retained |
| Fingerprint reuse | implementation_hash/fingerprint | File identity/size/mtime/ctime checked, content digest reread after change, bounded64-entry lock-protected cache; not anti-tamper against metadata forgery; Windows ctime is creation time |
| Resource/replan bounds | hierarchical.run + Executor | Low-RAM fixture serializes, nonzero GPU reservation rejected, failed read replans once then pauses, three read retries capped; worker/thread cleanup,100 five-way requests |
| Public integration | [brain.py](../../../../jarvis/brain.py), tools.py, existing specialized workflows | Existing actual Actions/ToolRegistry local-file/cache/repair/summary fixture reused; synthesis transport faked, no native model quality claim |


Read docs/system-map.md, hierarchical-execution.md and hierarchical-benchmarks.md; historical linked measurements retained as historical, not rerun claims. Sources and current registrations/configuration were inspected. Run order: schema/effect contracts → checkpoint ownership/restore → cache → failure/consent boundaries → repeated/concurrent fixtures → matched fingerprint benchmark → full regression/readiness. Actual brain.hierarchical_execution defaults retained: enabled/parallel_reads/macro_cache true, concurrency3, max_seconds300, repairs/replans1. Unknown keys now rejected. No new dependency/service/tool name. Existing launch/stop/recovery path retained.

## Executed results

Baseline **32 PASS**,2.41s,[XML](existing-baseline.xml). Before-fix regressions **7 FAIL/1 PASS**,[XML](reproduced-failures.xml): effect overlap, stale argument restore, corrupt cache JSON, exception-secret persistence, missing guarded task update, recursive JSON encoding, credential template retention. Final review reproduced **one additional stale-descendant failure** when upstream readback changed,[XML](restore-dependency-reproduced.xml),and fixed it: descendants require currently verified prerequisites. **8 reproduced defects fixed in total.** NaN config was already rejected; not counted as a new fix. A later catalog invocation had one missing fixture subdirectory, corrected without changing product behavior; [retained failure](catalog-first-fixture-error.xml).

Final targeted **180 PASS/1 existing explicit BLOCKED skip**,15.91s,[XML](cases-and-contracts.xml). Full **2314 PASS/8 explicit BLOCKED skips**,349.15s,[XML](full-regression.xml),[actual completion chunk](full-run-completion.txt). Counts overlap; do not sum. One existing pywinauto STA COM warning remains. Launcher **ready**,[redacted check](readiness.json). [Commands](commands.txt),[32 case IDs/assertions/scopes](tests.jsonl).

Safe journeys use actual file/registry/cache/repair/summary boundaries with controlled inference, a persisted read checkpoint/new TaskState, low-RAM serial admission, two bounded failed-read plans, and fake compose/preview/approve/send. Five independent DAG requests×20 rounds assert100 unique traces/task isolation/thread cleanup. Generic fake mail tools are not enabled production adapters. No approval or world effect is inferred from model/tool claims. Partial successful work is retained; there is no automatic undo of irreversible changes.

Final boundary assertions cover cancellation during result verification and actual Models.predict dag_plan private context with cloud enabled: fake local chat receives the synthetic payload and Groq calls0. They do not certify live native model output. The first full run passed before those final assertions and the stale-descendant correction; an intermediate rerun was interrupted for that correction. Preserved prior full XML is historical; only final full-regression.xml represents accepted code/tests.

## Paired component measurement and keep decision

| Fingerprint mode | Samples | p50 ms | p95 ms | Peak traced Python bytes |
| --- | --- | --- | --- | --- |
| before_cold | 5 | 1.3433 | 1.5955 | 124924 |
| before_warm | 20 | 1.3430 | 1.4813 | 120412 |
| after_cold | 5 | 3.4199 | 3.5778 | 127477 |
| after_warm | 20 | 1.3178 | 1.4818 | 8567 |

[Raw50 samples](benchmarks.csv),[scope/summary](benchmark-summary.json). Saved pre-change algorithm versus current algorithm on the same current source bytes and machine. Before hashes6 files each call; after checks8 files/model labels with cached content digests. Five cleared digest-cache calls and20 warm calls/version; cold is not cold OS/model state. Tracemalloc covers operation allocations, not whole-host RAM. No model/tool/network dispatch or external side effects; TTFT/first audio/VRAM not applicable, not zero. Initial during-workload measurements are preserved separately when the final quiet rerun exists.

Warm p95 **1.481→1.482ms**, cold p95 **1.595→3.578ms**. Retain avoided repeated source reads and lower warm transient allocation with tested invalidation; cold metadata/source checks cost more. A small timing difference is not a statistically established whole-task speedup. Safety fixes are retained for correctness; no faster unsafe writes, no native-model or voice latency claim.

## Remaining risks and exact scope

Cancellation is cooperative and drains owned work; an uncooperative backend waits for its timeout. Serial effects are per graph, not a global cross-process lock. Automatic rollback is not provided; partial progress is checkpointed. Native model planning/semantic accuracy, live approval provenance/accounts/UI, physical GPU contention and multi-hour soak were not run. The checkpoint binding is a consistency hash, not an authentication signature. Fresh local read verification and current task policy remain necessary. File metadata reuse is not protection against an actor restoring or forging timestamps; Windows ctime is creation time. New recognized credentials are omitted from templates; arbitrary personal data may remain in local task results/templates, and old rows are not scrubbed. Categorical errors trade detail for privacy. Optional task_id remains backward-compatible; unguarded legacy callers do not gain the new identity guarantee. No broad security or production certificate.

[Changes](changes.md),[failures](failures.md),[upstream/compatibility](compatibility.md),[rollback/resume](rollback.md),[exact files/hashes](files-changed.json),[scoped patch](source.patch). Earliest global blockers remain in the main catalog; no Prompt10 fixture case is pending.
