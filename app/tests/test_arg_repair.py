"""control.arg_repair: only the planner's "arguments in the operation slot" shape becomes a type step."""
import json
from unittest.mock import Mock

import pytest

from jarvis.control.arg_repair import repaired
from jarvis.tools import control_tool


@pytest.mark.parametrize('value', ['{"content": {"text": "1234*56-789="}}', '{"text": "1234*56-789="}'])
def test_text_in_the_operation_slot_becomes_type(value):
    step = repaired({'action': 'app_act', 'value': value})
    assert step['value'] == 'type' and json.loads(step['content']) == {'text': '1234*56-789='}


@pytest.mark.parametrize('step', [
    {'action': 'app_act', 'value': 'type', 'content': '{"text": "x"}'},  # Already right.
    {'action': 'app_act', 'value': '{"text": "x", "ref": "u3"}'},  # A target: not ours to guess.
    {'action': 'app_act', 'value': '{"content": {"text": "x"}}', 'content': '{"ref": "u3"}'},  # Content given.
    {'action': 'app_act', 'value': '{"key": "enter"}'},
    {'action': 'app_act', 'value': '{"text": ""}'},
    {'action': 'app_act', 'value': '{not json'},
])
def test_everything_else_is_unchanged(step):
    assert repaired(step) == step


def test_the_hook_runs_only_with_the_flag():
    step = {'action': 'app_act', 'value': '{"content": {"text": "1234*56-789="}}', 'content': ''}
    for config, expected in (({}, None), ({'control': {'arg_repair': True}}, 'type')):
        actions = Mock(config=config)
        seen = []
        actions.control.return_value.app_act.side_effect = lambda op, args, cancelled: seen.append((op, args)) or '{}'
        control_tool(actions, dict(step), lambda: False)
        if expected is None:
            assert not seen or seen[0][0] != 'type'
        else:
            assert seen == [('type', {'text': '1234*56-789='})]
