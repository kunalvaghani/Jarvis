# Jarvis Spotify Connector — 2026 API + Windows Desktop Media Control

**86 `spotify_*` MCP commands**, built as `SpotifyConnector(BaseConnector)` following your uploaded YouTube adapter. Includes a separate local-only desktop control path for Windows. No paid AI API, no LLM calls required for deterministic media control, no scraped credentials or music downloads.

> **Integration status:** The package is independently runnable as an MCP v2 stdio server, but **it has not been patched into your main Jarvis repository**, which was not uploaded. You must adapt it to your real `BaseConnector`, `ToolRegistry`, `mcp_bridge.py`, permissions and media router before treating it as integrated. Review `CODEX_INTEGRATION_PROMPT.md`.

## Control paths

| Mode | Requires | Works for | Important limits |
|---|---|---|---|
| Spotify Web API | Spotify developer app, user-approved PKCE OAuth; **developer app owner must have Premium in 2026** | Search, playlists, library, Spotify Connect playback, devices, exact song queue | Spotify rate limits, account/market restrictions, up to five users in new development-mode app, scopes vary |
| Windows media session (GSMTC) | Windows, Spotify desktop media session, optional `winrt-Windows.Media.Control` | Play/pause/skip/previous/stop/seek/shuffle when Spotify exposes the control, read current media | Some media session controls may be unavailable or rejected by Spotify; no reliable account library or remote queue |
| Windows local audio session | Windows, Spotify desktop app, `pycaw` | Spotify-only volume/mute, readback | Changes only Spotify application audio, **not** Spotify Connect remote device volume |
| Desktop deep link | Spotify desktop installed | Open the app, specific item, local search | **Opening is not proof of playback**; no results extraction or search metadata without API |

**Important:** The Spotify Web API is not a way to bypass a Spotify subscription, listen offline, suppress ads, download tracks, or automate a free-tier account in ways the service disallows. API calls themselves are not paid LLM tokens, but developer mode requires Premium as stated. Windows controls do not circumvent Spotify's existing playback rules.

## Windows PowerShell installation

Inside the extracted `jarvis_spotify_connector` folder:

```powershell
py -3.12 -m venv .venv-spotify
.\.venv-spotify\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv-spotify\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-spotify\Scripts\python.exe client_smoke.py
```

Use Python 3.11–3.13 with supported Wheels and an MCP SDK v2 environment. If only local desktop actions are desired, the Windows dependency packages are sufficient for the core child class, but `mcp` is still needed to expose it as an MCP server.

### Authorize Spotify Web API (optional; required for cloud account features)

1. At <https://developer.spotify.com/dashboard>, create an app under a **Spotify Premium app-owner account**. Add your Spotify account to the allowlist if applicable.
2. In your app, set the redirect URI exactly to `http://127.0.0.1:8765/callback` (use the numeric loopback IP, **not** `localhost`).
3. Copy the **Client ID** (not Client Secret). In the PowerShell window where you run the connector:

```powershell
$env:SPOTIFY_CLIENT_ID="YOUR_PUBLIC_CLIENT_ID"
.\.venv-spotify\Scripts\python.exe auth_login.py
```

4. Authorize the requested permissions in your own browser. PKCE tokens are stored in the OS credential manager using Python `keyring`, **not** a plaintext `.env` or JSON file. The initial login operation is **intentionally not** an MCP tool; your LLM should never see or operate on OAuth credentials.
5. Add `SPOTIFY_CLIENT_ID` to the MCP server **subprocess environment** (or to your user's environment), so the long-lived subprocess can refresh the OS-stored token after it expires.

To clear the local saved login:

```powershell
.\.venv-spotify\Scripts\python.exe auth_logout.py
```

This clears the local tokens. To revoke application access remotely, also use Spotify account application permissions.

## Run as a standalone MCP process

```powershell
.\.venv-spotify\Scripts\python.exe server.py
```

This is a **stdio JSON-RPC server**, not an interactive command prompt. Launch it **from your existing Jarvis MCP host** instead of trying to type commands in its terminal. The included `client_smoke.py` starts its own subprocess and checks tool discovery.

## Attach to Jarvis

Refer to `connector_manifest.example.json` for illustrative fields only. The two uploaded packages explicitly warn that the manifest schema is **not** guaranteed to match your actual Jarvis bridge; inspect and adapt it instead of dropping it directly into config. Recommended route:

`voice / text → Jarvis intent router → ToolRegistry (spotify namespace + host approvals) → MCP bridge (one persistent subprocess) → server.py → SpotifyConnector(BaseConnector) → SpotifyAPI or WindowsSpotify`.

Keep your existing YouTube controller intact and add Spotify as an independent namespace. Do **not** register each command twice (once natively, once through MCP); the ToolRegistry should own permission checks and dispatch. Expose common commands in the default LLM tool subset; let Jarvis lazily discover rarely used playlist/library/diagnostic actions. This avoids adding 86 tool schemas to every prompt.

**Suggested approvals:** no extra user approval for read-only/status and reversible playback operations under pre-approved Spotify automation; confirm destructive playlist replacement and library deletion, and confirm sharing/public visibility/collaboration changes. Do not auto-run changes based solely on untrusted song/playlist names or tool outputs.

## Common example intents (mapped to MCP tool methods)

| Jarvis utterance | MCP tool | Arguments |
|---|---|---|
| “Pause Spotify” | `spotify_pause` | — |
| “Play Spotify” | `spotify_resume` | — |
| “Next Spotify song” | `spotify_next` | — |
| “Go back 30 seconds on Spotify” | `spotify_seek_relative` | `delta_ms=-30000` |
| “Set Spotify volume to 55%” | `spotify_volume` | `percent=55` (API) |
| “Set Spotify app volume to 55%” | `spotify_local_volume` | `percent=55` (Windows) |
| “Repeat this song” | `spotify_repeat` | `mode="track"` |
| “Shuffle Spotify on” | `spotify_shuffle` | `enabled=true` |
| “Play track [official Spotify link]” | `spotify_play_track` | `track="https://open.spotify.com/track/..."` |
| “Find Hello by Adele and play it” | `spotify_play_search` | `query="Hello", artist="Adele"` |
| “Add this song to my saved music” | `spotify_save_current` | — |
| “Show my devices” | `spotify_devices` | — |
| “Move music to my PC” | `spotify_transfer` | `device` from `spotify_devices` |
| “Create a private playlist called Work Mix” | `spotify_create_playlist` | `name="Work Mix",public=false` |
| “Add this song to my playlist” | `spotify_add_current_to_playlist` | `playlist` with exact playlist URI |
| “Find playlists for study music” | `spotify_search_playlists` | `query="study music"` |
| “Open Spotify search for jazz without an API” | `spotify_open_search` | `query="jazz"` |

See **`COMMANDS.md`** for all 86 tool names and signatures.

## 2026 compatibility

- Uses `/me/playlists` to create playlists, not the older `/users/{id}/playlists` endpoint.
- Uses `/playlists/{id}/items` to add, read, remove, replace, reorder—not `/tracks`.
- Uses generic `PUT/DELETE /me/library`, plus `GET /me/library/contains`, instead of removed item-specific save/remove endpoints.
- Search `limit` bounded to 10 results per request, with `offset` pagination.
- Does not call removed multi-track/album/artist lookup, recommendations, browse-new-releases, user lookup or unsupported recommendations/audio features endpoints.
- Reading playlists you neither own nor collaborate on may return metadata without items; do not treat missing items as an empty playlist.
- Song playback API may report accepted without immediate proof. Use `spotify_verify_playback` as a separate readback or read `spotify_status`.

Official docs: [February 2026 migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide), [PKCE authorization](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow), [redirect URIs](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri), [player API](https://developer.spotify.com/documentation/web-api/reference/get-information-about-the-users-current-playback), [rate limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits).

## Testing and limitations

- No tokens, credentials, audio streaming, playlists, or other account assets were touched during development.
- Offline unit tests exercise command routing, old-to-new endpoint migration, mock Spotify responses, error propagation, fake Windows media sessions, secure identifiers, OAuth helpers, simulated MCP registration and hundreds of adversarial URLs.
- **Live Spotify login, API calls, Windows desktop operation, and actual MCP v2 wire-protocol smoke cannot be claimed as tested** in the authoring environment. Run the script and the final Jarvis end-to-end matrix on your PC; see `TEST_REPORT.md`.
- Spotify does not provide a public API to manage folders, clear the entire playback queue, download tracks, forcefully dismiss ads, or stream protected music. These are intentionally not faked as supported commands.

## Security notes

- URL allowlisting, strict ID validation, path sanitization, bounded requests/timeouts, one 401 refresh retry, GET-only 429/5xx retry.
- API 204 means Spotify accepted the command; `verified: null` is intentionally **not** a fabricated success readback.
- Authorization login uses state / PKCE / numeric-loopback callback; never exposes tokens to Jarvis tool arguments.
- Windows media sessions are filtered by Spotify app ID; audio is filtered by Spotify.exe process; no global hotkey sent to a random foreground app.
- Tools access private user Spotify content. If Jarvis can route to a cloud LLM, apply your existing data minimization/consent policies and never forward Spotify OAuth tokens.
