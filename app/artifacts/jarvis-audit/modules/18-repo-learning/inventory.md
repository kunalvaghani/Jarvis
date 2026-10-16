# Prompt 18 repository-learning audit — 2026-10-16 IST

**30 PASS /2 BLOCKED /0 FAIL** offline catalog scope. Baseline {'PASS': 62, 'SKIPPED': 10, 'FAIL': 0}; focused {'PASS': 225, 'SKIPPED': 3, 'FAIL': 0}; full {'PASS': 2706, 'SKIPPED': 32, 'FAIL': 0}. Focused run includes two catalog blockers and neighboring GPU/Docker fixture results; exact skip reasons in XML. [Commands/results](commands.txt), [32 IDs](tests.jsonl), [targeted XML](cases-and-contracts.xml), [full XML](full-regression.xml), [owned journey](repository-journey.json).

Synthetic public metadata, fake GitHub/archive/model transports and temporary vault/cache fixtures. Actual command/background worker, trusted Git init/commit/read/local snapshot and refused file-transport clone ran on owned data. Final full suite: 10 owned Docker kernel fixtures passed /0 skipped; Docker availability changed after the initial unavailable baseline without a service-start action by this audit. No live GitHub clone, private repository/vault, native LLM/GPU, GUI/voice trial, real account write, dependency/ability installation or downloaded-third-party-code execution.

| Claim | Actual binding / active configuration | Assertion / boundary |
| --- | --- | --- |
| Coding knowledge | Actions creates RepoLearner with memory enabled; commands.parse → execute → enqueue/start/run/learn; Actions coding tasks call RepoLearner.prepare; agent_context.learned_references/reference_for feed coding_context | command→worker→knowledge/index/note→Stop→restart→offline reference journey; no model training |
| Discovery | repo_learning.search/query/pick; public GitHub metadata API | zero stays empty; malformed items rejected; real Python-Markdown/markdown identity checked through Firecrawl, authored size/star fields; no live Jarvis API census |
| Source provenance | branch resolved once via commit endpoint; archive/tree/raw URLs use40hex SHA | commit stored in index/knowledge/note/reference; old unpinned cache yields metadata only |
| Analysis | Python AST, other-language declaration regex, manifests/test paths | no source execution; model key-module paths must exist; source_trust=untrusted, executed_tests=false; tests present is not tests passed |
| Bounds | archive40MB,20k entries/tree paths, selected source12MB,400KB/file; key-file fallback45 files/2.5MB/2 fetch workers | strict whole-file read budget; pre-append streamed caps; unsafe/link/generated/minified paths excluded; truncated trees refused; parser allocations not a hard process sandbox |
| Cache/concurrency | repo-knowledge files/knowledge.json and Obsidian Jarvis Repos/index.json/notes | SHA256 snippet names/content, tamper refusal, five independent requests×20 rounds preserve identities; serialized first acquisition and duplicate reuse |
| Licensing | permissive SPDX metadata + root license artifact required for snippets | unknown/copyleft/unpinned/platform-specific code omitted; origin/SHA/license/review flag retained. Not target-license legal compatibility proof |
| Platform | SwiftUI/AppKit/Darwin/fcntl static hints | Windows review note suppresses snippets; not complete build/dependency resolution |
| Privacy | local scheduler/knowledge_worker summary; public query guard; exact parsed API token origin and no redirects | fake credentials/private email goal causes0 HTTP calls even with Groq flag; recognized credential assignments/key material redacted before model/cache; heuristic only |
| Persistence/Stop | unique atomic JSON via skill_memory.atomic; rollback a fresh-learning index row on failed canonical write; corrupt-index guard | failed save one attempt; prior index preserved; before-transport/after-model Stop checks; derived notes best effort, multi-file transaction absent |
| Browser backpressure | dwell→verification≤2 workers→queue20; learning serialized | duplicate verifier thread removed; rapid titles admit2 checks; post-Stop observe/enqueue refused; queue not durable |
| Separate executable skills | repo_acquisition/repo_analysis/repository_skills → repo_tools/toolkits | trusted Git local snapshot/unsafe file-clone refusal; missing human approval denies smoke check;final full kernel fixtures:10 PASS /0 skips |
| Ability proposals | existing repo_abilities on_learned callback | proposal is not install/approval; neighboring fake approval/lifecycle tests retained; no real ability installed |
| Settings | enabled/auto_browse/search_for_coding true;repos_per_task1;min_stars20;dwell8s;refresh30d;max_zip40MB;modelqwen3.5:9b | strict flags/finite bounds; stable config/tool names and manifest/launcher/recovery preserved |

JRV-18-003: static symbols/test-file presence and untrusted labels do not behaviorally validate arbitrary README claims; no authorized general sandbox test oracle. JRV-18-019: completed knowledge reopens, but in-flight learning jobs have no durable checkpoint/process-crash restart contract.

Read actual map, repo-learning and linked repo-abilities/repository-skills docs and source/config registrations. Candidate repo_tools/toolkits bind the execution pipeline, not the multi-language reference learner. Optional integrations/repository-runtime was not rebuilt. Historical images/live counts retain dates/scope; no new visible UI/screenshot.

Order: preserve dirty audit/12-tool-registry/preimages → baseline → reproduced assertions → narrow fixes → official current upstream → equivalent A/B → targeted/privacy/permissions/concurrency → owned command/Git journey → frozen full regression and read-only launcher check → ledger/report. Existing dirty branch retained because a fresh checkout would omit user/module14–17 work. No reset/commit/install/deploy.

Saved-memory relevance warm p50/p95 **1.2128/1.2665 → 0.6546/0.7882 ms**, identical scores/top3 names on 500 repositories with 80 keywords each. [50 raw samples](benchmarks.csv), [scope](benchmark-summary.json), [tradeoffs](changes.md), [upstream](compatibility.md), [rollback](rollback.md).
