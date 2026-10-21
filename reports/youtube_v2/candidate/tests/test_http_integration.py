"""Real localhost HTTP transport regression (not a YouTube live network test)."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from youtube_connector.data_api import YouTubeDataAPI
from youtube_connector.base import ConnectorError

class Handler(BaseHTTPRequestHandler):
    calls=[]
    def log_message(self,*args):pass
    def do_GET(self):
        Handler.calls.append(('GET',self.path,self.headers.get('Authorization')))
        if self.path.startswith('/v3/videos') and 'id=forbidden' in self.path:
            self.send_response(403)
            self.send_header('Content-Type','application/json')
            self.end_headers();self.wfile.write(b'{"error":{"message":"forbidden"}}');return
        b=json.dumps({'items':[{'id':'dQw4w9WgXcQ'}],'path':self.path}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json')
        self.end_headers();self.wfile.write(b)
    def do_POST(self):
        size=int(self.headers.get('Content-Length','0'))
        body=self.rfile.read(size).decode() if size else ''
        Handler.calls.append(('POST',self.path,self.headers.get('Authorization'),body))
        self.send_response(204)
        self.end_headers()

class RealHTTPTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_address[1]}/v3/'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=5)
    def setUp(self):Handler.calls.clear()
    async def test_real_http_get_query_encoding(self):
        api=YouTubeDataAPI(key='test-key')
        with patch('youtube_connector.data_api.YT_BASE',self.base):
            res=await api.request('videos',params={'part':'snippet','id':'dQw4w9WgXcQ'})
        self.assertEqual(res['items'][0]['id'],'dQw4w9WgXcQ')
        parsed=parse_qs(urlparse(Handler.calls[0][1]).query)
        self.assertEqual(parsed['key'],['test-key'])
        self.assertEqual(parsed['part'],['snippet'])
    async def test_real_http_oauth_post_no_key_in_url(self):
        api=YouTubeDataAPI(key='test-key',token='fake_token')
        with patch('youtube_connector.data_api.YT_BASE',self.base):
            res=await api.request('videos/rate',method='POST',params={'id':'dQw4w9WgXcQ','rating':'like'},oauth=True)
        self.assertTrue(res['ok'])
        self.assertEqual(Handler.calls[0][2],'Bearer fake_token')
        self.assertNotIn('key=',Handler.calls[0][1])
    async def test_real_http_error_no_false_success(self):
        api=YouTubeDataAPI(key='test-key')
        with patch('youtube_connector.data_api.YT_BASE',self.base):
            with self.assertRaisesRegex(ConnectorError,'HTTP 403'):
                await api.request('videos',params={'part':'snippet','id':'forbidden'})
