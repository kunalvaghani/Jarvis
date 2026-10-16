# Jarvis audit — Prompt23 — 2026-10-16 IST

**Gmail audit — 2026-10-16 IST:** Approval now refuses False/changed fields, draft writes recheck freshness after approval, and damaged journals fail closed. FileBuddy attachment drafts now require approval and durable non-replay records. **24 Prompt23 fixture PASS /8 BLOCKED**; full regression **2,900 PASS /56 skips /0 failures**, launcher **ready**. No live Gmail trial. Adapter source verification is stale until separately reviewed; account isolation, complete privacy/resource/replay/observability contracts remain incomplete.

HEAD **9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6**, branch **audit/12-tool-registry**, inherited diffs preserved. [Environment](modules/23-gmail/environment.json). Baseline {'PASS': 66, 'FAIL': 0, 'SKIPPED': 0, 'seconds': 10.733}; combined focused {'PASS': 68, 'FAIL': 0, 'SKIPPED': 8, 'seconds': 4.4350000000000005}; full tests-directory {'PASS': 2900, 'FAIL': 0, 'SKIPPED': 56, 'seconds': 550.263}. Full command excludes the separately executed3-test supplement. All **385 frozen runtime/test hashes unchanged**. [Full XML](modules/23-gmail/full-regression.xml), [skips](modules/23-gmail/full-regression-skip-reasons.json), [readiness](modules/23-gmail/readiness.json).

Owned in-memory Gmail mailboxes and fake OAuth/HTTP, isolated DPAPI-token placeholders, actual durable journal locks/checkpoints, an owned child exiting23 after its write-intent checkpoint, five independent fake-mailbox writes ×20 rounds, and existing headless Gmail-like DOM/document fixtures. No live mailbox/profile read, real draft/send/Trash/label/delete, token decryption, consent/refresh request, credential setup, account verification, service restart, install or model/GPU trial. The Chrome DOM fixture intercepts mail.google.com with authored local HTML; it is not live Gmail. The independently executed supplement adds exact-recipient drafts, insufficient-scope refusal and inert hidden HTML; it is outside the full tests-directory command and included in changed-file hashes.

Same HTML-draft update CPU warm p50/p95 **10.0738/10.3053 → 8.4738/8.5884 ms**, traced peak **141482 → 123313 bytes**;50 calls, byte-identical MIME and result, one fake PUT/sample, zero real mailbox writes. Initial5 calls are not fresh-process cold starts. OAuth/network/browser/RSS/VRAM excluded. Reusing parsed draft info avoids a second decode; the new freshness guard adds one real GET after approval, so remote end-to-end latency may increase.

[Source-map matrix](modules/23-gmail/inventory.md), [changes/metrics](modules/23-gmail/changes.md), [exact files](modules/23-gmail/files-changed.json), [diff](modules/23-gmail/source.patch), [official URLs/dates](modules/23-gmail/compatibility.md), [risks/flaws](modules/23-gmail/failures.md), [rollback/resume](modules/23-gmail/rollback.md), [commands/results](modules/23-gmail/commands.txt).

- **JRV-23-010 BLOCKED:** One OAuth-selected account per base; no explicit multi-account identity broker or account-bound approval/journal. Separate fake clients are not complete account-switch isolation proof.
- **JRV-23-012 BLOCKED:** File attachments stay remote on reads, and attachment draft approval/journaling now have fixtures; a complete attachment secret-to-model oracle and attachment/body upload readback are absent.
- **JRV-23-018 BLOCKED:** Before-write cancellation and Stop during fresh observation are covered; complete TaskState cancellation semantics during readback are unproved.
- **JRV-23-021 BLOCKED:** Local interpreter context is bounded; no complete fake-cloud/private-context/log-redaction oracle across all mail and attachment flows.
- **JRV-23-025 BLOCKED:** No complete Gmail RAM/GPU-pressure admission and core-command responsiveness proof. Ordinary adapter operations use no GPU; composition does.
- **JRV-23-026 BLOCKED:** Uncertain outcomes refuse replay; successfully completed identical events have no durable event-ID deduplication contract. A new explicit approved request can repeat identical mail.
- **JRV-23-027 BLOCKED:** Draft-update CPU A/B is measured; complete OAuth/workflow cold-start/RSS/VRAM benchmark absent.
- **JRV-23-032 BLOCKED:** Journals omit body/subject and transport errors are categorical; complete private-data redaction and cross-flow correlation remain unproved.

All1,184 IDs: **{'PASS': 684, 'FAIL': 0, 'BLOCKED': 57, 'SKIPPED': 0, 'NOT RUN': 443}**. [Ledger](test-results.jsonl), [category/tier statistics](summary.json), [remaining IDs](remaining-case-ids.txt). Next NOT RUN **JRV-24-001**; earliest unresolved **JRV-04-001**. [Previous Prompt22 report](final-report-before-module23.md). No production-ready certificate; overall37-module audit remains incomplete.

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
| 23 gmail | PASS: 24, BLOCKED: 8 |
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
      "PASS": 23,
      "NOT RUN": 14
    },
    "contract": {
      "PASS": 23,
      "NOT RUN": 14
    },
    "edge": {
      "PASS": 46,
      "NOT RUN": 28
    },
    "fault": {
      "PASS": 90,
      "BLOCKED": 2,
      "NOT RUN": 56
    },
    "idempotency": {
      "PASS": 21,
      "BLOCKED": 2,
      "NOT RUN": 14
    },
    "load": {
      "PASS": 23,
      "NOT RUN": 14
    },
    "observability": {
      "PASS": 18,
      "BLOCKED": 5,
      "NOT RUN": 14
    },
    "performance": {
      "PASS": 21,
      "BLOCKED": 2,
      "NOT RUN": 14
    },
    "privacy": {
      "PASS": 21,
      "BLOCKED": 2,
      "NOT RUN": 14
    },
    "race": {
      "PASS": 23,
      "NOT RUN": 14
    },
    "recovery": {
      "PASS": 42,
      "BLOCKED": 4,
      "NOT RUN": 28
    },
    "resource": {
      "PASS": 21,
      "BLOCKED": 2,
      "NOT RUN": 14
    },
    "scenario": {
      "PASS": 244,
      "BLOCKED": 37,
      "NOT RUN": 163
    },
    "security": {
      "PASS": 46,
      "NOT RUN": 28
    },
    "semantic": {
      "PASS": 22,
      "BLOCKED": 1,
      "NOT RUN": 14
    }
  },
  "by_tier": {
    "P0": {
      "PASS": 168,
      "BLOCKED": 17,
      "NOT RUN": 111
    },
    "P1": {
      "PASS": 369,
      "BLOCKED": 25,
      "NOT RUN": 235
    },
    "P2": {
      "PASS": 147,
      "BLOCKED": 15,
      "NOT RUN": 97
    }
  }
}
```
