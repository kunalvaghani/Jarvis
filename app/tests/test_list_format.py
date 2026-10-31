"""The user's titled-list rule for text the planner types itself (live S3)."""
import tempfile
from unittest.mock import Mock

import pytest

from jarvis.learning.verifiers.text_file import titled_list_problems
from jarvis.list_format import titled, topic_title

S3 = ('Open Notepad, type a shopping list with milk, eggs and bread on separate lines, and save it as shopping.txt '
      'in my Jarvis test folder.')


def test_s3_bare_lines_become_the_titled_list_the_oracle_expects():
    text = titled('milk\neggs\nbread', S3)
    assert text == 'Shopping List\n- milk\n- eggs\n- bread'
    assert titled_list_problems(text.splitlines(), ('shopping', 'list'), ('milk', 'eggs', 'bread')) == []


@pytest.mark.parametrize('goal,title', [
    ('make a to-do list: call mom, pay rent', 'To-Do List'), ('write my todo list', 'To-Do List'),
    ('type a packing list for the beach', 'Packing List'), ('a checklist for launch day', 'Checklist'),
    ('write a list of chores', 'Chores List'), ('type a grocery list', 'Grocery List'),
])
def test_titles_name_the_topic(goal, title):
    assert topic_title(goal) == title


@pytest.mark.parametrize('goal', ['type hello world into notepad', 'list the files in Downloads', 'write a short note',
                                  'open the list view'])
def test_goals_without_a_list_leave_text_unchanged(goal):
    assert titled('milk\neggs\nbread', goal) == 'milk\neggs\nbread'


@pytest.mark.parametrize('text', [
    'Shopping List\n- milk\n- eggs',          # already the rule
    '1. milk\n2. eggs',                        # already pointed
    'milk',                                    # one line
    'Dear Sam,\n' + 'x' * 120,                 # prose, not items
])
def test_text_that_is_not_bare_items_is_unchanged(text):
    assert titled(text, S3) == text


def test_an_existing_title_keeps_its_words_and_items_get_points():
    assert titled('Shopping List\nmilk\neggs', S3) == 'Shopping List\n- milk\n- eggs'
    assert titled('\nmilk\n\neggs\n', S3) == 'Shopping List\n- milk\n- eggs'


def test_app_act_type_applies_the_rule_from_the_running_task():
    from jarvis.task_state import TaskState
    from jarvis.tools import control_tool
    with tempfile.TemporaryDirectory() as directory:
        actions = Mock()
        actions.task_state = TaskState(directory)
        actions.task_state.start(S3, 'task')
        service = actions.control.return_value
        service.app_act.return_value = '{"ok": true}'
        control_tool(actions, {'action': 'app_act', 'value': 'type', 'content': '{"ref": "u5", "text": "milk\\neggs\\nbread"}'},
                     lambda: False)
        assert service.app_act.call_args.args[1]['text'] == 'Shopping List\n- milk\n- eggs\n- bread'
        control_tool(actions, {'action': 'app_act', 'value': 'key', 'content': '{"text": "ctrl+s"}'}, lambda: False)
        assert service.app_act.call_args.args[1]['text'] == 'ctrl+s'
    idle = Mock()
    idle.task_state = None
    idle.control.return_value.app_act.return_value = '{"ok": true}'
    control_tool(idle, {'action': 'app_act', 'value': 'type', 'content': '{"text": "milk\\neggs"}'}, lambda: False)
    assert idle.control.return_value.app_act.call_args.args[1]['text'] == 'milk\neggs'
