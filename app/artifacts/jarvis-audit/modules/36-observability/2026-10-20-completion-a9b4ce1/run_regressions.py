"""Audit current source; route only existing dependency/metadata roots read-only."""
from pathlib import Path
import runpy
import sys

APP = next(p for p in Path(__file__).resolve().parents if (p / 'main.py').is_file())
sys.path.insert(0, str(APP))
from tests import test_skill_selection_audit as audit
from jarvis.hermes_skills import HermesSkills
INSTALL = Path('D:/Kunals GitHub Repo/Jarvis/app')
audit.HermesSkills = lambda base: HermesSkills(INSTALL if Path(base).resolve() == APP.resolve() else base)
sys.argv[1:1] = ['--final', str(APP / 'tests/test_prompt36_observability.py'),
                 str(APP / 'tests/test_runtime_health.py'), str(APP / 'tests/test_cognition_and_routing.py'),
                 str(APP / 'tests/test_task_state.py'), str(APP / 'tests/test_skill_selection_audit.py')]
runpy.run_path(str(APP / 'artifacts/jarvis-audit/modules/35-security/2026-10-20-completion-a9b4ce1/run_security.py'), run_name='__main__')
