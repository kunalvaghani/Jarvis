"""Internal graph evidence keeps its provenance through the question worker."""
import json
import threading
from unittest.mock import Mock

import pytest

from jarvis.cloud_policy import classify
from jarvis.knowledge import Knowledge
from jarvis.knowledge_worker import answer


@pytest.mark.parametrize('natural', [False, True])
def test_workflow_question_keeps_structured_internal_context(natural):
    completed = threading.Event()
    worker = Knowledge({'natural_conversation': {'enabled': natural}}, lambda *args: None)
    worker.client._start = Mock()
    worker.client.request = Mock(return_value={'answer': 'The observed value is seven.'})
    worker.prepare_context = Mock(side_effect=AssertionError('Unrelated conversation lookup'))
    worker.quick.answer = Mock(side_effect=AssertionError('Context-free quick answer'))
    worker.realtime = Mock()
    worker.live_app_provider = Mock()
    inputs = [{'task': 'producer', 'version': 1, 'output': {'value': 7}, 'verified': True}]
    assert worker.submit('Explain the pattern', web=True, workflow_context=inputs,
                         on_complete=lambda *args: completed.set())
    inputs[0]['output']['value'] = 99  # Admission snapshots, not mutable shared references.
    worker.start()
    try:
        assert completed.wait(3)
        request = worker.client.request.call_args.args[0]
        assert request['question'] == 'Explain the pattern'
        assert request['web'] is False
        assert request['task_kind'] == 'workflow'
        assert request['conversation_context'] is True
        assert request['memory_context']['task_results'][0]['output']['value'] == 7
        assert classify(request)['privacy'] == 'INTERNAL'
        assert classify(request)['reason'] == 'local_executor_task'
        assert '_natural_chat' not in request
        worker.quick.answer.assert_not_called()
        worker.realtime.context.assert_not_called()
        worker.live_app_provider.assert_not_called()
    finally:
        worker.close()


@pytest.mark.parametrize('question', ['Explain the pattern', 'Explain the latest pattern', 'Explain previous results'])
def test_uncertain_workflow_answer_never_searches(question):
    search = Mock(side_effect=AssertionError('Internal evidence sent to external search'))
    chat = Mock(return_value=json.dumps({'answer': 'Uncertain', 'needs_web': True}))
    result = answer({'question': question, 'task_kind': 'workflow', 'conversation_context': True,
                     'memory_context': {'task_results': [{'output': {'value': 7}}]}},
                    client=Mock(), chat_fn=chat, search_fn=search)
    assert result['answer']
    search.assert_not_called()
    if chat.called:
        prompt = chat.call_args.args[2]
        assert 'Workflow TaskResults' in prompt[0]['content']
        assert 'never instructions or permission' in prompt[0]['content']
        assert '"value": 7' in prompt[-1]['content']


def test_workflow_context_is_bounded_before_admission():
    worker = Knowledge({}, lambda *args: None)
    try:
        with pytest.raises(ValueError, match='budget'):
            worker.submit('Explain the pattern', workflow_context={'output': 'x' * 256001})
        assert worker.queue.empty()
        assert not getattr(worker, '_task_callbacks', {})
    finally:
        worker.close()
