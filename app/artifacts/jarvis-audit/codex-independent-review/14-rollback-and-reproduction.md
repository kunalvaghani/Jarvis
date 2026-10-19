# Independent Jarvis audit checkpoint — 2026-10-19 IST

Pinned `claude`: `36fbf3ce925080f7f54afa87eaf1d9b88414142d`. Isolated branch `codex-review`. This package reports actual execution, not a certification of the entire assistant.

Audited SHA: `36fbf3ce925080f7f54afa87eaf1d9b88414142d`. Worktree: `D:/Kunals GitHub Repo/LocalGithub/Jarvis-codex-review`. Original checkout: clean when audit began; no source edits there. Review branch: `codex-review`; no merges into claude/main.

From app/, using the existing original `.venv/Scripts/python.exe` as interpreter:

```powershell
python scripts/verification/independent_audit.py inventory
python scripts/verification/independent_audit.py smoke
python scripts/verification/independent_audit.py regression
python scripts/verification/independent_audit.py security
python scripts/verification/independent_audit.py documents
python -m pytest tests/test_independent_review.py -q -p no:cacheprovider
python scripts/verification/independent_benchmarks.py
python -m jarvis.launcher --check
python scripts/verification/independent_report.py
```

Use distinct output folders or preserve an earlier packet before rerunning: scripts update their own report files and pytest basetemp is disposable. pytest needs normal process/Git permissions for disposable nested repositories. External account tests are not enabled. Real-app/performance/long-soak acceptance is listed rather than implemented as an unsafe automatic mode.

To reproduce the defects without reverting production: create another isolated checkout at the pinned SHA, copy only tests/test_independent_review.py there, and run the selected independent tests. Baseline evidence preserves the original 10 failures plus the later pre-import failure. To undo reviewed repairs, revert their reviewed commit on the review branch only, or discard the isolated worktree after deliberately preserving needed evidence. Never reset/restore the working claude or main checkout.
