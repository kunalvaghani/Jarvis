# YouTube connector

This is the first app connector. `YouTubeConnector` inherits from [BaseConnector](../../../jarvis_connector/base.py)
and gives Jarvis **read-only** YouTube search and lookup through the MCP server `youtube`. It was
adapted from the `jarvis_youtube_connector` starter.

| Tool | Arguments | Returns |
| --- | --- | --- |
| `search_videos` | `query`, `limit` 1–10 (default 5) | `video_id`, `title`, `channel`, `duration_seconds`, `live`, `url` |
| `search_playlists` | `query`, `limit` 1–10 (default 5) | `playlist_id`, `title`, `channel`, `video_count`, `url`, `play_url` |
| `video_details` | `video`: ID or https link | `title`, `channel`, `duration_seconds`, `views`, `live`, `playable`, `status` |
| `playlist_videos` | `playlist`: ID or link, `limit` 1–15 | the playlist's videos in order, each with a URL that plays it inside the playlist; `more` when trimmed |
| `parse_link` | `link` | `is_youtube`, IDs and a safe watch URL, checked offline |

## Why the connector does not play, pause or skip

The starter's connector owned its own Playwright browser for playback. That design does not fit Jarvis:

- Jarvis's MCP bridge starts a **new connector process for each call and stops it afterwards**. A
  browser owned by the connector would close after every call, so `pause` would start a new, empty browser.
- Jarvis already has verified YouTube playback in its own browser
  ([media_player.py](../../../../../jarvis/media_player.py), `media_control`). A second browser would
  compete with it. The starter's integration notes also say not to duplicate working abilities.

The connector therefore finds things, and Jarvis plays them with its existing tools.
`browser_navigate` opens a playlist's `play_url`, `media_search` plays a video by title, and
`media_control` handles pause, next and previous. The
[youtube-media skill guide](../../../../../skills/youtube-media/SKILL.md) tells the planner how to
combine them.

## Data sources and safety

- **Default source: YouTube's public pages.** The connector reads the data embedded in the results,
  watch and playlist pages, as Jarvis's own search already does. This is best effort and can break
  when YouTube changes its layout. The parser handles the shapes observed live on 2026-10-20
  (`videoRenderer`, and `lockupViewModel` for playlists and playlist items) and the older shapes.
  The playlist search filter `sp=EgIQAw==` is a YouTube UI parameter, not a public API contract.
- **Optional source: YouTube Data API v3**, used for the two search tools when `JARVIS_YOUTUBE_API_KEY`
  is set in Jarvis's environment. The bridge passes it through `env_names` and redacts it from
  results, and the connector never returns the key or the request URL. Data API quotas apply.
- The connector fetches only `https://www.youtube.com` and `https://www.googleapis.com`. It refuses
  redirects to other sites, limits each page to 8 MB, and reports network and HTTP errors without URLs.
- It returns only named fields. Raw page data includes viewer-specific stream URLs that contain the
  requester's IP address, so it is never passed through. Titles are trimmed to 120 characters and
  treated as untrusted text.
- It never downloads media, signs in, comments, likes, subscribes or changes an account.
- Every call still goes through Jarvis's approval card.

## Run and test

```powershell
cd "app\integrations\jarvis-connectors"
..\..\.venv\Scripts\python.exe connectors\apps\youtube\server.py --list-tools
..\..\.venv\Scripts\python.exe -m pytest tests\test_youtube.py -q -p no:cacheprovider
$env:JARVIS_LIVE_YOUTUBE = "1"; ..\..\.venv\Scripts\python.exe -m pytest tests\test_youtube.py -q -p no:cacheprovider   # also runs the live check
..\..\.venv\Scripts\python.exe evals\youtube_qwen_eval.py   # live qwen3.5:9b evaluation (needs Ollama)
```
