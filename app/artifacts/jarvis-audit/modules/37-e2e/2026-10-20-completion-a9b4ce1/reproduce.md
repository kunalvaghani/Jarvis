# Reproduce safely

From this worktree app directory, use the existing original main venv Python. No package setup/install required or authorized.

1. Run `python artifacts/jarvis-audit/modules/37-e2e/2026-10-20-completion-a9b4ce1/run_regressions.py --junitxml=artifacts/jarvis-audit/modules/37-e2e/2026-10-20-completion-a9b4ce1/final.xml -q`.
2. With the installed-dependency runner in the P31 independent packet, run tests/test_gpu_scheduler.py, tests/test_gpu_scheduler_audit.py, and phase06 tests `test_P06_gate_quarantines_code_or_test_or_evaluator_changes` / `test_P06_gate_refuses_when_its_policy_or_heldout_data_are_tampered`. Save supplemental.xml. Physical CUDA remains skipped.
3. Run run_journeys.py in this directory. It uses owned temporary files and existing skills Python, actual registry/adapters/stores, recording-fake cloud and simulated Brain/hook. It writes actual Python component call journals and 30 randomized pinned/current exception cleanup pairs. Workbook model author/approvals are simulated. Manual fixture cleanup of the old leaking hook is outside timing.
4. Run `python -m jarvis.launcher --check`; preserve repair_required output and do not install to hide it.
5. Run collect.py only after completed XML results exist; it verifies source/original evidence, writes classifications/reports and appends cumulative handoff documentation.

Before-fixes.xml preserves pre-repair failing tests; reproducing those requires restoring only the two pinned source files in a separate owned checkout. Do not reverse retained patches or mutate the user's running checkout. Benchmark source is loaded from git at the pinned SHA into an isolated module; no native hook is started. Cold/warm voice/GPU performance and peak memory are NOT measured.
