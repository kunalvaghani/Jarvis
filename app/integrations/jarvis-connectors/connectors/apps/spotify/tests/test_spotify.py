"""Offline tests. No Spotify account, network, or Windows hardware needed."""
import asyncio
import inspect
import json
import random
import string
import sys
import types
import unittest
from unittest.mock import patch,AsyncMock
from spotify_connector.base import ConnectorError, UnsupportedAction, BaseConnector
from spotify_connector.identifiers import spotify_uri,resource_id,uri_list,bounded
from spotify_connector.spotify import SpotifyConnector
from spotify_connector.windows_media import WindowsSpotify
from spotify_connector.auth import PKCETokenManager,pkce_pair,authorization_url,redirect_uri
from spotify_connector.api import SpotifyAPI,SpotifyAPIError

ID1='4iV5W9uYEdYUVa79Axb7Rh'
ID2='3n3Ppam7vgaVa1iaRUc9Lp'
T='spotify:track:'+ID1
P='spotify:playlist:'+ID1
E='spotify:episode:'+ID2

class FakeTokens:
    client_id='fake'
    def __init__(self, authenticated=True):self.enabled=authenticated;self.refreshed=0
    def authenticated(self):return self.enabled
    def access_token(self):return 'test_secret_token'
    def refresh_after_401(self):self.refreshed+=1;return 'new_secret_token'

class FakeAPI:
    def __init__(self):self.calls=[];self.response={};self.exception=None
    async def request(self,method,path,params=None,json_body=None):
        self.calls.append((method,path,params,json_body))
        if self.exception:raise self.exception
        if method == 'GET' and path == '/me/player/devices': return {'devices':[{'id':value,'is_active':True,'is_restricted':False} for value in ('dev-123456','device-123456')]}
        if method == 'GET' and path == '/me': return {'id':'fixture-owner'}
        if method == 'GET' and path.startswith('/playlists/'): return {'owner':{'id':'fixture-owner'}, 'public':False}
        return self.response

class FakeWindows:
    def __init__(self):self.calls=[]
    async def action(self,name,value=None):self.calls.append(('action',name,value));return {'ok':True,'source':'windows_gsmtc','accepted':True}
    async def open(self,value=None):self.calls.append(('open',value));return {'ok':True,'playing_verified':False}
    async def search(self,query):self.calls.append(('search',query));return {'ok':True,'results_extracted':False}
    async def status(self):self.calls.append(('status',));return {'ok':True,'position_ms':5000}

class IdentifierTests(unittest.TestCase):
    def test_valid_spotify_ids_for_all_kinds(self):
        for kind in ['track','album','artist','playlist','episode','show','audiobook','chapter']:
            uri=f'spotify:{kind}:{ID1}'
            with self.subTest(kind=kind):
                self.assertEqual(spotify_uri(uri),uri)
                self.assertEqual(spotify_uri(f'https://open.spotify.com/{kind}/{ID1}?si=test'),uri)
                self.assertEqual(resource_id(uri,kind),ID1)
                self.assertEqual(resource_id(ID1,kind),ID1)
                self.assertEqual(spotify_uri(f'https://open.spotify.com/intl-en/{kind}/{ID1}'),uri)
    def test_malicious_urls_and_malformed(self):
        bad=['','x','http://open.spotify.com/track/'+ID1,'https://evil.com/track/'+ID1,
             'https://open.spotify.com.evil.com/track/'+ID1,
             'https://open.spotify.com@evil.com/track/'+ID1,
             'https://evil.com@open.spotify.com/track/'+ID1,
             'https://open.spotify.com:99/track/'+ID1,
             'https://open.spotify.com:bad/track/'+ID1,
             'https://open.spotify.com/%2e%2e/track/'+ID1,
             'spotify:track:../../secrets', 'spotify:track:'+ID1+':x',
             'spotify:search:hello','file://open.spotify.com/track/'+ID1,'https://open.spotify.com/',
             'https://open.spotify.com/track/'+ID1+'abc',
             'javascript:alert(1)', 'https://open.spotify.com/track/%00'+ID1,
             'https://open.spotify.com/track/'+ID1+'/more']
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ConnectorError):spotify_uri(value)
    def test_batch_rejections(self):
        for value in ([],[T]*101, 'str',[E], [T, 'https://bad.example/track/'+ID1]):
            with self.subTest(value=str(value)[:30]):
                with self.assertRaises(ConnectorError):uri_list(value,{'track'})
    def test_limit_bool_rejected(self):
        for x in (True,False,-1,201,4.0,None):
            with self.assertRaises(ConnectorError):bounded(x,'n',1,200)
    def test_fuzz_random_identifiers_fail_closed(self):
        rng=random.Random(2001)
        for _ in range(300):
            v=''.join(rng.choice(string.ascii_letters+'/?:$@!.\\-') for _ in range(rng.randint(1,42)))
            with self.subTest(v=v):
                with self.assertRaises(ConnectorError):spotify_uri(v)

class APIRequests(unittest.IsolatedAsyncioTestCase):
    async def test_api_json_success_empty_success(self):
        calls=[]
        def transport(method,url,body,token,timeout):
            calls.append((method,url,body,token,timeout));return 204,None
        api=SpotifyAPI(FakeTokens(),transport)
        r=await api.request('PUT','/me/player/volume',params={'volume_percent':25},json_body={'anything':True})
        self.assertIsNone(r);self.assertTrue(calls[0][1].startswith('https://api.spotify.com/v1/me/player/volume?'))
        self.assertEqual(json.loads(calls[0][2]),{'anything':True})
    async def test_host_override_and_path_rejected(self):
        api=SpotifyAPI(FakeTokens(),lambda *args:self.fail('request should not occur'))
        for path in ('https://attacker.com/x','//attacker.com','/../admin','/me?token=x','/../me','/me\\fake','me/player'):
            with self.subTest(path=path):
                with self.assertRaises(ConnectorError):await api.request('GET',path)
        with self.assertRaises(ConnectorError):await api.request('PATCH','/me/player')
    async def test_refresh_once_on_401(self):
        token=FakeTokens(); calls=[]
        def transport(m,u,b,t,timeout):
            calls.append(t)
            if len(calls)==1:raise SpotifyAPIError(401,'anything')
            return 204,None
        api=SpotifyAPI(token,transport)
        await api.request('PUT','/me/player/pause')
        self.assertEqual(calls,['test_secret_token','new_secret_token']);self.assertEqual(token.refreshed,1)
    async def test_forbidden_does_not_fallback(self):
        token=FakeTokens(); windows=FakeWindows(); api=FakeAPI();api.exception=SpotifyAPIError(403,'test')
        connector=SpotifyConnector(api=api,windows=windows,token_manager=token)
        with self.assertRaises(SpotifyAPIError):await connector.pause()
        self.assertFalse(windows.calls)
    async def test_no_retry_mutating_429(self):
        calls=[]
        def transport(*args):calls.append(args);raise SpotifyAPIError(429,'rate',retry_after=0)
        with self.assertRaises(SpotifyAPIError):await SpotifyAPI(FakeTokens(),transport).request('POST','/me/player/next')
        self.assertEqual(len(calls),1)
    async def test_retry_get_429_once(self):
        calls=[]
        def transport(*args):
            calls.append(args)
            if len(calls)==1:raise SpotifyAPIError(429,'rate',retry_after=0)
            return 200, {'ok':True}
        result=await SpotifyAPI(FakeTokens(),transport).request('GET','/me')
        self.assertEqual(result,{'ok':True});self.assertEqual(len(calls),2)
    def test_error_does_not_include_secrets(self):
        e=SpotifyAPIError(401,'Bearer secret123');self.assertNotIn('secret123',str(e))
        e=SpotifyAPIError(403,'Bearer secret123');self.assertNotIn('secret123',str(e))

class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.api=FakeAPI();self.win=FakeWindows();self.tokens=FakeTokens()
        self.c=SpotifyConnector(api=self.api,windows=self.win,token_manager=self.tokens)
    async def test_parent_contract_and_info(self):
        from server import SpotifyConnector as ProductionConnector
        self.assertIsInstance(ProductionConnector(),BaseConnector)
        self.assertEqual(self.c.info.namespace,'spotify')
        self.assertGreaterEqual(len(self.c.info.capabilities),75)
        for name in self.c.info.capabilities:
            self.assertTrue(callable(getattr(self.c,name)))
        result=await self.c.health();self.assertTrue(result['api_authorized'])
    async def test_play_commands_payloads_and_safe_targeting(self):
        await self.c.play_track(ID1)
        self.assertEqual(self.api.calls[-1][:2],('PUT','/me/player/play'))
        self.assertEqual(self.api.calls[-1][-1],{'uris':[T]})
        await self.c.play_playlist(P,'dev-123456',offset=4)
        self.assertEqual(self.api.calls[-1][-1],{'context_uri':P,'offset':{'position':4}})
        self.assertEqual(self.api.calls[-1][2],{'device_id':'dev-123456'})
        await self.c.play_episode(E)
        self.assertEqual(self.api.calls[-1][-1]['uris'],[E])
        for kind in ('album','artist'):
            await getattr(self.c,'play_'+kind)(f'spotify:{kind}:{ID1}')
            self.assertEqual(self.api.calls[-1][-1]['context_uri'],f'spotify:{kind}:{ID1}')
    async def test_playback_operations_paths_2026(self):
        operations=[('pause',(), 'PUT','/me/player/pause'),('resume',(),'PUT','/me/player/play'),
                    ('next',(),'POST','/me/player/next'),('previous',(),'POST','/me/player/previous'),
                    ('seek',(5000,),'PUT','/me/player/seek'),('volume',(50,),'PUT','/me/player/volume'),
                    ('shuffle',(True,),'PUT','/me/player/shuffle'),('repeat',('track',),'PUT','/me/player/repeat'),
                    ('transfer',('device-123456',),'PUT','/me/player'),('add_to_queue',(T,),'POST','/me/player/queue')]
        for name,args,verb,path in operations:
            with self.subTest(command=name):
                result=await getattr(self.c,name)(*args)
                self.assertTrue(result['accepted']);self.assertIsNone(result['verified'])
                self.assertEqual(self.api.calls[-1][:2],(verb,path))
    async def test_no_api_fallback_only_subset(self):
        self.tokens.enabled=False
        for name,expected in [('pause','pause'),('resume','play'),('next','next'),('previous','previous')]:
            await getattr(self.c,name)();self.assertEqual(self.win.calls[-1][1],expected)
        await self.c.play_track(ID1);self.assertEqual(self.win.calls[-1],('open',T))
        await self.c.repeat('track');self.assertEqual(self.win.calls[-1],('action','repeat','track'))
        for name, args in [('volume',(50,)),('repeat',('track','device-123456'))]:
            with self.assertRaises(ConnectorError):await getattr(self.c,name)(*args)
    async def test_no_api_status(self):
        self.tokens.enabled=False
        out=await self.c.status();self.assertEqual(out['position_ms'],5000)
    async def test_get_reads_2026(self):
        cases=[('get_track',(T,),'/tracks/'+ID1),('get_album',('spotify:album:'+ID1,),'/albums/'+ID1),
               ('get_artist',('spotify:artist:'+ID1,),'/artists/'+ID1),('get_playlist',(P,),'/playlists/'+ID1),
               ('get_episode',(E,),'/episodes/'+ID2),('get_show',('spotify:show:'+ID1,),'/shows/'+ID1),
               ('playlist_items',(P,),'/playlists/'+ID1+'/items'),('my_playlists',(),'/me/playlists'),
               ('saved_tracks',(),'/me/tracks'),('saved_albums',(),'/me/albums'),
               ('get_profile',(),'/me')]
        for method,args,path in cases:
            with self.subTest(method=method):
                await getattr(self.c,method)(*args)
                self.assertEqual(self.api.calls[-1][1],path)
    async def test_search_limit_2026_and_validation(self):
        await self.c.search('bollywood','track',10,3)
        self.assertEqual(self.api.calls[-1][2],{'q':'bollywood','type':'track','limit':10,'offset':3})
        for limit in (0,11,-5,True):
            with self.assertRaises(ConnectorError):await self.c.search('songs','track',limit)
        for query in ('',' '*10):
            with self.assertRaises(ConnectorError):await self.c.search(query)
    async def test_playlist_current_paths_and_write_payload(self):
        await self.c.create_playlist('Evening mix',False,'Chill songs')
        self.assertEqual(self.api.calls[-1][1],'/me/playlists')
        await self.c.add_playlist_items(P,[T,E])
        self.assertEqual(self.api.calls[-1][1],f'/playlists/{ID1}/items')
        self.assertEqual(self.api.calls[-1][-1]['uris'],[T,E])
        await self.c.remove_playlist_items(P,[T])
        self.assertEqual(self.api.calls[-1][-1]['items'],[{'uri':T}])
        await self.c.reorder_playlist_items(P,1,4,1,'snapshot2')
        self.assertEqual(self.api.calls[-1][-1]['snapshot_id'],'snapshot2')
        await self.c.replace_playlist_items(P,[])
        self.assertEqual(self.api.calls[-1][-1],{'uris':[]})
    async def test_playlist_write_invalid_never_hits_api(self):
        for name,args in [('add_playlist_items',(P,['https://bad.example/track/'+ID1],)),
                          ('remove_playlist_items',(P,[])),('reorder_playlist_items',(P,-1,5)),
                          ('create_playlist',('',)),('update_playlist',(P,)),
                          ('replace_playlist_items',(P,[T]*101))]:
            self.api.calls.clear()
            with self.subTest(method=name):
                with self.assertRaises(ConnectorError):await getattr(self.c,name)(*args)
                self.assertFalse(self.api.calls)
    async def test_library_generic_new_endpoints(self):
        await self.c.save_items([T,'spotify:album:'+ID1])
        self.assertEqual(self.api.calls[-1][:2],('PUT','/me/library'))
        self.assertEqual(self.api.calls[-1][2]['uris'],T+',spotify:album:'+ID1)
        self.assertIsNone(self.api.calls[-1][3])
        await self.c.remove_saved_items([T])
        self.assertEqual(self.api.calls[-1][:2],('DELETE','/me/library'))
        self.assertEqual(self.api.calls[-1][2]['uris'],T)
        await self.c.contains_saved([T])
        self.assertEqual(self.api.calls[-1][:2],('GET','/me/library/contains'))
    async def test_seek_relative_bounds(self):
        self.api.response={'progress_ms':5000,'item':{'duration_ms':15000}}
        await self.c.seek_relative(-100000)
        self.assertEqual(self.api.calls[-1][2]['position_ms'],0)
        await self.c.seek_relative(100000)
        self.assertEqual(self.api.calls[-1][2]['position_ms'],14999)
    async def test_volume_relative_bounds(self):
        self.api.response={'device':{'volume_percent':95}}
        await self.c.volume_relative(20)
        self.assertEqual(self.api.calls[-1][2]['volume_percent'],100)
    async def test_play_search_ambiguous_and_unique(self):
        self.api.response={'tracks':{'items':[{'name':'hello','uri':T,'artists':[{'name':'A'}]},
                                              {'name':'hello','uri':'spotify:track:'+ID2,'artists':[{'name':'B'}]}]}}
        out=await self.c.play_search('hello')
        self.assertFalse(out['ok']);self.assertEqual(len(self.api.calls),1)
        out=await self.c.play_search('hello','A')
        self.assertTrue(out['ok']);self.assertEqual(self.api.calls[-1][1],'/me/player/play')
    async def test_save_current(self):
        self.api.response={'item':{'uri':T}}
        await self.c.save_current()
        self.assertEqual(self.api.calls[-1][1],'/me/library')
    async def test_close_fail_closed(self):
        await self.c.close()
        with self.assertRaises(ConnectorError):await self.c.search('anything')
        await self.c.connect()
        await self.c.search('anything')

class WindowsTests(unittest.IsolatedAsyncioTestCase):
    class Session:
        source_app_user_model_id='Spotify.exe'
        async def try_play_async(self):return True
        async def try_pause_async(self):return False
        async def try_change_playback_position_async(self,v):self.v=v;return True
        async def try_change_shuffle_active_async(self,v):self.v=v;return True
    async def test_exact_spotify_only(self):
        session=self.Session()
        async def get_sessions():return [types.SimpleNamespace(source_app_user_model_id='chrome.exe'),session]
        win=WindowsSpotify(get_sessions)
        self.assertTrue((await win.action('play'))['accepted'])
        with self.assertRaises(UnsupportedAction):await win.action('pause')
        await win.action('seek',1000);self.assertEqual(session.v,10_000_000)
        await win.action('shuffle',True);self.assertIs(session.v,True)
    async def test_other_player_not_controlled(self):
        called=[]
        async def get_sessions():return [types.SimpleNamespace(source_app_user_model_id='NotSpotify.exe',try_play_async=lambda:called.append(True))]
        with self.assertRaises(UnsupportedAction):await WindowsSpotify(get_sessions).action('play')
        self.assertEqual(called,[])
    async def test_multi_spotify_ambiguous(self):
        async def get_sessions():return [self.Session(),self.Session()]
        with self.assertRaises(UnsupportedAction):await WindowsSpotify(get_sessions).action('play')
    async def test_deeplink_safe(self):
        opened=[];win=WindowsSpotify(opener=opened.append)
        await win.open(T)
        await win.search('Daft Punk songs')
        self.assertEqual(opened[0],T)
        self.assertEqual(opened[1],'spotify:search:Daft%20Punk%20songs')
        with self.assertRaises(ConnectorError):await win.open('https://bad.example/')

class OAuthTests(unittest.TestCase):
    def test_pkce_challenge(self):
        a,b=pkce_pair();self.assertGreaterEqual(len(a),43);self.assertEqual(len(b),43)
    def test_oauth_url_and_csrf(self):
        url=authorization_url('a','http://127.0.0.1:8765/callback','random','challenge')
        self.assertIn('code_challenge_method=S256',url)
        self.assertIn('state=random',url)
        self.assertIn('playlist-modify-private',url)
    def test_no_plaintext_token_fallback(self):
        class Store:
            def __init__(self):self.value={'refresh_token':'secret','expires_at':0}
            def load(self):return self.value
            def save(self,t):self.value=t
        store=Store();mgr=PKCETokenManager(client_id='abc',store=store)
        with patch('spotify_connector.auth.exchange',return_value={'access_token':'fresh','expires_in':3600}):
            self.assertEqual(mgr.access_token(),'fresh')
        self.assertEqual(store.value['refresh_token'],'secret')
        self.assertTrue(mgr.authenticated())
    def test_redirect_must_be_loopback(self):
        self.assertEqual(redirect_uri(8765),'http://127.0.0.1:8765/callback')
        for port in (0,80,65536,True):
            with self.assertRaises(ConnectorError):redirect_uri(port)

class MCPInterfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_mcp_registration_and_call(self):
        """Interface test without package dependency; not a real MCP protocol test."""
        import importlib.util
        from pathlib import Path
        spec=importlib.util.spec_from_file_location('spotify_test_server',Path(__file__).resolve().parents[1]/'server.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        server=module.SpotifyConnector(allow_write=True, service=SpotifyConnector(api=FakeAPI(),windows=FakeWindows(),token_manager=FakeTokens()))
        try:
            expected={'spotify_'+x for x in SpotifyConnector().info.capabilities}
            self.assertEqual({row['name'] for row in server.describe()},expected)
            self.assertTrue(server.invoke('spotify_pause',{})['untrusted_data']['accepted'])
            self.assertIn('untrusted_data',server.invoke('spotify_search',{'query':'rock'}))
            self.assertIn('untrusted_data',server.invoke('spotify_create_playlist',{'name':'Playlist'}))
        finally: server.close()

if __name__=='__main__':unittest.main()

class VolumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_per_app_spotify_only_and_readback(self):
        from spotify_connector.windows_volume import WindowsSpotifyVolume
        class Vol:
            level=0.5;muted=False
            def SetMasterVolume(self,v,_):self.level=v
            def GetMasterVolume(self):return self.level
            def SetMute(self,v,_):self.muted=bool(v)
            def GetMute(self):return self.muted
        class Proc:
            def __init__(self,name):self._name=name
            def name(self):return self._name
        class S:
            def __init__(self,name):self.Process=Proc(name);self.SimpleAudioVolume=Vol()
        spotify=S('spotify.exe');other=S('chrome.exe')
        controller=WindowsSpotifyVolume(lambda:[spotify,other])
        r=controller.volume(25)
        self.assertTrue(r['verified']);self.assertEqual(spotify.SimpleAudioVolume.level,0.25)
        self.assertEqual(other.SimpleAudioVolume.level,0.5)
        r=controller.mute(True)
        self.assertTrue(r['verified']);self.assertTrue(spotify.SimpleAudioVolume.muted)
        self.assertFalse(other.SimpleAudioVolume.muted)
    async def test_no_spotify_volume_session(self):
        from spotify_connector.windows_volume import WindowsSpotifyVolume
        with self.assertRaises(UnsupportedAction):WindowsSpotifyVolume(lambda:[]).volume(25)
    async def test_remote_verify_playback(self):
        c=SpotifyConnector(api=FakeAPI(),windows=FakeWindows(),token_manager=FakeTokens())
        c.api.response={'is_playing':True,'item':{'uri':T},'progress_ms':1200}
        r=await c.verify_playback(T,True)
        self.assertTrue(r['verified'])
        r=await c.verify_playback(E,True)
        self.assertFalse(r['verified'])
