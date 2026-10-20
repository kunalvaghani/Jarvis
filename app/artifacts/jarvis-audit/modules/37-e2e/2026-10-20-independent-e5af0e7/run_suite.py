"""Independent source-root selection, read-only installed dependencies, safe fixtures."""
import argparse
import ast
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--mode', choices=['boundary', 'full', 'selection'], default='full')
parser.add_argument('--focus', action='append', default=[])
options, remaining = parser.parse_known_args()
APP = options.root.resolve()
os.chdir(APP)  # Owned child interpreters must import the audited source as well.
sys.path.insert(0, str(APP))
INSTALL = Path('D:/Kunals GitHub Repo/Jarvis/app')
from jarvis import app_adapters
from tests import test_phase02_execution_strategy, test_phase03_living_skills
app_adapters.APP = INSTALL
for module in [test_phase02_execution_strategy, test_phase03_living_skills]:
    module.SKILLS = INSTALL / '.venv-skills/Scripts/python.exe'
import pytest

boundary = ['test_prompt34_completion.py', 'test_prompt34_remaining_routes.py', 'test_prompt35_security.py',
            'test_prompt36_observability.py', 'test_prompt37_e2e_boundaries.py']
selected = [str(APP / 'tests' / p) for p in boundary]
excluded = []
if options.mode == 'full':
    from jarvis import codex_workload
    installed_localgithub = codex_workload.localgithub
    codex_workload.localgithub = lambda config: installed_localgithub({'localgithub_path': str(INSTALL.parents[1] / 'LocalGithub'), **config})
    from tests import test_skill_selection_audit as census
    from jarvis import hermes_skills
    HermesSkills = hermes_skills.HermesSkills
    hermes_skills.HermesSkills = lambda base: HermesSkills(INSTALL if Path(base).resolve() == APP else base)
    census.HermesSkills = hermes_skills.HermesSkills
    files = ['test_groq.py', 'test_repository_skill_isolation.py', 'test_toolkits.py', 'test_agent_runtime.py',
        'test_phase01_baseline.py', 'test_repo_abilities.py', 'test_prompt31_approval_binding.py',
        'test_prompt33_boundaries.py', 'test_prompt34_dependency_repair.py', 'test_prompt33_mcp_boundaries.py',
        'test_prompt33_followup.py', 'test_desktop_actions.py', 'test_desktop_tasks.py', 'test_runtime_health.py',
        'test_cognition_and_routing.py', 'test_task_state.py', 'test_task_recovery.py', 'test_everyday_runtime.py',
        'test_intent_testbook.py', 'test_gpu_scheduler.py', 'test_independent_review.py', 'test_windows_commands.py',
        'test_ui_controls.py', 'test_recovery.py', 'test_launcher_readiness.py', 'test_speech.py',
        'test_f5_speech.py', 'test_natural_voice.py', 'test_buddy.py', 'test_island.py', 'test_island_desk.py']
    files += [p.name for p in (APP / 'tests').glob('test_*audit.py') if p.name != 'test_web_development_audit.py']
    selected += [str(APP / 'tests' / p) for p in sorted(set(files)) if (APP / 'tests' / p).is_file()]
    for name in ['test_phase02_execution_strategy.py', 'test_phase03_living_skills.py', 'test_phase04_learning_memory.py',
                 'test_phase05_escalation_demonstration.py', 'test_phase06_controlled_evolution.py',
                 'test_phase07_azr_training.py', 'test_phase08_integration.py', 'test_web_development_audit.py']:
        path = APP / 'tests' / name
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith('test_'): continue
            reason = ''
            if name == 'test_web_development_audit.py':
                if 'preview' in [a.arg for a in node.args.args]:
                    reason = 'Owned authored browser/build prerequisites absent in audit checkout; no install/download.'
            elif any(term in node.name for term in ['demonstration', 'demonstrated', 'real_hook', 'restart_recovery',
                    'local_embedding', 'vault_', 'viking', 'incremental_reindex', 'damaged_manifest', 'browser_', 'blender_sandbox']):
                reason = 'Native hook/model/vault/browser/engine acceptance excluded; dedicated fake boundary tests run separately.'
            elif name == 'test_phase06_controlled_evolution.py' and node.name not in {
                    'test_P06_protected_sources_can_never_be_surfaces', 'test_P06_mutation_is_literal_only_and_bounded',
                    'test_P06_production_surfaces_match_modules_and_evaluator_policy',
                    'test_P06_independent_gate_rule_matches_but_does_not_trust_the_worker',
                    'test_P06_eevee_phases_keep_floor_pareto_front_and_reject_unsafe_prompts',
                    'test_P06_gate_quarantines_code_or_test_or_evaluator_changes',
                    'test_P06_gate_refuses_when_its_policy_or_heldout_data_are_tampered',
                    'test_P06_lab_has_no_shared_git_metadata_and_candidates_do_not_touch_production'}:
                reason = 'Broader evolution/promotion lab excluded; sealed/tamper and ownership checks selected explicitly.'
            elif name == 'test_phase08_integration.py' and 'flow_C' in node.name:
                reason = 'Broad real-source mutation experiment deferred; independent gate tests retained.'
            if reason:
                excluded.append({'id': name + '::' + node.name, 'status': 'BLOCKED', 'reason': reason})
            else:
                selected.append(str(path) + '::' + node.name)

selected = list(dict.fromkeys(selected))
if options.focus:
    selected = [str(APP) + '/' + node for node in options.focus]
if options.mode == 'selection':
    print(json.dumps(selected)); raise SystemExit(0)
OUT = Path(__file__).resolve().parent
(OUT / (options.mode + '-selection.json')).write_text(json.dumps({'source_root_kind': 'pinned' if 'baseline' in str(APP) else 'candidate',
    'selected': [s.replace(str(APP), '%SOURCE_APP%') for s in selected], 'excluded': excluded}, indent=2), encoding='utf-8')
raise SystemExit(pytest.main(selected + remaining))
