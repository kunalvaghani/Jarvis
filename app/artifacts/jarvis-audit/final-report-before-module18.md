# Jarvis audit — Prompt 17 follow-up, 2026-10-16 IST

**Document audit — 2026-10-16 IST:** Bounded extraction/context, multilingual tokenization, stale-source checks, atomic session writes and drop admission guards added. Warm BM25 lookup p50/p95 **0.8772/0.9154 → 0.0550/0.0591 ms** on 1,500 identical chunks; top5 IDs/pages/text identical; scores match to 10 decimal places.
Verification: **2,654 full regression PASS / 40 skips**; **28 Prompt 17 catalog PASS /4 BLOCKED**. Cross-document conflicts, semantic citation faithfulness, hard parser resource isolation and operation traces remain incomplete. Launcher **repair_required**. Installed pypdf 6.20.0 predates the 6.20.1 cyclic-tree security fix; no dependency installation performed.

Synthetic PDF/DOCX/text, fake local model/HTTP/account transports, temporary session/index readback. Actual owned Tk WM_DROPFILES and child event-loop regression fixtures ran; no Explorer drag, real document/account, live model/GPU, microphone or Obsidian trial.

[Source-map/code/config/assertion matrix](modules/17-rag-documents/inventory.md), [all 32 IDs](modules/17-rag-documents/tests.jsonl), [targeted XML](modules/17-rag-documents/cases-and-contracts.xml), [full XML](modules/17-rag-documents/full-regression.xml), [actual synthetic journey](modules/17-rag-documents/document-journey.json), [redacted readiness](modules/17-rag-documents/readiness.json).

Repo HEAD **e1a33a0944b5cd725e1a76a72eda228513e45963**, retained branch **audit/12-tool-registry**, no commit; inherited user/module14–16 changes preserved. [Actual environment](modules/17-rag-documents/environment.json): Windows/Python3.10.6, pypdf6.20.0, RAM33656832000B; target Ryzen7/32GB/RTX3050Laptop4GB. No GPU/model/audio performance claim. 379 runtime/test file hashes unchanged during accepted full run. [Implementation/docs files](modules/17-rag-documents/files-changed.json), [generated output files](modules/17-rag-documents/generated-files.json), [complete scoped diff](modules/17-rag-documents/source.patch), [preimage hashes](modules/17-rag-documents/source-hashes.json). No manifest/launcher/recovery or dependency/service interface change.

Baseline **30 PASS /2 native deselected**; final targeted **156 PASS /11 BLOCKED skips**; accepted full **2654 PASS /40 skips /0FAIL**. Counts overlap and are not unique catalog totals. [Failure history/harness correction](modules/17-rag-documents/failures.md) preserved; no pass awarded merely from reading a catalog row. Actual owned native drop/event-loop and buddy regression fixtures ran; user Explorer drag/live sends were not run. Synthetic drop/command/restart journey **0.690s**, authored local response, zero network/external-effect calls.

Warm BM25 lookup p50/p95 **0.8772/0.9154 → 0.0550/0.0591 ms** on 1,500 identical chunks; top5 IDs/pages/text identical; scores match to 10 decimal places. Warm traced temporary lookup peak 1566→1462B. Five fresh prepared-index queries/20warm per version; [50raw samples](modules/17-rag-documents/benchmarks.csv), [scope](modules/17-rag-documents/benchmark-summary.json), [keep/defer tradeoffs](modules/17-rag-documents/changes.md). Persistent postings memory/index construction/hash/parsing/TTFT/audio/VRAM excluded; no overall end-to-end speed/memory claim. Prior per-module measurements retained [through16](final-report-before-module17.md).

## Open gates and risk

JRV-17-003: the answer API selects one document; no cross-document conflict arbitration. JRV-17-005: extracted text is capped, but pypdf parses page streams in-process without a hard RAM/time sandbox. JRV-17-012: valid page numbers do not establish semantic entailment; a fake wrong date with a valid page passes. JRV-17-032: document/model/spill operations lack unified redacted operation trace IDs.

Firecrawl [official URLs/dates](modules/17-rag-documents/upstream-checks.json), [compatibility](modules/17-rag-documents/compatibility.md): pypdf 6.20.1(2026-10-12) adds a cyclic-tree security fix absent from installed6.20.0; Python requirement compatible, no installation under prompt boundary. Upstream LightRAG/GraphRAG are comparison projects, not installed Jarvis dependencies. No untrusted-PDF security certification, complex-table/OCR/semantic entailment, general multi-document or production-readiness claim. Existing acoustic/GPU/account/other module gates remain. Readiness **repair_required**: docker: unavailable (DockerEngineUnavailable), ollama: unavailable (ConnectionError). No service repair/start or package download attempted.

[Scoped rollback and exact resume](modules/17-rag-documents/rollback.md). Next NOT RUN **JRV-18-001**; earliest older unresolved **JRV-04-001**. All 1,184 unique IDs: **{'PASS': 525, 'FAIL': 0, 'BLOCKED': 24, 'SKIPPED': 0, 'NOT RUN': 635}**. [Exact ledger](test-results.jsonl), [tier/category totals](summary.json), [exact remaining IDs](remaining-case-ids.txt). Missing contracts are explicit BLOCKED, not claimed complete.

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
      "PASS": 130,
      "BLOCKED": 7,
      "NOT RUN": 159
    },
    "P1": {
      "PASS": 280,
      "BLOCKED": 12,
      "NOT RUN": 337
    },
    "P2": {
      "PASS": 115,
      "BLOCKED": 5,
      "NOT RUN": 139
    }
  },
  "by_category": {
    "config": {
      "PASS": 17,
      "NOT RUN": 20
    },
    "contract": {
      "PASS": 17,
      "NOT RUN": 20
    },
    "edge": {
      "PASS": 34,
      "NOT RUN": 40
    },
    "fault": {
      "PASS": 68,
      "NOT RUN": 80
    },
    "idempotency": {
      "PASS": 17,
      "NOT RUN": 20
    },
    "load": {
      "PASS": 17,
      "NOT RUN": 20
    },
    "observability": {
      "PASS": 15,
      "BLOCKED": 2,
      "NOT RUN": 20
    },
    "performance": {
      "PASS": 17,
      "NOT RUN": 20
    },
    "privacy": {
      "PASS": 17,
      "NOT RUN": 20
    },
    "race": {
      "PASS": 17,
      "NOT RUN": 20
    },
    "recovery": {
      "PASS": 34,
      "NOT RUN": 40
    },
    "resource": {
      "PASS": 17,
      "NOT RUN": 20
    },
    "scenario": {
      "PASS": 187,
      "BLOCKED": 22,
      "NOT RUN": 235
    },
    "security": {
      "PASS": 34,
      "NOT RUN": 40
    },
    "semantic": {
      "PASS": 17,
      "NOT RUN": 20
    }
  }
}
```
