"""End-to-end through Jarvis's real ToolRegistry -> mcp_bridge -> stdio subprocess -> notes connector.

Uses Jarvis's actual .jarvis/mcp.json schema in a temporary base folder and a mocked
approval callback (approval UI is out of scope); everything after approval is real.
"""
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from conftest import ROOT
from jarvis.task_state import TaskState
from jarvis.tools import ToolRegistry

NOTES = ROOT / 'connectors' / 'notes' / 'server.py'


@pytest.fixture
def jarvis(tmp_path):
    notes = tmp_path / 'approved_notes'
    notes.mkdir()
    (notes / 'blender.md').write_text('# Blender\nMaterial creation uses the Principled BSDF node.\n', encoding='utf-8')
    (tmp_path / 'private.md').write_text('outside the approved folder', encoding='utf-8')
    config = {'enabled': True, 'trusted': True, 'command': sys.executable,
              'args': [str(NOTES), '--runtime', 'builtin', '--root', str(notes)],
              'allow_tools': ['list_notes', 'read_note', 'search_notes'], 'timeout_seconds': 20}
    (tmp_path / '.jarvis').mkdir()
    (tmp_path / '.jarvis' / 'mcp.json').write_text(json.dumps({'servers': {'notes': config}}), encoding='utf-8')
    state = TaskState(tmp_path)
    state.start('Connector end-to-end check', 'task')
    actions = SimpleNamespace(base=tmp_path, task_state=state, report=Mock(), config={},
                              allowed_tools=None, _approve=Mock(), skills=None)
    return actions


def call(actions, tool, **arguments):
    step = dict(action='mcp_call', value='notes', content=json.dumps({'name': tool, 'arguments': arguments}))
    return ToolRegistry(actions).execute(step, lambda: False)


def test_search_through_jarvis_returns_verified_structured_result(jarvis):
    result = call(jarvis, 'search_notes', query='Blender material', max_results=10)
    payload = json.loads(result.evidence)
    assert payload['isError'] is False
    assert payload['structuredContent']['result'][0]['filename'] == 'blender.md'
    assert jarvis._approve.call_count == 1
    approved = json.loads(jarvis._approve.call_args.args[1])
    assert approved['server'] == 'notes' and approved['call']['name'] == 'search_notes'


def test_list_tools_through_jarvis(jarvis):
    step = dict(action='mcp_list_tools', value='notes', content='{}')
    rows = json.loads(ToolRegistry(jarvis).execute(step, lambda: False).evidence)
    assert {row['name'] for row in rows} == {'list_notes', 'read_note', 'search_notes'}


def test_escape_attempt_is_a_failed_call_not_data(jarvis):
    with pytest.raises(ValueError):
        call(jarvis, 'read_note', filename='..\\private.md')


def test_schema_invalid_call_is_refused_by_jarvis_before_the_connector(jarvis):
    with pytest.raises(ValueError):
        call(jarvis, 'list_notes', limit=500)
    with pytest.raises(ValueError):
        call(jarvis, 'search_notes', query='x', unexpected=True)


def test_tool_outside_allowlist_is_refused(jarvis):
    config_path = jarvis.base / '.jarvis' / 'mcp.json'
    data = json.loads(config_path.read_text(encoding='utf-8'))
    data['servers']['notes']['allow_tools'] = ['list_notes']
    config_path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        call(jarvis, 'read_note', filename='blender.md')
    assert jarvis._approve.call_count == 0
