"""The user's pinned Chrome profile must survive every supported launch route."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jarvis import media_player, youtube_chrome
from jarvis.actions import Actions
from jarvis.browser_automation import BrowserAutomation
from jarvis.commands import parse
from jarvis.tools import ToolRegistry


def locked(tmp_path):
    a = Actions.__new__(Actions)
    a.base = tmp_path
    a.config = {'media': {'youtube_profile_only':True, 'youtube_chrome_profile':'Default',
                          'youtube_browser':'user_chrome'}}
    a.apps = {'chrome':[r'C:\Program Files\Google\Chrome\Application\chrome.exe']}
    a.report = Mock()
    a.browser_automation = None
    a.last_media = None
    a.youtube_target = ''
    a.projects = SimpleNamespace(pending=None)
    a.ui_controls = None
    a.desktop = None
    a._browser = Mock(side_effect=AssertionError('Wrong browser opened'))
    return a


@pytest.mark.parametrize('target', ['youtube', 'https://youtube.com/', 'https://youtu.be/aqz-KE-bpKQ',
                                  'https://www.youtube.com/playlist?list=PL123456789abc'])
def test_planner_navigation_uses_only_default_profile(tmp_path, monkeypatch, target):
    a = locked(tmp_path)
    launched = Mock()
    monkeypatch.setattr(youtube_chrome.subprocess, 'Popen', launched)
    result = ToolRegistry(a).execute({'action':'browser_navigate','value':target}, lambda:False)
    assert json.loads(result.evidence)['outcome'] == 'opened_only'
    assert json.loads(result.evidence)['playing_verified'] is False
    assert launched.call_count == 1
    assert '--profile-directory=Default' in launched.call_args.args[0]
    a._browser.assert_not_called()


def test_natural_language_open_uses_default_and_never_tries_owned_browser(tmp_path, monkeypatch):
    a = locked(tmp_path)
    launched = Mock()
    monkeypatch.setattr(youtube_chrome.subprocess, 'Popen', launched)
    command = parse('open youtube')
    result = a.execute(command)
    assert 'profile Default' in result
    assert launched.call_count == 1
    assert '--profile-directory=Default' in launched.call_args.args[0]
    a._browser.assert_not_called()


def test_pinned_profile_overrides_owned_mode_and_rejects_other_profile(tmp_path, monkeypatch):
    a = locked(tmp_path)
    a.config['media']['youtube_browser'] = 'jarvis'
    assert youtube_chrome.settings(a) == 'Default'
    launched = Mock()
    monkeypatch.setattr(youtube_chrome.subprocess, 'Popen', launched)
    with pytest.raises(youtube_chrome.ChromeUnavailable, match='locked'):
        youtube_chrome.open_url(a, 'https://www.youtube.com/', 'Profile 1')
    launched.assert_not_called()


def test_search_failure_never_falls_back(tmp_path, monkeypatch):
    a = locked(tmp_path)
    monkeypatch.setattr(media_player, 'youtube_search', lambda *a, **k: [])
    monkeypatch.setattr(youtube_chrome, 'open_url', Mock(side_effect=youtube_chrome.ChromeUnavailable('missing')))
    with pytest.raises(ValueError, match='no other browser'):
        media_player.search_youtube(a, 'cats', lambda:False)
    a._browser.assert_not_called()


def test_play_failure_never_falls_back(tmp_path, monkeypatch):
    a = locked(tmp_path)
    monkeypatch.setattr(media_player, 'fetch_image', lambda *a: '')
    monkeypatch.setattr(media_player, 'pause_other', lambda *a: None)
    monkeypatch.setattr(youtube_chrome, 'play', Mock(side_effect=youtube_chrome.ChromeUnavailable('missing')))
    with pytest.raises(media_player.PlaybackUncertain, match='no other browser'):
        media_player.play_youtube_item(a, 'aqz-KE-bpKQ', 'Big Buck Bunny', 'Blender', lambda:False)
    a._browser.assert_not_called()


@pytest.mark.parametrize('url', ['https://user@youtube.com/', 'https://youtube.com:4433/',
                                'https://youtube.com:bad/', 'https://youtube.com.evil.test/'])
def test_authority_is_validated_before_launch(tmp_path, monkeypatch, url):
    launched = Mock()
    monkeypatch.setattr(youtube_chrome.subprocess, 'Popen', launched)
    with pytest.raises(youtube_chrome.ChromeUnavailable):
        youtube_chrome.open_url(locked(tmp_path), url, 'Default')
    launched.assert_not_called()


def test_cancelled_open_has_no_effect(tmp_path, monkeypatch):
    launched = Mock()
    monkeypatch.setattr(youtube_chrome.subprocess, 'Popen', launched)
    with pytest.raises(ValueError, match='cancelled'):
        youtube_chrome.open_requested(locked(tmp_path), 'youtube', lambda:True)
    launched.assert_not_called()


def test_owned_browser_rejects_youtube_before_starting_worker():
    browser = BrowserAutomation({'chrome':['chrome.exe']})
    browser.settings['youtube_profile_only'] = True
    browser.transport = Mock()
    for operation, args in [('navigate',{'value':'youtube'}), ('search',{'value':'cats'}),
                             ('play_video',{'video_id':'aqz-KE-bpKQ'}), ('control',{'value':'pause'})]:
        with pytest.raises(ValueError, match='restricted'):
            browser.request(operation, **args)
    browser.transport.request.assert_not_called()


def test_windows_command_88_respects_profile(tmp_path, monkeypatch):
    from jarvis.windows_commands import execute
    a = locked(tmp_path)
    launched = Mock()
    monkeypatch.setattr(youtube_chrome.subprocess, 'Popen', launched)
    assert 'profile Default' in execute(a, [88], {})
    assert '--profile-directory=Default' in launched.call_args.args[0]


def test_unrelated_navigation_keeps_existing_path(tmp_path):
    assert youtube_chrome.open_requested(locked(tmp_path), 'https://example.com/') is None
