# Jarvis audit — Prompt22 — 2026-10-16 IST

**Web/app audit — 2026-10-16 IST:** Strict preview URL/test-plan validation, service-worker/WebSocket isolation and reused health opener added. **18 Prompt22 fixture PASS /14 BLOCKED**. Full regression **2,855 PASS /48 skips /0 failures**; launcher **ready**. Real authored build and isolated headless browser checks passed; HMR, warning classification, safe restart, host confinement, dependency compatibility, crash continuation and complete redaction remain incomplete.

HEAD **9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6**, branch **audit/12-tool-registry**, inherited changes preserved; no audit commit. [Environment](modules/22-web-development/environment.json). Baseline {'PASS': 25, 'FAIL': 0, 'SKIPPED': 0, 'seconds': 6.737}; focused {'PASS': 50, 'FAIL': 0, 'SKIPPED': 14, 'seconds': 67.729}; full {'PASS': 2855, 'FAIL': 0, 'SKIPPED': 48, 'seconds': 532.419}. All **384 frozen source/test hashes unchanged**. [Full output](modules/22-web-development/full-regression.xml), [skips](modules/22-web-development/full-regression-skip-reasons.json), [readiness](modules/22-web-development/readiness.json).

Actual existing trusted authored dashboard TypeScript/Vite build, owned temporary static previews, installed headless Chrome desktop/mobile/reduced-motion checks with project-local axe, deliberate overflow/dead-button failures, isolated mock remote API, Unicode DOM readback, cancellation/timeout and owned process cleanup. Five independent status sessions ×20 rounds use no model/GPU. Network/RAM/process faults and planner responses are fakes; these do not prove native memory pressure handling or arbitrary generated applications. No dependency installs, private account/browser-profile reuse, external sends, personal deletes, OS settings, native packaging, model downloads or publication. Build writes only the pre-existing authored acceptance artifact output; generated test projects and snapshots are owned temporary fixtures.

Health-check overhead warm p50/p95 **0.38605/0.39860 → 0.01765/0.01930 ms**; peak traced allocation **7319 → 2352 bytes**. Same fake HTTP200 response and active/dead/closed assertions;25 calls/version in one process. Five initial calls are not fresh-process cold starts. Imports/construction/network/browser/build/GPU excluded. Cached opener retains per-instance memory and moves construction to instance startup; no end-to-end speed or VRAM claim.

[Source-map evidence matrix and actual fixture captures](modules/22-web-development/inventory.md), [changes/metrics](modules/22-web-development/changes.md), [exact files](modules/22-web-development/files-changed.json), [diff](modules/22-web-development/source.patch), [upstream URLs/dates](modules/22-web-development/compatibility.md), [risk/flaws](modules/22-web-development/failures.md), [rollback/resume](modules/22-web-development/rollback.md), [commands/results](modules/22-web-development/commands.txt).

- **JRV-22-002 BLOCKED:** Production preview uses Vite preview/Next start/exported static files, not a development HMR lifecycle.
- **JRV-22-004 BLOCKED:** Exit status and raw build diagnostics exist; no benign-versus-regression warning classifier.
- **JRV-22-008 BLOCKED:** Watchdog stops owned failed preview and requests explicit continuation; no safe automatic restart contract. Project/server code can have side effects, so it is not silently replayed.
- **JRV-22-010 BLOCKED:** Browser contexts isolate cookies/storage and permissions; project build/server code still runs as host user without filesystem confinement.
- **JRV-22-011 BLOCKED:** Reviewed install/lock guards exist; no reproducible dependency-upgrade API-break compatibility oracle.
- **JRV-22-019 BLOCKED:** Owned child jobs stop on exit; no durable preview crash-resume protocol.
- **JRV-22-032 BLOCKED:** Raw build/browser logs may contain credentials; complete credential-redacted trace contract missing.
- **JRV-22-018 BLOCKED:** Stop/timeout smoke checks do not prove consistent TaskState cancellation during planning and readback.
- **JRV-22-021 BLOCKED:** Token URL refusal does not prove the complete fake-cloud/private-context/log-redaction contract.
- **JRV-22-023 BLOCKED:** Explicit one-file scope does not prove positive-versus-negative development-intent execution semantics.
- **JRV-22-025 BLOCKED:** Injected MemoryError stops launch, but RAM/GPU admission and core-command responsiveness under pressure are unproved.
- **JRV-22-026 BLOCKED:** Repair avoids restart; durable identical-event and uncertain-write deduplication across the complete flow is unproved.
- **JRV-22-027 BLOCKED:** Health microbenchmark is measured; full development request cold-start/RSS/VRAM benchmark is absent.
- **JRV-22-030 BLOCKED:** Pre-launch faults/dead-process checks do not prove active-worker disconnect recovery with durable task provenance.

All1,184 catalog IDs: **{'PASS': 660, 'FAIL': 0, 'BLOCKED': 49, 'SKIPPED': 0, 'NOT RUN': 475}**. [Exact ledger](test-results.jsonl), [category/tier totals](summary.json), [remaining IDs](remaining-case-ids.txt). Next NOT RUN **JRV-23-001**; earliest older unresolved **JRV-04-001**. [Previous Prompt21 report](final-report-before-module22.md). Overall37-module audit remains incomplete; no production-ready certificate.

## Enumerated modules

| Module | Catalog status |
| --- | --- |
| 01 architecture-inventory | PASS: 32 |
| 02 perception-cognition | PASS: 32 |
| 03 intent-direct | PASS: 32 |
| 04 voice-stt | BLOCKED: 3, PASS: 29 |
| 05 voice-tts | PASS: 30, BLOCKED: 2 |
| 06 questions-context | PASS: 30, BLOCKED: 2 |
| 07 model-routing | PASS: 32 |
| 08 gpu-scheduler | PASS: 30, BLOCKED: 2 |
| 09 deliberation | PASS: 31, BLOCKED: 1 |
| 10 dag-planning | PASS: 32 |
| 11 skill-selection | PASS: 31, BLOCKED: 1 |
| 12 tool-registry | PASS: 32 |
| 13 desktop-control | PASS: 30, BLOCKED: 2 |
| 14 browser-playwright | PASS: 30, BLOCKED: 2 |
| 15 app-research | PASS: 31, BLOCKED: 1 |
| 16 memory | PASS: 28, BLOCKED: 4 |
| 17 rag-documents | PASS: 28, BLOCKED: 4 |
| 18 repo-learning | PASS: 30, BLOCKED: 2 |
| 19 ability-forge | PASS: 32 |
| 20 self-evolution | PASS: 28, BLOCKED: 4 |
| 21 native-coding | PASS: 27, BLOCKED: 5 |
| 22 web-development | PASS: 18, BLOCKED: 14 |
| 23 gmail | NOT RUN: 32 |
| 24 whatsapp | NOT RUN: 32 |
| 25 media | NOT RUN: 32 |
| 26 realtime-data | NOT RUN: 31, PASS: 1 |
| 27 gods-eye | NOT RUN: 32 |
| 28 sandbox-deerflow | NOT RUN: 32 |
| 29 reverse-engineering | NOT RUN: 31, PASS: 1 |
| 30 harness-planners | NOT RUN: 32 |
| 31 ui-island-pip | NOT RUN: 32 |
| 32 service-recovery | NOT RUN: 32 |
| 33 mcp-integrations | NOT RUN: 32 |
| 34 dependencies | NOT RUN: 31, PASS: 1 |
| 35 security | NOT RUN: 30, PASS: 2 |
| 36 observability | NOT RUN: 32 |
| 37 e2e | NOT RUN: 32 |

## Category and tier statistics

```json
{
  "by_category": {
    "config": {
      "PASS": 22,
      "NOT RUN": 15
    },
    "contract": {
      "PASS": 22,
      "NOT RUN": 15
    },
    "edge": {
      "PASS": 44,
      "NOT RUN": 30
    },
    "fault": {
      "PASS": 87,
      "BLOCKED": 1,
      "NOT RUN": 60
    },
    "idempotency": {
      "PASS": 21,
      "BLOCKED": 1,
      "NOT RUN": 15
    },
    "load": {
      "PASS": 22,
      "NOT RUN": 15
    },
    "observability": {
      "PASS": 18,
      "BLOCKED": 4,
      "NOT RUN": 15
    },
    "performance": {
      "PASS": 21,
      "BLOCKED": 1,
      "NOT RUN": 15
    },
    "privacy": {
      "PASS": 21,
      "BLOCKED": 1,
      "NOT RUN": 15
    },
    "race": {
      "PASS": 22,
      "NOT RUN": 15
    },
    "recovery": {
      "PASS": 40,
      "BLOCKED": 4,
      "NOT RUN": 30
    },
    "resource": {
      "PASS": 21,
      "BLOCKED": 1,
      "NOT RUN": 15
    },
    "scenario": {
      "PASS": 234,
      "BLOCKED": 35,
      "NOT RUN": 175
    },
    "security": {
      "PASS": 44,
      "NOT RUN": 30
    },
    "semantic": {
      "PASS": 21,
      "BLOCKED": 1,
      "NOT RUN": 15
    }
  },
  "by_tier": {
    "P0": {
      "PASS": 162,
      "BLOCKED": 15,
      "NOT RUN": 119
    },
    "P1": {
      "PASS": 354,
      "BLOCKED": 23,
      "NOT RUN": 252
    },
    "P2": {
      "PASS": 144,
      "BLOCKED": 11,
      "NOT RUN": 104
    }
  }
}
```
