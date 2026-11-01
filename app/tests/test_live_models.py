"""Live high-detail models and checked web apps (control.api_routes): plans, looks, checks and the repair loop."""
import json
import random

from jarvis.blender_live import live_request, look_of
from jarvis.learning.verifiers.blender_scene import house_problems
from jarvis.reference_research import ARTICLES, STYLES, default_plan, house_plan, search, validated
from jarvis.web_app import build, describe, matches

TEST = 'in my Jarvis test folder'


def box(lo, hi, **extra):
    return {'min': list(lo), 'max': list(hi), 'modifiers': ['BEVEL', 'BOOLEAN'], 'evaluated': 200, 'nodes': ['TEX_BRICK'],
            'transmission': 0.0, **extra}


def house(**changes):
    rows = {
        'House.Wall.F0.front': box((-5, -4, .3), (5, -3.75, 3.2)), 'House.Wall.F0.back': box((-5, 3.75, .3), (5, 4, 3.2)),
        'House.Wall.F0.left': box((-5, -3.75, .3), (-4.75, 3.75, 3.2)),
        'House.Wall.F0.right': box((4.75, -3.75, .3), (5, 3.75, 3.2)),
        'House.Door': box((-.5, -3.95, .3), (.5, -3.9, 2.4)), 'House.Roof': box((-5.4, -4.4, 3.2), (5.4, 4.4, 6)),
        'House.Floor.0': box((-4.75, -3.75, .3), (4.75, 3.75, .34)),
        'Furniture.F0.living.sofa.0': box((-4, 2, .34), (-2, 3, 1.1)), 'Furniture.F0.living.rug.1': box((-1, -1, .34), (1, 1, .35)),
    }
    for n, (x, y) in enumerate([(-3, -3.8), (3, -3.8), (-3, 3.8), (3, 3.8)], 1):
        rows[f'House.Window.{n}'] = box((x - .5, y - .01, 1.2), (x + .5, y + .01, 2.4), transmission=1.0)
    rows.update(changes)
    return rows


def test_a_planned_house_passes_and_each_defect_is_caught():
    assert house_problems(house()) == []
    solid = house(**{'House.Wall.F0.front': {**house()['House.Wall.F0.front'], 'modifiers': ['BEVEL']}})
    assert any('openings' in p for p in house_problems(solid))
    floating = house(**{'Furniture.F0.living.sofa.0': box((-4, 2, 1.0), (-2, 3, 1.8))})
    assert any('floor' in p for p in house_problems(floating))
    plain = house(**{name: {**row, 'nodes': ['BSDF_PRINCIPLED']} for name, row in house().items() if 'Wall' in name})
    assert any('texture' in p for p in house_problems(plain))
    roofless = house()
    del roofless['House.Roof']
    assert any('roof' in p for p in house_problems(roofless))


def test_requests_choose_houses_humans_and_looks():
    assert live_request(f'Open Blender and design a detailed house with a chimney, and save it as h.blend {TEST}.')['operation'] == 'house'
    face = live_request(f'Open Blender and build a realistic high poly human face, and save it as f.blend {TEST}.')
    assert face['operation'] == 'human_head'
    look = look_of('a realistic face with long blonde hair, green eyes and olive skin, no beard', 'human_head')
    assert look == {'skin': 'olive', 'hair': 'blonde', 'hair_length': 'long', 'eyes': 'green', 'beard': 'none'}
    assert look_of('a realistic female body', 'human_body_female', random.Random(1))['beard'] == 'none'
    looks = {json.dumps(look_of('a realistic male body', 'human_body_male', random.Random(seed)), sort_keys=True)
             for seed in range(6)}
    assert len(looks) > 3  # Different every run.


def test_plans_are_clamped_and_vary_by_style():
    fallback = default_plan('tudor', random.Random(0))
    wild = {'floors': 9, 'width': 300, 'roof': {'type': 'dome', 'pitch_deg': 89, 'colour': 'red'},
            'walls': {'material': 'glass'}, 'rooms': [{'floor': 0, 'name': 'x', 'furniture': ['spaceship']}]}
    plan = validated(wild, fallback)
    assert plan['floors'] == 3 and plan['width'] == 16 and plan['roof']['type'] == 'gable'
    assert plan['roof']['colour'] == fallback['roof']['colour'] and plan['walls']['material'] == 'plaster'
    # Unknown furniture falls back to the style's rooms, and the third storey the plan now has gets rooms too.
    assert plan['rooms'][:len(fallback['rooms'])] == fallback['rooms']
    assert {r['floor'] for r in plan['rooms']} == {0, 1, 2}
    fewer = validated({'floors': 1, 'rooms': fallback['rooms']}, fallback)
    assert {r['floor'] for r in fewer['rooms']} == {0}  # Rooms on storeys the plan dropped are not squeezed downstairs.
    styles = {house_plan('design a house', None, lambda: False, False, random.Random(seed))['style'] for seed in range(12)}
    assert len(styles) >= 4 and styles <= set(STYLES)
    assert house_plan('design a victorian house', None, lambda: False, False)['style'] == 'victorian'


def test_wikipedia_references_are_plain_sentences_and_only_titles_leave():
    seen = []

    def fetch(url):
        seen.append(url)
        return json.dumps({'query': {'pages': {'1': {'extract': 'Tudor Revival is a style of houses. It has steep gables '
                                                                 'and dark timber framing. Short.'}}}})
    sentences = search(ARTICLES['tudor'], fetch)
    assert sentences == ['Tudor Revival is a style of houses.', 'It has steep gables and dark timber framing.']
    assert 'titles=Tudor+Revival+architecture' in seen[0] and 'en.wikipedia.org' in seen[0]


def test_web_requests_are_recognised_and_trimmed():
    goal = f'Open VS Code and make a todo list web app where new items animate in with anime.js in a new folder called todo-app {TEST}.'
    assert matches(goal) == ('anime', 'todo-app')
    assert describe(goal) == 'make a todo list web app where new items animate in with anime.js.'
    assert matches(f'Open VS Code and build a flask web app in a new folder called x {TEST}') is None


def test_the_repair_loop_fixes_what_the_browser_found():
    calls = []

    def request(operation, cancelled, **data):
        calls.append(data)
        return {'text': 'broken' if len(calls) == 1 else 'fixed'}

    def checker(html, library):
        return ['error: x is not defined'] if html == 'broken\n' else []
    html, problems = build(request, 'make a counter web app', 'gsap', lambda: False, lambda *a: None, checker)
    assert html == 'fixed\n' and problems == ['error: x is not defined']
    assert calls[1]['tool'] == 'improve_code' and 'x is not defined' in calls[1]['goal'] and calls[1]['context'] == 'broken\n'
    assert all(call.get('long_output') is True for call in calls)
    never = build(lambda *a, **k: {'text': 'broken'}, 'make a counter web app', 'gsap', lambda: False,
                  lambda *a: None, checker)
    assert never[0] is None  # Still broken after every repair round: nothing is written.
