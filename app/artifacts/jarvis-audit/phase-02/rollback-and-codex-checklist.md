# Phase 2 — Rollback and independent Codex verification checklist

No Codex review evidence exists for this phase.

## Rollback

```powershell
git revert 16d9b4d591238b292db217357942e74adc96c7eb          # on branch claude; history preserved
```

Behaviour-only rollback without reverting code: set `"execution_strategy": {"desktop_order": "pointer_first"}` in
`config/config.json` to restore the cyan-cursor-first desktop order.

Environment: the phase installed `openpyxl==3.1.5` and `python-docx==1.2.0` (plus `lxml`, `typing_extensions`) into
`.venv-skills` only. To remove them: `.venv-skills/Scripts/python.exe -m pip uninstall openpyxl python-docx` (and remove
the two lines from `requirements/skills.txt` and `openpyxl`/`docx` from `utility_imports` in the manifest, otherwise
launcher repair reinstalls them).

Document backups written by real use live in `.jarvis-runtime/backups/documents/` (ignored by Git, never deleted
automatically). Restore a file by copying its backup over the edited file.

## Checklist

1. [ ] `git diff <sha>~1 <sha> --stat` matches [files-changed.txt](files-changed.txt); `main` unchanged.
2. [ ] `python -m pytest tests/test_phase02_execution_strategy.py -q` → 30 passed on a machine with Excel, Word,
   Blender at `D:\Blender\blender.exe`, UE 5.8 manifest, VS Code and Chrome; otherwise the affected tests must skip with a
   `BLOCKED:` reason, never pass.
3. [ ] Confirm the tests labelled MOCK (07c, 07d, 07e, 09b, 09c) are not cited as real-software evidence.
4. [ ] Read `jarvis/execution_strategy.py:strategy_tool`: fallback only on `ToolUnavailable`; any other exception
   re-raises; writes `max_attempts == 1`.
5. [ ] Read `jarvis/app_adapters.py:commit`: hash check → backup → checkpoint → `os.replace` → post-hash check.
6. [ ] Confirm every new tool appears in `tools.SPECS` and that `strategy_execute` dispatches nested calls through
   `ToolRegistry.execute` (search for direct handler calls: there are none outside `app_adapters.execute`).
7. [ ] Run `python -m pytest tests -q` and compare with [test-results.md](test-results.md).
8. [ ] `python -m jarvis.launcher --check` → ready.
9. [ ] Re-run `scripts/verification/phase02_execution_benchmark.py --out <new file>`; absolute times will differ.
10. [ ] After the suite, `tasklist | findstr /I "EXCEL WINWORD blender"` shows no process started by the tests.
11. [ ] Challenge the behaviour change: structured UIA is now preferred over the pointer for `activate`/`open_menu`.
