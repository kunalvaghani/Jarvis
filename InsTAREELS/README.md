# Jarvis — local Windows voice assistant

A local Windows assistant using **English-only Whisper medium.en on NVIDIA CUDA**, wake-word activation, concurrent desktop actions, and live dictation. The faster-whisper runtime uses `int8_float16` and was verified on the RTX 3050's 4 GB of VRAM. No API key, audio uploads, or saved microphone recordings.

## Unified task tools

### Desktop actions

Tasks can fill named accessible text fields, scroll an accessible container one page, press supported shortcuts, expand menus/dropdowns, and choose buttons in active modal dialogs. Each action checks the destination before execution and is followed by observation and verification. Examples:

- `fill Search field with robot tutorials`
- `scroll down`
- `press control plus f`
- `open File menu and select Save as`
- `select Cancel in the dialog`

Text entry replaces a field's value without submitting it. Password fields and read-only fields are excluded. Supported shortcuts include Tab, Shift+Tab, Escape, Ctrl+A/F/L/S/Shift+S/C/V/Z/Y, Alt+Left/Right/F/E, arrow keys, Home/End, PageUp/PageDown, and F5. Use named buttons for confirmation and submission. File deletion continues through the file tool's approval flow. Custom interfaces that do not expose UI Automation patterns may still need manual interaction.

The preferred local models are Qwen3.5-4B for planning/decisions and Qwen3-VL-4B for screen interpretation. These are practical local choices for this PC, not a claim of universal benchmark leadership. If a preferred model is missing, the brain can use installed Qwen3-4B/Qwen2.5-3B for text or Qwen3-VL-2B for vision. Planning logs identify the fallback. Once the preferred model is installed, subsequent requests automatically use it. Set `brain.allow_model_fallback` to false to require configured models exactly. Run `verify_desktop_planner.py` with `.venv/Scripts/python.exe` to check live model planning and independent field selection without executing desktop actions. Add `--vision-only` to check the vision model on a synthetic form image.

The autonomous planner receives one shared tool catalog from `jarvis/tools.py`. The same catalog defines its action schema and routes execution to file operations, terminal commands, browser actions, or desktop controls. Direct file work uses file tools; website navigation uses browser tools; visible button selection uses a freshly checked desktop control. Terminal execution and file deletion retain visible user approval. Tool routes appear in the activity log, and dispatch evidence is followed by the existing observation and verification loop before another action runs. Existing direct voice commands remain available.

Firecrawl documentation was used to review browser tool boundaries. This local registry uses Jarvis's existing browser and desktop adapters; the Codex Firecrawl connector is not automatically a credential or browser session available to the Jarvis process.

## Name correction

App names match installed candidates using aliases, spelling edits, swapped letters, and close spoken forms. Examples include `open chrmoe`, `open spoitfy`, and `open kalkulator`. Known website names such as `youtub` resolve to their registered URLs. Button selection compares the requested words with visible enabled control labels, including labels with extra app/site text: `select svae`, `select setings`, or `select contnue`. Jarvis logs the interpreted name. Similar candidates remain numbered choices; unrelated gibberish has no automatic target. Destructive button names are excluded from typo inference.

## Start

If installation is interrupted, double-click **Resume Whisper Setup.cmd** when the connection is stable. It installs the missing packages, resumes the model download, and runs a synthetic-speech GPU check before reporting success.

Requires Windows 10/11, Python 3.10+, and an NVIDIA CUDA GPU with an up-to-date driver. From this folder run:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Then close any older Jarvis window and double-click **Start Jarvis.cmd**. A small orb appears at the top center, just below the camera. Click it to open the control panel, choose your microphone, and click **Start listening**. Click the orb or **Hide** to collapse the panel; right-click the orb for quick controls and Quit. Windows capture exclusion keeps the orb and panel out of supported screenshots. Initial setup downloads CUDA libraries and the ~1.53 GB English Whisper model. Subsequent use is offline. The app verifies CUDA by running inference before starting capture and displays the actual device and precision. It does not silently fall back to CPU. Allow microphone access for desktop apps in Windows Settings if needed.

The input meter should move when you talk. Choose **Microphone Array (Realtek)** to try the laptop microphone, or your headset explicitly, rather than relying on the Windows default. The selection is saved to `config.json`.

Clicking **Start listening** also wakes Jarvis once microphone capture is ready. Wait for **Awake**, then say **“open notepad”** directly; “Jarvis open notepad” also works. After “go to sleep” or 90 seconds of inactivity, say “Jarvis” again. Recognized speech ignored while asleep is explained in the action log. **Microphone off** means you must click Start listening before speaking.

## Whisper settings

`config.json` contains the model path and `whisper` options:

- `device: "cuda"`, `compute_type: "int8_float16"`: GPU inference with quantized weights.
- `partial_interval_seconds: 1.0`: request a new partial transcription about once per second. Actual update delay also depends on GPU decoding time.
- `silence_seconds: 0.8`: finalize after detected speech ends. This does not pause microphone capture.
- `vad_threshold: 0.45`: Silero speech detection threshold. Lower values accept quieter speech but more background noise.
- `language: "en"`: transcribe speech as English without language detection. The English-only `medium.en` model is downloaded by `setup.ps1`.

The installed `models/faster-whisper-small.en` is a smaller, faster English-only fallback. To use it, set `whisper.model` to `small.en`, remove `whisper.repo`, and set `model_path` to `models/faster-whisper-small.en`. Medium.en decoded the included synthetic command in about 0.67 seconds and recognized `notes.txt` directly. Live accuracy depends on the selected microphone, accent, background noise, and phrasing.

Whisper is not a native streaming recognizer. This app continuously captures audio in one worker and decodes rolling hypotheses in another. Silero voice activity detection avoids feeding silence into Whisper. Long speech rolls through overlapping 20-second windows; timestamped words retain the earlier transcript. Pending partial snapshots are replaced by newer ones so they cannot build an ever-growing inference backlog. Completed utterances retain their order. CUDA DLL discovery is scoped to the process; no system PATH or driver changes are made.

## Talk while it works

- “Hey Jarvis open notepad then write here are my ideas for today”
- “Open notepad and write my name is Kunal” — both actions run in order; “and type” also works.
- Keep speaking; stable words stream into the focused destination app, with three words held back for recognition corrections.
- “Stop dictation then create a file called ideas dot txt containing buy milk”
- “Rename file ideas dot txt to shopping dot txt”
- “Delete file shopping dot txt”
- “Jarvis open calculator then open paint”
- “Go to sleep” cancels queued tasks and returns to wake-word listening.

Say **then**, **and then**, or **next command** between tasks to execute completed clauses without ending your speech. Without a separator, a command waits for the speech recognizer's natural endpoint. Dictation streams partial results without requiring a pause. “Stop dictation then …” ends dictation before the next command. Control phrases and “then” are reserved; they cannot be dictated literally in this version. Commands before a spoken separator can already have run, so later corrections cannot undo them.

After an app-opening command, **and write**, **and type**, and **and dictate** also start dictation, including when recognition splits the sentence into separate segments. Ordinary “and” inside dictated text stays literal.

Deletion and renaming wait for a finalized speech segment, even when “then” is spoken; subsequent tasks stay behind them. Each deletion now needs a separate approval dialog showing the exact file path. Approved files go to the Windows Recycle Bin. Silence for 90 seconds returns to wake-word mode. The microphone remains active for wake detection until you click Stop listening, Stop all tasks, or close the window. No background Windows service or startup registration is installed.

## Desktop and files

### Screen-aware autonomous tasks

**Setup:** double-click **Setup Jarvis Brain.cmd**. It creates `.venv-brain` separately from Whisper, installs CPU PyTorch and Laya, downloads the pinned English Laya checkpoint plus the Ollama models configured in `config.json`, and runs synthetic-screen inference checks. Interrupted model downloads can resume by rerunning setup. The feature is not ready until setup and verification finish successfully; existing direct commands continue working while models are missing.

After setup, restart Jarvis. Say **“Jarvis task open YouTube in Chrome”** or type the goal in the bottom box and click **Do task**. Pressing **Enter** routes instructions and questions the same way as speech. Compound instructions such as **“open YouTube and search for how to make robot and play first video”** stay together as a task. This YouTube workflow opens the search directly, observes the results, and selects the requested visible video in screen order. Explicit configured app launches in screen aware tasks run before model planning of the remaining steps. Previously unrecognized finalized commands also go to the planner; known direct commands retain their faster path. **Ask Jarvis** continues to answer questions without desktop actions.

The roles are:

- **Qwen3.5 4B planner:** produces the next supported steps from the currently visible screen.
- **Laya selector:** compares up to eight shortlisted visible control labels plus “none.” Its scores are advisory, not authorization or a guarantee of accuracy.
- **Qwen3.5 4B decision checker:** checks each step against your goal and selects a candidate when needed. A unique exact control name skips Laya's comparison; ambiguous choices require both models to agree. A final check considers the whole goal.
- **Qwen3 VL 4B screen reader:** captures the active destination window after every action, checks whether the expected result is visible, and describes the landed screen to the planner. Jarvis then plans its next action from that screen, keeping a short record of completed actions so it does not repeat them.

All inference runs locally on CPU; Whisper keeps the GPU. Laya stays loaded in a separate process between tasks. The automatic loop supports opening apps/files/folders, websites, browser and music searches, exposed UI controls, creating a new file with spoken content in a named folder, and requesting an app window to close. It cannot activate a button that the app does not expose to Windows UI Automation, type arbitrary text, or use keyboard shortcuts. A new instruction or **Stop all tasks** interrupts the plan.

Examples: **“Jarvis play jazz on YouTube”**, **“Jarvis play my playlist on Spotify”**, **“Jarvis open playlist Focus on Spotify”**, **“Jarvis pause Spotify”**, **“Jarvis resume Spotify”**, **“Jarvis next song on Spotify”**, **“Jarvis previous song on Spotify”**, **“Jarvis shuffle on”**, **“Jarvis repeat one”**, **“Jarvis skip 30 seconds on Spotify”**, **“Jarvis rewind 15 seconds on Spotify”**, **“Jarvis set Spotify volume to 50 percent”**, **“Jarvis mute Spotify”**, and **“Jarvis what's playing on Spotify.”** Spotify search opens the installed Spotify app. Searching alone does not start playback; Jarvis must select a result and verify the playing state. Playback controls use Spotify's Windows media session, and volume controls use Spotify's own audio session; neither targets another app's music. Spotify may require its own login or account permissions. Closing sends the normal window close request, so an app can present a Save prompt. File creation never overwrites an existing file; the spoken folder must be identified unambiguously in the catalog, or you can say **“this folder”** with File Explorer selected.

For projects on D:, say **“Jarvis open project folder”** to open `D:\Phython Project`, **“Jarvis which project was I using”** to hear the last project Jarvis opened (or the most recently active folder it found), or **“Jarvis open my pending project”** for a numbered list of recent project folders. Say **“option two”** or the project name while the list is open. Jarvis then opens that project in File Explorer and Codex, and opens YouTube in Chrome. It remembers projects it opens in `project_memory.json`. Recent file activity is only a clue; Jarvis cannot determine whether work is actually pending. Change `project_roots` in `config.json` to scan other project parent folders.

Only current, revalidated controls can be activated. Invalid plans, ambiguous choices, changed targets, and unverified results stop the loop with an explanation; uncertain clicks are never replayed. Tasks stop after six verified actions. The planner can edit a named UTF-8 text file, or request deletion of one named file in a named folder. Deletion waits for your approval. It can propose a command only when your task asks for command execution; Jarvis displays that command for separate approval before running it. Send/payment/upload/permission actions remain unsupported. Screenshots and labels remain local and are treated as untrusted input. Model verification is fallible; a successful check is not a guarantee that every task succeeded.

After each autonomous action, Jarvis fetches a fresh accessibility snapshot and, with screen awareness enabled, a new screenshot. It waits briefly for a window or control change; if the first visual check catches a loading page, it observes once more. It never repeats the action while waiting. The next step is planned only after the result is verified. Coding tasks similarly read back every created folder, draft, and edited file before moving to the next write. The local task journal records the observation checkpoint.

Run `.\.venv\Scripts\python.exe verify_brain.py` to test all three models against synthetic screens without desktop actions. `--selector-only` checks Laya alone. `brain-worker.log` contains local runtime diagnostics. The model choices are configurable under `brain` in `config.json`.

Run `.\.venv\Scripts\python.exe verify_scenarios.py` for 13 varied synthetic requests, including a real create-and-read check in an isolated temporary folder. `scenario_results.json` records every plan and pass/fail result. Rerun **Setup Jarvis Brain.cmd** if a configured model is missing.

Sources: [Laya model and limitations](https://huggingface.co/convaiinnovations/laya), [Qwen3.5](https://ollama.com/library/qwen3.5). Laya's published model card explicitly warns about zero-shot errors and uncalibrated confidence; the desktop workflow has not been fine-tuned or calibrated on your usage.

### General questions and internet knowledge

Restart Jarvis after updating. Click the orb and **Start listening**, then ask **“Jarvis why is the sky blue?”**, **“explain photosynthesis”**, or **“search the internet for today's technology news”**. Use **“ask …”** for anything that does not begin with a question word. You can also type a question in the panel and click **Ask**; **Preview** remains a preview only. Stop dictation before asking a question.

Answers appear in the transcript log, with a short preview above it, and are spoken aloud. **Speak answers** toggles playback; **Stop voice** interrupts it. English uses the local Piper Alan British male voice for an assistant sound; Hindi uses the local Piper Rohan voice. Both are installed by `setup.ps1`. These are assistant-style voices, not an imitation of an actor's voice. The **Answer language** control selects Auto, English, or Hindi. Auto responds in Hindi to Hindi or Hinglish questions and English to English questions. You can type or say questions such as “mujhe batao gravity kya hai” or “पानी क्यों उबलता है”. Hindi answers use Devanagari for accurate Hindi speech. Source URLs stay in the transcript rather than being read aloud. Voice synthesis runs locally. The microphone ignores speech while Jarvis is speaking so it does not hear its own answer; click **Stop voice** to interrupt playback. Questions run in a separate process and queue, so desktop actions and microphone capture can continue. **Stop all tasks** cancels pending questions and speech. The last three question/answer pairs stay in session memory for follow-ups; say **“forget conversation”** to clear them. This history is not saved to disk.

The local Ollama model **qwen3.5:4b** provides answers. Jarvis starts the installed Ollama server if necessary; it never downloads models automatically. The standard Ollama chat template is used. `knowledge.num_gpu: 0` keeps the LLM on CPU, leaving GPU memory for Whisper. Responses can take several seconds.

### Jarvis command prompt and file edits

Click **Command prompt** in the orb panel, or say **“Jarvis open Jarvis command prompt.”** Enter a Windows command and press **Run**. Jarvis shows the exact command in an approval dialog first, runs it from `JarvisFiles`, and displays its output and exit code. Commands time out after 60 seconds. A command can change or delete files, so review the entire command before approving it. You can also say **“Jarvis run command dir”** or ask a task to run a command.

### Coding in a named project

Jarvis writes the current task and its checkpoints to local `task_state.json`. The record includes the goal, selected project, stages, action targets, window titles, and verification summaries; it does not store screenshots or generated file contents. A crash or restart marks an unfinished task as interrupted. Repeating the same unfinished request gives the planner that history alongside a fresh screen observation, so it can identify what remains. The record never replays old clicks or commands automatically. Only the latest 20 previous tasks and 30 checkpoints per task are retained. Remove `task_state.json` while Jarvis is closed if you want to clear this local history.

Say **“Jarvis code in project Demo: add a greeting function”** or **“Jarvis fix the greeting in project Demo.”** Jarvis finds the named project in `project_roots`, inspects a bounded source file list, plans changes to up to three files, reads those files together for context, and generates complete replacements with the local coding model. It validates Python and JSON syntax, checks for changed files and unexpectedly truncated output, then writes each file. It cannot delete project files through this coding mode. Check the changed files and run the project's tests yourself; syntax checks alone cannot establish that generated code works. Say **“Jarvis open project Demo”** or **“Jarvis list projects”** to find the project name. Run `python verify_coder.py` for a synthetic, no-write model check.

With the destination folder open in File Explorer, say **“Jarvis modify kunal.py to add a UI”** or **“Jarvis create a tools folder and a Python script.”** You do not need to say the folder name: Jarvis uses the open Explorer folder, reports its source files, and reads the existing file before editing it. If an edit names a file that is missing or appears in multiple subfolders, Jarvis reports the available paths instead of creating a different file. Jarvis can plan up to three new folders and three files inside that folder. It creates folders and draft files first, then generates or edits source. A failed generation leaves a recognizable draft that can be resumed. Existing files are changed only after the generated replacement passes validation. It will not delete files as part of a coding plan. Run `python verify_coder.py --workflow-smoke` to test folder creation, script creation, and a follow-up script edit in a temporary folder.

For a new standalone Python file, open its destination in File Explorer and say **“Jarvis create a Python file with calculator code in it.”** Jarvis uses the selected folder and chooses `calculator.py` from the stated purpose. It first creates a visible draft, writes the code into that file, then checks the result. For a basic calculator it runs arithmetic and division-by-zero checks. For other Python requests it generates code with the local model and checks syntax; a failed generation leaves a draft that Jarvis can resume on the next attempt. It does not overwrite an existing user file. You can name the file explicitly as well.
**“Jarvis create Python code for calculator in TestCodes project folder”** also works when the selected Explorer folder is `TestCodes`; Jarvis checks the spoken folder name against the selected folder before writing. Restart Jarvis after installing code updates so its running process loads the new behavior.

For a direct text edit in `JarvisFiles`, say **“Jarvis modify file notes dot txt replace old with new.”** This changes one exact match and stops if the old text appears zero or multiple times. Say **“Jarvis overwrite file notes dot txt with content new text”** to replace the complete file. For a task in another folder, name the folder and file; Jarvis will not infer an unnamed destination. **“Jarvis delete file notes dot txt”** asks for approval of that exact path before moving it to the Recycle Bin.

### Questions about your screen

Open the app you want Jarvis to inspect, then ask **“What is on my screen?”**, **“What does this error mean?”**, or **“Screen pe kya dikh raha hai?”**. You can also click the orb, type a question, and press **Ask screen**. Jarvis briefly hides both the panel and orb, captures the last active external window, then restores the orb. It reads visible text with local OCR and sends the screenshot to the local **qwen3-vl:4b** vision model. The screenshot stays in memory and is not sent to a web search service or saved to disk. The window title appears in the action log so you can see which app it read.

Screen answers describe one frame at question time. They can read visible text and describe images, but cannot reliably infer motion, hidden content, or what happened earlier. Screen content is treated as untrusted input and cannot trigger desktop actions. Run **Setup Jarvis Brain.cmd** if the vision model is missing; it downloads the model configured in `knowledge.screen_model`.

Explicit searches and questions about current information use public web search; otherwise the local model decides whether it needs web verification. This uncertainty decision is imperfect. Say **“search the internet for …”** to force a check. Search sends the question (up to 500 characters) to the search providers; audio, the PC catalog, button memory, and conversation history are not uploaded. Answers use search snippets and list their source URLs, rather than claiming full-page research. Offline/search failures are shown clearly. Set `knowledge.internet` to `false` for offline-only use, or `knowledge.enabled` to `false` to disable question answering. The LLM and web results cannot issue desktop actions.

Implementation references: [Ollama chat API](https://docs.ollama.com/api/chat), [raw generation API](https://docs.ollama.com/api/generate), [DDGS search library](https://pypi.org/project/ddgs/).

### Remembered button choices

Jarvis saves successful selections made **through Jarvis** in local `ui_memory.json`, scoped to the app executable and window title. It does not monitor manual mouse clicks. While awake and listening, it checks periodically for a remembered, currently available option when you return to a screen. It shows **“Use it again? Say yes or no.”** Answer **“yes”** to select it, or **“no”** to see alternatives and then say **“select option two”** or **“select [name]”**. Suggestions appear on screen; they are not spoken aloud.

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

Exact labels win over longer labels. Multiple matches produce numbered choices in the action log. Choices expire after 45 seconds and are invalidated when the window or available controls change. Clicking waits for finalized speech. UI calls run in an isolated worker with cancellation and a timeout so a stuck app cannot block microphone capture. If dictating, say “stop dictation” before giving a selection command.
Ordinal and pointer-based choices rely on visible accessibility controls. Jarvis avoids destructive controls in inferred selections; name a control explicitly when that is your intent. If a video page does not expose usable video links, Jarvis asks you to choose another way.

### PC catalog

`config.json` now contains discovered Windows applications, Start Menu shortcuts, executable registrations, and named folders. `file_catalog.json` contains file and folder paths from the PC scan; `file_catalog.sqlite3` accelerates lookups without loading millions of aliases into memory. `config.before-pc-scan.json` preserves the configuration from before the first scan. `scan_report.json` records counts, exclusions, and inaccessible paths.

Examples: **“open chrome”**, **“open blender”**, **“open visual studio code”**, **“open folder downloads”**, **“open file filename dot pdf”**. If names are duplicated, choose a numbered candidate, say the parent folder followed by the filename, or add a unique name under `files` in `config.json`, mapping it to the full path.

Double-click **Refresh PC Catalog.cmd** after installing apps or moving files, then restart Jarvis. The scan reads names and paths, not document contents. It skips Windows internals, AppData, ProgramData, dependency/cache folders, and reparse points/junctions, and records permission-denied locations. It does not claim to index every protected or cached file. Direct file creation, rename, edit, and deletion use `files_root`; a multi-step task can create, edit, or request deletion of a single file in a named folder. Deletion always opens an approval dialog. File edits require UTF-8 text and either one exact snippet to replace or an explicit full overwrite.

Some packaged apps launch through Windows shell IDs. For those apps, select the text field and say “stop dictation, then write …” before dictating; their actual destination process cannot reliably be inferred from the launcher.

Notepad, Calculator, Paint, and File Explorer are configured. Add apps as executable argument arrays in `config.json`, for example `"my editor": ["C:\\Path\\Editor.exe"]`. Commands never become shell scripts.

Click the app's text field before saying “Jarvis write …”, or open Notepad by voice first. Typing is bound to the initial foreground window and stops if focus changes. After a typing error, say “stop dictation”, select the destination, and restart. Moving the pointer to a screen corner triggers the typing fail-safe. Some elevated or custom apps reject simulated typing.

Each fresh dictation command selects the currently focused app, except when it follows an app-open command: that sequence retains the verified opened window. To switch apps during ongoing dictation, say “stop dictation”, click the new text field, and say “write …”.

File operations are restricted to the configured `files_root` (default `JarvisFiles`). They target single filenames, never folders. “Dot txt” becomes `.txt`; a missing extension defaults to `.txt`. Creation and rename never overwrite existing files. To choose another folder, edit `files_root` in `config.json`. Voice cannot expand that scope.

`microphone` may be an input device index or device name. List available devices:

```powershell
.\.venv\Scripts\python.exe -m sounddevice
```

Whisper recognition still depends on the microphone, noise, accent, and overlapping speakers. Wake recognition is speech-to-text matching, not speaker authentication. The app shows Whisper's original punctuation in the transcript but normalizes case and command punctuation before passing text to the existing command engine. Dictated text currently uses that normalized form too. Transcript history is memory-only and capped in the UI.

## God's Eye View

Say **“Jarvis open God's Eye View”** to start Bilawal Sidhu's local 3D Earth console and open it in Chrome. You can also say **“open God's Eye View in Edge”**. Jarvis starts the console only on request; the local server stops when Jarvis closes. The installed source is under `integrations/gods-eye-view-src/gods-eye-view-main`. While its browser window is active, Jarvis's existing screen questions can describe the visible view. The globe's own analyst and voice features need a separate OpenAI API key; no key is configured by this integration. Public data layers work without one. The globe adds spatial data and does not replace Jarvis's local Qwen planner or Laya selector.

God's Eye View's source code is [MIT licensed](https://github.com/bilawalsidhu/gods-eye-view/blob/main/LICENSE). Its bundled assets and third-party data retain [separate terms](https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md). The installed local copy can be updated from [upstream](https://github.com/bilawalsidhu/gods-eye-view); run `npm ci` in its folder after an update. It uses Node 24.14 or newer.

## Silent startup and recovery

### Task failure recovery

`brain.task_recovery` is enabled. Missing controls, unavailable dialogs and stale targets detected before dispatch are recorded as not executed. Jarvis takes a fresh observation and asks the existing Qwen planner for a different supported approach. The alternative plan still passes the normal goal, filename, exact text, command and approval checks; failed actions are blocked. Recovery is limited to two alternative plans within the six-iteration task budget.

Tool exceptions and results that cannot be verified are recorded as uncertain and pause the task, since an external effect may already have happened. Decision-model rejection, sensitive controls and missing approval never trigger an alternate route around those checks. Failure history survives in `task_state.json` and is supplied when revisiting the same unfinished goal. Repair messages stay in the transcript; no new background service or dependency is needed.

Research through Firecrawl used agent feedback and bounded stopping patterns described in [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

### Adaptive planning

`brain.adaptive_planning` is enabled in `config.json`. For unified tool tasks, Jarvis breaks the goal into executable tasks, performs one action, observes and verifies its result, then revises the remaining tasks using the original goal, current screen, completed results and action budget. The planner can remove unnecessary tasks, reorder remaining tasks or add a newly needed navigation step. Completion still requires an independent check against the full goal.

Remaining tasks, verified results and bounded revision history are saved in `task_state.json`. After a crash they are context for a fresh observation, never an automatic replay queue. An uncertain result or failed replanning pauses the task; completed actions are not repeated. The existing coding workflow separately validates generated files before committing them. No new model or background service is required: replanning uses the configured Qwen planner inside the existing supervised inference worker. Six external actions per task remain the limit.

Research through Firecrawl: [OPEA's plan/execute/replan workflow](https://github.com/opea-project/GenAIComps/blob/8130a3fb9cd8f2fcef8eff6657844e11ddf63d71/comps/agent/src/integrations/strategy/planexec/README.md).

Double-click **Start Jarvis.cmd** to start the hidden, single-instance supervisor and Jarvis with listening enabled. **Stop Jarvis.cmd** or Jarvis's Quit command stops supervision and owned repair downloads. Stopping only the microphone leaves the other service checks running and keeps the microphone stopped after an unrelated crash.

The background watchdog checks the interface heartbeat, microphone/decoder, action and question threads, speech thread, Ollama, configured Ollama models, and God's Eye's local server after it has been requested. Repairs use hidden processes and appear only as `REPAIR` messages in the transcript. Logs and startup snapshots are stored under `.jarvis-runtime`; no repair notifications are spoken. Recovery does not launch or reopen unrelated user apps.

Startup checks restore missing declared Python dependencies and model assets. Invalid Jarvis source syntax or configuration can be restored from a previous startup snapshot, preserving the damaged copy. A separate standard-library bootstrap can restore the supervisor's entry point before importing it. These snapshots verify syntax, not program behavior: recovery cannot invent fixes for arbitrary logic bugs, reinstall Windows/Python/drivers, or recover its bootstrap if that file itself is damaged. Repairs needing a network connection retry with backoff. Stop interrupts owned setup processes.

Crashes preserve task checkpoints and pause unfinished work. File writes, shell commands, clicks, and shortcuts are never replayed automatically after an uncertain failure. Resume a task using the fresh screen/file state. File deletion and command approval remain in place; normal task approval dialogs are separate from silent repair.

`runtime_manifest.json` declares runtime dependencies; `AGENTS.md` requires future upgrades to maintain the launcher and recovery registrations together. Check syntax, configuration, dependency imports and local model files without starting the interface:

```powershell
.\.venv\Scripts\python.exe -m jarvis.launcher --check
```

The recovery design follows [Supervisor's process states and retry behavior](https://supervisord.org/subprocess.html) and [Ollama's service configuration](https://docs.ollama.com/faq). Research also included [Supervisor's restart discussion on GitHub](https://github.com/Supervisor/supervisor/issues/212) and [a Python background watchdog discussion on Reddit](https://www.reddit.com/r/Python/comments/42oy0x/running_watchdog_in_the_background/).

## Verification commands

Jarvis adapts Ultron's memory decay code for recent successful UI suggestions
and recalls compact summaries of related verified tasks when planning. This
runs locally with the existing task history and dependencies. See
[Ultron integration and attribution](docs/ultron-integration.md) for scope,
license, and validation details.

Spoken replies are enabled in the saved settings. Jarvis uses conversational
answer wording and the installed British male Piper voice, playing sentences
as they are synthesized. Stop voice interrupts playback; repair notices stay
silent. Microsoft JARVIS dependency checks now validate related task steps.
See [planning and speech integration details](docs/jarvis-repository-integrations.md)
for source attribution, settings, and the voice preview.

The launcher now uses the animated J.A.R.V.I.S. HUD logo in a draggable dock.
Click it to open a modern command center with conversation and voice settings.
See [HUD interface](docs/hud-interface.md) for controls, artwork attribution,
and a rendered layout preview.

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

```powershell
python -m unittest discover -s tests -v
.\.venv\Scripts\python.exe verify_whisper.py --audio tests\fixtures\jarvis-command.wav
.\.venv\Scripts\python.exe verify_brain.py
.\.venv\Scripts\python.exe verify_scenarios.py
.\.venv\Scripts\python.exe verify_speech.py
.\.venv\Scripts\python.exe verify_ui.py
python verify_coder.py --workflow-smoke
.\.venv\Scripts\python.exe main.py
```

The **Preview text command** box accepts a full “Jarvis …” sentence and displays planned actions without executing them. Automated tests cover streaming, duplicate prevention, wake gating, explicit deletion, cancellation, and filesystem restrictions. Live microphone accuracy and typing into your chosen apps need a spoken trial on your PC.

`verify_whisper.py` loads the configured model, executes GPU inference, prints the recognized text, timing, and planned commands, and never executes desktop actions. The included WAV is synthetic test speech, not a recording of the user. Unit tests cover punctuation normalization, overlap stitching, backpressure, cancellation during inference, plus the existing file and typing restrictions.

References: [faster-whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu), [English-only medium.en conversion used here](https://huggingface.co/Systran/faster-whisper-medium.en), and [Silero integration](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/vad.py). Desktop control uses the Windows API directly.
