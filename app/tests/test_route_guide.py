"""Route guide: APIs/code/MCP first, screen control where needed or asked, results shown to the user."""
from jarvis.route_guide import guide
from jarvis.tools import SPECS
from jarvis.toolkits import TOOLS

OFFERED = {s.name for s in SPECS} | set(TOOLS)


def rule(goal):
    return next(r for r in guide(goal, OFFERED) if r['target'] == 'policy')['rule']


def first(goal, target):
    return next(r for r in guide(goal, OFFERED) if r['target'] == target)['order'][0]['tool']


def test_api_first_for_apps_with_apis_and_the_result_is_shown():
    assert first('put the totals in populations.xlsx', 'spreadsheet') == 'office_xlsx'
    assert first('Open Blender, add a cylinder and save cylinder.blend', 'blender') == 'blender_task'
    assert first('write a report note from your brain', 'notes') == 'knowledge_search'
    assert 'Prefer the first usable API' in rule('Open Blender, add a cylinder and save cylinder.blend')
    assert 'open it in its app' in guide('put totals in a.xlsx', OFFERED)[-1]['screen_aware']


def test_hands_on_requests_use_the_app_itself():
    assert 'explicitly asked to use the app' in rule('Open Notepad and type a shopping list')
    assert 'explicitly asked to use the app' in rule('Use the Calculator app to work out 12 times 4')
    assert 'explicitly asked to use the app' in rule('draw a house in Paint')


def test_only_offered_tools_are_suggested():
    rows = guide('Open Blender and add a cylinder', {'screen_act'})
    assert rows[0]['order'] == [{'tool': 'screen_act', 'tier': 'gui', 'how': rows[0]['order'][0]['how']}]
    assert guide('hello there', OFFERED) == []
