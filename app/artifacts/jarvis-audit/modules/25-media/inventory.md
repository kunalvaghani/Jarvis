# Prompt25 media audit — 2026-10-16 IST

**PARTIAL:16 catalog fixture PASS/16 BLOCKED.**

Only authored search results, fake UI runners/URIs/Windows sessions/audio levels, real owned child timeout cleanup and existing isolated browser/server fixtures. No real song/video playback, pause/seek/volume/device setting, tab/window activation, account like/save/queue, credential read/setup, installation or model/GPU workload. Existing rendered sample media-card artwork remains dated and attributed; no new live screenshot claimed.

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

[Report](../../final-report.md) · [Assertions](cases-and-contracts.xml) · [Diff](source.patch)
