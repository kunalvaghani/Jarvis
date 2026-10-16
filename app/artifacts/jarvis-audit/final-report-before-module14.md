# Jarvis audit — Prompt13 follow-up, 2026-10-15 IST

**Prompt13:30 catalog fixture PASS / 2 BLOCKED / 0 FAIL.** Full **2423 PASS / 21 skips**, 386.72s; targeted **191 PASS / 2 BLOCKED skips**. Launcher **repair_required**. [Full XML](modules/13-desktop-control/full-regression.xml),[targeted XML](modules/13-desktop-control/cases-and-contracts.xml),[actual completion](modules/13-desktop-control/full-run-completion.txt),[redacted readiness](modules/13-desktop-control/readiness.json). Counts overlap. These are fixture/regression checks. Readiness failed: Docker/Ollama unavailable, F5 check timed out; no service start attempted. Whole-system/live production acceptance remains open.

Repo `1dd5ea3ff47bc9ee42ed6fbd27fc3f5b68335f41`, existing branch `audit/12-tool-registry`, Windows/Python3.10.6, Ryzen7/32GB/RTX3050 Laptop4GB target; CPU-only mocked desktop work. Existing dirty/Prompt12 work preserved, no new checkout/reset/commit/deploy/install/account write/personal setting/delete/model/real input. [Environment/run order/inventory](modules/13-desktop-control/inventory.md).

## Source map, changes and measurement

| Documented claim / entry | Checked implementation | Executed proof / limit |
| --- | --- | --- |
| Ordered providers | execution_adapters.PROVIDERS → execution_router.execute | Actual order jarvis-pointer → UFO → Windows-MCP → CUA → OpenComputerUse → Agent-S; five adapted ports, not five installed frameworks; only preparation fallback, deny/dispatch failure stops |
| Existing app/keyboard path | actions.Desktop.capture/type, Actions._execute, window_focus.focus_app | Existing executable/focus checks and per-character foreground/SendInput checks retained; no typing-speed change/live Notepad proof. App focus helpers can select the first matching executable/Z-order window; not general duplicate-window disambiguation |
| UIA target/focus | UIControls._handle → UITransport → ui_worker.perform/routed.guard | Explicit HWND/PID/foreground/visible/enabled/runtime ID/name/role/rectangle; fake changed foreground/lock0 refuses input, duplicate labels clarify; no live app launch certification |
| Touch/coordinates | JarvisPointer.prepare → jarvis_pointer.tap | Temporary physical-pixel DPI context restored; exact runtime ID/geometry/focus/hit-test repeated after idle and immediately before touch; fake150% geometry injects one down/up at300,225, moved target gets0 touches |
| Visual-point fallback | independent_cursor.at_point/activate_point | Existing window/PID/coverage guard now passed into tap admission; no whole-scene capture during every idle wait, so same-window scene races remain possible |
| Readback and no replay | execution_router + direct_execution.run + TaskState | Exact fake-native field value, no-op fresh state, failed/hung dispatch sent once, no next provider, direct runner pauses on unverified result; postcondition observations are bounded but COM itself can block |
| IPC failure ownership | UITransport.request/_stop_process/_backoff/close | Malformed/mismatched frames stop only owned worker, no replay;100 requests over5 threads×20 rounds have unique serial IDs; cancellation/backoff/intentional Stop preserved |
| Privacy/authority | categorical router errors/trace UUIDs, ui_worker.record, ToolRegistry policy | Synthetic secret excluded from new router receipt/message; existing journal omits labels/text. Current registry approval/allowlist still authoritative; not a general personal-data scrubber |
| Source/dependency truth | integrations/execution-primitives/source-manifest + retained licenses | Pinned selected sources; Windows-MCP pattern subset runs existingPython3.10.6, full Python3.14 server not installed; licenses preserved; no package/model/service added |


Eight reproduced faults fixed; [before failures](modules/13-desktop-control/failures.md),[scoped changes](modules/13-desktop-control/changes.md),[exact files and SHA256s](modules/13-desktop-control/files-changed.json),[source patch](modules/13-desktop-control/source.patch),[rollback/resume](modules/13-desktop-control/rollback.md). Baseline118 PASS. Current order remains pointer-first, not the older UIA-first map claim. Late pointer guards cover semantic target/window admission; visual same-window scene and final-check/input races remain limits. Malformed protocol cleanup respects owned worker/backoff/no replay.

Paired synthetic router warm p50/p95 **0.02175/0.04360→0.02440/0.03570ms**; cold p95 **0.06390→0.04860ms**. [50 trials](modules/13-desktop-control/benchmarks.csv),[peak allocation/scope](modules/13-desktop-control/benchmark-summary.json). First-success provider construction6→1; warm median increases slightly and tail timings vary; no speedup claim.0 real effects, one fake dispatch/readback each. No native COM/desktop/GPU/TTFT/audio measurement. Prior per-module results/metrics remain in [preserved previous report](final-report-before-module13.md) and linked predecessors; pre-existing [Prompt12 evidence](modules/12-tool-registry/inventory.md) is preserved independently, reconciled after review and a fresh [registry/accounting check](modules/13-desktop-control/accounting-followup.xml).

Firecrawl official current pages: UFOv3.0.10(no displayed date), Windows-MCPv0.8.8(10Oct01:33,no year printed), CuaSpacesv0.9.2(no date), OpenComputerUsev1.2.0(Aug25,no year printed), Agent-Sv0.3.2(2025-12-16); [exact URLs/findings](modules/13-desktop-control/upstream-checks.json),[compatibility and Microsoft DPI guidance](modules/13-desktop-control/compatibility.md). Pinned ports/full-server separation and licenses retained; no untested upstream/runtime upgrade.

## Risks, blockers and exact accounting

Live150%DPI/multi-monitor and real UAC/secure-desktop tests blocked; no personal OS state changed. Physical admission/input is not atomic; visual-point idle wait lacks full-image recapture. Shared keyboard/focus/pointer compatibility restoration remains. Uncooperative COM can block until owned worker timeout; verification deadline is not forcible cancellation. Arbitrary model/GUI/business-task correctness, all elevated apps, long soak and physical GPU contention remain unverified. Existing acoustic/shared-speech-lease/unfamiliar-program-research/PDF blockers persist. Existing executable/Z-order app-focus selection is not general duplicate-window clarification. No production/security or universal two-second certificate.

1184 unique catalog IDs: **{'PASS': 411, 'FAIL': 0, 'BLOCKED': 11, 'SKIPPED': 0, 'NOT RUN': 762}**. [All IDs/assertions](test-results.jsonl),[all32 Prompt13 IDs](modules/13-desktop-control/tests.jsonl),[remaining IDs](remaining-case-ids.txt),[machine-readable totals](summary.json). No pass inferred from JSONL ingestion. Existing module12 dedicated37 assertions were reviewed/rerun in a focused follow-up, resolving a missing catalog namespace;32 fixture cases now counted. This reporting-only change followed the final application full run; [fresh follow-up XML](modules/13-desktop-control/accounting-followup.xml) verifies it independently.


| tier | PASS | FAIL | BLOCKED | SKIPPED | NOT RUN |
| --- | --- | --- | --- | --- | --- |
| P0 | 100 | 0 | 5 | 0 | 191 |
| P1 | 221 | 0 | 4 | 0 | 404 |
| P2 | 90 | 0 | 2 | 0 | 167 |

| category | PASS | FAIL | BLOCKED | SKIPPED | NOT RUN |
| --- | --- | --- | --- | --- | --- |
| config | 13 | 0 | 0 | 0 | 24 |
| contract | 13 | 0 | 0 | 0 | 24 |
| edge | 26 | 0 | 0 | 0 | 48 |
| fault | 52 | 0 | 0 | 0 | 96 |
| idempotency | 13 | 0 | 0 | 0 | 24 |
| load | 13 | 0 | 0 | 0 | 24 |
| observability | 13 | 0 | 0 | 0 | 24 |
| performance | 13 | 0 | 0 | 0 | 24 |
| privacy | 13 | 0 | 0 | 0 | 24 |
| race | 13 | 0 | 0 | 0 | 24 |
| recovery | 26 | 0 | 0 | 0 | 48 |
| resource | 13 | 0 | 0 | 0 | 24 |
| scenario | 151 | 0 | 11 | 0 | 282 |
| security | 26 | 0 | 0 | 0 | 48 |
| semantic | 13 | 0 | 0 | 0 | 24 |


| Module | Name | Status |
| --- | --- | --- |
| 01 | architecture-inventory | PARTIAL |
| 02 | perception-cognition | FIXTURE COMPLETE |
| 03 | intent-direct | FIXTURE COMPLETE |
| 04 | voice-stt | LIVE ACOUSTIC VALIDATION BLOCKED |
| 05 | voice-tts | LIVE ACCEPTANCE BLOCKED |
| 06 | questions-context | FIXTURE COMPLETE |
| 07 | model-routing | FIXTURE COMPLETE / LIVE CLOUD BLOCKED |
| 08 | gpu-scheduler | PARTIAL / SHARED SPEECH COORDINATION BLOCKED |
| 09 | deliberation | PARTIAL / MANDATORY UNFAMILIAR-PROGRAM RESEARCH BLOCKED |
| 10 | dag-planning | FIXTURE COMPLETE / LIVE ACCEPTANCE UNVERIFIED |
| 11 | skill-selection | 31 FIXTURE PASS / 1 BLOCKED; LIVE ACCEPTANCE UNVERIFIED |
| 12 | tool-registry | 32 FIXTURE PASS; LIVE ACCEPTANCE UNVERIFIED |
| 13 | desktop-control | 30 FIXTURE PASS / 2 BLOCKED; LIVE DESKTOP ACCEPTANCE UNVERIFIED |
| 14 | browser-playwright | PARTIAL |
| 15 | app-research | PARTIAL |
| 16 | memory | PARTIAL |
| 17 | rag-documents | PARTIAL |
| 18 | repo-learning | PARTIAL |
| 19 | ability-forge | PARTIAL |
| 20 | self-evolution | PARTIAL |
| 21 | native-coding | PARTIAL |
| 22 | web-development | PARTIAL |
| 23 | gmail | PARTIAL |
| 24 | whatsapp | PARTIAL |
| 25 | media | PARTIAL |
| 26 | realtime-data | PARTIAL |
| 27 | gods-eye | PARTIAL |
| 28 | sandbox-deerflow | PARTIAL |
| 29 | reverse-engineering | PARTIAL |
| 30 | harness-planners | PARTIAL |
| 31 | ui-island-pip | PARTIAL |
| 32 | service-recovery | PARTIAL |
| 33 | mcp-integrations | PARTIAL |
| 34 | dependencies | PARTIAL |
| 35 | security | PARTIAL |
| 36 | observability | PARTIAL |
| 37 | e2e | PARTIAL |

Earliest unresolved **JRV-04-001**; next NOT RUN **JRV-14-001**. Prompt13 unresolved **JRV-13-004/JRV-13-007**. Read the next requested prompt before continuing; all37 modules are not complete.
