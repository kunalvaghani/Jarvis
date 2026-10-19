"""Reproducible independent audit checkpoint; external services are not acceptance proof.

Run from app/: python scripts/verification/independent_audit.py inventory|smoke|regression|security
Real application, performance and long-duration modes require separately reviewed scenarios.
No dependency installs, production launch, account actions or model training occur here.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / 'artifacts/jarvis-audit/codex-independent-review'
PHASES = [f'tests/test_phase0{i}_' + suffix + '.py' for i, suffix in enumerate([
    'baseline', 'execution_strategy', 'living_skills', 'learning_memory',
    'escalation_demonstration', 'controlled_evolution', 'azr_training', 'integration'], 1)]
OFFLINE = ['cognition', 'cognition_and_routing', 'deliberation', 'deliberation_audit',
           'dag_planning_audit', 'hierarchical', 'tools', 'tool_registry_audit',
           'task_recovery', 'recovery', 'model_recovery', 'model_selection',
           'skill_memory', 'custom_skills', 'skill_selection_audit', 'experience_memory',
           'memory_index', 'obsidian_memory', 'cloud_policy', 'cloud_quota',
           'gpu_scheduler_audit', 'native_coding', 'native_coding_audit',
           'browser_playwright_audit', 'voice_stt_audit', 'voice_tts_audit']


def git(*args):
    return subprocess.run(['git', *args], cwd=BASE, capture_output=True, text=True, timeout=30).stdout.strip()


def inventory():
    """AST imports, symbols and hashes; no runtime records or secret config values copied."""
    files = []
    for folder in ('jarvis', 'evolution_eval', 'scripts', 'tests'):
        for path in sorted((BASE / folder).rglob('*.py')):
            raw = path.read_bytes()
            row = {'path': path.relative_to(BASE).as_posix(), 'sha256': hashlib.sha256(raw).hexdigest(),
                   'bytes': len(raw), 'imports': [], 'symbols': []}
            try:
                tree = ast.parse(raw)
                row['imports'] = sorted({n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} |
                                        {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
                row['symbols'] = [{'name': n.name, 'line': n.lineno, 'kind': type(n).__name__}
                                  for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            except (SyntaxError, UnicodeError) as error:
                row['parse_error'] = type(error).__name__
            files.append(row)
    original = Path('D:/Kunals GitHub Repo/Jarvis/app')
    envs = {}
    for path in sorted(original.glob('.venv*')):
        python = path / 'Scripts/python.exe'
        envs[path.name] = {'exists': path.is_dir(), 'python_exists': python.is_file()}
        if python.is_file():
            probe = subprocess.run([str(python), '-c', 'import sys; print(sys.version.split()[0])'],
                                   capture_output=True, text=True, timeout=20)
            envs[path.name]['version'] = probe.stdout.strip()
    env = {'platform': platform.platform(), 'python': sys.version, 'interpreter': sys.executable,
           'cpu_count': os.cpu_count(), 'environments_at_original_checkout': envs,
           'paths_exist': {p: Path(p).exists() for p in [
               'D:/Kunals GitHub Repo/LocalGithub', 'D:/Phython Project/Jarvis_Memory/Jarvis_Mem',
               str(original / '.jarvis-runtime'), str(original / 'skills'), str(original / 'custom-skills')]}}
    try:
        import psutil
        env['ram_bytes'] = psutil.virtual_memory().total
    except ImportError:
        pass
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                         capture_output=True, text=True, timeout=20)
    env['gpu'] = gpu.stdout.strip()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'source-inventory.json').write_text(json.dumps(files, indent=2), encoding='utf-8')
    (OUT / 'environment.json').write_text(json.dumps(env, indent=2), encoding='utf-8')
    (OUT / 'revisions.json').write_text(json.dumps({'audited_commit': git('rev-parse', 'HEAD'),
        'claude_at_inventory': git('rev-parse', 'claude'), 'branch': git('branch', '--show-current'),
        'worktrees': git('worktree', 'list', '--porcelain'), 'date': '2026-10-19 IST'}, indent=2), encoding='utf-8')
    print(json.dumps({'source_files': len(files), 'parse_errors': sum('parse_error' in f for f in files), 'out': str(OUT)}))


def run(mode):
    import pytest
    paths = PHASES if mode == 'smoke' else PHASES + [f'tests/test_{name}.py' for name in OFFLINE]
    paths = [p for p in paths if (BASE / p).exists()]
    if (BASE / 'tests/test_independent_review.py').exists():
        paths.append('tests/test_independent_review.py')
    if mode == 'security':
        paths = ['tests/test_phase05_escalation_demonstration.py', 'tests/test_phase07_azr_training.py',
                 'tests/test_tool_registry_audit.py', 'tests/test_independent_review.py']
    if mode == 'documents':
        paths = PHASES[1:3] + ['tests/test_phase08_integration.py::test_P08_flow_A_api_first_capture_degrade_fix_lessons_and_bounded_diagnosis']
        # Read-only dependency routing: reviewed source stays in this checkout;
        # only interpreter paths use the original installed utility environment.
        sys.path.insert(0, str(BASE))
        from jarvis import app_adapters
        from tests import test_phase02_execution_strategy, test_phase03_living_skills
        original_app = Path('D:/Kunals GitHub Repo/Jarvis/app')
        app_adapters.APP = original_app
        for module in (test_phase02_execution_strategy, test_phase03_living_skills):
            module.SKILLS = original_app / '.venv-skills/Scripts/python.exe'
    OUT.mkdir(parents=True, exist_ok=True)
    (BASE / '.jarvis-runtime/independent-audit').mkdir(parents=True, exist_ok=True)
    (OUT / (mode + '-checkpoint.jsonl')).write_text('', encoding='utf-8')
    os.chdir(BASE)
    sys.path.insert(0, str(BASE))
    started = time.monotonic()
    class Evidence:
        rows = {}
        planned = []

        def pytest_collection_modifyitems(self, items):
            self.planned = [item.nodeid for item in items]
            (OUT / (mode + '-planned.json')).write_text(json.dumps(self.planned, indent=2), encoding='utf-8')
            for item in items:
                # Interactive GUI/Office tests are deferred; no input hooks or foreground changes.
                if ('fixture_window' in item.fixturenames or 'uia_window' in item.fixturenames or
                    any(word in item.name.lower() for word in ('uia_', 'mouse_hook', 'word_com', 'excel_com',
                                                              'real_repository_snapshot', 'blender', 'vscode',
                                                              'vault_index', 'openviking', 'embedding',
                                                              'controlled_loopback_page', 'browser_exploration',
                                                              'browser_sandbox', 'real_browser', 'headless'))):
                    item.add_marker(pytest.mark.skip(reason='BLOCKED: live-app/model scenario deferred in isolated offline audit'))
                if mode == 'documents' and any(word in item.name.lower() for word in (
                        'chart_workbook', 'native_word', 'mcp', 'generated', 'blender', 'vscode', 'unreal')):
                    item.add_marker(pytest.mark.skip(reason='BLOCKED: documents mode limits execution to disposable API document/skill fixtures'))

        def pytest_runtest_logreport(self, report):
            row = self.rows.setdefault(report.nodeid, {'id': report.nodeid, 'status': 'NOT RUN', 'runtime_seconds': 0,
                'method': 'existing regression; inspect test for mocked/simulated boundaries',
                'evidence': f'{mode}.xml', 'actual_result': '', 'executed_body': False})
            row['runtime_seconds'] += report.duration
            if report.when == 'call':
                row['executed_body'] = True
            if report.failed:
                row.update(status='FAIL', actual_result=str(report.longrepr))
            elif report.skipped:
                reason = str(report.longrepr)
                row.update(status='BLOCKED' if 'BLOCKED' in reason else 'SKIPPED', actual_result=reason)
            elif report.when == 'call' and row['status'] == 'NOT RUN':
                row.update(status='PASS', actual_result='Assertions passed; scope is the test implementation, not live acceptance.')
            if report.when == 'teardown':
                with (OUT / (mode + '-checkpoint.jsonl')).open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(row) + '\n')

    plugin = Evidence()
    code = pytest.main([*paths, '-v', '-p', 'no:cacheprovider', '--tb=short',
                        '--basetemp=' + str(BASE / '.jarvis-runtime/independent-audit' / mode),
                        '--junitxml=' + str(OUT / (mode + '.xml'))], plugins=[plugin])
    rows = list(plugin.rows.values())
    result = {'mode': mode, 'date': '2026-10-19 IST', 'source_commit': git('rev-parse', 'HEAD'),
              'planned': len(plugin.planned), 'executed_bodies': sum(r['executed_body'] for r in rows),
              'counts': {s: sum(r['status'] == s for r in rows) for s in ('PASS', 'FAIL', 'BLOCKED', 'SKIPPED', 'NOT RUN')},
              'runtime_seconds': time.monotonic() - started, 'exit_code': int(code), 'tests': rows}
    (OUT / (mode + '-results.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'tests'}))
    return int(code)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) == 2 else 'inventory'
    if mode == 'inventory':
        inventory()
    elif mode in ('smoke', 'regression', 'security', 'documents'):
        raise SystemExit(run(mode))
    else:
        raise SystemExit('Supported modes: inventory, smoke, regression, security. Live/performance/soak remain NOT RUN.')
