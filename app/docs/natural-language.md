# Understanding everyday phrasing

**2026-10-15 fixture follow-up:** Four anchored intent rules cover "turn the sound
down a notch", "pause what's playing", "I said close the tab, not the browser"
and latest/most-recent document references. The latter go to the planner rather
than guessing an installed app. The completion pass asks for filename, path or
folder before any model request or opening for ambiguous latest-document requests.
Parser inputs must be strings of at most 100,000 characters; malformed deeply
nested command JSON produces a validation error. "Open Notepad, then type hello" preserves ordered
dispatch and a Notepad typing target; only punctuation before a split boundary
is removed. Existing composed-versus-verbatim writing semantics remain.
Deterministic matching covers an audited finite corpus; it does not establish
arbitrary language understanding, latest-file correctness or live app availability.
[Dated fixture evidence, benchmarks, limits and rollback](../artifacts/jarvis-audit/modules/03-intent-direct/inventory.md).
October 11 measurements below are historical and remain labeled as such.

Updated 2026-10-11 IST. Jarvis now understands requests and questions however they're phrased: politely, casually, as a question, with filler words, or as a standing instruction ("don't send anything unless I approve it"). The coverage is checked against the 800-scenario *Jarvis Natural-Language Intent Testbook* (2,400 phrasings across 25 areas), kept in the repository at [`tests/fixtures/intent_testbook.txt`](../tests/fixtures/intent_testbook.txt).

## Before and after

Measured on this PC on 2026-10-11, parsing every testbook phrasing:

| | Before | After |
| --- | --- | --- |
| Phrasings not understood (fell to the slow small-model guess) | 1,438 of 2,400 | 9 (3 context-dependent corrections × 3 forms) |
| Dropped as "no action taken for a negated command" | 98 | 0 |
| Scenarios whose three phrasings reach the same intent | 487 of 800 | 800 of 800 |
| Generated permutations that reach the same intent | — | 18,714 of 18,714 |

The three scenarios left to conversation are corrections that only make sense in context ("No, I meant the other one", "No, that was an answer to your question", "I meant the GitHub repo, not the local folder"). They go to the waiting question or prompt if there is one, otherwise to the normal conversation path.

Several testbook phrasings used to reach the **wrong** action, and are now fixed:
- "close this tab, not the entire browser" closed the browser;
- "start a conversation…" tried to open an app named "a conversation";
- "show me the active services" flew God's Eye somewhere;
- "never mind; leave the current work untouched" cancelled a task;
- "put the video in full screen" typed text into a window called "full screen";
- "write this in a professional tone" used "a professional tone" as the target window.

## How it works

1. **Phrasing** ([`jarvis/phrasing.py`](../jarvis/phrasing.py)) reduces a sentence to one canonical form, so all three testbook columns end up the same:
   - **Lead-ins** are stripped: "Hey Jarvis,", "could you", "I need you to", "quick question:", "just checking –", "by the way", "do you know…".
   - **Endings** are stripped: ", please", "for me", "right now".
   - **The leading verb's synonym** is mapped: "pull up" means show, "bring up" means open, "give me the gist of" means summarize, "walk me through" means explain, "take a look at" means check, "put on" means play, "drop" means cancel, "start over" means restart, "switch X on" means turn X on.
   - **Spoken numbers** become digits ("thirty seconds" → "30 seconds").

   Only the head of the sentence is rewritten. Dictated text ("write exactly …", "… saying …", file content, code requests) keeps its words, capitals and punctuation.

2. **Intent catalog** ([`jarvis/intent_catalog.py`](../jarvis/intent_catalog.py)) maps each family of everyday requests onto something Jarvis really does. It runs before the older rules, so these phrasings never fall into a generic "open …" or "show …".

3. **Handlers** ([`jarvis/intent_handlers.py`](../jarvis/intent_handlers.py)) answer the new kinds:

| Kind | What it does | Examples |
| --- | --- | --- |
| `behavior` | Answers a standing instruction or a "how do you…" question with what Jarvis actually does, checked against the code, or says plainly that it isn't supported yet. Never takes an action. | "Don't store my password", "never use an approval from an earlier message", "use your pointer without stealing my mouse", "which messaging actions can you actually perform?" |
| `conversation_style` | Changes this session: short, simple or serious answers (sent to the answer model), slower or faster speech, "just thinking aloud" (two minutes of conversation only), private mode (who a message is from, not what it says), quiet mode (alerts go to the log), "keep this off the record" (memory paused), "stop watching WhatsApp". | "Keep your answer short", "speak a little more slowly", "turn off spoken notifications during the meeting" |
| `repeat_last` | Repeats the last reply, only its last sentence, or the last exact text typed. | "Say that again", "repeat only the last sentence" |
| `jarvis_status` | Live facts about Jarvis, answered at once even while a task is running. | Which models are loaded and how much is on the GPU; task history and the last failure; pending approvals; Gmail sign-in; GitHub calls left; weather-watcher state; launcher check; God's Eye version; recent changes |
| `system_info` | Live, read-only facts about this PC. | CPU and memory use with the busiest processes; GPU and VRAM; GPU processes; Windows version; running services, apps and minimised windows; whether an app is running, installed or frozen; newest downloads; the focused window; the control under the pointer |
| `whatsapp_read` | Reads WhatsApp without sending anything. | Unread chats from the chat list, the open chat, who is calling, people matching a name, a contact's latest message |
| `media_related` | Uses what's playing now. | A live version, more by this artist, the channel's latest video, the same song on Spotify or YouTube |
| `gods_eye_camera` | Moves or inspects the current God's Eye view without reloading. | Zoom in or out, orbit, pan north/south/east/west, look straight down, go back to the previous view, label the place, clear labels, fly the drawn route, "what are you looking at", hide one or all of the layers Jarvis turned on |

The catalog also routes many phrasings to existing commands:
- **Media:** "skip forward 10 seconds", "set the video volume to 40 percent", exact playback speed ("change playback speed to 1.5 times", new), full screen, captions.
- **Queue:** "cancel the YouTube task only", "remove task number two", "add opening Notepad to the queue".
- **Desktop:** snapping, minimising, maximising, task view, show desktop and closing a tab, through the vetted Windows command catalog.
- **Memory and repositories:** memory recall and saving a conversation summary now; repository questions by aspect (structure, entry point, dependencies, setup, tests, licence, which coding task used it).
- **God's Eye:** every place, layer and style phrasing in the testbook.
- **Email:** anything mentioning inbox, thread, draft, recipient, CC, label, attachment or sender goes to the Gmail workflow, which still asks before any write.

Read-only status questions run off the task queue, so "what's in the queue?" or "how much memory is free?" is answered immediately even while a long task runs. Results of memory, repository, API-health, weather, WhatsApp and God's Eye commands are now spoken; before, they only appeared in the log.

## Safety stays as it was

- A first name alone never picks a WhatsApp contact, and sends, deletes and replies still need a fresh approval of the exact preview.
- "Don't…" sentences that aren't a known standing instruction are still refused with no action.
- When a WhatsApp preview is waiting, edits like "make the reply warmer" still reach it.
- Status and behavior answers never act.
- The voice engine keeps these sentences whole, so "queue a coding task, then play music while it works" is never split into two commands.

## What isn't supported yet (Jarvis says so)

- Moving a window to another monitor.
- Reordering or pausing the task queue.
- Ending, muting or checking a WhatsApp call already in progress (answering and declining a ringing call work).
- Reading Discord servers or channels.
- Hiding the island on request.
- Lowering music while Jarvis speaks.
- Pausing background repository learning by voice.
- A God's Eye airports layer.
- Delivery and read ticks on WhatsApp.

Larger multi-file coding tasks can still fail validation on the local model, as before.

## Verification (2026-10-11 IST, this PC)

| Check | Result |
| --- | --- |
| Testbook | All 2,400 phrasings reach the intent frozen in [`tests/fixtures/intent_testbook_expected.json`](../tests/fixtures/intent_testbook_expected.json), after a scenario-by-scenario review of where each one goes. |
| Permutations | 18,714 generated variants reach the same intent as their testbook sentence. The variants combine politeness, wake words, discourse markers and endings ([`tests/intent_permutations.py`](../tests/intent_permutations.py)). |
| Live answers through the real `Actions` | "How much memory is free?" → 16.4 of 31.3 GB free. "Check the GPU model and VRAM" → RTX 3050 Laptop GPU, 4096 MB. "What's my Windows version?" → Windows 11 build 26200. "How many GitHub requests are left?" → 59 of 60. "What version of God's Eye is installed?" → 591f299d from 2026-10-10. "Keep your answer short" then "can you remember the tone I asked for?" → recalled. "Say that again" → repeated the last reply. Quiet mode on and off. |
| Live God's Eye camera | Eiffel Tower → zoom out → "what are you looking at" → label the place → central London → back to the Eiffel Tower → thermal → normal. "Zoom out a lot" took the view from 59.8 km to 120.7 km, and "look straight down" over London kept the point in view at 51.508, −0.128. Two bugs were found and fixed: "central London" had found a tube line called Central, and "where" reported the camera's own position instead of the point in view. |

Unit tests are in [`tests/test_intent_testbook.py`](../tests/test_intent_testbook.py). Regression and readiness (2026-10-11 IST): **1,493 tests ran, all passed with one skip** (`artifacts/logs/intent-regression-2026-10-11.log`), and `python -m jarvis.launcher --check` reported `ready`.
