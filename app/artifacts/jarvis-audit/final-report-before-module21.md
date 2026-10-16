# Jarvis audit — Prompt20 — 2026-10-16 IST

**Idle evolution audit — 2026-10-16 IST:** Interrupted discovery is recoverable; uncertain learning writes stay in `needs_review`. Daily budgets and a three-attempt cap persist, saver/resource failures defer, and private/negative topics are screened before public discovery. Patches require fresh code/test-bound evaluation and approval; rollback refuses later edits.
Verification: **2,796 full regression PASS /36 skips**; **28 Prompt20 fixture PASS /4 BLOCKED**. Native game preemption, safe automatic write resume, privacy/canary and lockfile rollout remain open. Launcher **repair_required**.

HEAD **e1a33a0944b5cd725e1a76a72eda228513e45963**, branch **audit/12-tool-registry**; inherited changes preserved, no audit commit. [Environment](modules/20-self-evolution/environment.json). Baseline {'PASS': 96, 'FAIL': 0, 'SKIPPED': 0, 'seconds': 26.639}; targeted {'PASS': 183, 'FAIL': 0, 'SKIPPED': 4, 'seconds': 36.317}; full {'PASS': 2796, 'FAIL': 0, 'SKIPPED': 36, 'seconds': 455.362}. All **382 frozen runtime/test hashes unchanged**. [Full output](modules/20-self-evolution/full-regression.xml), [skip reasons](modules/20-self-evolution/full-regression-skip-reasons.json), [readiness](modules/20-self-evolution/readiness.json).

Owned temporary backlogs/files/Git repositories; fake discovery, learners, approval, CPU/RAM/GPU failures and clock. Actual owned child exits29 during discovery; reload returns that read step to pending and completes with a fake learner. Actual trusted Git worktree→pytest assertion→refused approval→approved owned fixture deploy→readback→explicit rollback ran. No Jarvis source was self-patched, no real ability installed, no dependency installation, account operation, OS setting change, model download or live inference/voice/GUI trial. Native Windows power-saving state was read without changing it. The card image is a rendered fixture preview, not a native screenshot.

Next-job selection warm p50/p95 **0.4128/0.4465→0.3599/0.3694ms**, traced peak **33944→664B** on the same1,000 eligible/tied fixture rows. Exact selected signature/tie order preserved. This excludes I/O, inference, audio, GPU, construction and energy measurements.

[Source-map-to-code evidence matrix](modules/20-self-evolution/inventory.md), [changes/metrics](modules/20-self-evolution/changes.md), [exact files](modules/20-self-evolution/files-changed.json), [diff](modules/20-self-evolution/source.patch), [upstream URLs/dates](modules/20-self-evolution/compatibility.md), [risk/known flaws](modules/20-self-evolution/failures.md), [rollback/resume](modules/20-self-evolution/rollback.md), [commands/results](modules/20-self-evolution/commands.txt).

- **JRV-20-002 BLOCKED:** No native game/GPU occupancy sensor or guaranteed kernel preemption. Cooperative busy/activity/resource callbacks are tested; blocking I/O/native kernels may finish before yielding.
- **JRV-20-003 BLOCKED:** Learner writes lack a transactional completion receipt. Durable `needs_review` prevents uncertain replays, but automatic safe continuation through an interrupted repository write is not proved; no dedicated review/resume UI.
- **JRV-20-006 BLOCKED:** No independent semantic privacy oracle, hardened host patch execution sandbox, shadow evaluation or canary/automatic post-deploy rollback. A source worktree is not security isolation.
- **JRV-20-011 BLOCKED:** Only a single eligible Jarvis Python source target is supported; no lockfile/environment migration rollout or reproducible dependency environment test exists. Dependency inputs invalidate receipts, but are not upgraded by this manager.

No production-ready certificate. All1,184 IDs: **{'PASS': 615, 'FAIL': 0, 'BLOCKED': 30, 'SKIPPED': 0, 'NOT RUN': 539}**. [Exact ledger](test-results.jsonl), [tier/category counts](summary.json), [remaining IDs](remaining-case-ids.txt). Next NOT RUN **JRV-21-001**; earliest unresolved **JRV-04-001**; current missing contracts002/003/006/011. [Previous Prompt19 report](final-report-before-module20.md) preserves its original evidence. The overall37-module production audit remains incomplete.

## Enumerated modules

| Module | Catalog statuses |
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
| 21 native-coding | NOT RUN: 32 |
| 22 web-development | NOT RUN: 32 |
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
      "PASS": 20,
      "NOT RUN": 17
    },
    "contract": {
      "PASS": 20,
      "NOT RUN": 17
    },
    "edge": {
      "PASS": 40,
      "NOT RUN": 34
    },
    "fault": {
      "PASS": 80,
      "NOT RUN": 68
    },
    "idempotency": {
      "PASS": 20,
      "NOT RUN": 17
    },
    "load": {
      "PASS": 20,
      "NOT RUN": 17
    },
    "observability": {
      "PASS": 18,
      "BLOCKED": 2,
      "NOT RUN": 17
    },
    "performance": {
      "PASS": 20,
      "NOT RUN": 17
    },
    "privacy": {
      "PASS": 20,
      "NOT RUN": 17
    },
    "race": {
      "PASS": 20,
      "NOT RUN": 17
    },
    "recovery": {
      "PASS": 39,
      "BLOCKED": 1,
      "NOT RUN": 34
    },
    "resource": {
      "PASS": 20,
      "NOT RUN": 17
    },
    "scenario": {
      "PASS": 218,
      "BLOCKED": 27,
      "NOT RUN": 199
    },
    "security": {
      "PASS": 40,
      "NOT RUN": 34
    },
    "semantic": {
      "PASS": 20,
      "NOT RUN": 17
    }
  },
  "by_tier": {
    "P0": {
      "PASS": 151,
      "BLOCKED": 10,
      "NOT RUN": 135
    },
    "P1": {
      "PASS": 329,
      "BLOCKED": 14,
      "NOT RUN": 286
    },
    "P2": {
      "PASS": 135,
      "BLOCKED": 6,
      "NOT RUN": 118
    }
  }
}
```
