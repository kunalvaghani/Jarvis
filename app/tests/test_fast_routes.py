"""Fixed routes for clear requests (control.api_routes): parsers are exact or step aside before any action."""
from fractions import Fraction
import json
from unittest.mock import Mock

import pytest

from jarvis.fast_routes import blender_step, calculation, grounded, run, site_question

FOLDER = 'in my Jarvis test folder'


def objects(goal):
    step = blender_step(goal)
    return step and json.loads(step['content'])['objects'][0]


def test_blender_primitives_are_parsed_exactly():
    item = objects('Open Blender, add a cone with radius 1 metre and depth 3 metres at the centre, name it JarvisCone, '
                   f'and save the file as cone.blend {FOLDER}.')
    assert item == {'type': 'cone', 'name': 'JarvisCone', 'location': [0, 0, 0], 'scale': {'radius': 1.0, 'depth': 3.0}}
    assert objects(f'Open Blender, add a cube 4 metres on each side, name it Box, save it as box.blend {FOLDER}')['scale'] == [2, 2, 2]
    assert objects(f'Open Blender, add a sphere with radius 1.5 at the centre, name it Ball, save as ball.blend {FOLDER}')[
        'scale'] == {'radius': 1.5}
    step = blender_step(f'In Blender add a cylinder named it, name it Pipe, at (1, 2, 3), save as pipe.blend {FOLDER}')
    assert json.loads(step['content'])['objects'][0]['location'] == [1, 2, 3] and step['folder'] == 'Jarvis test folder'


@pytest.mark.parametrize('goal', [
    'Open Blender and add a cube',  # No name, file or folder.
    f'Open Blender, add a cube and a sphere, name it X, save as x.blend {FOLDER}',  # Two shapes.
    f'Open Blender, add a cube 20 cm on each side, name it X, save as x.blend {FOLDER}',  # Other units.
    f'Open Blender, add a torus with radius 2, name it X, save as x.blend {FOLDER}',  # Torus sizes: planner.
    f'add a cube, name it X, save as x.blend {FOLDER}',  # Blender not named.
])
def test_unclear_blender_requests_go_to_the_planner(goal):
    assert blender_step(goal) is None


@pytest.mark.parametrize('goal,keys,value', [
    ('Use the Calculator app to work out 1234 times 56 minus 789 and tell me the answer.', '1234*56=-789=', 68315),
    ('Use the Calculator app: add 2025 and 375, then multiply the result by 12, and tell me the answer.',
     '2025+375=*12=', 28800),
    ('Use the Calculator app to work out 7056 divided by 84 plus 1000 and tell me the answer.', '7056/84=+1000=', 1084),
    ('In Calculator, what is 10 divided by 4?', '10/4=', Fraction(5, 2)),
    ('Use the Calculator app: subtract 5 from 20, then divide the result by 3.', '20-5=/3=', 5),
])
def test_calculator_requests_become_exact_key_sequences(goal, keys, value):
    assert calculation(goal) == (keys, value)


@pytest.mark.parametrize('goal', [
    'Use the Calculator app to work out the square root of 2',
    'Open Calculator',
    'Use the Calculator app to work out 5 divided by 0',
    'work out 3 times 4',  # Calculator not named: the planner may compute directly.
])
def test_unclear_calculations_go_to_the_planner(goal):
    assert calculation(goal) is None


def test_website_questions_name_exactly_one_page_and_never_act():
    assert site_question('On books.toscrape.com, what is the price of "Tipping the Velvet"?')[0] == 'books.toscrape.com'
    assert site_question('On www.scrapethissite.com/pages/simple, what is the capital of Andorra?')[0] == \
        'www.scrapethissite.com/pages/simple'
    assert site_question('Log in to example.com and what is my balance?') is None
    assert site_question('Compare a.com and b.com, which is cheaper?') is None
    assert site_question('open example.com') is None


def test_answers_must_be_grounded_in_the_page():
    page = 'Tipping the Velvet £53.74 In stock'
    assert grounded('It costs £53.74.', page)
    assert not grounded('It costs £51.77.', page)
    assert grounded('There are 3 quotes by Albert Einstein.', 'quotes ... by Albert Einstein')  # A small count.


def fake_actions(config, display='68,315'):
    actions = Mock(config=config)
    control = actions.control.return_value
    control.app_read.return_value = f'Window "Calculator" [u1]\n  Text "Display is {display}" [u3]'
    return actions


def test_the_calculator_route_types_once_and_checks_the_display():
    actions = fake_actions({'control': {'api_routes': True}})
    goal = 'Use the Calculator app to work out 1234 times 56 minus 789 and tell me the answer.'
    assert run(actions, goal, lambda: False) == 'Finished: Calculator shows 68,315 (1234*56=-789).'
    actions.control.return_value.app_act.assert_called_once_with('type', {'text': '1234*56=-789='}, actions.control
                                                                 .return_value.app_act.call_args.args[2])
    wrong = fake_actions({'control': {'api_routes': True}}, display='67,526')
    assert 'not the expected 68315' in run(wrong, goal, lambda: False)
    assert wrong.control.return_value.app_act.call_count == 1  # Never typed again.


def test_routes_run_only_with_the_flag():
    actions = fake_actions({})
    assert run(actions, 'Use the Calculator app to work out 2 plus 2 and tell me the answer.', lambda: False) is None
    actions.control.assert_not_called()


def test_the_website_route_answers_only_from_the_page():
    actions = Mock(config={'control': {'api_routes': True}})
    control = actions.control.return_value
    control.web_open.return_value = '{"ok": true}\nRootWebArea'
    control.last_web = 'All products\n' + 'link "Tipping the Velvet"\ntext "£53.74"\n' * 3
    actions.brain.client.request.return_value = {'text': 'Tipping the Velvet costs £53.74.'}
    goal = 'On books.toscrape.com, what is the price of the book "Tipping the Velvet"?'
    assert run(actions, goal, lambda: False) == 'Finished: Tipping the Velvet costs £53.74.'
    actions.brain.client.request.return_value = {'text': 'It costs £99.00.'}  # Not on the page.
    assert run(actions, goal, lambda: False) is None
    actions.brain.client.request.return_value = {'text': 'NOT ON PAGE'}
    assert run(actions, goal, lambda: False) is None


def test_blender_arguments_written_into_the_value_field_are_split():
    from jarvis import app_adapters
    match = app_adapters.INLINE_CONTENT.match('cube.blend, content={"operation":"create","objects":[]}')
    assert match.group(1) == 'cube.blend' and json.loads(match.group(2)) == {'operation': 'create', 'objects': []}


def test_a_dependent_then_clause_stays_one_command():
    from jarvis.engine import split_commands
    goal = 'Use the Calculator app: add 2025 and 375, then multiply the result by 12, and tell me the answer.'
    assert split_commands(goal) == [goal]
    assert split_commands('open notepad then type hello') == ['open notepad', 'type hello']


def test_a_question_is_never_done_before_it_is_answered():
    from jarvis.brain import ASKS_ANSWER
    assert ASKS_ANSWER.search('On books.toscrape.com, what is the price of "Tipping the Velvet"?')
    assert ASKS_ANSWER.search('Use the Calculator app to work out 2 plus 2 and tell me the answer.')
    assert not ASKS_ANSWER.search('Open Blender, add a cube')
