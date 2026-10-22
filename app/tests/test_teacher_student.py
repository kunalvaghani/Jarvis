import json
from unittest.mock import patch

import pytest

from jarvis.teacher_student import compile_procedure, curated_examples


def verified_task():
    return {'status': 'completed', 'checkpoints': [
        {'stage': 'model_route', 'evidence': json.dumps({'model': 'qwen3.5:9b'})},
        {'stage': 'goal_verified', 'evidence': 'File readback matches'},
        {'stage': 'verified', 'evidence': 'Fresh native file read'}],
        'plan': {'completed': [{'action': 'read_file', 'value': 'private-notes.txt', 'folder': 'private-folder',
                                'expected': 'Read requested file', 'verified': True, 'result': 'private body'}]}}


def test_teacher_trace_compiles_parameterized_guidance_without_old_private_bindings():
    template = compile_procedure(verified_task())
    assert template['teacher'] == 'qwen3.5:9b'
    assert template['steps'][0]['arguments']['value'] == {'$slot': 'value_1'}
    assert 'private' not in json.dumps(template)
    other = verified_task()
    other['plan']['completed'][0].update(value='different.txt', folder='different-folder', result='different content')
    assert compile_procedure(other)['family'] == template['family']


@pytest.mark.parametrize('mutation', ['unverified', 'failed', 'no_goal_proof', 'small_only', 'shell'])
def test_unproved_or_unsafe_procedure_is_not_promoted(mutation):
    task = verified_task()
    if mutation == 'unverified': task['plan']['completed'][0]['verified'] = False
    if mutation == 'failed': task['failures'] = [{'action': 'read_file'}]
    if mutation == 'no_goal_proof': task['checkpoints'] = task['checkpoints'][:1]
    if mutation == 'small_only': task['checkpoints'][0]['evidence'] = json.dumps({'model': 'qwen3.5:4b'})
    if mutation == 'shell': task['plan']['completed'][0]['action'] = 'run_command'
    assert compile_procedure(task) is None


def examples():
    return [{'input': 'Public case '+str(i), 'target': '{"tool":"read_file"}',
             'family': 'family-'+str(i), 'verification': 'Deterministic test passed',
             'reviewed': True, 'verified': True, 'teacher_model': 'qwen3.5:9b', 'privacy': 'public'} for i in range(30)]


def test_family_split_prevents_parameter_variant_leakage():
    rows = examples()
    rows.append({**rows[0], 'input': 'Another variant of the same procedure'})
    split = curated_examples(rows)
    assert {r['family'] for r in split['train']}.isdisjoint({r['family'] for r in split['heldout']})


def test_private_or_unreviewed_examples_require_explicit_authorization():
    rows = examples()
    rows[0]['privacy'] = 'private'
    with pytest.raises(ValueError): curated_examples(rows)
    assert curated_examples(rows, allow_private=True)
    rows[0]['reviewed'] = False
    with pytest.raises(ValueError): curated_examples(rows, allow_private=True)


def test_offline_preparation_never_imports_training_dependencies_or_trains(tmp_path):
    from scripts.training.student_lora import main
    source = tmp_path/'public.jsonl'
    source.write_text(''.join(json.dumps(r)+'\n' for r in examples()), encoding='utf-8')
    out = tmp_path/'candidate'
    assert main(['--examples', str(source), '--out', str(out)]) == 0
    assert json.loads((out/'report.json').read_text())['status'] == 'prepared'
    assert not (out/'adapter').exists()


def test_active_foreground_blocks_training_before_output_or_base_loading(tmp_path):
    from scripts.training.student_lora import main
    source = tmp_path/'public.jsonl'
    source.write_text(''.join(json.dumps(r)+'\n' for r in examples()), encoding='utf-8')
    with patch('scripts.training.student_lora.busy', return_value=True):
        with pytest.raises(ValueError, match='Foreground'):
            main(['--examples', str(source), '--out', str(tmp_path/'blocked'), '--train',
                  '--base', str(tmp_path), '--base-manifest', str(tmp_path/'manifest.json')])
    assert not (tmp_path/'blocked').exists()


def test_training_preflight_requires_real_qwen35_support_and_official_architecture():
    from scripts.training.student_lora import training_class
    from types import SimpleNamespace
    config = {'model_type': 'qwen3_5', 'architectures': ['Qwen3_5ForConditionalGeneration']}
    with pytest.raises(ValueError, match='lacks Qwen3.5'):
        training_class(config, SimpleNamespace())
    marker = object()
    assert training_class(config, SimpleNamespace(Qwen3_5ForConditionalGeneration=marker)) is marker
    with pytest.raises(ValueError, match='architecture'):
        training_class({'model_type': 'arbitrary_remote_code'}, SimpleNamespace())


def test_heldout_grading_preserves_json_types_and_all_nested_arguments():
    from scripts.training.student_lora import target_matches
    assert target_matches('{"tool":"read_file","arguments":{"value":"notes.txt"}}',
                          '{"arguments":{"value":"notes.txt"},"tool":"read_file"}')
    assert not target_matches('{"verified":1}', '{"verified":true}')
    assert not target_matches('{"tool":"read_file","arguments":{"value":"wrong.txt"}}',
                              '{"arguments":{"value":"notes.txt"},"tool":"read_file"}')


def test_example_export_needs_consent_teacher_attribution_and_human_review():
    from jarvis.teacher_student import examples_from_task
    task = verified_task()
    task.update(goal='Read a public fixture', model_routes=[{'model': 'qwen3.5:9b'}])
    with pytest.raises(ValueError, match='authorization'):
        examples_from_task(task)
    rows = examples_from_task(task, privacy='public')
    assert rows[0]['reviewed'] is False and rows[0]['verified'] is True
    assert json.loads(rows[0]['target'])['arguments']['value'] == 'private-notes.txt'
    # The public label is an explicit curator assertion, not automatic inference.
    with pytest.raises(ValueError, match='reviewed'):
        curated_examples(rows)
    task['model_routes'].append({'model': 'qwen3.5:2b'})
    with pytest.raises(ValueError, match='wholly teacher'):
        examples_from_task(task, privacy='public')
