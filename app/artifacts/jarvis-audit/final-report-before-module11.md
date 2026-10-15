# Jarvis audit through Prompt10 — 2026-10-15 IST

**Prompt10:32 catalog fixture PASS,0 FAIL/BLOCKED/SKIPPED/NOT RUN.** Targeted **180 PASS/1 existing explicit BLOCKED skip**; full **2314 PASS/8 explicit BLOCKED skips**,349.15s. [Targeted XML](modules/10-dag-planning/cases-and-contracts.xml),[full XML](modules/10-dag-planning/full-regression.xml),[completion output](modules/10-dag-planning/full-run-completion.txt). Suites overlap. Launcher **ready**,[redacted result](modules/10-dag-planning/readiness.json); one existing pywinauto COM warning. Whole-system production acceptance remains open.

Repo `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`,branch `codex/jarvis-prove-fix-audit`; Windows/Python3.10.6,SQLite3.37.2,Ryzen7/32GB/RTX3050 Laptop4GB target. No new GPU/model test. Existing dirty work preserved; no account send, personal deletion, OS/config mutation, ability/install/download, credentials, commit or deployment.

## Changes, source map and measurements

Per-graph serial effects, exact bound read restoration/fresh verification, task UUID checkpoint/authorization guards, bounded invalid-cache fallback, credential-template exclusion, categorical errors/run traces and source digest reuse with metadata invalidation. Baseline32 PASS;8 reproduced failures fixed. [Source-map/dependency/entry-point evidence matrix](modules/10-dag-planning/inventory.md),[failures](modules/10-dag-planning/failures.md),[files/hashes](modules/10-dag-planning/files-changed.json),[scoped patch](modules/10-dag-planning/source.patch),[rollback](modules/10-dag-planning/rollback.md).

Fingerprint warm p50/p95 **1.343/1.481→1.318/1.482ms**; cold p95 **1.595→3.578ms**. Warm peak traced allocation **120412→8567 bytes**; operation scope, not total RAM. [50 paired samples](modules/10-dag-planning/benchmarks.csv),[measurement limits](modules/10-dag-planning/benchmark-summary.json). Cold checks cost more; no whole-task/model/voice speed claim. Earlier per-module baselines/metrics remain in [preserved through09 report](final-report-before-module10.md) and linked predecessors.

Official [upstream/compatibility checks](modules/10-dag-planning/compatibility.md): Python thread cancellation is cooperative; SQLite3.54.0 released2026-10-09 versus local3.37.2; Python3.10.22 security/source release2026-10-01 versus local3.10.6. No untested runtime/library upgrade performed. Structured outputs still need validation and do not grant authority.

## Risk and exact catalog accounting

Per-graph serialization is not a global write lock. Generic fake mail journey is not a production DAG mail adapter; specialized approval paths are preserved. Partial progress is retained, not automatically rolled back. Native GUI/accounts, model quality, physical GPU contention and multi-hour soak were not tested. Metadata cache is not protection against restored or forged metadata; hashes bind consistency, not human identity. Local private results/old templates may remain. Prior acoustic/shared-speech-lease/mandatory-program-research blockers persist. No universal security/production or two-second response certificate.

1184 unique IDs: **{'PASS': 324, 'FAIL': 0, 'BLOCKED': 8, 'SKIPPED': 0, 'NOT RUN': 852}**. [Exact case/assertion ledger](test-results.jsonl),[tier/category/run totals](summary.json),[32 Prompt10 cases/scopes](modules/10-dag-planning/tests.jsonl),[remaining IDs](remaining-case-ids.txt). No PASS inferred from merely reading JSONL.

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
| 11 | skill-selection | PARTIAL |
| 12 | tool-registry | PARTIAL |
| 13 | desktop-control | PARTIAL |
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

Earliest global unresolved **JRV-04-001**; next NOT RUN **JRV-11-001**. No Prompt10 fixture case pending. Read the next requested module prompt before proceeding; this report does not claim all37 modules are complete.
