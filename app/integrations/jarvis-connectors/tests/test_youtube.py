"""YouTube connector: offline parsing/safety tests plus opt-in live checks (JARVIS_LIVE_YOUTUBE=1).

Fixtures are synthetic but follow the page shapes observed live on 2026-10-20
(videoRenderer, lockupViewModel playlists/items, ytInitialPlayerResponse).
"""
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from conftest import ROOT, load_connector
from jarvis_connector import ToolError

YouTubeConnector = load_connector('apps/youtube', 'YouTubeConnector')
pages = sys.modules['youtube_pages']
SERVER = ROOT / 'connectors' / 'apps' / 'youtube' / 'server.py'
LIVE = os.environ.get('JARVIS_LIVE_YOUTUBE') == '1'

VID, VID2, PL = 'YOJsKatW-Ts', 'Xyj0Mq-YdUY', 'PLOzDu-MXXLlgKMA3S2FXY_XVyDrukc0si'
STREAM = 'https://rr2---sn.googlevideo.com/initplayback?ip=203.0.113.7&id=abc'  # must never leak


def video_renderer(video_id, title, length='19:11'):
    row = {'videoId': video_id, 'title': {'runs': [{'text': title}]}, 'ownerText': {'runs': [{'text': 'Chan'}]},
           'onesie': {'url': STREAM}}
    if length:
        row['lengthText'] = {'simpleText': length}
    return {'videoRenderer': row}


def lockup(kind, content_id, title, channel='the bootleg boy', badge='29 videos', first=VID):
    return {'lockupViewModel': {
        'contentType': kind, 'contentId': content_id,
        'contentImage': {'thumbnailBadgeViewModel': {'text': badge}},
        'metadata': {'lockupMetadataViewModel': {'title': {'content': title}, 'metadata': {'contentMetadataViewModel': {
            'metadataRows': [{'metadataParts': [{'text': {'content': channel}}]},
                             {'metadataParts': [{'text': {'content': '35M'}}]}]}}}},
        'rendererContext': {'commandContext': {'onTap': {'innertubeCommand': {
            'watchEndpoint': {'videoId': first, 'playlistId': content_id, 'onesie': {'url': STREAM}}}}}}}}


def page(data, variable='ytInitialData'):
    return '<html><script>var ' + variable + ' = ' + json.dumps(data) + ';</script></html>'


SEARCH = {'contents': [video_renderer(VID, 'RAINING IN OSAKA'), {'adSlotRenderer': {}},
                       video_renderer(VID, 'duplicate'), video_renderer('bad', 'malformed id'),
                       video_renderer(VID2, 'Live radio', length=None), video_renderer('a' * 11, 'x' * 300)]}
PLAYLISTS = {'contents': [lockup('LOCKUP_CONTENT_TYPE_PLAYLIST', PL, 'RAINING (Lofi HipHop)'),
                          lockup('LOCKUP_CONTENT_TYPE_VIDEO', VID, 'not a playlist'),
                          {'playlistRenderer': {'playlistId': 'PLlegacy12345678', 'title': {'simpleText': 'Legacy'},
                                                'shortBylineText': {'runs': [{'text': 'Old'}]}, 'videoCount': '1,204',
                                                'navigationEndpoint': {'watchEndpoint': {'videoId': VID2}}}}]}
PLAYLIST_PAGE = {'metadata': {'playlistMetadataRenderer': {'title': 'RAINING (Lofi HipHop)'}},
                 'contents': [lockup('LOCKUP_CONTENT_TYPE_VIDEO', VID, 'Osaka', badge='19:11'),
                              lockup('LOCKUP_CONTENT_TYPE_VIDEO', VID2, 'Paris', badge='18:38')]}
PLAYER = {'playabilityStatus': {'status': 'OK'}, 'streamingData': {'formats': [{'url': STREAM}]},
          'videoDetails': {'videoId': VID, 'title': 'RAINING IN OSAKA', 'author': 'the bootleg boy',
                           'lengthSeconds': '1151', 'viewCount': '35562525', 'isLiveContent': False}}


class FakeWeb:
    """Records every URL; answers from a path -> body map."""
    def __init__(self, responses):
        self.responses, self.urls = responses, []

    def __call__(self, url):
        self.urls.append(url)
        for prefix, body in self.responses.items():
            if url.startswith(prefix):
                return body
        raise AssertionError('unexpected fetch ' + url)


@pytest.fixture
def youtube(monkeypatch):
    monkeypatch.delenv('JARVIS_YOUTUBE_API_KEY', raising=False)
    connector = YouTubeConnector()
    connector.configure(SimpleNamespace(timeout=5))
    return connector


def use(connector, responses):
    web = FakeWeb(responses)
    connector.fetch = web
    return web


# ----- links ------------------------------------------------------------------------
@pytest.mark.parametrize('link,video,playlist', [
    (VID, VID, ''), (PL, '', PL),
    ('https://www.youtube.com/watch?v=' + VID, VID, ''),
    ('https://youtube.com/watch?v=' + VID + '&list=' + PL + '&index=3', VID, PL),
    ('https://youtu.be/' + VID + '?si=tracking', VID, ''),
    ('https://www.youtube.com/shorts/' + VID, VID, ''),
    ('https://m.youtube.com/embed/' + VID, VID, ''),
    ('https://www.youtube.com/playlist?list=' + PL, '', PL),
    ('  https://music.youtube.com/watch?v=' + VID + '  ', VID, ''),
])
def test_parse_link_accepts_youtube(link, video, playlist):
    assert pages.parse_link(link) == {'video_id': video, 'playlist_id': playlist}


@pytest.mark.parametrize('link', [
    'http://www.youtube.com/watch?v=' + VID, 'https://youtube.com.evil.example/watch?v=' + VID,
    'https://evil.example/watch?v=' + VID, 'https://user:pw@www.youtube.com/watch?v=' + VID,
    'https://www.youtube.com:8443/watch?v=' + VID, 'javascript:alert(1)', 'https://www.youtube.com/watch?v=short',
    'https://www.youtube.com/watch?v=' + VID + 'x', 'https://www.youtube.com/@channel', 'lofi hip hop', '',
    'https://www.youtube.com/redirect?q=https://evil.example', 'file:///C:/secret.txt'])
def test_parse_link_rejects_everything_else(link):
    assert pages.parse_link(link) is None


def test_parse_link_tool_is_offline(youtube):
    web = use(youtube, {})
    assert youtube.invoke('parse_link', {'link': 'https://evil.example/watch?v=' + VID})['is_youtube'] is False
    found = youtube.invoke('parse_link', {'link': 'https://youtu.be/' + VID})
    assert found == {'is_youtube': True, 'video_id': VID, 'playlist_id': '', 'url': 'https://www.youtube.com/watch?v=' + VID}
    assert web.urls == []


# ----- search / lookup ----------------------------------------------------------------
def test_search_videos_extracts_named_fields_only(youtube):
    web = use(youtube, {'https://www.youtube.com/results?': page(SEARCH)})
    rows = youtube.invoke('search_videos', {'query': 'lofi & "hip hop"', 'limit': 10})
    assert [r['video_id'] for r in rows] == [VID, VID2, 'a' * 11]          # duplicate and malformed skipped
    assert rows[0] == {'video_id': VID, 'title': 'RAINING IN OSAKA', 'channel': 'Chan', 'duration_seconds': 1151,
                       'live': False, 'url': 'https://www.youtube.com/watch?v=' + VID}
    assert rows[1]['live'] is True and rows[1]['duration_seconds'] == 0
    assert len(rows[2]['title']) == 120
    assert '203.0.113.7' not in json.dumps(rows)
    assert 'search_query=lofi+%26+%22hip+hop%22' in web.urls[0]               # query is encoded, never spliced


def test_search_limit_is_respected(youtube):
    use(youtube, {'https://www.youtube.com/results?': page(SEARCH)})
    assert len(youtube.invoke('search_videos', {'query': 'x', 'limit': 1})) == 1


def test_search_playlists_handles_new_and_legacy_layouts(youtube):
    web = use(youtube, {'https://www.youtube.com/results?': page(PLAYLISTS)})
    rows = youtube.invoke('search_playlists', {'query': 'lofi'})
    assert 'sp=EgIQAw%3D%3D' in web.urls[0]
    assert rows[0] == {'playlist_id': PL, 'title': 'RAINING (Lofi HipHop)', 'channel': 'the bootleg boy', 'video_count': 29,
                       'url': 'https://www.youtube.com/playlist?list=' + PL,
                       'play_url': 'https://www.youtube.com/watch?v=' + VID + '&list=' + PL}
    assert rows[1]['playlist_id'] == 'PLlegacy12345678' and rows[1]['video_count'] == 1204
    assert len(rows) == 2 and '203.0.113.7' not in json.dumps(rows)


def test_no_results_is_an_empty_list(youtube):
    use(youtube, {'https://www.youtube.com/results?': page({'contents': []})})
    assert youtube.invoke('search_videos', {'query': 'zzzz'}) == []


def test_consent_or_changed_page_is_a_tool_error(youtube):
    use(youtube, {'https://www.youtube.com/results?': '<html>Before you continue to YouTube</html>'})
    result = youtube.call('search_videos', {'query': 'x'})
    assert result['isError'] is True and 'consent page or layout change' in result['content'][0]['text']


def test_corrupt_embedded_data_is_a_tool_error(youtube):
    use(youtube, {'https://www.youtube.com/results?': '<script>var ytInitialData = {"contents": [;</script>'})
    assert youtube.call('search_videos', {'query': 'x'})['isError'] is True


def test_video_details(youtube):
    web = use(youtube, {'https://www.youtube.com/watch?': page(PLAYER, 'ytInitialPlayerResponse')})
    details = youtube.invoke('video_details', {'video': 'https://youtu.be/' + VID})
    assert details == {'video_id': VID, 'title': 'RAINING IN OSAKA', 'channel': 'the bootleg boy', 'duration_seconds': 1151,
                       'views': 35562525, 'live': False, 'playable': True, 'status': 'OK',
                       'url': 'https://www.youtube.com/watch?v=' + VID}
    assert web.urls[0].startswith('https://www.youtube.com/watch?v=' + VID + '&')
    assert '203.0.113.7' not in json.dumps(details)


def test_unavailable_video_and_bad_input(youtube):
    use(youtube, {'https://www.youtube.com/watch?': page({'playabilityStatus': {'status': 'ERROR'}}, 'ytInitialPlayerResponse')})
    assert 'status ERROR' in youtube.call('video_details', {'video': VID})['content'][0]['text']
    for bad in ['https://evil.example/watch?v=' + VID, 'https://www.youtube.com/playlist?list=' + PL]:
        with pytest.raises(ToolError):
            youtube.invoke('video_details', {'video': bad})


def test_playlist_videos(youtube):
    use(youtube, {'https://www.youtube.com/playlist?': page(PLAYLIST_PAGE)})
    result = youtube.invoke('playlist_videos', {'playlist': 'https://www.youtube.com/watch?v=' + VID + '&list=' + PL})
    assert result['title'] == 'RAINING (Lofi HipHop)' and result['more'] is False
    assert result['videos'][1] == {'index': 2, 'video_id': VID2, 'title': 'Paris', 'channel': 'the bootleg boy',
                                   'duration_seconds': 1118, 'url': 'https://www.youtube.com/watch?v=' + VID2 + '&list=' + PL + '&index=2'}
    with pytest.raises(ToolError):
        youtube.invoke('playlist_videos', {'playlist': 'https://www.youtube.com/watch?v=' + VID})


def test_large_playlist_is_trimmed_to_what_jarvis_can_receive(youtube):
    many = {'contents': [lockup('LOCKUP_CONTENT_TYPE_VIDEO', '%011d' % i, 'T' * 110, channel='C' * 110, badge='1:00')
                         for i in range(15)]}
    use(youtube, {'https://www.youtube.com/playlist?': page(many)})
    youtube.max_result_chars = 3000
    result = youtube.invoke('playlist_videos', {'playlist': PL, 'limit': 15})
    assert result['more'] is True and 1 <= len(result['videos']) < 15 and youtube.fits(result)


def test_empty_playlist_is_a_tool_error(youtube):
    use(youtube, {'https://www.youtube.com/playlist?': page({'contents': []})})
    with pytest.raises(ToolError):
        youtube.invoke('playlist_videos', {'playlist': PL})


# ----- API key mode -------------------------------------------------------------------
def test_api_search_uses_key_but_never_returns_it(youtube, monkeypatch):
    monkeypatch.setenv('JARVIS_YOUTUBE_API_KEY', 'SYNTHETIC-KEY-123')
    api = {'items': [{'id': {'videoId': VID}, 'snippet': {'title': 'Osaka', 'channelTitle': 'Boy', 'liveBroadcastContent': 'none'}},
                     {'id': {'videoId': 'bad'}, 'snippet': {}}]}
    web = use(youtube, {'https://www.googleapis.com/youtube/v3/search?': json.dumps(api)})
    rows = youtube.invoke('search_videos', {'query': 'osaka'})
    assert [r['video_id'] for r in rows] == [VID] and 'SYNTHETIC-KEY-123' in web.urls[0]
    assert 'SYNTHETIC-KEY-123' not in json.dumps(rows)
    use(youtube, {'https://www.googleapis.com/youtube/v3/search?': 'not json'})
    result = youtube.call('search_videos', {'query': 'osaka'})
    assert result['isError'] is True and 'SYNTHETIC-KEY-123' not in json.dumps(result)


def test_real_fetch_refuses_other_hosts_and_hides_urls(youtube):
    for url in ['https://evil.example/', 'http://www.youtube.com/', 'https://www.youtube.com.evil.example/']:
        with pytest.raises(ToolError):
            YouTubeConnector.fetch(youtube, url)


def test_network_failure_message_has_no_url_or_key(youtube, monkeypatch):
    import urllib.request
    from urllib.error import URLError

    def offline(*args, **kwargs):
        raise URLError('getaddrinfo failed for https://www.googleapis.com/?key=SYNTHETIC-KEY-123')
    monkeypatch.setattr(sys.modules[YouTubeConnector.__module__], 'urlopen', offline)
    result = youtube.call('video_details', {'video': VID})
    assert result['isError'] is True and 'could not be reached' in result['content'][0]['text']
    assert 'SYNTHETIC' not in json.dumps(result) and 'googleapis' not in json.dumps(result)


def test_catalog_is_read_only_and_bridge_compatible(youtube):
    from jarvis import mcp_contract
    rows = youtube.describe()
    assert {r['name'] for r in rows} == {'search_videos', 'search_playlists', 'video_details', 'playlist_videos', 'parse_link'}
    assert all(r['annotations']['readOnlyHint'] for r in rows)
    for row in rows:
        mcp_contract.validate_schema_value(row['inputSchema'], {
            'search_videos': {'query': 'x'}, 'search_playlists': {'query': 'x'}, 'video_details': {'video': VID},
            'playlist_videos': {'playlist': PL}, 'parse_link': {'link': 'x'}}[row['name']])


# ----- through Jarvis -------------------------------------------------------------------
def bridge(tmp_path, tools=None):
    from jarvis.task_state import TaskState
    tools = tools or ['search_videos', 'search_playlists', 'video_details', 'playlist_videos', 'parse_link']
    (tmp_path / '.jarvis').mkdir()
    (tmp_path / '.jarvis' / 'mcp.json').write_text(json.dumps({'servers': {'youtube': {
        'enabled': True, 'trusted': True, 'command': sys.executable, 'args': [str(SERVER), '--runtime', 'builtin'],
        'allow_tools': tools, 'timeout_seconds': 30}}}), encoding='utf-8')
    state = TaskState(tmp_path)
    state.start('YouTube connector check', 'task')
    return SimpleNamespace(base=tmp_path, task_state=state, report=Mock(), config={}, allowed_tools=None,
                           _approve=Mock(), skills=None)


def jarvis_call(actions, tool, **arguments):
    from jarvis.tools import ToolRegistry
    step = dict(action='mcp_call', value='youtube', content=json.dumps({'name': tool, 'arguments': arguments}))
    return json.loads(ToolRegistry(actions).execute(step, lambda: False).evidence)


def test_offline_tool_through_jarvis_bridge(tmp_path):
    actions = bridge(tmp_path)
    result = jarvis_call(actions, 'parse_link', link='https://youtu.be/' + VID)
    assert result['structuredContent']['result']['video_id'] == VID and actions._approve.call_count == 1


def test_jarvis_refuses_invalid_arguments_before_the_connector(tmp_path):
    actions = bridge(tmp_path)
    for tool, arguments in [('search_videos', {'query': 'x', 'limit': 50}), ('search_videos', {'query': ''}),
                            ('video_details', {'video': VID, 'extra': 1})]:
        with pytest.raises(ValueError):
            jarvis_call(actions, tool, **arguments)
    # Jarvis approves the process first, then validates against the advertised schema before tools/call.
    assert actions._approve.call_count == 3


@pytest.mark.skipif(not LIVE, reason='live YouTube check; set JARVIS_LIVE_YOUTUBE=1')
def test_live_youtube_through_jarvis_bridge(tmp_path):
    actions = bridge(tmp_path)
    videos = jarvis_call(actions, 'search_videos', query='lofi hip hop', limit=10)['structuredContent']['result']
    assert videos and all(pages.VIDEO_ID.fullmatch(v['video_id']) for v in videos)
    playlists = jarvis_call(actions, 'search_playlists', query='lofi hip hop')['structuredContent']['result']
    assert playlists and playlists[0]['playlist_id']
    listing = jarvis_call(actions, 'playlist_videos', playlist=playlists[0]['playlist_id'], limit=15)
    assert listing['structuredContent']['result']['videos']
    details = jarvis_call(actions, 'video_details', video=videos[0]['video_id'])['structuredContent']['result']
    assert details['video_id'] == videos[0]['video_id'] and details['title']


def test_titles_are_nfkc_normalized_for_the_model_and_speech(youtube):
    use(youtube, {'https://www.youtube.com/results?': page({'contents': [video_renderer(VID, 'RAINING IN ＯＳＡＫＡ')]})})
    assert youtube.invoke('search_videos', {'query': 'osaka'})[0]['title'] == 'RAINING IN OSAKA'
