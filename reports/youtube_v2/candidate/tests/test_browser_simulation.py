"""DOM-level state simulation tests; these DO NOT substitute for live YouTube E2E."""
import asyncio
import unittest
from unittest.mock import AsyncMock
from youtube_connector.youtube_v2 import YouTubeConnector
from youtube_connector.base import UnsupportedAction

class SimulatedPage:
    url='https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    def __init__(self):
        self.state={'paused':False,'seconds':10.0,'duration':180.0,'volume':50,
                    'muted':False,'speed':1.0,'loop':False,'ended':False,'ready_state':4,'title':'Song'}
    async def evaluate(self, js, data=None):
        if not isinstance(data,dict):return self.state.copy()
        action=data['action'];v=data['values'];s=self.state
        if action=='seek':s['seconds']=min(float(s['duration']),max(0,float(v['seconds'])))
        elif action=='seek_relative':s['seconds']=min(float(s['duration']),max(0,s['seconds']+float(v['seconds'])))
        elif action=='volume':s['volume']=round(float(v['volume']))
        elif action=='mute':s['muted']=True
        elif action=='unmute':s['muted']=False
        elif action=='toggle_mute':s['muted']=not s['muted']
        elif action=='speed':s['speed']=float(v['rate'])
        elif action=='speed_delta':s['speed']=min(2,max(.25,s['speed']+float(v['delta'])))
        elif action=='loop':s['loop']=bool(v['enabled'])
        elif action=='pause':s['paused']=True
        elif action=='play':s['paused']=False
        return {'ok':True,**s}

class DOMSimulationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.page=SimulatedPage()
        self.c=YouTubeConnector(page=self.page,api_key='')
    async def test_seek_readback(self):
        self.assertEqual((await self.c.seek(30))['state']['seconds'],30)
        self.assertEqual((await self.c.skip_forward(10))['state']['seconds'],40)
        self.assertEqual((await self.c.skip_back(45))['state']['seconds'],0)
    async def test_media_volume(self):
        await self.c.set_volume(90)
        self.assertEqual((await self.c.volume_up(40))['state']['volume'],100)
        self.assertEqual((await self.c.volume_down(40))['state']['volume'],60)
    async def test_media_speed(self):
        await self.c.set_speed(1.5)
        self.assertEqual((await self.c.speed_up(.5))['state']['speed'],2)
        self.assertEqual((await self.c.speed_down(1))['state']['speed'],1)
    async def test_media_mute(self):
        self.assertTrue((await self.c.mute())['state']['muted'])
        self.assertFalse((await self.c.toggle_mute())['state']['muted'])
    async def test_media_loop(self):
        self.assertTrue((await self.c.set_video_loop(True))['state']['loop'])
    async def test_state_does_not_auto_succeed_if_media_missing(self):
        p=SimulatedPage()
        async def reject(js,data=None):return {'ok':False,'reason':'no_video'}
        p.evaluate=reject
        c=YouTubeConnector(page=p,api_key='')
        with self.assertRaisesRegex(UnsupportedAction,'no_video'):
            await c.set_volume(50)
    async def test_concurrent_volume_operations_are_serialized(self):
        # In a real browser the Playwright page is single-threaded; explicit lock
        # ensures each read-modify-write is atomic from Jarvis's perspective.
        await asyncio.wait_for(asyncio.gather(*[self.c.volume_up(5) for _ in range(10)]),2)
        self.assertEqual(self.page.state['volume'],100)
