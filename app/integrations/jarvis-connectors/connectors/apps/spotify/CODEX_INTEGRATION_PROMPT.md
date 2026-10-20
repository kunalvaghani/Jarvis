# CODEX TASK — Integrate and harden Spotify child connector in my real Jarvis repository

You have my real Jarvis repository and the supplied `jarvis_spotify_connector` package. Treat the package as a **reviewed integration candidate**, not as already integrated or fully live-tested. Keep every existing Jarvis feature working and do not modify or replace the existing YouTube connector unless a shared base-class compatibility fix is truly required.

## 1. Mandatory baseline audit

1. Inspect `system-map.md`, my actual `BaseConnector`, tool registry, MCP bridge/process recovery, `brain.py`, `capabilities.py`, intent router, OS/desktop/browser/media/voice code, account-consent/security/telemetry modules, and test harness. Do not guess my host interfaces.
2. Inspect all files in this Spotify package and verify the 2026 Spotify Web API paths against official developer docs. Pay particular attention to `/me/playlists`, `/playlists/{id}/items`, `/me/library` query parameter `uris`, and search `limit <= 10`.
3. Identify existing Spotify integrations or generic media commands so there is **only one authoritative command** per action. Do not break legacy YouTube, VLC, local playback, browser shortcuts or speaker volume operations.
4. Identify any existing Jarvis BaseConnector. If one exists, adapt `SpotifyConnector` to its constructor, context, lifecycle, observability, response/error formats, permissions and capability discovery contracts. Do not install or use a second production BaseConnector hierarchy.
5. Run existing baseline tests, record pass/fail, and classify pre-existing failures before modifications. Use separate branch/worktree; do not overwrite user work.

## 2. Architecture and capabilities

- Integrate the 86 `spotify_*` tools exposed in `server.py` as a **namespaced, persistent MCP v2** subprocess through existing `mcp_bridge.py`, OR map them to native ToolRegistry registrations if my codebase already has a better adapter. Do not register duplicates. Treat the included manifest as illustrative, not automatically schema-compatible.
- Implement zero-LLM-cost deterministic routing for pause/resume/next/previous/seek/volume/status. Resolve ambiguous intent with the existing Jarvis music-provider choice (`spotify` vs `youtube`); never let a Spotify command accidentally control YouTube.
- Support modes: Spotify API (authorized user) and Windows local Spotify session. Local actions must never send media hotkeys to whichever app happens to be foreground; use the Spotify-specific Windows session. Spotify volume must target the Spotify application audio session, not all other apps.
- Distinguish `accepted`, `verified`, `opened_requested`, and `playing_verified` statuses. If Spotify API 204 accepts but playback can't be read back, never say the song is playing with certainty.
- Consider shared `MediaProviderRouter` / active-provider state in Jarvis; default playback controls to the last successfully targeted music provider unless user explicitly specifies Spotify/YouTube. Preserve clear user override and error reporting.
- Use one persistent MCP child process with health checks and restart backoff; reconnect safely after restart. Do not recreate a network client/OS session every tool call unnecessarily.
- Keep 86 tools discoverable via MCP but activate only a small common subset in LLM context. Discover detailed playlist, library and diagnostics tools on demand to control prompt/tool-schema bloat and response latency.
- Honor account data consent: no dumping OAuth tokens to models, logs, ReasoningBank, embeddings, telemetry, Groq or other cloud providers. Auth is an explicitly human-triggered local PKCE browser flow, not an LLM tool.
- On an account operation, require the right permissions; confirm destructive changes (`replace_playlist_items`, `remove_playlist_items`, `remove_saved_items`, visibility and collaboration edits) under my existing policy.

## 3. End-to-end command grammar and sequences

Cover spoken/typed intent variants, including:

- “Play Spotify”, “resume my Spotify”, “pause music”, “pause Spotify only”, “skip song”, “play previous track”, “stop the Spotify desktop session”.
- “Jump to 1 minute 35 seconds”, “rewind 20 seconds”, “skip ahead 45 seconds”, “raise volume by 10%”, “make Spotify app 35%”, “mute only Spotify”, “repeat one song”, “repeat playlist”, “turn off shuffle”.
- “Search Kesariya”, “search songs by Arijit Singh”, “play Hello by Adele”, “open Spotify search for jazz”, “play this Spotify link”, “play the fourth item in playlist X”, “play my saved songs”.
- “Which song is playing?”, “is Spotify paused?”, “which device is active?”, “switch playback to desktop / mobile device”, “show my queue”, “add song X to queue”.
- “Create private playlist Work Focus”, “rename playlist”, “add current song”, “remove explicit song from that exact playlist”, “reorder 2nd to 8th”, “replace entire playlist after confirmation”.
- “Save this song”, “unsave this track”, “list saved albums”, “show my top tracks last month”, “show recently played”, “show my playlist songs”.

Require explicit disambiguation for identical titles, incomplete links, similarly named playlists, device names that are not uniquely matched, and inactive devices. Search must never automatically choose arbitrary first result when confidence is low.

## 4. Error handling and service resilience

Test unauthenticated developer app, expired token, user-revoked app, missing/invalid scopes, missing Premium, wrong account allowlist, no active Spotify player, multiple Spotify local media sessions, unsupported OS capability, missing package, missing desktop Spotify app, 403 private playlist, 429 rate limits with `Retry-After`, 401 refresh, 502/503 and timeouts, empty search results, stale device ID, Spotify relinking, missing metadata and malformed JSON.

- Preserve bounded request timeouts and response sizes, avoid unsafe retries on non-idempotent POST.
- Use explicit bounded GET retries; never retry arbitrary account writes after unknown success.
- Ensure URI parsing rejects lookalike hosts, `http://`, redirects to other domains, path traversal, ambiguous IDs and malicious URI schemes.
- Respect account scopes, owner-only playlist endpoints, and limited development-mode quotas. No unofficial download, DRM bypass, stream extraction, ad circumvention or scraper-based authentication.
- Degrade only to **supported** Windows local controls when API auth is absent. Do not mask a 403 or 429 by silently changing control paths without notifying user.
- Ensure connection teardown, crash recovery and cancellation release OS/stdio resources; do not duplicate commands after recovery.

## 5. Regression and performance matrix

1. Run `python -m unittest discover -s tests -v` and `client_smoke.py` from this package. Add a **real MCP wire-protocol** integration test; distinguish stub-registration tests from real MCP.
2. Test all 86 tools for discovery, signatures, argument validation, dispatch, exception propagation and permissions. Exhaust all valid/invalid combinations of boolean, string, integer, URI and device parameters.
3. On a real Windows desktop (using an authorized Spotify app/account), perform **manual opt-in** live tests of: open app, local status, pause, resume, skip, seek, app volume/mute, API status, device transfer, search, play exact track, queue, playlist creation/edit, save current. Never delete or replace live playlists during smoke tests; use a dedicated test playlist and confirmation.
4. Cross-provider: run Spotify controls while YouTube/VLC/music/browser is active, then reverse. Verify Spotify tools never hijack other apps, and existing provider controls still work.
5. Across restart: kill/relaunch MCP child, close Spotify app, sleep/wake desktop, end Spotify session, reconnect OAuth refresh, and simulate disconnects during `POST`/`PUT` without duplicate effects.
6. Voice: speech-to-text variants, homophones, fast consecutive next/pause requests, overlapping commands, queued vs cancelled requests, ambiguous track names, stress test 100+ command sequences. Ensure deterministic commands do not wait for external/cloud LLM classification.
7. Browser and desktop agent regression: do not break or duplicate Playwright YouTube tab lifecycle, app switching, media keys, dynamic island notifications, MCP registry, scheduler, state memory or security monitoring.
8. Benchmark command routing and service process memory/CPU at idle and in use; record median/p95 dispatch time separate from Spotify network latency. Include rate-limited API and simulated Windows test results.
9. Add negative security tests: tool prompt injection via Spotify track metadata, malicious playlist descriptions, token exfiltration, token in exception traces, invalid ID/URL, cross-provider dispatch and unauthorized destructive operations.
10. Confirm rolling back Spotify registration leaves all old Jarvis behavior operational; do not weaken old assertions to achieve a green result.

## 6. Deliverables and acceptance criteria

- The integrated code must use my actual Connector contracts and coexist with YouTube, not just a copy of this ZIP.
- Provide a feature matrix with 86 tools, supported modes, scopes, approval rules, and live vs simulated test status.
- Show the true `mcp_bridge` manifest/config edits, lazy tool loading design, intent aliases, security and token storage behavior.
- Show baseline vs after suite pass/fail with counts and targeted unit/contract/real MCP/Windows/API/E2E/regression evidence. Any untestable live case must be explicitly marked **NOT TESTED**, never mocked and claimed live.
- Write an audit and integration report under `artifacts/jarvis-audit/spotify-connector/`, with changed files, exact branch + SHA, known restrictions, performance, security threats, outstanding gaps and rollback command.
- Work on an isolated branch/worktree. Do not push or merge without my explicit approval. Do not run destructive operations on my personal Spotify library.

**Exit condition:** All applicable tests pass, no YouTube/desktop regressions, no secret leakage, explicit untested cases, and I can run commands naturally through Jarvis using the selected Spotify provider.
