# Reproduction / rollback

Use existing main Python. Run run_suite.py --root <isolated-e5af-app> --mode full --junitxml=<absolute-output> -q. The 104-test baseline selects P34 dependency/completion/remaining routes plus P37/task state/task recovery files. Run pytest tests/test_prompt37_ui_restart.py separately with optional JARVIS_E2E_EVIDENCE_DIR pointing to an owned packet; no setup step. run_workflows.py reproduces three owned/simulated journals and the fixed historical paired cleanup comparison.

No production rollback required. The new test is proposed via new-test.patch, which applies to the pinned index; review/integrate on claude and rerun that test. Never reset/clean the old review worktree or overwrite user config. New detached checkout retains a test-only overlay. No automatic merge/deployment, deleting user files or uncertain-write replay.
