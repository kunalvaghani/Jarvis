# Prompt16 memory audit — 2026-10-16 IST

**28 catalog PASS / 4 BLOCKED / 0 FAIL.** Baseline 72 PASS; targeted 146 PASS / 4 explicit blocker skips; full 2616 PASS / 36 skips. [Catalog assertions](tests.jsonl), [targeted XML](cases-and-contracts.xml), [full XML](full-regression.xml), [actual user journey](memory-journey.json).

Temporary synthetic vaults/SQLite databases, actual file/FTS transaction readback, deterministic model/network fakes. No real vault, personal conversation, Obsidian GUI, cloud account, native LLM/GPU, microphone or external effect was exercised.

| Source-map claim | Real binding/configuration | Assertion / boundary |
| --- | --- | --- |
| Durable user facts | memory_curator.parse_command/execute → add/forget → version1 JSON and regenerated Markdown; memory.long_term.enabled=true, learn_facts=true, summarize=true, max_facts500, idle15min | command→canonical readback→reopen→local answer; fsync before replace, precommit failure restores RAM; postcommit derived-note failure retains committed fact |
| Identity/corrections | subject and preference_slot guards before existing lexical overlap | tested explicit simple prefers correction; different named subjects/polarity preserved. Not general semantic entity resolution/conflict arbitration |
| Episodic sessions | Knowledge.attach_conversations → ConversationMemory: sessions/turns/FTS5, timeout1s, connection transaction context | pending/cancelled excluded from recall; temporary exclusive DB lock released then single commit; duplicate finish replaces one FTS row; real reopen |
| Sensitive data | shared obsidian_memory.SENSITIVE + clean; curator.safe; begin/finish import shared matcher | OTP/card/credential fixture markers redacted before clipping and SQLite indexing. Heuristic only, no retroactive real-history scrub |
| Corrupt/legacy store | curator.load caps JSON, validates shapes, skips invalid facts; valid legacy missing-version JSON accepted as version1 | corrupt canonical preserved, new writes require review; malformed model output ignored with categorical error; no new SQL schema/migration |
| Procedural learning | SkillMemory verified records, scoped guides; ExperienceMemory bounded cases and verification scope | existing procedure/case regression assertions, source/payload restrictions and no uncertain replay retained |
| Hotness/decay | experience.hotness/hotness_many cached ISO parse + existing numpy vector path | vector/scalar same for50 mixed stamps; no new vector framework or model download |
| Retrieval | curator.relevant + Obsidian.recall + memory_index; context_hub/Brain/Knowledge consume bounded references | query terms/scoring computed once, identical top8 on500-fact A/B; recent fallback preserved. Existing incremental index remains; no semantic reranker added without benefit proof |
| Idle/Stop | existing background queue max50 and40 current turns; GPU scheduler background inference outside fact lock | typing while fake summary waits remains under100ms; closed observer rejects new jobs, in-flight extraction drops output after Stop; no claim of preempting native model kernels |
| Erase/offline/freshness/traces | partial or missing contracts | JRV-16-004: no cross-store erase/tombstone protocol; fact forgetting does not purge SQLite, summaries/Daily notes or stop paraphrased rehydration. JRV-16-006: no durable unavailable-vault outbox; the bounded model-job queue is not write recovery. JRV-16-011: no general document-versus-memory freshness reconciliation. JRV-16-032: errors are categorical but memory lifecycle operations lack end-to-end correlation IDs. |

Order: read actual map and linked memory/cognitive docs, preserve dirty audit branch/source preimages, baseline, reproduce, narrow fixes, equivalent A/B, targeted/neighbors/privacy, synthetic command journey, final frozen full run, read-only launcher check, ledger reconciliation. Existing dirty audit/12-tool-registry retained to preserve inherited user/module14–15 diffs; no commit/reset/refactor/new service/dependency/model download. Active manifest/launchers remain compatible through full regression/readiness.

Measured warm p50/p95 **15.4031/20.1828→5.3995/5.7082ms**; peak traced Python allocation **25960→30755B**. Small allocation increase retained for faster equivalent results; [50 raw samples](benchmarks.csv), [scope](benchmark-summary.json). Five cold objects are fresh RAM state, not disk startup. No model/voice/VRAM timing claim.

[Paired durability fault proof](durability-reproduction.json): old preimage RAM differed from canonical disk after the injected replacement failure; fixed RAM matched disk. Both made exactly one attempt. Script: scripts/verification/verify_memory_durability.py.

Launcher **repair_required**: [redacted actual result](readiness.json). [Limits/upstream](compatibility.md), [fixes](changes.md), [failure history](failures.md), [rollback/resume](rollback.md).
