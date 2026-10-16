# Phase 1 — Rollback and independent Codex verification checklist

No Codex review has taken place for this phase; no review evidence exists yet.

## Rollback

All Phase 1 changes are in one commit on branch `claude` (SHA in [README.md](README.md)). Nothing was merged into `main`
or any other branch, no dependency was installed into a project environment, and no runtime state, vault or user file was
modified.

```powershell
# From the repository root, on branch claude. Creates a new commit; history is preserved.
git revert <phase-01-commit-sha>
```

Partial rollback (one fix) — restore specific files from the parent commit, then commit:

```powershell
git checkout <phase-01-commit-sha>~1 -- app/jarvis/tools.py            # D1
git checkout <phase-01-commit-sha>~1 -- app/jarvis/cognition.py        # D4
git checkout <phase-01-commit-sha>~1 -- app/jarvis/launcher.py app/jarvis/hierarchical.py   # D2, D3
git checkout <phase-01-commit-sha>~1 -- app/tests/test_web_development_audit.py             # D5
git checkout <phase-01-commit-sha>~1 -- app/tests/test_reverse_engineering_audit.py         # D6
```

Rolling back `agent_events.py`/`execution_contracts.py` also removes the `tool.outcome` contract that Phases 2–4 depend
on; revert those phases first. Existing `agent-events.jsonl` files remain readable either way: older readers ignore the
extra event kind only if they filter by `event`; `tool.outcome` rows use the same envelope (`version`, `at`, `event`,
`call_id`, `tool`).

## Checklist for independent verification

Run from `app/` with `.venv/Scripts/python.exe` (Python 3.10.6).

1. [ ] `git log -1 --format=%H claude` matches the SHA in README.md; `git diff <sha>~1 <sha> --stat` matches
   [files-changed.txt](files-changed.txt); `main` is unchanged (`git log -1 main` = `5b52737`'s ancestor state recorded in
   [git-state.txt](git-state.txt)).
2. [ ] `python -m pytest tests/test_phase01_baseline.py -q` → 19 passed.
3. [ ] Stash the five source/test fixes and rerun step 2 → the D1/D3/D4/D5 tests fail (8 failures), D2 tests still pass
   (documented: no behaviour change).
4. [ ] `python -m pytest tests -q` → compare with [test-results.md](test-results.md) (no failures expected; note the
   machine-load caveat for `test_JRV_29_012`).
5. [ ] After step 4, `git status --short` shows no modified file under `artifacts/jarvis-audit/modules/` (D5).
6. [ ] `python -m jarvis.launcher --check` → `"status": "ready"` (requires the same local Docker/Ollama models).
7. [ ] `python scripts/verification/phase_baseline.py --label verify --out <tmp>/m.json` → every section `MEASURED`,
   `tool_registry.contract_error_rate == 0`, `privacy_routing.private_marked_public == 0`. Absolute timings will differ.
8. [ ] Review `jarvis/execution_contracts.py`: outcome rows accept only categorical/bounded fields; `record_outcome`
   rejects uncorrelated call IDs; `may_replay` is true only for `read_only`/`idempotent`.
9. [ ] Review `jarvis/agent_events.py`: lifecycle kinds still drop every non-lifecycle field
   (`tests/test_architecture_audit.py` JRV-01-020/032 still pass).
10. [ ] Challenge: confirm no claim in [architecture-and-dependency-map.md](architecture-and-dependency-map.md) depends on a
    live account, model or desktop action.
