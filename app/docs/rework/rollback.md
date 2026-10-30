# Rollback (control-layer rework)

## Starting point

| | |
|---|---|
| Branch | `claude_ControlArchitect` (created by the user, tracks `origin/claude_ControlArchitect`) |
| Starting revision | `7e7a39a9b4c0226e2c9ec89235476be5f17999a7` (merge of PR #19, 2026-10-29) |
| Working tree at start | clean |
| Other work in flight | Autonomous repair campaign is **PAUSED_BY_USER** (2026-10-29); its state lives in `.jarvis-runtime/campaign-checkpoints/autonomous-repair-pause-2026-10-29`. This rework does not touch campaign state or frozen artifacts. |

## Rolling back

Each phase is a separate commit on this branch, so rollback never needs a force-push.

1. To undo one phase: `git revert <phase-commit>`.
2. To return the whole application to the starting point: `git checkout main` (or `git checkout 7e7a39a -- app/`) and restart Jarvis with `Stop Jarvis.cmd` then `Start Jarvis.cmd`.
3. Live routing switches to the new layer only in Phase 5. Until then, reverting is unnecessary: the old controllers remain the active path.
4. After Phase 5, the switch is guarded by `control_layer.enabled` in `config/config.json` (added in Phase 5); setting it to `false` restores the old routing without a code change until the old controllers are deleted in Phase 10.
5. Never delete `.jarvis-runtime/` during rollback; it holds task checkpoints and receipts.

## Python 3.11 interpreter switch (2026-10-30)

`app/.venv` is now Python 3.11.9 with exactly the 120 packages, at the same versions, that the 3.10 environment had. The previous 3.10.6 environment was moved, not deleted, to `app/.venv310`. Every launcher keeps using `.venv`, so no script changed.

To roll back the interpreter (Jarvis stopped first with `Stop Jarvis.cmd`):

```bat
cd app
ren .venv .venv311-switched
ren .venv310 .venv
```

`app/.venv311` was the side-by-side environment used for the parity check. Nothing referenced it; it was deleted with the user's approval on 2026-10-30. `.venv310` remains the rollback.

## Reproducing the Phase 0 evidence

```bash
cd app
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider     # baseline suite
.venv/Scripts/python.exe -m jarvis.launcher --check                  # readiness
```

The dependency map was generated with an AST scan of imports over `jarvis/*.py`, `main.py`, `jarvis_bootstrap.py` and `tests/*.py`, counting `from .X import`, `from jarvis.X import`, `import jarvis.X` and `"jarvis.X"` module strings.
