# Automation upgrade

Updated 2026-10-01. This change improves target selection and avoids repeated model inference for supported, explicit workflows. It does not establish that every desktop task succeeds or finishes in five seconds.

## Causes found and changes

| Observed cause | Implementation |
| --- | --- |
| Each accessibility observation started another Python/COM process. | A hidden, persistent UIA worker handles fresh observations and actions. Only the process stays warm; target wrappers and geometry are rechecked on each request. |
| Simple media tasks could require planning, decision and visual-model calls. | Direct workflows compile supported requests into explicit steps, then check the requested result using DOM, accessibility or Windows media state. These workflows use no model calls. |
| Duplicate links and buttons became separate choices. | Links with the same exposed destination collapse into one navigation choice. Explicit named context disambiguates matching labels. Different destinations remain separate. |
| YouTube's search field was absent from the live UIA snapshot. | Playwright controls a separate Jarvis Chrome window through the actual page DOM. Search text, result identity and active playback are checked. |
| Native Spotify search and song rows had unexpected accessibility roles. | The current query ComboBox and song metadata under Search results are recognized. Library entries and music-video rows are excluded. Artist metadata helps match named songs. Playback is checked through Spotify's Windows media session. |

For general model-planned tasks, exact, unique controls explicitly named in the user's goal can avoid the decision-model call. File/process evidence and exact field readback can avoid redundant visual inference. Ambiguous targets and other goals retain the existing planning and verification path. Ollama inference still runs on CPU on this PC; complex tasks can remain slow.

## Use

Restart Jarvis once after updating. Examples:

- `open YouTube and search robot tutorials and play first video`
- `search YouTube for robot tutorials and play second video`
- `play The Chainsmokers Don't Let Me Down on Spotify`
- `open calculator and open notepad`
- `open Jarvis browser`

`open YouTube` and explicit YouTube searches use the owned Chrome session by default. Follow-up search, ordinal selection and player commands use DOM when the selected window belongs to that session. Other browser windows retain the accessibility route. An explicitly requested Edge/Firefox window uses the existing route rather than silently substituting Chrome. The direct compiler rejects unsupported extra action clauses; other task phrasing still uses the planner.

The planner now has `browser_inspect`, `browser_navigate`, `browser_click` and `browser_fill`, bringing the registry to **69 tools**. Click/fill require the exact freshly observed URL and a unique named target. Fill takes exact user-requested text and checks the resulting value. Generic clicks return dispatch evidence and require separate goal verification. Password filling and sensitive account actions do not gain automatic approval through these tools.

## Setup and configuration

Playwright **1.63.0** is installed in `.venv`, pinned in [requirements/runtime.txt](../requirements/runtime.txt), and declared in [config/runtime_manifest.json](../config/runtime_manifest.json). It uses the configured installed Chrome; no additional browser binary was downloaded. Normal setup installs the dependency. This browser layer needs no paid API.

Settings in [config/config.json](../config/config.json):

```json
{
  "agent_runtime": {"fast_workflows": true, "dom_browser": true},
  "brain": {"fast_grounding": true}
}
```

`fast_workflows` selects the direct task compiler. `dom_browser` selects the preferred YouTube route; it does not remove the browser tools from the registry. `fast_grounding` enables the conservative exact-target/model-call shortcut. Restart after changing settings.

Chrome uses `.jarvis-runtime/browser-profile/`, ignored by Git. This separate local profile persists logins and cookies; account-only features require signing in there. The worker controls only its own window/profile and does not attach to or close ordinary shared Chrome windows. There is no new saved UI screenshot for this backend change.

## Memory and recovery

The existing Obsidian vault now contains **nine bundled skill guides**, including browser navigation, plus the refreshed **69 tool / 41 direct-operation** catalogue. Existing project/software inventory and its original scan date are preserved. Successful managed tasks update procedures only after `goal_verified`; failed, partial and uncertain attempts are not promoted. New actions still inspect the current surface rather than replaying stored handles or coordinates. See [skills and learning](skills-and-learning.md).

UIA and browser transports have deadlines, cancellation, owned-process cleanup and bounded retry backoff. Watchdog repair can start an idle worker; it cannot replay a previous external action. Stop/Quit closes owned workers. A deliberately closed browser is not reopened by background repair. A new explicit open/search task can open another session. A timeout after dispatch reports uncertainty instead of clicking again.

## Live evidence, 2026-10-01

The default sandboxed process could not enumerate the interactive desktop. The approved desktop test process could. These later checks are real desktop checks, separate from mocked regression tests.

| Live check | Result | Scope |
| --- | --- | --- |
| Owned Chrome YouTube search | 4.087 s first request; 0.500 s next request | Query URL and visible video results verified; [report](../artifacts/reports/browser-automation-check.json). |
| Complete YouTube search → first video → playback | 5.681 s cold; **2.918 s warm** | Selected video ID and actual non-ad playback verified, then paused; zero model calls; [report](../artifacts/reports/direct-workflow-check.json). |
| Native Spotify search → matched song → playback | **6.656 s** | Actual Spotify playback observed through Windows media state, then paused; zero model calls; [report](../artifacts/reports/spotify-search-check.json). |
| Native Spotify UIA observation | 2.412 s first; 1.727 / 1.676 s warm | 188 controls observed; read-only process-reuse check before the later per-request collection optimization; [report](../artifacts/reports/warm-uia-check.json). |

These timings exclude speech recognition and spoken output and are individual local measurements, not a latency guarantee. An earlier cold playback check timed out; its cause was not established. [Initial playback failure](../artifacts/reports/direct-workflow-check-initial-failure.json), [initial Spotify row-detection failure](../artifacts/reports/spotify-search-initial-failure.json). Ads, buffering, account restrictions, changed site layouts and missing accessibility patterns can still prevent completion. Browser controls beyond search, selection, playback and pause have regression/readiness coverage but were not all checked live. Frame stepping requires a paused video; previous-video navigation may require a playlist.

## Research and attribution

Firecrawl was used for research. The implementation is original Jarvis integration code; no new external agent repository was installed or copied.

- [Microsoft UFO](https://github.com/microsoft/UFO): Windows automation combining native UIA/Win32/COM and application interfaces; informed the hybrid native/browser approach.
- [Playwright actionability](https://playwright.dev/python/docs/actionability): unique target resolution and visibility/stability checks before actions; implemented through Playwright locators.
- [Playwright release/dependency](https://pypi.org/project/playwright/): the installed Python browser library.
- [Workflow-use workflows](https://github.com/browser-use/workflow-use/blob/5d2d19fe8835cc86f1bf3e04302a5000d590f249/workflows/README.md): reusable semantic workflows informed the design. Its AGPL code was not imported or vendored; its published speed claims are not Jarvis measurements.
- [Browserclaw](https://github.com/browserclaw/browserclaw): semantic browser observations informed target handling; no package or code was imported.

**Final regression/readiness, 2026-10-01:** All 523 tests passed in 30.560 seconds. Launcher readiness reported `ready`, no missing components, local Qwen planner/vision and Hermes planning. Documentation local links were checked. These results are separate from the live media checks above.

## Reproduce regression/readiness checks

Run from the application folder:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe -m jarvis.launcher --check
.venv\Scripts\python.exe -m scripts.skills.refresh_skill_memory
.venv\Scripts\python.exe -m scripts.skills.refresh_media_memory
```

The live reports used public media and temporary task journals. They do not contain account inventories, cookies or private desktop captures. The regression suite checks ambiguous versus duplicate targets, actual Spotify accessibility shapes, no replay after uncertainty, cancellation, worker backoff/repair, Stop, intentional browser closure, scope/URL checks and value readback failures.
