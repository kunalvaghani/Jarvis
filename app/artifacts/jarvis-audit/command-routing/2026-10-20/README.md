# Spoken command routing repairs (2026-10-20 IST)

The user reported that Jarvis could not select or play YouTube videos, opened YouTube in DuckDuckGo instead of
Google Chrome, and could not play songs on Spotify. Every case below was traced through the real code path:
`Listener` → `Engine.feed` → `commands.parse` → `conversation_intent.normalize` → `Actions.submit` →
`Actions._execute`. Conversation text and private paths from the local log are summarised, not copied.

## What the conversation log showed

| User said (from the local conversation log) | What Jarvis did | Cause |
| --- | --- | --- |
| "Open youtube" | Replied "Command 88 returned; inspect the result before repeating." and YouTube opened in the Windows default browser (DuckDuckGo) | `Actions._execute` matched Windows catalog command 88 (`Start-Process 'https://www.youtube.com'`) before the browser route, so Windows' default browser was used and the raw PowerShell status became the reply. Commands 87–92 (Google, YouTube, Gmail, GitHub, Drive, ChatGPT) had the same problem |
| "so i will select the second video" / "shall we select the second video" | Chat reply "Got it, I'll select the second video", but nothing was selected | The lead-in was only stripped before verbs in a fixed list, and `select`/`click`/`choose` were missing. "I will" was not a recognised lead-in. The text fell to the chat classifier |
| "there is play finding her on spotify" | Chat reply asking whether to play it | Speech recognition heard "Jarvis" as "there is"; only the literal word "jarvis" was stripped |
| "it's obviously finding her on spotify" | Chat reply claiming it would search | A correction ("it's obviously X on Spotify") was not recognised |
| "opens spotify and play adhd" (older) | Chat reply "I can't actually open apps" | The third-person verb "opens" was not recognised |
| Chat replies to command-like text | Promised actions ("I'll select…", "I'll always play the first song") that never ran | The answer prompt forbade claiming completed actions but not promising future ones |

Once parsed, the YouTube player (Jarvis-controlled Chrome via Playwright, with verified playback) and the Spotify
player (native app with search and verified now-playing) were already on the correct routes. The failures were
upstream of them.

## Repairs

- `jarvis/actions.py`: "open" for the website catalog entries (Google, YouTube, Gmail, GitHub, Google Drive,
  ChatGPT) now runs the `browse` route with **Google Chrome** (`apps.chrome`), never the Windows default browser.
  YouTube uses the Jarvis-controlled Chrome (`agent_runtime.dom_browser`), so "select the second video" and
  playback controls act on that page.
- `jarvis/conversation_intent.py`:
  - Filler and lead-ins are stripped only when a recognised action verb remains: "so", "okay", "jarvis",
    "there is/there's", "I will/I'll", "I'm going to", "can/could/would/will you", "please", "just".
  - Action verbs now include select, click, choose, tap, press, scroll, mute/unmute, put on and
    next/previous song/track/video.
  - Third-person verbs ("opens", "plays", "selects") are normalised.
  - Corrections ("it's obviously/actually X on Spotify", "I said/meant X on YouTube") become play commands.
  - Statements stay chat. Only the stripped remainder can become an action, and "it's X on spotify" without a
    correcting word is unchanged.
- `jarvis/knowledge_worker.py`: when command-like text reaches chat, the answer model must not agree to or
  promise the action. It says the text was not run as a command and asks the user to repeat it starting with
  the action.

## Verification (2026-10-20)

| Check | Result |
| --- | --- |
| Parser probe through the real `Engine` with the user's failing phrases, after the repair | All parse to `select_context` or `play_media` with the right service — [probe](parser-probe-after.txt) |
| 17 chat statements ("there is a problem with my code", "so I will be late today", "it's a nice song on spotify", …) | None became an action; `quick_kind` never returns `task` — same probe file |
| New `tests/test_command_routing_fixes.py` | **26 passed** |
| Existing routing suites (brain parser, task routing, natural names, fast conversation, media player, Windows commands, command cleanup, pointer, browser audit, automation upgrade) | **222 passed / 2 skipped** |
| Full regression (16:18–16:37 IST) | **3,661 passed / 0 failed / 148 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |

**NOT RUN live:** no browser, Spotify, video or voice action was performed for this record. The repairs take
effect after Jarvis restarts. The live check is: "open YouTube", then "play lofi music on YouTube", then
"select the second video", then "play Finding Her on Spotify".

**Not changed:** YouTube opens in the Jarvis-controlled Chrome profile (real Chrome and real youtube.com, but
not your personal Chrome profile). Jarvis can only click and verify inside a browser it controls. If YouTube is
opened in your own Chrome window, "select the second video" falls back to on-screen UI automation.
