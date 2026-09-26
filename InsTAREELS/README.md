# Jarvis — local Windows voice assistant

A local Windows assistant using **English-only Whisper medium.en on NVIDIA CUDA**, wake-word activation, concurrent desktop actions, live dictation, local Qwen planning and vision, Piper speech, and a draggable animated HUD. The faster-whisper runtime uses `int8_float16` and was verified on the RTX 3050's 4 GB of VRAM. Core local inference needs no API key and does not upload microphone audio or save microphone recordings. Web tools and optional account services use network requests and may require credentials.

**Documentation updated: 2026-09-27.** The application is in this `InsTAREELS` directory, inside the parent Jarvis repository. All commands below run from this directory unless stated otherwise.

## Images and media

![Jarvis command center rendered layout preview](artifacts/jarvis-hud-preview.png)

The current dark/cyan command center includes the HUD logo, microphone status, replies, conversation, voice settings, question/task input, terminal, preview, files, and Stop/Quit controls. This image is a rendered layout preview with sample conversation, not a live desktop screenshot. [HUD controls and preview generation](docs/hud-interface.md).

![Bundled animated HUD reference artwork](jarvis/assets/jarvis-reference.gif)

This bundled reference animation supplies the cropped circular logo used by the HUD renderer. It is third-party artwork; see [asset provenance](jarvis/assets/README.md). A [static reference image](artifacts/reference-logo.png), [earlier reference UI](integrations/reference-jarvis-ui.png), and [reference cover](integrations/reference-jarvis-cover.jpg) are also retained; they are reference material rather than screenshots of the current Jarvis panel.

[Listen to the installed English voice preview](artifacts/jarvis-voice-preview.wav). The sample uses the local Piper voice and is not a microphone recording.

## Contents

- [Capabilities](#capabilities-at-a-glance)
- [Setup and launch](#start)
- [Speech recognition settings](#whisper-settings)
- [Voice commands and dictation](#talk-while-it-works)
- [Desktop, files, questions, and coding](#desktop-and-files)
- [God's Eye View](#gods-eye-view)
- [Recovery and adaptive planning](#silent-startup-and-recovery)
- [Integrations and toolkits](#integrations-and-toolkits)
- [Autonomous toolkit use](#autonomous-toolkit-use)
- [Architecture and project layout](#architecture-and-project-layout)
- [Configuration and relocation](#configuration-and-relocation)
- [Troubleshooting](#troubleshooting)
- [Verification](#verification-commands)
- [Current validation and update history](#current-validation-and-update-history)
- [Documentation maintenance and attribution](#documentation-maintenance-and-attribution)

## Capabilities at a glance

| Area | Current behavior |
| --- | --- |
| Voice input | English Whisper on CUDA, wake gating, Silero VAD, overlapping transcription, live dictation, and cancellation. |
| Interface | Draggable animated launcher, command center, transcript, voice/settings controls, text input, and preview mode. |
| Questions and screen understanding | Local Qwen answers, optional web research, English/Hindi replies, and local vision of the destination window. |
| Desktop and browser | App/site launching, searches, exposed control selection, exact text-field filling, scrolling, supported shortcuts, menus, and dialogs. |
| Files and projects | Scoped file creation/editing, approved deletion, catalog lookup, project discovery, recent-project memory, and Explorer context. |
| Coding | Related-source context, bounded multi-file work, exact replacements, syntax checks, original-byte backups, diffs, atomic per-file writes, and readback. |
| Task execution | Shared tool registry, dependency checks, independent decisions, observations, verification, adaptive replanning, and bounded safe alternatives. |
| Memory | Durable checkpoints, related verified task summaries, and decaying successful UI suggestions. |
| Speech output | Local British male English and Hindi Piper voices, sentence playback, interruption, and recognition mute during replies. |
| Media and globe | Spotify session controls and on-demand God's Eye View browser console. |
| Toolkits | 52 registered operations: 15 core tools plus 37 toolkit operations; provider tools become available only when configured. |
| Recovery | Hidden single-instance supervisor, worker/service health checks, startup snapshots, bounded retries, and explicit-stop handling. |

Local models do not make every task reliable. Custom/elevated apps may not expose usable controls; ambiguous targets require clarification. External writes and deletion use the applicable approval flow, and uncertain effects are never automatically replayed.

### Task questions and option replies

A plain file request such as **“open folder Downloads, create a file called JarvisTest .txt there and write hello kunal in it”** uses an exact file plan, preserves the filename/content, and resolves Downloads before launching or writing. It does not require selecting an Explorer folder or enter code generation just because the request mentions a folder. Full existing destination paths can be resolved without a catalog refresh.

When an essential detail is missing, Jarvis displays and speaks a task question, retains the original goal, and waits for an answer for up to three minutes. For a missing destination, reply **“Downloads”** or a full folder path. A short answer continues the paused task rather than becoming a general question; a new explicit command/question replaces it. Stop/cancel clears the question. Verified progress is retained, and an answer cannot replay an action whose result is uncertain.

For an offered file/app, project or UI list, reply **“one,” “the second one,” “option two,”** or the exact displayed name. UI selections still validate the current window and controls. File/app/UI lists expire after 45 seconds; project lists and task questions after three minutes. Invalid numbers preserve the offered choices; expired replies ask you to repeat the request for a fresh list. These flows do not grant deletion, command or account-write approval.

## Hardware and current models

On this PC (Ryzen 7 5800H, 32 GB RAM, RTX 3050 Laptop with 4 GB VRAM), keep **Qwen3.5 4B** for planning, decisions, code and answers, **Qwen3-VL 4B** for screen vision, and the pinned English **Laya** checkpoint for control ranking. Ollama and Laya use CPU; Whisper **medium.en** uses CUDA `int8_float16`. Piper supplies the English/Hindi voices. Laya's candidate suggestion still needs independent Qwen agreement for ambiguous controls.

The 2026-09-27 comparison found all three installed vision candidates passed two synthetic field-verification checks each; that limited evidence does not justify switching the stack. Very large models in the supplied screenshots exceed practical local memory; smaller 7–14B alternatives can fit RAM in isolation but need end-to-end evaluation before replacement. [Hardware, model sizes, timings, sources and limitations](MODEL_AUDIT.md), [raw comparison results](artifacts/hardware-model-comparison.json). No model configuration changed.

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

Install Ollama before running **Setup Jarvis Brain.cmd** for local questions and screen-aware planning. That setup creates the separate brain environment, installs CPU inference dependencies, downloads the configured planning/vision and Laya models, and verifies them. A fresh installation needs internet access for these downloads. The optional God's Eye console also needs Node 24.14+ and `npm ci` in `integrations/gods-eye-view-src/gods-eye-view-main`.

Then close any older Jarvis window and double-click **Start Jarvis.cmd**. The draggable animated HUD launcher opens the command center when clicked. Choose your microphone and click **Start listening** if listening is off. Click the launcher or **Hide** to collapse the panel; right-click the launcher for quick controls and Quit. The panel logo also toggles listening; Escape hides the panel, while **Quit Jarvis** actually stops supervision. Windows capture exclusion keeps the launcher and panel out of supported screenshots. Initial setup downloads CUDA libraries and the ~1.53 GB English Whisper model. Core inference subsequently works offline; web research and online services require connectivity. The app verifies CUDA by running inference before starting capture and displays the actual device and precision. It does not silently fall back to CPU. Allow microphone access for desktop apps in Windows Settings if needed.

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

Brain and question inference use the local CPU configuration; Whisper keeps the GPU. Laya stays loaded in a separate process between tasks. The automatic loop supports opening apps/files/folders, websites, browser and music searches, exposed UI controls, exact text-field filling, scrolling, supported shortcuts, menus/dialogs, creating a new file with spoken content in a named folder, and requesting an app window to close. It cannot activate controls that the app does not expose to Windows UI Automation; text entry and shortcuts must pass the supported tool's destination checks. A new instruction or **Stop all tasks** interrupts the plan.

Examples: **“Jarvis play jazz on YouTube”**, **“Jarvis play my playlist on Spotify”**, **“Jarvis open playlist Focus on Spotify”**, **“Jarvis pause Spotify”**, **“Jarvis resume Spotify”**, **“Jarvis next song on Spotify”**, **“Jarvis previous song on Spotify”**, **“Jarvis shuffle on”**, **“Jarvis repeat one”**, **“Jarvis skip 30 seconds on Spotify”**, **“Jarvis rewind 15 seconds on Spotify”**, **“Jarvis set Spotify volume to 50 percent”**, **“Jarvis mute Spotify”**, and **“Jarvis what's playing on Spotify.”** Spotify search opens the installed Spotify app. Searching alone does not start playback; Jarvis must select a result and verify the playing state. Playback controls use Spotify's Windows media session, and volume controls use Spotify's own audio session; neither targets another app's music. Spotify may require its own login or account permissions. Closing sends the normal window close request, so an app can present a Save prompt. File creation never overwrites an existing file; the spoken folder must be identified unambiguously in the catalog, or you can say **“this folder”** with File Explorer selected.

For projects on D:, say **“Jarvis open project folder”** to open the first available configured project root (currently `D:\Kunals GitHub Repo`), **“Jarvis which project was I using”** to hear the last project Jarvis opened (or the most recently active folder it found), or **“Jarvis open my pending project”** for a numbered list of recent project folders. Say **“option two”** or the project name while the list is open. Jarvis then opens that project in File Explorer and Codex, and opens YouTube in Chrome. It remembers projects it opens in `project_memory.json`. Recent file activity is only a clue; Jarvis cannot determine whether work is actually pending. Change `project_roots` in `config.json` to scan other project parent folders.

Only current, revalidated controls can be activated. Invalid plans, ambiguous choices, changed targets, and unverified results stop the loop or enter the bounded recovery path when failure is known to precede execution; uncertain clicks are never replayed. Tasks have a six-action budget. The planner can edit a named UTF-8 text file, or request deletion of one named file in a named folder. Deletion waits for your approval. It can propose a command only when your task asks for command execution; Jarvis displays that command for separate approval before running it. Generic desktop payment/upload/permission actions are unsupported. Configured toolkit adapters separately support selected account sends and remote writes with destination/content approval; see the toolkit guide. Screenshots and labels remain local and are treated as untrusted input. Model verification is fallible; a successful check is not a guarantee that every task succeeded.

After each desktop action, Jarvis fetches a fresh accessibility snapshot and, with screen awareness enabled, a new screenshot. Toolkit operations instead verify their returned data or service acknowledgement and supply the verified result to planning. It waits briefly for a window or control change; if the first visual check catches a loading page, it observes once more. It never repeats the action while waiting. The next step is planned only after the result is verified. Coding tasks similarly read back every created folder, draft, and edited file before moving to the next write. The local task journal records the observation checkpoint.

Run `.\.venv\Scripts\python.exe verify_brain.py` to test all three models against synthetic screens without desktop actions. `--selector-only` checks Laya alone. `brain-worker.log` contains local runtime diagnostics. The model choices are configurable under `brain` in `config.json`.

Run `.\.venv\Scripts\python.exe verify_scenarios.py` for 13 varied synthetic requests, including a real create-and-read check in an isolated temporary folder. `scenario_results.json` records every plan and pass/fail result. Rerun **Setup Jarvis Brain.cmd** if a configured model is missing.

Sources: [Laya model and limitations](https://huggingface.co/convaiinnovations/laya), [Qwen3.5](https://ollama.com/library/qwen3.5). Laya's published model card explicitly warns about zero-shot errors and uncalibrated confidence; the desktop workflow has not been fine-tuned or calibrated on your usage.

### General questions and internet knowledge

Restart Jarvis after updating. Click the HUD launcher and **Start listening**, then ask **“Jarvis why is the sky blue?”**, **“explain photosynthesis”**, or **“search the internet for today's technology news”**. Use **“ask …”** for anything that does not begin with a question word. You can also type a question in the panel and click **Ask**; **Preview** remains a preview only. Stop dictation before asking a question.

Answers appear in the transcript log, with a short preview above it, and are spoken aloud. **Speak answers** toggles playback; **Stop voice** interrupts it. English uses the local Piper Alan British male voice for an assistant sound; Hindi uses the local Piper Rohan voice. Both are installed by `setup.ps1`. These are assistant-style voices, not an imitation of an actor's voice. The **Answer language** control selects Auto, English, or Hindi. Auto responds in Hindi to Hindi or Hinglish questions and English to English questions. You can type or say questions such as “mujhe batao gravity kya hai” or “पानी क्यों उबलता है”. Hindi answers use Devanagari for accurate Hindi speech. Source URLs stay in the transcript rather than being read aloud. Voice synthesis runs locally. The microphone ignores speech while Jarvis is speaking so it does not hear its own answer; click **Stop voice** to interrupt playback. Questions run in a separate process and queue, so desktop actions and microphone capture can continue. **Stop all tasks** cancels pending questions and speech. The last three question/answer pairs stay in session memory for follow-ups; say **“forget conversation”** to clear them. This history is not saved to disk.

The local Ollama model **qwen3.5:4b** provides answers. Jarvis starts the installed Ollama server if necessary; it never downloads models automatically. The standard Ollama chat template is used. `knowledge.num_gpu: 0` keeps the LLM on CPU, leaving GPU memory for Whisper. Responses can take several seconds.

### Jarvis command prompt and file edits

Click **Terminal** in the command center, or say **“Jarvis open Jarvis command prompt.”** Enter a Windows command and press **Run**. Jarvis shows the exact command in an approval dialog first, runs it from `JarvisFiles`, and displays its output and exit code. Commands time out after 60 seconds. A command can change or delete files, so review the entire command before approving it. You can also say **“Jarvis run command dir”** or ask a task to run a command.

### Coding in a named project

Jarvis writes the current task and its checkpoints to local `task_state.json`. The record includes the goal, selected project, stages, action targets, window titles, and verification summaries; it does not store screenshots or generated file contents. A crash or restart marks an unfinished task as interrupted. Repeating the same unfinished request gives the planner that history alongside a fresh screen observation, so it can identify what remains. The record never replays old clicks or commands automatically. Only the latest 20 previous tasks and 30 checkpoints per task are retained. Remove `task_state.json` while Jarvis is closed if you want to clear this local history.

Say **“Jarvis code in project Demo: add a greeting function”** or **“Jarvis fix the greeting in project Demo.”** Jarvis finds the named project in `project_roots`, inspects a bounded source file list, plans changes to up to three files, reads those files together for context, and generates complete replacements with the local coding model. It validates Python and JSON syntax, checks for changed files and unexpectedly truncated output, then writes each file. It cannot delete project files through this coding mode. Check the changed files and run the project's tests yourself; syntax checks alone cannot establish that generated code works. Say **“Jarvis open project Demo”** or **“Jarvis list projects”** to find the project name. Run `python verify_coder.py` for a synthetic, no-write model check.

With the destination folder open in File Explorer, say **“Jarvis modify kunal.py to add a UI”** or **“Jarvis create a tools folder and a Python script.”** You do not need to say the folder name: Jarvis uses the open Explorer folder, reports its source files, and reads the existing file before editing it. If an edit names a file that is missing or appears in multiple subfolders, Jarvis reports the available paths instead of creating a different file. Jarvis can plan up to three new folders and three files inside that folder. It creates folders and draft files first, then generates or edits source. A failed generation leaves a recognizable draft that can be resumed. Existing files are changed only after the generated replacement passes validation. It will not delete files as part of a coding plan. Run `python verify_coder.py --workflow-smoke` to test folder creation, script creation, and a follow-up script edit in a temporary folder.

For a new standalone Python file, open its destination in File Explorer and say **“Jarvis create a Python file with calculator code in it.”** Jarvis uses the selected folder and chooses `calculator.py` from the stated purpose. It first creates a visible draft, writes the code into that file, then checks the result. For a basic calculator it runs arithmetic and division-by-zero checks. For other Python requests it generates code with the local model and checks syntax; a failed generation leaves a draft that Jarvis can resume on the next attempt. It does not overwrite an existing user file. You can name the file explicitly as well.
**“Jarvis create Python code for calculator in TestCodes project folder”** also works when the selected Explorer folder is `TestCodes`; Jarvis checks the spoken folder name against the selected folder before writing. Restart Jarvis after installing code updates so its running process loads the new behavior.

For a direct text edit in `JarvisFiles`, say **“Jarvis modify file notes dot txt replace old with new.”** This changes one exact match and stops if the old text appears zero or multiple times. Say **“Jarvis overwrite file notes dot txt with content new text”** to replace the complete file. For a task in another folder, name the folder and file; Jarvis will not infer an unnamed destination. **“Jarvis delete file notes dot txt”** asks for approval of that exact path before moving it to the Recycle Bin.

### Questions about your screen

Open the app you want Jarvis to inspect, then ask **“What is on my screen?”**, **“What does this error mean?”**, or **“Screen pe kya dikh raha hai?”**. You can also click the HUD launcher, type a question, and press **Ask screen**. Jarvis briefly hides both the panel and HUD launcher, captures the last active external window, then restores the launcher. It reads visible text with local OCR and sends the screenshot to the local **qwen3-vl:4b** vision model. The screenshot stays in memory and is not sent to a web search service or saved to disk. The window title appears in the action log so you can see which app it read.

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

![God's Eye View upstream demonstration](integrations/gods-eye-view-src/gods-eye-view-main/docs/media/hero-open-source-reveal.gif)

Bundled upstream demonstration, not a screenshot of a verified Jarvis task. Additional globe demos are available in the [upstream media guide](integrations/gods-eye-view-src/gods-eye-view-main/docs/media/README.md). Some showcased layers or analyst features have separate data/API requirements.

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

## Integrations and toolkits

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

| Integration | What Jarvis uses | Reference and attribution |
| --- | --- | --- |
| Ultron | Adapted time-decay ranking and compact recall of verified task summaries; no upstream server at runtime. | [Memory adaptation](docs/ultron-integration.md), retained Apache-2.0 license. |
| Microsoft JARVIS | Adapted dependency validation for task IDs; execution stays sequential. | [Planning integration](docs/jarvis-repository-integrations.md), retained MIT license. |
| isair/jarvis | Inspected voice design; independently implemented conversational speech and sentence playback using installed Piper voices. | [Speech integration](docs/jarvis-repository-integrations.md), reference license retained; no upstream runtime source copied. |
| Jarvis HUD reference | Bundled reference animation cropped by the renderer; independently built Tk command center. | [HUD](docs/hud-interface.md) and [artwork provenance](jarvis/assets/README.md). |
| agenticSeek | Related-source discovery, exact replacement validation, bounded feedback, and coding review artifacts. | [Coding improvements](docs/agenticseek-integration.md), retained GPLv3 reference license; no imported upstream runtime. |
| General-Agent-Runtime | Reusable hidden question worker and removal of duplicate model discovery overhead. | [Response speed measurements](docs/gar-response-speed.md); configured models unchanged. |
| SuperAGI | Independently implemented file/resource/coding/web/GitHub/account adapters. | [Toolkit guide](docs/superagi-toolkits.md), retained MIT reference license. |
| God's Eye View | Separate on-demand local 3D Earth console. | [Installed source](integrations/gods-eye-view-src/gods-eye-view-main/README.md), MIT code and separate data/asset terms. |

Toolkit groups include file listing/reading/appending/search, local resource and knowledge search, thinking/specification/test/code drafts, public web search/static scraping, GitHub reads/reviews/approved writes, email, Google Calendar, Jira, Apollo, Slack, and X. Of the 37 added operations, 19 require no account credentials and 18 need environment configuration. No-credential web operations still need network access. Coding drafts are returned for review; the project coding workflow performs checked writes.

Use **“list toolkits”** to inspect required environment variable names before launch. Provider credentials are not supplied by Codex plugins, and OAuth acquisition/refresh is not automated. See the guide for exact payloads, approvals, and current adapter limits. Email attachments, Instagram publishing, image generation, SuperAGI agent spawning, and its full service stack are not implemented by these adapters.

## Autonomous toolkit use

Jarvis chooses and combines toolkit operations from the given goal; you do not need to specify tool names. Initial planning, adaptive replanning and recovery now see every configured operation rather than a keyword-filtered subset. There are **34 available operations without account credentials**, and **52 when all required provider configuration is present**. The 18 account-backed operations still need their environment variables.

Verified tool results feed the next decision, remaining plan and final goal check. File/API/draft results are checked directly instead of requiring a desktop screenshot. Unknown URLs, IDs, SHAs or source text should be discovered by a prerequisite read, followed by replanning. Full result context stays in current-task memory with bounded/truncated input; durable checkpoint summaries stay compact. The configured models are unchanged; planning context is expanded to 16,384 tokens for the full catalog and observations.

Examples:

- `task find useful public sources about Python asyncio and compare the main tradeoffs`
- `read file source.txt in Demo and draft tests for its functions`
- `task check my upcoming calendar meetings and draft a preparation checklist`
- `task review pull request 12 in GitHub repository owner/repository`
- `task research Python asyncio and email a summary to recipient@example.com`

External messages and remote changes require the appropriate account configuration and visible approval of the destination and exact payload. Drafting does not save or execute code. Every initial and revised plan checks write intent, while failure/cancellation blocks dependent actions and uncertain effects are never replayed. The six-action budget is unchanged. See [autonomous toolkit details](docs/superagi-toolkits.md#autonomous-planning-and-chaining).

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
    Questions --> Reply[Transcript and Piper sentence playback]
    Verify --> Reply
    Supervisor[Bootstrap, launcher and watchdog] --> Brain
    Supervisor --> Questions
    Supervisor --> Input
```

Planning, observation and inference can retry within their defined bounds; external actions cannot be replayed after uncertainty. Task history informs planning and is never an executable replay queue. Question work and speech use separate workers so desktop tasks and capture can continue.

```text
Jarvis/
  README.md                     Repository entry point
  AGENTS.md                     Documentation maintenance instructions
  InsTAREELS/
    README.md                   Complete application guide
    AGENTS.md                   Runtime and documentation requirements
    main.py                     App state and UI lifecycle
    jarvis_bootstrap.py          Minimal supervised entry point
    Start Jarvis.cmd             Hidden single-instance startup
    Stop Jarvis.cmd              Explicit supervisor shutdown
    config.json                 Local settings, apps, folders and models
    runtime_manifest.json       Dependencies, capabilities and owned services
    requirements*.txt           Main and isolated brain dependencies
    jarvis/                     Application modules and assets
    tests/                      Regression tests and synthetic speech fixture
    docs/                       Audits, integration notes and recovery design
    artifacts/                  HUD preview and synthetic voice sample
    integrations/               References, licenses and globe source
    models/                     Downloaded Whisper, Laya and voice assets
    JarvisFiles/                Default direct-file and terminal workspace
    .venv/                      Main Python environment
    .venv-brain/                Isolated CPU brain environment
    .jarvis-runtime/             Health state, snapshots, repairs and coding diffs
```

| Modules | Responsibility |
| --- | --- |
| `audio.py`, `whisper_backend.py`, `engine.py`, `commands.py` | Capture, VAD/transcription, wake/stream handling, and command parsing. |
| `interface.py`, `hud.py`, `main.py` | Dock/panel rendering, controls, event handling, and app lifecycle. |
| `actions.py`, `desktop_actions.py`, `ui_controls.py`, `ui_worker.py`, `browser.py` | Direct actions, accessibility-backed operations, checked destinations, and browser launching. |
| `brain.py`, `brain_worker.py`, `model_selection.py`, `screen_worker.py` | Planning/decisions, Laya, model availability/fallback, and screen observation. |
| `tools.py`, `toolkits.py`, `task_graph.py` | Shared tool schemas/routes, provider adapters, and task dependencies. |
| `coder.py`, `code_context.py`, `projects.py`, `catalog.py` | Checked source generation/edits, project context/discovery, and indexed path lookup. |
| `knowledge.py`, `knowledge_worker.py`, `question_client.py`, `speech.py`, `piper_speech.py` | Answers, web/screen context, worker reuse, voice synthesis, and playback. |
| `task_state.py`, `task_recovery.py`, `experience.py`, `ui_memory.py` | Checkpoints, safe alternatives, verified task recall, and UI suggestions. |
| `launcher.py`, `recovery.py`, `model_recovery.py` | Process ownership, startup readiness, health checks, and bounded silent repair. |
| `spotify.py`, `gods_eye_view.py` | Spotify-specific sessions and owned globe server lifecycle. |

## Configuration and relocation

| Setting | Current saved value / purpose |
| --- | --- |
| `model_path` | `models/faster-whisper-medium.en`, resolved from the app directory. |
| `whisper` | `medium.en`, CUDA, `int8_float16`, English, 1 s partial interval, 0.8 s silence, 0.45 VAD threshold. |
| `files_root` | `JarvisFiles`, resolved from the app directory. |
| `folders["jarvis files"]` | Relative `JarvisFiles` alias; follows a future app directory move. |
| `project_roots` | `D:\Kunals GitHub Repo`, its `Jarvis` directory, existing `D:\Phython Project`, and `D:\`. These are local machine paths. |
| `microphone`, `wake_timeout_seconds` | Default device (`null`), 90 s wake inactivity timeout. |
| `knowledge` | Enabled, `qwen3.5:4b`, `qwen3-vl:4b`, English answers, internet enabled, CPU inference (`num_gpu: 0`). |
| `speech` | Enabled, English, length scale 1.05, noise 0.667/0.8, sentence silence 0.18 s. |
| `brain` | Enabled, Qwen planner/decision/vision, Laya selector, screen awareness, adaptive planning, and task recovery enabled. |
| `apps`, `folders`, `files`, `file_catalog` | Installed app targets, named path aliases, optional explicit file aliases, and catalog source. |

Current application location: `D:\Kunals GitHub Repo\Jarvis\InsTAREELS`. Launchers use their own directory; application/model paths derive from source locations. Run commands from the app directory so Python resolves the `jarvis` package. The **open project folder** command uses the first existing non-drive-root entry in `project_roots`, rather than relying on the old folder name.

After another move, review absolute `project_roots` and app/folder aliases, then refresh the PC catalog for moved indexed paths. Historical task records describe the original targets and should not be blindly rewritten. Python virtual environments also contain absolute activation/console-launcher paths: the activation scripts in both current environments were corrected during this relocation. Prefer `python.exe -m pip` from the selected environment; if an environment is moved again and fails, recreate it with the setup scripts. Verify readiness before restarting Jarvis.

Runtime records include `task_state.json` (bounded task history/checkpoints), `ui_memory.json` (successful choices), optional `project_memory.json` (opened projects), the file catalog/SQLite index, worker logs, and `.jarvis-runtime/repairs.jsonl`. Coding originals/diffs/hashes are stored in `.jarvis-runtime/coding/<id>/`. The UI transcript and question conversation history are bounded in memory; task metadata and repair records persist locally. Screenshots and generated file contents are not embedded in task-state records.

## Troubleshooting

| Symptom | Check / action |
| --- | --- |
| Startup fails or dependencies/models are missing | Run the launcher readiness command below; inspect `.jarvis-runtime/repairs.jsonl` and worker logs. Rerun the relevant setup/resume script. |
| Setup interrupted | Rerun **Resume Whisper Setup.cmd** or **Setup Jarvis Brain.cmd** when connectivity returns. Downloads are designed to resume. |
| GPU speech check fails | Confirm NVIDIA driver/GPU availability and inspect `verify_whisper.py` output. This configuration does not silently use CPU Whisper. |
| No recognized speech | Check Windows microphone access, the selected device and input meter, listening state, and whether reply playback is muting recognition. |
| Answers/planning unavailable | Install/start Ollama, complete brain setup, and inspect the configured model names and worker logs. |
| Jarvis ignores a spoken selection | Stop dictation, keep the destination visible, list exposed controls, and name an unambiguous current label. Choices expire after 45 s. |
| File lookup fails after a move | Check aliases and run **Refresh PC Catalog.cmd**; restart Jarvis. An outdated SQLite index is rejected rather than guessed. |
| Project folder opens the wrong location | Reorder/update `project_roots` in `config.json`; the first existing non-drive root is used for the generic project-folder command. |
| Toolkit is unavailable | Use **list toolkits**, set the required provider environment variables before startup, and review provider scopes in the toolkit guide. |
| Unfinished task after a crash | Inspect fresh screen/file state and use **resume last task** when appropriate. An uncertain write/click remains paused until inspected. |
| Panel disappears but Jarvis remains active | Closing/hiding the panel is intentional; use **Quit Jarvis** or **Stop Jarvis.cmd** to stop supervision. |
| Globe fails to launch | Check Node, installed `node_modules`, port 4173, and `jarvis-launch.log` in the globe source directory. |

## Verification commands

Use the main environment explicitly to avoid another installed Python or a stale moved console launcher:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m jarvis.launcher --check
.\.venv\Scripts\python.exe verify_whisper.py --audio tests\fixtures\jarvis-command.wav
.\.venv\Scripts\python.exe verify_brain.py
.\.venv\Scripts\python.exe verify_scenarios.py
.\.venv\Scripts\python.exe verify_speech.py
.\.venv\Scripts\python.exe verify_ui.py
.\.venv\Scripts\python.exe verify_coder.py --workflow-smoke
```

Additional targeted checks:

```powershell
.\.venv\Scripts\python.exe verify_desktop_planner.py
.\.venv\Scripts\python.exe verify_desktop_planner.py --vision-only
.\.venv\Scripts\python.exe verify_ui.py --preview artifacts\jarvis-hud-preview.png
.\.venv\Scripts\python.exe verify_question_speed.py --live
.\.venv\Scripts\python.exe verify_toolkits.py --live
.\.venv\Scripts\python.exe verify_toolkit_planner.py
.\.venv\Scripts\python.exe verify_hardware_models.py
.\.venv\Scripts\python.exe verify_clarification.py
```

Unit tests use controlled fixtures/mocks for desktop and provider behavior. Readiness checks import declared dependencies and check local assets without launching the main interface. Model checks need installed models; UI checks create their own test window; coding/toolkit smoke checks write only their isolated temporary workspace. Live question/toolkit checks can contact local inference and public web services. Use **Start Jarvis.cmd** for ordinary supervised use; direct `main.py` execution bypasses the supervisor.

The **Preview text command** box accepts a full “Jarvis …” sentence and displays planned actions without executing them. Automated tests cover streaming, duplicate prevention, wake gating, explicit deletion, cancellation, and filesystem restrictions. Live microphone accuracy and typing into your chosen apps need a spoken trial on your PC.

`verify_whisper.py` loads the configured model, executes GPU inference, prints the recognized text, timing, and planned commands, and never executes desktop actions. The included WAV is synthetic test speech, not a recording of the user. Unit tests cover punctuation normalization, overlap stitching, backpressure, cancellation during inference, plus the existing file and typing restrictions.

References: [faster-whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu), [English-only medium.en conversion used here](https://huggingface.co/Systran/faster-whisper-medium.en), and [Silero integration](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/vad.py). Desktop control uses the Windows API directly.

## Current validation and update history

**2026-09-27 file-task and clarification fix:** all **347 regression tests passed**, including the reported spoken sentence, exact contents, folder questions and answers, option names/numbers/ordinals, expired/invalid choices, cancellation, and uncertain-action blocking. The live Qwen smoke check created and read back two temporary files, including a task continued by a Downloads answer; Explorer launch/observations were simulated, with no real desktop, microphone or account actions. Launcher readiness reported ready with no missing requirements. Both README files document the new behavior and `verify_clarification.py` reproduces the smoke check.

**2026-09-27 hardware/model review:** actual hardware inspection, six synthetic vision step checks, and live Laya/Qwen agreement and unrelated-action rejection checks passed. All 330 regression tests passed; launcher readiness reported ready with no missing requirements. Current model assignments retained; see the model audit for the scope and timings.

**2026-09-27 autonomous toolkit planning:** all **330 regression tests passed**, including autonomous dispatch coverage for all 37 added toolkit operations with mocked adapters, actual scoped temporary-file reads, bounded result context, configured-tool schemas, failed verification, and unrequested-send rejection. The actual local `qwen3.5:4b` selected research and source-reading tools and replanned from source text into `write_tests` without unnecessary clarification. Launcher readiness passed with no missing dependencies/models; **96 local documentation links/images/anchors passed**. The live planner check executed inference only, with no desktop, web-tool or account actions. All models remain unchanged.

**2026-09-27 relocation validation:** all **317 tests passed** and `python -m jarvis.launcher --check` reported `ready` with an empty missing list. Direct checks confirmed the relative Jarvis-files alias, relocated Jarvis project discovery, and `python -m pip` in both Python environments. This verifies regressions and runtime readiness, not every real app, account operation, or live microphone condition.

**2026-09-27 documentation and follow-up fix:** expanded both README entry points, embedded existing media with provenance, documented current settings/architecture/integrations, and added ongoing documentation requirements. Reviewing the generic project-folder command revealed a remaining hardcoded old folder name; it now uses the configured project roots, with a regression test for a renamed root and a missing first entry. All **318 regression tests passed**, the launcher reported `ready` with no missing assets/dependencies, and all **56 local documentation links, images, and anchors** passed validation.

Earlier implemented work includes streaming speech and direct commands; catalog/project and accessibility controls; local screen-aware planning and coding; Spotify/globe integration; supervisor/checkpoint recovery; adaptive plans and safe alternatives; verified task/UI recall; task dependency checks; sentence speech; the HUD interface; related-code edits and backups; reusable question inference; and the 37 toolkit adapters. Detailed source revisions and historical validation counts remain in the linked integration notes rather than being presented as current reruns.

Historical measurements include approximately 43% less overlay render time in the earlier feature audit and roughly 17% lower warm question latency in a small reusable-worker benchmark. These measure particular components and samples, not an overall task-speed guarantee. See [feature audit](docs/FEATURE_AUDIT.md) and [response speed](docs/gar-response-speed.md) for methods and limitations. Real account-backed toolkit writes were tested with mocked transports; documentation does not claim a live message, event, or repository change occurred.

## Documentation maintenance and attribution

Update this README alongside future changes to features, setup, dependencies, settings, paths, interface, integrations, limitations, or verification. Refresh the parent [repository README](../README.md) when its overview changes. Add current UI media when available; label previews, references and upstream demos accurately. Keep links relative so the documentation works after moving the repository. Date test results and distinguish readiness, regression, synthetic inference, and live checks. These requirements are recorded in [application instructions](AGENTS.md) and [repository instructions](../AGENTS.md).

Reference repositories, retained licenses, and pinned revisions are documented under `docs/` and `integrations/`. Downloaded reference sources do not imply that their entire products run inside Jarvis. The bundled HUD branding/artwork and globe datasets have separate provenance and terms; see [HUD artwork](jarvis/assets/README.md) and [globe data sources](integrations/gods-eye-view-src/gods-eye-view-main/DATA_SOURCES.md). Do not infer a single project-wide license from an upstream reference license.
