# Jarvis audit — Prompt14 follow-up, 2026-10-15 IST

**Prompt14:30 catalog fixture PASS / 2 BLOCKED / 0 FAIL.** Full **2536 PASS / 31 skips**, 398.03s; targeted **165 PASS / 4 BLOCKED skips**. Launcher **repair_required**. [Full XML](modules/14-browser-playwright/full-regression.xml),[targeted XML](modules/14-browser-playwright/cases-and-contracts.xml),[actual completion](modules/14-browser-playwright/full-run-completion.txt),[readiness/gaps](modules/14-browser-playwright/readiness.json),[skip reasons](modules/14-browser-playwright/full-regression-skip-reasons.json). Counts overlap; fixture success is separate from service readiness/live production acceptance.

Current repo `e1a33a0944b5cd725e1a76a72eda228513e45963`; baseline `bdcb15a52bbf23101950cd1625f249a564e647ee`, existing branch `audit/12-tool-registry`; Windows/Python3.10.6, installed Playwright1.63.0/Chrome, Ryzen7/32GB/RTX3050 Laptop4GB target. Isolated actual headless browser contexts and synthetic/loopback data; no production profile/user tabs/account writes/personal deletions/OS settings/credentials/install/browser download/model/deploy/commit. Existing changes preserved. HEAD advanced through an external phase1 commit during this run; this audit made no commit. Saved scoped preimages and final hashes define its changes. [Environment](modules/14-browser-playwright/environment.json), [Inventory/dependency/run order](modules/14-browser-playwright/inventory.md).

## Source map, fixes and measured change

| Claim / entry | Actual implementation and boundary | Executed proof / limitation |
| --- | --- | --- |
| Owned browser/controller | BrowserAutomation.request → UITransport(module=browser_worker) → Session.perform/open | Fixed controller executable settings override caller settings; validate before open; existing separate persistent production profile retained. Tests use fresh nonpersistent contexts, not that profile |
| Semantic actions | Session.perform click/fill → get_by_role(exact) → visible wait → uniqueness → browser_cursor.click | CSS classes irrelevant; delayed element uses built-in wait; exact observed URL rechecked after wait/before fill/readback; pinned node compared to current semantic locator after cue |
| DOM discovery | Session.inspect → one SUMMARY evaluate → validate_summary | HTML/ARIA labels, bound5000 visited nodes/120 controls, no field values/cookies, hidden/inert disabled filtering; metadata marked untrusted. This is an approximate accessible-name summary, not a complete accessibility tree |
| Authentication/redirect | bounded DOM summary flag → navigate message | Owned loopback302→signin plus visible password detection; no credential entry. Heuristic not general OAuth/SSO/session validity proof |
| Forms/dialogs | exact fill/input_value, generic sensitive-target refusal, existing registry scope/approvals | Exact Unicode value and0 fixture submits; no Enter from generic fill. Site input/autosave handlers can still issue requests; generic click labels are not a complete transaction policy |
| Tabs/downloads | bound Session.page/open_tabs; generic click/fill refuses >1 owned tab | Original page not silently retargeted. No production explicit tab-selection or verified-download/save adapter. Harness alone verifies suggested filename and exact synthetic PDF-marker bytes |
| Fault/recovery/handoff | UITransport lock/serial/deadline/owned process/backoff; BrowserAutomation.owns_handle |100 fake IPC requests over5 threads×20 rounds, timeout/cancel/malformed response no replay, intentional Stop. Existing owned-browser versus desktop routing preserved; no new live Windows handoff trial |
| Authority/privacy | untrusted summary contract, ToolRegistry allowlist, metadata-only agent events | Injection labels do not override known tools/scope/approvals; fake private field values absent from summary; UUID events omit payload. Not a general personal-text scrubber or prompt-injection proof |
| Existing neighboring paths | windows_command_browser.perform, media workflows, app_knowledge profiles | Existing scoped recipes/media/AppKnowledge remain; their historical live results are not rerun as general site/account acceptance |


Nine reproduced defects corrected. Baseline62 PASS; [failure history](modules/14-browser-playwright/failures.md),[retained changes](modules/14-browser-playwright/changes.md),[exact files/hashes](modules/14-browser-playwright/files-changed.json),[scoped source patch](modules/14-browser-playwright/source.patch),[rollback/resume](modules/14-browser-playwright/rollback.md). Boundaries retain current registry approvals, browser/profile ownership and no replay. No new generic download or tab capability.

Same-machine headless summary benchmark warm p50/p95 **18.585/22.125→6.906/12.563ms**, cold-context p95 **83.254→11.762ms**;4→1 browser round trips. [50 raw samples](modules/14-browser-playwright/benchmarks.csv),[allocations/scope](modules/14-browser-playwright/benchmark-summary.json).80 common name/role/href rows equivalent; absent href normalized to None. New HTML-label behavior separately asserted. Page load excluded, no real external effects; no universal site/model/audio/VRAM or2-second claim. Previous per-module metrics and reports preserved [through13](final-report-before-module14.md).

Firecrawl official [actionability](https://playwright.dev/python/docs/actionability)/[downloads](https://playwright.dev/python/docs/downloads)/[PyPI metadata](https://pypi.org/pypi/playwright/json): upstream1.64.0 uploaded2026-10-13T23:35:20Z, Python>=3.10; local1.63.0 retained under no-install contract. [Actual extraction results](modules/14-browser-playwright/upstream-checks.json),[compatibility decision](modules/14-browser-playwright/compatibility.md). No current-version or untested upgrade claim.

## Risks, blockers and exact accounting

JRV-14-007 verified-download/save and JRV-14-009 explicit tab selection are missing production adapters. Auth detection/accessible-name summary are heuristics; iframe/shadow/very large DOM coverage limited. A fill can invoke site autosave; label filtering is not universal transaction protection. DOM guard/input not atomic; existing240ms cursor cue retained with final admission. Other established logs retain their redaction policy. Headed browser/desktop handoff, real accounts/logins, general live sites, physical GPU contention and long soak not certified. Two prior native9b proofs are now stale after the concurrent knowledge_worker change; Ollama unavailable, so fresh validation is BLOCKED without modifying old proof hashes. Earlier acoustic/GPU/research/PDF/DPI/UAC catalog acceptance gates remain unrevalidated here. Current Phase2 documentation supersedes older implementation claims about absent speech leases; retained historical skip labels are not a fresh assertion that those leases are missing. Initial full2 failures were stale live-evidence hash checks, retained separately; they are now explicit native-prerequisite blockers, not new inferred passes. Current Phase2 speech/GPU changes are not re-audited by this browser module; their earlier catalog gates remain acceptance gaps, not fresh missing-implementation claims. No whole-system production/security certificate.

1184 unique IDs: **{'PASS': 439, 'FAIL': 0, 'BLOCKED': 15, 'SKIPPED': 0, 'NOT RUN': 730}**. [Exact ledger](test-results.jsonl),[32 module14 IDs/assertions](modules/14-browser-playwright/tests.jsonl),[remaining IDs](remaining-case-ids.txt),[machine totals](summary.json). No pass inferred from reading JSONL.


| tier | PASS | FAIL | BLOCKED | SKIPPED | NOT RUN |
| --- | --- | --- | --- | --- | --- |
| P0 | 107 | 0 | 6 | 0 | 183 |
| P1 | 235 | 0 | 7 | 0 | 387 |
| P2 | 97 | 0 | 2 | 0 | 160 |

| category | PASS | FAIL | BLOCKED | SKIPPED | NOT RUN |
| --- | --- | --- | --- | --- | --- |
| config | 14 | 0 | 0 | 0 | 23 |
| contract | 14 | 0 | 0 | 0 | 23 |
| edge | 28 | 0 | 0 | 0 | 46 |
| fault | 56 | 0 | 0 | 0 | 92 |
| idempotency | 14 | 0 | 0 | 0 | 23 |
| load | 14 | 0 | 0 | 0 | 23 |
| observability | 14 | 0 | 0 | 0 | 23 |
| performance | 14 | 0 | 0 | 0 | 23 |
| privacy | 14 | 0 | 0 | 0 | 23 |
| race | 14 | 0 | 0 | 0 | 23 |
| recovery | 28 | 0 | 0 | 0 | 46 |
| resource | 14 | 0 | 0 | 0 | 23 |
| scenario | 159 | 0 | 15 | 0 | 270 |
| security | 28 | 0 | 0 | 0 | 46 |
| semantic | 14 | 0 | 0 | 0 | 23 |


| Module | Name | Status |
| --- | --- | --- |
| 01 | architecture-inventory | PARTIAL |
| 02 | perception-cognition | FIXTURE COMPLETE |
| 03 | intent-direct | FIXTURE COMPLETE |
| 04 | voice-stt | LIVE ACOUSTIC VALIDATION BLOCKED |
| 05 | voice-tts | LIVE ACCEPTANCE BLOCKED |
| 06 | questions-context | 30 CURRENT FIXTURE PASS / 2 NATIVE ACCEPTANCE BLOCKED |
| 07 | model-routing | FIXTURE COMPLETE / LIVE CLOUD BLOCKED |
| 08 | gpu-scheduler | PARTIAL / SHARED SPEECH COORDINATION BLOCKED |
| 09 | deliberation | PARTIAL / MANDATORY UNFAMILIAR-PROGRAM RESEARCH BLOCKED |
| 10 | dag-planning | FIXTURE COMPLETE / LIVE ACCEPTANCE UNVERIFIED |
| 11 | skill-selection | 31 FIXTURE PASS / 1 BLOCKED; LIVE ACCEPTANCE UNVERIFIED |
| 12 | tool-registry | 32 FIXTURE PASS; LIVE ACCEPTANCE UNVERIFIED |
| 13 | desktop-control | 30 FIXTURE PASS / 2 BLOCKED; LIVE DESKTOP ACCEPTANCE UNVERIFIED |
| 14 | browser-playwright | 30 FIXTURE PASS / 2 BLOCKED; LIVE SITE ACCEPTANCE UNVERIFIED |
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

Earliest global unresolved **JRV-04-001**, next NOT RUN **JRV-15-001**. Prompt14 unresolved **JRV-14-007/JRV-14-009**. Read the next requested prompt before continuing;37 modules are not all complete.
