# Independent Jarvis audit checkpoint — 2026-10-19 IST

Pinned `claude`: `36fbf3ce925080f7f54afa87eaf1d9b88414142d`. Isolated branch `codex-review`. This package reports actual execution, not a certification of the entire assistant.

| ID | Severity | Root cause | Provenance | Status |
|---|---|---|---|---|
| IR-001 | P1 | demonstration.window_state copies private/unknown UIA Text and toggle names without is_password screening; snapshots are persisted by sessions | Added in Phase05 commit 105b97b | Fixed in isolated checkout; four failing synthetic cases now pass |
| IR-002 | P1 | trainer treats GPU-state read/JSON failures as idle, omits shared schema validation, and checks foreground only after loading GPU dependencies/model | Added in Phase07 commit caffdd8 | Fixed unknown-state handling plus pre-import admission; eight final synthetic cases pass |
| IR-003 | P1 | Windows recipe catalog and source were pinned with inconsistent newline conventions; Git autocrlf checkout breaks ordinary command routing | Pre-upgrade commit b54c0c1 | Normalize CRLF to LF before pinned-content checks; LF/CRLF and tamper tests plus cognition/STT retests |
| IR-004 | P2 | Isolated evolution Git worktree creation fails at Windows MAX_PATH on a deep source snapshot | Added in Phase06 commit 46c77cd | Per-command core.longpaths=true for owned Git subprocesses; lab-final.xml |

Baseline reproduction: reproductions-before.xml = 10 FAIL / 1 PASS. Additional early-admission reproduction: training-admission-before.xml = 1 FAIL. These demonstrate two root causes, not eleven independent defects. Retests: trainer-final.xml and reproductions-after.xml. No P0 or P3 defect was confirmed within this checkpoint. Suite failures must be read independently; they are not silently recategorized as passes.

The early limited sandbox run trainer-related-after.xml had two environment-induced failures (Git config writes and atomic registry replace denied). Its failures remain preserved; the outside-sandbox rerun is trainer-final.xml.
