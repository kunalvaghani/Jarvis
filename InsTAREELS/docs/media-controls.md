# YouTube and native Spotify controls

Updated 2026-10-01. For playing by name, unscoped controls ("pause", "next song") and the island media card, see the newer [full YouTube and Spotify control](media-player.md) page (2026-10-10). The later [automation upgrade](automation-upgrade.md) adds the owned Chrome DOM route and live YouTube/native Spotify playback verification. Research used Firecrawl and the official [YouTube shortcuts](https://support.google.com/youtube/answer/7631406?hl=en) and [Spotify shortcuts](https://support.spotify.com/us/article/keyboard-shortcuts/) pages. Windows media-session and audio-session controls use the existing local dependencies; no Spotify Web API key or paid integration is required.

## Why the reported commands failed

- The ordinal parser accepted `select first video` but omitted `play first video`. The latter could fall through to the planner, which could drop the explicit position and ask about several matching titles. All four verbs (`play`, `open`, `select`, `choose`) now preserve the requested video number and activate one fresh result directly.
- Spotify was present in both the website and installed-app catalogs. The website check ran first. `open Spotify` now prefers its configured Windows app registration; `open Spotify web player` or an explicit browser request opens the website.
- General `search ...` went to Google. It now uses foreground YouTube or native Spotify context, otherwise web search. Explicit `search ... on YouTube/Spotify` keeps the named service. An active YouTube search field is filled, exact text is checked, and Enter is sent once. If no suitable field is exposed before any write, Jarvis opens an encoded YouTube results URL instead. A failed or uncertain write is never retried through another method.

Google video results can expose the same title as a hyperlink and several embedded player buttons. Result selection now includes those embedded video buttons, removes repeated title variants, and excludes player/navigation buttons and channel context. Selection uses current screen order, not a remembered title or fixed screen coordinates. Unqualified `select the video` can still be ambiguous; a supplied ordinal does not require another numbered choice.

## Direct commands

Say these after the wake word. The examples use runtime search text, media state and accessible controls.

| Intent | Examples |
| --- | --- |
| Launch | `open YouTube`; `open Spotify`; `open Spotify web player` |
| Search | `search for robot tutorials on YouTube`; `Spotify search for jazz`; `search for jazz` while the media app is active |
| Choose a result | `play first video`; `open second video on YouTube`; `select option number 1`; `play first song on Spotify`; `select second track` |
| Search and play by name | `play jazz on YouTube`; `play Don't Let Me Down on Spotify`; supported direct workflows verify the chosen result and playback without model calls |
| YouTube playback | `pause video`; `resume video`; `next video`; `previous video`; `what is playing on YouTube`; `restart video` |
| YouTube volume | `mute on YouTube`; `unmute on YouTube`; `volume up on YouTube`; `set volume to 40 percent on YouTube` |
| YouTube seek | `rewind 30 seconds on YouTube`; `skip 20 seconds on YouTube`; `seek to 50 percent on YouTube` |
| YouTube viewing | `full screen`; `exit full screen`; `miniplayer`; `theater mode on YouTube`; `toggle captions on YouTube`; `enable captions on YouTube` |
| YouTube speed and detail | `speed up on YouTube`; `slow down on YouTube`; `next chapter on YouTube`; `previous chapter on YouTube`; `next frame on YouTube`; `previous frame on YouTube` |
| Spotify transport | `pause Spotify`; `resume Spotify`; `next song on Spotify`; `previous song on Spotify`; `what's playing on Spotify` |
| Spotify playback options | `turn on shuffle on Spotify`; `turn off shuffle on Spotify`; `repeat one on Spotify`; `repeat all on Spotify`; `repeat off on Spotify`; `rewind 15 seconds on Spotify` |
| Spotify volume | `set Spotify volume to 50 percent`; `volume up on Spotify`; `mute Spotify`; `unmute Spotify` |
| Spotify navigation | `show queue on Spotify`; `show library on Spotify`; `show playlists on Spotify`; `show artists on Spotify`; `show albums on Spotify`; `show podcasts on Spotify`; `show now playing on Spotify`; `show liked songs on Spotify`; `show home on Spotify` |
| Spotify current-song actions | `show lyrics on Spotify`; `like this song on Spotify`; `add this song to queue on Spotify` when the corresponding control/menu is exposed |
| Other visible controls | `list buttons`; `select Settings`; `open Settings menu`; `fill Search field with robot tutorials`; named multi-step tasks for quality/speed menus, filters, playlists and other accessible app controls |

These are supported command routes, not a guarantee that every control exists on every page/account/version. Like/save checks the visible saved state instead of toggling an already saved song off. Spotify track ordinals use fresh song/track rows or Search results rows with song metadata; sidebar playlists and music videos are excluded. Playback uses one exposed Play button or native double-click on a freshly revalidated row. The managed workflow checks actual Windows media playback; selection alone does not prove playback.

## Task and memory integration

The shared planner registry includes `media_control`, with a `platform` of `youtube` or `spotify`. YouTube operation values include `play`, `pause`, `next`, `previous`, `mute`, `unmute`, `fullscreen`, `exit_fullscreen`, `captions`, `captions_on/off`, `seek_10/-10`, `position_0..100`, `volume_0..100/up/down`, `speed_up/down`, `next/previous_chapter`, `next/previous_frame`, `restart`, `theater`, `miniplayer` and `status`.

Spotify transport and volume reuse their dedicated Windows implementations. Spotify UI values include `queue`, `library`, `playlists`, `artists`, `albums`, `podcasts`, `home`, `now_playing`, `liked_songs`, `lyrics`, `like` and `add_queue`. Menus and other app operations remain available through the existing named select, fill, scroll and menu tools. The same catalog reaches Hermes/local planning and Obsidian tool-context retrieval. Media platform identity is included in task checkpoints so recovery cannot substitute a different service.

`scripts/skills/refresh_media_memory.py` updates only the existing owned tools note and tool/operation fields in the Obsidian index, preserving the existing project/app inventory and its original scan date. Normal startup also refreshes the catalog in the background. The existing Obsidian vault was refreshed successfully on 2026-10-01: **69 runtime tools and 41 direct operations**, including media controls and context-aware search.

## Execution and limits

- Scoped controls check the actual browser/Spotify executable and the active YouTube window identity. A single matching background media window can be focused for the explicitly requested service. Multiple possible windows require the user to select the intended window. A foreground change after observation cancels the action.
- YouTube shortcuts focus an observed player control first; letters are never blindly typed into an unknown search field. Volume and percentage seek use the observed slider range and verify the result.
- The accessibility shortcut route supports relative YouTube seeking in multiples of 10 seconds up to 300 seconds; the owned DOM player route supports signed integer-second seeks. Percentage seeking supports 0–100. Frame stepping requires an already paused player. Previous-video navigation requires a playlist. Caption on/off requires exposed toggle state; an explicit toggle works with the named captions button. Controls hidden by layout, ads, sign-in, account restrictions or missing accessibility patterns may be unavailable.
- Spotify transport targets its own Windows media session and volume targets only `Spotify.exe` audio sessions. The app must expose the requested feature; rejected controls are reported, and playback is not fabricated. Volume handles an already initialized Windows COM apartment without uninitializing another library's COM state.
- Mutations are not automatically replayed after failure. The existing bounded UI worker, Stop/Quit cancellation and silent recovery remain in use. The later automation upgrade adds persistent owned UIA/browser workers and Playwright with bounded recovery; external actions are never replayed.
- Direct media commands avoid language-model planning. UI-provider latency, loading, recognition and speech still vary; universal sub-five-second completion has not been established.

## Verification on 2026-10-01

The focused regression suite covers ordinal preservation, duplicate Google video results, player/navigation exclusion, Spotify app routing, search-field identity, exact text verification before submission, foreground changes, source scoping, already-paused/saved states, failed clicks/writes without replay, player shortcuts, frame preconditions, slider ranges, COM ownership and planner/checkpoint dispatch.

Initial regression/readiness checks, before the later automation upgrade: the installed Spotify Windows package and configured native app registration were checked. The final focused suite passed **27 tests**; the full regression suite passed **489 tests in 30.067 seconds**, and launcher readiness returned `ready` with no missing requirements. `git diff --check` passed.

Earlier sandboxed checks: an opt-in live check requested a new YouTube search window and native Spotify launch, but neither window could be observed within its deadline. A subsequent read-only check found **zero visible windows** in this execution desktop even though Chrome and Spotify processes existed. Live search, result activation and audible playback were therefore **not verified**. The report path was subsequently refreshed by the later interactive check; see the dated evidence below. Regression/readiness checks do not substitute for these live checks. Run the optional live script from your ordinary Windows desktop to verify launch/search; it does not start playback or modify an account.

**Later interactive checks, 2026-10-01:** An approved desktop process could see the actual windows. The owned Chrome YouTube search/first-video workflow verified active playback in 5.681 s cold and 2.918 s warm; native Spotify search/matched-song playback verified in 6.656 s. Both used zero model calls, excluding recognition and spoken output. The earlier Spotify one-control snapshot was taken during loading; later UIA snapshots exposed 188 controls. [Full results, initial failures and limitations](automation-upgrade.md#live-evidence-2026-10-01).

Restart Jarvis once to load the new command routes. Then try `open Spotify`, `search for jazz on Spotify`, or `open YouTube`, `search for robot tutorials`, `play first video`. Previously unfinished tasks can be resumed through the existing checkpoint command after inspecting current state.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_media_routes.py -q
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe -m jarvis.launcher --check
.venv\Scripts\python.exe -m scripts.skills.refresh_media_memory
# Optional visible desktop check; launches apps and submits one generic search.
.venv\Scripts\python.exe -m scripts.verification.verify_media_controls --live
```
