# Jarvis audit — Prompt 28, 2026-10-16 IST

**PARTIAL: 20 sandbox/DeerFlow catalog fixture PASS / 12 BLOCKED. No general production acceptance.**

Preserved dirty branch `audit/12-tool-registry`, commit `9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6`, canonical `app/`. Main Python 3.10.6, Windows-10-10.0.26200-SP0, RAM 33656832000 bytes; optional Python 3.12.14. Target RTX 3050 Laptop 4 GB from earlier census; no GPU/LLM workload. [Environment](modules/28-sandbox-deerflow/environment.json), [optional package metadata](modules/28-sandbox-deerflow/optional-runtime.json).

Mock-based Docker, worker, restart and transport faults; isolated files/checkpoints; five concurrent writes × 20 rounds and an owned checkpoint-crash child. Separately, nine actual owned ephemeral containers used the installed reviewed image: synthetic 2+2/UID/isolation, all seven literal media recipes, and a nonzero exit with stop/no-replay and cleanup. Stock narration ran CPU ONNX with existing assets and was not played. No Desktop startup/restart, image pull/build, dependency installation, account operation, personal input mount, public research query, LLM inference, audible playback or GPU workload. Only the attested fixture containers were removed; generated files were preserved. Historical measurements and artwork remain dated; no new GUI screenshot is claimed.

## Source-map evidence

| Claim | Actual entry/source | Executed evidence and limit |
| --- | --- | --- |
| Research tools | ToolRegistry → deerflow.execute/request → owned deerflow_worker → scoped observe | 7 registered tools; 23 public guides; real harness registration/discovery, mocked worker faults and existing source-receipt assertions; no new live model/public research trial |
| Network separation | worker research/web_research/sandbox allowlists; SandboxJob.create | Public web route omits local project context; Docker NetworkMode=none inspected. No account/browser/host-exec tools in the research adapter; semantic prompt/approval gaps remain |
| Isolation | SandboxJob.create → RepositorySandbox.cli → local Linux Docker | Actual UID 65534, root read-only, no network, capabilities dropped, no-new-privileges, 2 GiB RAM/swap, 128 PID limit; mounts inspected against allowed destinations, no Docker socket; no hostile-daemon guarantee |
| Mounts | SandboxJob._local/create/stage_inputs/path | Reparse/link checks include application/job/skills/model ancestors; explicit copied inputs and no project mount; fake linked ancestor rejected before run. Not atomic handle-based containment against a hostile host mutating directories |
| Identity | immutable image ID, new state.container_id, owned() | New jobs pin full Docker ID; exec/kill/remove target inspected ID; replaced-ID test refuses. Legacy checkpoints without container_id still use image/label/name attestation |
| Budgets and recovery | execute/observe/_checkpoint/save; DockerService | Pending attempted/uncertain checkpoint fences different commands after restart; locked writes use exclusive create and shared 20-effect budget; 512K-character checkpoint bound and schema validation. Daemon startup remains existing managed behavior, not a new lazy-start policy |
| Timeouts/nonzero | Linux timeout + bounded Docker CLI + uncertainty checkpoint | Injected timeout kills attested owned job; real exit 7 stops its container, retains uncertainty and refuses replay; cleanup inspected. Complete logs/daemon-outage recovery remain incomplete |
| Media | deerflow_media.validate/execute/verify_artifacts | All 7 installed literal recipes exercised; chart PNG 1280×720, malformed PNG rejected. PNG uses Pillow structure checks; WAV PCM readback, bounded PPTX ZIP/CRC checks; PDF/MP4 envelope checks alone do not prove pages/codecs/frames |
| Outputs | SandboxJob.inventory → actual files; parent artifact_evidence | Bounded deterministic lexical traversal preserves first 200 paths/sizes, platform ordering and link exclusions; directory/depth/traversal budgets. Actual file evidence remains distinct from model prose |
| Lifecycle | owned worker/OwnedJob; DockerService; close/reap_orphans | Existing Start/Stop/bootstrap/launcher/recovery interfaces unchanged; no shared-engine stop, personal config edit, dependency or new service. Aggregate admission and cross-process job locks are not added |

## Executed assertions and measurements

Baseline **30 passed**. Focused **84 PASS / 12 explicit BLOCKED skips / 0 FAIL**. Full Python tests-directory **3065 PASS / 124 skipped / 0 FAIL in 564.951s** (JUnit suite time; console wall time in log), one existing COM-threading warning. Launcher dependency/configuration readiness **ready**, optional Groq not live checked. Actual installed-image offline fixture checks passed math=4, UID/isolation, all seven literal recipes with declared format proof levels, nonzero→uncertain/stopped/no replay, and cleanup of only owned containers. No current live DeerFlow LLM/research or general media quality acceptance claim.

For 3,000 synthetic files and identical first 200 inventory rows, warm p50/p95 changed from 717.24235/797.70220 ms to 646.88830/739.16570 ms; peak temporary Python allocation 5313699 → 719966 bytes. [Raw samples](modules/28-sandbox-deerflow/benchmarks.csv). Keep final traversal; first slower candidate is preserved. Five initial iterations are not cold process starts. No TTFT/audio/network/model/container/render/RSS/VRAM speed claim.

All 392 frozen runtime/test files remained unchanged during the full run. [Hashes](modules/28-sandbox-deerflow/full-start-source-hashes.json), [full log](modules/28-sandbox-deerflow/full-regression.log), [XML](modules/28-sandbox-deerflow/full-regression.xml), [skip reasons](modules/28-sandbox-deerflow/full-regression-skip-reasons.json), [container receipt](modules/28-sandbox-deerflow/container-fixture.json), [other recipe receipts](modules/28-sandbox-deerflow/renderer-fixtures.json), [source inventory](modules/28-sandbox-deerflow/source-inventory.json), [repro/failure history](modules/28-sandbox-deerflow/failures.md), [commands](modules/28-sandbox-deerflow/commands.md), [changed files](modules/28-sandbox-deerflow/files-changed.json), [diff](modules/28-sandbox-deerflow/source.patch), [upstream URLs/dates](modules/28-sandbox-deerflow/compatibility.md), [retrieval metadata](modules/28-sandbox-deerflow/upstream-checks.json), [rollback](modules/28-sandbox-deerflow/rollback.md).

## Exact 1,184-case accounting

**{"PASS": 773, "FAIL": 0, "BLOCKED": 127, "SKIPPED": 0, "NOT RUN": 284}**. Every Prompt 28 case has executed assertions or an explicit blocker; narrower passed tests never override incomplete full-case contracts. Historical module evidence and metrics remain linked.

| Module/evidence | Status | PASS | BLOCKED | NOT RUN |
| --- | --- | ---: | ---: | ---: |
| [01-architecture-inventory](modules/01-architecture-inventory/inventory.md) | PARTIAL | 32 | 0 | 0 |
| [02-perception-cognition](modules/02-perception-cognition/inventory.md) | FIXTURE COMPLETE | 32 | 0 | 0 |
| [03-intent-direct](modules/03-intent-direct/inventory.md) | FIXTURE COMPLETE | 32 | 0 | 0 |
| [04-voice-stt](modules/04-voice-stt/inventory.md) | LIVE ACOUSTIC VALIDATION BLOCKED | 29 | 3 | 0 |
| [05-voice-tts](modules/05-voice-tts/inventory.md) | LIVE ACCEPTANCE BLOCKED | 30 | 2 | 0 |
| [06-questions-context](modules/06-questions-context/inventory.md) | 30 CURRENT FIXTURE PASS / 2 NATIVE ACCEPTANCE BLOCKED | 30 | 2 | 0 |
| [07-model-routing](modules/07-model-routing/inventory.md) | FIXTURE COMPLETE / LIVE CLOUD BLOCKED | 32 | 0 | 0 |
| [08-gpu-scheduler](modules/08-gpu-scheduler/inventory.md) | PARTIAL / SHARED SPEECH COORDINATION BLOCKED | 30 | 2 | 0 |
| [09-deliberation](modules/09-deliberation/inventory.md) | PARTIAL / MANDATORY UNFAMILIAR-PROGRAM RESEARCH BLOCKED | 31 | 1 | 0 |
| [10-dag-planning](modules/10-dag-planning/inventory.md) | FIXTURE COMPLETE / LIVE ACCEPTANCE UNVERIFIED | 32 | 0 | 0 |
| [11-skill-selection](modules/11-skill-selection/inventory.md) | 31 FIXTURE PASS / 1 BLOCKED; LIVE ACCEPTANCE UNVERIFIED | 31 | 1 | 0 |
| [12-tool-registry](modules/12-tool-registry/inventory.md) | 32 FIXTURE PASS; LIVE ACCEPTANCE UNVERIFIED | 32 | 0 | 0 |
| [13-desktop-control](modules/13-desktop-control/inventory.md) | 30 FIXTURE PASS / 2 BLOCKED; LIVE DESKTOP ACCEPTANCE UNVERIFIED | 30 | 2 | 0 |
| [14-browser-playwright](modules/14-browser-playwright/inventory.md) | 30 FIXTURE PASS / 2 BLOCKED; LIVE SITE ACCEPTANCE UNVERIFIED | 30 | 2 | 0 |
| [15-app-research](modules/15-app-research/inventory.md) | PARTIAL | 31 | 1 | 0 |
| [16-memory](modules/16-memory/inventory.md) | PARTIAL | 28 | 4 | 0 |
| [17-rag-documents](modules/17-rag-documents/inventory.md) | PARTIAL | 28 | 4 | 0 |
| [18-repo-learning](modules/18-repo-learning/inventory.md) | PARTIAL | 30 | 2 | 0 |
| [19-ability-forge](modules/19-ability-forge/inventory.md) | FIXTURE VERIFIED; LIVE/HARDENING GATES OPEN | 32 | 0 | 0 |
| [20-self-evolution](modules/20-self-evolution/inventory.md) | PARTIAL | 28 | 4 | 0 |
| [21-native-coding](modules/21-native-coding/inventory.md) | PARTIAL | 27 | 5 | 0 |
| [22-web-development](modules/22-web-development/inventory.md) | PARTIAL | 18 | 14 | 0 |
| [23-gmail](modules/23-gmail/inventory.md) | PARTIAL | 24 | 8 | 0 |
| [24-whatsapp](modules/24-whatsapp/inventory.md) | PARTIAL | 14 | 18 | 0 |
| [25-media](modules/25-media/inventory.md) | PARTIAL | 16 | 16 | 0 |
| [26-realtime-data](modules/26-realtime-data/inventory.md) | PARTIAL | 20 | 12 | 0 |
| [27-gods-eye](modules/27-gods-eye/inventory.md) | PARTIAL | 20 | 12 | 0 |
| [28-sandbox-deerflow](modules/28-sandbox-deerflow/inventory.md) | PARTIAL | 20 | 12 | 0 |
| [29-reverse-engineering](modules/29-reverse-engineering/inventory.md) | PARTIAL | 1 | 0 | 31 |
| [30-harness-planners](modules/30-harness-planners/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [31-ui-island-pip](modules/31-ui-island-pip/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [32-service-recovery](modules/32-service-recovery/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [33-mcp-integrations](modules/33-mcp-integrations/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [34-dependencies](modules/34-dependencies/inventory.md) | PARTIAL | 1 | 0 | 31 |
| [35-security](modules/35-security/inventory.md) | PARTIAL | 2 | 0 | 30 |
| [36-observability](modules/36-observability/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [37-e2e](modules/37-e2e/inventory.md) | PARTIAL | 0 | 0 | 32 |


Tier totals:
```json
{
  "P0": {
    "PASS": 194,
    "BLOCKED": 31,
    "NOT RUN": 71
  },
  "P1": {
    "PASS": 419,
    "BLOCKED": 59,
    "NOT RUN": 151
  },
  "P2": {
    "PASS": 160,
    "BLOCKED": 37,
    "NOT RUN": 62
  }
}
```
Category totals:
```json
{
  "config": {
    "PASS": 27,
    "BLOCKED": 1,
    "NOT RUN": 9
  },
  "contract": {
    "PASS": 24,
    "BLOCKED": 4,
    "NOT RUN": 9
  },
  "edge": {
    "PASS": 53,
    "BLOCKED": 3,
    "NOT RUN": 18
  },
  "fault": {
    "PASS": 106,
    "BLOCKED": 6,
    "NOT RUN": 36
  },
  "idempotency": {
    "PASS": 23,
    "BLOCKED": 5,
    "NOT RUN": 9
  },
  "load": {
    "PASS": 26,
    "BLOCKED": 2,
    "NOT RUN": 9
  },
  "observability": {
    "PASS": 18,
    "BLOCKED": 10,
    "NOT RUN": 9
  },
  "performance": {
    "PASS": 21,
    "BLOCKED": 7,
    "NOT RUN": 9
  },
  "privacy": {
    "PASS": 21,
    "BLOCKED": 7,
    "NOT RUN": 9
  },
  "race": {
    "PASS": 25,
    "BLOCKED": 3,
    "NOT RUN": 9
  },
  "recovery": {
    "PASS": 46,
    "BLOCKED": 10,
    "NOT RUN": 18
  },
  "resource": {
    "PASS": 21,
    "BLOCKED": 7,
    "NOT RUN": 9
  },
  "scenario": {
    "PASS": 282,
    "BLOCKED": 58,
    "NOT RUN": 104
  },
  "security": {
    "PASS": 55,
    "BLOCKED": 1,
    "NOT RUN": 18
  },
  "semantic": {
    "PASS": 25,
    "BLOCKED": 3,
    "NOT RUN": 9
  }
}
```

## Remaining contracts and risk

- **JRV-28-005 BLOCKED:** Offline confinement is tested, but untrusted-repository installer provenance and a separate explicit approval event are not enforced by a dedicated sandbox installer gate.
- **JRV-28-008 BLOCKED:** Wrong PNG structure and missing optional runtime are refused; all seven installed literal recipes were exercised. Uniform per-renderer missing-module/font/codec/voice readiness probes and precise unavailable-capability diagnostics are not implemented.
- **JRV-28-009 BLOCKED:** Per-container CPU limits are configured and RAM/PID limits inspected. No cross-process admission quota for multiple DeerFlow research/render jobs; each job still requests 2 CPUs/2 GiB independently.
- **JRV-28-010 BLOCKED:** Failed/unobserved sources cannot authorize a matching receipt. HTTP-200 paywalls, teaser text and incomplete extraction lack a comprehensive paywall/content-availability classifier.
- **JRV-28-012 BLOCKED:** Unknown/failed/mismatched source-call citations are rejected by existing tests. Resolved citation IDs do not verify claim entailment, source quality or factual correctness.
- **JRV-28-015 BLOCKED:** Non-object worker JSON now returns a controlled protocol error, and checkpoint/media validation is stronger. A complete typed schema for result/receipt/source/artifact/tool data is absent.
- **JRV-28-021 BLOCKED:** No host credential env or project mount is offered to the tested container, and public research omits the project field. No full fake-secret/cloud/Groq/telemetry/cache oracle; commands/diagnostics and selected input copies may contain private content locally.
- **JRV-28-023 BLOCKED:** Cancellation is deterministic, but there is no complete semantic negation oracle for natural-language research/sandbox goals. A model’s interpretation of “do not run X” is not a permission guarantee.
- **JRV-28-025 BLOCKED:** Per-container limits and bounded filesystem fixtures pass; no full host RAM-pressure/GPU-allocation failure versus responsive core-command test. No GPU workload ran.
- **JRV-28-027 BLOCKED:** A/B measures 20 warm and five initial inventory iterations with tracemalloc. Not five cold processes/full harness/container jobs with RSS/VRAM, TTFT/audio or general research/render latency.
- **JRV-28-030 BLOCKED:** Owned worker cancellation and real nonzero-container failure are covered. Full daemon/worker disconnect/crash recovery with task provenance, durable cleanup retry and cross-process leases remains incomplete.
- **JRV-28-032 BLOCKED:** Job IDs, state, image/container identity and output hashes exist. Raw command/diagnostic/error files and full model/research traces lack a complete private-data redaction/correlation/readback oracle.

The Docker daemon/kernel is a trusted boundary, not a proven escape-proof sandbox. Latest platform security releases were researched but not installed. Link checks are not atomic filesystem-handle containment; legacy jobs lack pinned container IDs and locks are per instance/process. Pending effects refuse replay and may require manual inspection. Media proof levels differ: envelope checks do not establish full decodability or content correctness. Source receipts establish source-call provenance, not paywall access, claim support or comprehensive privacy. These gaps prevent production certification.

## Resume

Next incomplete module case **JRV-28-005**; global oldest unresolved **JRV-04-001**; next untouched module **29/JRV-29-001**. [Exact module IDs](modules/28-sandbox-deerflow/remaining-case-ids.txt), [global IDs](remaining-case-ids.txt). Complete approval provenance and process-wide admission, renderer readiness, paywall/source-quality/entailment, typed results, privacy/negation/resource/trace and disconnect cleanup contracts. Follow commands.md, freeze sources, run full/readiness, reconcile and verify artifacts. Shared-engine/platform/dependency installations, untrusted installers and real account actions require separate explicit authorization. [Previous Prompt 27 report](final-report-before-module28.md) preserves earlier results.
