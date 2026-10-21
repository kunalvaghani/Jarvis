"""Opt-in real YouTube test. FAIL if playback can't be verified; no false success.

Requires: YOUTUBE_LIVE_TESTS=1, Chromium installed, interactive desktop,
YouTube reachable, cookies/consent configured. Avoid running in CI by default.
"""
import os
import unittest
from youtube_connector.youtube_v2 import YouTubeConnector
from youtube_connector.base import ConnectorError,UnsupportedAction

@unittest.skipUnless(os.environ.get('YOUTUBE_LIVE_TESTS')=='1','Requires explicit interactive YouTube live test')
class LiveYouTubeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.c=YouTubeConnector(api_key='')
        await self.c.connect()
    async def asyncTearDown(self):await self.c.close()
    async def test_real_watch_play_pause_seek_volume_speed_reload(self):
        # Public representative video; if blocked by consent/ads this FAILS (not a pass).
        from youtube_connector.youtube import youtube_watch_url
        vid='dQw4w9WgXcQ'
        opened=await self.c.play_video(vid)
        self.assertEqual(opened['video_id'],vid)
        self.assertTrue(opened['playing_verified'],'Video must actually start. Investigate login/consent/autoplay if it did not.')
        status=await self.c.get_status()
        self.assertTrue(status['video_loaded'])
        self.assertFalse(status['paused'])
        self.assertTrue((await self.c.pause())['paused'])
        await self.c.seek(5)
        at=await self.c.get_playback_time()
        self.assertGreaterEqual(at['seconds'],0)
        await self.c.set_volume(35)
        self.assertEqual((await self.c.get_volume())['volume'],35)
        await self.c.set_speed(1.25)
        self.assertAlmostEqual((await self.c.get_speed())['speed'],1.25)
        self.assertFalse((await self.c.resume())['paused'])
        await self.c.browser_reload()
        self.assertTrue((await self.c.get_status())['video_loaded'])
