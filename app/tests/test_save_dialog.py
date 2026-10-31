"""Shared Save-dialog recipe (control.shared_save): save_file uses app_act save_as for a new file in a known
window; the visual path is chosen only before any key is sent; after the shortcut there is no fallback."""
import json
import tempfile
from unittest.mock import Mock

import pytest

from jarvis.control.save_dialog import save_file_step
from jarvis.control.types import ControlError, ErrorCategory
from jarvis.tools import ToolRegistry


def fake_actions(folder, scope='win-4242', save=None):
    actions = Mock()
    actions._task_folder.return_value = str(folder)
    control = actions.control.return_value
    control.app_scope = scope

    def app_act(op, args, cancelled):
        assert op == 'save_as'
        return (save or saved)(args)
    control.app_act.side_effect = app_act
    return actions


def saved(args):
    from pathlib import Path
    Path(args['text']).write_text('hello', encoding='utf-8')
    return json.dumps({'ok': True, 'verified': True, 'executed': True, 'result': 'Saved'}) + '\nWindow "Notepad" [u1]'


STEP = {'action': 'save_file', 'value': 'notes.txt', 'folder': 'tests'}


def test_new_file_saves_through_the_shared_recipe(tmp_path):
    actions = fake_actions(tmp_path)
    evidence = save_file_step(actions, STEP, lambda: False)
    assert 'verified on disk' in evidence and (tmp_path / 'notes.txt').read_text() == 'hello'
    args = actions.control.return_value.app_act.call_args.args[1]
    assert args == {'text': str(tmp_path.resolve() / 'notes.txt'), 'window': '4242'}


def test_existing_file_or_unknown_window_uses_the_visual_path_before_any_input(tmp_path):
    (tmp_path / 'notes.txt').write_text('keep', encoding='utf-8')
    actions = fake_actions(tmp_path)
    assert save_file_step(actions, STEP, lambda: False) is None  # Overwrite needs the approval path.
    for scope in ('', 'tab-1', 'win-abc', None):
        other = fake_actions(tmp_path, scope=scope)
        (tmp_path / 'notes.txt').unlink(missing_ok=True)
        assert save_file_step(other, STEP, lambda: False) is None
        other.control.return_value.app_act.assert_not_called()


def test_failure_after_the_shortcut_is_reported_never_repeated(tmp_path):
    def not_saved(args):
        return json.dumps({'ok': False, 'verified': False, 'executed': True, 'result': 'not created'})
    actions = fake_actions(tmp_path, save=not_saved)
    with pytest.raises(ValueError, match='not repeated'):
        save_file_step(actions, STEP, lambda: False)
    assert actions.control.return_value.app_act.call_count == 1

    def no_dialog(args):
        raise ControlError('The Save As dialog did not appear in this window. Nothing was saved.',
                           ErrorCategory.TARGET_NOT_FOUND)
    actions = fake_actions(tmp_path, save=no_dialog)
    with pytest.raises(ValueError, match='did not appear'):
        save_file_step(actions, STEP, lambda: False)
    assert actions.control.return_value.app_act.call_count == 1


def registry_actions(directory, config):
    from jarvis.task_state import TaskState
    actions = Mock()
    actions.config = config
    actions.task_state = TaskState(directory)
    actions.task_state.start('Save document as notes.txt in tests', 'task')
    actions.brain.visual_fallback.save_file.return_value = 'visual path'
    return actions


def test_tool_uses_the_recipe_only_with_the_flag(tmp_path):
    step = {**STEP, 'content': ''}
    with tempfile.TemporaryDirectory() as directory:
        off = registry_actions(directory, {})
        off._task_folder.return_value = str(tmp_path)
        assert ToolRegistry(off).execute(step, lambda: False).evidence == 'visual path'
        off.control.assert_not_called()
    with tempfile.TemporaryDirectory() as directory:
        on = registry_actions(directory, {'control': {'shared_save': True}})
        on._task_folder.return_value = str(tmp_path)
        on.control.return_value.app_scope = 'win-77'
        on.control.return_value.app_act.side_effect = lambda op, args, cancelled: saved(args)
        assert 'verified on disk' in ToolRegistry(on).execute(step, lambda: False).evidence
        on.brain.visual_fallback.save_file.assert_not_called()
    with tempfile.TemporaryDirectory() as directory:
        unknown = registry_actions(directory, {'control': {'shared_save': True}})
        unknown._task_folder.return_value = str(tmp_path / 'x')
        (tmp_path / 'x').mkdir()
        unknown.control.return_value.app_scope = ''
        assert ToolRegistry(unknown).execute(step, lambda: False).evidence == 'visual path'
