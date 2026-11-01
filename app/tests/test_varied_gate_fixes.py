"""Defects the varied live gate found (2026-10-31): each request kind must work beyond the one fixed wording."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from jarvis.coder import coding_folder, nested_folder, workspace_coding_request
from jarvis.conversation_intent import quick_kind


@pytest.mark.parametrize('text', [
    'On www.scrapethissite.com/pages/simple, what capital and population does the page list for Andorra?',
    'On quotes.toscrape.com, how many of the quotes on the first page are by Albert Einstein?',
    'what does https://example.org say?',
])
def test_a_question_about_a_named_website_is_a_task(text):
    assert quick_kind(text) == 'task'


@pytest.mark.parametrize('text', ['how are you?', 'what is 2.5 times 4?', 'tell me a joke?'])
def test_ordinary_questions_stay_conversation(text):
    assert quick_kind(text) == 'chat'


def test_using_an_app_is_not_building_one():
    assert not workspace_coding_request('Use the Calculator app: add 2025 and 375, then multiply the result by 12.')
    assert not workspace_coding_request('change the wallpaper')
    assert workspace_coding_request('create a todo app in python')
    assert workspace_coding_request('Open VS Code and change main.py so multiples of 7 also print Bazz')


def test_a_child_folder_inside_a_known_folder_is_found(tmp_path):
    (tmp_path / 'fizzbuzz-app').mkdir()
    actions = Mock()
    actions._task_folder.side_effect = lambda name, cancelled: (str(tmp_path) if name == 'Jarvis test folder'
                                                                else (_ for _ in ()).throw(ValueError(name)))
    goal = 'Open VS Code and add a function is_prime(n) to main.py in the fizzbuzz-app folder in my Jarvis test folder.'
    assert coding_folder(actions, goal, lambda: False) == str(tmp_path / 'fizzbuzz-app')
    assert nested_folder(actions, goal.replace('fizzbuzz-app', 'missing-app'), 'missing-app', lambda: False) is None


def test_a_blend_export_that_repeats_the_save_is_ignored(tmp_path, monkeypatch):
    import json
    from jarvis import app_adapters
    monkeypatch.setattr(app_adapters, '_root', lambda actions, step, cancelled: tmp_path)
    seen = {}
    monkeypatch.setattr(app_adapters, '_approve', lambda actions, kind, data, cancelled: seen.update(data) or
                        (_ for _ in ()).throw(ValueError('stop after approval')))
    step = {'action': 'blender_task', 'value': 'cone.blend', 'folder': 'tests', 'content': json.dumps(
        {'operation': 'create', 'objects': [{'type': 'cone', 'name': 'JarvisCone', 'location': [0, 0, 0]}],
         'export': {'format': 'blend', 'path': 'cone.blend'}})}
    with pytest.raises(ValueError, match='stop after approval'):
        app_adapters.blender_task(Mock(), step, lambda: False)
    assert seen['export'] is None
    step['content'] = step['content'].replace('"path": "cone.blend"', '"path": "other.blend"')
    with pytest.raises(ValueError, match='Export format'):
        app_adapters.blender_task(Mock(), step, lambda: False)


def test_calculator_guidance_forbids_a_second_equals():
    from jarvis.route_guide import guide
    rows = guide('Use the Calculator app to work out 987 times 65 plus 432', {'app_open', 'app_act', 'think'})
    text = ' '.join(step['how'] if 'how' in step else str(step) for row in rows for step in row.get('order', []))
    assert 'never press = or Enter again' in text


def test_a_shortened_read_says_so_only_with_cache_order():
    from jarvis.native_tools import step_update
    data = {'step_number': 2, 'screen': {'tool_results': [{'action': 'web_read', 'result': 'z' * 5000}]},
            'last_result': {'verified': True}}
    assert step_update(data, 'web_read')['tool_result'] == 'z' * 4000  # Flag off: unchanged.
    cut = step_update(data, 'web_read', 2000, True)['tool_result']
    assert cut.startswith('z' * 2000) and 'find' in cut
    short = {**data, 'screen': {'tool_results': [{'action': 'web_read', 'result': 'short'}]}}
    assert step_update(short, 'web_read', 2000, True)['tool_result'] == 'short'


def test_a_shared_recipe_save_records_what_the_brain_verifies(tmp_path):
    from jarvis.control.save_dialog import save_file_step
    from jarvis.visual_fallback import VisualFallback
    actions = Mock()
    actions._task_folder.return_value = str(tmp_path)
    actions.control.return_value.app_scope = 'win-5'

    def app_act(op, args, cancelled):
        Path(args['text']).write_bytes(b'Reading List\r\n- Dune')
        return '{"ok": true}'
    actions.control.return_value.app_act.side_effect = app_act
    actions.brain.visual_fallback.file_state = VisualFallback.file_state
    save_file_step(actions, {'action': 'save_file', 'value': 'reading.txt', 'folder': 'x'}, lambda: False)
    saved = actions.brain.visual_fallback.last_saved
    assert saved['path'] == tmp_path.resolve() / 'reading.txt'
    assert {k: saved[k] for k in ('size', 'mtime_ns', 'sha256')} == VisualFallback.file_state(saved['path'])


def test_blender_guidance_explains_radius_and_depth():
    from jarvis.route_guide import guide
    rows = guide('Open Blender, add a cone with radius 1 metre and depth 3 metres', {'blender_task', 'open', 'screen_act'})
    assert '"depth": d' in str(rows)


def test_a_new_folder_inside_a_named_folder_is_created_there(tmp_path):
    actions = Mock()
    actions._task_folder.side_effect = lambda name, cancelled: (str(tmp_path) if name == 'Jarvis test folder'
                                                                else (_ for _ in ()).throw(ValueError(name)))
    goal = ('Open VS Code and create a pomodoro timer web app with smooth GSAP animations in a new folder called '
            'pomodoro-app in my Jarvis test folder, and save it.')
    assert coding_folder(actions, goal, lambda: False) == str(tmp_path / 'pomodoro-app')
    assert (tmp_path / 'pomodoro-app').is_dir()
