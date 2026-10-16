# Jarvis audit — Prompt15 follow-up, 2026-10-16 IST

**App/site knowledge audit — 2026-10-16 IST:** Fresh surface/version and task UUID checks prevent stale context reuse; login observations suppress research/control hints; bounded inputs and numeric public versions fail closed. Source preference uses configured origin, with explicit URL version hints marked stale. Cache lookup warm median 3.52→0.45 ms on synthetic records.
Verification: **2,576 full regression PASS / 32 skips**; **31 Prompt15 catalog PASS / 1 BLOCKED** (plugin identity namespace missing). Launcher **repair_required**. Owned headless browser fixture passed; live accounts/native GUI/model/production readiness remain unverified.

Isolated fake public transports, temporary app stores and actual production acquisition/registry/DAG/cache paths. The browser journey additionally uses owned headless Chrome and an intercepted synthetic page with all other destinations aborted. No live model, account, third-party action, native GUI, physical GPU load or long soak certification.

[Source-map/code/config/test inventory](modules/15-app-research/inventory.md), [full test XML](modules/15-app-research/full-regression.xml), [targeted XML](modules/15-app-research/cases-and-contracts.xml), [32 case assertions](modules/15-app-research/tests.jsonl), [readiness](modules/15-app-research/readiness.json), [actual synthetic browser journey](modules/15-app-research/browser-journey.json).

Repo/commit/environment: [exact baseline](modules/15-app-research/environment.json); branch retained audit/12-tool-registry, HEAD e1a33a0944b5cd725e1a76a72eda228513e45963, no audit commit, Windows/Python3.10.6, Ryzen7/32GB/RTX3050Laptop4GB target. Inherited module14/user diffs preserved, no new dependency/service/config setting or production cache changed. 377 source/test hashes unchanged during accepted full run. [Exact changed files](modules/15-app-research/files-changed.json), [scoped diff](modules/15-app-research/source.patch), [source hashes](modules/15-app-research/source-hashes.json).

Nine failure families reproduced/fixed, with QA setup errors distinguished in [failure history](modules/15-app-research/failures.md). [Before/after changes and tradeoffs](modules/15-app-research/changes.md). Baseline29 PASS; targeted 138 PASS / 1 blocked skip. Tests overlap and are not summed as unique catalog results. Full skip reasons remain explicit in XML. No failure hidden by catalog reconciliation.

Warm lookup p50/p95 3.5175/3.7913→0.4451/0.4511 ms; peak traced Python allocations 357246→64405 bytes. Five fresh-store and20 warm lookups/version, identical24-record fixture; independent copied results asserted. [Raw samples](modules/15-app-research/benchmarks.csv), [cold/warm scope](modules/15-app-research/benchmark-summary.json). Cold is fresh in-memory object, excludes disk load; no full-task/VRAM/model/audio speed claim. Synthetic headless user journey 2.375s, authored planner and independent DOM oracle. Earlier per-module measurements preserved in [report through14](final-report-before-module15.md).

Firecrawl official current-source and release checks: [evidence URLs/dates](modules/15-app-research/upstream-checks.json), [compatibility rationale](modules/15-app-research/compatibility.md). Installed ddgs9.16.0 matches PyPI latest release2026-08-26, Python>=3.10; retained with measured internal cache optimization. Connector key not exported. No installation or paid requirement.

## Open gates and risk

JRV-15-010 plugin-specific identity/version scoping missing. Exact-origin preference depends on configured documentation URL, not authenticated publisher discovery; explicit URL hints are not semantic document reconciliation. Unknown versions remain uncertain. Authentication, names, sensitive host screening and signature invalidation are bounded heuristics; hidden/SSO/custom plugin surfaces can require clarification. Native GUI/accounts/live model, physical resource contention and long soak not certified. Launcher status above is actual readiness, not a feature check. Existing earlier acoustic/native-model/GPU/PDF/download/tab and unfamiliar-program approval gates remain catalog blockers; no whole-system production/security certification. Recovery still only repeats observations; no uncertain external effect replay. [Rollback/resume](modules/15-app-research/rollback.md).

1184 catalog IDs: **{'PASS': 470, 'BLOCKED': 16, 'NOT RUN': 698}**. [Exact ledger](test-results.jsonl), [totals by tier/category](summary.json), [all remaining IDs](remaining-case-ids.txt). Next NOT RUN: **JRV-16-001**. Earliest unresolved: **JRV-04-001**.

## Modules

| Module | Catalog status counts |
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
| 16 memory | NOT RUN:31 / PASS:1 |
| 17 rag-documents | NOT RUN:32 |
| 18 repo-learning | NOT RUN:32 |
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
      "PASS": 115,
      "BLOCKED": 6,
      "NOT RUN": 175
    },
    "P1": {
      "PASS": 252,
      "BLOCKED": 7,
      "NOT RUN": 370
    },
    "P2": {
      "PASS": 103,
      "BLOCKED": 3,
      "NOT RUN": 153
    }
  },
  "by_category": {
    "config": {
      "PASS": 15,
      "NOT RUN": 22
    },
    "contract": {
      "PASS": 15,
      "NOT RUN": 22
    },
    "edge": {
      "PASS": 30,
      "NOT RUN": 44
    },
    "fault": {
      "PASS": 60,
      "NOT RUN": 88
    },
    "idempotency": {
      "PASS": 15,
      "NOT RUN": 22
    },
    "load": {
      "PASS": 15,
      "NOT RUN": 22
    },
    "observability": {
      "PASS": 15,
      "NOT RUN": 22
    },
    "performance": {
      "PASS": 15,
      "NOT RUN": 22
    },
    "privacy": {
      "PASS": 15,
      "NOT RUN": 22
    },
    "race": {
      "PASS": 15,
      "NOT RUN": 22
    },
    "recovery": {
      "PASS": 30,
      "NOT RUN": 44
    },
    "resource": {
      "PASS": 15,
      "NOT RUN": 22
    },
    "scenario": {
      "PASS": 170,
      "BLOCKED": 16,
      "NOT RUN": 258
    },
    "security": {
      "PASS": 30,
      "NOT RUN": 44
    },
    "semantic": {
      "PASS": 15,
      "NOT RUN": 22
    }
  }
}
```
