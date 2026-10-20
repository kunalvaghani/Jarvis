> Historical report supplied with the candidate. It is not validation of this Jarvis integration. Fresh results are in the [integration audit](../../../../../artifacts/jarvis-audit/spotify-connector/README.md).

# Independent validation report — 20 October 2026

## Inputs analyzed

- `jarvis_youtube_connector(1).zip`: example BaseConnector, child subclass, nine async MCP tools, Playwright browser, standalone MCP v2 server, 20 unittest methods.
- `jarvis_custom_connector_starter(1).zip`: independent notes MCP server and pure-Python notes core, 6 unittest methods.
- **Not provided:** Full Jarvis runtime, true production BaseConnector, ToolRegistry implementation, voice router, installed Spotify app/account, Spotify developer credentials.

## Executed here, not assumed

- Compile check (`python -m compileall`): PASS.
- Spotify offline unit/contract tests (unittest / pytest): PASS (39 test methods, 366 subtests).
- Source YouTube unit tests: PASS (20 tests, run unchanged).
- Source Notes starter unit tests: PASS (6 tests, run unchanged).
- Spy/stub MCP tool registration: PASS (86 named functions / expected signatures, several dispatch calls). **Not a real MCP transport test.**
- Local-only simulated Spotify media session, per-app audio volume/mute, API request error/retry, 2026 endpoints and OAuth helpers: PASS.
- Deterministic hostile/invalid URI fuzz: PASS (300 sampled inputs plus edge cases).
- Testing uses fake API and fake Windows media sessions; not a live Spotify account.

## Bugs found and fixed while testing

1. MCP server wrapper code generator initially included bound `self` in exposed arguments; fixed and added introspection check.
2. API transport failed to reject a `//host`-style path; fixed fixed-origin path guard and test.
3. Authless API writes were mistakenly allowed by an injected fake API; `_write` now checks authorization before attempting action.
4. Local Windows media-session matching was broad enough to match `NotSpotify.exe`; now matches `Spotify.exe` or the genuine Spotify UWP AppUserModelID prefix.
5. Spotify library endpoints reviewed against October 2026 docs; generic `/me/library` uses a **40-URI maximum and query-string `uris`**, updated from earlier incorrect JSON-body / 50-item draft.
6. MCP outputs were marked `dict` even though some Spotify read endpoints return JSON arrays; wrapper return typing corrected to `Any`.

## Still NOT TESTED in this environment

- Actual Spotify OAuth browser login, token storage to Windows Credential Manager and refresh against Spotify.
- Any live Spotify Web API request, Premium/account allowlist behavior, playback acceptance/verification on a real device.
- `winrt-Windows.Media.Control` with Spotify Windows desktop and actual Spotify app-specific volume via `pycaw`.
- Real MCP v2 package wire-protocol smoke / Jarvis MCP host discover/register/dispatch (SDK not installed in authoring environment).
- Jarvis voice commands, multi-agent routing, cross-provider YouTube regression in the real Jarvis process, cloud-privacy enforcement, Windows crash/service restart behavior.

## Recommended live acceptance gates

1. `install_windows.ps1` exits 0 including real MCP stdio smoke.
2. Without authorization, open Spotify / `spotify_local_status`, `spotify_local_play`, `spotify_local_pause` and `spotify_local_volume` target only the Spotify process.
3. Authorize with PKCE and Premium; list devices; play a known track; call `spotify_verify_playback` and confirm source URI and play state.
4. Create one disposable **private** test playlist; add/reorder/remove test items with user approval and verify through Spotify UI. Avoid tests on personal playlists.
5. Run the full Jarvis voice and YouTube suites before enabling by default.

## Risk statement

This is a fully packaged, offline-tested feature module, not proof of deployment into the Jarvis runtime or proof that Spotify will honor every endpoint for this specific user's subscription/app. Official API 204 indicates the request was accepted, not independently verified playback. The Windows media controls depend on app/OS support and may be rejected.
