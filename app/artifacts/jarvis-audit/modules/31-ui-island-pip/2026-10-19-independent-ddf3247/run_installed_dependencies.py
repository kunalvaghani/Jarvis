"""Route installed interpreters read-only; execute audited source from this worktree."""
from pathlib import Path
import sys

BASE = next(p for p in Path(__file__).resolve().parents if (p / 'jarvis').is_dir() and (p / 'main.py').is_file())
sys.path.insert(0, str(BASE))
from jarvis import app_adapters
from tests import test_phase02_execution_strategy, test_phase03_living_skills
import pytest

installed = Path('D:/Kunals GitHub Repo/Jarvis/app')
assert (installed / '.venv-skills/Scripts/python.exe').is_file()
app_adapters.APP = installed
for module in (test_phase02_execution_strategy, test_phase03_living_skills):
    module.SKILLS = installed / '.venv-skills/Scripts/python.exe'
raise SystemExit(pytest.main(sys.argv[1:]))
