# New work

Added tests/test_prompt37_ui_restart.py, a portable regression for JRV-37-021. A real owned child running Actions exits 27 after one mock-outbox attempt and an uncertain checkpoint. A fresh Actions instance queues resume; real App.report and App.drain deliver the paused result through Island/Desk and actual Tk widgets. Reads actual overview/live text, verifies one speech-sink call and zero planner calls, and reads the durable marker/outbox again.

The test bypasses App constructor (no mic/model startup), uses hidden owned widgets and fake send/speech boundaries. Only the drain recovery scheduler wrapper is bypassed so assertion failures propagate; the event consumer body executes. No screenshot, account send, native hook or physical audio. No production behavior changed. One setup run failed to find the not-yet-created test after shell quoting failed; setup-error evidence retained and superseded by successful portable execution.
