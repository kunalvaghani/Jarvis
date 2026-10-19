# Phase 6 — Rollback and independent Codex verification checklist

No Codex review evidence exists for this phase.

## Rollback

```powershell
git revert <phase-06-commits>     # on claude; see commit.txt
```

Disable without reverting: set `evolution_lab.enabled: false` in `config/config.json`. Deployed evolution releases
(none were deployed in this phase) are rolled back with `python -m jarvis.evolution_promotion rollback <release>`.
This works while Jarvis is stopped and refuses to overwrite a file edited after deployment.
Runtime state (ignored by Git): `.jarvis-runtime/evolution/` (archive, results.tsv, lab repository, releases).
Deleting it removes experiment history only; production source is never stored there.

## Checklist

1. [ ] `git log main..claude` shows only `claude` commits; `git branch`/`git worktree list` in the Jarvis repo show no experiment branches or worktrees.
2. [ ] `python -m pytest tests/test_phase06_controlled_evolution.py -q` → 25 passed (needs Git; about 2 minutes).
3. [ ] Read `evolution_eval/gate.py`: seal (committed blobs), integrity (single file, independent literal rule, evaluator bounds), paired bootstrap, ten domains, post-integrity.
4. [ ] Try to falsify: edit `evolution_eval/policy.json` without committing and run `RetentionGate('.', 'evolution_eval').seal()` → must raise.
5. [ ] Try to falsify: write a non-literal change into a lab candidate worktree and evaluate it → must be quarantined.
6. [ ] Read `jarvis/evolution_surfaces.py` `PROTECTED` and confirm no policy/approval/evaluator/test/config file can be a surface.
7. [ ] Inspect `experiments/candidates.json`: every candidate has parent, generation, lab commit, values, seed, environment, decision and reason.
8. [ ] Re-run the DAG gate: `python -c "from jarvis.autoresearch import AutoResearch; print(AutoResearch('.').reevaluate('cand_dc72ef14b5a0')['decision'])"` (needs the local `.jarvis-runtime/evolution` from this machine).
9. [ ] Confirm the DAG improvement is only on synthetic DAGs and that no real-task benefit is claimed.
10. [ ] Read `jarvis/evolution_promotion.py`: approval before write, snapshot, health checks, auto-rollback, stale/evaluator refusal.
11. [ ] Check the three lab-deselected tests and reasons in `policy.json`; confirm they ran in the production full regression.
