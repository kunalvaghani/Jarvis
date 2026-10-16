# Reproduction, fixes and limitations

Original sandbox baseline stalled after23 assertions and was stopped by exact owned pytest process identity; no pass count inferred. Outside-sandbox baseline70 PASS. New assertions reproduced13 FAIL/5 PASS/24 explicit blockers. First neighbors142 PASS/41 skips; later153 PASS/33 skips (includes WhatsApp blockers). A test fixture initially failed because its search field included the filler word Song while production clean_query removes it; corrected before accepted focused run. The first completed full run found2 failures/2969 PASS/89 skips in543.71s: island metadata fixtures used noncanonical placeholder Spotify IDs. Both fixture IDs were changed to the known package identity while preserving original memory-stream, multiple-session and missing-metadata assertions. Follow-up island/media neighbors58 PASS/16 skips; final full regression rerun on a fresh frozen source manifest. Final focused123 PASS/16 skips. [First completed full-run failures](full-before-fixture-fix.xml) and [interrupted pre-performance run](interrupted-full-before-performance.log) are preserved separately from final full output. No real playback occurred.

Fixed arbitrary YouTube fallback, ambiguous video/song choice, album-as-song fallback, Spotify substring source spoofing, loss of non-Latin query tokens, cancellation before URI dispatch, invalid service selection, title-only Spotify verification and cross-service fallback after uncertain mutation. WinRT dependency failures are categorical.

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
