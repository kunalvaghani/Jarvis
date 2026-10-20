# Spotify child connector

Integrated on an isolated branch on **2026-10-20 IST**. The primary checkout is unchanged; merge/deployment requires separate approval. The supplied package is adapted to the existing `integrations/jarvis-connectors/jarvis_connector/BaseConnector`, with no second production connector hierarchy. See the [audit](../artifacts/jarvis-audit/spotify-connector/README.md) and [86-tool matrix](../artifacts/jarvis-audit/spotify-connector/feature-matrix.md).

## Runtime and command routing

`commands.py` and `spotify_host.py` recognize deterministic commands without an LLM. Calls go through the existing `ToolRegistry` → `mcp_bridge.execute` → exact per-call approval → one serialized persistent child. The existing watchdog checks that child with MCP `ping`, repairs with bounded backoff, and never replays a tool after a disconnect or uncertain response. Quit closes it; recovery does not reopen Spotify itself. The YouTube registration and connector source are unchanged.

All 86 names remain discoverable over MCP. `mcp_list_tools` with server `spotify` returns six common schemas by default. Use content `{"query":"playlist"}` to load up to six relevant schemas, a narrower operation query for others, or `{"names_only":true}` for all names. Detailed calls use `mcp_call`, value `spotify`, content `{"name":"spotify_search_tracks","arguments":{"query":"Kesariya","limit":5}}`. Annotations cannot waive host approval.

Examples include “play Spotify”, “resume my Spotify”, “pause Spotify only”, “skip song”, “play previous track”, “jump to 1 minute 35 seconds”, “rewind 20 seconds”, “make Spotify app 35%”, “mute only Spotify”, “repeat one song”, “turn off shuffle”, “search songs by Arijit Singh”, “open Spotify search for jazz”, “play Hello by Adele on Spotify”, “play the fourth item in playlist Work Focus”, and “show my Spotify queue”. Unqualified playback follows the last successfully targeted provider while this connector is enabled. Explicit YouTube requests still use YouTube.

The existing task queue keeps the phrase “show my queue”; say **“show my Spotify queue”** for music. Generic “search Kesariya” retains the existing contextual/browser search behavior; say **“search Spotify for Kesariya”** for the API catalogue. Missing playlist names, item identifiers or replacement contents produce clarification rather than an arbitrary action. Name lookup refuses multiple matches and incomplete playlist listings. Device-name transfer requires one exact, active, unrestricted device. Detailed playlist/library actions are available through on-demand MCP discovery; not every possible spoken edit has a shortcut.

## Modes and result meanings

- **Windows local:** exact Spotify GSMTC sessions for transport/seek/shuffle/repeat; Pycaw selects only `Spotify.exe` audio sessions across active outputs. Multiple Spotify media sessions are refused. No foreground media hotkeys or master-volume writes are used. By-name playback without OAuth retains Jarvis's existing title/artist-checked native accessibility picker, with no retry after an uncertain click.
- **Spotify API:** authorized account, correct scopes, Spotify app allowlisting/subscription and service availability are required. API 403/429 errors do not silently switch to local controls. Exact playlist offsets and explicitly named remote devices require API authorization. Owner checks precede playlist writes.
- **Deep link:** opening Spotify or an exact resource is `opened_requested`, not proof that playback began.

Receipts distinguish `accepted`, `verified`, `opened_requested` and `playing_verified`. A successful API 204 is accepted only. Use `spotify_verify_playback` to check expected URI/state separately. Local play/pause/seek perform bounded readback; a missing observation leaves the action accepted but unverified. Next/previous are dispatched once; a previous request may restart the current track, and is never automatically repeated to force a track change.

The built-in runtime implements real MCP stdio using protocol `2025-11-25`. The existing base also supports the optional official MCP SDK v2 runtime. SDK v2 is not installed/tested in this Python 3.10 environment; successful real-wire checks here use the built-in runtime, not a stub or an SDK-v2 certification.

## Registration, OAuth and permissions

From `app/`, using an existing interpreter:

```powershell
.\.venv\Scripts\python.exe scripts/setup/register_spotify_connector.py
.\.venv\Scripts\python.exe integrations/jarvis-connectors/connectors/apps/spotify/client_smoke.py
```

The registration script creates a private config backup, preserves other servers, uses the actual `servers`/`command`/`args`/`allow_tools` schema, and passes only the public `SPOTIFY_CLIENT_ID` environment-variable name. The committed candidate registration points to this isolated checkout; rerun registration in the eventual deployment checkout so its absolute paths match that checkout.

Local controls use existing WinRT, Pycaw and pywin32 declarations. Optional API setup is declared in [`requirements/spotify.txt`](../requirements/spotify.txt); no package was installed by this integration. Install that file explicitly in the chosen interpreter before OAuth. The optional SDK-v2 dependency requires a compatible Python version.

Set your public Spotify client ID in the local shell and run `integrations/jarvis-connectors/connectors/apps/spotify/auth_login.py` yourself. Register the exact numeric-loopback redirect `http://127.0.0.1:8765/callback` in Spotify's developer dashboard. The CLI uses PKCE/state validation and Windows Credential Manager through the explicit `WinVaultKeyring` backend, with no plaintext fallback. Login/logout are not MCP tools. Tokens from an earlier standalone package require this human consent flow again.

No OAuth token is supplied to prompts, approvals, logs, telemetry, ReasoningBank, embeddings or cloud models. API calls require the recorded account-consent flag and current scopes. Before account dispatch, the child supplies a per-process opaque credential binding; the host displays a fresh account-fingerprint approval and overwrites any model-supplied binding. The child rechecks that binding/scopes and refuses relinking while approval is pending. The fingerprint is not a verified account label. Credential storage and real API account operations remain untested live here because OAuth/keyring setup was not performed.

Playlist remove/replace, unsave and playlist-detail/visibility/collaboration edits are destructive tools and require exact host approval. Collaborative playlists must be private. No personal library write was used for verification. Search is capped at 10; library `uris` batches at 40. Save/remove currently support the reviewed resource kinds in the service and deliberately reject artist/user URIs rather than guessing new endpoint semantics.

## Verification and rollback

Run `python scripts/verification/verify_spotify_connector.py` for the real, read-only wire smoke, and `python scripts/verification/benchmark_spotify_connector.py` for local overhead. `--live-local` on the verification script may interrupt playback and must be explicitly human-authorized; it stops on an uncertain operation. Live API transfer/queue/library acceptance, cross-provider reverse-control trials, physical voice/STT, sleep/wake and OAuth refresh/revocation remain separate acceptance gates in the [audit](../artifacts/jarvis-audit/spotify-connector/README.md).

To withdraw registration without changing YouTube:

```powershell
.\.venv\Scripts\python.exe scripts/setup/register_spotify_connector.py --disable
```

Restart Jarvis to close any existing child. Old Spotify/YouTube/VLC/browser/speaker-volume handlers remain in place. Restoring a saved private `.jarvis/mcp.json` backup also restores the original registration; do not copy credentials into that file.

Current API semantics were checked with Firecrawl against Spotify's [February 2026 changelog](https://developer.spotify.com/documentation/web-api/references/changes/february-2026), [March corrections](https://developer.spotify.com/documentation/web-api/references/changes/march-2026), [library query parameters](https://developer.spotify.com/documentation/web-api/reference/save-library-items), [playlist-item removal](https://developer.spotify.com/documentation/web-api/reference/remove-items-playlist), [playlist ownership/collaboration rules](https://developer.spotify.com/documentation/web-api/reference/change-playlist-details) and [PKCE guide](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow).
