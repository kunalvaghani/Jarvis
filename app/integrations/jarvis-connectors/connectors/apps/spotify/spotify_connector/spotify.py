"""Spotify backend service composed by the production BaseConnector child in server.py.

Spotify 2026 development-mode endpoints; optional Windows-only GSMTC control.
No undocumented Spotify APIs, credential scraping, downloads or playback hacking.
"""
from __future__ import annotations
import asyncio
import os
import re
from typing import Any
from .base import BaseConnector, ConnectorError, ConnectorInfo, UnsupportedAction
from .identifiers import bounded,device_id,resource_id,spotify_uri,uri_list
from .auth import PKCETokenManager
from .api import SpotifyAPI
from .windows_media import WindowsSpotify
from .windows_volume import WindowsSpotifyVolume

TRACKLIKE = {'track','episode'}
SAVABLE = {'track','album','episode','show','audiobook','playlist'}
SEARCH_TYPES = {'track','album','artist','playlist','show','episode','audiobook'}


class SpotifyConnector:
    def __init__(self, api=None, windows=None, token_manager=None, windows_volume=None):
        self.tokens = token_manager or PKCETokenManager()
        self.api = api or SpotifyAPI(self.tokens)
        self.windows = windows or WindowsSpotify()
        self.windows_volume = windows_volume or WindowsSpotifyVolume()
        self._lock = asyncio.Lock()
        self._closed = False

    def require_text(self, value, label, limit=200):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
            raise ConnectorError(label + ' must be a bounded nonempty string')
        return value.strip()

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(name='Spotify',version='1.0.0',namespace='spotify',capabilities=(
            'health','status','currently_playing','devices','queue','recently_played',
            'pause','resume','toggle','next','previous','stop','seek','seek_relative',
            'volume','volume_relative','shuffle','repeat','transfer','play_track',
            'play_album','play_artist','play_playlist','play_show','play_episode',
            'play_uris','play_saved_tracks','add_to_queue','search','search_tracks',
            'search_albums','search_artists','search_playlists','search_episodes',
            'get_track','get_album','get_artist','get_playlist','get_episode','get_show',
            'album_tracks','artist_albums','show_episodes','playlist_items',
            'my_playlists','create_playlist','update_playlist','add_playlist_items',
            'remove_playlist_items','replace_playlist_items','reorder_playlist_items',
            'save_items','remove_saved_items','contains_saved','saved_tracks',
            'saved_albums','saved_shows','saved_episodes','followed_artists','top_tracks',
            'top_artists','get_profile','open_desktop','open_resource','open_search',
            'local_status','local_play','local_pause','local_next','local_previous',
            'local_seek','local_shuffle','local_stop','play_search','queue_search',
            'save_current','remove_current_saved','add_current_to_playlist',
            'get_audiobook','get_chapter','audiobook_chapters','playlist_images',
            'verify_playback','local_volume','local_mute','local_volume_status',
        ))

    async def connect(self) -> None:
        self._closed = False # Lazy: never automatically open browser or remote connection.

    async def close(self) -> None:
        self._closed = True

    async def health(self) -> dict[str, Any]:
        return {'ok':True,'connector':'spotify','version':self.info.version,
                'api_configured':bool(self.tokens.client_id),
                'api_authorized':self.tokens.authenticated(),
                'account_binding':self.tokens.binding() if hasattr(self.tokens,'binding') else '',
                'windows_local_supported':os.name=='nt',
                'capabilities':list(self.info.capabilities),
                'note':'API requires user-approved OAuth and Spotify developer app; local controls require Spotify desktop media session.'}

    async def _req(self, method: str, path: str, *, params=None, body=None):
        if self._closed:
            raise ConnectorError('Spotify connector is closed')
        check = getattr(self.tokens, 'require_request_scopes', None)
        if check is not None:
            check(method, path, params=params, body=body)
        return await self.api.request(method,path,params=params,json_body=body)

    async def _write(self, method: str,path: str, *,params=None,body=None, action: str):
        if not self.tokens.authenticated():
            raise ConnectorError('Spotify API authorization required for '+action+'; run auth_login.py')
        async with self._lock:
            if path.startswith('/playlists/'):
                playlist_path = '/'.join(path.split('/')[:3])
                details = await self._req('GET', playlist_path)
                profile = await self._req('GET', '/me')
                if not isinstance(details,dict) or not isinstance(profile,dict) or not profile.get('id') or (details.get('owner') or {}).get('id') != profile['id']:
                    raise ConnectorError('Playlist owner must match the authorized Spotify account')
                check = getattr(self.tokens, 'require_playlist_scope', None)
                if check is not None: check(bool(details.get('public')) or bool((body or {}).get('public')))
            result=await self._req(method,path,params=params,body=body)
        return {'ok':True,'accepted':True,'verified':None,'playing_verified':False,'status':'accepted','action':action,'source':'spotify_web_api','response':result}

    async def _playback(self, verb: str, name: str, *,params=None,body=None):
        if not self.tokens.authenticated():
            fallback={'pause':'pause','resume':'play','next':'next','previous':'previous','stop':'stop'}
            if name in fallback:
                return await self.windows.action(fallback[name])
            raise ConnectorError('Spotify API authorization required for '+name+'; run auth_login.py')
        return await self._write(verb,'/me/player/'+('play' if name=='resume' else name),params=params,body=body,action=name)

    # Player: status read is safely routed; other local fallbacks are explicit.
    async def status(self):
        if self.tokens.authenticated():
            state=await self._req('GET','/me/player')
            return {'ok':True,'source':'spotify_web_api','active':bool(state),'playback':state}
        return await self.windows.status()

    async def currently_playing(self):
        item=await self._req('GET','/me/player/currently-playing')
        return {'ok':True,'source':'spotify_web_api','currently_playing':item}

    async def devices(self): return await self._req('GET','/me/player/devices')
    async def queue(self): return await self._req('GET','/me/player/queue')
    async def recently_played(self, limit:int=20):
        return await self._req('GET','/me/player/recently-played',params={'limit':bounded(limit,'limit',1,50)})
    async def pause(self): return await self._playback('PUT','pause')
    async def resume(self): return await self._playback('PUT','resume')
    async def next(self): return await self._playback('POST','next')
    async def previous(self): return await self._playback('POST','previous')
    async def stop(self):
        # Spotify Web API has no stop endpoint; pause is semantically different.
        return await self.windows.action('stop')
    async def toggle(self):
        if self.tokens.authenticated():
            state=await self._req('GET','/me/player')
            if not state:
                raise UnsupportedAction('No active Spotify player; cannot determine toggle state')
            return await (self.pause() if state.get('is_playing') else self.resume())
        return await self.windows.action('toggle')
    async def seek(self,position_ms:int,device:str|None=None):
        pos=bounded(position_ms,'position_ms',0,86_400_000)
        if not self.tokens.authenticated():
            if device: raise ConnectorError('Authorize Spotify API before targeting a remote device')
            return await self.windows.action('seek',pos)
        return await self._write('PUT','/me/player/seek',params={'position_ms':pos,'device_id':device_id(device)},action='seek')
    async def seek_relative(self, delta_ms:int,device:str|None=None):
        if not isinstance(delta_ms,int) or isinstance(delta_ms,bool) or abs(delta_ms)>86_400_000:
            raise ConnectorError('delta_ms out of range')
        if self.tokens.authenticated():
            state=await self._req('GET','/me/player')
            if not state or state.get('progress_ms') is None: raise UnsupportedAction('Playback position unknown')
            duration=((state.get('item') or {}).get('duration_ms'))
            upper=duration-1 if isinstance(duration,int) and duration>0 else 86_400_000
            new=max(0,min(upper,state['progress_ms']+delta_ms))
        else:
            state=await self.windows.status(); new=max(0,min(86_400_000,state['position_ms']+delta_ms))
        return await self.seek(new,device)
    async def volume(self,percent:int,device:str|None=None):
        return await self._write('PUT','/me/player/volume',params={'volume_percent':bounded(percent,'percent',0,100),'device_id':device_id(device)},action='volume')
    async def volume_relative(self,delta:int,device:str|None=None):
        if not isinstance(delta,int) or isinstance(delta,bool) or not -100<=delta<=100:raise ConnectorError('Invalid volume delta')
        state=await self._req('GET','/me/player'); vol=((state or {}).get('device') or {}).get('volume_percent')
        if not isinstance(vol,int):raise UnsupportedAction('Current Spotify volume unknown')
        return await self.volume(max(0,min(100,vol+delta)),device)
    async def shuffle(self,enabled:bool,device:str|None=None):
        if not isinstance(enabled,bool):raise ConnectorError('enabled must be boolean')
        if not self.tokens.authenticated(): return await self.windows.action('shuffle',enabled)
        return await self._write('PUT','/me/player/shuffle',params={'state':str(enabled).lower(),'device_id':device_id(device)},action='shuffle')
    async def repeat(self,mode:str,device:str|None=None):
        if mode not in ('off','track','context'):raise ConnectorError('repeat must be off, track or context')
        if not self.tokens.authenticated():
            if device: raise ConnectorError('Authorize Spotify API before targeting a remote device')
            return await self.windows.action('repeat',mode)
        return await self._write('PUT','/me/player/repeat',params={'state':mode,'device_id':device_id(device)},action='repeat')
    async def transfer(self,device:str,play:bool=False):
        if not isinstance(play,bool):raise ConnectorError('play must be boolean')
        if not device_id(device): raise ConnectorError('A nonempty exact device ID is required')
        devices = await self._req('GET','/me/player/devices')
        matches = [row for row in devices.get('devices',[]) if isinstance(row,dict) and row.get('id') == device]
        if len(matches) != 1 or not matches[0].get('is_active') or matches[0].get('is_restricted'):
            raise UnsupportedAction('Choose an exact active unrestricted Spotify device')
        return await self._write('PUT','/me/player',body={'device_ids':[device_id(device)],'play':play},action='transfer')
    async def play_uris(self,items:list[str],device:str|None=None,position_ms:int|None=None):
        uris=uri_list(items,TRACKLIKE,100)
        body={'uris':uris}
        if position_ms is not None:body['position_ms']=bounded(position_ms,'position_ms',0,86_400_000)
        return await self._write('PUT','/me/player/play',params={'device_id':device_id(device)},body=body,action='play_uris')
    async def play_track(self,track:str,device:str|None=None):
        uri=spotify_uri(track,{'track'}) if not (len(track)==22 and track.isalnum()) else 'spotify:track:'+track
        if not self.tokens.authenticated():
            if device: raise ConnectorError('Authorize Spotify API before targeting a remote device')
            return await self.windows.open(uri)
        return await self.play_uris([uri],device)
    async def play_episode(self,episode:str,device:str|None=None):
        uri='spotify:episode:'+resource_id(episode,'episode')
        if not self.tokens.authenticated():
            if device: raise ConnectorError('Authorize Spotify API before targeting a remote device')
            return await self.windows.open(uri)
        return await self.play_uris([uri],device)
    async def play_context(self,ref:str,kind:str,device:str|None=None,offset:int|None=None):
        if offset is not None and not self.tokens.authenticated():
            raise UnsupportedAction('API authorization is required for an exact playlist position')
        uri='spotify:'+kind+':'+resource_id(ref,kind)
        if not self.tokens.authenticated():
            if device: raise ConnectorError('Authorize Spotify API before targeting a remote device')
            return await self.windows.open(uri)
        body={'context_uri':uri}
        if offset is not None:body['offset']={'position':bounded(offset,'offset',0,9999)}
        return await self._write('PUT','/me/player/play',params={'device_id':device_id(device)},body=body,action='play_'+kind)
    async def play_album(self,album:str,device:str|None=None):return await self.play_context(album,'album',device)
    async def play_artist(self,artist:str,device:str|None=None):return await self.play_context(artist,'artist',device)
    async def play_playlist(self,playlist:str,device:str|None=None,offset:int|None=None):return await self.play_context(playlist,'playlist',device,offset)
    async def play_show(self,show:str):return await self.windows.open('spotify:show:'+resource_id(show,'show')) # Web API doesn't guarantee show context playback
    async def play_saved_tracks(self,limit:int=30,device:str|None=None):
        data=await self.saved_tracks(limit)
        uris=[x.get('track',{}).get('uri') for x in data.get('items',[]) if isinstance(x,dict) and isinstance(x.get('track'),dict)]
        if not uris:raise UnsupportedAction('No saved tracks to play')
        return await self.play_uris(uris,device)
    async def add_to_queue(self,ref:str,device:str|None=None):
        return await self._write('POST','/me/player/queue',params={'uri':spotify_uri(ref,TRACKLIKE),'device_id':device_id(device)},action='queue_add')

    # Search and metadata (2026 dev-mode: search limit <=10).
    async def search(self,query:str,kind:str='track',limit:int=5,offset:int=0):
        q=self.require_text(query,'search query',160)
        if kind not in SEARCH_TYPES:raise ConnectorError('Unsupported Spotify search type')
        return await self._req('GET','/search',params={'q':q,'type':kind,'limit':bounded(limit,'limit',1,10),'offset':bounded(offset,'offset',0,10000)})
    async def search_tracks(self,query:str,limit:int=5):return await self.search(query,'track',limit)
    async def search_albums(self,query:str,limit:int=5):return await self.search(query,'album',limit)
    async def search_artists(self,query:str,limit:int=5):return await self.search(query,'artist',limit)
    async def search_playlists(self,query:str,limit:int=5):return await self.search(query,'playlist',limit)
    async def search_episodes(self,query:str,limit:int=5):return await self.search(query,'episode',limit)
    async def _get(self,kind:str,ref:str):return await self._req('GET',f'/{kind}s/{resource_id(ref,kind)}')
    async def get_track(self,ref:str):return await self._get('track',ref)
    async def get_album(self,ref:str):return await self._get('album',ref)
    async def get_artist(self,ref:str):return await self._get('artist',ref)
    async def get_playlist(self,ref:str):return await self._get('playlist',ref)
    async def get_episode(self,ref:str):return await self._get('episode',ref)
    async def get_show(self,ref:str):return await self._get('show',ref)
    async def album_tracks(self,album:str,limit:int=30,offset:int=0):return await self._req('GET',f'/albums/{resource_id(album,"album")}/tracks',params=self._page(limit,offset))
    async def artist_albums(self,artist:str,limit:int=20,offset:int=0):return await self._req('GET',f'/artists/{resource_id(artist,"artist")}/albums',params=self._page(limit,offset))
    async def show_episodes(self,show:str,limit:int=20,offset:int=0):return await self._req('GET',f'/shows/{resource_id(show,"show")}/episodes',params=self._page(limit,offset))
    @staticmethod
    def _page(limit:int=20,offset:int=0):return {'limit':bounded(limit,'limit',1,50),'offset':bounded(offset,'offset',0,10000)}

    # Playlists. All 2026 current /items paths. Writes are explicit (no ambiguous search/autoselection).
    async def my_playlists(self,limit:int=20,offset:int=0):return await self._req('GET','/me/playlists',params=self._page(limit,offset))
    async def playlist_items(self,playlist:str,limit:int=50,offset:int=0):
        return await self._req('GET',f'/playlists/{resource_id(playlist,"playlist")}/items',params=self._page(limit,offset))
    async def create_playlist(self,name:str,public:bool=False,description:str=''):
        n=self.require_text(name,'playlist name',100)
        if not isinstance(public,bool):raise ConnectorError('public must be boolean')
        if not isinstance(description,str) or len(description)>300:raise ConnectorError('Invalid description')
        return await self._write('POST','/me/playlists',body={'name':n,'public':public,'description':description},action='create_playlist')
    async def update_playlist(self,playlist:str,name:str='',description:str='',public:bool|None=None,collaborative:bool|None=None):
        body={}
        if name:body['name']=self.require_text(name,'playlist name',100)
        if description:body['description']=self.require_text(description,'description',300)
        if public is not None:
            if not isinstance(public,bool):raise ConnectorError('public must be boolean')
            body['public']=public
        if collaborative is not None:
            if not isinstance(collaborative,bool): raise ConnectorError('collaborative must be boolean')
            if collaborative and public is True: raise ConnectorError('Collaborative playlists must be private')
            body['collaborative']=collaborative
            if collaborative: body['public']=False
        if not body:raise ConnectorError('No update supplied')
        return await self._write('PUT',f'/playlists/{resource_id(playlist,"playlist")}',body=body,action='update_playlist')
    async def add_playlist_items(self,playlist:str,items:list[str],position:int|None=None):
        uris=uri_list(items,TRACKLIKE)
        body={'uris':uris}
        if position is not None:body['position']=bounded(position,'position',0,100000)
        return await self._write('POST',f'/playlists/{resource_id(playlist,"playlist")}/items',body=body,action='add_playlist_items')
    async def remove_playlist_items(self,playlist:str,items:list[str],snapshot_id:str=''):
        uris=uri_list(items,TRACKLIKE)
        body={'items':[{'uri':u} for u in uris]}
        if snapshot_id:body['snapshot_id']=self.require_text(snapshot_id,'snapshot ID',250)
        return await self._write('DELETE',f'/playlists/{resource_id(playlist,"playlist")}/items',body=body,action='remove_playlist_items')
    async def replace_playlist_items(self,playlist:str,items:list[str]):
        if not isinstance(items,list) or len(items)>100:raise ConnectorError('Provide at most 100 replacement items')
        uris=uri_list(items,TRACKLIKE) if items else []
        return await self._write('PUT',f'/playlists/{resource_id(playlist,"playlist")}/items',body={'uris':uris},action='replace_playlist_items')
    async def reorder_playlist_items(self,playlist:str,range_start:int,insert_before:int,range_length:int=1,snapshot_id:str=''):
        body={'range_start':bounded(range_start,'range_start',0,100000),'insert_before':bounded(insert_before,'insert_before',0,100000),'range_length':bounded(range_length,'range_length',1,100)}
        if snapshot_id:body['snapshot_id']=self.require_text(snapshot_id,'snapshot ID',250)
        return await self._write('PUT',f'/playlists/{resource_id(playlist,"playlist")}/items',body=body,action='reorder_playlist_items')

    # Library, personalization, user-specific catalogue.
    async def save_items(self,items:list[str]):
        uris=uri_list(items,SAVABLE,40)
        return await self._write('PUT','/me/library',params={'uris':','.join(uris)},action='save_library')
    async def remove_saved_items(self,items:list[str]):
        uris=uri_list(items,SAVABLE,40)
        return await self._write('DELETE','/me/library',params={'uris':','.join(uris)},action='remove_library')
    async def contains_saved(self,items:list[str]):
        uris=uri_list(items,SAVABLE,40)
        return await self._req('GET','/me/library/contains',params={'uris':','.join(uris)})
    async def saved_tracks(self,limit:int=20,offset:int=0):return await self._req('GET','/me/tracks',params=self._page(limit,offset))
    async def saved_albums(self,limit:int=20,offset:int=0):return await self._req('GET','/me/albums',params=self._page(limit,offset))
    async def saved_shows(self,limit:int=20,offset:int=0):return await self._req('GET','/me/shows',params=self._page(limit,offset))
    async def saved_episodes(self,limit:int=20,offset:int=0):return await self._req('GET','/me/episodes',params=self._page(limit,offset))
    async def followed_artists(self,limit:int=20):return await self._req('GET','/me/following',params={'type':'artist','limit':bounded(limit,'limit',1,50)})
    async def top_tracks(self,time_range:str='medium_term',limit:int=20):return await self._top('tracks',time_range,limit)
    async def top_artists(self,time_range:str='medium_term',limit:int=20):return await self._top('artists',time_range,limit)
    async def _top(self,kind:str,time_range:str,limit:int):
        if time_range not in ('short_term','medium_term','long_term'):raise ConnectorError('Invalid time range')
        return await self._req('GET',f'/me/top/{kind}',params={'time_range':time_range,'limit':bounded(limit,'limit',1,50)})
    async def get_profile(self):return await self._req('GET','/me')

    # Higher-level deterministic voice-friendly workflows. Never silently play an
    # ambiguous result. Artist/title validation precedes any account side effect.
    async def play_search(self,query:str,artist:str='',device:str|None=None):
        q=self.require_text(query,'track search',160)
        if artist:artist=self.require_text(artist,'artist',100)
        data=await self.search(q+' artist:'+artist if artist else q,'track',5)
        matches=((data.get('tracks') or {}).get('items') or []) if isinstance(data,dict) else []
        scored=[]
        for item in matches:
            if not isinstance(item,dict) or not item.get('uri') or not item.get('name'):continue
            name=item['name'].casefold().strip(); query=q.casefold().strip()
            names=[a.get('name','').casefold() for a in item.get('artists',[]) if isinstance(a,dict)]
            if artist and artist.casefold() not in names: continue
            score=(6 if name==query else 2 if query in name else 0)+(5 if artist and artist.casefold() in names else 0)
            scored.append((score,item))
        scored.sort(key=lambda si:si[0],reverse=True)
        if not scored:
            return {'ok':False,'reason':'no_results','query':q,'candidates':[]}
        # Require exact title/artist match; top score must be strictly above runner up.
        if scored[0][0]<6 or (len(scored)>1 and scored[0][0]==scored[1][0]):
            return {'ok':False,'reason':'ambiguous_results','query':q,
                    'candidates':[{'name':i.get('name'),'artists':[x.get('name') for x in i.get('artists',[])], 'uri':i.get('uri')} for _,i in scored[:5]]}
        chosen=scored[0][1]
        result=await self.play_uris([spotify_uri(chosen['uri'],{'track'})],device)
        return {'ok':True,'selected':{'name':chosen['name'],'uri':chosen['uri']},'playback':result}

    async def queue_search(self,query:str,artist:str='',device:str|None=None):
        # Search only; refuse to add on ambiguous match.
        q=self.require_text(query,'track search',160)
        data=await self.search(q,'track',5)
        matches=((data.get('tracks') or {}).get('items') or []) if isinstance(data,dict) else []
        matches=[i for i in matches if isinstance(i,dict) and i.get('name','').casefold()==q.casefold()
                 and (not artist or artist.casefold() in [a.get('name','').casefold() for a in i.get('artists',[]) if isinstance(a,dict)])]
        if len(matches)!=1:
            return {'ok':False,'reason':'not_one_exact_match','candidates':[{'name':i.get('name'),'uri':i.get('uri')} for i in matches[:5]]}
        return await self.add_to_queue(matches[0]['uri'],device)

    async def _current_track_uri(self):
        result=await self.currently_playing()
        item=result.get('currently_playing') or {}
        uri=(item.get('item') or {}).get('uri')
        if not uri:raise UnsupportedAction('No current Spotify track or episode identified')
        return spotify_uri(uri,TRACKLIKE)
    async def save_current(self):return await self.save_items([await self._current_track_uri()])
    async def remove_current_saved(self):return await self.remove_saved_items([await self._current_track_uri()])
    async def add_current_to_playlist(self,playlist:str):return await self.add_playlist_items(playlist,[await self._current_track_uri()])
    async def get_audiobook(self,ref:str):return await self._get('audiobook',ref)
    async def get_chapter(self,ref:str):return await self._get('chapter',ref)
    async def audiobook_chapters(self,ref:str,limit:int=20,offset:int=0):
        return await self._req('GET',f'/audiobooks/{resource_id(ref,"audiobook")}/chapters',params=self._page(limit,offset))
    async def playlist_images(self,playlist:str):return await self._req('GET',f'/playlists/{resource_id(playlist,"playlist")}/images')

    async def verify_playback(self,expected_uri:str='',expected_is_playing:bool|None=None):
        state=await self._req('GET','/me/player')
        if not state:
            return {'ok':True,'verified':False,'reason':'no_active_device','source':'spotify_web_api'}
        if expected_uri:
            if isinstance(expected_uri,str) and len(expected_uri)==22 and expected_uri.isalnum():
                expected='spotify:track:'+expected_uri
            else:
                expected=spotify_uri(expected_uri,TRACKLIKE)
        else:expected=None
        if expected_is_playing is not None and not isinstance(expected_is_playing,bool):
            raise ConnectorError('expected_is_playing must be boolean or null')
        uri=(state.get('item') or {}).get('uri')
        playing=state.get('is_playing')
        match=bool(uri or playing is not None)
        if expected: match=match and uri==expected
        if expected_is_playing is not None:match=match and playing==expected_is_playing
        return {'ok':True,'verified':match,'playing_verified':bool(match and playing is True),'status':('playing_verified' if match and playing is True else 'verified' if match else 'unverified'),'source':'spotify_web_api',
                'observed_uri':uri,'observed_is_playing':playing,
                'observed_progress_ms':state.get('progress_ms')}

    @staticmethod
    def _audio_call(function, *args):
        initialized = False
        try:
            if os.name == 'nt':
                import comtypes
                try:
                    comtypes.CoInitialize(); initialized = True
                except OSError as exc:
                    if getattr(exc, 'winerror', None) != -2147417850: raise
            return function(*args)
        finally:
            if initialized: comtypes.CoUninitialize()

    async def local_volume(self,percent:int):
        return await asyncio.to_thread(self._audio_call, self.windows_volume.volume, percent)
    async def local_mute(self,enabled:bool):
        return await asyncio.to_thread(self._audio_call, self.windows_volume.mute, enabled)
    async def local_volume_status(self):
        return await asyncio.to_thread(self._audio_call, self.windows_volume.status)

    # Desktop URI, local GSMTC actions (explicit no-API mode)
    async def open_desktop(self):return await self.windows.open()
    async def open_resource(self,ref:str):
        if isinstance(ref,str) and len(ref)==22 and ref.isalnum():
            raise ConnectorError('Ambiguous raw ID: specify an official Spotify URI or URL')
        return await self.windows.open(ref)
    async def open_search(self,query:str):return await self.windows.search(query)
    async def local_status(self):return await self.windows.status()
    async def local_play(self):return await self.windows.action('play')
    async def local_pause(self):return await self.windows.action('pause')
    async def local_next(self):return await self.windows.action('next')
    async def local_previous(self):return await self.windows.action('previous')
    async def local_stop(self):return await self.windows.action('stop')
    async def local_seek(self,position_ms:int):return await self.windows.action('seek',bounded(position_ms,'position_ms',0,86_400_000))
    async def local_shuffle(self,enabled:bool):return await self.windows.action('shuffle',enabled)
