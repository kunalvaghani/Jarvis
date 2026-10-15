# Jarvis audit — through Prompt11, 2026-10-15 IST

**Prompt11:31 fixture PASS / 1 BLOCKED; no pending or failed fixture cases.** Arbitrary PDF editing lacks a validated offered adapter. Full **2355 PASS / 9 BLOCKED skips**, 349.16s; targeted **157 PASS / 1 BLOCKED skip**. [Full XML](modules/11-skill-selection/full-regression.xml),[targeted XML](modules/11-skill-selection/cases-and-contracts.xml),[actual completion](modules/11-skill-selection/full-run-completion.txt),[launcher ready](modules/11-skill-selection/readiness.json). Suites overlap; existing COM warning persists. Whole-system/live production acceptance remains open.

Repo `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`, Windows/Python3.10.6, Ryzen7/32GB/RTX3050 Laptop4GB target. CPU-only guide work, no new heavyweight/GPU test. Existing dirty work preserved; no commit/deployment, account send/write, personal deletion, system setting, credentials or ability installation. [Environment, dependency/entry-point/source-map evidence matrix and execution order](modules/11-skill-selection/inventory.md).

Eight pre-existing reproduced defects fixed: guide path/metadata validation, Hermes duplicate/missing resource validation/pre-open bounds, observed recipe ordering, missing utility environment and malformed validation handling. [Reproductions](modules/11-skill-selection/failures.md),[exact changed files/hashes](modules/11-skill-selection/files-changed.json),[scoped before/after diff](modules/11-skill-selection/source.patch),[rollback/resume](modules/11-skill-selection/rollback.md). Public source census10 native/210 verified Hermes/23 DeerFlow; utility proof stale before and after,0 offered. No helpers/providers newly activated.

Same-machine metadata ranking warm p50/p95 **12.588/12.777→6.618/12.850ms**; cold p95 **20.267→8.671ms**. [50 measurements](modules/11-skill-selection/benchmarks.csv),[allocation/tradeoffs/scope](modules/11-skill-selection/benchmark-summary.json). All selected rankings identical on the fixture; no general semantic precision, TTFT/audio/VRAM or whole-task speed claim. Bounded cache retains description metadata, not goals; recognized credential descriptions bypass it. Cold allocation cost is explicit. [Earlier per-module metrics/report through10](final-report-before-module11.md) and linked predecessors preserve prior evidence.

Official upstream pages checked today through Firecrawl: [Agent Skills](https://agentskills.io/client-implementation/adding-skills-support) (no date), [Hermes v0.22.2](https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.2) (2026-10-15), [DeerFlow v2.1.0](https://github.com/bytedance/deer-flow/releases/tag/v2.1.0) (page24 Sep;2026 inferred). [Actual answers and compatibility limits](modules/11-skill-selection/upstream-checks.json),[pinned revisions/decision](modules/11-skill-selection/compatibility.md). No upstream/runtime installation assumed compatible without tests.

## Risk and exact accounting

Guidance does not grant permission; current registry, policy, scope, approvals and cancellation remain authoritative. Hashes/provenance establish consistency, not identity; reload metadata is not adversarial tamper-proof. Legacy procedure failure counts unavailable, rate is a smoothed estimate. No real GUI/account/native model/physical GPU/long soak validation in this module. Arbitrary PDF editing and utility revalidation require reviewed implementation/authorized checks; earlier acoustic, shared speech lease and mandatory unfamiliar-program research blockers remain. No whole-system security/production or universal two-second certificate.

All1184 unique catalog IDs accounted: **{'PASS': 354, 'FAIL': 0, 'BLOCKED': 9, 'SKIPPED': 0, 'NOT RUN': 821}**. [Exact ledger](test-results.jsonl),[tier/category/run totals](summary.json),[32 Prompt11 IDs/scopes](modules/11-skill-selection/tests.jsonl),[remaining IDs](remaining-case-ids.txt). No pass inferred from JSONL ingestion. Prior reports and failures retained.

| Tier | PASS | FAIL | BLOCKED | SKIPPED | NOT RUN |
| --- | --- | --- | --- | --- | --- |
| P0 | 87 | 0 | 5 | 0 | 204 |
| P1 | 190 | 0 | 2 | 0 | 437 |
| P2 | 77 | 0 | 2 | 0 | 180 |

| Category | PASS | FAIL | BLOCKED | SKIPPED | NOT RUN |
| --- | --- | --- | --- | --- | --- |
| config | 11 | 0 | 0 | 0 | 26 |
| contract | 11 | 0 | 0 | 0 | 26 |
| edge | 22 | 0 | 0 | 0 | 52 |
| fault | 44 | 0 | 0 | 0 | 104 |
| idempotency | 11 | 0 | 0 | 0 | 26 |
| load | 11 | 0 | 0 | 0 | 26 |
| observability | 11 | 0 | 0 | 0 | 26 |
| performance | 11 | 0 | 0 | 0 | 26 |
| privacy | 11 | 0 | 0 | 0 | 26 |
| race | 11 | 0 | 0 | 0 | 26 |
| recovery | 22 | 0 | 0 | 0 | 52 |
| resource | 11 | 0 | 0 | 0 | 26 |
| scenario | 134 | 0 | 9 | 0 | 301 |
| security | 22 | 0 | 0 | 0 | 52 |
| semantic | 11 | 0 | 0 | 0 | 26 |

## Source-map evidence and exact scoped files

| Claim / entry point | Actual checked-out evidence | Proven boundary / limitation |
| --- | --- | --- |
| Native/custom/personal guides | skills/, custom-skills/, skill_memory.SkillMemory.refresh/context | 10 bundled; bounded50/source; builtin > custom > personal deterministic collision reporting; hot reload uses path/mtime/size, not adversarial metadata forgery protection |
| Tool discovery | capabilities.rank_tools/runtime_context → ToolRegistry.search/catalog | Existing handlers only, prerequisites/scope/provider filters retained; unknown names diagnostic, not executable |
| Trust/provenance | refresh → skill_read folder=@jarvis | Origin, relative path, SHA256 and untrusted_guidance label; registry policy/current authorization remain authoritative; hash is consistency, not authenticity |
| Hermes references | hermes_skills.HermesSkills → skill_list/read folder=@hermes | 210 indexed SKILL.md contents verified,1090 indexed resources; unique bounded metadata, indexed exact resource/read budget, hashes checked; helpers not run |
| DeerFlow references | deerflow.status/search_skills/read_skill → folder=@deerflow | 23 public guides present; existing neighboring fixture suite, no provider readiness inferred from guide availability |
| Utility activation | utility_profiles.availability/tools → toolkits/registry | Separate environment exists but validation already stale before this update:0 offered. Missing/malformed/stale states fail closed. No arbitrary PDF-edit adapter offered |
| Learned procedures | SkillMemory.record/context | Existing verified recipe preserved after failure; new success/attempt counts, relevance then smoothed rate then recency; historical missing failures not reconstructed |
| Builtin and lifecycle policy | commands.py immutable dispatch; ToolRegistry.execute → check_policy/_execute/event | Existing builtin wins; denied/cancelled tools never dispatched in fixtures; categorical UUID metadata excludes payloads; no replay/helper queue |


Changed files (not the entire pre-existing dirty tree); before/after hashes and artifact inventory are linked above:

- app/jarvis/capabilities.py
- app/jarvis/skill_memory.py
- app/jarvis/hermes_skills.py
- app/jarvis/utility_profiles.py
- app/jarvis/agent_tools.py
- app/config/runtime_manifest.json
- app/scripts/verification/audit_catalog.py
- app/tests/test_audit_result_accounting.py
- app/tests/test_skill_selection_audit.py
- app/scripts/verification/verify_skill_selection_audit.py
- app/scripts/verification/report_skill_selection_audit.py
- app/README.md
- app/docs/skills-and-learning.md
- app/docs/runtime-capabilities.md
- app/docs/hermes-skills-and-comparison.md
- app/docs/utility-skills.md
- app/docs/system-map.md
- README.md (root overview)

## Enumerated modules

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

Earliest unresolved **JRV-04-001**; next NOT RUN **JRV-12-004**. Prompt11 unresolved **JRV-11-002**. Read the next requested prompt before proceeding;37 modules are not all complete.
