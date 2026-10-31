"""App-API routes (control.api_routes): a verified document opens in the app the user named, by its exact path."""
import json
import tempfile
from unittest.mock import Mock

import pytest

from jarvis.app_routes import show_document
from jarvis.tools import ToolRegistry

H2 = ('Open Blender, add a cylinder with radius 1 metre and depth 2 metres at the centre, name it JarvisCylinder, '
      'and save the file as cylinder.blend in my Jarvis test folder.')
STEP = {'action': 'blender_task', 'value': 'cylinder.blend', 'folder': 'jarvis test folder'}


def verified(name='cylinder.blend', state='verified'):
    return json.dumps({'method': 'blender.background', 'verification': state, 'file': name})


def setup(tmp_path, name='cylinder.blend'):
    (tmp_path / name).write_bytes(b'BLENDER')
    actions = Mock()
    actions._task_folder.return_value = str(tmp_path)
    return actions


def test_verified_blend_opens_in_blender_when_the_user_named_it(tmp_path):
    actions, opened = setup(tmp_path), []
    evidence = show_document(actions, STEP, verified(), H2, lambda: False, opened.append)
    assert opened == [str((tmp_path / 'cylinder.blend').resolve())]
    assert 'in Blender' in evidence and 'do not open it again' in evidence


@pytest.mark.parametrize('goal', ['add a cylinder and save cylinder.blend in my Jarvis test folder',
                                  'make a 3d model file'])
def test_no_app_named_means_nothing_opens(tmp_path, goal):
    actions, opened = setup(tmp_path), []
    assert show_document(actions, STEP, verified(), goal, lambda: False, opened.append) == verified()
    assert opened == []


@pytest.mark.parametrize('evidence', [verified(state='failed'), 'not json', json.dumps(['x']),
                                      verified(name='other.blend'), verified(name='..\\..\\escape.blend'),
                                      verified(name='cylinder.txt')])
def test_only_the_verified_file_in_the_task_folder_opens(tmp_path, evidence):
    actions, opened = setup(tmp_path), []
    (tmp_path / 'cylinder.txt').write_text('x')
    assert show_document(actions, STEP, evidence, H2, lambda: False, opened.append) == evidence
    assert opened == []


def test_other_tools_cancel_and_open_errors(tmp_path):
    actions, opened = setup(tmp_path), []
    assert show_document(actions, {**STEP, 'action': 'create_file'}, verified(), H2, lambda: False, opened.append) == verified()
    assert show_document(actions, STEP, verified(), H2, lambda: True, opened.append) == verified()
    assert opened == []

    def broken(path):
        raise OSError('no association')
    assert 'did not open it' in show_document(actions, STEP, verified(), H2, lambda: False, broken)


def test_excel_and_word(tmp_path):
    actions, opened = setup(tmp_path, 'populations.xlsx'), []
    step = {'action': 'office_xlsx', 'value': 'populations.xlsx', 'folder': 'x'}
    assert 'in Excel' in show_document(actions, step, verified('populations.xlsx'), 'put them in a new Excel workbook',
                                       lambda: False, opened.append)
    assert show_document(actions, step, verified('populations.xlsx'), 'make populations.xlsx', lambda: False,
                         opened.append) == verified('populations.xlsx')
    assert len(opened) == 1


def test_registry_opens_only_with_the_flag(tmp_path, monkeypatch):
    from jarvis.task_state import TaskState
    import jarvis.app_routes as routes
    opened = []
    monkeypatch.setattr(routes.os, 'startfile', opened.append, raising=False)
    monkeypatch.setattr('jarvis.toolkits.execute', lambda actions, step, cancelled: verified())
    (tmp_path / 'cylinder.blend').write_bytes(b'B')
    for config, expected in (({}, 0), ({'control': {'api_routes': True}}, 1)):
        with tempfile.TemporaryDirectory() as directory:
            actions = Mock()
            actions.config = config
            actions._task_folder.return_value = str(tmp_path)
            actions.task_state = TaskState(directory)
            actions.task_state.start(H2, 'task')
            ToolRegistry(actions).execute({**STEP, 'content': ''}, lambda: False)
        assert len(opened) == expected
