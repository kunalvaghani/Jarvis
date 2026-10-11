# Screen pre-awareness: Jarvis offers help for the app in front of you

Updated 2026-10-11 IST. Jarvis now notices which app you're using. After you've stayed in it for about four seconds, it asks one question that fits that app, and if you say yes, it does the job by looking at the screen:

- **YouTube:** "You're on YouTube. Want me to open one of the videos on screen? Just say a word from its title." Say "yes", then one word from a title (or say the word straight away). Jarvis reads the video titles on screen, finds the one with that word, and opens it. A misheard spelling still matches ("despasito" finds "Despacito"). If several videos match, Jarvis reads them out; say "first", "second", or another word.
- **Notepad, Sticky Notes, OneNote, Obsidian, Word:** "Do you have something in mind to write? You can dictate and I'll write it." Say "yes". Jarvis puts the cursor at the end of your text, starts a new line, and types everything you say until you say "stop writing", press Esc, or stay quiet for two minutes.
- **Other apps:** a question that fits what the app does (see the table below). For an app Jarvis has no profile for, it offers the buttons it can see ("Want me to press something in this app? I can see Render, Export, Settings and more").

Jarvis only asks when it makes sense:
- the microphone is on;
- Jarvis isn't talking;
- nothing is running, queued or waiting on you;
- you aren't already writing.

Each app is asked once every 10 minutes at most. Say "no" three times to the same app and Jarvis stops asking about it. Private windows never get unprompted questions: mail, banking, sign-in and payment pages, and incognito windows. Jarvis also never saves the button labels it reads in chat apps.

## What Jarvis knows about your apps

Before building this, Jarvis took stock of the apps on this PC, using [`jarvis/app_knowledge.py`](../jarvis/app_knowledge.py):

- **Inventory:** the 333 Start-menu apps already in `config.json` `apps`, each sorted into a category from its name and executable. Measured 2026-10-11: 84 Windows and hardware tools, 39 coding and developer tools, 30 help pages, 28 terminals, 21 office/document apps, 16 games and launchers, 16 everyday tools, 15 media, 15 creative/3D/recording, 11 messaging and calls, 9 browsers, 7 notes, 7 email, 6 AI assistants, 6 file managers, 5 cloud/backup, 5 security, 4 uninstallers, 2 music, 1 video and 1 meetings app. Five were left as "other".
- **Profiles:** 34 hand-written profiles covering the apps installed here. Each one says what the app does, lists its main features, and gives the question Jarvis asks in it.
- **Buttons, learned live:** while an app is in front, Jarvis reads its buttons, menus and tabs through Windows UI Automation. It keeps only their *names*, never field contents, list items, chats, passwords or positions, and saves them to `.jarvis-runtime/app_knowledge.json`, so it knows an app better the more you use it.

A scan of the windows open on 2026-10-11 showed why buttons have to be learned live: windows in the background expose almost nothing (VS Code showed 3 buttons, File Explorer 3), while an app in front exposes far more (one Chrome page showed 86 buttons and 24 links).

That knowledge feeds the rest of Jarvis. Every answer and task plan now sees the app in front: what it does, its features and the buttons it has shown. You can also ask about it directly (see "Say" below).

| App (profile) | Jarvis asks | A "yes" does |
| --- | --- | --- |
| YouTube | open one of the videos on screen? | reads the titles, opens the one you name by a word |
| Notepad, Sticky Notes, OneNote, Obsidian, Word | something in mind to write? | cursor to the end, new line, hands-free writing |
| ChatGPT / Claude / Copilot (app or web) | dictate a prompt? | hands-free writing into the prompt box |
| Web browser (other sites) | a quick summary of this page? | the screen model summarises the page |
| VS Code, Cursor, Visual Studio | explain the code on screen or look for a bug? | the screen model explains it |
| Terminal, PowerShell, Command Prompt | explain the output or error on screen? | the screen model explains it |
| File Explorer | looking for a file or folder? | opens the item you name |
| Spotify | play something? | "play … on Spotify" |
| VLC / Media Player, Photos, Zoom, OBS, Paint | press something? | presses the button you name |
| WhatsApp, Telegram, Discord, Teams | message someone? | builds the message command (preview and approval as usual) |
| Calculator | calculate something? | types the sum (arithmetic only) and says the answer |
| Settings | which setting? | opens that settings page |
| Task Manager | what's using the most CPU and memory? | answers it |
| Excel, Blender / Unity / Unreal / Gaea | ask me how to do something? | answers your question looking at the screen |
| PowerPoint, GitHub Desktop / SourceTree, Docker, Windows Security | suggestions / summary / explanation | the screen model answers |
| Gmail, Outlook | — (private: no unprompted questions) | — |

## Say

| Say | What happens |
| --- | --- |
| "Yes" / "sure" / "go ahead" (after a question) | Does the app's job, or asks the one detail it needs. |
| A word from a video title, "the second one", a button name | Answers the follow-up. |
| "No" / "not now" | Fine; that app isn't asked again for 10 minutes. Three no's mute it. |
| "Start dictation" / "take dictation" / "let me dictate" | Hands-free writing into the app in front. |
| "Stop writing" (or Esc) | Ends hands-free writing. The words "stop writing" aren't typed. |
| "What can you do here?" | Asks this screen's question now. |
| "What does this app do?" | What it is, its features, and the buttons Jarvis has seen in it. |
| "What buttons are on screen?" | Reads the app's buttons now and lists them. |
| "What apps do I have?" | The inventory by category. |
| "Stop asking about this app" | Mutes this app. |
| "Pause screen suggestions" / "Resume screen suggestions" | Switches all offers off or back on. |

Anything else you say while a question is open is handled normally, and the question is dropped.

## Safety

- Before pressing anything, Jarvis reads the screen again, so it never acts on a stale list.
- Destructive buttons (delete, send, buy, pay and similar) are never pressed from a fuzzy match. Jarvis tells you to say "click …" yourself instead.
- Messages still go through the usual WhatsApp preview and approval.
- The calculator accepts arithmetic only; nothing is evaluated as code.
- Hands-free writing types into the app you said yes in, from the end of its text. Typing stops if the window changes.

## Settings

`config/config.json` (defaults shown; leaving the section out uses them):

```json
"screen_awareness": { "enabled": true, "dwell_seconds": 4, "cooldown_minutes": 10, "offer_seconds": 45,
                      "ask_unknown_apps": true, "dictation_idle_seconds": 120 }
```

## Fixed along the way

Push-to-write could drop a character near the start of a phrase in Windows 11 Notepad ("Hello from" became "Hello rrom"). Its typing helper was being created lazily on the writer's background thread. It's now created up front, and both push-to-write and hands-free writing type exactly. A second cause was Notepad's own autocorrect reacting when dictation was glued onto the last word of a note; hands-free writing now starts on a new line in notes and documents.

## Limits

- YouTube results must be on screen. Titles come from the browser's accessibility tree, so on a page that's still loading Jarvis offers the general browser question instead.
- Apps that don't expose named controls (some games and custom-drawn interfaces) can't be pressed by name. Jarvis says so instead of guessing coordinates.
- Hands-free writing needs push-to-write to be enabled (it is by default) and the microphone on.
- Questions are spoken, and Jarvis wakes for your answer, so a bare "yes" works without saying "Jarvis" first.

## Verification (2026-10-11 IST)

**Live on this PC, with a real `Actions` instance** (UI-verification config; learned buttons were written to a scratch folder; typing went only into a scratch note the check created):
- **Notepad:** the question came 5.0 s after the note came to the front. "Yes" turned hands-free writing on. The phrase was typed at the end of the note on a new line, exactly "Hello from Jarvis. This line was typed by hands-free writing.", and read back from the saved file.
- **YouTube:** on a "lofi hip hop" results page, the question came 4.6 s after the page loaded. "Yes", then "best", made Jarvis pick "Best of lofi hip hop 2021 ✨ [beats to relax/study to]" from the videos on screen and open it. The tab's title changed to that video's title, then the check paused the video and closed the window it had opened.
- "What does this app do?" on YouTube answered with its description, features and the buttons it had just learned.

One incident during the first live attempt: Windows 11 Notepad reopened an existing note tab instead of a blank page. The check's clean-up keystrokes (select all, delete) were sent to it before the window was closed. The file on disk (`Downloads\context.txt`) was verified unchanged (same size, last saved before the test), and Notepad kept no edits. The check was then rewritten to type only into a scratch file it creates and to never select or delete anything.

**Regression/readiness (not live feature checks):**
- 21 new tests in [`tests/test_screen_awareness.py`](../tests/test_screen_awareness.py) cover:
  - the inventory and profile matching;
  - learning button names only;
  - title matching, misspellings and ordinals;
  - the YouTube flow (yes then a word, a word straight away, choosing between matches, no match);
  - muting after three no's, and other requests passing through;
  - only asking when idle;
  - Notepad hands-free writing, Spotify, WhatsApp, private pages, Explorer (including refusing an unsafe button), the calculator, the code editor and unknown apps;
  - the commands, the latch, the stop phrase, and routing through `Actions.submit`.
- Full suite: 1,532 tests passed with one skip. The launcher readiness check reported `ready`. See the [regression log](../artifacts/logs/screen-awareness-regression-2026-10-11.log).
