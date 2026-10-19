"""Phase 7: AZR-style tasks, independent oracle, sandbox, rewards, dataset curation, proposer, registry and gates.

Docker-backed sandbox tests skip as BLOCKED when the reviewed runtime image is unavailable.
GPU training, resume, cancellation and preemption are exercised by recorded real runs
(artifacts/jarvis-audit/phase-07); here the trainer's argument bounds and foreground check are tested.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from jarvis import azr_dataset, azr_tasks  # noqa: E402
from jarvis.azr_reward import CORRECT, MALFORMED, WRONG, score_symbolic  # noqa: E402
from jarvis.azr_tasks import (abduction_task, check_abduction, check_deduction, deduction_task, execute,  # noqa: E402
                              induction_task, render_target, screen_program)


def sandbox_ready():
    try:
        from jarvis.mcp_synthesis import image_status
        return image_status()['available']
    except Exception:
        return False


needs_sandbox = pytest.mark.skipif(not sandbox_ready(), reason='BLOCKED: reviewed Docker runtime image unavailable')


# ---- environment and deduction ----------------------------------------------------------------------------------------
def test_P07_generators_are_deterministic_and_answers_come_from_the_simulation():
    assert deduction_task(5) == deduction_task(5) and abduction_task(5) == abduction_task(5)
    assert induction_task(5) == induction_task(5)
    task = deduction_task(11)
    assert task['answer'] == execute(task['initial'], task['calls'])


def test_P07_deduction_halts_at_first_failure_and_scores_outcomes():
    initial = {'files': {'docs/a.txt': 'x'}, 'apps': [], 'clipboard': ''}
    calls = [{'id': 's1', 'tool': 'append_file', 'args': {'path': 'docs/a.txt', 'text': 'y'}},
             {'id': 's2', 'tool': 'delete_file', 'args': {'path': 'docs/missing.txt'}},
             {'id': 's3', 'tool': 'create_file', 'args': {'path': 'docs/b.txt', 'content': 'z'}}]
    final = execute(initial, calls)
    assert final == {'files': {'docs/a.txt': 'xy'}, 'apps': [], 'clipboard': '',
                     'halted': {'step': 's2', 'reason': 'missing:docs/missing.txt'}}
    task = {'mode': 'deduction', 'initial': initial, 'calls': calls, 'answer': final}
    assert score_symbolic(task, 'The result is ' + json.dumps(final))['reward'] == CORRECT
    wrong = {**final, 'files': {'docs/a.txt': 'xy', 'docs/b.txt': 'z'}, 'halted': None}
    assert score_symbolic(task, json.dumps(wrong))['reward'] == WRONG
    assert score_symbolic(task, 'no idea')['reward'] == MALFORMED
    assert score_symbolic(task, json.dumps({'files': {}}))['reward'] == MALFORMED  # valid JSON, wrong schema


# ---- abduction: outcome judged, many correct answers ------------------------------------------------------------------
def test_P07_abduction_accepts_any_valid_dag_and_rejects_unsafe_ordering():
    initial = {'files': {'docs/a.txt': 'red'}, 'apps': [], 'clipboard': ''}
    desired = {'files': {'docs/a.txt': 'red', 'work/b.txt': 'red', 'tmp/c.txt': 'blue'}, 'apps': ['editor'], 'clipboard': ''}
    task = {'mode': 'abduction', 'initial': initial, 'desired': desired}
    plan_a = [{'id': 'a', 'tool': 'copy_file', 'args': {'src': 'docs/a.txt', 'dst': 'work/b.txt'}, 'deps': []},
              {'id': 'b', 'tool': 'create_file', 'args': {'path': 'tmp/c.txt', 'content': 'blue'}, 'deps': []},
              {'id': 'c', 'tool': 'open_app', 'args': {'app': 'editor'}, 'deps': []}]
    plan_b = [{'id': 'x', 'tool': 'open_app', 'args': {'app': 'editor'}, 'deps': []},
              {'id': 'y', 'tool': 'create_file', 'args': {'path': 'tmp/c.txt', 'content': 'bl'}, 'deps': ['x']},
              {'id': 'z', 'tool': 'append_file', 'args': {'path': 'tmp/c.txt', 'text': 'ue'}, 'deps': ['y']},
              {'id': 'w', 'tool': 'copy_file', 'args': {'src': 'docs/a.txt', 'dst': 'work/b.txt'}, 'deps': []}]
    assert check_abduction(task, json.dumps(plan_a))['correct']
    assert check_abduction(task, json.dumps(plan_b))['correct']  # a different, longer plan is also correct
    unordered = [dict(c) for c in plan_b]
    unordered[2] = {**unordered[2], 'deps': []}  # append races with create on the same file
    assert check_abduction(task, json.dumps(unordered))['reason'].startswith('missing_dependency')
    cyclic = [{**plan_a[0], 'deps': ['b']}, {**plan_a[1], 'deps': ['a']}, plan_a[2]]
    assert check_abduction(task, json.dumps(cyclic))['reason'] == 'cycle'
    short = plan_a[:2]
    assert check_abduction(task, json.dumps(short))['reason'] == 'goal_not_reached'
    bogus = [{**plan_a[0], 'tool': 'format_disk'}]
    assert check_abduction(task, json.dumps(bogus))['format_ok'] is False


def test_P07_reference_plans_are_verified_by_the_oracle():
    for seed in range(150):
        task = abduction_task(seed)
        assert check_abduction(task, render_target(task))['correct'], seed


# ---- induction: static screen and restricted execution --------------------------------------------------------------
@pytest.mark.parametrize('source', [
    'import os\ndef f(x):\n    return os.listdir(".")\n',
    'def f(x):\n    return eval("1+1")\n',
    'def f(x):\n    return open("/etc/passwd").read()\n',
    'def f(x):\n    while True:\n        pass\n',
    'def f(x):\n    return x.__class__.__mro__\n',
    'def f(x):\n    return __import__("os")\n',
    'x = 1\ndef f(x):\n    return x\n',
    'def g(x):\n    return x\n',
])
def test_P07_static_screen_rejects_unsafe_programs(source):
    with pytest.raises((ValueError, SyntaxError)):
        screen_program(source)


@needs_sandbox
def test_P07_sandbox_scores_generalization_and_contains_hostile_code(tmp_path):
    from jarvis.azr_reward import score_induction_batch
    from jarvis.azr_sandbox import run_programs
    task = induction_task(3, families={'sum_even'})
    lookup = 'def f(x):\n    table = ' + repr({json.dumps(c['input']): c['output'] for c in task['visible']}) + \
             '\n    return table.get(str(x).replace("\'", "\\""), 0)\n'
    items = [('good', task, task['reference_source']), ('memorised', task, '```python\n' + lookup + '```'),
             ('recursion', task, 'def f(x):\n    return f(x)\n'),
             ('memory', task, 'def f(x):\n    return [0] * (10 ** 10)\n'),
             ('slow', task, 'def f(x):\n    return sum(range(10 ** 12))\n'),
             ('escape', task, 'def f(x):\n    return open("/etc/hostname").read()\n')]
    results = score_induction_batch(tmp_path, items, run_programs)
    assert results['good']['reward'] == CORRECT and results['good']['deterministic']
    assert results['memorised']['reason'] in {'visible_only', 'fails_visible'} and results['memorised']['reward'] == WRONG
    for key in ('recursion', 'memory', 'slow'):
        assert results[key]['correct'] is False and results[key]['reward'] == WRONG
    assert results['escape']['reward'] == MALFORMED  # rejected before execution (forbidden name)
    raw = run_programs(tmp_path, [{'id': 'p', 'source': 'def f(x):\n    return open\n', 'cases': [{'input': 1, 'output': 1}]}])
    assert raw['p']['screen'].startswith('rejected')


# ---- dataset curation ------------------------------------------------------------------------------------------------
def test_P07_dataset_splits_are_leak_free_versioned_and_tamper_evident(tmp_path):
    counts = {'train': {'deduction': 25, 'abduction': 25, 'induction': 25},
              'validation': {'deduction': 5, 'abduction': 5, 'induction': 5},
              'heldout': {'deduction': 8, 'abduction': 8, 'induction': 8}}
    datasets, meta = azr_dataset.build(counts)
    assert all(v == {'signatures': 0, 'ids': 0} for v in meta['leakage'].values())
    families = {r['task']['family'] for r in datasets['train'] + datasets['validation'] if r['task']['mode'] == 'induction'}
    assert not families & azr_dataset.HELDOUT_FAMILIES
    assert {r['task']['family'] for r in datasets['heldout'] if r['task']['mode'] == 'induction'} <= azr_dataset.HELDOUT_FAMILIES
    for rows in datasets.values():
        assert len({r['id'] for r in rows}) == len(rows)
        for row in rows:
            assert row['provenance']['answer_source'] and row['provenance']['env_version'] == azr_tasks.ENV_VERSION
    manifest = azr_dataset.write(tmp_path / 'v1', datasets, meta)
    assert manifest['counts']['train'] == len(datasets['train'])
    assert azr_dataset.load(tmp_path / 'v1', 'train')[0]['id'] == datasets['train'][0]['id']
    path = tmp_path / 'v1' / 'train.jsonl'
    path.write_text(path.read_text(encoding='utf-8').replace('"deduction"', '"deduction" ', 1), encoding='utf-8')
    with pytest.raises(ValueError, match='manifest hash'):
        azr_dataset.load(tmp_path / 'v1', 'train')
    with pytest.raises(FileExistsError):
        azr_dataset.write(tmp_path / 'v1', datasets, meta)


def test_P07_training_targets_are_oracle_answers_not_model_text():
    task = deduction_task(42)
    target = json.loads(render_target(task))
    assert target == task['answer'] == execute(task['initial'], task['calls'])
    assert check_deduction(task, render_target(task))['correct']


# ---- proposer: the model proposes tasks, never answers -------------------------------------------------------------
def test_P07_proposer_validation_ignores_model_answers_and_penalizes_bad_proposals(monkeypatch):
    from jarvis import azr_proposer
    proposal = {'initial': {'files': {'docs/a.txt': 'one'}, 'apps': [], 'clipboard': ''},
                'calls': [{'id': 's1', 'tool': 'append_file', 'args': {'path': 'docs/a.txt', 'text': ' two'}}],
                'answer': {'files': {'docs/a.txt': 'FAKE'}}}
    task = azr_proposer.validate_deduction(proposal)
    assert task['answer']['files'] == {'docs/a.txt': 'one two'}  # computed, the proposed answer is ignored
    abduction = azr_proposer.abduction_from(task)
    assert abduction and check_abduction(abduction, render_target(abduction))['correct']
    proposer = azr_proposer.Proposer(BASE)
    monkeypatch.setattr(azr_proposer, 'ollama', lambda *a, **k: '{"initial": {"files": {}}, "calls": [{"tool": "rm_rf", "args": {}}]}')
    assert proposer.propose_deduction([]) is None and proposer.rejections[-1]['format_reward'] == -1
    answers = iter([json.dumps(task['answer']), 'wrong', json.dumps(task['answer']), 'wrong'])
    monkeypatch.setattr(azr_proposer, 'ollama', lambda *a, **k: next(answers))
    assert proposer.learnability(task) == {'solve_rate': 0.5, 'r_propose': 0.5, 'rollouts': 4}
    monkeypatch.setattr(azr_proposer, 'ollama', lambda *a, **k: json.dumps(task['answer']))
    assert proposer.learnability(task)['r_propose'] == 0.0  # always solved: no learning signal (AZR)
    monkeypatch.setattr(azr_proposer, 'ollama', lambda *a, **k: 'nothing')
    assert proposer.learnability(task)['r_propose'] == 0.0  # never solved: no learning signal (AZR)


# ---- trainer guards, registry and gates -----------------------------------------------------------------------------
def test_P07_trainer_rejects_unbounded_budgets_and_overwrites(tmp_path):
    script = BASE / 'scripts' / 'training' / 'train_azr_lora.py'
    for extra in (['--max-steps', '0'], ['--max-steps', '5000'], ['--grad-accum', '100'], ['--max-len', '9000']):
        result = subprocess.run([sys.executable, str(script), '--dataset', str(tmp_path), '--out', str(tmp_path / 'o'), *extra],
                                capture_output=True, text=True, cwd=BASE)
        assert result.returncode == 2 and 'bounded' in result.stderr
    (tmp_path / 'exists').mkdir()
    result = subprocess.run([sys.executable, str(script), '--dataset', str(tmp_path), '--out', str(tmp_path / 'exists')],
                            capture_output=True, text=True, cwd=BASE)
    assert result.returncode == 2 and 'refusing to overwrite' in result.stderr


def test_P07_foreground_gpu_check_reads_the_shared_lease_registry(monkeypatch, tmp_path):
    from scripts.training import train_azr_lora as trainer
    monkeypatch.setattr(trainer, 'BASE', tmp_path)
    assert trainer.foreground_gpu_busy() is False
    import os
    import psutil
    gpu = tmp_path / '.jarvis-runtime' / 'gpu'
    gpu.mkdir(parents=True)
    row = {'token': 'a' * 32, 'pid': os.getpid(), 'birth': psutil.Process().create_time(), 'role': 'question',
           'model': 'qwen3.5:9b', 'priority': 80, 'queued_at': 0}
    (gpu / 'state.json').write_text(json.dumps({'active': None, 'pending': [row]}), encoding='utf-8')
    assert trainer.foreground_gpu_busy() is True
    (gpu / 'state.json').write_text(json.dumps({'active': {**row, 'pid': 999999}, 'pending': []}), encoding='utf-8')
    assert trainer.foreground_gpu_busy() is False  # stale (dead) holders do not block training forever


def test_P07_registry_keeps_checkpoints_experimental_until_gated_exported_and_approved(tmp_path):
    from jarvis.model_registry import ModelRegistry
    adapter = tmp_path / 'adapter'
    adapter.mkdir()
    (adapter / 'adapter_model.safetensors').write_bytes(b'weights')
    registry = ModelRegistry(tmp_path)
    weak = registry.register(adapter, 'b' * 64, 'd' * 64, {'decision': 'not_improved', 'seal': 's'})
    with pytest.raises(ValueError, match='qualified'):
        registry.approve(weak['id'], lambda *a: None)
    good = registry.register(adapter, 'b' * 64, 'd' * 64, {'decision': 'qualified_experimental', 'seal': 's'},
                             {'exact_match_rate': 0.5, 'merged_reloads_with_transformers': True})
    with pytest.raises(ValueError, match='Export'):
        registry.approve(good['id'], lambda *a: None)
    ready = registry.register(adapter, 'b' * 64, 'd' * 64, {'decision': 'qualified_experimental', 'seal': 's'},
                              {'exact_match_rate': 1.0, 'merged_reloads_with_transformers': True})
    def deny(*args):
        raise ValueError('Action cancelled; approval was not given.')
    with pytest.raises(ValueError, match='approval'):
        registry.approve(ready['id'], deny)
    assert {r['status'] for r in registry.entries()} == {'experimental'}
    (adapter / 'adapter_model.safetensors').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='changed'):
        registry.approve(ready['id'], lambda *a: None)
    config = (BASE / 'config' / 'config.json').read_text(encoding='utf-8')
    assert 'trained_pc_checkpoint' in config  # existing model settings untouched by Phase 7


def test_P07_model_gate_refuses_an_unsealed_evaluator(tmp_path):
    root = tmp_path / 'canon'
    evaluator = root / 'app' / 'evolution_eval'
    shutil.copytree(BASE / 'evolution_eval', evaluator, ignore=shutil.ignore_patterns('__pycache__', 'heldout', 'train'))
    (evaluator / 'heldout').mkdir()
    (evaluator / 'heldout' / 'azr_tasks.jsonl').write_text('', encoding='utf-8')
    git = ['git', '-c', 'user.name=t', '-c', 'user.email=t@localhost', '-c', 'commit.gpgsign=false']
    subprocess.run([*git, 'init', '-q'], cwd=root, check=True)
    subprocess.run([*git, 'add', '-A'], cwd=root, check=True)
    subprocess.run([*git, 'commit', '-q', '-m', 'x'], cwd=root, check=True)
    from evolution_eval.model_gate import ModelGate
    gate = ModelGate(root / 'app', evaluator)
    assert gate.retention.seal()
    (evaluator / 'heldout' / 'azr_tasks.jsonl').write_text('{"tampered": true}\n', encoding='utf-8')
    result = gate.evaluate(tmp_path / 'adapter', tmp_path / 'out')
    assert result['decision'] == 'refused' and 'evaluator_unsealed' in result['reason']


def test_P07_wilson_interval_and_policy_are_bounded():
    from evolution_eval.model_gate import wilson
    assert wilson(0, 0) == [0.0, 0.0] and wilson(30, 60)[0] < .5 < wilson(30, 60)[1]
    policy = json.loads((BASE / 'evolution_eval' / 'policy.json').read_text(encoding='utf-8'))['model_gate']
    assert policy['min_absolute_improvement'] > 0 and policy['max_latency_ratio'] <= 2 and policy['vram_limit_mb'] <= 4096
