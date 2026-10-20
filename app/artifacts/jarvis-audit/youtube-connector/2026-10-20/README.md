# YouTube connector: integration evidence (2026-10-20)

Branch `claude`, uncommitted working tree on top of `9bfcf4f`. Windows 11. Jarvis `.venv` (Python 3.10.6).
Local Ollama `qwen3.5:9b`: temperature 0.1, thinking off, `num_ctx` 8192.

## Architecture decision

The starter (`D:\Phython Project\Connectors\jarvis_youtube_connector`) owned a Playwright browser
for search and playback. That design was not adopted:

- **Process lifetime.** `jarvis/mcp_bridge.py` starts one connector process per call and stops it
  afterwards (`execute` → `finally: client.close()`). A connector-owned browser would close after
  every call, so pause, next and status would each find a new, empty browser.
- **Duplication.** Jarvis already plays and controls YouTube with verification in its own browser
  worker (`media_player.play_youtube`, `browser_worker.play_video`/`control`, `media_control`).
  The starter's own integration prompt says not to duplicate working abilities or create competing
  browser controllers.

**Adopted:** a read-only child of the existing `BaseConnector`
(`integrations/jarvis-connectors/connectors/apps/youtube/`) with five tools: `search_videos`,
`search_playlists`, `video_details`, `playlist_videos` and `parse_link`. Playback stays on Jarvis's
existing tools. The skill guide tells the planner to play a found playlist with `browser_navigate`
(its `play_url`) and a found video with `media_search`.

## Changed files

| File | Change |
| --- | --- |
| `integrations/jarvis-connectors/connectors/apps/youtube/` | new: `server.py`, `youtube_pages.py`, `README.md` |
| `integrations/jarvis-connectors/jarvis_connector/base.py` | **fix:** the result cap now covers the whole MCP result Jarvis receives (9,500 characters); new `fits()`/`result_size()` |
| `integrations/jarvis-connectors/connectors/notes/server.py` | `read_note` returns at most 3,000 characters, to fit the corrected cap |
| `integrations/jarvis-connectors/tests/test_youtube.py`, `tests/conftest.py` | new tests; the loader registers modules in `sys.modules` |
| `integrations/jarvis-connectors/evals/youtube_qwen_eval.py` | new live model evaluation |
| `jarvis/capabilities.py` | new `youtube_lookup` route (YouTube plus playlist/views/duration/details/links/top-N wording) → `mcp_call`, `browser_navigate` |
| `skills/youtube-media/SKILL.md` | connector section: tool list, an exact `mcp_call` example, playback hand-off, no answers from memory |
| `.jarvis/mcp.json` (app) | new: server `youtube`, enabled and trusted; `.venv` python plus `--runtime builtin`; exact `allow_tools`; `env_names` `JARVIS_YOUTUBE_API_KEY`; 30 s timeout |

## Defects found and fixed during the work

1. **The base result cap let Jarvis receive cut, invalid JSON (introduced in the previous turn).**
   The bridge sends the value twice (text plus structuredContent, with re-escaping) and truncates
   at 10,000 characters. The old cap of 8,000 characters applied to the value alone, so a
   6,000-character note would have been truncated. A live `playlist_videos` call with 15 items hit
   the guard and failed. After the fix it returns all 15 items in 8,130 characters, and larger
   playlists are trimmed with `more: true`.
2. **The model invented titles.** With full-width titles such as "ＯＳＡＫＡ", qwen3.5:9b answered
   playlist contents with made-up titles in direct mode (run 1). Titles are now NFKC-normalized,
   and run 2 passed 9/9 in direct mode.
3. **Jarvis-mode planner chose the wrong tool or packed the call into the wrong field.** Two
   successive guide fixes addressed this (runs 2 and 3, then run 4): "media_search cannot find
   playlists", an exact `mcp_call` example step, and "never answer from memory".
4. **Two scorer and test mistakes of mine, fixed:** a correct "fake link" answer given without a
   tool was counted as a failure, and a test wrongly assumed that Jarvis validates arguments before
   approval. Jarvis approves first and validates before `tools/call`.

## Test results

| Check | Kind | Result |
| --- | --- | --- |
| Connector suite (`integrations/jarvis-connectors/tests`), `JARVIS_LIVE_YOUTUBE=1` | regression + live | **89 passed, 1 skipped** (symlink creation is not permitted) |
| includes 41 YouTube tests: link allowlist and lookalike hosts, credentials/ports, page parsing (new and legacy layouts), consent or changed pages, no IP or stream-URL leakage, API key never returned, network errors without URLs, trimming, schemas accepted by `mcp_contract` | offline | PASS |
| includes live YouTube through `ToolRegistry` → `mcp_bridge` → connector: video search, playlist search, playlist listing, details | live network | PASS |
| `tests/test_prompt33_mcp_boundaries.py` | regression | 8 passed |
| 43 Jarvis test files touching routing, media, skills and MCP (after the route change) | regression | **865 passed, 20 skipped, 0 failed** (15 min 46 s) |
| Skill and routing tests after the final guide text | regression | **395 passed, 2 skipped** |
| `python -m jarvis.launcher --check` | readiness | `ready` |
| Full Jarvis regression (about 3,600 tests) | regression | NOT RUN in this change |

## qwen3.5:9b evaluation (live)

There are ten user-style prompts. Every connector call ran through Jarvis's real
ToolRegistry → mcp_bridge → connector → live YouTube path, with approval auto-granted and counted
by the harness. Playback steps (`browser_navigate`, `media_search`, `media_control`) were scored
but **not executed**.

- **direct mode:** the model sees the connector's tools as native functions.
- **jarvis mode:** the model gets Jarvis's one-step JSON format, the tools Jarvis's capability
  routes offer for the prompt (with field hints from `tools._FIELDS`) and the youtube-media guide.
  This mirrors the planner's format and settings; it is **not** the full Jarvis Brain.

| Run | Change before it | direct | jarvis |
| --- | --- | --- | --- |
| 1 ([json](qwen-eval-run1-before-fixes.json)) | none | 7/9 | 5/10 |
| 2 ([json](qwen-eval-run2-nfkc-guide.json)) | NFKC titles, guide rule, field hints, scorer fix | **9/9** | 3/10 |
| 3 ([json](qwen-eval-run3-jarvis-example.json)) | exact `mcp_call` example step | n/a | 6/10 |
| 4 ([1](qwen-eval-run4-jarvis-trial1.json), [2](qwen-eval-run4-jarvis-trial2.json), [3](qwen-eval-run4-jarvis-trial3.json)) | "never answer from memory" | n/a | **8/10, 8/10, 8/10** |

In run 2, the drop to 3/10 happened because the model now chose the right tool and arguments but
put the whole call in `value`. The exact example step in run 3 brought it to 6/10. Run 4 time per scenario: median
about 27 s (the model was already loaded).

**Still failing in all three run-4 trials:** "How long is this video <link>?" and "top 5 results
for python asyncio tutorial". The model returns `done=true` on step 1 with an invented duration or
an invented list and calls no tool. In live Jarvis, a first-step `done` goes to the independent
goal verifier (`brain.py`, `incremental_plan and plan.get('done')`). If the verifier does not
confirm the goal, Jarvis says "Task paused…"; if it does, Jarvis says a fixed "Finished…" message.
Either way the invented answer is not spoken. The effect is a stalled request, not wrong
information. Not verified live.

## Not run, or open

- **Full Jarvis Brain with voice or typed input → connector:** NOT RUN. The harness above mirrors
  the planner and is not the Brain.
- **Playback hand-off** (`browser_navigate` to a `play_url`, then verified playback): scored only.
  `browser_navigate` does not itself verify playback.
- **Every `mcp_call` shows an approval card.** This is Jarvis's existing policy and was not weakened.
  A lookup therefore needs one spoken "approve".
- **YouTube Data API mode:** offline tests only. No key is configured.
- **SDK v2 runtime:** NOT RUN, because `mcp` 2.x is not installed. The connector is pinned to
  `--runtime builtin`.

## Security checks

- The connector fetches only `https://www.youtube.com` and `https://www.googleapis.com` and refuses
  redirects to other sites.
- Pages are limited to 8 MB, and the timeout is 12 s per request.
- Only named fields are returned. Live pages embed stream URLs containing the requester's IP
  address; a test proves they never appear in results.
- The API key travels only through `env_names`, which the bridge redacts. It never appears in
  results or error text (tested).
- Read-only: there are no write tools. Every tool advertises `readOnlyHint`.

## Rollback

1. Delete `app/.jarvis/mcp.json`, or set `"enabled": false`. Jarvis then cannot start the connector.
2. Revert the `youtube_lookup` route in `jarvis/capabilities.py` and the "YouTube lookups" section
   of `skills/youtube-media/SKILL.md`.
3. Remove `integrations/jarvis-connectors/connectors/apps/youtube/`.

Nothing else depends on the connector.
