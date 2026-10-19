"""Run safe neighboring suites against this worktree and installed dependency roots."""
from pathlib import Path
import runpy
import sys

APP = next(p for p in Path(__file__).resolve().parents if (p / 'main.py').is_file())
sys.argv[1:1] = [str(APP / 'tests' / name) for name in (
    'test_prompt37_e2e_boundaries.py', 'test_everyday_runtime.py',
    'test_task_recovery.py', 'test_intent_testbook.py')]
runpy.run_path(str(APP / 'artifacts/jarvis-audit/modules/36-observability/2026-10-20-completion-a9b4ce1/run_regressions.py'), run_name='__main__')
