# Jarvis audit — Prompt18 follow-up, 2026-10-16 IST

**Repository-learning audit — 2026-10-16 IST:** Coding references now pin commits, verify cached excerpt hashes, restrict license-sensitive excerpt transfer, bound downloads/browser checks and screen discovery queries for private markers. Pinned duplicate learning reuses memory; corrupt indexes are preserved. Saved-memory relevance warm p50/p95 **1.2128/1.2665 → 0.6546/0.7882 ms**, identical scores/top3 names on 500 repositories with 80 keywords each.
Verification: **2,706 full regression PASS / 32 skips**; **30 Prompt 18 catalog PASS /2 BLOCKED**. Arbitrary repository behavior validation and durable in-flight job recovery remain incomplete. Derived caching adds cold work/memory; launcher **repair_required**.

Synthetic public metadata, fake GitHub/archive/model transports and temporary vault/cache fixtures. Actual command/background worker, trusted Git init/commit/read/local snapshot and refused file-transport clone ran on owned data. Final full suite: 10 owned Docker kernel fixtures passed /0 skipped; Docker availability changed after the initial unavailable baseline without a service-start action by this audit. No live GitHub clone, private repository/vault, native LLM/GPU, GUI/voice trial, real account write, dependency/ability installation or downloaded-third-party-code execution.

[Source-map/code/config/assertion matrix](modules/18-repo-learning/inventory.md), [commands/results](modules/18-repo-learning/commands.txt), [all 32 IDs](modules/18-repo-learning/tests.jsonl), [targeted XML](modules/18-repo-learning/cases-and-contracts.xml), [full XML](modules/18-repo-learning/full-regression.xml), [owned journey](modules/18-repo-learning/repository-journey.json), [readiness](modules/18-repo-learning/readiness.json).

HEAD **e1a33a0944b5cd725e1a76a72eda228513e45963**, dirty branch **audit/12-tool-registry** retained, no commit, prior work preserved. [Environment](modules/18-repo-learning/environment.json): Windows/Python3.10.6/Requests2.34.2/git version 2.49.1.windows.1; target Ryzen7/32GB/RTX3050Laptop4GB. No native GPU/model/audio measurement. 380 runtime/test hashes unchanged during acceptance. [Scoped files](modules/18-repo-learning/files-changed.json), [generated outputs](modules/18-repo-learning/generated-files.json), [preimages](modules/18-repo-learning/source-hashes.json), [full scoped diff](modules/18-repo-learning/source.patch).

Baseline {'PASS': 62, 'SKIPPED': 10, 'FAIL': 0}; focused {'PASS': 225, 'SKIPPED': 3, 'FAIL': 0}; full {'PASS': 2706, 'SKIPPED': 32, 'FAIL': 0}. Counts overlap, not unique catalog totals. [Failure/harness history](modules/18-repo-learning/failures.md), [full skip reasons](modules/18-repo-learning/full-regression-skip-reasons.json). Command/worker/restart/coding-context/trusted-Git journey **2.289s**,0 real HTTP/downloaded-source executions. Owned Git fixture commit **b4509251bb23a98aa29c5ce0ac6209dedf9176ff** independently read/snapshotted; unsafe file clone denied. No user GUI/account/model trial.

Saved-memory relevance warm p50/p95 **1.2128/1.2665 → 0.6546/0.7882 ms**, identical scores/top3 names on 500 repositories with 80 keywords each. Warm traced allocation 19815→6295B; cold p50 1.2918→3.8665ms, peak 19815→4597431B. [50 raw samples](modules/18-repo-learning/benchmarks.csv), [scope](modules/18-repo-learning/benchmark-summary.json), [keep/tradeoff](modules/18-repo-learning/changes.md). Retain extra cold work/roughly4.6MB derived cache for repeated warm use on32GB target; not an overall memory/end-to-end latency win. Disk/acquisition/source parsing/model/audio/VRAM excluded. Prior module metrics retained [through17](final-report-before-module18.md).

## Open gates, upstream and risk

JRV-18-003: static symbols/test-file presence and untrusted labels do not behaviorally validate arbitrary README claims; no authorized general sandbox test oracle. JRV-18-019: completed knowledge reopens, but in-flight learning jobs have no durable checkpoint/process-crash restart contract.

Firecrawl [official URLs/release dates](modules/18-repo-learning/upstream-checks.json), [compatibility/limits](modules/18-repo-learning/compatibility.md). Requests2.34.2(2026-05-14),Python>=3.10 already current; Git for Windows2.56.0(2)(2026-10-05) newer than installed2.49.1.windows.1, no installer. Static references do not establish arbitrary behavior, legal target-license compatibility, durable job crash resume, universal PII classification, hard parser/process RAM limits or multi-file/multi-process transactions. Existing acoustic/GPU/model/Docker/pypdf/other-module gates remain. Launcher **repair_required**: ollama: unavailable (ConnectionError); no repair/start/download attempted. No production-ready certificate.

[Rollback/resume](modules/18-repo-learning/rollback.md). Next NOT RUN **JRV-19-001**; earliest unresolved **JRV-04-001**. All 1,184 unique IDs: **{'PASS': 555, 'FAIL': 0, 'BLOCKED': 26, 'SKIPPED': 0, 'NOT RUN': 603}**. [Exact ledger](test-results.jsonl), [tier/category totals](summary.json), [exact remaining IDs](remaining-case-ids.txt). PASS requires dedicated executed assertions; fixture evidence does not silently certify live services.

## Modules

| Module | Catalog statuses |
| --- | --- |
| 01 architecture-inventory | PASS:32 |
| 02 perception-cognition | PASS:32 |
| 03 intent-direct | PASS:32 |
| 04 voice-stt | BLOCKED:3 / PASS:29 |
| 05 voice-tts | BLOCKED:2 / PASS:30 |
| 06 questions-context | BLOCKED:2 / PASS:30 |
| 07 model-routing | PASS:32 |
| 08 gpu-scheduler | BLOCKED:2 / PASS:30 |
| 09 deliberation | BLOCKED:1 / PASS:31 |
| 10 dag-planning | PASS:32 |
| 11 skill-selection | BLOCKED:1 / PASS:31 |
| 12 tool-registry | PASS:32 |
| 13 desktop-control | BLOCKED:2 / PASS:30 |
| 14 browser-playwright | BLOCKED:2 / PASS:30 |
| 15 app-research | BLOCKED:1 / PASS:31 |
| 16 memory | BLOCKED:4 / PASS:28 |
| 17 rag-documents | BLOCKED:4 / PASS:28 |
| 18 repo-learning | BLOCKED:2 / PASS:30 |
| 19 ability-forge | NOT RUN:32 |
| 20 self-evolution | NOT RUN:32 |
| 21 native-coding | NOT RUN:32 |
| 22 web-development | NOT RUN:32 |
| 23 gmail | NOT RUN:32 |
| 24 whatsapp | NOT RUN:32 |
| 25 media | NOT RUN:32 |
| 26 realtime-data | NOT RUN:31 / PASS:1 |
| 27 gods-eye | NOT RUN:32 |
| 28 sandbox-deerflow | NOT RUN:32 |
| 29 reverse-engineering | NOT RUN:31 / PASS:1 |
| 30 harness-planners | NOT RUN:32 |
| 31 ui-island-pip | NOT RUN:32 |
| 32 service-recovery | NOT RUN:32 |
| 33 mcp-integrations | NOT RUN:32 |
| 34 dependencies | NOT RUN:31 / PASS:1 |
| 35 security | NOT RUN:30 / PASS:2 |
| 36 observability | NOT RUN:32 |
| 37 e2e | NOT RUN:32 |

## Tier/category statistics

```json
{
  "by_tier": {
    "P0": {
      "PASS": 137,
      "BLOCKED": 8,
      "NOT RUN": 151
    },
    "P1": {
      "PASS": 296,
      "BLOCKED": 13,
      "NOT RUN": 320
    },
    "P2": {
      "PASS": 122,
      "BLOCKED": 5,
      "NOT RUN": 132
    }
  },
  "by_category": {
    "config": {
      "PASS": 18,
      "NOT RUN": 19
    },
    "contract": {
      "PASS": 18,
      "NOT RUN": 19
    },
    "edge": {
      "PASS": 36,
      "NOT RUN": 38
    },
    "fault": {
      "PASS": 72,
      "NOT RUN": 76
    },
    "idempotency": {
      "PASS": 18,
      "NOT RUN": 19
    },
    "load": {
      "PASS": 18,
      "NOT RUN": 19
    },
    "observability": {
      "PASS": 16,
      "BLOCKED": 2,
      "NOT RUN": 19
    },
    "performance": {
      "PASS": 18,
      "NOT RUN": 19
    },
    "privacy": {
      "PASS": 18,
      "NOT RUN": 19
    },
    "race": {
      "PASS": 18,
      "NOT RUN": 19
    },
    "recovery": {
      "PASS": 35,
      "BLOCKED": 1,
      "NOT RUN": 38
    },
    "resource": {
      "PASS": 18,
      "NOT RUN": 19
    },
    "scenario": {
      "PASS": 198,
      "BLOCKED": 23,
      "NOT RUN": 223
    },
    "security": {
      "PASS": 36,
      "NOT RUN": 38
    },
    "semantic": {
      "PASS": 18,
      "NOT RUN": 19
    }
  }
}
```
