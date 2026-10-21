# YouTube v2 baseline — 2026-10-21

Starting revision: `3bb40b3` (main, includes Spotify PR #9 and Blender PR #10).
Task branch: `codex/youtube-v2-integration`. No production source or active configuration changed before this baseline.

## Ownership and call graph

| Component | Current owner / reference | Integration constraint |
|---|---|---|
| Parent and typed schemas | `app/integrations/jarvis-connectors/jarvis_connector/base.py` | Use the actual BaseConnector, not the supplied minimal ABC or missing FastMCP dependency. |
| Five installed MCP tools | `app/integrations/jarvis-connectors/connectors/apps/youtube/server.py:39`, methods at 105–150 | Retain search_videos, search_playlists, video_details, playlist_videos, parse_link and return shapes. |
| Host registry / planning | `app/jarvis/tools.py:31`, `app/jarvis/capabilities.py:33`, `app/jarvis/commands.py:407`, `app/jarvis/brain.py` | Existing deterministic media route and model policies remain authoritative. |
| MCP / approval | `app/jarvis/mcp_bridge.py:216`, `app/jarvis/mcp_persistent.py:132` | Host approves calls; persistent providers currently only Spotify/Blender; ordinary catalogs capped at 100. |
| Browser owner | `app/jarvis/browser_automation.py:6` → `app/jarvis/ui_transport.py:11` → `app/jarvis/browser_worker.py:127` | One warm worker owns synchronous Playwright Page and `.jarvis-runtime/browser-profile`; no second production browser. |
| User Chrome preference | `app/jarvis/youtube_chrome.py:40`, `app/jarvis/media_player.py:337` | User Chrome Default first; OS media-session verification. Preserve preference and unrelated tabs. |
| Playback and queues | `app/jarvis/actions.py:1185`, `app/jarvis/browser_worker.py:261`, `app/jarvis/media_player.py:266` | Existing selected results and playback separate from read-only MCP; do not replace with local v2 queue silently. |
| Public API credential | `app/jarvis/media_player.py:72`; installed child `server.py:81` | Credential environment names differ. Never put credentials in tool arguments or evidence. |
| Shutdown/recovery | `app/jarvis/ui_transport.py:136`, browser manager close, Actions.close, main watchdog | Respect deliberate closure; never replay uncertain mutations. |

Existing path: final text/voice → commands/Actions → ToolRegistry/media tools → existing browser or scoped Chrome session → observed playback → response. MCP lookups use the existing BaseConnector child separately.

## Supplied package audit

Source directory: `D:/Phython Project/Connectors/jarvis_youtube_connector` (read only).
The advertised nine original names belong to this supplied standalone package, not the installed five-tool connector. Preserve both sets when migration becomes eligible.

Known defects / migration gaps, identified before editing:

1. Supplied `youtube_connector/youtube.py:98` launches Playwright's downloaded Chromium unconditionally. Gate A fails at setup because revision chromium-1243 is absent. Use already installed Chrome via an injected Page; no browser download is needed.
2. Supplied `server.py:5` imports FastMCP; this is not Jarvis's actual parent/runtime. Its module-level constructor also chooses a separate browser/profile (`youtube.py:78`), conflicting with existing ownership.
3. Supplied `youtube_v2.py:424–440` dequeues before playback verification; false/uncertain startup consumes the item. `queue_play_previous` at 459–466 pops history before navigation and has no restoration on failure.
4. Supplied `youtube_v2.py:89–103` temporarily swaps shared `_page` during search; concurrent unguarded lifecycle calls could observe the transient page. Injected-page search falls back to navigation of the playing tab.
5. Supplied `youtube_v2.py:45–79` applies media changes without checking ad state and reports `ok` from immediate property readback. Requested/observed identity, consent, loading and buffering need explicit classification.
6. Supplied `youtube.py:29–61` URL parser checks hostname but does not reject userinfo/nonstandard ports and does not support embed video links already accepted by the installed child.
7. Supplied `data_api.py:26` eagerly computes Path.home even with a token path; sanitized MCP environments can lack home. API transport at 60 follows redirects by default; error at 70 includes untrusted API message text, potentially reflecting secrets. Resource regex at 19 allows arbitrary alphabetic resources, not an endpoint allowlist.
8. Supplied `youtube_v2.py:128–135` catches failed media action then clicks play/pause, risking a duplicate effect after an uncertain mutation. Click-control loop at 236–244 similarly tries another selector after ambiguous click failure.
9. `103 > 100`: host catalog limit (`mcp_bridge.py:168`) needs an explicitly scoped migration; raising every server's allowance would broaden unrelated integrations.
10. Supplied live tests cover one happy-path video, not the full requested Gate A/B matrix. Offline tests are not evidence of public playback, real OAuth, or per-command live verification.

Line references refer to the unchanged supplied files or starting revision; later patches must describe changes separately.

## Baseline execution

- Supplied package: 92 tests run, 91 passed, 1 opt-in live skip; 6.322 seconds. See [log](supplied-baseline.log).
- Supplied opt-in live suite: 1 setup error, missing downloaded Chromium. See [Gate A attempt](supplied-live-gate-a.log). This is not a live playback pass.
- Unchanged full Jarvis pytest suite launched from canonical `app/` before source changes; [log](baseline-pytest.log) and exit file record completion. Results pending at baseline creation.
- Dedicated public-content profile for live probes: `app/.jarvis-runtime/youtube-v2-gate-a-profile`; no account writes or private profile changes authorized by these tests.
- Cold/warm dispatch, p50/p95, footprint and full acceptance counts remain unmeasured until actual verified dispatch. Prior Blender metrics are not YouTube measurements.

Gate A must pass before production integration/registration. Gate B has not run. No release acceptance claimed.

Completion addendum (after baseline creation, before production edits): unchanged full suite **3,835 passed / 152 skipped / 1 warning**, 1,235.40 seconds, exit 0. The injected public-page probe exposed initial ready_state=0 and volume resetting from 35 to 100 on resume; these observations are not accepted playback/control coverage. The user's subsequent profile-only instruction supersedes the earlier disposable-profile testing arrangement; no more alternate-profile YouTube launches are permitted. See [current status](acceptance.md) for later changes and gates.
