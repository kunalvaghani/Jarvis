"""Additional enabled-policy checks; real existing stores/adapters, stub text author.

Run from app with .venv/Scripts/python.exe -m pytest
artifacts/engineering-judgment/test_enabled_skill_evolution.py -q -ra.
No source, shared service or main microphone changes.
"""
from pathlib import Path
import sys

import pytest

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / 'tests'))
import test_phase03_living_skills as phase

env = phase.env


def draft(body):
    return body.split('## Steps')[0] + '\n## Steps\n' + '\n'.join(
        f'{i}. Inspect the confirmed worksheet name before the existing adapter operation.' for i in range(30))


def test_enabled_existing_real_fix_validation_and_rollback(env):
    env.skills.memory.engineering_options = {'enabled': True, 'mode': 'advisory'}
    phase.test_P03_fix_repairs_degraded_skill_minimally_and_rolls_back(env)


def test_large_bundled_fix_is_only_a_review_proposal(env):
    env.skills.memory.engineering_options = {'enabled': True}
    row = phase.by_name(env.skills, 'sheet-editing')
    phase.degrade(env.skills.store, row['skill_id'])
    before = (env.source / 'sheet-editing/SKILL.md').read_bytes()
    def author(kind, context):
        assert context['engineering_guidance'] and context['observation']
        return draft(context['body'])
    result = phase.SkillEvolution(env.skills, env.registry, author=author).fix(
        row['skill_id'], {'sheets': ['Budget']}, [])
    assert result['status'] == 'proposed'
    assert (env.source / 'sheet-editing/SKILL.md').read_bytes() == before


@pytest.mark.parametrize('failure', ['disabled-size', 'missing-observation', 'new-tool'])
def test_policy_cannot_relax_observation_or_tool_boundaries(env, failure):
    env.skills.memory.engineering_options = {'enabled': failure != 'disabled-size'}
    row = phase.by_name(env.skills, 'sheet-editing')
    phase.degrade(env.skills.store, row['skill_id'])
    proposed = draft(row['body'])
    if failure == 'new-tool':
        proposed = proposed.replace('tools: [office_xlsx]', 'tools: [office_xlsx, pdf_document]')
    message = {'disabled-size': 'not minimal', 'missing-observation': 'observed defect', 'new-tool': 'new tools'}[failure]
    with pytest.raises(ValueError, match=message):
        phase.SkillEvolution(env.skills, env.registry, author=lambda *_: proposed).fix(
            row['skill_id'], {} if failure == 'missing-observation' else {'sheets': ['Budget']}, [])


def test_large_evolved_fix_still_needs_actual_adapter_validation(env):
    env.skills.memory.engineering_options = {'enabled': True}
    captured = phase.captured(env)
    row = phase.by_name(env.skills, captured['name'])
    phase.degrade(env.skills.store, row['skill_id'])
    phase.workbook(env.docs / 'renamed.xlsx', sheet='Budget')
    before = row['body']
    with pytest.raises(ValueError):
        phase.SkillEvolution(env.skills, env.registry, author=lambda _, c: draft(c['body'])).fix(
            row['skill_id'], {'sheets': ['Budget']},
            [phase.xlsx_step('renamed.xlsx', 'write', sheet='Data', cells={'A1': 1})])
    assert phase.by_name(env.skills, captured['name'])['body'] == before
    assert env.skills.store.versions(row['skill_id'])[-1]['status'] == 'rejected'
