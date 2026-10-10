# Jarvis's independent cursor

## Update — real clicks with Jarvis's own pointer (2026-10-10 IST)

Jarvis now **physically clicks** wherever a task needs a click: buttons in apps, links and buttons in your own
browser, custom controls and canvases. The cyan **J** cursor moves to the target and Jarvis taps it with its own
pointer ([jarvis_pointer.py](../jarvis/jarvis_pointer.py)), using Windows touch injection, a separate input
device. Your mouse buttons are never used.

- **First choice for every click.** The pointer is the first click method for buttons, links, menus, tabs, list
  items, check boxes and similar controls ([execution_adapters.py](../jarvis/execution_adapters.py)). Before
  tapping, Jarvis checks that the control's centre point really belongs to that control in that window and is not
  covered by another window. If not (covered, off-screen, too small), it falls back to the accessibility actions
  described below, before any input.
- **Targets without accessibility.** A point found by visual grounding with no accessible control (a canvas, a
  game-like surface, an unlabeled image) is now tapped instead of refused
  ([independent_cursor.py](../jarvis/independent_cursor.py)).
- **Your mouse.** For compatibility with mouse-only apps, Windows moves its hidden mouse position to the tap.
  Jarvis puts your pointer back where it was right after the tap (about 0.1 s) and keeps it visible. If you are
  moving the mouse or holding a mouse button, Jarvis waits up to 1.5 s for a pause, and otherwise does not click.
  The earlier statement below that the system pointer is "never moved" no longer holds for this path.
- **Jarvis's own browser** keeps its existing Playwright clicks: real browser-level mouse events inside its own
  Chrome profile, with the in-page cue. They never touch your pointer.
- **Off switch.** `cursor.physical_clicks` in [config/config.json](../config/config.json) (default `true`).
  Setting it to `false` restores the accessibility-only behaviour described below.
- Clicks are never retried automatically after an uncertain outcome.

### Live checks — 2026-10-10 IST

- A custom web button (a plain element that only reacts to real clicks) in the user's regular Chrome was clicked
  through Jarvis's real UI path by the `jarvis-pointer` provider: the page counted one click, and the mouse stayed at
  the same position before and after.
- A canvas with no accessible control was clicked through the visual-point path: one click counted, and the mouse
  position was unchanged.
- During development, a raw tap moved the hidden mouse position to the target; restoring it and a one-pixel nudge
  returned the pointer to its exact position in a visible state. That restore is part of every tap.

Regression on 2026-10-10 IST: **1,387 tests ran in 210.844 s, OK with one skipped class** (Docker's Linux
engine unavailable) ([log](../artifacts/logs/pointer-regression.log)); `python -m jarvis.launcher --check`
reports `ready`. Pointer and task-cancelling fixtures: [test_jarvis_pointer.py](../tests/test_jarvis_pointer.py).

These checks covered the listed targets, not every app, game or account action. Apps running as administrator do
not accept input from a normal-user Jarvis.

---


Implemented and checked **2026-10-08 IST**. When Jarvis activates a supported
control, a cyan arrow marked **J** approaches it, activates it once, and disappears.
The user's system pointer is never moved, hidden, restored or borrowed by this
path. Existing named-control requests, owned-browser clicks and supported
coordinate recipes use it automatically; there is no new setting or dependency.
Start Jarvis normally after the update.

![Actual headful Chrome screenshot of the owned cursor fixture, before activation](../artifacts/media/independent-cursor-browser-fixture.png)

This is a real rendered verification fixture with the cyan J cue and a counter
still at zero, before the click. It is not a production-notch screenshot, a
YouTube/Spotify account capture or an upstream reference image. The cursor
artwork and lifecycle are independently authored for Jarvis.

## How activation works

Windows applications use [UI Automation Invoke](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-implementinginvoke)
and the existing role-aware SelectionItem, Toggle or ExpandCollapse patterns.
[independent_cursor.py](../jarvis/independent_cursor.py) displays a nonactivating,
click-through, disposable Win32 window, with a roughly 180 ms approach animation.
The existing serial UI worker rechecks identity, owner, bounds, visibility,
enabled state and foreground after animation, before the one dispatch. Grounded
visual points must resolve a fresh accessible control; non-password Edit targets
can receive native focus. UWP frame hosts and their child processes are matched
through their actual root window. Changed targets/focus cancel before input.

The cue's own rendering thread expires after 950 ms even if a native action
blocks. Normal cleanup also disposes it; terminating its owning worker removes
the OS window. No additional daemon or recovery service is needed. Existing
bounded workers and damaged-copy-preserving source snapshots cover the modules.
Provider order remains UFO, Windows-MCP, CUA, Open Computer Use, Agent-S; the last
adapter now refuses absent accessibility patterns instead of using a physical
centre click. Upstream licenses and pinned source attribution remain retained.

Jarvis's owned browser uses [browser_cursor.py](../jarvis/browser_cursor.py).
It pins the selected DOM element, draws a temporary SVG cue, checks that the page
has not navigated, and calls Playwright once through Chrome's protocol. The
element remains the same across animation; Playwright checks actionability.
The cue ignores pointer events, is removed after the action, and has a 1.2 s
fallback removal timer. Navigation closes its document. DOM construction uses
elements/attributes rather than `innerHTML`, respecting YouTube's Trusted Types
policy. Cleanup errors never trigger another activation.

Direct media APIs, text assignment, shortcuts and no-op state requests do not
need a button cue. App focus and keyboard input remain shared. This is an
independent visual cursor with semantic activation, not a second Windows mouse
device or an independent desktop session.

## Supported targets and limits

Native buttons need an actual supported accessibility pattern. Custom canvas,
games, inaccessible/elevated controls and physical-only gestures may refuse.
Mouse move, drag, wheel, button-down/up, right/middle/double/triple-click recipes
now stop before physical input. Single coordinate clicks require an explicit
current-window point and an accessible control there. Native accessibility
scroll and supported browser actions remain available. The original 493-command
catalog is retained as reference; its entries do not imply every mouse recipe
can run. [Updated command contract](windows-commands.md).

The animation starts near the selected control. It does not expose private
screenshots, add screen/model uploads, or change account/credential storage.
Live actions still need fresh admitted state; there is no automatic action
replay after uncertainty. These checks establish the listed controls, not every
button, login, account action or arbitrary app task.

## Verification on 2026-10-08 IST

The [aggregate receipt](../artifacts/reports/independent-cursor-validation.json) combines
**separately dated** actual-worker checks, with explicit postconditions:

| Target | Action and observation | System pointer |
| --- | --- | --- |
| Owned native fixture | Exactly one button activation by the provider route and by grounded accessibility; click-through/noactivation styles, foreground preservation, disposal and expiry while callback blocks | Unchanged in the clean native run |
| Owned DOM fixture | Counter 0 to 1, one activation, cue removed | Unchanged in the clean DOM run |
| YouTube | Guide drawer closed to open | Unchanged; cue removed |
| GitHub public repository | Platform menu `aria-expanded` false to true | Unchanged; cue removed |
| Spotify web | Browse changed path `/` to `/search` | Unchanged; cue removed |
| Spotify desktop | Search once; focused search ComboBox observed on a read-only follow-up | Unchanged |
| Windows Camera | Switch to video mode, observe changed mode control, restore original photo mode | Unchanged for switch and restoration |

No Camera photo/video was taken; no account write or GitHub publication was made.
Public sites ran in a fresh isolated headful Chrome profile, separate from user
tabs and Jarvis's normal browser profile. Generic browser receipts still report
downstream goal verification as false; the verifier independently checked each
specific property in the table, without promoting arbitrary task completion.

[Original live history](../artifacts/reports/independent-cursor-live-history.json) retains
the early paint signature bug, YouTube Trusted Types failure, ambiguous GitHub
target refusal and trials where global pointer readings changed. Those readings
cannot establish who moved the pointer. Clean native and website checks occurred
in separate runs; this is not a claim of one perfect combined trial. Spotify's
initial observer wrongly expected an Edit rather than a ComboBox. A fresh
read-only observation corrected the evidence without repeating its activation;
[history](../artifacts/reports/independent-cursor-spotify-history.json) is preserved.

**1,165 regression tests passed in 216.872 seconds** after final source review:
[final log](../artifacts/logs/cursor-final-regression-tests.log). Eight focused cursor
checks cover stale focus/navigation, unsupported patterns, one dispatch and
cleanup on failure; [focused log](../artifacts/logs/cursor-focused-tests.log).
The 47 focused visual checks include rejection of physical mouse injection
before `SendInput`; [visual log](../artifacts/logs/cursor-visual-tests.log).
All five native provider checks passed separately:
[actual provider log](../artifacts/logs/cursor-native-adapters.log).
These regression/provider checks are distinct from the live app/site observations.

The [repository audit](../artifacts/reports/cursor-repository-audit.json) parsed all 344
authored Python files with zero static correctness errors, validated all nine
bundled skill definitions and checked 769 local documentation links with no
missing targets. It retains 79 unused-import/variable warnings; static warnings
alone do not prove a file is disconnected or safe to delete.

Configured-service/dependency readiness is
[ready](../artifacts/reports/cursor-readiness.json). Hosted LocalGithub services and
optional external account integrations are outside that readiness scope.
Normal supervised startup is recorded separately in
[startup health](../artifacts/reports/cursor-startup-check.json); operational heartbeats
do not establish a fresh audible spoken answer.

Reproduce selected checks from the application folder:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_independent_cursor
.venv/Scripts/python.exe -m scripts.verification.verify_independent_cursor
.venv/Scripts/python.exe -m scripts.verification.verify_independent_cursor --web
.venv/Scripts/python.exe -m scripts.verification.verify_independent_cursor --app spotify
.venv/Scripts/python.exe -m scripts.verification.verify_independent_cursor --app camera
```

Native app checks require that app already open and left in the foreground.
They may refuse if focus changes; inspect the fresh state before issuing another
action. The Camera check changes and restores mode only.
