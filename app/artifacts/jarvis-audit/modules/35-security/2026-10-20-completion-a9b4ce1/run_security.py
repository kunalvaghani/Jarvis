"""Select safe fixture tests; no native desktop/recording or model inference tests."""
import ast
from pathlib import Path
import runpy
import sys

APP = next(p for p in Path(__file__).resolve().parents if (p / 'main.py').is_file())
sys.path.insert(0, str(APP))
files = ['test_groq.py', 'test_repository_skill_isolation.py', 'test_toolkits.py', 'test_agent_runtime.py',
         'test_phase01_baseline.py', 'test_ability_forge_audit.py', 'test_repo_abilities.py',
         'test_prompt31_approval_binding.py', 'test_prompt33_boundaries.py']
selected = [str(APP / 'tests' / name) for name in files if (APP / 'tests' / name).is_file()]
for name in ['test_phase02_execution_strategy.py', 'test_phase03_living_skills.py', 'test_phase04_learning_memory.py',
             'test_phase05_escalation_demonstration.py', 'test_phase06_controlled_evolution.py',
             'test_phase07_azr_training.py', 'test_phase08_integration.py']:
    path = APP / 'tests' / name
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith('test_'):
            continue
        if any(t in node.name for t in ['demonstration', 'demonstrated', 'real_hook', 'restart_recovery',
              'local_embedding', 'vault_', 'viking', 'incremental_reindex', 'damaged_manifest',
              'browser_', 'blender_sandbox']):
            continue
        if name == 'test_phase06_controlled_evolution.py' and node.name not in {
             'test_P06_protected_sources_can_never_be_surfaces', 'test_P06_mutation_is_literal_only_and_bounded',
             'test_P06_production_surfaces_match_modules_and_evaluator_policy',
             'test_P06_independent_gate_rule_matches_but_does_not_trust_the_worker',
             'test_P06_eevee_phases_keep_floor_pareto_front_and_reject_unsafe_prompts'}:
            continue
        if name == 'test_phase08_integration.py' and 'flow_C' in node.name:
            continue
        selected.append(str(path) + '::' + node.name)
if '--final' in sys.argv:
    sys.argv.remove('--final')
    selected += [str(APP / 'tests/test_prompt35_security.py'), str(APP / 'tests/test_prompt34_completion.py'),
                 str(APP / 'tests/test_prompt34_dependency_repair.py'),
                 str(APP / 'tests/test_prompt33_mcp_boundaries.py'), str(APP / 'tests/test_prompt33_followup.py'),
                 str(APP / 'tests/test_desktop_actions.py'), str(APP / 'tests/test_desktop_tasks.py'),
                 str(APP / 'tests/test_desktop_control_audit.py')]
sys.argv[1:1] = selected
runpy.run_path(str(APP / 'artifacts/jarvis-audit/modules/31-ui-island-pip/2026-10-19-independent-0e3ad47/run_installed_dependencies.py'), run_name='__main__')
