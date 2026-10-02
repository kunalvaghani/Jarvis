# Historical Jarvis HUD

**Replaced at runtime on 2026-09-30.** The following describes the previous interface and its historical verification. The current [Dynamic Island interface](dynamic-island.md) uses native rounded capsules and compact controls; it does not show the circular HUD artwork.

The requested reference repository is a terminal voice assistant, without
desktop GUI widgets to reuse. Its README links an animated Iron Man HUD with a
circular J.A.R.V.I.S. logo. We copied that animation locally, extracted its logo
in the runtime renderer, and built a Tk command center around the same dark,
cyan aesthetic. Source and asset attribution are in `jarvis/assets/README.md`.

The old orb is replaced at runtime by a 138 x 164 draggable HUD launcher. Click
to show/hide Jarvis, drag to reposition, and right-click for listening, terminal,
voice-stop and Quit controls. The larger panel includes the animated logo,
live standby/listening/thinking/working/speaking status, response display,
conversation transcript, voice settings, question/task input, and existing
task/voice Stop controls. Closing the panel hides it; Quit actually stops Jarvis.
Escape hides the panel. The logo inside the panel toggles microphone listening.

`jarvis/interface.py` constructs the UI; `jarvis/hud.py` renders its logo and
status rings. Animation caches are bounded to two display sizes and 32 frames
per size. Frames are rendered without creating services, making network calls,
or changing voice/task actions. If the asset is missing or unreadable, a built-in
emblem is rendered and a silent repair note goes to the existing transcript and
repair journal. Existing source snapshots, launcher, bootstrap, Start/Stop
scripts, microphone stops, screen capture exclusion, and approval handling are
preserved. No extra dependencies are required.

Verification:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe verify_ui.py --preview artifacts\jarvis-hud-preview.png
.\.venv\Scripts\python.exe -m jarvis.launcher --check
```

The preview exports the actual widget layout with a sample conversation using
Pillow; it is a rendered layout preview, not a desktop screenshot. The UI test
creates its own hidden/offscreen window, never starts listening, and closes its
own workers afterward. Regression tests cover callback wiring, small-window
control visibility, missing/damaged artwork, and existing recovery fault,
shutdown, and retry-backoff behavior. Changes load on Jarvis's next launch.

Results on 2026-09-26: all 280 regression tests passed, UI startup/shutdown
passed, and launcher reported `ready` with no missing dependencies.
