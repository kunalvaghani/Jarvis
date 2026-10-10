# Jarvis — local Windows voice assistant

**UI edge finish and smoother animation (2026-10-10 IST):** The existing island design,
glass controls and animations are retained. Fixed the one-pixel side tails, added
fractional-alpha blending around the outer curves, and removed the 24–30 fps animation
cap. Active motion targets the monitor's detected 60–144 Hz rate with rendering time
inside each frame deadline. Cached text/curves and small moving-region redraws reduce
repeated work; paused games stop uploading identical frames. Hidden UI startup/shutdown
and native-edge cleanup/fallback checks passed. See [behavior, measured callback rates
and verification scope](docs/ui-smoothness.md); rates vary with load and are not a
guarantee of constant compositor-presented FPS.
The final off-screen callbacks measured **99–119 fps** across the three fixtures;
**1,459 regression tests ran successfully with one skip**, and launcher readiness
reported **`ready`**. Jarvis remains stopped; start it normally once to load the fix.

![Rendered edge-finish preview over light and dark backgrounds — sample text, not a desktop screenshot](artifacts/media/island-smoothness-preview.png)

**Project organization (2026-10-09–10 IST):** The canonical application folder is
`app/`. Maintenance commands are grouped under `scripts/`, setup shortcuts under
`launchers/`, and settings/dependencies under `config/` and `requirements/`.
Historical artifacts are grouped and preserved. A local `InsTAREELS` junction
supports existing Windows paths. See the [folder map, migration and verification
record](docs/project-structure.md). Final regression ran 1,315 tests successfully
with one skip; configured launcher readiness is `ready`. All seven existing
environments resolve correctly, and recovery snapshots match the final source.
These are relocation/regression checks; historical live feature measurements
retain their original dates. Jarvis remains deliberately stopped.

**Long-term memory, API repair and bad-weather alerts (2026-10-10 IST):** Jarvis now builds its own memory in
the Obsidian vault. It learns facts about you from conversation (preferences, people, plans with real dates)
using the local Qwen 9B model in the background. It also saves "remember that …" immediately, forgets on request,
and summarises each conversation into `Jarvis Conversations/`. Every question and task now gets the relevant facts,
so "what music should I put on while studying?" uses what you told it, and "what did we talk about yesterday?" has
an answer. "What can you do", "which APIs are you connected to" and "check your APIs" answer from Jarvis's own
registries and a live test. The API check found 66 of 82 public APIs working. After replacing dead endpoints
(SpaceX → Launch Library 2, Bluesky, REST Countries → World Bank) and adding fallbacks, retries and timeouts, 77 of
82 work, plus Gmail. The rest are an upstream outage (Overpass) or optional self-hosted services. A weather watch
runs every 30 minutes, even mid-task. It warns about thunderstorms, heavy rain, strong wind, heat, fog, unhealthy
air, nearby earthquakes, cyclones and floods in the next 36 hours, aloud and on the island. Regression: 1,444 tests
passed with one skip; readiness `ready`. [Details, thresholds, settings and verification](docs/memory-apis-alerts.md).

**WhatsApp automation, incoming calls, voice approvals, and the "play/pause answered as chat" fix (2026-10-10 IST):**
"send a WhatsApp message to Jay saying I'll be late" opens WhatsApp Desktop and finds the person. A first name
alone lists everyone with that name as island choices; answer by name, number or click. Jarvis then drafts the
message, or uses your exact words with "saying exactly", and shows it on the island. It sends only after you say
"approve"/"send it" or click, and you can say what to change first. The chat header must confirm the right person,
and the sent message must appear in the chat. Nothing is resent if that can't be confirmed. "Reply to my WhatsApp
messages" drafts replies to unread chats. A watcher drafts a reply when a new message arrives and asks before
answering or declining incoming calls. Telegram is recognised (not signed in on this PC); Discord, Teams and others
say they aren't automated yet. Separately, "Pause." / "Play." with Whisper's punctuation now control the player
instead of reaching the chat model. Live on this PC (sent only to the account's own chat): send with a voice edit in
17.9 s, first-name choice plus verbatim send in 10.7 s, automatic reply in 12.6 s; calls are not yet tested live.
Regression: 1,429 tests passed with one skip; readiness `ready`. [How it works, commands, settings and limits](docs/whatsapp.md).

![Rendered island WhatsApp cards with made-up names — not a desktop screenshot](artifacts/media/island-whatsapp-card-preview.png)

**Spotify control follow-up repair (2026-10-10 IST):** Pause/resume, next/previous and
volume now work through the native Spotify session even after Jarvis's desktop
libraries initialize COM. Transport and metadata use fresh MTA threads with bounded
waits; cancelled or uncertain controls are never retried. Volume covers Spotify's
audio sessions on all active outputs, including a headset selected separately in
Windows. Repeated play/pause is harmless; previous sends a second press only after
observing the current song restart. Player selection also recognises Spotify in the
tray and ignores a closed last-used YouTube player. Added "increase Spotify volume",
"lower volume on Spotify" and "turn down the volume". Live low-level checks from a
COM-initialized caller passed pause/resume, next/previous and numeric/up/down volume;
the original 50% volume was restored. A separate live text check also passed through
the real Engine and Actions route for all these commands, including bare "play".
Microphone recognition and speech output were not tested.
Final regression: **1,455 tests ran successfully with one skip**; all 15 focused
Spotify tests passed, and launcher readiness reported **`ready`**, with no missing
or incomplete requirements. Jarvis was already stopped; start it normally once to
load the repaired source.
[Repair details and verification](docs/media-player.md#spotify-control-follow-up-repair-2026-10-10-ist).

**Full YouTube and Spotify control, with an animated island card (earlier 2026-10-10 IST checkpoint):** "play nadan parinde",
"open YouTube and play X" and "play X on Spotify" now search, pick the clearly matching song or video, play it and
verify playback directly, without the planner. A split utterance ("open YouTube" … "and play X") no longer ends up in
chat. YouTube search uses the YouTube Data API v3 when a key is saved in `secrets/youtube.json`, otherwise a keyless
search. Spotify uses the desktop app's search, its accessibility tree, a click with Jarvis's pointer, and Windows
media-session verification. Words like "pause", "next song", "volume up", "go back 10 seconds", "mute" and "play it
again" control whichever player is actually playing. Starting one service pauses the other. The island shows a red
YouTube or green Spotify card with artwork, title, live equalizer and progress for every media command. Live on this
PC: YouTube played in 5.2 s and Spotify in 7.7 s, and every listed control passed on both. Regression: 1,412 tests
passed with one skip; launcher readiness `ready`. [Commands, API key setup,
live results and limits](docs/media-player.md).

![Rendered island media cards with sample titles and generated artwork — not a desktop screenshot](artifacts/media/island-media-card-preview.png)

**Jarvis's own pointer clicks, and cancelling specific tasks (2026-10-10 IST):** Every click a task needs
(app buttons, links and buttons in your own browser, custom controls, canvases) is now a real tap with Jarvis's
own pointer while the cyan J cursor shows where it acts. Your mouse buttons are never used. Windows briefly moves
its hidden mouse position for older apps, and Jarvis restores your pointer right away; it waits if you are using
the mouse. Targets without accessibility support, which were refused before, are now clicked; accessibility
actions remain the fallback. Turn it off with `cursor.physical_clicks`. Live: a custom web button in your Chrome
and a canvas were each clicked once, with the mouse position unchanged. You can also cancel one queued task by
describing it: "cancel the YouTube one", "never mind the email", "remove number 2" (the queue status is now
numbered), "never mind" for your latest request, or "cancel everything except the email". Ties are never
guessed. Live: in a spoken session, "cancel the YouTube one" and "never mind" removed exactly those requests
while the running task finished. [Pointer details](docs/independent-cursor.md) ·
[queue commands](docs/fast-conversation.md#try-it).

**Natural male voice and smooth long speech (2026-10-10 IST):** Jarvis now speaks with a man's voice
(Kokoro `am_michael` + `am_fenrir` blend) and a human delivery: varied pauses, a longer pause between
paragraphs, soft breaths before some longer sentences, slight pace changes, and emotion from the words
(quicker when excited, slower when sorry). Answers are written like a warm, witty friend on a call, with an
occasional light joke when the mood fits. Speech is one continuous stream with no 2,500-character cut or
240-second limit, starts while the answer is still being written, and stops instantly when interrupted
without reloading the model. Live: a 4.5-minute reply was synthesized at 0.30× real time idle and 0.60×
while the planner generated (both ahead of playback); speech started 1.47 s after a reply and 0.83 s after
an interruption. Listening quality has not yet been judged by a person; samples of seven male voices are in
`artifacts/media/voice-samples/`. [Voice, settings and measurements](docs/natural-male-voice.md).

**Writing by voice and push-to-write (2026-10-10 IST):** Dictation mode is gone. “Write a short
thank-you note here” has the local model compose the text and types it into the current window as it is
generated; “write exactly …” (or “word for word”, or quoted text) types your words verbatim, keeping capitals
and punctuation; “in Notepad” targets an app, and “open Notepad and write …” always writes into Notepad.
Holding **Left Ctrl + Left Alt** types everything you say at the cursor until you let go, with no wake word.
A keyboard hook replaces only the final Alt release with a harmless mask key so Notepad/Office never fall
into menu-shortcut mode. Other key combinations are left alone. Line breaks are Shift+Enter, and terminals
never receive line breaks. Live: a composed 26-word note began typing in Notepad after 11.8 s; exact text kept
“PASSED at 5:30 PM!”; the hook's release handling held in both release orders. A hands-on push-to-write
session with the physical keys and microphone is not yet verified.
[Commands, hotkey details and limits](docs/push-to-write.md).

**Fast planning, task queue and natural conversation (2026-10-10 IST):** Say "Jarvis" once and
talk like a call; it keeps listening until 10 minutes of silence or "goodbye". Tasks you give during
the conversation queue up and run in the background ("Okay, I'll do that next") while questions are
answered; "what's in the queue", "cancel this task" and "stop all tasks" control them. Natural
phrasing works ("let's make an email", "let's watch a video about cats on YouTube"), and ordinary
talk gets a reply instead of becoming a task. Planning executes each step as soon as it is planned
and sends a failed or ineffective step back to the planner, which tries a different approach from
that point (up to five), never repeating a failed action; uncertain writes still pause. Speed comes
from measured fixes on this RTX 3050 (4 GB): the split CPU+GPU model stays loaded with 12 CPU
threads, each task's planning calls reuse the model cache (next-step prompt reading 1.2–5.5 s
instead of 18–24 s), screenshots are sent only when needed, and redundant model checks and
irrelevant tools were removed. Live tests: the Wikipedia task finished in 68.5 s (previously failed
after 209 s), "open Notepad and type …" works (new `type_text` tool, window focus and typing-speed
fixes), and conversational answers start in 4–6 s (previously 40 s, or no answer). Regression:
1,358 tests OK with one Docker-dependent skip; launcher readiness `ready`. The call was simulated
through the real voice engine; no live microphone session is claimed.
[Usage, configuration, measurements and limits](docs/fast-conversation.md).

**Gmail full voice automation (2026-10-10 IST):** Jarvis can now send emails,
send or delete drafts, move emails to Trash and restore them, apply and create
labels, move, archive, mark read/unread/starred, group emails by sender and read
emails aloud. Say, for example, `send an email to name at gmail dot com asking about
lunch`, `read aloud my latest email`, `delete the latest email`, `move the latest
email to Work` or `group my emails by sender`. Every send, Trash, label change and
draft deletion needs one click on the approval card, with readback verification and
no replay. "Delete" always means Trash, which is recoverable for 30 days. Replying
and forwarding are not supported yet. The added `gmail.modify` scope needs a one-time
reconnection, which is already completed on this machine. A live trial on the connected account passed
all 13 operations through real command dispatch, using only self-sent test mail.
The full regression ran 1,334 tests successfully with one Docker-dependent skip, and
launcher readiness is `ready`. No spoken microphone trial is claimed; the commands
load on the next start.
[Commands, safety and verification](docs/gmail-api.md#send-trash-labels-and-speech--2026-10-10-ist).

**Gmail command repair (2026-10-09 IST):** Draft/write, message-body reads, draft
reads/lists and updates now use direct Gmail API workflows rather than screenshot
planning. Literal subject/body commands parse locally, including speech punctuation
and mixed quotation marks. Topic-based composition uses one isolated Qwen text
interpreter; no screenshot or app search is supplied. Updates resolve exact draft
subjects, preserve unchanged fields/HTML MIME and require approval plus hash-checked
readback. Durable local journals prevent uncertain writes from replaying.
Live existing-test draft read, message-body read and update/readback passed; real
Qwen composed the requested topic after conflicting planner rules were removed.
Final command regression: 1,308 tests ran successfully; the live Docker isolation
class was skipped because the Linux engine was unavailable.
Configured launcher readiness is `ready`. After final checks, the user chose to
keep Jarvis stopped; the repaired command workflow loads on the next start.
[Commands and verification limits](docs/gmail-api.md#gmail-command-workflows--2026-10-09-ist).

**Unread Gmail repair (2026-10-09 IST):** The reported `find my unread emails`
task searched for a Gmail desktop application and repeated that unsuccessful action.
Plural email routing, natural command parsing and API-first planner guidance are
now corrected. Exact unread-list commands use one bounded API search plus sender,
subject and date metadata, without screen/model inference or marking mail read.
Verified workflow completion is separate from untrusted email subject text.
Live command-to-API execution passed in 2.953 seconds; a separate filtered Qwen
proposal passed. Final regression ran 1,291 tests successfully; the live repository
isolation test class was skipped because Docker's Linux engine was unavailable.
Configured readiness is `ready`.
Say `find my unread emails`, `show unread emails`, or `list my unread Gmail emails`.
Additional filters still use Qwen planning. Credentials remain DPAPI encrypted;
the reviewed adapter was explicitly reverified with the existing local token.
At that checkpoint, the approved restart reached running/listening with healthy
capture/decoder and action/question/speech workers. The newer deliberate stop and
subsequent command repair are recorded above.
[Usage, fresh checks and limits](docs/gmail-api.md#unread-email-repair--2026-10-09-ist).

**Gmail API (2026-10-09 IST):** Added local Desktop OAuth for message search/read
and draft creation/read/update, preferred over Chrome when connected. Tokens stay
Windows DPAPI encrypted locally; draft writes require approval and readback.
Account consent and live API checks passed: message search/read, draft listing/read,
recipient-free draft creation and hash-checked update/readback. Sending was not exposed
at that stage; it was added on 2026-10-10 (see above).
Adding the selected account as a test user resolved the initial Google 403.
Connected-account regression: 1,291 tests passed; final routing corrections received
78 focused checks. Real Qwen API search and regular dispatch passed. Current utility
revalidation enables 37 local skills; the Chrome
Gmail check was unavailable while Google Cloud was selected. Six API tools are connected.
[Setup, tools and limits](docs/gmail-api.md).

**Gmail Compose flow (2026-10-09 IST):** Added a local Chrome draft adapter for
Compose → optional To → Subject/body in the existing logged-in profile, without
moving the user's mouse or requiring a project folder. It preserves older minimized
drafts and blocks sending. The user loaded the adapter; live Compose, subject/body
entry, blank To and delayed readback passed. Actual Qwen selected and dispatched
Gmail inspection successfully. Gmail is now among 38 active local skills (41 passing
contracts, including three inactive mock-only integrations). Nine browser/transport
checks passed; the final regression passed 1,279 tests in 262.679 seconds.
[One-time setup and validation limits](docs/gmail-drafts.md).

**Planner/email repair (2026-10-09 IST):** Native next-step planning no longer
receives conflicting text-plan JSON instructions. Ordinary tasks receive one
bounded inference-only format correction; actions are never replayed. Gmail
intent selects the form guidance, and an unavailable Gmail adapter causes an
explicit readiness question before speculative inference. The reported request
and a real Qwen Chrome-opening proposal passed their checks. Gmail draft execution
now has live verification. Jarvis was intentionally stopped at that checkpoint;
the approved restart after the unread-email repair is recorded above.
[Evidence and remaining setup](docs/utility-skills.md#planner-and-email-repair--2026-10-09-ist).

**Curated utility skills (2026-10-09 IST):** All 42 supplied skill contracts have
individual fixture trials. Currently 41 contracts pass (38 actual local skills and
three mock-only messaging adapters, which remain inactive). The owned desktop
button test passed using Jarvis's cursor without moving the user's mouse. Gmail
draft completion passed; Windows symlink privilege remains unresolved and disabled.
All 1,265 regression tests and four actual Qwen skill-selection tasks passed.
The earlier skill rollout restarted with healthy microphone/workers and current recovery snapshots.
Passing skills connect to the normal Qwen catalogue/dispatcher through typed
arguments, source-bound validation, scoped files and runtime approvals. Optional
Slack/GitHub/Twilio results are mock-service contracts, not live sends. Credentials
and monitor images remain local. [Setup, every skill, when/how guidance, actual
results and pending live checks](docs/utility-skills.md).

**Repository skill engine (2026-10-09 IST):** Jarvis now analyzes explicitly named
Python repositories as data, persists versioned capability knowledge, and exposes
approved skills to its existing Qwen planner and command tools. Execution requires
the reviewed local Docker Linux runtime, isolated smoke validation, activation
approval and approval for each call. Three real repositories passed actual routing,
Qwen selection, isolated execution, reload and disable trials. Say `learn repository
https://github.com/mahmoud/boltons`, `show learned repository skills`, or
`disable all repository skills`. [Setup, exact commands, security, implementation
report and dated validation](docs/repository-skills.md).

**Final engine verification:** **1,241 regression tests passed in 227.003 seconds**,
including ten actual container security checks. Configured readiness and hidden UI
startup/shutdown passed. After the supervised app restart, all three persisted
approved trial skills were discoverable and returned their original results through
fresh Jarvis Actions/ToolRegistry dispatch, without relearning or reactivation.

**Native coding validation (2026-10-09 IST):** **1,212 regression tests passed**
in 206.667 seconds; configured service readiness is `ready`. Actual three-worker
HTML/CSS/JavaScript generation passed LocalGithub assembly, combined checks and
an independent Chrome counter oracle across five viewport widths. That live
trial took 943.766 seconds; newer component completion is regression-checked,
without a new live timing claim. Native vision also passed an owned synthetic
image check. The command/diff console has an actual checked capture, and the
supplied command reference has 24 usage guides with 58 program profiles
(22 locally available; availability is distinct from functional validation).
Firecrawl remains optional and unconfigured by user choice.
After the final checks, Jarvis restarted with healthy microphone capture/decoding
and action, question and speech workers. All 153 Python recovery snapshots match
the current code, and the saved configuration uses the native backend.
[Usage, actual screenshot, dated checks and limits](docs/native-coding.md).

**Native coding update (2026-10-08 IST):** The default is now Jarvis's own local
Qwen3.5 9B tool loop, with checked source edits, fixed tests, separate LocalGithub
worktrees, combined verification and an expandable command/diff workspace.
Codex CLI/account integration is optional legacy configuration and is not used
by native coding. The supplied six-page command reference is packaged as data
with 24 when/how guides and installed-program discovery. Actual single- and
two-worker native Python trials passed unchanged independent tests and assembly;
the 1,208-test regression checkpoint passed. Website and final refined-tool
verification are recorded in the [native guide](docs/native-coding.md), with
failures and missing toolchains distinguished from successful checks.

**Python workload repair (2026-10-08 IST):** Unnamed single Python-script requests
now retain Python and plan one implementation with its executable behavioral
tests in one worker. This fixes the reported empty `check_indices` failure and
rejects accidental HTML/CSS/JavaScript plans before writes. Every worker schema
requires nonempty check indices, with diagnostics for all invalid assignments.
Also repaired the Codex completion/GPU-cleanup handoff and compact Python worker
context. **1,198 regression tests passed**; configured readiness is `ready`.
An actual local-Codex continuation passed six generated tests and an independent
visible-circle launch in an isolated fixture. Earlier failures/time limits remain
recorded; this is not a latency guarantee. Jarvis restarted with live microphone
capture/decoding, healthy foreground workers and current recovery snapshots.
The original `TestCodes` folder and failed checkpoint were not replayed or changed.
[Behavior, verification and limits](docs/codex-workloads.md).

**Earlier GPU allocation checkpoint (2026-10-08 IST):** Planning, execution, questions and
local Codex now use a process-shared priority queue with speech memory reserved.
The primary 9B model uses partial GPU offload; local Codex uses nine GPU layers.
Live inference beside Whisper observed a 3,392 MiB peak on the 4,096 MiB GPU.
Small helpers default to CPU after a slower cold GPU sample. Specialist speech
and control runtimes retain their existing devices; hosted Codex is unchanged.
**1,192 regression tests passed**, configured readiness is `ready`, and actual
local Codex creation/editing plus synthetic GPU vision passed. Jarvis restarted
with healthy microphone/workers, GPU health metadata and current recovery snapshots.
[Configuration, measured timings, ownership and validation limits](docs/gpu-priority.md).

**Earlier cursor checkpoint (2026-10-08 IST):** Jarvis now displays its own temporary
cyan **J** cursor for supported native/browser activations, leaving the system
mouse untouched. Actual-worker checks passed on YouTube, GitHub, Spotify web and
desktop, Windows Camera and owned fixtures. Camera's original mode was restored.
Physical-only mouse gestures refuse; app focus and keyboard remain shared.
**1,165 Jarvis regression tests passed**; configured readiness is `ready`.
Jarvis restarted with live microphone capture/decoding and all foreground workers;
both cursor modules have current recovery snapshots.
[Implementation, actual screenshot, dated evidence and limits](docs/independent-cursor.md).

![Actual headful Chrome render of the owned Jarvis cursor fixture before activation](artifacts/media/independent-cursor-browser-fixture.png)

This is the verification fixture, not the production notch or a user account.

**Earlier production repair checkpoint (2026-10-08 IST):** All **1,156 Jarvis regression tests and 31 LocalGithub tests passed**; configured local-service readiness reports `ready`. The actual Codex/local Qwen full-stack repair passed its real homepage, seven browser interactions, six API requests, seven generated unit tests and an independent persistence check. Spotify transport passed on October 7. Resumed Computer Use checks passed against actual Jarvis controls in the isolated fixture. Fixed cold coding startup, protected interfaces, unchanged-save handling, checkpoint sharing locks, media helper cleanup and game Pause focus. Jarvis restarted normally; microphone capture/decoding and all foreground workers are alive with fresh audio. Optional account/service setup and untested native frameworks remain explicit. [Evidence and limits](docs/production-validation.md).

![Actual Computer Use screenshot of the isolated Jarvis widget fixture after Pause; microphone, inference, media polling and memory writes disabled](artifacts/media/production-game-pause-fixture.jpg)

This decorated, opaque verification window uses the actual Jarvis controls. It is a fixture screenshot, not a capture of the production notch or a live microphone session.

**Production validation and repairs (2026-10-07 IST):** Fixed REST Countries v5 search/response handling, removed private URL details from provider receipts, added ignored local key storage and corrected rate-limit backoff. All 55 realtime and three runtime-health tests passed. With Whisper resident, measured partial GPU question inference improved first/repeated arithmetic replies from 17.6/4.3 to 9.0/2.8 seconds. The operator confirmed the restarted live spoken reply was faster and audible. All nine existing browser fixtures passed fresh interaction/layout checks. [Results, local credential setup and remaining production checks](docs/production-validation.md).

**System audit and repairs (2026-10-07 IST):** Inventoried authored source, tools, skills and related installations; repaired configured-service readiness, partial/new-format model-cache restoration, hidden UI isolation, screen-capture owner identity, inseparable Codex test ownership and conflicting Harness plan/clarification output. The missing context-selection model is installed and the launcher reports `ready`. **1,132 Jarvis regression tests and 31 LocalGithub tests passed**; actual local Codex creation/editing passed with unchanged CLI behavior. Removed only the disconnected old orb renderer and its generated copies. Third-party API/configuration and model-generation limits remain explicit. [Architecture, cleanup decisions, fresh checks and remaining gaps](docs/system-audit.md).

**Green public data and serious alerts (2026-10-07 IST):** Added **82 adapters**
matching only the green APIs in the supplied screenshots. Questions use relevant
timestamped observations; tasks receive cached evidence and can fetch exact data
through `realtime_query`. A location-aware idle monitor checks seven hazard feeds,
notifies only for fresh serious evidence and suppresses duplicates. Approximate
IP location refreshes hourly; explicit coordinates and location controls are
available. Unknown/stale location does not become a guessed home city.
The separate Qwen2.5 0.5B reader uses one CPU thread, 1,024-token context,
short schema-bound assessments and `keep_alive=0`. It defers for active tasks,
loaded foreground models, low RAM or high CPU. Temporary memory/CPU use is
unavoidable; this is best-effort resource control, not zero-cost inference.
The small model and lightweight WebSocket dependency are installed/declared;
setup, launchers and silent recovery remain compatible.
**Live probes: 68 successful providers, 8 unavailable/rate-limited, 6 requiring
setup.** Five need self-hosted services/regional GBFS feeds; REST Countries
retired keyless access and now needs a free-plan key. No accounts or heavy
servers were created. The actual idle reader passed with live weather/NOAA
excerpts, and a subsequent model-status read showed no resident model.
Restart through Stop/Start Jarvis. [Configuration, full inventory, limits and test results](docs/realtime-data.md).
Final regression: **1,117 tests passed**, including **50 focused realtime tests**;
launcher readiness is `ready`. A live-data foreground question also passed.

**LocalGithub workload orchestration (2026-10-06–07 IST):** Coding, app and website
requests now receive a checked workload/interface plan. Suitable work runs in
separate local Codex sessions with exact file ownership, per-worker tests and
dependency ordering. LocalGithub's local Git layer combines tested commits;
combined checks gate application to the selected project. Two workers share the
existing local 9B model; speed gains are not guaranteed. The hosted Gitea review
queue is not bypassed or used for automatic assembly. No new dependencies or
LocalGithub source changes. Restart via Stop/Start Jarvis.
[Configuration, checkpoints, verification and limits](docs/codex-workloads.md).
New plain websites use three source workers and real Chrome component checks;
markup precedes concurrent CSS/JavaScript work. Jarvis preserves exact selectors,
passes predecessor markup to workers and reports text/input assertion mismatches.
Website workers receive compact task/guidance/tool context. Chrome checks five
widths from 320px to 1920px, alongside real interactions and advancing animation.
Repairs address all observed failures in a complete source write; empty feature
cards fail, and tested peer CSS can inform JavaScript state bindings.
The configured repair budget is three, based on the completed live trial;
the normal overall coding deadline remains 30 minutes.
Regression/readiness checks on 2026-10-07 passed 1,067 tests plus 53 focused tests
and reported `ready`;
[the receipt](artifacts/reports/codex-workload-regression-check.json) distinguishes these
from the live model-generated website trial. The animated Orbit Studio website
completed in 15 minutes 50 seconds with three tested worker commits and successful
LocalGithub assembly. Eleven browser checks and 260 additional click/keyboard
interactions passed across five widths, including actual page color changes.
Post-promotion hashes confirmed unchanged source. Only Jarvis/Codex authored or
repaired the website. [Live results and screenshots](docs/codex-workloads.md#verification-2026-10-07-ist).

![Actual Chrome desktop render after a theme toggle; Jarvis/Codex-generated Orbit Studio test website](artifacts/media/codex-workload-theme.png)

**Codex verification and repair (2026-10-05–06):** Coding tasks now declare
expected files, purposes and executable checks before writes. Jarvis checks
missing/empty/stub files and local UI resources, executes supported runtime and
browser checks, then supplies failures and fresh source attachments to up to
two Codex repair turns. Requested frontend/backend projects require both layers
and actual UI/API interaction checks. Fixed rejections caused by applying desktop
GUI requirements to declared web servers and directly executed test files. Interrupted or uncertain saves stop without
replay. The actual local Python create/edit fixture passed automatic tests;
**1,042 regression tests passed; launcher readiness is `ready`.** All application
creation/editing remains with Codex/local Qwen. No new dependency or paid model
API. Restart via Stop/Start Jarvis.
That October 5–6 full-stack trial was unverified: checks caught a generated recursive
backend factory and a test file running zero tests. Those historical failures are retained; the October 8 resumed repair passed the
checks linked above. Successful arbitrary generation is not guaranteed.
[Verification, repair behavior and limits](docs/codex-code-local.md).

**Coding destination and reply repair (2026-10-05 IST):** `create an app to
monitor my health in folder TestCodes folder` now resolves `TestCodes` rather
than treating the app's purpose as its destination. A confirmed folder reply
resumes the original request once through the configured **Codex/local Qwen**
executor, with island and spoken completion. Invalid answers retain the question;
expiry, cancellation and uncertain-write guards remain active. Handoff tests
use a recording Codex boundary and create no application source. The existing
catalog resolves the reported request to its real `TestCodes` folder. **1,021
regression tests passed; launcher readiness is `ready`.** Restart Jarvis
through Stop/Start to load the fix.
[Folder syntax, resumption and verification scope](docs/codex-code-local.md).

**Ollama model visibility repair (2026-10-05 IST):** The `/api/show` 404 came
from a WSL server using a different model store from the existing Windows cache.
Restored the configured Qwen models from cached files without registry downloads,
preserving Gemma and the shared server. Setup now checks cache roots, restores
base models before local aliases, and never pulls Jarvis alias names. Coding
preflight repairs a missing alias or explains unavailable weights before editing
files. Actual local script creation/edit and generated counter-app browser
interaction passed after a Qwen repair of moving controls; **1,013 regression tests passed
and launcher readiness is `ready`**. Restart Jarvis once to load the recovery
changes. [Setup and troubleshooting](docs/codex-code-local.md).

**Local Codex coding (2026-10-05 IST):** Jarvis now uses the installed Codex
CLI with **local Qwen3.5 9B** for coding tasks, replacing the configured Claude
Code executor. Explicit folder/file paths take priority, followed by the fresh
File Explorer folder and remembered scope. Visible text, file activity and
results stream into the existing island. Checked saves preserve originals;
Stop closes only the owned process tree. Each task uses isolated Codex settings,
without changing the desktop chat model or requiring paid model API calls.
Actual local creation/edit and a Python run passed; **1,006 regression tests
passed and launcher readiness is `ready`**. The island replay passed 90 updates
without widget rebuilds or completion collapse. All **nine animated UI fixtures**
passed actual browser checks after reviewed corrections; React fixtures also
passed strict type checks/builds. Native C/C++/C#/Java compilation remains pending.
[Setup, behavior and limits](docs/codex-code-local.md),
[languages and fixture results](docs/multilingual-coding.md).
Restart through Stop/Start Jarvis to load the new backend.

![Rendered Jarvis island with authored Codex activity; not a desktop screenshot or live inference](artifacts/media/codex-code-island-preview.png)

**Windows command reference (2026-10-04):** Imported all **493 commands / 21
categories** from the supplied ZIP with pinned recipes, explicit parameter binding
and direct matching for app launches, file/host requests and exact command names.
The island reports execution and retains approvals; recipe voice requests wait
for the final transcript. Python input checks the current
app/window; DOM commands use the owned browser; Office recipes use one owned batch.
Configured launchers preserve typing focus. Added free PyAutoGUI/OpenCV dependencies.
All IDs are available through command search and explicit requests; optional apps,
permissions and exact targets remain necessary. Owned file/DOM/native fixtures passed; **980 regression tests passed** and
launcher readiness is `ready`. Verification results are in the
[execution guide](docs/windows-commands.md). Restart via Stop/Start Jarvis.

**Longer plan execution (2026-10-04):** The executor now permits twenty actions
by default, retains the full completion list and checks the entire goal before
reporting success. Stop and uncertain actions still block further execution.
Ten actual Qwen-generated file plans spanning **2–20 actions** passed after fixes
and retests; ten authored plans also passed. A separate owned
Win32 fixture verified **20 real button activations in 64.953 s**. These checks
use deterministic decision/verification oracles; the native test uses an authored
plan. The twenty-step recorded Qwen proposal was retested in a fresh fixture.
No new dependency or paid API. Restart via Stop/Start
Jarvis. **960 regression tests passed; launcher readiness is `ready`.**
[Configuration, live records and scope](docs/plan-execution.md).

**Existing-script GUI edits (2026-10-04):** `add UI to calculator.py` sends the
exact current source and requested change straight to the configured local Qwen
coder. GUI requests reject console-only and placeholder output before saving;
ambiguous follow-up targets require a filename. Locked streaming sidecars switch
to island-only previews, and active generation renews an idle timeout within a
separate total limit. Original-source checks and coding reviews protect edits.
An actual Qwen fixture completed in **189.5 s**, streamed **421** updates, and
its generated Tkinter window passed six arithmetic/error checks through real
widget callbacks. These results cover an authored fixture, not arbitrary user
scripts. **940 regression tests passed; launcher readiness is `ready`.**
No new dependency or paid API. Restart through Stop/Start Jarvis.
[Behavior, limits and verification](docs/python-gui-edits.md).

**Session memory, context selector and live app awareness (2026-10-04):**
Completed questions/answers and managed task replies now extend durable paired
sessions. Follow-ups prefer the current session, then saved conversations; ambiguous
matches show dated context choices in the island. Clicking a choice resumes the
original question once, and dropdown/input focus is preserved. A separate free
local **Qwen3.5 0.8B** thread selects distinctive context matches and supplies
ready output to the main planner. It does not rewrite commands or execute tasks.
The production background fixture selected context in **1.437 s**; cold/busy
requests retain manual choices within the three-second budget.

The planner also receives checked current/recent app-window status and observed
accessible buttons/controls. Supported direct commands use coded adapters with
fresh target validation. An owned native fixture confirmed two clicks, changed
labels and blocked closed-window/stale-target input with **zero model calls**.
Saved memory selection and its next follow-up passed actual local answer checks.
Full text is stored locally; prompts use bounded excerpts. No paid API or new
Python dependency. **929 regression tests passed; launcher readiness is `ready`.**
Restart through the normal Stop/Start Jarvis launchers.
[Behavior, configuration, model comparison, app limitations and dated regression/readiness records](docs/session-context.md).

![Rendered actual island memory-choice widgets with authored examples; not a desktop screenshot or private memory](artifacts/media/session-memory-choices-preview.png)

**Conservative voice cleanup (2026-10-04):** A separate local **Qwen2.5 0.5B**
selector now cleans eligible final speech commands. It chooses only between the
original and a checked surface edit; it cannot add actions or invent targets.
Dictation, literal payloads, numbers, negation and committed actions are preserved.
Clear commands bypass inference; timeout falls back unchanged within a two-second
default budget. This free 398 MB model was fastest among three tested options:
**0.265 s warm median**, with all 16 constrained text fixtures matched. Live
production cleanup also matched 16/16 fixtures (seven model calls, nine bypasses).
This is not a real-microphone accuracy guarantee. **886 regression tests passed;
launcher readiness is `ready`.** No new Python dependencies.
Restart through Stop/Start Jarvis. [Research, exact edit scope, setup and separate verification records](docs/command-cleanup.md).

**Smooth long-output growth (2026-10-04):** Streaming updates keep the answer
view mounted and append text in place. The same island grows to the screen limit,
then scrolls; token pauses and draft replacement do not collapse it. Unchanged
placement/rendering is skipped, and scrolling back preserves your reading line.
A 160-update UI replay recorded **zero view unmounts and zero layout rebuilds**;
**864 tests passed; launcher readiness is `ready`**. Restart through the normal
Stop/Start launchers. [Rendered growth stages, behavior and verification scope](docs/smooth-island-growth.md).

![Rendered long-output growth at a common scale — authored fixture, not live model output or a desktop screenshot](artifacts/media/island-growth-preview.png)

**Streaming island answers (2026-10-04):** Ollama question output now appears
inside the existing island as it is generated. Actual output resets the silence
timeout (300 seconds HTTP / 330 seconds worker); the total ceiling is 30 minutes.
Stop cancels the owned request, and interrupted previews remain marked incomplete.
Code examples stream plain source; normal questions keep web-verification logic.
The C++ game question delivered first text in **13.3 seconds**, streamed **7,984
characters**, and finished in **6 minutes 47 seconds** without the old deadline
abort. The generated code was not compiled or run. **859 tests passed; launcher
readiness is `ready`.**
No new dependencies. [Configuration, rendered preview and separate live/regression evidence](docs/streaming-answers.md).
Restart Jarvis through its normal Stop/Start launchers to load this change.

![Rendered island with authored partial code — not a desktop screenshot or live answer](artifacts/media/answer-stream-preview.png)

**Ollama output/timeout repair (2026-10-04):** Restored the missing `qwen3.5:9b`
tag from identical installed weights. CPU planning now has a bounded 300-second
HTTP allowance and 330-second worker allowance. Fresh checks returned text in
8.95 seconds, warm chat in 0.35 seconds and a native proposal in 21.8 seconds;
the proposal was not executed. Logs also showed server bind conflicts, GPU
discovery timeouts and cancelled loads. **843 regression tests passed; launcher
readiness is `ready`.** These checks do not verify the original long C++ request.
[Diagnosis, changes, measured limits and troubleshooting](docs/ollama-output-timeouts.md).
Restart Jarvis through its normal launchers.

**Ordered native execution (2026-10-04):** Compatible desktop inputs now use
reviewed UFO → Windows-MCP → CUA → Open Computer Use → Agent-S primitives in that
order. Exact supported desktop/file task grammar skips Qwen; other requests keep
the existing direct workflows and planner. Provider fallback occurs before input;
uncertain actions pause without replay. No new dependencies or paid APIs.
**839 regression tests passed; launcher readiness is `ready`.** A real owned
Windows fixture completed fill → checkbox selection through the persistent worker
in **0.453 seconds with zero model calls**. This does not establish arbitrary task
speed. All five repos are indexed (5,700 source files); selected compatible actions
are adapted, not every framework function activated.
[Commands, exact integration scope, source inventory, licenses and evidence](docs/execution-providers.md).
Restart Jarvis through the normal Stop/Start launchers.

**One glass notch (2026-10-04):** Jarvis now expands from the screen edge into one
surface for typing, scrollable answers/code, tasks, approvals, music, games,
history, Prepared, settings and the command console. Rounded glass buttons and
inputs share highlights, borders and hover/focus states. Curved shoulders and
interruptible 340 ms motion follow the supplied VoiceOS references. **•••** opens
features inside the notch; **Esc** collapses it. No new dependencies or paid APIs.
**809 regression tests passed; launcher readiness is `ready`.**
[Controls, Firecrawl research, architecture and verification limits](docs/voiceos-notch.md).
Restart Jarvis once through the normal Stop/Start launchers.

![Rendered glass notch widgets with sample content — not desktop screenshots or live task results](artifacts/media/jarvis-notch-preview.png)

**Qwen3.5:9b primary model (2026-10-04):** The verified 6.6 GB Ollama download now
supplies questions, vision, planning, decisions and coding. General one-step
planning uses native function calls with checked execution and verified result
feedback. All **82 registered tools** have native schemas; relevant configured
tools are discovered by intent. App/integration discovery and three Firecrawl
public-read adapters are added. Firecrawl needs `JARVIS_FIRECRAWL_KEY`; account
services/MCP need their own authorization. Codex plugin logins are not transferred.
**803 regression tests and launcher readiness passed.** Real native feedback,
vision, coding and runtime-catalog fixtures passed in **31–115 seconds** on CPU, so the five-second
target remains unestablished. [Setup, complete tool categories, plugin scope,
primary sources and measured evidence](docs/qwen35-9b.md). Restart Jarvis once.

**One-step planning and repeat navigation (2026-10-03):** General desktop planning
now asks for one action from a fresh screenshot, the aim and verified step history.
A background worker prepares the next prompt during execution; a two-frame ring
is cleared on task exit. Verified native navigation recipes can skip model calls
for the same request with fresh control and outcome checks. A real local-model
fixture returned the correct action in **34.125 seconds**, so universal five-second
execution is not established. [Behavior, repeat scope, configuration, authored
fixture and dated verification](docs/step-planning.md). Restart Jarvis once.

Verification on **2026-10-03**: **785 regression tests passed**, including 27
step-planning checks; launcher readiness reported `ready` with `qwen-next-step`.
[Dated regression/readiness record](artifacts/reports/step-planning-regression-check.json).

**Idle-time anticipation (2026-10-03):** A separate bounded component uses explicit
research requests and eligible sustained browser/editor titles to prepare source
outlines or suggest review checklists. The island's **Prepared** view shows evidence,
expiry and Accept/Dismiss controls. Public research from inferred browser topics
requires acceptance or the explicit **always prepare public research** command.
Feedback reduces unwanted proposals; Stop, cancellation, context changes and expiry
invalidate work. Optional local synthesis is off by default. [Commands, compute
limits, rendered sample preview, research attribution and verification
scope](docs/anticipation.md). Restart Jarvis once. A generic live query retrieved
three public sources; anticipation usefulness has not been benchmarked.

Verification on **2026-10-03**: **758 regression tests passed**, including 39
anticipation checks; launcher readiness reported `ready` with no missing components.
[Dated regression/readiness record](artifacts/reports/anticipation-regression-check.json).

![Rendered Prepared view with sample activity and sources — not a desktop screenshot or live research result](artifacts/media/anticipation-preview.png)

**Web/app development (2026-10-02):** Jarvis now retrieves its own framework-aware guides, writes a design brief, builds complete projects in three-file batches, runs reviewed Node type/build tooling, inspects owned desktop/mobile previews and retains independently verified framework lessons. Vite, Next.js, Electron renderer and Expo web adapters passed real build/browser checks; native packaging/device behavior needs separate platform verification. DeepSeek Harness can supply scoped development plans; code generation and outcome checking remain Jarvis-owned. [Commands, setup, actual screenshots, sources and measured limits](docs/web-app-development.md). [Sequential acceptance evidence](artifacts/reports/development-acceptance-check.json) · [real local model probe](artifacts/reports/development-model-check.json) · [regression/readiness evidence](artifacts/reports/development-regression-check.json). **719 regression tests passed; launcher readiness is `ready`.** Restart once using the normal Stop/Start launchers.

![Actual Chrome screenshot of the authored development acceptance dashboard; not an autonomous model-generated project](artifacts/media/development-previews/vite-desktop.png)


**Interactive island (2026-10-02):** Task/answer previews, current file/activity and source-writing progress now share the island with bound clickable choices, inline approvals, Spotify artwork/player cards and five local games: Flappy, Snake, 2048, Tic Tac Toe and Memory. Changing views or playing games preserves background coding; a local focus timer and recorded goal/last-task shortcuts are included. The surface is slightly translucent. A real Windows Spotify read returned metadata and artwork; live playback, candidate selection and voice still need an interactive trial. [Behavior, commands, sources and verification](docs/interactive-island.md). Restart once through the normal Stop/Start launchers.

![Rendered interactive island widgets with sample content — not desktop screenshots or live Spotify results](artifacts/media/island-desk-preview.png)

Interactive-island verification on 2026-10-02: **693 regression tests passed**, hidden UI startup/shutdown and temporary background-file checks passed, and launcher readiness reported `ready`. [Dated regression/readiness record](artifacts/reports/island-regression-check.json). These checks do not establish live voice or Spotify playback reliability.

**Visual interaction and Save checks (2026-10-02):** Native Windows controls retain priority; missing named controls can use local Qwen3-VL, a reviewed Apache-2.0 UI-TARS parser and a guarded one-shot Windows input worker. Each action requires fresh observation and outcome checking. The new explicit application `save_file` workflow reads back the requested filename, gates exact-file overwrites and checks stable file bytes/SHA-256 on disk. [Integration, evaluated Agent S/UI-TARS sources, commands, configuration and limitations](docs/visual-interaction.md). Live local vision passed on a rendered fixture; interactive Windows input remains unverified because this execution session exposed no foreground window. **667 regression tests and launcher readiness passed; four real local-model checks passed on a synthetic fixture.** Restart Jarvis once.

**Experience learning (2026-10-02):** A local Memento-inspired case bank now records successful, failed and uncertain tasks, initial app/UI/tool/project conditions, reported failure causes, checked outcomes and verified recovery methods. Relevant positive and negative cases reach native/Hermes/DeepSeek Harness planning and coding; changed/missing conditions require fresh inspection before adapting a procedure. Close-window observations distinguish hidden/destroyed/remaining windows and do not claim process exit. No new dependencies or model-weight training. [How it works, configuration, privacy and verification](docs/experience-learning.md). Restart Jarvis once; the configured vault receives `Jarvis Experiences` notes during normal use. **618 regression tests passed; launcher readiness reported `ready` with `deepseek-harness`.** [Isolated persistence/retrieval and one real Harness/Qwen proposal](artifacts/reports/experience-learning-check.json) passed; the unexecuted synthetic-state model turn took **79.344 seconds**, which does not establish a live task-success or quality improvement.

**DeepSeek Harness (2026-10-02):** The official Python SDK and matching Windows runtime (`0.1.5rc1`) now run general planning/replanning with local Qwen through an owned loopback gateway. Jarvis retains action execution, approvals and independent verification. Read-only research accepts `--backend harness`; direct workflows and streaming coding retain their existing routes. [How the harness works, setup, integration scope and measured limits](docs/deepseek-harness.md). **592 regression tests passed; launcher readiness reported `ready` with `deepseek-harness`.** Three real Qwen turns passed with synthetic observations, without desktop execution. Restart Jarvis to load the selected planner.

**Sharp UI and commands during speech (2026-10-01):** Native DPI rendering and antialiased larger text sharpen the island. Its header displays live task/file phases and streamed character counts beside the status. Microphone capture stays active during speech; addressed “Jarvis …” commands interrupt replies with text-based self-echo filtering. General questions can run while coding continues. [Behavior, Full HD rendered preview and verification limits](docs/hd-display-and-voice-input.md).

![Full HD rendered island preview — not a desktop screenshot](artifacts/media/jarvis-hd-status-preview.png)

Verification: **578 tests passed**, hidden UI startup/shutdown and preview export passed, and launcher readiness reported `ready`. Live overlapping microphone speech still needs a spoken trial; the echo filter is textual rather than acoustic cancellation.

**Runtime memory connections (2026-10-01):** Task intent now connects relevant tools, skill guidance and validated remembered program paths to planning and coding. Discovery includes prerequisite reads and respects task scope; personal Obsidian guides reload during runtime use. The real vault received the linked capability catalogue with **70 tools, nine local guides and 210 Hermes references**. Seven configured routing checks passed; 566 regression tests passed. [How selection works, personal guides and verification limits](docs/runtime-capabilities.md).

**Streaming coding (2026-10-01):** Qwen3-Coder now streams source into new script drafts as it arrives; existing edits use a visible sibling draft and commit after validation. Clear single-Python-script requests skip separate plan inference. A bounded 900-second coding deadline replaces the failing 120/150-second coding waits, with cancellation and guarded resume. A real alarm script was generated with 154 checked draft updates in **164.158 s**, first nonempty code at **136.342 s**; an isolated edit completed with 292 checked updates in **229.482 s**. Loading/prompt processing remains slow on this CPU. **555 regression tests and launcher readiness passed.** [Implementation, real source, verification and limits](docs/streaming-coding.md).

**Folder navigation and personal skills (2026-10-01):** Spoken folder requests now preserve drive constraints, search live drive-root folders and indexed deeper names, tolerate bounded spelling differences, and remember Jarvis folder opens in local runtime/Obsidian notes. Equal names can use a higher usage count; unclear ties still ask. Personal workflow guides can be created with `scripts/skills/add_skill.py`, saved under `custom-skills`, copied to Obsidian and retrieved across tasks/coding. Live evidence: five Ollama phrases resolved correctly, with one independently confirmed Explorer open in **0.881 s**, excluding voice. **547 regression tests passed; launcher readiness passed.** [Folder lookup and limits](docs/folder-navigation.md) · [Add custom skills](docs/skills-and-learning.md#adding-personal-skills).

**Hermes skills and comparison (2026-10-01):** The existing Nous Research Hermes installation now supplies an indexed library of **210 upstream reference skills** (58 bundled, 152 optional) and supporting files in Obsidian, alongside nine Jarvis guides. 168 declare Windows support; additional requirements remain explicit. A matched live comparison exposed model-planner timeouts and browser/playback failures; the later direct follow-up verified 3/3 tasks in **4.313 / 0.250 / 3.266 seconds**, excluding voice. Direct workflows are selected first, with native Qwen as the general fallback; Hermes remains installed as an optional planner and its skills remain connected. Both model routes failed the latest complete-goal check. All 535 regression tests and launcher readiness passed. Original failures are retained. [Catalogue, integration, comparison method and limitations](docs/hermes-skills-and-comparison.md).

**Automation upgrade (2026-10-01):** A warm UIA worker, direct verified workflows and an owned Playwright Chrome session reduce repeated startup/model calls and redundant option prompts. Live search → first YouTube video → verified playback took **5.681 s cold / 2.918 s warm**; native Spotify search → matched song → verified playback took **6.656 s**, all excluding speech input/output. Both workflows used zero model calls. Nine skill guides and the 69-tool/41-operation catalogue are synchronized to Obsidian. All 523 regression tests and launcher readiness passed. Restart Jarvis once. [Behavior, setup, sources, live evidence and limits](docs/automation-upgrade.md).

**Initial skills and execution learning (2026-10-01, before the automation upgrade):** Eight workflow guides are installed in the configured Obsidian vault. Verified tasks update reusable procedures; matching guidance is supplied to desktop/media planning and project coding. Exact recent navigation proposals can skip initial planning while retaining fresh action checks. Failed or partial attempts are logged and never promoted. Verification: 501 regression tests and launcher readiness passed; full desktop task latency remains unmeasured. [Usage, research, privacy, verification and speed limits](docs/skills-and-learning.md).

**Initial YouTube and Spotify controls (2026-10-01, before interactive desktop checks):** “Play first video” now preserves its ordinal and avoids a redundant choice. “Open Spotify” prefers its installed Windows app. Media searches use the active service, with direct player, seek, volume, captions and Spotify library/queue commands registered for tasks and Obsidian memory. Verification: 489 regression tests passed and launcher readiness passed; live playback remains unverified because the execution desktop exposed no visible windows. [Commands, verification and limits](docs/media-controls.md).

**Free natural voice and model-repair fix (2026-10-01):** English speech now uses the user-selected local Kokoro Heart voice, with a warm worker and continuous reply playback. The repeated configured-model warning came from expecting `qwen3-coder:30b` while the installed 30.5B coder is named `Qwen3-Coder:latest`; Jarvis now uses that installed name. Recovery distinguishes pending work from failure. Verification on 2026-10-01: 462 regression tests passed and launcher readiness passed. Live model availability passed, and two warm short voice replies synthesized in 2.359 and 2.000 seconds, excluding playback and answer generation. [Voice preview, setup, costs, timing limits and troubleshooting](docs/natural-voice-and-model-repair.md).

**2026-10-01 Hermes regression/readiness:** All 449 tests passed and launcher readiness reported `ready` with `planning_backend: hermes`. These checks cover integration guards and provider shutdown, not live desktop task completion. [Verification details](docs/hermes-agent.md#verification-and-limits).

**Hermes Agent integration (2026-10-01):** The free MIT Hermes Agent is installed in an isolated Python 3.14 runtime and enabled for model-based task planning/replanning with local Qwen. It receives relevant Obsidian memory and the current tool catalogue. Jarvis retains action execution, approvals and independent verification. The native Ollama adapter handles this PC's raw Qwen template. Live inference checks passed with synthetic observations: 37.09 seconds for planning and 16.75 seconds for replanning; neither proposal was executed. These are not live desktop success or five-second latency benchmarks. [Installation, configuration, attribution and limits](docs/hermes-agent.md).

A local Windows assistant using **English-only Whisper medium.en on NVIDIA CUDA**, wake-word activation, concurrent desktop actions, voice writing with push-to-write, local Qwen planning and vision, a natural Kokoro male English voice and Piper Hindi speech, and a compact animated Dynamic Island. The faster-whisper runtime uses `int8_float16` and was verified on the RTX 3050's 4 GB of VRAM. Core local inference needs no API key and does not upload microphone audio or save microphone recordings. Web tools and optional account services use network requests and may require credentials.

**Documentation updated: 2026-10-04.** The application is in this `app` directory, inside the parent Jarvis repository. All commands below run from this directory unless stated otherwise.

**Actual Qwen weight training:** Downloaded Qwen2.5-Coder-0.5B-Instruct and completed six local CUDA LoRA gradient rounds: 681 training examples, 171 optimizer steps and 1,081,344 trained adapter parameters. Corrective training uses 86 projects, with 14 excluded from updates. The best checkpoint passed 7/14 validation projects versus 1/14 before training; later rounds regressed. Dedicated adapters and full merged weights are saved locally, with exact resume and optional Jarvis Python-coder integration. Fresh evaluation passed 31/100 projects and 1/10 larger cases; a new invoice task passed 0/10 cases. All 391 regression tests and launcher readiness passed. At the time of this 2026-09-27 evaluation, the existing 4B coder remained selected because this candidate was not ready for promotion. [Setup, evidence and limitations](docs/qwen-weight-training.md).

**Additional coding-language training (2026-09-28):** Continued that 0.5B Qwen adapter through two real CUDA LoRA rounds on 16 checked JavaScript and SQLite examples plus four verified Python replay examples per round. Four separate JavaScript/SQL tasks were held out. Mean held-out loss fell from 0.551 to 0.365, but JavaScript did not meet the requested export interface on either held-out task, and both SQL tasks already passed before training. The checkpoint is available for explicit local use; the 4B coder remained selected at the time of this 2026-09-28 evaluation. The new regression suite passed 400 tests and launcher readiness. [Run details and limits](docs/qwen-weight-training.md#additional-javascript-and-sql-training-2026-09-28).

**PC context and Qwen training:** A dedicated PC adapter completed two real gradient rounds (448 examples, 112 optimizer steps). Validation improved from 4/32 to 32/32; fresh model requests passed 11/13, while fresh exact-name lookup passed 12/12 real project/folder checks. The adapter is configured with live-path validation and metadata fallback. Project, folder and indexed-file context refreshes for planning, coding and PC questions; private contents are excluded. [Behavior, training and limits](docs/pc-model-training.md).

**Local Qwen questions (2026-09-28):** General answers, planning, PC questions and screen vision use the configured local Qwen models through Ollama. The optional cloud text provider and its credential setup have been removed; no API key is needed for these paths. The existing web search option still fetches public results when a question needs current information. Configuration is in [config/config.json](config/config.json).

**2026-09-28 regression/readiness check:** 398 automated tests passed and `python -m jarvis.launcher --check` reported ready, with `qwen3.5:4b` as planner and `qwen3-vl:4b` for screen vision. These checks do not constitute a new live end-to-end question or desktop-action test.

## Images and media

![Jarvis Dynamic Island rendered state previews](artifacts/media/jarvis-island-preview.png)

The current UI is a small black island at the top of the screen. It morphs for listening, work, speech and temporary replies; clicking opens compact conversation/input controls with settings hidden on demand. These are rendered previews with sample content, not desktop screenshots. [Dynamic Island behavior, references and verification](docs/dynamic-island.md).

![Rendered compact Jarvis controls](artifacts/media/jarvis-island-controls.png)

![Bundled animated HUD reference artwork](jarvis/assets/jarvis-reference.gif)

This older HUD artwork is retained for provenance and historical previews; the current island does not display its circular logo. It is third-party artwork; see [asset provenance](jarvis/assets/README.md). A [static reference image](artifacts/media/reference-logo.png), [earlier reference UI](integrations/references/jarvis-ui/reference-jarvis-ui.png), and [reference cover](integrations/references/jarvis-ui/reference-jarvis-cover.jpg) are also retained; they are reference material rather than screenshots of the current Jarvis panel.

[Listen to the current male voice](artifacts/media/voice-samples/am_michael60+am_fenrir40.wav) (generated speech from the local Kokoro blend, not a microphone recording; other male voices are in the same folder). The [earlier Heart voice preview](artifacts/media/jarvis-heart-preview.wav) is kept for reference.

## Contents

- [Hermes skills and measured route comparison](docs/hermes-skills-and-comparison.md)
- [Automation upgrade and live checks](docs/automation-upgrade.md)
- [Capabilities](#capabilities-at-a-glance)
- [Setup and launch](#start)
- [Speech recognition settings](#whisper-settings)
- [Voice commands and writing](#talk-while-it-works)
- [Desktop, files, questions, and coding](#desktop-and-files)
- [God's Eye View](#gods-eye-view)
- [Recovery and adaptive planning](#silent-startup-and-recovery)
- [Integrations and toolkits](#integrations-and-toolkits)
- [Everyday runtime questions](#everyday-runtime-questions)
- [Autonomous toolkit use](#autonomous-toolkit-use)
- [Agent runtime and project research](#agent-runtime-and-project-research)
- [Architecture and project layout](#architecture-and-project-layout)
- [Configuration and relocation](#configuration-and-relocation)
- [Troubleshooting](#troubleshooting)
- [Verification](#verification-commands)
- [Current validation and update history](#current-validation-and-update-history)
- [Documentation maintenance and attribution](#documentation-maintenance-and-attribution)

## Capabilities at a glance

| Area | Current behavior |
| --- | --- |
| Voice input | English Whisper on CUDA, wake gating, Silero VAD, overlapping transcription, write commands, push-to-write, and cancellation. |
| Interface | Compact Dynamic Island, smooth state transitions, temporary reply cards, conversation/input controls, and settings on demand. |
| Questions and screen understanding | Direct local greetings/time/date, bounded live weather lookup, local Qwen for broader answers, optional web research, and local screen vision. |
| Desktop and browser | App/site launching, searches, exposed control selection, exact text-field filling, scrolling, supported shortcuts, menus, and dialogs. |
| Files and projects | Scoped file creation/editing, approved deletion, catalog lookup, project discovery, recent-project memory, and Explorer context. |
| Coding | Related-source context, bounded multi-file work, exact replacements, syntax checks, original-byte backups, diffs, atomic per-file writes, readback, verified failure recall, related examples, and learned missing-import checks. |
| Task execution | One observed next action for general desktop planning, overlapping prompt preparation, two transient frames, checked repeat navigation, shared tool registry, independent decisions and verification. |
| Memory | Local Obsidian vault with dated Jarvis interactions and foreground-window intervals, plus durable checkpoints, task summaries, and UI suggestions. |
| Speech output | Natural local Kokoro male English voice (pauses, breaths, pace and emotion) and Piper Hindi voice; one continuous stream with no length limit, answers spoken while written, instant interruption without reloading, and recognition mute during replies. |
| Media and globe | Spotify session controls and on-demand God's Eye View browser console. |
| Tools | 70 registered operations: 16 core, 4 DOM browser tools, 37 earlier toolkit adapters and 13 agent/MCP tools; configuration and runtime approval gates apply. |
| Agent runtime | Hierarchical repository guidance, explicit skills, deferred tools, source maps, Git observations, read batches, events/deny hooks, approved MCP stdio, and headless read-only sessions/research agents. |
| Recovery | Hidden single-instance supervisor, worker/service health checks, startup snapshots, bounded retries, and explicit-stop handling. |
| Anticipation | Separate idle preparation, evidence-bound browser/editor suggestions, scoped research authorization, local feedback, expiring artifacts and Prepared review cards. |

Local models do not make every task reliable. Custom/elevated apps may not expose usable controls; ambiguous targets require clarification. External writes and deletion use the applicable approval flow, and uncertain effects are never automatically replayed.

### Task questions and option replies

A plain file request such as **“open folder Downloads, create a file called JarvisTest .txt there and write hello kunal in it”** uses an exact file plan, preserves the filename/content, and resolves Downloads before launching or writing. It does not require selecting an Explorer folder or enter code generation just because the request mentions a folder. Full existing destination paths can be resolved without a catalog refresh.

When an essential detail is missing, Jarvis displays and speaks a task question, retains the original goal, and waits for an answer for up to three minutes. For a missing destination, reply **“Downloads”** or a full folder path. A short answer continues the paused task rather than becoming a general question; a new explicit command/question replaces it. Stop/cancel clears the question. Verified progress is retained, and an answer cannot replay an action whose result is uncertain.

For an offered file/app, project or UI list, reply **“one,” “the second one,” “option two,”** or the exact displayed name. UI selections still validate the current window and controls. File/app/UI lists expire after 45 seconds; project lists and task questions after three minutes. Invalid numbers preserve the offered choices; expired replies ask you to repeat the request for a fresh list. These flows do not grant deletion, command or account-write approval.

## Hardware and current models

On this PC (Ryzen 7 5800H, 32 GB RAM, RTX 3050 Laptop with 4 GB VRAM), the current configuration uses **Qwen3.5 9B** for planning, decisions, answers, screen vision and **native Jarvis project coding**, and the pinned English **Laya** checkpoint for control ranking. Primary/native Ollama inference uses priority-managed partial GPU offload with speech reservation; the optional legacy local Codex alias uses nine GPU layers. Small helpers and Laya use CPU. Model-backed tasks can still have substantial latency. Whisper **medium.en** uses CUDA `int8_float16`. Kokoro Heart supplies English speech; Piper supplies Hindi speech. Laya's candidate suggestion still needs independent Qwen agreement for ambiguous controls. [GPU policy and limits](docs/gpu-priority.md), [native coding](docs/native-coding.md).

The 2026-09-27 comparison found all three installed vision candidates passed two synthetic field-verification checks each; that limited evidence does not justify switching the stack. Very large models in the supplied screenshots exceed practical local memory; smaller 7–14B alternatives can fit RAM in isolation but need end-to-end evaluation before replacement. [Hardware, model sizes, timings, sources and limitations](docs/MODEL_AUDIT.md), [raw comparison results](artifacts/reports/hardware-model-comparison.json). No model configuration changed.

## Agent runtime and project research

Jarvis now has **69 registered operations**: 16 core tools, 4 DOM browser tools,
37 existing toolkit adapters and 12 agent/MCP operations. Coding tasks read applicable `AGENTS.md`,
explicitly selected `$name` skills and a bounded repository symbol map. Local
plugin bundles can contribute declarative skills. Planning uses deferred toolkit
discovery (`agent_runtime.deferred_tools: true`) with `tool_search`; configured
tools are discoverable without exposing the whole catalog on every request.

New tools inspect source maps and Git status/log/diffs, read repository guidance
and skills, and batch up to four independent local reads. Metadata events and
optional deny hooks record/control tool execution. Trusted stdio MCP servers
require explicit configuration, exact allowlists and visible approval for each
server start/call. These path checks and policies are application controls, not
an OS sandbox.

The headless read-only agent supports resumable/forked JSONL sessions and up to
three separate research agents. From the app directory, run
`python -m jarvis.agent_cli --project . --goal "Map this project"`; Ollama must
already be running. `python -m scripts.verification.verify_agent_runtime` checks a fixture without a
model, and `--live` requests a temporary-project local-model check.

[Setup, usage, MCP/policy examples, research coverage and limits](docs/codex-runtime-integration.md).
No new Python dependencies or UI changes were introduced. Arbitrary JavaScript,
an OS sandbox, write-capable subagents, remote execution and Codex protocol/model
parity remain outside the implemented scope.

## Unified task tools

### Desktop actions

Tasks can fill named accessible text fields, scroll an accessible container one page, press supported shortcuts, expand menus/dropdowns, and choose buttons in active modal dialogs. Each action checks the destination before execution and is followed by observation and verification. Examples:

- `fill Search field with robot tutorials`
- `scroll down`
- `press control plus f`
- `open File menu and select Save as`
- `select Cancel in the dialog`

Text entry replaces a field's value without submitting it. Password fields and read-only fields are excluded. Supported shortcuts include Tab, Shift+Tab, Escape, Ctrl+A/F/L/S/Shift+S/C/V/Z/Y, Alt+Left/Right/F/E, arrow keys, Home/End, PageUp/PageDown, and F5. Use named buttons for confirmation and submission. File deletion continues through the file tool's approval flow. Custom interfaces that do not expose UI Automation patterns may still need manual interaction.

The preferred local models are Qwen3.5-4B for planning/decisions and Qwen3-VL-4B for screen interpretation. These are practical local choices for this PC, not a claim of universal benchmark leadership. If a preferred model is missing, the brain can use installed Qwen3-4B/Qwen2.5-3B for text or Qwen3-VL-2B for vision. Planning logs identify the fallback. Once the preferred model is installed, subsequent requests automatically use it. Set `brain.allow_model_fallback` to false to require configured models exactly. Run `scripts/verification/verify_desktop_planner.py` with `.venv/Scripts/python.exe` to check live model planning and independent field selection without executing desktop actions. Add `--vision-only` to check the vision model on a synthetic form image.

The autonomous planner receives one shared tool catalog from `jarvis/tools.py`. The same catalog defines its action schema and routes execution to file operations, terminal commands, browser actions, or desktop controls. Direct file work uses file tools; website navigation uses browser tools; visible button selection uses a freshly checked desktop control. Terminal execution and file deletion retain visible user approval. Tool routes appear in the activity log, and dispatch evidence is followed by the existing observation and verification loop before another action runs. Existing direct voice commands remain available.

Firecrawl documentation was used to review browser tool boundaries. This local registry uses Jarvis's existing browser and desktop adapters; the Codex Firecrawl connector is not automatically a credential or browser session available to the Jarvis process.

## Obsidian memory

Jarvis writes to the existing Obsidian vault at `D:\Phython Project\Jarvis_Memory\Jarvis_Mem` while the app runs. `Jarvis Brain.md` explains the notes, and `Daily/YYYY-MM-DD.md` contains timestamped short summaries of Jarvis requests, answers, outcomes, and foreground-window intervals. The vault is outside this Git repository. Obsidian is installed at `D:\OBSIDIAN\Obsidian.exe` and is registered as the `obsidian` app in `config/config.json`, so Jarvis can open it by name. The earlier `.jarvis-runtime/obsidian-vault/` was not deleted; new notes go to the selected vault. Set `memory.enabled` to `false` in `config/config.json` to stop new notes, or change `memory.vault` to another local vault. Restart Jarvis after changing these settings.

A user-provided personal profile is stored as `Kunal Vaghani.md` inside the configured vault and linked from `Jarvis Brain.md`. Jarvis reads it for short personalized greetings and supplies it as reference context to local Qwen questions; the model is instructed to use details only when relevant. Historical daily observations are retrieved for matching activity questions. Update the note in Obsidian when location, goals, or family details change; age is calculated from the recorded birth date when asked. The profile contents are outside Git and are not reproduced in this README. Model answers can still be wrong, so current PC facts need fresh checks.

On normal startup Jarvis says “Good morning/afternoon/evening, Kunal sir,” followed by current weather and time in the detected city when a live UTC offset is available; otherwise it says the local PC time. It skips that spoken greeting on an automatic recovery restart. Say or type **“hello,” “how are you,” “time,” “date,”** or **“weather”** for direct answers that bypass Ollama. Current weather uses an approximate public IP location from [ipapi](https://ipapi.co/) and [Open-Meteo](https://open-meteo.com/en/docs) current conditions. If IP location is unavailable, it tries the city in the Obsidian profile (or `weather.fallback_city`); if weather cannot be fetched, Jarvis says so instead of inventing conditions. An IP or VPN can place you in the wrong city. `weather.ip_location: false` disables the IP lookup and uses the saved city. The weather lookup sends your public IP to ipapi and coordinates/city lookup to Open-Meteo; no microphone audio or profile text is sent. Successful current weather is cached for ten minutes and failed lookups for one minute. A cold weather lookup can exceed four seconds or fail; local model answers, speech recognition and voice playback have variable latency. The 2–4 second target applies best to the direct local replies, not every question.

Obsidian Graph view shows links between notes, not whether a background connection is running. `Jarvis Brain.md` now links each `Daily/` note and each daily note links back; new daily notes get these links automatically. The Obsidian window alone does not record PC activity: Jarvis must be running for new observations to be written.

## Everyday runtime questions

The supplied `Jarvis_Everyday_Question_Bank.zip` has 147 intents and 672 sample phrases. Jarvis uses its examples as a coverage guide; it does not load the zip as a table of fixed live answers. The direct question route calculates from the current clock, Obsidian profile, input numbers, random generator or PC telemetry, and fetches short-lived external data when needed. Examples: **“What date is 30 days from now?”**, **“How old am I?”**, **“What is 18 percent of 750?”**, **“Convert 5 kilometers to miles,”** **“How much RAM is free?”**, and **“Flip a coin.”** CPU, RAM, battery and disk readings use `psutil`; GPU temperature uses a bounded `nvidia-smi` query when available. Unsupported readings are reported as unavailable.

For **“Weather tomorrow,” “Will it rain today?”, “What is the humidity?”, “What is the UV index?”, “When is sunrise today?”** and related short questions, Jarvis reads [Open-Meteo forecast data](https://open-meteo.com/en/docs). Its AQI answer uses the [Open-Meteo air quality API and CAMS model](https://open-meteo.com/en/docs/air-quality-api), so it is an estimate. “What time is it in London?” geocodes the named city, reads its current UTC offset and combines that offset with the PC clock; place names can be ambiguous. Currency conversions use [Frankfurter's latest available reference rate](https://frankfurter.dev/) and name the rate date. These services receive the requested city or currency pair; the profile note and microphone audio stay local. Network calls have short timeouts, current weather is cached for ten minutes, and currency rates for one hour. If a source is unreachable, Jarvis says it cannot verify the value.

The bank also includes actions and private/live data that need separate integrations: calendar events, email, bank balances, smart-home devices, calls, camera input, transit and similar requests. The current direct route does not claim those data or execute those actions. Broader questions continue through local Qwen and optional web search. A **five-second answer for every bank example is not guaranteed**: ASR, speech playback, model generation, cold caches, network delays, unavailable integrations and multi-step actions vary. Fixed Q/A records from the zip were not installed as answers to changing values.

Ask questions such as **“What did I work on in Atlas yesterday?”** or **“Which app was open when I asked about the project?”** Jarvis retrieves up to eight relevant observations from the last 30 daily notes and passes them to its local answer model. For PC paths it also uses the existing fresh filesystem metadata. Answers should name the observation date and say when the notes cannot establish a fact. Window titles and time spent in the foreground are observations only: Jarvis does not record every click, keystroke, page body, private file content, or activity while it is closed. It redacts notes containing obvious credential words, but window titles and questions may still be sensitive; keep the vault local and review it before syncing or sharing.

## Name correction

App names match installed candidates using aliases, spelling edits, swapped letters, and close spoken forms. Examples include `open chrmoe`, `open spoitfy`, and `open kalkulator`. Known website names such as `youtub` resolve to their registered URLs. Button selection compares the requested words with visible enabled control labels, including labels with extra app/site text: `select svae`, `select setings`, or `select contnue`. Jarvis logs the interpreted name. Similar candidates remain numbered choices; unrelated gibberish has no automatic target. Destructive button names are excluded from typo inference.

## Start

If installation is interrupted, double-click **launchers/Resume Whisper Setup.cmd** when the connection is stable. It installs the missing packages, resumes the model download, and runs a synthetic-speech GPU check before reporting success.

Requires Windows 10/11, Python 3.10+, and an NVIDIA CUDA GPU with an up-to-date driver. From this folder run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts/setup/setup.ps1
```

Install Ollama before running **launchers/Setup Jarvis Brain.cmd** for local questions and screen-aware planning. That setup creates the separate brain environment, installs CPU inference dependencies, downloads the configured planning/vision and Laya models, and verifies them. A fresh installation needs internet access for these downloads. The optional God's Eye console also needs Node 24.14+ and `npm ci` in `integrations/gods-eye-view-src/gods-eye-view-main`.

Then close any older Jarvis window and double-click **Start Jarvis.cmd**. Click the top-edge notch to open its glass composer; use **Features** inside the island for settings and other views. Choose your microphone and click **Start listening** if listening is off. Click the header or use **Escape** to collapse the notch; right-click the launcher for quick controls and Quit. Use Start listening to toggle the microphone; Escape hides the panel, while **Quit Jarvis** actually stops supervision. Windows capture exclusion keeps the single island window out of supported screenshots. Initial setup downloads CUDA libraries and the ~1.53 GB English Whisper model. Core inference subsequently works offline; web research and online services require connectivity. The app verifies CUDA by running inference before starting capture and displays the actual device and precision. It does not silently fall back to CPU. Allow microphone access for desktop apps in Windows Settings if needed.

The input meter should move when you talk. Choose **Microphone Array (Realtek)** to try the laptop microphone, or your headset explicitly, rather than relying on the Windows default. The selection is saved to `config/config.json`.

Clicking **Start listening** also wakes Jarvis once microphone capture is ready. Wait for **Awake**, then say **“open notepad”** directly; “Jarvis open notepad” also works. After “go to sleep” or 90 seconds of inactivity, say “Jarvis” again. Recognized speech ignored while asleep is explained in the action log. **Microphone off** means you must click Start listening before speaking.

## Whisper settings

`config/config.json` contains the model path and `whisper` options:

- `device: "cuda"`, `compute_type: "int8_float16"`: GPU inference with quantized weights.
- `partial_interval_seconds: 1.0`: request a new partial transcription about once per second. Actual update delay also depends on GPU decoding time.
- `silence_seconds: 0.8`: finalize after detected speech ends. This does not pause microphone capture.
- `vad_threshold: 0.45`: Silero speech detection threshold. Lower values accept quieter speech but more background noise.
- `language: "en"`: transcribe speech as English without language detection. The English-only `medium.en` model is downloaded by `scripts/setup/setup.ps1`.

The installed `models/faster-whisper-small.en` is a smaller, faster English-only fallback. To use it, set `whisper.model` to `small.en`, remove `whisper.repo`, and set `model_path` to `models/faster-whisper-small.en`. Medium.en decoded the included synthetic command in about 0.67 seconds and recognized `notes.txt` directly. Live accuracy depends on the selected microphone, accent, background noise, and phrasing.

Whisper is not a native streaming recognizer. This app continuously captures audio in one worker and decodes rolling hypotheses in another. Silero voice activity detection avoids feeding silence into Whisper. Long speech rolls through overlapping 20-second windows; timestamped words retain the earlier transcript. Pending partial snapshots are replaced by newer ones so they cannot build an ever-growing inference backlog. Completed utterances retain their order. CUDA DLL discovery is scoped to the process; no system PATH or driver changes are made.

## Talk while it works

- “Hey Jarvis open notepad and write a short list of ideas for today” — the local model writes it into Notepad
- “Open notepad and write exactly my name is Kunal” — typed word for word; “type exactly” also works
- Hold **Left Ctrl + Left Alt** and speak to type everything you say at the cursor; let go to stop
- “Create a file called ideas dot txt containing buy milk”
- “Rename file ideas dot txt to shopping dot txt”
- “Delete file shopping dot txt”
- “Jarvis open calculator then open paint”
- “Go to sleep” or “goodbye” returns to wake-word listening; queued tasks keep running. “Stop all tasks” cancels them.

Say **then**, **and then**, or **next command** between tasks to execute completed clauses without ending your speech. Without a separator, a command waits for the speech recognizer's natural endpoint. Commands before a spoken separator can already have run, so later corrections cannot undo them.

There is no dictation mode (2026-10-10). After an app-opening command, **and write** / **and type** write into that app, including when recognition splits the sentence into separate segments; a “then” inside a write command is part of the text. See [writing by voice and push-to-write](docs/push-to-write.md).

Deletion and renaming wait for a finalized speech segment, even when “then” is spoken; subsequent tasks stay behind them. Each deletion now needs a separate approval dialog showing the exact file path. Approved files go to the Windows Recycle Bin. Silence for 90 seconds returns to wake-word mode. The microphone remains active for wake detection until you click Stop listening, Stop all tasks, or close the window. No background Windows service or startup registration is installed.

## Desktop and files

### Screen-aware autonomous tasks

**Setup:** double-click **launchers/Setup Jarvis Brain.cmd**. It creates `.venv-brain` separately from Whisper, installs CPU PyTorch and Laya, downloads the pinned English Laya checkpoint plus the Ollama models configured in `config/config.json`, and runs synthetic-screen inference checks. Interrupted model downloads can resume by rerunning setup. The feature is not ready until setup and verification finish successfully; existing direct commands continue working while models are missing.

After setup, restart Jarvis. Say **“Jarvis task open YouTube in Chrome”** or type the goal in the bottom box and click **Do task**. Pressing **Enter** routes instructions and questions the same way as speech. Compound instructions such as **“open YouTube and search for how to make robot and play first video”** stay together as a task. This YouTube workflow opens the search directly, observes the results, and selects the requested visible video in screen order. Explicit configured app launches in screen aware tasks run before model planning of the remaining steps. Previously unrecognized finalized commands also go to the planner; known direct commands retain their faster path. **Ask Jarvis** continues to answer questions without desktop actions.

The roles are:

- **Qwen3.5 9B planner:** produces the next supported steps from the currently visible screen.
- **Laya selector:** compares up to eight shortlisted visible control labels plus “none.” Its scores are advisory, not authorization or a guarantee of accuracy.
- **Qwen3.5 9B decision checker:** checks each step against your goal and selects a candidate when needed. A unique exact control name skips Laya's comparison; ambiguous choices require both models to agree. A final check considers the whole goal.
- **Qwen3.5 9B screen reader:** captures the active destination window after every action, checks whether the expected result is visible, and describes the landed screen to the planner. Jarvis then plans its next action from that screen, keeping a short record of completed actions so it does not repeat them.

Brain and question inference use the local CPU configuration; Whisper keeps the GPU. Laya stays loaded in a separate process between tasks. The automatic loop supports opening apps/files/folders, websites, browser and music searches, exposed UI controls, exact text-field filling, scrolling, supported shortcuts, menus/dialogs, creating a new file with spoken content in a named folder, and requesting an app window to close. It cannot activate controls that the app does not expose to Windows UI Automation; text entry and shortcuts must pass the supported tool's destination checks. A new instruction or **Stop all tasks** interrupts the plan.

Examples: **“Jarvis play jazz on YouTube”**, **“Jarvis play my playlist on Spotify”**, **“Jarvis open playlist Focus on Spotify”**, **“Jarvis pause Spotify”**, **“Jarvis resume Spotify”**, **“Jarvis next song on Spotify”**, **“Jarvis previous song on Spotify”**, **“Jarvis shuffle on”**, **“Jarvis repeat one”**, **“Jarvis skip 30 seconds on Spotify”**, **“Jarvis rewind 15 seconds on Spotify”**, **“Jarvis set Spotify volume to 50 percent”**, **“Jarvis mute Spotify”**, and **“Jarvis what's playing on Spotify.”** Spotify search opens the installed Spotify app. Searching alone does not start playback; Jarvis must select a result and verify the playing state. Playback controls use Spotify's Windows media session, and volume controls use Spotify's own audio session; neither targets another app's music. Spotify may require its own login or account permissions. Closing sends the normal window close request, so an app can present a Save prompt. File creation never overwrites an existing file; the spoken folder must be identified unambiguously in the catalog, or you can say **“this folder”** with File Explorer selected.

For projects on D:, say **“Jarvis open project folder”** to open the first available configured project root (currently `D:\Kunals GitHub Repo`), **“Jarvis which project was I using”** to hear the last project Jarvis opened (or the most recently active folder it found), or **“Jarvis open my pending project”** for a numbered list of recent project folders. Say **“option two”** or the project name while the list is open. Jarvis then opens that project in File Explorer and Codex, and opens YouTube in Chrome. It remembers projects it opens in `project_memory.json`. Recent file activity is only a clue; Jarvis cannot determine whether work is actually pending. Change `project_roots` in `config/config.json` to scan other project parent folders.

Only current, revalidated controls can be activated. Invalid plans, ambiguous choices, changed targets, and unverified results stop the loop or enter the bounded recovery path when failure is known to precede execution; uncertain clicks are never replayed. Tasks default to a 20-action budget (`brain.max_task_actions`, configurable from 1–40). The planner can edit a named UTF-8 text file, or request deletion of one named file in a named folder. Deletion waits for your approval. It can propose a command only when your task asks for command execution; Jarvis displays that command for separate approval before running it. Generic desktop payment/upload/permission actions are unsupported. Configured toolkit adapters separately support selected account sends and remote writes with destination/content approval; see the toolkit guide. Screenshots and labels remain local and are treated as untrusted input. Model verification is fallible; a successful check is not a guarantee that every task succeeded.

For model-planned desktop actions, Jarvis fetches fresh accessibility evidence and normally uses a new screenshot with screen awareness enabled. Exact field readback and file/process evidence can bypass redundant visual inference; direct supported workflows use fresh DOM/accessibility/Windows media checks. See the [automation upgrade](docs/automation-upgrade.md). Toolkit operations instead verify their returned data or service acknowledgement and supply the verified result to planning. It waits briefly for a window or control change; if the first visual check catches a loading page, it observes once more. It never repeats the action while waiting. The next step is planned only after the result is verified. Coding tasks similarly read back every created folder, draft, and edited file before moving to the next write. The local task journal records the observation checkpoint.

Run `.\.venv\Scripts\python.exe -m scripts.verification.verify_brain` to test all three models against synthetic screens without desktop actions. `--selector-only` checks Laya alone. `.jarvis-runtime/logs/brain-worker.log` contains local runtime diagnostics. The model choices are configurable under `brain` in `config/config.json`.

Run `.\.venv\Scripts\python.exe -m scripts.verification.verify_scenarios` for 13 varied synthetic requests, including a real create-and-read check in an isolated temporary folder. `artifacts/reports/scenario_results.json` records every plan and pass/fail result. Rerun **launchers/Setup Jarvis Brain.cmd** if a configured model is missing.

Sources: [Laya model and limitations](https://huggingface.co/convaiinnovations/laya), [Qwen3.5](https://ollama.com/library/qwen3.5). Laya's published model card explicitly warns about zero-shot errors and uncalibrated confidence; the desktop workflow has not been fine-tuned or calibrated on your usage.

### General questions and internet knowledge

Restart Jarvis after updating. Click the island and **Start listening**, then ask **“Jarvis why is the sky blue?”**, **“explain photosynthesis”**, or **“search the internet for today's technology news”**. Use **“ask …”** for anything that does not begin with a question word. You can also type a question in the panel and click **Ask**; the right-click menu’s **Preview typed command** remains a preview only.

Answers appear in the transcript log, with a short preview above it, and are spoken aloud. **Speak answers** toggles playback; **Stop voice** interrupts it. English uses a local Kokoro male voice blend (`am_michael` + `am_fenrir`) with natural pauses and breathing; Hindi uses the local Piper Rohan voice. Both are installed by `scripts/setup/setup.ps1`. Kokoro stays warm between replies and plays one continuous stream, starting before the whole reply is synthesized ([details](docs/natural-male-voice.md)). These are assistant-style voices, not an imitation of an actor's voice. The **Answer language** control selects Auto, English, or Hindi. Auto responds in Hindi to Hindi or Hinglish questions and English to English questions. You can type or say questions such as “mujhe batao gravity kya hai” or “पानी क्यों उबलता है”. Hindi answers use Devanagari for accurate Hindi speech. Source URLs stay in the transcript rather than being read aloud. Voice synthesis runs locally. Microphone capture now continues during speech. Say **“Jarvis …”** to interrupt a reply and issue a command; captured playback references reject matching self-echo. This is text-based filtering, not acoustic echo cancellation. **Stop voice** remains available. Questions run in a separate process and queue and no longer supersede a running coding/automation task; voice, questions and the action worker can operate concurrently. **Stop all tasks** cancels pending questions and speech. The last three question/answer pairs stay in session memory for follow-ups; say **“forget conversation”** to clear that short session history. When Obsidian memory is enabled, short question and answer notes remain in its local vault.

The local Ollama model **qwen3.5:9b** provides answers. Jarvis starts the installed Ollama server if necessary. The supervised model-recovery path can restore missing declared models in the background; partial downloads are retained for bounded later attempts. The standard Ollama chat template is used. The enabled `gpu_scheduler` controls actual GPU allocation; set `gpu_scheduler.primary_layers: 0` for CPU primary inference. `knowledge.num_gpu` remains the scheduler-disabled fallback. Responses can take several seconds, especially with model loading or long context. [Current GPU settings](docs/gpu-priority.md) and [earlier measured voice latency](docs/production-validation.md).

### Jarvis command prompt and file edits

Right-click the island and choose **Command prompt**, or say **“Jarvis open Jarvis command prompt.”** Enter a Windows command and press **Run**. Jarvis shows the exact command in an approval dialog first, runs it from `JarvisFiles`, and displays its output and exit code. Commands time out after 60 seconds. A command can change or delete files, so review the entire command before approving it. You can also say **“Jarvis run command dir”** or ask a task to run a command.

### Coding in a named project

Jarvis writes the current task and its checkpoints to local `.jarvis-runtime/state/task_state.json`. The record includes the goal, selected project, stages, action targets, window titles, and verification summaries; it does not store screenshots or generated file contents. A crash or restart marks an unfinished task as interrupted. Repeating the same unfinished request gives the planner that history alongside a fresh screen observation, so it can identify what remains. The record never replays old clicks or commands automatically. Only the latest 20 previous tasks and 30 checkpoints per task are retained. Remove `.jarvis-runtime/state/task_state.json` while Jarvis is closed if you want to clear this local history.

The configured default is **native Jarvis with local Qwen3.5 9B**, using declared file/check contracts, guarded source tools, fixed test assertions and runtime verification. All native workloads use LocalGithub's local Git layer before combined checks and promotion. See the [current native coding workflow](docs/native-coding.md). The [legacy Codex adapter](docs/codex-code-local.md) and [historical workload guide](docs/codex-workloads.md) remain available. The following draft/replacement behavior describes the optional `brain.coding_backend: "direct-qwen"` route.

Say **“Jarvis code in project Demo: add a greeting function”** or **“Jarvis fix the greeting in project Demo.”** Jarvis finds the named project in `project_roots`, inspects a bounded source file list, plans changes to up to three files, reads those files together for context, and generates complete replacements with the local `brain.coder` model (`qwen3.5:9b`). It validates Python and JSON syntax, checks for changed files and unexpectedly truncated output, then writes each file. It cannot delete project files through this coding mode. Check the changed files and run the project's tests yourself; syntax checks alone cannot establish that generated code works. Say **“Jarvis open project Demo”** or **“Jarvis list projects”** to find the project name. Run `python -m scripts.verification.verify_coder` for a synthetic, no-write model check.

With the destination folder open in File Explorer, say **“Jarvis modify kunal.py to add a UI”** or **“Jarvis create a tools folder and a Python script.”** You do not need to say the folder name: Jarvis uses the open Explorer folder, reports its source files, and reads the existing file before editing it. If an edit names a file that is missing or appears in multiple subfolders, Jarvis reports the available paths instead of creating a different file. Jarvis can plan up to three new folders and three files inside that folder. It creates folders and draft files first, then generates or edits source. A failed generation leaves a recognizable draft that can be resumed. Existing files are changed only after the generated replacement passes validation. It will not delete files as part of a coding plan. Run `python -m scripts.verification.verify_coder --workflow-smoke` to test folder creation, script creation, and a follow-up script edit in a temporary folder.

For a new standalone Python file, open its destination in File Explorer and say **“Jarvis create a Python file with calculator code in it.”** Jarvis uses the selected folder and chooses `calculator.py` from the stated purpose. It first creates a visible draft, writes the code into that file, then checks the result. For a basic calculator it runs arithmetic and division-by-zero checks. For other Python requests it generates code with the local model and checks syntax; a failed generation leaves a draft that Jarvis can resume on the next attempt. It does not overwrite an existing user file. You can name the file explicitly as well.
**“Jarvis create Python code for calculator in TestCodes project folder”** also works when the selected Explorer folder is `TestCodes`; Jarvis checks the spoken folder name against the selected folder before writing. Restart Jarvis after installing code updates so its running process loads the new behavior.

For a direct text edit in `JarvisFiles`, say **“Jarvis modify file notes dot txt replace old with new.”** This changes one exact match and stops if the old text appears zero or multiple times. Say **“Jarvis overwrite file notes dot txt with content new text”** to replace the complete file. For a task in another folder, name the folder and file; Jarvis will not infer an unnamed destination. **“Jarvis delete file notes dot txt”** asks for approval of that exact path before moving it to the Recycle Bin.

### Questions about your screen

Open the app you want Jarvis to inspect, then ask **“What is on my screen?”**, **“What does this error mean?”**, or **“Screen pe kya dikh raha hai?”**. You can also click the island, type a question, and press **Ask screen**. Jarvis briefly hides both the controls and island, captures the last active external window, then restores the launcher. It reads visible text with local OCR and sends the screenshot to the local **qwen3.5:9b** vision model. The screenshot stays in memory and is not sent to a web search service or saved to disk. The window title appears in the action log so you can see which app it read.

Screen answers describe one frame at question time. They can read visible text and describe images, but cannot reliably infer motion, hidden content, or what happened earlier. Screen content is treated as untrusted input and cannot trigger desktop actions. Run **launchers/Setup Jarvis Brain.cmd** if the vision model is missing; it downloads the model configured in `knowledge.screen_model`.

Explicit searches and questions about current information use public web search; otherwise the local model decides whether it needs web verification. This uncertainty decision is imperfect. Say **“search the internet for …”** to force a check. Search sends the question (up to 500 characters) to the search providers; audio, the PC catalog, button memory, and conversation history are not uploaded. Answers use search snippets and list their source URLs, rather than claiming full-page research. Offline/search failures are shown clearly. Set `knowledge.internet` to `false` for offline-only use, or `knowledge.enabled` to `false` to disable question answering. The LLM and web results cannot issue desktop actions.

Implementation references: [Ollama chat API](https://docs.ollama.com/api/chat), [raw generation API](https://docs.ollama.com/api/generate), [DDGS search library](https://pypi.org/project/ddgs/).

### Remembered button choices

Jarvis saves successful selections made **through Jarvis** in local `.jarvis-runtime/state/ui_memory.json`, scoped to the app executable and window title. It does not monitor manual mouse clicks. While awake and listening, it checks periodically for a remembered, currently available option when you return to a screen. It shows **“Use it again? Say yes or no.”** Answer **“yes”** to select it, or **“no”** to see alternatives and then say **“select option two”** or **“select [name]”**. Suggestions appear on screen; they are not spoken aloud.

Say **“suggest a button”** to request a suggestion immediately, or **“forget button memory”** to erase the saved choices. Suggestions expire after 45 seconds; changed windows/controls invalidate approval. Learning only occurs after a successful activation, and Jarvis never automatically activates a remembered choice without your answer.

### Select buttons and options by voice

Common phrasing is accepted: **“button list”**, **“choose Person 1”**, **“open Person1 profile”**, **“pause video”**, and **“close”**. Spacing and profile numbers are normalized; a profile's Open button takes priority over its More actions menu. Close buttons can belong to several tabs/windows, so Jarvis lists numbered choices with parent labels where available. “Pause” does not toggle a player that already exposes Play.

### Common names and browser commands

Try **“open YouTube in Chrome”**, **“open Chrome and search MyHuna”**, **“search my hood on Chrome”**, **“open D drive”**, **“open VS Code”**, or **“open my budget”**. Browser searches open Google results in the requested installed browser; **“search the internet for …”** still requests a researched answer. Follow-up questions can begin with **“but why…”** or **“so how…”**.

App matching accepts common aliases, spacing differences, partial names, and close spelling matches. File opening accepts words from longer indexed names, in any order, without requiring an extension. Multiple matches produce a numbered list: say **“select option two”** within 45 seconds. Very broad file searches ask for more detail. This matching uses real catalog entries and exposed controls; it does not infer arbitrary targets or repair every speech-recognition error. Rename and deletion still require explicit filenames.

- **“Click Save”** or **“click the Save button”**
- **“Select comedy with cartoons”** (for a visible tab, button, link, or list option with that label)
- **“Open chrome and select comedy with cartoons”**
- **“List buttons”**, then **“select option two”**
- **“Select second video”** on a YouTube results window, or **“select third result”** for a visible result. Jarvis counts matching controls in their visible screen order.
- **“Select this option”** while pointing at an exposed option, or after Jarvis has shown numbered choices. If several options still fit, Jarvis asks which one you mean.
- **“Select svae”** can match a visible **Save** control. Close spellings are accepted only when the visible choice is clear; ties produce a numbered list.
- **“Click File”**, then name an item in the opened menu

Jarvis uses Windows UI Automation names, not guessed screen coordinates. Keep the destination app in front; if Jarvis itself is in front, it can use the last window it targeted. Controls must be visible, enabled, and exposed by the app's accessibility interface. Hidden dropdown items require opening the dropdown first. Custom canvases and some browser controls may not expose names; the action log explains when no match is available.

Exact labels win over longer labels. Multiple matches produce numbered choices in the action log. Choices expire after 45 seconds and are invalidated when the window or available controls change. Clicking waits for finalized speech. UI calls run in an isolated worker with cancellation and a timeout so a stuck app cannot block microphone capture.
Ordinal and pointer-based choices rely on visible accessibility controls. Jarvis avoids destructive controls in inferred selections; name a control explicitly when that is your intent. If a video page does not expose usable video links, Jarvis asks you to choose another way.

### PC catalog

`config/config.json` now contains discovered Windows applications, Start Menu shortcuts, executable registrations, and named folders. `.jarvis-runtime/state/file_catalog.json` contains file and folder paths from the PC scan; `.jarvis-runtime/state/file_catalog.sqlite3` accelerates lookups without loading millions of aliases into memory. `.jarvis-runtime/backups/config.before-pc-scan.json` preserves the configuration from before the first scan. `.jarvis-runtime/state/scan_report.json` records counts, exclusions, and inaccessible paths.

Examples: **“open chrome”**, **“open blender”**, **“open visual studio code”**, **“open folder downloads”**, **“open file filename dot pdf”**. If names are duplicated, choose a numbered candidate, say the parent folder followed by the filename, or add a unique name under `files` in `config/config.json`, mapping it to the full path.

Double-click **launchers/Refresh PC Catalog.cmd** after installing apps or moving files, then restart Jarvis. The scan reads names and paths, not document contents. It skips Windows internals, AppData, ProgramData, dependency/cache folders, and reparse points/junctions, and records permission-denied locations. It does not claim to index every protected or cached file. Direct file creation, rename, edit, and deletion use `files_root`; a multi-step task can create, edit, or request deletion of a single file in a named folder. Deletion always opens an approval dialog. File edits require UTF-8 text and either one exact snippet to replace or an explicit full overwrite.

Some packaged apps launch through Windows shell IDs. For those apps, click the text field and say “write … here”; their actual destination process cannot reliably be inferred from the launcher.

Notepad, Calculator, Paint, and File Explorer are configured. Add apps as executable argument arrays in `config/config.json`, for example `"my editor": ["C:\\Path\\Editor.exe"]`. Commands never become shell scripts.

Click the app's text field before saying “Jarvis write … here”, or name the app (“write … in Notepad”). Typing is bound to that window and stops if focus changes; nothing more is typed after an error. Moving the pointer to a screen corner triggers the typing fail-safe. Some elevated or custom apps reject simulated typing.

Each write command targets the window you were in when you asked, except when it follows an app-open command or names an app: then it writes into that app. Push-to-write follows the cursor phrase by phrase.

File operations are restricted to the configured `files_root` (default `JarvisFiles`). They target single filenames, never folders. “Dot txt” becomes `.txt`; a missing extension defaults to `.txt`. Creation and rename never overwrite existing files. To choose another folder, edit `files_root` in `config/config.json`. Voice cannot expand that scope.

`microphone` may be an input device index or device name. List available devices:

```powershell
.\.venv\Scripts\python.exe -m sounddevice
```

Whisper recognition still depends on the microphone, noise, accent, and overlapping speakers. Wake recognition is speech-to-text matching, not speaker authentication. The app shows Whisper's original punctuation in the transcript but normalizes case and command punctuation before passing text to the existing command engine. Dictated text currently uses that normalized form too. Transcript history is memory-only and capped in the UI.

## God's Eye View

![God's Eye View upstream demonstration](integrations/gods-eye-view-src/gods-eye-view-main/docs/media/hero-open-source-reveal.gif)

Bundled upstream demonstration, not a screenshot of a verified Jarvis task. Additional globe demos are available in the [upstream media guide](integrations/gods-eye-view-src/gods-eye-view-main/docs/media/README.md). Some showcased layers or analyst features have separate data/API requirements.

Say **“Jarvis open God's Eye View”** to start Bilawal Sidhu's local 3D Earth console and open it in Chrome. You can also say **“open God's Eye View in Edge”**. Jarvis starts the console only on request; the local server stops when Jarvis closes. The installed source is under `integrations/gods-eye-view-src/gods-eye-view-main`. While its browser window is active, Jarvis's existing screen questions can describe the visible view. The globe's own analyst and voice features need a separate OpenAI API key; no key is configured by this integration. Public data layers work without one. The globe adds spatial data and does not replace Jarvis's local Qwen planner or Laya selector.

God's Eye View's source code is [MIT licensed](https://github.com/bilawalsidhu/gods-eye-view/blob/main/LICENSE). Its bundled assets and third-party data retain [separate terms](https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md). The installed local copy can be updated from [upstream](https://github.com/bilawalsidhu/gods-eye-view); run `npm ci` in its folder after an update. It uses Node 24.14 or newer.

## Silent startup and recovery

### Task failure recovery

`brain.task_recovery` is enabled. Missing controls, unavailable dialogs and stale targets detected before dispatch are recorded as not executed. Jarvis takes a fresh observation and asks the existing Qwen planner for a different supported approach. The alternative plan still passes the normal goal, filename, exact text, command and approval checks; failed actions are blocked. Recovery is limited to two alternative plans within the configured task budget (20 actions by default).

Tool exceptions and results that cannot be verified are recorded as uncertain and pause the task, since an external effect may already have happened. Decision-model rejection, sensitive controls and missing approval never trigger an alternate route around those checks. Failure history survives in `.jarvis-runtime/state/task_state.json` and is supplied when revisiting the same unfinished goal. Repair messages stay in the transcript; no new background service or dependency is needed.

Research through Firecrawl used agent feedback and bounded stopping patterns described in [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

### Tool, project and app memory

Jarvis writes `Jarvis Tools.md`, `Jarvis Projects.md`, `Jarvis Apps.md` and a structured `Jarvis Index.json` into the configured Obsidian vault. The Brain note links to these catalogues. Tool notes describe all registered tools, required configuration names, approval requirements and direct command operations; credential values are never included. Project summaries use bounded README excerpts, package descriptions, Python module docstrings or directory signals and identify their basis. Software entries include configured app aliases, Windows App Paths and uninstall registrations, with available executable, shortcut, shell ID or install-directory locations. An install directory is reference data, not a launch target; registrations with no known location remain explicitly unknown. Startup adds verified Windows App Paths as runtime launch aliases without rewriting configuration.

Relevant catalogue entries feed task planning, replanning, decisions, coding and question answering, with a 5,000-character input budget. Simple questions such as “Where is my Atlas project?” or “What does my Atlas project do?” read the saved summary and a verified existing folder directly, bypassing model inference. Summary answers include their source and index date; they do not establish current functionality. Saved notes never authorize actions; current tool registration, credentials, path existence and normal approvals remain authoritative. Exact normalized project names also resolve coding destinations and project opens; duplicate names still require selection. Missing or ambiguous folders still need clarification. Local project/software questions use the supplied catalogue rather than sending private catalogue data to a web search.

A bounded refresh runs off the response path on startup and at most hourly when another request arrives. Quit cancels scanning and prevents subsequent refresh writes. Changes to `Jarvis Index.json` are reloaded by modification time and file size. The scan covers configured `project_roots` plus Desktop, Documents, Downloads, OneDrive, source and repos folders; set `memory.include_user_project_folders` to `false` to use only configured roots. It visits at most 30,000 directories for 45 seconds and five levels below each root, skips linked paths, known install directories, generated dependencies and common source subfolders, and records inaccessible paths and coverage limits. It is not an exhaustive inventory of every drive, deep folder or unregistered portable app. Detected folders can include independent subprojects or downloaded source. Summaries are historical descriptions, not proof that the software currently works.

Refresh explicitly from the application directory:

```powershell
.venv\Scripts\python.exe -m jarvis.memory_index --dry-run
.venv\Scripts\python.exe -m jarvis.memory_index
```

The first command reports counts without writing the vault. The second replaces Jarvis-owned catalogue notes and index, preserving other notes and the personal profile. No Obsidian plugin or API token is needed: Jarvis reads and writes local vault files directly. Automatic refresh errors are retained in memory status; existing notes remain available where readable.

**2026-09-30 verification:** The local vault contains 64 tool descriptions, 38 direct operations, 302 detected project folders and 793 app aliases/software registrations, linked from Jarvis Brain. The bounded scan visited 12,803 directories and reported six inaccessible paths; five-level depth and exclusions still apply. Private project/software contents were kept outside Git. All 428 regression tests passed, including catalogue reload, duplicate names, stale paths, prompt bounds, task context and cancellation of refresh on Quit. Launcher readiness reported `ready`. A live direct project-summary/path lookup read the actual vault in 10.06 ms on its first call and 0.66–0.82 ms on repeated calls; these are text lookup timings, excluding speech recognition and speech output. A separate local model-backed project answer timed out at 60 seconds even though Ollama's API was reachable, so end-to-end model answers and a universal five-second target remain unverified.


### Adaptive planning

`brain.adaptive_planning` and `brain.incremental_planning` are enabled in `config/config.json`. General desktop planning requests one next action using a fresh image, the original goal, verified results and the action budget. It prepares a prompt scaffold during execution and clears its two-frame context on exit. Setting incremental planning to false restores the configured multi-step backend. Completion still requires an independent check against the full goal. [Repeat navigation scope, configuration and measured limits](docs/step-planning.md).

Remaining tasks, verified results and bounded revision history are saved in `.jarvis-runtime/state/task_state.json`. After a crash they are context for a fresh observation, never an automatic replay queue. An uncertain result or failed replanning pauses the task; completed actions are not repeated. The existing coding workflow separately validates generated files before committing them. No new model or background service is required: replanning uses the configured Qwen planner inside the existing supervised inference worker. External actions use the configured task budget, 20 by default (1–40).

Research through Firecrawl: [OPEA's plan/execute/replan workflow](https://github.com/opea-project/GenAIComps/blob/8130a3fb9cd8f2fcef8eff6657844e11ddf63d71/comps/agent/src/integrations/strategy/planexec/README.md).

Double-click **Start Jarvis.cmd** to start the hidden, single-instance supervisor and Jarvis with listening enabled. **Stop Jarvis.cmd** or Jarvis's Quit command stops supervision and owned repair downloads. Stopping only the microphone leaves the other service checks running and keeps the microphone stopped after an unrelated crash.

The background watchdog checks the interface heartbeat, microphone/decoder, action and question threads, speech thread, Ollama, configured Ollama models, and God's Eye's local server after it has been requested. Repairs use hidden processes and appear only as `REPAIR` messages in the transcript. Logs and startup snapshots are stored under `.jarvis-runtime`; no repair notifications are spoken. Recovery does not launch or reopen unrelated user apps.

Startup checks restore missing declared Python dependencies and model assets. Invalid Jarvis source syntax or configuration can be restored from a previous startup snapshot, preserving the damaged copy. A separate standard-library bootstrap can restore the supervisor's entry point before importing it. These snapshots verify syntax, not program behavior: recovery cannot invent fixes for arbitrary logic bugs, reinstall Windows/Python/drivers, or recover its bootstrap if that file itself is damaged. Repairs needing a network connection retry with backoff. Stop interrupts owned setup processes.

Crashes preserve task checkpoints and pause unfinished work. File writes, shell commands, clicks, and shortcuts are never replayed automatically after an uncertain failure. Resume a task using the fresh screen/file state. File deletion and command approval remain in place; normal task approval dialogs are separate from silent repair.

`config/runtime_manifest.json` declares runtime dependencies; `AGENTS.md` requires future upgrades to maintain the launcher and recovery registrations together. Check syntax, configuration, dependency imports and local model files without starting the interface:

```powershell
.\.venv\Scripts\python.exe -m jarvis.launcher --check
```

The recovery design follows [Supervisor's process states and retry behavior](https://supervisord.org/subprocess.html) and [Ollama's service configuration](https://docs.ollama.com/faq). Research also included [Supervisor's restart discussion on GitHub](https://github.com/Supervisor/supervisor/issues/212) and [a Python background watchdog discussion on Reddit](https://www.reddit.com/r/Python/comments/42oy0x/running_watchdog_in_the_background/).

## Integrations and toolkits

Jarvis adapts Ultron's memory decay code for recent successful UI suggestions
and recalls compact summaries of related verified tasks when planning. This
runs locally with the existing task history and dependencies. See
[Ultron integration and attribution](docs/ultron-integration.md) for scope,
license, and validation details.

Spoken replies are enabled in the saved settings. Jarvis uses conversational
answer wording and the user-selected Kokoro Heart English voice, synthesizing
each reply into one continuous buffer before playback. The owned voice worker
stays warm between replies; Hindi uses Piper. Stop voice interrupts playback; repair notices stay
silent. Microsoft JARVIS dependency checks now validate related task steps.
See [planning and speech integration details](docs/jarvis-repository-integrations.md)
for historical source attribution. See [current Heart voice and repair details](docs/natural-voice-and-model-repair.md)
for settings, the current preview, measured timing and limitations.

The launcher now uses a compact native Dynamic Island with animated size changes.
Click to open conversation and controls; Settings reveals microphone/language options.
See [Dynamic Island interface](docs/dynamic-island.md) for behavior, design references and rendered previews.

Autonomous coding now uses related project sources, exact-match edits and
shared context across generated files. Original files and diffs are saved before
project writes; uncertain writes block automatic replay. See
[agenticSeek-inspired coding improvements](docs/agenticseek-integration.md).

Questions reuse a hidden worker and task inference avoids duplicate model
discovery, keeping the same configured models. See
[GAR-inspired response speed improvements](docs/gar-response-speed.md)
for measured latency and recovery behavior.

SuperAGI-inspired adapters add 37 toolkit operations, including scoped resource
search, coding drafts, GitHub, research and credential-gated account services.
Say **“list toolkits”** to see configuration requirements. See
[toolkit integration and command examples](docs/superagi-toolkits.md).

| Integration | What Jarvis uses | Reference and attribution |
| --- | --- | --- |
| Ultron | Adapted time-decay ranking and compact recall of verified task summaries; no upstream server at runtime. | [Memory adaptation](docs/ultron-integration.md), retained Apache-2.0 license. |
| Microsoft JARVIS | Adapted dependency validation for task IDs; execution stays sequential. | [Planning integration](docs/jarvis-repository-integrations.md), retained MIT license. |
| isair/jarvis | Inspected voice design; independently implemented conversational speech and sentence playback using installed Piper voices. | [Speech integration](docs/jarvis-repository-integrations.md), reference license retained; no upstream runtime source copied. |
| Jarvis HUD reference | Historical circular artwork retained for attribution; replaced at runtime by the native Dynamic Island. | [HUD](docs/hud-interface.md) and [artwork provenance](jarvis/assets/README.md). |
| agenticSeek | Related-source discovery, exact replacement validation, bounded feedback, and coding review artifacts. | [Coding improvements](docs/agenticseek-integration.md), retained GPLv3 reference license; no imported upstream runtime. |
| General-Agent-Runtime | Reusable hidden question worker and removal of duplicate model discovery overhead. | [Response speed measurements](docs/gar-response-speed.md); configured models unchanged. |
| SuperAGI | Independently implemented file/resource/coding/web/GitHub/account adapters. | [Toolkit guide](docs/superagi-toolkits.md), retained MIT reference license. |
| God's Eye View | Separate on-demand local 3D Earth console. | [Installed source](integrations/gods-eye-view-src/gods-eye-view-main/README.md), MIT code and separate data/asset terms. |

Toolkit groups include file listing/reading/appending/search, local resource and knowledge search, thinking/specification/test/code drafts, public web search/static scraping, GitHub reads/reviews/approved writes, email, Google Calendar, Jira, Apollo, Slack, and X. Of the 37 added operations, 19 require no account credentials and 18 need environment configuration. No-credential web operations still need network access. Coding drafts are returned for review; the project coding workflow performs checked writes.

Use **“list toolkits”** to inspect required environment variable names before launch. Provider credentials are not supplied by Codex plugins, and OAuth acquisition/refresh is not automated. See the guide for exact payloads, approvals, and current adapter limits. Email attachments, Instagram publishing, image generation, SuperAGI agent spawning, and its full service stack are not implemented by these adapters.

## Autonomous toolkit use

Jarvis chooses and combines toolkit operations from the given goal; you do not need to specify tool names. Initial planning, adaptive replanning and recovery receive relevant configured toolkit operations plus previously discovered tools. `tool_search` loads more operations for subsequent steps. Set `agent_runtime.deferred_tools` to false to expose the entire configured catalog. There are **51 operations with no required account environment variables**, and **69 registered in total**. The 18 account-backed operations need their environment variables; MCP wrappers additionally need trusted local server configuration and approval.

Verified tool results feed the next decision, remaining plan and final goal check. File/API/draft results are checked directly instead of requiring a desktop screenshot. Unknown URLs, IDs, SHAs or source text should be discovered by a prerequisite read, followed by replanning. Full result context stays in current-task memory with bounded/truncated input; durable checkpoint summaries stay compact. Native next-step inference uses an 8,192-token context and at most 450 output tokens; legacy planning and coding can use a 16,384-token context for selected tools, guidance and observations.

Examples:

- `task find useful public sources about Python asyncio and compare the main tradeoffs`
- `read file source.txt in Demo and draft tests for its functions`
- `task check my upcoming calendar meetings and draft a preparation checklist`
- `task review pull request 12 in GitHub repository owner/repository`
- `task research Python asyncio and email a summary to recipient@example.com`

External messages and remote changes require the appropriate account configuration and visible approval of the destination and exact payload. Drafting does not save or execute code. Every initial and revised plan checks write intent, while failure/cancellation blocks dependent actions and uncertain effects are never replayed. The configured task budget applies, 20 by default (1–40). See [autonomous toolkit details](docs/superagi-toolkits.md#autonomous-planning-and-chaining).

## Architecture and project layout

```mermaid
flowchart TD
    Input[Microphone or text input] --> Route[Wake gating and command routing]
    Route --> Direct[Direct commands]
    Route --> Brain[Local planner and decision checks]
    Route --> Questions[Reusable question worker]
    Brain --> Registry[Shared tool registry and dependency checks]
    Direct --> Registry
    Registry --> Actions[Desktop, browser, files, coding and toolkits]
    Actions --> Observe[Fresh screen, controls and file evidence]
    Observe --> Verify[Step and full goal verification]
    Verify --> Replan[Adaptive remaining plan]
    Replan --> Brain
    Verify --> Journal[Persistent checkpoints and verified history]
    Questions --> Reply[Transcript and continuous Kokoro speech]
    Verify --> Reply
    Supervisor[Bootstrap, launcher and watchdog] --> Brain
    Supervisor --> Questions
    Supervisor --> Input
```

Planning, observation and inference can retry within their defined bounds; external actions cannot be replayed after uncertainty. Task history informs planning and is never an executable replay queue. Question work and speech use separate workers so desktop tasks and capture can continue.

```text
Jarvis/
  AGENTS.md                     Repository maintenance instructions
  README.md                     Project overview and navigation
  .gitignore                    Local compatibility-junction exclusion
  app/
    AGENTS.md                   Application maintenance requirements
    README.md                   Complete application guide
    main.py                     App state and UI lifecycle
    jarvis_bootstrap.py          Minimal supervised entry point
    Start Jarvis.cmd             Hidden single-instance startup
    Stop Jarvis.cmd              Explicit supervisor shutdown
    requirements.txt            Includes requirements/runtime.txt
    config/                     Settings and runtime manifest
    requirements/               Main and isolated dependency sets
    launchers/                  Setup and maintenance shortcuts
    jarvis/                     Application modules, assets, data and templates
    scripts/                    Setup, catalog, models, training, skills,
                                integrations, audits, verification and previews
    tests/                      Regression tests and controlled fixtures
    docs/                       Guides, structure, audits and dated evidence
    examples/                   Maintained examples
    integrations/               Active adapters, upstream sources,
                                provider profiles and attributed references
    artifacts/                  reports/, media/, training/, projects/,
                                research/, fixtures/ and logs/
    skills/                     Bundled skill guidance
    custom-skills/              Local custom skill workspace
    models/                     Local downloaded models and voice assets
    JarvisFiles/                Local direct-file and terminal workspace
    secrets/                    Local credential storage
    .venv*/                     Isolated local Python environments
    .jarvis-runtime/             State, logs, backups, journals and recovery
  InsTAREELS/                    Ignored local junction to app (Windows)
```

| Modules | Responsibility |
| --- | --- |
| `audio.py`, `whisper_backend.py`, `engine.py`, `commands.py` | Capture, VAD/transcription, wake/stream handling, and command parsing. |
| `interface.py`, `hud.py`, `main.py` | Dock/panel rendering, controls, event handling, and app lifecycle. |
| `actions.py`, `desktop_actions.py`, `ui_controls.py`, `ui_worker.py`, `browser.py` | Direct actions, accessibility-backed operations, checked destinations, and browser launching. |
| `brain.py`, `brain_worker.py`, `model_selection.py`, `screen_worker.py` | Planning/decisions, Laya, model availability/fallback, and screen observation. |
| `step_planning.py` | Task-owned two-frame context, prepared prompts and exact-goal verified native navigation recipes. |
| `tools.py`, `toolkits.py`, `native_tools.py`, `firecrawl_tools.py`, `task_graph.py` | Registered schemas, native proposals, guarded provider adapters, and task dependencies. |
| `coder.py`, `code_context.py`, `projects.py`, `catalog.py` | Checked source generation/edits, project context/discovery, and indexed path lookup. |
| `agent_context.py`, `agent_tools.py`, `agent_events.py`, `mcp_bridge.py` | Repository guidance/skills/maps, scoped reads/batches, metadata events/deny hooks and approved stdio MCP. |
| `agent_session.py`, `agent_cli.py` | Headless read-only provider loop, JSONL sessions/forks, bounded research agents and stdio API. |
| `knowledge.py`, `knowledge_worker.py`, `question_client.py`, `speech.py`, `piper_speech.py` | Answers, web/screen context, worker reuse, voice synthesis, and playback. |
| `task_state.py`, `task_recovery.py`, `experience.py`, `ui_memory.py`, `obsidian_memory.py` | Checkpoints, safe alternatives, verified task recall, UI suggestions, and local Obsidian notes. |
| `launcher.py`, `recovery.py`, `model_recovery.py` | Process ownership, startup readiness, health checks, and bounded silent repair. |
| `gpu_scheduler.py` | Process-shared inference priority, speech reservation, partial offload, bounded cache handoff and metadata health. |
| `spotify.py`, `gods_eye_view.py` | Spotify-specific sessions and owned globe server lifecycle. |
| `memory_curator.py`, `capability_guide.py`, `weather_watch.py` | Long-term memory (learned facts, "remember/forget", conversation summaries, prompt context), capability and API answers with a live API check, and bad-weather/emergency alerts. |
| `whatsapp.py`, `messengers.py` | WhatsApp Desktop through its accessibility tree (search, choose, draft, preview/approve, send and verify, replies, message/call watcher) and other messaging apps. |
| `media_player.py` | Play by name on YouTube (Data API v3 or keyless search) and Spotify (app search, accessibility read, pointer click, media-session check), service resolution and island media cards. |

## Configuration and relocation

| Setting | Current saved value / purpose |
| --- | --- |
| `model_path` | `models/faster-whisper-medium.en`, resolved from the app directory. |
| `whisper` | `medium.en`, CUDA, `int8_float16`, English, 1 s partial interval, 0.8 s silence, 0.45 VAD threshold. |
| `files_root` | `JarvisFiles`, resolved from the app directory. |
| `folders["jarvis files"]` | Relative `JarvisFiles` alias; follows a future app directory move. |
| `project_roots` | `D:\Kunals GitHub Repo`, its `Jarvis` directory, existing `D:\Phython Project`, and `D:\`. These are local machine paths. |
| `microphone`, `wake_timeout_seconds` | Default device (`null`), 90 s wake inactivity timeout. |
| `knowledge` | Enabled, `qwen3.5:9b` answers/vision, English answers, internet enabled; actual offload governed by `gpu_scheduler`. |
| `gpu_scheduler` | Enabled; primary layer ceiling 12, coding layers 9, speech/headroom reservation 1,024/512 MiB, queue 120 s, warm cache 30 s, helpers default CPU. |
| `speech` | Enabled, English, length scale 1.05, noise 0.667/0.8, sentence silence 0.18 s. |
| `brain` | Enabled, `qwen3.5:9b` planner/coder/decision/vision, native function calls, no model fallback, Laya selector, adaptive planning/recovery. |
| `agent_runtime.deferred_tools` | Enabled; show relevant configured toolkit tools and load others through `tool_search`. |
| `apps`, `folders`, `files`, `file_catalog` | Installed app targets, named path aliases, optional explicit file aliases, and catalog source. |
| `memory.long_term`, `weather_alerts` | Learned facts and conversation summaries with `qwen3.5:9b` (15-minute idle summaries); weather and emergency alerts every 30 min at `warning` level. See [settings](docs/memory-apis-alerts.md#settings-configconfigjson). |
| `whatsapp` | Enabled; watch messages and calls every 2 s, draft replies for approval, skip groups and muted chats, at most 5 replies per request. See [WhatsApp settings](docs/whatsapp.md#settings-configconfigjson--whatsapp). |
| `media.default_service` | `youtube`; where "play X" goes when no service is named and Jarvis has not played anything yet. The optional YouTube Data API v3 key goes in gitignored `secrets/youtube.json` (`{"api_key": "..."}`) or `JARVIS_YOUTUBE_API_KEY`, never here. |

Current application location: `D:\Kunals GitHub Repo\Jarvis\app`. Launchers use their own directory; application/model paths derive from source locations. Run commands from the app directory so Python resolves the `jarvis` package. The **open project folder** command uses the first existing non-drive-root entry in `project_roots`, rather than relying on the old folder name.

After another move, review absolute `project_roots` and app/folder aliases, then refresh the PC catalog for moved indexed paths. Historical task records describe the original targets and should not be blindly rewritten. Python virtual environments also contain absolute activation/console-launcher paths: the activation scripts in both current environments were corrected during this relocation. Prefer `python.exe -m pip` from the selected environment; if an environment is moved again and fails, recreate it with the setup scripts. Verify readiness before restarting Jarvis.

Runtime records under `.jarvis-runtime/state/` include `.jarvis-runtime/state/task_state.json` (bounded task history/checkpoints), `.jarvis-runtime/state/ui_memory.json` (successful choices), optional `.jarvis-runtime/state/project_memory.json` (opened projects), the file catalog/SQLite index, worker logs, and `.jarvis-runtime/repairs.jsonl`. Coding originals/diffs/hashes are stored in `.jarvis-runtime/coding/<id>/`. The UI transcript and question conversation history are bounded in memory; task metadata and repair records persist locally. Screenshots and generated file contents are not embedded in task-state records. Obsidian notes are saved separately in the configured `D:\Phython Project\Jarvis_Memory\Jarvis_Mem` vault.

## Troubleshooting

| Symptom | Check / action |
| --- | --- |
| Startup fails or dependencies/models are missing | Run the launcher readiness command below; inspect `.jarvis-runtime/repairs.jsonl` and worker logs. Rerun the relevant setup/resume script. |
| Setup interrupted | Rerun **launchers/Resume Whisper Setup.cmd** or **launchers/Setup Jarvis Brain.cmd** when connectivity returns. Downloads are designed to resume. |
| GPU speech check fails | Confirm NVIDIA driver/GPU availability and inspect `scripts/verification/verify_whisper.py` output. This configuration does not silently use CPU Whisper. |
| No recognized speech | Check Windows microphone access, the selected device and input meter, listening state, and whether reply playback is muting recognition. |
| Answers/planning unavailable | Install/start Ollama, complete brain setup, and inspect the configured model names and worker logs. |
| Jarvis ignores a spoken selection | Keep the destination visible, list exposed controls, and name an unambiguous current label. Choices expire after 45 s. |
| File lookup fails after a move | Check aliases and run **launchers/Refresh PC Catalog.cmd**; restart Jarvis. An outdated SQLite index is rejected rather than guessed. |
| Project folder opens the wrong location | Reorder/update `project_roots` in `config/config.json`; the first existing non-drive root is used for the generic project-folder command. |
| Toolkit is unavailable | Use **list toolkits**, set the required provider environment variables before startup, and review provider scopes in the toolkit guide. |
| Unfinished task after a crash | Inspect fresh screen/file state and use **resume last task** when appropriate. An uncertain write/click remains paused until inspected. |
| Panel disappears but Jarvis remains active | Closing/hiding the panel is intentional; use **Quit Jarvis** or **Stop Jarvis.cmd** to stop supervision. |
| Globe fails to launch | Check Node, installed `node_modules`, port 4173, and `jarvis-launch.log` in the globe source directory. |

## Verification commands

For the complete dated inventory and optional isolated static checker, see [repeat the system audit](docs/system-audit.md#repeat-the-audit). `--check` now includes configured local service/model availability; `--offline-check` reports dependency readiness only.

Use the main environment explicitly to avoid another installed Python or a stale moved console launcher:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m jarvis.launcher --check
.\.venv\Scripts\python.exe -m scripts.verification.verify_whisper --audio tests\fixtures\jarvis-command.wav
.\.venv\Scripts\python.exe -m scripts.verification.verify_brain
.\.venv\Scripts\python.exe -m scripts.verification.verify_scenarios
.\.venv\Scripts\python.exe -m scripts.verification.verify_speech
.\.venv\Scripts\python.exe -m scripts.verification.verify_ui
.\.venv\Scripts\python.exe -m scripts.verification.verify_coder --workflow-smoke
```

Additional targeted checks:

```powershell
.\.venv\Scripts\python.exe -m scripts.verification.verify_desktop_planner
.\.venv\Scripts\python.exe -m scripts.verification.verify_desktop_planner --vision-only
.\.venv\Scripts\python.exe -m scripts.verification.verify_ui --preview artifacts\jarvis-hud-preview.png
.\.venv\Scripts\python.exe -m scripts.verification.verify_question_speed --live
.\.venv\Scripts\python.exe -m scripts.verification.verify_toolkits --live
.\.venv\Scripts\python.exe -m scripts.verification.verify_toolkit_planner
.\.venv\Scripts\python.exe -m scripts.verification.verify_hardware_models
.\.venv\Scripts\python.exe -m scripts.verification.verify_clarification
.\.venv\Scripts\python.exe -m scripts.verification.verify_real_world
```

Unit tests use controlled fixtures/mocks for desktop and provider behavior. Readiness checks import declared dependencies and check local assets without launching the main interface. Model checks need installed models; UI checks create their own test window; coding/toolkit smoke checks write only their isolated temporary workspace. Live question/toolkit checks can contact local inference and public web services. Use **Start Jarvis.cmd** for ordinary supervised use; direct `main.py` execution bypasses the supervisor.

`scripts/verification/verify_real_world.py` performs thirteen live local-model/repository/file/web
checks and a three-file application build with ten CLI cases. It keeps dated
results in `artifacts/real-world-*`, uses a fresh workspace for each rerun, and
closes only a test-owned Ollama server. No desktop, microphone or third-party
account/MCP actions are covered. See the [live test report](docs/real-world-validation.md)
for observed failures and answer-quality limits. Source inspection now obtains
explicitly requested read observations before inference; repository maps favor
application code over reference trees. Bounded model-response correction and
CPU queue deadlines improve headless research. The web scraper supports a literal
excerpt query, such as JSON `content` `{"query":"json.loads"}`.
Text inference also inspects local Qwen template metadata: prompt-only templates
receive explicit role delimiters; native chat templates retain their chat API.
This corrects guidance delivery without changing the installed model.

The **Preview text command** box accepts a full “Jarvis …” sentence and displays planned actions without executing them. Automated tests cover streaming, duplicate prevention, wake gating, explicit deletion, cancellation, and filesystem restrictions. Live microphone accuracy and typing into your chosen apps need a spoken trial on your PC.

`scripts/verification/verify_whisper.py` loads the configured model, executes GPU inference, prints the recognized text, timing, and planned commands, and never executes desktop actions. The included WAV is synthetic test speech, not a recording of the user. Unit tests cover punctuation normalization, overlap stitching, backpressure, cancellation during inference, plus the existing file and typing restrictions.

References: [faster-whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu), [English-only medium.en conversion used here](https://huggingface.co/Systran/faster-whisper-medium.en), and [Silero integration](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/vad.py). Desktop control uses the Windows API directly.

## Current validation and update history

**2026-09-27 coding curriculum:** completed [100 standalone Python CLI projects](docs/coding-curriculum.md)
with real local inference and executable checks: **69/100 passed**, including
**61 first recorded attempts** and **8 repairs**; **31 failed** within two attempts.
There were **405 actual CLI invocations** across the completed primary attempts.
Ten larger follow-up checks passed **10/10**, and a new invoice calculator through
normal Jarvis coding passed **10/10**, including eight withheld cases, in one inference.
The report preserves all failures, two inference timeouts, interrupted files and protocol changes.

Jarvis now recalls verified failure categories and related fixed examples, applies a
learned check for selected missing Python imports before returning drafts, and ships
**151 metadata records** so the experience survives a fresh checkout. This is
experience memory, **not model-weight training** or guaranteed error elimination.
Run `python -m scripts.training.train_coding --limit 100 --attempts 2` from this directory; larger and transfer
verification commands are in the linked guide. Previously recalled examples are teaching
data and cannot be called unseen tests in later repeated runs. Current project language,
interfaces and permissions govern applicability of the curriculum lessons.

All **386 regression tests passed**; launcher readiness reported `ready` with no
missing requirements. No new dependencies or visible Jarvis UI changes were introduced.
These are live coding checks plus regression/readiness results; microphone, desktop,
real accounts and external MCP providers were not newly live-tested in this curriculum.

**2026-09-27 live task trials:** thirteen real scenarios used the installed local
model, actual repository/Git, scoped disk writes and live Python documentation.
The three-agent investigation completed after a CPU queue timeout fix. The
three-file expense application initially passed **4/10 real CLI cases**; after
explicit failure feedback and a Jarvis-generated repair in a fresh copy,
**10/10 passed**, preserving every CSV input. Earlier source answers and builds
failed; some audit prose remains inaccurate despite keyword checks. The
[complete task/evidence report](docs/real-world-validation.md) preserves those
failures and distinguishes repair success from an autonomous first attempt.
All **376 regression tests passed**; launcher readiness reported `ready` with no
missing requirements. Microphone, desktop and real account/MCP-provider actions
were not live-tested. Both README files and the integration guides were updated.
All **129 local documentation links and anchors** in the updated documentation resolved.

**2026-09-27 agent runtime integration:** all **370 regression tests passed**,
including 23 new runtime tests with real temporary Git/MCP fixtures, timeout,
blocked stdin, oversized/invalid output, cancellation, approval/allowlist gates,
instruction preflight, skills, policy hooks, batches, session resume/fork and
isolated research-agent failures. Launcher readiness reported `ready` with no
missing requirements. These are regression/readiness results, not validation of
real third-party MCP providers or desktop/account actions. The attempted live
headless model smoke check could not connect because Ollama was not running;
live model behavior had not yet been verified at that stage. Subsequent live
trials are recorded in the [live task report](docs/real-world-validation.md).
The fixture-provider smoke check inspected source, preserved project files and
resumed its saved session successfully.
The headless stdio metadata/catalog check passed; all **108 local documentation
links and anchors** across both README files and the new guide resolved.

**2026-09-27 file-task and clarification fix:** all **347 regression tests passed**, including the reported spoken sentence, exact contents, folder questions and answers, option names/numbers/ordinals, expired/invalid choices, cancellation, and uncertain-action blocking. The live Qwen smoke check created and read back two temporary files, including a task continued by a Downloads answer; Explorer launch/observations were simulated, with no real desktop, microphone or account actions. Launcher readiness reported ready with no missing requirements. Both README files document the new behavior and `scripts/verification/verify_clarification.py` reproduces the smoke check.

**2026-09-27 hardware/model review:** actual hardware inspection, six synthetic vision step checks, and live Laya/Qwen agreement and unrelated-action rejection checks passed. All 330 regression tests passed; launcher readiness reported ready with no missing requirements. Current model assignments retained; see the model audit for the scope and timings.

**2026-09-27 autonomous toolkit planning:** all **330 regression tests passed**, including autonomous dispatch coverage for all 37 added toolkit operations with mocked adapters, actual scoped temporary-file reads, bounded result context, configured-tool schemas, failed verification, and unrequested-send rejection. The actual local `qwen3.5:4b` selected research and source-reading tools and replanned from source text into `write_tests` without unnecessary clarification. Launcher readiness passed with no missing dependencies/models; **96 local documentation links/images/anchors passed**. The live planner check executed inference only, with no desktop, web-tool or account actions. All models remain unchanged.

**2026-09-27 relocation validation:** all **317 tests passed** and `python -m jarvis.launcher --check` reported `ready` with an empty missing list. Direct checks confirmed the relative Jarvis-files alias, relocated Jarvis project discovery, and `python -m pip` in both Python environments. This verifies regressions and runtime readiness, not every real app, account operation, or live microphone condition.

**2026-09-27 documentation and follow-up fix:** expanded both README entry points, embedded existing media with provenance, documented current settings/architecture/integrations, and added ongoing documentation requirements. Reviewing the generic project-folder command revealed a remaining hardcoded old folder name; it now uses the configured project roots, with a regression test for a renamed root and a missing first entry. All **318 regression tests passed**, the launcher reported `ready` with no missing assets/dependencies, and all **56 local documentation links, images, and anchors** passed validation.

Earlier implemented work includes streaming speech and direct commands; catalog/project and accessibility controls; local screen-aware planning and coding; Spotify/globe integration; supervisor/checkpoint recovery; adaptive plans and safe alternatives; verified task/UI recall; task dependency checks; sentence speech; the HUD interface; related-code edits and backups; reusable question inference; and the 37 toolkit adapters. Detailed source revisions and historical validation counts remain in the linked integration notes rather than being presented as current reruns.

Historical measurements include approximately 43% less overlay render time in the earlier feature audit and roughly 17% lower warm question latency in a small reusable-worker benchmark. These measure particular components and samples, not an overall task-speed guarantee. See [feature audit](docs/FEATURE_AUDIT.md) and [response speed](docs/gar-response-speed.md) for methods and limitations. Real account-backed toolkit writes were tested with mocked transports; documentation does not claim a live message, event, or repository change occurred.

## Documentation maintenance and attribution

Update this README alongside future changes to features, setup, dependencies, settings, paths, interface, integrations, limitations, or verification. Refresh the parent [repository README](../README.md) when its overview changes. Add current UI media when available; label previews, references and upstream demos accurately. Keep links relative so the documentation works after moving the repository. Date test results and distinguish readiness, regression, synthetic inference, and live checks. These requirements are recorded in [application instructions](AGENTS.md) and [repository instructions](../AGENTS.md).

Reference repositories, retained licenses, and pinned revisions are documented under `docs/` and `integrations/`. Downloaded reference sources do not imply that their entire products run inside Jarvis. The bundled HUD branding/artwork and globe datasets have separate provenance and terms; see [HUD artwork](jarvis/assets/README.md) and [globe data sources](integrations/gods-eye-view-src/gods-eye-view-main/DATA_SOURCES.md). Do not infer a single project-wide license from an upstream reference license.

**2026-09-29 model routing update:** `brain.coder` is set to the locally installed `qwen3-coder:30b` for project code planning/edits and toolkit `write_code`, `improve_code`, and `write_tests` drafts. General task planning, decisions, questions, and vision retain their configured models. Brain setup and model recovery include the coder; missing configured coder models fail coding requests rather than silently switching to another model. The 2026-09-29 regression suite passed 402 tests in the project `.venv`; `python -m jarvis.launcher --check` reported `ready` with no missing assets or dependencies. Model availability was checked with `ollama list`. These are routing, regression, and readiness checks, not a live coding quality benchmark.

**2026-09-29 Obsidian memory update:** Created the local vault and added dated activity notes plus bounded retrieval for questions. The project `.venv` regression suite passed 405 tests, and `python -m jarvis.launcher --check` reported `ready` with no missing assets or dependencies. These are regression and readiness checks, not a live test of continuous desktop activity or answer accuracy.

**2026-09-29 existing-vault connection:** Verified the named Obsidian executable and vault exist, configured `memory.vault` and the Obsidian app launcher, and created `Jarvis Brain.md` plus `Daily/` in the vault without changing its existing files. The 405-test project `.venv` suite passed, launcher readiness reported `ready`, and an integration-check note written to this vault was retrieved successfully. Live desktop capture and answer accuracy still require a running Jarvis session.

**2026-09-29 graph-link follow-up:** Added bidirectional Obsidian links to the existing daily note and automatic links for future daily notes. The Graph view can display these links after reindexing. No Jarvis process was running during this check. The 405-test project `.venv` suite passed and launcher readiness reported `ready`; these verify note-link behavior and startup, not live activity capture.

**2026-09-29 personal-profile memory:** Added a dated personal note to the existing Obsidian vault, linked it to Jarvis Brain, and verified that personal questions retrieve it while an unrelated coding question does not. The vault note remains outside Git. The project `.venv` regression suite passed 406 tests and launcher readiness reported `ready`. This is a retrieval/regression check, not a live spoken-answer check.

**2026-09-29 personalized quick answers:** The project `.venv` regression suite passed 412 tests and `python -m jarvis.launcher --check` reported `ready`. Focused tests exercised the Obsidian profile in the local model prompt, direct greeting/time/date answers without a model call, startup greeting composition, mocked IP weather lookup, saved-city fallback, and cached failure behavior. The direct greeting path completed within one second in the automated test. These are regression/readiness checks; live weather, microphone-to-speech latency, and real startup playback were not verified in this session.

**2026-09-29 everyday bank runtime update:** The project `.venv` regression suite passed 420 tests and launcher readiness reported `ready`. Mocked-service tests covered live-field weather and AQI requests, city time offset, currency rate/date/cache, profile/date/math calculations, and explicit offline behavior. A computed question reached the answer event without Ollama in under one second in an automated worker test. A separate warm direct Ollama API sample (`qwen3.5:4b`, CPU, `think: false`, 80-token cap) took 3.67 seconds; this is one model measurement, not full voice latency. The local environment's proxy rejected live Open-Meteo and Frankfurter requests, so those integrations were not verified live. The five-second target remains unverified for the entire bank.

**Dynamic Island UI (2026-09-30):** Replaced the circular HUD and large command center with a compact black island, 420 ms size transitions, active status bars and temporary answer cards. Clicking opens compact controls with settings on demand. Firecrawl research covered the requested MacDynamic-Island repository, React Bits, SmoothUI and Motion; the native Tk implementation adds no React/Electron dependency and copies no upstream component code. All 432 regression tests passed; hidden UI startup/shutdown and rendered preview generation passed without microphone capture, startup speech or vault writes. Launcher readiness reported `ready`. Animation frame rate and live voice/tasks were not benchmarked. [Design, controls, sources and previews](docs/dynamic-island.md).
