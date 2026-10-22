import json
from unittest.mock import patch

import pytest

from jarvis.small_model import Outcomes, route, settings

NAMES = {'qwen3.5:2b', 'qwen3.5:4b', 'qwen3.5:9b'}


@pytest.mark.parametrize('goal', ['Open Calculator', 'Search YouTube for jazz', 'Pause Spotify', 'Read notes.txt in Downloads'])
def test_routine_uses_small_without_a_classifier(goal):
    assert route('next_step', {'goal': goal}, {}, NAMES)['model'] == 'qwen3.5:4b'


@pytest.mark.parametrize('data', [
    {'goal': 'Debug the coding project'}, {'goal': 'Inspect Blender'},
    {'goal': 'Research unfamiliar software'}, {'goal': 'Open Calculator', 'failures': ['failed']},
    {'goal': 'Open Calculator', 'last_result': {'confirmed': False}},
    {'goal': 'Open Calculator', 'plan_validation_error': 'bad arguments'},
    {'goal': 'Open Calculator', 'images': ['image']},
])
def test_teacher_receives_difficult_or_failed_subtask(data):
    assert route('next_step', data, {}, NAMES)['model'] == 'qwen3.5:9b'


def test_disabled_hierarchy_and_non_planning_operations_preserve_existing_models():
    assert route('next_step', {'goal': 'Open Calculator'}, {'model_hierarchy': {'enabled': False}}, NAMES)['model'] is None
    assert route('code_edit', {}, {}, NAMES)['model'] is None
    assert route('verify', {}, {}, NAMES)['model'] is None
    assert route('next_step', {'goal': 'Open Calculator'}, {}, {'qwen3.5:9b'})['model'] == 'qwen3.5:9b'


def task(identity, status='completed', proof=True):
    return {'task_id': identity, 'status': status, 'checkpoints': [
        {'stage': 'model_route', 'evidence': json.dumps({'category': 'desktop', 'model': 'qwen3.5:4b'})},
        *([{'stage': 'goal_verified', 'evidence': 'Fresh goal check'},
           {'stage': 'verified', 'evidence': 'Native readback'}] if proof else [])]}


def test_outcomes_are_idempotent_and_do_not_confuse_completion_with_accuracy(tmp_path):
    history = Outcomes(tmp_path/'outcomes.sqlite3')
    history.record(task('unproved', proof=False))
    assert not history.path.exists()
    for i in range(2):
        history.record(task(str(i), 'failed', False))
        history.record(task(str(i), 'failed', False))
    assert history.unreliable('desktop', 'qwen3.5:4b')
    assert route('plan', {'goal': 'Open Calculator'}, {}, NAMES, history)['reason'] == 'verified_history'
    assert not history.unreliable('media', 'qwen3.5:4b')


def test_configuration_is_strict():
    for value in ({'enabled': 1}, {'execution_model': 'cloud-model'}, {'reasoning_model': 'tiny'}, {'typo': True}):
        with pytest.raises(ValueError):
            settings({'model_hierarchy': value})


def test_one_inference_fallback_preserves_all_context_and_completed_progress():
    from jarvis.brain_worker import Models
    worker = Models()
    request = {'operation': 'next_step', 'options': {}, 'goal': 'Open Calculator',
               'completed': [{'action': 'open', 'verified': True}], 'skill_context': {'guide': 'reference'},
               'tools': [{'action': 'open'}], 'memory_context': {'private': 'local only'}}
    calls = []
    def predict(data):
        calls.append(data)
        if len(calls) == 1:
            worker.routing_trace = {'model': 'qwen3.5:4b', 'category': 'desktop', 'reason': 'routine'}
            raise ValueError('Invalid proposal')
        return {'steps': [], 'model_used': 'qwen3.5:9b'}
    with patch.object(worker, '_predict', side_effect=predict):
        result = worker.predict(request)
    worker.client.close()
    assert len(calls) == 2
    assert calls[1]['completed'] is request['completed']
    assert calls[1]['memory_context'] is request['memory_context']
    assert calls[1]['tools'] is request['tools']
    assert result['model_route']['reason'] == 'executor_rejected'


def test_teacher_failure_is_not_retried():
    from jarvis.brain_worker import Models
    worker = Models()
    def failed(data):
        worker.routing_trace = {'model': 'qwen3.5:9b'}
        raise ValueError('Teacher unavailable')
    with patch.object(worker, '_predict', side_effect=failed) as predict:
        with pytest.raises(ValueError):
            worker.predict({'options': {}})
        assert predict.call_count == 1
    worker.client.close()


def test_verified_recovery_returns_routine_work_to_student_without_erasing_history():
    data = {'goal': 'Open Calculator', 'failures': [{'action': 'open', 'reason': 'old failure'}],
            'last_result': {'verified': True, 'confirmed': True}}
    assert route('next_step', data, {}, NAMES)['model'] == 'qwen3.5:4b'
    assert data['failures']
    data['last_result']['confirmed'] = False
    assert route('next_step', data, {}, NAMES)['model'] == 'qwen3.5:9b'


def test_small_gpu_admission_shrinks_for_speech_and_unknown_hardware():
    from jarvis.gpu_scheduler import allocation, settings as gpu_settings
    policy = gpu_settings({'enabled': True})
    hardware = {'total_mb': 4096, 'used_mb': 0}
    for model in ('qwen3.5:2b', 'qwen3.5:4b'):
        normal = allocation(model, 4096, policy, hardware)
        assert normal > 0
        assert allocation(model, 4096, {**policy, 'speech_reserve_mb': 3072}, hardware) < normal
        assert allocation(model, 4096, policy, None) == 0


def test_local_memory_embeddings_use_cpu_without_dropping_semantic_retrieval():
    from jarvis.local_embeddings import embed
    from unittest.mock import MagicMock
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b'{"embeddings":[[3,4]]}'
    with patch('urllib.request.urlopen', return_value=response) as call:
        assert embed(['public fixture']) == [[.6, .8]]
    payload = json.loads(call.call_args.args[0].data)
    assert payload['options']['num_gpu'] == 0
    assert payload['input'] == ['search_document: public fixture']
