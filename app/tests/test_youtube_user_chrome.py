"""YouTube in the user's Chrome profile, numbered results, playlists, skip-ad and the logo fix (2026-10-20).

Offline: fake media sessions, fake Chrome launch and a fake Jarvis browser. No real browser is driven.
"""
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

BASE = next(p for p in Path(__file__).resolve().parents if (p / 'main.py').is_file())
sys.path.insert(0, str(BASE))
from jarvis import media_player, youtube_chrome  # noqa: E402
from jarvis.browser_worker import AUTO_SKIP_ADS, validate_request  # noqa: E402
from jarvis.commands import parse  # noqa: E402
from jarvis.ui_controls import _category  # noqa: E402

PL = 'PLi-epCWqWTgKjhTGZVkmN3OLBRQG2mt2W'


def actions(mode='user_chrome', profile='Default'):
    browser = Mock()
    browser.request.return_value = {'verified': True, 'state': {'position': 1, 'duration': 200}}
    return SimpleNamespace(config={'media': {'youtube_browser': mode, 'youtube_chrome_profile': profile}},
                           apps={'chrome': ['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe']},
                           report=Mock(), _browser=lambda: browser, browser=browser)


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(media_player, 'fetch_image', lambda url: '')
    monkeypatch.setattr(media_player, 'pause_other', lambda *a: None)
    monkeypatch.setattr(media_player, 'first_playlist_title', lambda playlist_id: 'First Song')


# ----- parsing -------------------------------------------------------------------------------
@pytest.mark.parametrize('text,kind,value,extra', [
    ('play the first playlist', 'select_context', '1:playlist', 'select'),
    ('play the second one', 'select_context', '2:one', 'select'),
    ('play number 3', 'select_context', '3:one', 'select'),
    ('play 3', 'select_context', '3:one', 'select'),
    ('play the third playlist', 'select_context', '3:playlist', 'select'),
    ('play the last one', 'select_context', 'last:one', 'select'),
    ('so i will select the second video', 'select_context', '2:video', 'select'),
    ('open the second result', 'select_context', '2:result', 'select'),
    ('play the 2nd song', 'select_context', '2:track', 'play'),
    ('skip ad', 'media_control', 'skip_ad', 'youtube'),
    ('skip the ads', 'media_control', 'skip_ad', 'youtube'),
    ('play hindi lofi playlist from youtube', 'play_media', 'hindi lofi playlist', 'youtube'),
    ('play 22', 'play_media', '22', ''),
])
def test_spoken_phrasings(text, kind, value, extra):
    command = parse(text)
    assert (command.kind, command.value, command.extra) == (kind, value, extra)


@pytest.mark.parametrize('text,expected', [
    ('hindi lofi playlist', ('hindi lofi', 'playlist')),
    ('hindi lofi playlist or song', ('hindi lofi', 'playlist')),
    ('some hindi lofi songs', ('hindi lofi', 'video')),
])
def test_playlist_requests_are_detected(text, expected):
    assert media_player.youtube_request(text) == expected


# ----- logo fix ----------------------------------------------------------------------------------
def test_youtube_logo_is_never_video_one():
    rows = [('YouTube Home', ''), ('YouTube Premium', ''), ('YouTube IN', 'https://www.youtube.com/'),
            ('Best of Bollywood Hindi lofi mix by LoFi Hub 2.1M views', ''), ('Arijit Singh Lofi Songs 900K views', '')]
    controls = [{'name': n, 'role': 'Hyperlink', 'rect': (130, 90 + i, 230, 130), 'context': 'video' if i > 2 else '', 'href': h}
                for i, (n, h) in enumerate(rows)]
    chosen = _category(controls, 'video', 'lofi - YouTube - Google Chrome')
    assert [c['name'][:12] for c in chosen] == ['Best of Boll', 'Arijit Singh']


# ----- user Chrome -----------------------------------------------------------------------------
def test_settings_default_and_validation():
    assert youtube_chrome.settings(SimpleNamespace(config={})) == 'Default'
    assert youtube_chrome.settings(actions(mode='jarvis')) is None
    with pytest.raises(ValueError):
        youtube_chrome.settings(actions(profile='..\\evil'))


def test_open_url_uses_profile_without_shell(monkeypatch):
    launched = []
    monkeypatch.setattr(youtube_chrome.subprocess, 'Popen', lambda args, shell: launched.append((args, shell)))
    youtube_chrome.open_url(actions(), 'https://www.youtube.com/watch?v=U5ewn_HTZaM', 'Default')
    assert launched == [(['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', '--profile-directory=Default',
                          'https://www.youtube.com/watch?v=U5ewn_HTZaM'], False)]
    for bad in ['http://www.youtube.com/', 'https://evil.example/?youtube.com', 'file:///C:/x']:
        with pytest.raises(youtube_chrome.ChromeUnavailable):
            youtube_chrome.open_url(actions(), bad, 'Default')


class Sessions:
    """Fake Windows media sessions: a list of snapshots returned in turn (the last one repeats)."""
    def __init__(self, *snapshots):
        self.snapshots, self.sent = list(snapshots), []

    def read(self):
        return self.snapshots.pop(0) if len(self.snapshots) > 1 else self.snapshots[0]

    def send(self, action, title=''):
        self.sent.append((action, title))
        return 1


def run_play(fake, monkeypatch, title='Bollywood Lofi', timeout=8):
    monkeypatch.setattr(youtube_chrome, 'open_url', lambda *a: None)
    clock = iter(range(1000))
    return youtube_chrome.play(actions(), 'https://www.youtube.com/watch?v=U5ewn_HTZaM', title, lambda: False,
                               timeout=timeout, clock=lambda: next(clock), sleep=lambda s: None, read=fake.read, send=fake.send)


def row(title, status='playing'):
    return {'title': title, 'artist': 'x', 'status': status, 'position': 0, 'duration': 100}


def test_confirmed_playback_pauses_the_other_player_first(monkeypatch):
    fake = Sessions([row('Old song')], [row('Old song', 'paused')], [row('Old song', 'paused'), row('Bollywood Lofi Love Songs')])
    assert run_play(fake, monkeypatch)['title'] == 'Bollywood Lofi Love Songs'
    assert fake.sent[0] == ('pause_others', 'Bollywood Lofi')


def test_held_autoplay_gets_one_play_request(monkeypatch):
    fake = Sessions([], *[[row('Bollywood Lofi', 'paused')]] * 8, [row('Bollywood Lofi')])
    run_play(fake, monkeypatch, timeout=20)
    assert [a for a, _ in fake.sent].count('play') == 1


def test_nothing_started_means_safe_fallback(monkeypatch):
    with pytest.raises(youtube_chrome.ChromeUnavailable):
        run_play(Sessions([]), monkeypatch)


def test_something_else_started_is_uncertain_not_replayed(monkeypatch):
    with pytest.raises(youtube_chrome.PlaybackUncertain):
        run_play(Sessions([], [row('Advertisement - Buy now')]), monkeypatch)


def test_title_matching():
    assert youtube_chrome.matches('Tera Chehra || Arijit Singh', 'Tera Chehra || Arijit Singh || Slowed And Reverb')
    assert not youtube_chrome.matches('Tera Chehra', 'Completely different song')


# ----- play / fallback / numbered ------------------------------------------------------------------
def test_play_item_in_user_chrome_never_touches_jarvis_browser(monkeypatch):
    a = actions()
    monkeypatch.setattr(youtube_chrome, 'play', lambda *x, **k: row('First Song'))
    assert media_player.play_youtube_item(a, 'U5ewn_HTZaM', 'Bollywood Lofi', 'Sunny', lambda: False, playlist_id=PL) \
        == 'Playing the playlist Bollywood Lofi on YouTube in your Chrome.'
    assert a.youtube_target == 'user_chrome' and not a.browser.request.called


def test_chrome_unavailable_falls_back_to_jarvis_browser_with_playlist(monkeypatch):
    a = actions()
    def unavailable(*x, **k):
        raise youtube_chrome.ChromeUnavailable('no chrome')
    monkeypatch.setattr(youtube_chrome, 'play', unavailable)
    media_player.play_youtube_item(a, 'U5ewn_HTZaM', 'Bollywood Lofi', 'Sunny', lambda: False, playlist_id=PL)
    assert a.browser.request.call_args.kwargs == {'new_task': True, 'video_id': 'U5ewn_HTZaM', 'playlist_id': PL}
    assert a.youtube_target == 'jarvis'


def test_uncertain_chrome_playback_is_not_replayed_elsewhere(monkeypatch):
    a = actions()
    def uncertain(*x, **k):
        raise youtube_chrome.PlaybackUncertain('ad')
    monkeypatch.setattr(youtube_chrome, 'play', uncertain)
    with pytest.raises(media_player.PlaybackUncertain):
        media_player.play_youtube_item(a, 'U5ewn_HTZaM', 'X', '', lambda: False)
    assert not a.browser.request.called


def test_numbered_choice_plays_that_exact_result(monkeypatch):
    a, played = actions(), []
    monkeypatch.setattr(media_player, 'play_youtube_item', lambda *x, **k: played.append((x[1], k)) or 'ok')
    rows = [{'playlist_id': PL[:-1] + str(i), 'title': 'P' + str(i), 'channel': '', 'first_video_id': 'U5ewn_HTZa' + str(i)}
            for i in range(1, 4)]
    media_player.remember_results(a, 'playlist', rows)
    media_player.play_result(a, 2, 'playlist', lambda: False)
    media_player.play_result(a, -1, 'one', lambda: False)
    assert played == [('U5ewn_HTZa2', {'playlist_id': rows[1]['playlist_id']}), ('U5ewn_HTZa3', {'playlist_id': rows[2]['playlist_id']})]
    with pytest.raises(ValueError):
        media_player.play_result(a, 9, 'one', lambda: False)
    media_player.remember_results(a, 'video', [{'video_id': 'U5ewn_HTZaM', 'title': 'v'}])
    with pytest.raises(ValueError, match='not playlists'):
        media_player.play_result(a, 1, 'playlist', lambda: False)


def test_old_results_expire():
    a = actions()
    media_player.remember_results(a, 'video', [{'video_id': 'U5ewn_HTZaM', 'title': 'v'}])
    a.youtube_results['at'] -= 21 * 60
    assert media_player.recent_results(a) is None


def test_user_chrome_pause_is_read_back(monkeypatch):
    a = actions()
    a.last_youtube = {'title': 'Bollywood Lofi'}
    states = iter([[row('Bollywood Lofi')], [row('Bollywood Lofi')], [row('Bollywood Lofi', 'paused')]])
    monkeypatch.setattr(youtube_chrome, 'sessions', lambda: next(states))
    monkeypatch.setattr(youtube_chrome, 'act', lambda action, title: 1)
    assert media_player.control_user_chrome(a, 'pause', lambda: False, sleep=lambda s: None) == 'Paused Bollywood Lofi.'


def test_user_chrome_unconfirmed_change_is_uncertain(monkeypatch):
    a = actions()
    a.last_youtube = {'title': 'Bollywood Lofi'}
    monkeypatch.setattr(youtube_chrome, 'sessions', lambda: [row('Bollywood Lofi')])
    monkeypatch.setattr(youtube_chrome, 'act', lambda action, title: 1)
    clock = iter(range(100))
    with pytest.raises(media_player.PlaybackUncertain):
        media_player.control_user_chrome(a, 'next', lambda: False, clock=lambda: next(clock), sleep=lambda s: None)


# ----- Jarvis browser worker contract ------------------------------------------------------------
def test_worker_accepts_playlist_requests_and_rejects_bad_ones():
    validate_request({'operation': 'search', 'value': 'hindi lofi', 'kind': 'playlist', 'settings': {'auto_skip_ads': True}})
    validate_request({'operation': 'play_video', 'video_id': 'U5ewn_HTZaM', 'playlist_id': PL, 'settings': {}})
    for bad in [{'operation': 'search', 'value': 'x', 'kind': 'channel'},
                {'operation': 'play_video', 'video_id': 'U5ewn_HTZaM', 'playlist_id': 'javascript:alert(1)'},
                {'operation': 'search', 'value': 'x', 'settings': {'auto_skip_ads': 'yes'}}]:
        with pytest.raises(ValueError):
            validate_request(bad)


def test_auto_skip_script_only_runs_on_youtube_and_only_clicks_skip():
    assert 'youtube\\.com$' in AUTO_SKIP_ADS and '.ad-showing' in AUTO_SKIP_ADS
    assert 'ytp-skip-ad-button' in AUTO_SKIP_ADS and 'offsetParent' in AUTO_SKIP_ADS


def test_results_show_as_a_numbered_island_list_that_plays_the_chosen_item():
    from jarvis.island_choices import resolve, snapshot
    a = actions()
    a.generation, a.pending_open, a.pending_question = 1, None, None
    a.projects, a.ui_controls, a.knowledge = SimpleNamespace(pending=None), None, None
    import jarvis.whatsapp as whatsapp
    original, whatsapp.snapshot = whatsapp.snapshot, lambda actions: None
    try:
        media_player.remember_results(a, 'playlist', [{'title': 'Sad Lofi songs', 'playlist_id': PL, 'first_video_id': 'U5ewn_HTZaM'},
                                                      {'title': 'Bollywood Lofi Love Songs', 'playlist_id': PL, 'first_video_id': 'U5ewn_HTZaN'}])
        card = snapshot(a)
        assert card['kind'] == 'youtube' and [o['label'] for o in card['options']] == ['Sad Lofi songs', 'Bollywood Lofi Love Songs']
        command = resolve(a, card['token'], 1)
        assert (command.kind, command.value, command.extra) == ('select_context', '2:one', 'select')
    finally:
        whatsapp.snapshot = original


def test_search_opens_your_chrome_and_remembers_the_spoken_list(monkeypatch):
    a, opened = actions(), []
    monkeypatch.setattr(youtube_chrome, 'open_url', lambda acts, url, profile, cancelled: opened.append((url, profile)))
    monkeypatch.setattr(media_player, 'youtube_playlists', lambda q: [
        {'title': 'Sad Lofi songs', 'playlist_id': PL, 'first_video_id': 'U5ewn_HTZaM'}])
    reply = media_player.search_youtube(a, 'some hindi lofi playlists', lambda: False)
    assert opened == [('https://www.youtube.com/results?search_query=hindi%20lofi&sp=EgIQAw%3D%3D', 'Default')]
    assert reply.startswith('Found these YouTube playlists: 1. Sad Lofi songs')
    assert a.youtube_target == 'user_chrome' and not a.browser.request.called


def test_search_lists_nothing_but_still_opens_when_youtube_listing_fails(monkeypatch):
    a, opened = actions(), []
    monkeypatch.setattr(youtube_chrome, 'open_url', lambda *x: opened.append(x))
    def offline(*x, **k):
        raise ConnectionError('offline')
    monkeypatch.setattr(media_player, 'youtube_search', offline)
    assert 'Opened YouTube video results' in media_player.search_youtube(a, 'cats', lambda: False) and opened


def test_search_falls_back_to_jarvis_browser_when_chrome_is_missing(monkeypatch):
    a = actions()
    a.apps = {}
    monkeypatch.setattr(media_player, 'youtube_search', lambda q, limit: [])
    a.browser.request.return_value = {'message': 'Found these YouTube videos: 1. A', 'results': [{'video_id': 'U5ewn_HTZaM', 'title': 'A'}]}
    assert media_player.search_youtube(a, 'cats', lambda: False) == 'Found these YouTube videos: 1. A'
    assert a.youtube_target == 'jarvis' and a.youtube_results['rows'][0]['title'] == 'A'
