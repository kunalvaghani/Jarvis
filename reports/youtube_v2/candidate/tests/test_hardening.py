"""Additional safety contracts. Mocks do not count as live acceptance."""
import asyncio
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock, patch
from urllib.error import HTTPError

from youtube_connector.base import ConnectorError
from youtube_connector.youtube import extract_id
from youtube_connector.youtube_v2 import YouTubeConnector
from youtube_connector.data_api import YouTubeDataAPI, NoRedirect

VID = 'aqz-KE-bpKQ'


class HardeningTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_not_consumed_when_playback_unverified(self):
        c = YouTubeConnector(page=object(), api_key='')
        c._navigate = AsyncMock()
        c._attempt_start_unlocked = AsyncMock(return_value=False)
        await c.queue_add(VID)
        self.assertEqual((await c.queue_play_next())['outcome'], 'opened_only')
        self.assertEqual(list(c._queue), [VID])

    async def test_previous_history_survives_navigation_and_playback_failure(self):
        c = YouTubeConnector(page=object(), api_key='')
        c._history.append(VID)
        c._navigate = AsyncMock(side_effect=ConnectorError('navigation uncertain'))
        with self.assertRaises(ConnectorError):
            await c.queue_play_previous()
        self.assertEqual(list(c._history), [VID])
        c._navigate = AsyncMock()
        c._attempt_start_unlocked = AsyncMock(return_value=False)
        await c.queue_play_previous()
        self.assertEqual(list(c._history), [VID])

    async def test_uncertain_play_has_no_click_fallback(self):
        page = Mock(url='https://www.youtube.com/watch?v='+VID)
        c = YouTubeConnector(page=page, api_key='')
        c._video_state = AsyncMock(return_value={'paused':True})
        c._media = AsyncMock(side_effect=ConnectorError('uncertain'))
        with self.assertRaises(ConnectorError):
            await c.resume()
        page.locator.assert_not_called()

    async def test_uncertain_click_not_repeated_on_second_selector(self):
        page = Mock(url='https://www.youtube.com/watch?v='+VID)
        locator = Mock()
        locator.is_visible = AsyncMock(return_value=True)
        locator.click = AsyncMock(side_effect=RuntimeError('timeout after input'))
        page.locator.return_value.first = locator
        c = YouTubeConnector(page=page, api_key='')
        with self.assertRaises(RuntimeError):
            await c._click_control(('one','two'), 'test')
        self.assertEqual(page.locator.call_count, 1)
        self.assertEqual(locator.click.await_count, 1)

    async def test_resource_allowlist_blocks_undocumented_endpoints(self):
        api = YouTubeDataAPI(key='fake')
        for resource in ['innertube', 'privateEndpoint', '../videos', 'videos?key=x']:
            with self.subTest(resource=resource), self.assertRaises(ConnectorError):
                await api.request(resource)


class TransportTests(unittest.TestCase):
    def test_url_authority_and_embed(self):
        for prefix in ['https://user@youtube.com', 'https://youtube.com:444', 'https://youtube.com:bad']:
            self.assertIsNone(extract_id(prefix+'/watch?v='+VID, 'video'))
        self.assertEqual(extract_id('https://www.youtube.com/embed/'+VID, 'video'), VID)

    def test_http_failures_are_classified_without_reflecting_credentials(self):
        for status in [400,401,403,404,429,500]:
            body = json.dumps({'error': {'message':'secret-reflection', 'errors':[
                {'reason':'quotaExceeded' if status==403 else 'unknown'}]}}).encode()
            exc = HTTPError('https://www.googleapis.com/?key=secret', status, 'x', {}, BytesIO(body))
            opener = Mock()
            opener.open.side_effect = exc
            with self.subTest(status=status), patch('youtube_connector.data_api.build_opener', return_value=opener):
                with self.assertRaises(ConnectorError) as caught:
                    YouTubeDataAPI._fetch('https://www.googleapis.com/youtube/v3/videos')
                self.assertIn('HTTP '+str(status), str(caught.exception))
                self.assertNotIn('secret', str(caught.exception))
                if status == 403:
                    self.assertIn('quota_exhausted', str(caught.exception))

    def test_redirect_refuses_credential_forwarding(self):
        with self.assertRaises(ConnectorError):
            NoRedirect().redirect_request(None,None,302,'',{},'https://evil.test')

    def test_explicit_token_path_does_not_need_home(self):
        with patch.object(Path, 'home', side_effect=RuntimeError('no home')):
            api = YouTubeDataAPI(token_path='explicit-test-token.json')
        self.assertEqual(api.token_path, Path('explicit-test-token.json'))


class ActualParentTests(unittest.TestCase):
    def test_all_108_typed_handlers_validate_and_delegate_once(self):
        src = Path(__file__).resolve().parents[1]/'server.py'
        spec = importlib.util.spec_from_file_location('youtube_actual_parent_test', src)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(Path, 'home', side_effect=RuntimeError('MCP home unavailable')):
            c = module.YouTubeConnector(allow_write=True)
        try:
            catalog = c.describe()
            self.assertEqual(len(catalog),108)
            self.assertEqual(len({r['name'] for r in catalog}),108)
            old = {'search_videos','search_playlists','video_details','playlist_videos','parse_link'}
            for row in catalog:
                if row['name'] in old:
                    continue
                args = {}
                for key in row['inputSchema'].get('required', []):
                    kind = row['inputSchema']['properties'][key]['type']
                    args[key] = {'string':'test','number':1.0,'integer':1,'boolean':True,'array':[VID]}[kind]
                with self.subTest(name=row['name']):
                    c.dispatch = Mock(return_value={'ok':True})
                    self.assertFalse(c.call(row['name'], args)['isError'])
                    c.dispatch.assert_called_once()
                    self.assertTrue(c.call(row['name'], dict(args, approved=True))['isError'])
                    self.assertEqual(c.dispatch.call_count,1)
        finally:
            c.close_service()

    def test_default_page_is_not_opened_by_candidate(self):
        src = Path(__file__).resolve().parents[1]/'server.py'
        spec = importlib.util.spec_from_file_location('youtube_actual_parent_refusal', src)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        c = module.YouTubeConnector(allow_write=True)
        try:
            result = c.call('youtube_pause', {})
            self.assertTrue(result['isError'])
            self.assertIn('Default profile only', result['content'][0]['text'])
        finally:
            c.close_service()
