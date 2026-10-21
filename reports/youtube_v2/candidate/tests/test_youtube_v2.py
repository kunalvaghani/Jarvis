import asyncio
import ast
import importlib
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
from youtube_connector.youtube_v2 import YouTubeConnector,COMMAND_DESCRIPTIONS, CHANNEL_ID
from youtube_connector.base import ConnectorError,UnsupportedAction
from youtube_connector.data_api import YouTubeDataAPI

VID='dQw4w9WgXcQ'
PL='PL123456789abcdef'
CHANNEL='UC'+'a'*22

class CommandsTests(unittest.TestCase):
    def test_catalog_is_large_and_bound(self):
        self.assertEqual(len(COMMAND_DESCRIPTIONS),100)
        c=YouTubeConnector(page=object(),api_key='')
        for name in COMMAND_DESCRIPTIONS:
            with self.subTest(name=name):
                self.assertTrue(asyncio.iscoroutinefunction(getattr(c,name,None)))
    def test_generated_wrappers_complete(self):
        src=Path(__file__).resolve().parents[1]/'upstream_server.py'
        tree=ast.parse(src.read_text())
        names={node.name for node in tree.body if isinstance(node,ast.AsyncFunctionDef)}
        self.assertEqual(len(names),103)
        for method in COMMAND_DESCRIPTIONS:
            with self.subTest(method=method):self.assertIn('youtube_'+method,names)
        self.assertTrue({'youtube_next','youtube_previous','youtube_status'}<=names)
    def test_no_unsafe_generic_shell_tool(self):
        self.assertFalse({'youtube_execute_python','youtube_execute_js','youtube_run_shell'} & set(COMMAND_DESCRIPTIONS))
    def test_channel_id(self):
        self.assertIsNotNone(CHANNEL_ID.fullmatch(CHANNEL))

class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):self.c=YouTubeConnector(page=object(),api_key='')
    async def test_add_and_list(self):
        x=await self.c.queue_add(VID)
        self.assertEqual(x['size'],1)
        self.assertEqual((await self.c.queue_list())['videos'],[VID])
    async def test_reject_invalid_video(self):
        with self.assertRaises(ConnectorError):await self.c.queue_add('https://evil.test/watch?v='+VID)
    async def test_add_many_atomic_validation(self):
        with self.assertRaises(ConnectorError):await self.c.queue_add_many([VID,'wrong'])
        self.assertEqual((await self.c.queue_list())['size'],0)
    async def test_add_many_valid(self):
        self.assertEqual((await self.c.queue_add_many([VID,'A1234567890']))['size'],2)
    async def test_remove(self):
        await self.c.queue_add_many([VID,'A1234567890'])
        x=await self.c.queue_remove(0)
        self.assertEqual(x['removed'],VID)
    async def test_remove_invalid(self):
        with self.assertRaises(ConnectorError):await self.c.queue_remove(0)
    async def test_move(self):
        await self.c.queue_add_many([VID,'A1234567890'])
        self.assertEqual((await self.c.queue_move(0,1))['videos'][1],VID)
    async def test_repeat(self):
        x=await self.c.queue_set_repeat(True)
        self.assertTrue(x['repeat_queue'])
    async def test_repeat_requires_bool(self):
        with self.assertRaises(ConnectorError):await self.c.queue_set_repeat(1)
    async def test_shuffle(self):
        await self.c.queue_add_many([VID,'A1234567890'])
        x=await self.c.queue_set_shuffle(True)
        self.assertCountEqual(x['videos'],[VID,'A1234567890'])
    async def test_clear(self):
        await self.c.queue_add(VID)
        self.assertEqual((await self.c.queue_clear())['cleared'],1)
    async def test_empty_next(self):
        with self.assertRaises(ConnectorError):await self.c.queue_play_next()
    async def test_failed_navigation_preserves_queue(self):
        await self.c.queue_add(VID)
        self.c._navigate=AsyncMock(side_effect=ConnectorError('browser died'))
        with self.assertRaises(ConnectorError):await self.c.queue_play_next()
        self.assertEqual((await self.c.queue_list())['videos'],[VID])
    async def test_success_queue_play_state(self):
        self.c._page=type('P',(),{'url':'https://www.youtube.com/watch?v=A1234567890'})()
        self.c._navigate=AsyncMock()
        self.c._attempt_start_unlocked=AsyncMock(return_value=False)
        await self.c.queue_add(VID)
        x=await self.c.queue_play_next()
        self.assertTrue(x['opened'])
        self.assertFalse(x['playing_verified'])
        self.assertEqual(x['video_id'],VID)
    async def test_empty_previous(self):
        with self.assertRaises(ConnectorError):await self.c.queue_play_previous()

class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.c=YouTubeConnector(page=object(),api_key='')
        self.c._media=AsyncMock(return_value={'ok':True,'state':{'volume':40,'duration':180,'speed':1,'muted':False}})
    async def test_seek_bounds(self):
        for n in [-1,float('nan'),float('inf'),True,999999999]:
            with self.subTest(value=n),self.assertRaises(ConnectorError):await self.c.seek(n)
    async def test_volume_bounds(self):
        for n in [-1,101,float('nan'),'85']:
            with self.subTest(value=n),self.assertRaises(ConnectorError):await self.c.set_volume(n)
    async def test_speed_bounds(self):
        for n in [0,2.5,float('nan'),True]:
            with self.subTest(value=n),self.assertRaises(ConnectorError):await self.c.set_speed(n)
    async def test_set_volume_calls_correct(self):
        await self.c.set_volume(55)
        self.c._media.assert_awaited_with('volume',volume=55)
    async def test_volume_down(self):
        await self.c.volume_down(10)
        self.c._media.assert_awaited_with('volume',volume=30)
    async def test_volume_up(self):
        await self.c.volume_up(10)
        self.c._media.assert_awaited_with('volume',volume=50)
    async def test_seek_percent(self):
        await self.c.seek_percent(50)
        self.c._media.assert_awaited_with('seek',seconds=90)
    async def test_seek_percent_live_unsupported(self):
        self.c._media=AsyncMock(return_value={'state':{'duration':None}})
        with self.assertRaises(UnsupportedAction):await self.c.seek_percent(50)
    async def test_speed_up(self):
        await self.c.speed_up(.25)
        self.c._media.assert_awaited_with('speed_delta',delta=.25)
    async def test_speed_down(self):
        await self.c.speed_down(.25)
        self.c._media.assert_awaited_with('speed_delta',delta=-.25)
    async def test_skip_forward(self):
        await self.c.skip_forward(20)
        self.c._media.assert_awaited_with('seek_relative',seconds=20)
    async def test_skip_back(self):
        await self.c.skip_back(20)
        self.c._media.assert_awaited_with('seek_relative',seconds=-20)
    async def test_loop(self):
        await self.c.set_video_loop(True)
        self.c._media.assert_awaited_with('loop',enabled=True)
    async def test_ambiguous_result_rejected(self):
        self.c._search=AsyncMock(return_value={'results':[{'id':VID,'title':'Something totally different'},
                                                           {'id':'A1234567890','title':'Another unusual item'}]})
        with self.assertRaises(ConnectorError):await self.c._resolve('unknown request','video')
    async def test_exact_match_result_selected(self):
        self.c._search=AsyncMock(return_value={'results':[{'id':VID,'title':'hello music'},
                                                           {'id':'A1234567890','title':'other music'}]})
        self.assertEqual(await self.c._resolve('hello music','video'),VID)
    async def test_play_video_resolves_outside_lock(self):
        self.c._search=AsyncMock(return_value={'results':[{'id':VID,'title':'hello music'}]})
        self.c._navigate=AsyncMock()
        self.c._attempt_start_unlocked=AsyncMock(return_value=True)
        self.c._page=type('P',(),{'url':'https://www.youtube.com/watch?v='+VID})()
        x=await asyncio.wait_for(self.c.play_video('hello music'),timeout=.5)
        self.assertTrue(x['playing_verified'])
    async def test_bad_url_rejected(self):
        with self.assertRaises(ConnectorError):await self.c._resolve('https://evil.test/x','video')
    async def test_bad_host_for_dom(self):
        self.c._page=type('P',(),{'url':'https://example.com/'})()
        with self.assertRaises(UnsupportedAction):await self.c._dom('() => 1')

class APITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.c=YouTubeConnector(page=object(),api_key='test_api_key')
        self.c.data_api.request=AsyncMock(return_value={'items':[]})
    async def test_unapproved_mutations_blocked(self):
        operations=[('rate_video',(VID,'like')),('create_playlist',('Test',)),
                    ('update_playlist',(PL,'Name')),('delete_playlist',(PL,)),
                    ('add_video_to_playlist',(PL,VID)),('remove_playlist_item',('idAaaaaa',)),
                    ('subscribe_channel',(CHANNEL,)),('unsubscribe_channel',('idAaaaaa',)),
                    ('add_comment',(VID,CHANNEL,'comment')),('reply_comment',('idAaaaaa','reply')),
                    ('delete_my_comment',('idAaaaaa',))]
        for name,args in operations:
            with self.subTest(action=name),self.assertRaises(ConnectorError):
                await getattr(self.c,name)(*args)
        self.c.data_api.request.assert_not_called()
    async def test_approved_rate_uses_correct_path(self):
        self.c.approval_callback=AsyncMock(return_value=True)
        await self.c.rate_video(VID,'like')
        self.assertEqual(self.c.data_api.request.await_args.args[0],'videos/rate')
        self.assertEqual(self.c.data_api.request.await_args.kwargs['method'],'POST')
    async def test_api_details_read(self):
        await self.c.get_video_details(VID)
        self.assertEqual(self.c.data_api.request.await_args.args[0],'videos')
    async def test_api_comment_write_correct_structure(self):
        self.c.approval_callback=AsyncMock(return_value=True)
        await self.c.add_comment(VID,CHANNEL,'Great video!')
        body=self.c.data_api.request.await_args.kwargs['body']
        self.assertEqual(body['snippet']['topLevelComment']['snippet']['textOriginal'],'Great video!')
    async def test_playlist_create_private_by_default(self):
        self.c.approval_callback=AsyncMock(return_value=True)
        await self.c.create_playlist('My list')
        self.assertEqual(self.c.data_api.request.await_args.kwargs['body']['status']['privacyStatus'],'private')
    async def test_bad_rating(self):
        with self.assertRaises(ConnectorError):await self.c.rate_video(VID,'awesome')
    async def test_search_channels(self):
        await self.c.search_channels('Blender')
        self.assertEqual(self.c.data_api.request.await_args.kwargs['params']['type'],'channel')
    async def test_invalid_category_region(self):
        with self.assertRaises(ConnectorError):await self.c.get_video_categories('wrong')
    async def test_search_invalid_duration(self):
        with self.assertRaises(ConnectorError):await self.c.search_videos_filtered('music',video_duration='forever')
    async def test_no_oauth_for_private_read_is_not_claimed(self):
        await self.c.get_my_channel()
        self.assertTrue(self.c.data_api.request.await_args.kwargs['oauth'])

class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_reject_mutation_without_oauth(self):
        api=YouTubeDataAPI(key='abc')
        with self.assertRaises(ConnectorError):await api.request('playlists',method='POST',body={})
    async def test_reject_unlisted_endpoint(self):
        api=YouTubeDataAPI(key='abc')
        for target in ('https://evil.test','../../playlists','comments/insert','videos/rate/evil'):
            with self.subTest(endpoint=target),self.assertRaises(ConnectorError):
                await api.request(target)
    async def test_api_key_not_logging_error(self):
        api=YouTubeDataAPI(key='should_not_leak')
        with patch.object(YouTubeDataAPI,'_fetch',side_effect=ConnectorError('no connection')):
            with self.assertRaises(ConnectorError) as cm:await api.request('videos',params={'part':'snippet','id':VID})
        self.assertNotIn('should_not_leak',str(cm.exception))
    async def test_approved_api_url_does_not_contain_token(self):
        api=YouTubeDataAPI(key='abc',token='secret')
        with patch.object(YouTubeDataAPI,'_fetch',return_value={'ok':True}) as fetch:
            await api.request('videos/rate',method='POST',params={'id':VID,'rating':'like'},oauth=True)
            self.assertNotIn('secret',fetch.call_args.args[0])
            self.assertEqual(fetch.call_args.kwargs['token'],'secret')

if __name__=='__main__':unittest.main()

class SearchFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_failure_falls_back_with_reason(self):
        c=YouTubeConnector(page=object(),api_key='api_key')
        c._api_search_sync=lambda *args:(_ for _ in ()).throw(ConnectorError('quota exceeded'))
        c._browser_search=AsyncMock(return_value=[{'id':VID,'title':'video'}])
        result=await c.search_videos('something')
        self.assertEqual(result['source'],'youtube_browser')
        self.assertEqual(result['api_fallback_reason'],'quota exceeded')
    async def test_api_success_does_not_touch_browser(self):
        c=YouTubeConnector(page=object(),api_key='api_key')
        c._api_search_sync=lambda *args:[{'id':VID,'title':'video'}]
        c._browser_search=AsyncMock()
        result=await c.search_videos('something')
        self.assertEqual(result['source'],'youtube_data_api')
        c._browser_search.assert_not_called()
    async def test_no_api_uses_browser(self):
        c=YouTubeConnector(page=object(),api_key='')
        c._browser_search=AsyncMock(return_value=[])
        self.assertEqual((await c.search_playlists('music'))['source'],'youtube_browser')
    async def test_search_too_many_results(self):
        c=YouTubeConnector(page=object(),api_key='')
        with self.assertRaises(ConnectorError):await c.search_videos('music',50)
    async def test_temp_search_closes_tab_and_keeps_original(self):
        from unittest.mock import AsyncMock
        c=YouTubeConnector(page=object(),api_key='')
        page=object()
        tab=type('T',(),{})()
        tab.close=AsyncMock()
        ctx=type('CTX',(),{})()
        ctx.new_page=AsyncMock(return_value=tab)
        c._context=ctx
        c._page=page
        with patch('youtube_connector.youtube.YouTubeConnector._browser_search',new=AsyncMock(return_value=[])):
            await c._browser_search('music','video',5)
        self.assertIs(c._page,page)
        tab.close.assert_awaited_once()
    async def test_temp_tab_closed_after_error(self):
        c=YouTubeConnector(page=object(),api_key='')
        page=object()
        tab=type('T',(),{})()
        tab.close=AsyncMock()
        ctx=type('CTX',(),{})();ctx.new_page=AsyncMock(return_value=tab)
        c._context=ctx;c._page=page
        with patch('youtube_connector.youtube.YouTubeConnector._browser_search',new=AsyncMock(side_effect=ConnectorError('oops'))):
            with self.assertRaises(ConnectorError):await c._browser_search('music','video',5)
        self.assertIs(c._page,page)
        tab.close.assert_awaited_once()
