"""Owned module 03 routing assertions: never launch a real app or input text."""
import json
from unittest.mock import Mock, patch
import pytest
from jarvis.commands import Command, parse
from jarvis.engine import Engine


@pytest.mark.parametrize('text', ['Open Chrome', 'Could you bring up Chrome for me?'],
    ids=['JRV-03-001', 'JRV-03-002'])
def test_open_chrome_deterministic_handler(tmp_path, text):
    from jarvis.actions import Actions
    sent = []
    engine = Engine(sent.append, Mock())
    engine.activate()
    with patch('jarvis.repo_abilities.parse_learned', side_effect=AssertionError('Known command must bypass learning')):
        engine.feed(text, final=True)
    assert sent == [Command('open', 'chrome')]
    actions = Actions({'apps': {'chrome': ['fixture-chrome.exe']}, 'files_root': 'managed',
        '_ui_verification': True, 'memory': {'enabled': False}, 'brain': {'enabled': False}}, tmp_path, Mock())
    actions.desktop = Mock()
    try:
        with patch('jarvis.actions.subprocess.Popen') as launch, patch('jarvis.actions.time.sleep'):
            actions.execute(sent[0])
        launch.assert_called_once()
        assert launch.call_args.args[0][0] == 'fixture-chrome.exe'
    finally:
        actions.close()


def test_JRV_03_003_negation_never_dispatches():
    sent = []
    engine = Engine(sent.append, Mock())
    engine.activate()
    engine.feed('Please do not open Chrome', final=True)
    assert not sent


def test_JRV_03_004_folder_not_browser():
    command = parse('Open the Chrome downloads folder')
    assert command.kind in {'open_folder', 'task'}
    assert command.kind != 'open'


def test_latest_spreadsheet_uses_safe_planned_path():
    command = parse('Open my latest spreadsheet')
    assert command.kind in {'task', 'open_file', 'context_search'}


def test_JRV_03_005_latest_spreadsheet_asks_before_open(tmp_path):
    from jarvis.actions import Actions
    actions=Actions({'apps':{},'files_root':'managed','_ui_verification':True,
        'memory':{'enabled':False},'brain':{'enabled':False},'deliberation':{'enabled':False}},tmp_path,Mock())
    try:
        with patch('jarvis.actions.os.startfile') as opening,patch.object(actions.brain.client,'request') as model:
            result=actions.execute(parse('Open my latest spreadsheet'))
        assert 'Which spreadsheet' in result
        assert actions.pending_question['slot']=='file'
        assert actions.task_state.snapshot()['status']=='paused'
        opening.assert_not_called();model.assert_not_called()
    finally:actions.close()


def test_JRV_03_006_relative_volume():
    command = parse('Turn the sound down a notch')
    assert command == Command('spotify_volume', 'down', 'auto')


def test_JRV_03_007_volume_range():
    command = parse('Set volume to 150 percent')
    from jarvis.spotify import volume
    session = Mock()
    session.Process.name.return_value = 'spotify.exe'
    with patch('jarvis.spotify._audio_sessions', return_value=[session]):
        with pytest.raises(ValueError):
            volume(command.value, lambda: False)
    session.SimpleAudioVolume.SetMasterVolume.assert_not_called()


def test_JRV_03_011_alias_resolution():
    from jarvis.names import rank_spelling
    labels = {'visual studio code': ['fixture-code.exe']}
    for text in ('open VS Code', 'open vscode', 'open Visual Studio Code'):
        assert rank_spelling(parse(text).value, labels) == ['visual studio code']


def test_JRV_03_008_pause_current_player():
    assert parse("Pause what's playing") == Command('click_control', 'pause', 'click')


def test_JRV_03_009_ordered_compound():
    sent = []
    engine = Engine(sent.append, Mock())
    engine.activate()
    engine.feed('Open Notepad, then type hello', final=True)
    assert len(sent) == 2
    assert sent[0] == Command('open', 'notepad')
    assert sent[1].kind in {'write_text', 'compose_text'} and sent[1].value == 'hello'
    assert json.loads(sent[1].extra)['target'].lower() == 'notepad'


def test_JRV_03_010_close_tab_scope():
    assert parse('I said close the tab, not the browser') == Command('windows_command', '[329]', '{}')


def test_JRV_03_012_unknown_tool_not_executable():
    with pytest.raises(ValueError):
        parse('tool open_xxx {}')
    with pytest.raises(ValueError):
        parse('Run an unknown command named open_xxx')


@pytest.mark.parametrize('text', ['pause', 'volume up', 'open Chrome'])
def test_reflex_never_calls_canonical_or_learned(text):
    with patch('jarvis.phrasing.canonical', side_effect=AssertionError('No normalization')), \
        patch('jarvis.repo_abilities.parse_learned', side_effect=AssertionError('No learned route')):
        assert parse(text).kind in {'click_control', 'spotify_volume', 'open'}
