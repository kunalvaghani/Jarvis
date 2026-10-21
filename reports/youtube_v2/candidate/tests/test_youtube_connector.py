import unittest
from unittest.mock import AsyncMock
from youtube_connector.base import ConnectorError, UnsupportedAction
from youtube_connector.youtube import YouTubeConnector, extract_id, youtube_watch_url


class IdentifierTests(unittest.TestCase):
    def test_video_id(self):
        self.assertEqual(extract_id('dQw4w9WgXcQ', 'video'), 'dQw4w9WgXcQ')

    def test_watch_url(self):
        self.assertEqual(extract_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=2', 'video'), 'dQw4w9WgXcQ')

    def test_shorts_url(self):
        self.assertEqual(extract_id('https://www.youtube.com/shorts/dQw4w9WgXcQ', 'video'), 'dQw4w9WgXcQ')

    def test_youtu_be(self):
        self.assertEqual(extract_id('https://youtu.be/dQw4w9WgXcQ', 'video'), 'dQw4w9WgXcQ')

    def test_playlist_id_from_watch(self):
        self.assertEqual(extract_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123456789abc', 'playlist'), 'PL123456789abc')

    def test_reject_fake_youtube_hosts(self):
        self.assertIsNone(extract_id('https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ', 'video'))

    def test_playlist_url_wrong_path(self):
        self.assertIsNone(extract_id('https://www.youtube.com/evil?list=PL123456789abc', 'playlist'))

    def test_reject_non_https(self):
        self.assertIsNone(extract_id('http://www.youtube.com/watch?v=dQw4w9WgXcQ', 'video'))

    def test_reject_other_sites(self):
        self.assertIsNone(extract_id('https://example.org/watch?v=dQw4w9WgXcQ', 'video'))

    def test_build_watch_url(self):
        self.assertEqual(youtube_watch_url('dQw4w9WgXcQ', 'PL123456789abc'),
                         'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123456789abc')


class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_capabilities(self):
        c = YouTubeConnector(page=object())
        self.assertIn('search_playlists', c.info.capabilities)
        self.assertIn('previous_video', c.info.capabilities)

    async def test_health_without_api_key(self):
        c = YouTubeConnector(page=object(), api_key='')
        self.assertFalse((await c.health())['api_search_enabled'])

    async def test_blank_search_rejected(self):
        c = YouTubeConnector(page=object(), api_key='')
        with self.assertRaises(ConnectorError):
            await c.search_videos('')

    async def test_invalid_limit_rejected(self):
        c = YouTubeConnector(page=object(), api_key='')
        with self.assertRaises(ConnectorError):
            await c.search_playlists('Blender', 100)

    async def test_play_id_invokes_safe_url(self):
        c = YouTubeConnector(page=type('P', (), {'url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})(), api_key='')
        c._navigate = AsyncMock()
        c._attempt_start_unlocked = AsyncMock(return_value=True)
        result = await c.play_video('dQw4w9WgXcQ')
        c._navigate.assert_awaited_once_with('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        self.assertTrue(result['ok'])
        self.assertTrue(result['playing_verified'])

    async def test_opened_without_playback_is_explicit(self):
        c = YouTubeConnector(page=type('P', (), {'url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})(), api_key='')
        c._navigate = AsyncMock()
        c._attempt_start_unlocked = AsyncMock(return_value=False)
        result = await c.play_video('dQw4w9WgXcQ')
        self.assertTrue(result['opened'])
        self.assertFalse(result['playing_verified'])

    async def test_other_host_link_rejected(self):
        c = YouTubeConnector(page=object(), api_key='')
        with self.assertRaises(ConnectorError):
            await c.play_video('https://evil.example/watch?v=dQw4w9WgXcQ')

    async def test_previous_outside_playlist_rejected(self):
        page = type('P', (), {'url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})()
        c = YouTubeConnector(page=page, api_key='')
        c._video_state = AsyncMock(return_value={'paused':False,'current_time':40})
        with self.assertRaises(UnsupportedAction):
            await c.previous_video()

    async def test_pause_when_already_paused_no_click(self):
        page = type('P', (), {'url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})()
        c = YouTubeConnector(page=page, api_key='')
        c._video_state = AsyncMock(return_value={'paused':True,'current_time':12})
        result = await c.pause()
        self.assertTrue(result['paused'])

    async def test_invalid_playlist_link_not_accepted(self):
        c = YouTubeConnector(page=object(), api_key='')
        with self.assertRaises(ConnectorError):
            await c.play_playlist('https://www.youtube.com/evil?list=bad')


if __name__ == '__main__':
    unittest.main()
