# Jarvis audit — Prompt25, 2026-10-16 IST

**PARTIAL:16 media catalog fixture PASS/16 BLOCKED. Not production acceptance.**

Repo commit9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6, preserved dirty audit/12-tool-registry, canonical app/. Python3.10.6, Windows-10-10.0.26200-SP0, RAM33656832000bytes; target RTX3050 Laptop4GB from earlier census, no new GPU load. [Environment](modules/25-media/environment.json).

Only authored search results, fake UI runners/URIs/Windows sessions/audio levels, real owned child timeout cleanup and existing isolated browser/server fixtures. No real song/video playback, pause/seek/volume/device setting, tab/window activation, account like/save/queue, credential read/setup, installation or model/GPU workload. Existing rendered sample media-card artwork remains dated and attributed; no new live screenshot claimed.

## Source map evidence

| Map claim | Source/entry point | Actual evidence and limitation |
| --- | --- | --- |
| Fast dispatch | media_commands/commands→Actions→media_player.resolve/play | Named service stays explicit; deterministic selection and controls use zero model calls; full speech path not tested |
| YouTube play | youtube_search→choose_youtube→owned browser play_video | Actual fixture IDs; no unrelated top fallback, close-score competing IDs require channel/version; shorts <=45s excluded; live/unknown duration may be unavailable |
| Spotify play | URI search→UIA rows→choose_spotify→_activate→spotify_now | Song rows only; ties across title/artist ask; title+artist readback exact after NFC/case/space normalization; already-playing match avoids click |
| Native transport | spotify._control→_spotify_session→GSMTC | Explicit source-ID allowlist, one session required; pause/play idempotent and read back; multiple sessions refuse; Spotify browser not treated as native |
| Volume | spotify.volume→all active output sessions | Fake Spotify.exe mixer30% readback, Chrome unchanged; alternate-output regressions present, no live device selected |
| Active target | active_service→resolve | Only playing service or last started when both playing; paused available service preferred; not generic Windows transport of arbitrary apps |
| Uncertainty | PlaybackUncertain through play_youtube/play_spotify→play | Post-dispatch/unverified playback cannot fall back to another service; no persistent event-ID or write-intent record added |
| Untrusted metadata | Windows status and cards | Titles/artist are returned as data; no model command execution; complete private transcript/cloud redaction not proved |
| Lifecycle | _on_media_thread, island_media.MediaJobs, existing browser worker | Fresh MTA and bounded cancellation, real owned-child timeout regression; no new service or dependency |
| Config | config.media.default_service | youtube default, explicit youtube/spotify only, malformed defaults/unknown previous service refused; search1–300 characters |

## Executed verification and measurements

Baseline70 PASS/0 FAIL/11.548s. Focused123 PASS/16 explicit BLOCKED skips/0 FAIL. Full suite **2971 PASS/89 skips/0 FAIL in527.668s**. Existing COM-threading warning retained. Launcher dependency/configuration readiness **ready**, optional Groq not live checked. Native media/account/production readiness is unverified.

31-song selection warm p50/p95 22.29480/24.01100→20.82265/21.25810ms; Python peak 8619→8583B, identical chosen row. Keep query reuse plus ASCII fast path; Unicode candidate's earlier regression was superseded and full verification restarted. No UI/RSS/VRAM/cold-process/audio speed claim. [Measurements](modules/25-media/benchmarks.csv), [tradeoffs](modules/25-media/changes.md).

Frozen388 runtime/test files unchanged throughout accepted full run. [Source hashes](modules/25-media/full-start-source-hashes.json), [full output](modules/25-media/full-regression.log), [XML](modules/25-media/full-regression.xml), [skip reasons](modules/25-media/full-regression-skip-reasons.json), [reproductions](modules/25-media/failures.md), [commands](modules/25-media/commands.md), [changed files](modules/25-media/files-changed.json), [scoped diff](modules/25-media/source.patch), [rollback](modules/25-media/rollback.md).

Official URLs/release dates and retained dependencies: [compatibility](modules/25-media/compatibility.md). Pycaw20260921 is installed, newer20260927 not installed/tested. YouTube's public quota wording updated2026-10-15 supersedes historical guide calculations. No dependency or service added, Start/Stop/bootstrap/launcher/recovery sources unchanged.

## Exact1,184-case accounting

**{"PASS": 714, "FAIL": 0, "BLOCKED": 91, "SKIPPED": 0, "NOT RUN": 379}**. Every media case either has executed assertions or an explicit executed blocker; narrower checks do not override full-case blockers. Historical module measurements remain in their evidence links.

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
| [26-realtime-data](modules/26-realtime-data/inventory.md) | PARTIAL | 1 | 0 | 31 |
| [27-gods-eye](modules/27-gods-eye/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [28-sandbox-deerflow](modules/28-sandbox-deerflow/inventory.md) | PARTIAL | 0 | 0 | 32 |
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
    "PASS": 177,
    "BLOCKED": 24,
    "NOT RUN": 95
  },
  "P1": {
    "PASS": 386,
    "BLOCKED": 42,
    "NOT RUN": 201
  },
  "P2": {
    "PASS": 151,
    "BLOCKED": 25,
    "NOT RUN": 83
  }
}
```
Category totals:
```json
{
  "config": {
    "PASS": 24,
    "BLOCKED": 1,
    "NOT RUN": 12
  },
  "contract": {
    "PASS": 24,
    "BLOCKED": 1,
    "NOT RUN": 12
  },
  "edge": {
    "PASS": 49,
    "BLOCKED": 1,
    "NOT RUN": 24
  },
  "fault": {
    "PASS": 94,
    "BLOCKED": 6,
    "NOT RUN": 48
  },
  "idempotency": {
    "PASS": 21,
    "BLOCKED": 4,
    "NOT RUN": 12
  },
  "load": {
    "PASS": 23,
    "BLOCKED": 2,
    "NOT RUN": 12
  },
  "observability": {
    "PASS": 18,
    "BLOCKED": 7,
    "NOT RUN": 12
  },
  "performance": {
    "PASS": 21,
    "BLOCKED": 4,
    "NOT RUN": 12
  },
  "privacy": {
    "PASS": 21,
    "BLOCKED": 4,
    "NOT RUN": 12
  },
  "race": {
    "PASS": 24,
    "BLOCKED": 1,
    "NOT RUN": 12
  },
  "recovery": {
    "PASS": 43,
    "BLOCKED": 7,
    "NOT RUN": 24
  },
  "resource": {
    "PASS": 21,
    "BLOCKED": 4,
    "NOT RUN": 12
  },
  "scenario": {
    "PASS": 259,
    "BLOCKED": 46,
    "NOT RUN": 139
  },
  "security": {
    "PASS": 49,
    "BLOCKED": 1,
    "NOT RUN": 24
  },
  "semantic": {
    "PASS": 23,
    "BLOCKED": 2,
    "NOT RUN": 12
  }
}
```

## Unresolved contracts and release risk

- **JRV-25-011 BLOCKED:** Browser ownership/process cleanup has regression coverage; actual playing-tab close with unrelated tabs retained needs an owned DOM journey.
- **JRV-25-013 BLOCKED:** No complete network-outage workflow proof with bounded classification, trace and no uncertain fallback across every media path.
- **JRV-25-014 BLOCKED:** Owned media timeout fencing has regressions; complete browser/API/WinRT timeout matrix and provenance remains incomplete.
- **JRV-25-015 BLOCKED:** Search API/page payload shapes, recursion, response-size and malformed metadata handling are not completely bounded or validated.
- **JRV-25-017 BLOCKED:** No five independent full search/play requests x20 concurrency proof; native transport/UI search ownership remains shared.
- **JRV-25-018 BLOCKED:** Pre-URI and post-dispatch cancellation guards tested; complete TaskState cancellation/readback contract is unproved.
- **JRV-25-019 BLOCKED:** No durable playback mutation checkpoint/restart protocol. Native child timeout disposal is not crash-safe replay proof.
- **JRV-25-021 BLOCKED:** Untrusted titles remain data locally; complete Groq/telemetry/public-cache/trace secrecy oracle is absent.
- **JRV-25-023 BLOCKED:** Full opposed natural-language requests through routing and planner lack a no-effect negation proof.
- **JRV-25-024 BLOCKED:** Exact source-ID filtering passed; full native session/row identity replacement between planning and dispatch is unproved.
- **JRV-25-025 BLOCKED:** No complete RAM/GPU-pressure admission and core responsiveness fixture; no heavyweight inference or device-pressure mutation performed.
- **JRV-25-026 BLOCKED:** Uncertain playback no longer falls back to another service, and already-playing Spotify avoids activation; durable event-ID dedupe and YouTube tab reuse across repeated events remain unproved.
- **JRV-25-027 BLOCKED:** Identical31-song warm CPU/tracemalloc A/B measured; five real cold processes plus20 full workflows/RSS/VRAM/audio latency not measured.
- **JRV-25-028 BLOCKED:** No complete privileged like/save/queue/browser flow proof against forged tool approval claims.
- **JRV-25-030 BLOCKED:** Owned slow-child disposal and transport fencing covered; complete active native/browser connection-loss recovery with provenance is unproved.
- **JRV-25-032 BLOCKED:** Cards/transcripts contain titles/artists, transport exceptions can carry details; cross-flow IDs and complete private metadata redaction unproved.

Account like/save/queue actions are distinct from playback and not newly authorized by these fixtures. Allowlisted source IDs are metadata, not a hostile-process authentication boundary. Exact artist formatting can conservatively refuse valid alternate metadata. UI state can change after observation; no atomic search/activate transaction or durable playback journal was added. Privacy/payload/ownership gaps listed above prevent a production claim.

## Resume

Next incomplete module25 case **JRV-25-011**; global oldest unresolved **JRV-04-001**; next untouched module **26/JRV-26-001**. [Exact media IDs](modules/25-media/remaining-case-ids.txt), [global IDs](remaining-case-ids.txt). Resume with owned playing-tab closure fixtures, then HTTP/COM fault schema and durable provenance/replay contracts. Follow commands.md, freeze before full regression, run readiness, reconcile and verify artifacts. Live playback/device/account actions require separate explicit approval. [Previous report](final-report-before-module25.md) preserves module24 and earlier evidence.
