# Writing by voice and push-to-write — 2026-10-10 IST

Jarvis no longer has a dictation mode. There are three ways to put text where your cursor is.

| You say or do | What happens |
| --- | --- |
| `write a short thank-you note here` | The local model (`qwen3.5:9b`) writes it and Jarvis types it into the current window as it is generated |
| `write exactly Dear team, the call moved to 4 PM` | Typed word for word, keeping your capital letters and punctuation |
| **Hold Left Ctrl + Left Alt** and speak | Everything you say is typed at the cursor; let go to return to normal |

## Write commands

- **Composed text:** `write …`, `type …`. Add `here`, `in here`, `over here` or `in this app` for the
  current window, or `in Notepad` / `in Word` for a named app (Jarvis brings it to the front, or opens it).
  `open Notepad and write a haiku about rain` writes into Notepad, never into the window you were in before.
  The model matches the app (an email body, a chat message, a paragraph) and writes only the text, with no preface.
- **Exact text:** say `exactly`, `word for word` or `verbatim` (`write exactly …`, `type exactly this: …`,
  `write … exactly`), or speak quoted text. Nothing is changed or composed.
- If you say "in X" and X is not an app ("a poem about life in Paris"), it stays part of the text.
- Writing into a file (`write hello to notes.txt in Downloads`) is a planned file task, not typing.
- The window is remembered when you ask, so a write that waits behind another task still lands where you asked.
  If the target app does not come to the front, nothing is typed.
- Line breaks are typed as Shift+Enter: a new line in editors, email bodies and chat boxes, where a plain Enter
  would send. In terminals (Command Prompt, PowerShell, Windows Terminal, WSL) line breaks become spaces, so
  typed text never runs a command.
- `start dictation`, `stop dictation` and a bare `write` explain these options instead of starting a mode.

## Push-to-write

Hold **Left Ctrl + Left Alt** for a moment (0.2 s), then speak. No wake word is needed and nothing you say is
treated as a command. Each phrase is typed when you pause; letting go types what you said so far and returns
Jarvis to normal. Phrases follow your cursor, so you can click into another field between phrases. Say
"new line" or "new paragraph" for line breaks. Spoken answers stop when you start holding the keys.

Shortcuts are not hijacked: pressing any other key while holding Ctrl+Alt (Ctrl+Alt+Del, Ctrl+Alt+T …) cancels
push-to-write, and the half-spoken phrase is dropped. Right Alt (AltGr) does not trigger it.

Implementation: [push_to_write.py](../jarvis/push_to_write.py) (keyboard hook),
[audio.py](../jarvis/audio.py) (marks speech spoken while the keys are held),
[writing.py](../jarvis/writing.py) (write commands, typing and the push-to-write writer),
[engine.py](../jarvis/engine.py) (dictation state removed).

**Why the Alt release is special.** Releasing Alt on its own switches Notepad, Office and similar apps into
menu-shortcut mode, where the next typed letters run menu commands. The hook therefore replaces your real Alt
release with a harmless unassigned key (0xE8) followed by the release. This is the same technique AutoHotkey
uses. No other key is blocked or changed; Jarvis's own typing passes through untouched.

## Configuration

`push_to_write` in [config/config.json](../config/config.json): `enabled` (default `true`) and `hold_seconds`
(default `0.2`). The hotkey is fixed to Left Ctrl + Left Alt.

## Measurements — live, 2026-10-10 IST

Live on this computer (RTX 3050 Laptop 4 GB):

- `write a two sentence note about tomorrow being sunny here` into Notepad: typing began after 11.8 s and the
  26-word note was complete at 15.6 s.
- `Write exactly, Dear Kunal: the build PASSED at 5:30 PM!` typed with its original capitals and punctuation.
- The keyboard hook installed, received key events and shut down cleanly.
- The hook's release sequence was checked in Windows 11 Notepad in both release orders (Alt first and Ctrl
  first) while text was typed with both keys held: all text landed in place and Notepad never entered
  menu-shortcut mode. In the same test without the mask key, text typed after releasing the keys did not
  appear in the document.

Not yet verified: a hands-on push-to-write session with a physical keyboard and microphone. The hook's state
machine, speech routing and writer are covered by fixture tests; holding the real keys and speaking needs a
person at the computer.

Testing note: Notepad windows launched by the test scripts closed when each test command finished, because
the test tool runs programs inside a job that Windows ends with the command. This is a test-environment effect,
not Jarvis behaviour; Notepad restored all its tabs each time.

## Limitations

- Composed text starts after the model reads the request (about 10–12 s on this computer) and then types at
  the model's writing speed.
- Push-to-write types after each pause, not word by word, so revisions from the speech recogniser never
  appear on screen.
- Typing uses the keyboard; apps running as administrator do not accept input from a normal-user Jarvis.

## Verification

- Fixture tests: [test_push_to_write.py](../tests/test_push_to_write.py) (key state machine, routing, writer),
  [test_open_write.py](../tests/test_open_write.py) (open-and-write, exact, composed, safety), and updated engine,
  cleanup and knowledge tests.
- Regression, 2026-10-10 IST: **1,370 tests ran in 225.451 s, OK with one skipped class**
  ([log](../artifacts/logs/push-to-write-regression.log)); the skipped class needs Docker's Linux engine, which
  was unavailable. `python -m jarvis.launcher --check` reports `ready`.
