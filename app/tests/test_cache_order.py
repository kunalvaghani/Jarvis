"""speed.cache_order: keep the 9B planner on its cached conversation (only exact continuations reuse its cache)."""
import json
from unittest.mock import Mock, patch

import pytest

from jarvis.native_tools import plan, step_update

ROWS = [{'action': 'browse', 'description': 'Open a URL'}, {'action': 'select', 'description': 'Click'}]


@pytest.fixture(autouse=True)
def eight_k():
    with patch('jarvis.native_tools.effective_context', return_value=8192):
        yield


def client(calls, tokens):
    def post(url, json=None, timeout=None):
        calls.append(json)
        response = Mock()
        response.json.return_value = {'message': {'role': 'assistant', 'content': '', 'tool_calls': [
            {'function': {'name': 'browse', 'arguments': {'value': 'example.com', 'expected': 'Page open'}}}]},
            'prompt_eval_count': tokens, 'eval_count': 20, 'prompt_eval_duration': 1e9, 'eval_duration': 1e8}
        return response
    return Mock(post=post)


def two_steps(options, first_tokens):
    calls = []
    c = client(calls, first_tokens)
    first = plan(c, 'qwen3.5:9b', 'Rules.', {'goal': 'read the table', 'tools': ROWS, 'screen': {'controls': ['A']}},
                 dict(options))
    second = plan(c, 'qwen3.5:9b', 'Rules.', {
        'goal': 'read the table', 'tools': ROWS, 'conversation': first['conversation'], 'step_number': 2,
        'last_result': {'action': 'browse', 'verified': True, 'result': 'Opened'},
        'screen': {'title': 'Tables', 'controls': ['B'], 'tool_results': [{'action': 'browse', 'result': 'x' * 5000}]}},
        dict(options))
    return first, second, calls


def test_a_step_that_fits_only_without_the_fixed_reserve_continues_with_the_flag():
    # 6,400 measured tokens + update + 1,600 reserve > 7,680, but + the real 500-token reply fits.
    _, off, _ = two_steps({}, 5600)
    _, on, calls = two_steps({'cache_order': True}, 5600)
    assert off['inference']['continued'] is False
    assert on['inference']['continued'] is True
    before, after = calls[0]['messages'], calls[1]['messages']
    assert after[:len(before)] == before  # Same prefix: only the new turn is read.


def test_continued_tool_results_are_capped_shorter_with_the_flag():
    data = {'step_number': 2, 'screen': {'tool_results': [{'action': 'web_read', 'result': 'y' * 9000}]},
            'last_result': {'verified': True}}
    assert len(step_update(data, 'web_read')['tool_result']) == 4000
    assert len(step_update(data, 'web_read', 2000)['tool_result']) == 2000


def test_fresh_prompts_leave_room_for_continuations_but_keep_the_goal():
    big = {'goal': 'GOAL-TEXT read the table', 'tools': ROWS, 'screen': {'controls': ['A']},
           'reasoning_lessons': ['lesson ' * 1000] * 3, 'experience': ['exp ' * 2000] * 3}
    sizes = {}
    for name, options in (('off', {}), ('on', {'cache_order': True})):
        calls = []
        plan(client(calls, 3000), 'qwen3.5:9b', 'Rules.', dict(big), options)
        user = json.loads(calls[0]['messages'][-1]['content'])
        sizes[name] = (len(calls[0]['messages'][-1]['content']), set(user))
        assert user['goal'] == 'GOAL-TEXT read the table'
    assert sizes['on'][0] < sizes['off'][0]
    assert 'reasoning_lessons' not in sizes['off'][1] and 'experience' in sizes['off'][1]
    assert 'reasoning_lessons' not in sizes['on'][1] and 'experience' not in sizes['on'][1]


def test_without_the_flag_the_payload_is_unchanged():
    calls_a, calls_b = [], []
    data = {'goal': 'g', 'tools': ROWS, 'screen': {'controls': ['A']}}
    plan(client(calls_a, 1000), 'qwen3.5:9b', 'Rules.', dict(data), {})
    plan(client(calls_b, 1000), 'qwen3.5:9b', 'Rules.', dict(data), {'cache_order': False})
    assert calls_a == calls_b
    assert 'cache_order' not in calls_a[0]['messages'][-1]['content']


def test_the_brain_passes_the_flag_only_when_it_is_on():
    from jarvis.brain import Brain
    for config, expected in (({}, False), ({'speed': {'cache_order': True}}, True),
                             ({'speed': {'cache_order': 'yes'}}, False)):
        brain = Brain.__new__(Brain)
        brain.actions = Mock(config=config, acquisition=None)
        brain.options = {}
        brain.step_session = None
        seen = {}
        brain.propose_plan = lambda operation, cancelled, **data: seen.update(data) or {}
        brain.planning_request('next_step', lambda: False, goal='g', completed=[])
        assert ('cache_order' in seen) is expected
