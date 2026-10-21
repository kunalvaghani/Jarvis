"""Extended, backwards-compatible YouTube child connector.

Controls *the current YouTube tab* using supported on-page media and UI controls.
The official Data API handles metadata and OAuth-authorized account operations.
No stream downloading, ad avoidance, bypassing access restrictions or hidden APIs.
"""
from __future__ import annotations
import asyncio
import math
import os
import re
from typing import Callable, Awaitable
from collections import deque
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode, urlsplit
from .base import ConnectorError, ConnectorInfo, UnsupportedAction
from .youtube import YouTubeConnector as LegacyYouTubeConnector, extract_id, youtube_watch_url, VIDEO_ID, PLAYLIST_ID
from .data_api import YouTubeDataAPI

CHANNEL_ID = re.compile(r'^UC[A-Za-z0-9_-]{22}$')
RESOURCE_ID = re.compile(r'^[A-Za-z0-9_-]{4,150}$')

class YouTubeConnector(LegacyYouTubeConnector):
    def __init__(self, *args, oauth_token: str = '', approval_callback: Callable[[str, dict], Awaitable[bool]] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        token_path = os.environ.get('YOUTUBE_OAUTH_TOKEN_PATH') or str(self._profile_dir.parent/'youtube-oauth-token.json')
        self.data_api = YouTubeDataAPI(key=self._api_key, token=oauth_token, token_path=token_path)
        self._queue: deque[str] = deque()
        self._history: deque[str] = deque(maxlen=100)
        self._repeat_queue = False
        self._shuffle_queue = False
        self.approval_callback = approval_callback

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo('YouTube', '2.0.0', 'youtube', tuple(COMMAND_DESCRIPTIONS))

    async def health(self) -> dict[str, Any]:
        base = await super().health()
        base.update(version='2.0.0', total_commands=len(COMMAND_DESCRIPTIONS)+3, primary_commands=len(COMMAND_DESCRIPTIONS),
                    oauth_configured=bool(self.data_api.token or self.data_api.token_path.is_file()),
                    internal_queue_size=len(self._queue))
        return base

    async def _dom(self, script: str, *args) -> Any:
        await self.connect()
        if urlsplit(self._page.url).hostname not in {'youtube.com','www.youtube.com','m.youtube.com'}:
            raise UnsupportedAction('Active browser page is not YouTube')
        return await self._page.evaluate(script, *args)

    async def _media(self, action: str, **values) -> dict:
        """Read/modify active HTMLMediaElement; read back actual state."""
        valid = {'status','seek','volume','mute','unmute','toggle_mute','speed','speed_delta',
                 'seek_relative','loop','play','pause'}
        if action not in valid:
            raise UnsupportedAction('Unsupported media action')
        await self.connect()
        result = await self._dom('''async ({action, values}) => {
          const v=document.querySelector('video.html5-main-video');
          if (!v) return {ok:false, reason:'no_video'};
          const ad=!!document.querySelector('.ad-showing');
          if (ad && !['status','pause'].includes(action)) return {ok:false,reason:'ad_active_control_unsupported'};
          try {
            if (action==='seek') v.currentTime=Math.max(0, Math.min(Number(values.seconds), Number.isFinite(v.duration)?v.duration:1e9));
            if (action==='seek_relative') v.currentTime=Math.max(0, Math.min(v.currentTime + Number(values.seconds), Number.isFinite(v.duration)?v.duration:1e9));
            if (action==='volume') v.volume=Number(values.volume)/100;
            if (action==='mute') v.muted=true;
            if (action==='unmute') v.muted=false;
            if (action==='toggle_mute') v.muted=!v.muted;
            if (action==='speed') v.playbackRate=Number(values.rate);
            if (action==='speed_delta') v.playbackRate=Math.min(2,Math.max(.25,v.playbackRate + Number(values.delta)));
            if (action==='loop') v.loop=Boolean(values.enabled);
            if (action==='pause') v.pause();
            if (action==='play') { await v.play(); }
            return {ok:true,paused:v.paused,seconds:v.currentTime,
                    duration:Number.isFinite(v.duration)?v.duration:null,
                    volume:Math.round(v.volume*100),muted:v.muted,speed:v.playbackRate,
                    loop:v.loop,ended:v.ended,ready_state:v.readyState,
                    ad,buffering:!v.paused && v.readyState<3,
                    loading:v.readyState===0,video_id:new URL(location.href).searchParams.get('v'),
                    title:document.title};
          } catch(e){ return {ok:false,reason:'browser_media_rejected',error:String(e).slice(0,140)}; }
        }''', {'action':action, 'values':values})
        if not result.get('ok'):
            raise UnsupportedAction(result.get('reason', 'Cannot operate YouTube media player'))
        return {'ok':True, 'action':action, 'source':'dom_media', 'state':result}

    @staticmethod
    def _range(value: Any, label: str, low: float, high: float) -> float:
        if isinstance(value, bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low <= value <= high:
            raise ConnectorError(f'{label} must be a finite number in [{low},{high}]')
        return float(value)

    async def _browser_search(self, query: str, kind: str, limit: int) -> list[dict[str, str]]:
        # Preserve the active video: search in an ephemeral tab of *our own*
        # dedicated context. If page was injected by Jarvis, never create tabs
        # outside Jarvis's browser lifecycle: reuse legacy in that case.
        if self._context is None:
            return await super()._browser_search(query, kind, limit)
        original = self._page
        tab = await self._context.new_page()
        self._page = tab
        try:
            return await super()._browser_search(query, kind, limit)
        finally:
            self._page = original
            await tab.close()

    async def _search(self, query: str, kind: str, limit: int = 5) -> dict[str, Any]:
        query = self.require_text(query,'query',160)
        self._limit(limit)
        if limit > 10:
            raise ConnectorError('Search limit must be 1..10 for compatibility')
        async with self._lock:
            api_error = None
            if self._api_key:
                try:
                    items = await asyncio.to_thread(self._api_search_sync,query,kind,limit)
                    return {'ok':True,'query':query,'kind':kind,'source':'youtube_data_api','results':items}
                except ConnectorError as exc:
                    api_error = str(exc)[:180]
            items = await self._browser_search(query,kind,limit)
            return {'ok':True,'query':query,'kind':kind,'source':'youtube_browser',
                    'api_fallback_reason':api_error,'results':items}

    async def _set_playback(self, play: bool) -> dict[str, Any]:
        async with self._lock:
            before = await self._video_state()
            if before['paused'] != (not play):
                # Start with native media controls, then use the visible site button
                # when browsers block script-driven play and gesture is necessary.
                await self._media('play' if play else 'pause')
                try:
                    await self._page.wait_for_function(
                        'wanted => {const v=document.querySelector("video.html5-main-video"); return v && v.paused === wanted}',
                        arg=not play, timeout=6000)
                except Exception as exc:
                    raise ConnectorError('Playback command sent but playback state did not change') from exc
            after = await self._video_state()
            if after['paused'] != (not play):
                raise ConnectorError('Playback state verification failed')
            return {'ok':True,'action':'resume' if play else 'pause', 'paused':after['paused'], 'url':self._page.url}

    async def _resolve(self, value: str, kind: str) -> str:
        value = self.require_text(value, 'video/playlist', 250)
        identifier = extract_id(value, kind)
        if identifier: return identifier
        if value.lower().startswith(('https:', 'http:')):
            raise ConnectorError('Only exact YouTube HTTPS links are allowed')
        # Ambiguity is surfaced when top search titles score similarly.
        from difflib import SequenceMatcher
        search = await self._search(value, kind, 5)
        candidates = [r for r in search['results'] if r.get('id')]
        if not candidates:
            raise ConnectorError(f'{kind} search did not return a verified identifier')
        scores = [(SequenceMatcher(None,value.casefold(), str(x.get('title','')).casefold()).ratio(),x) for x in candidates]
        scores.sort(key=lambda pair: pair[0], reverse=True)
        if len(scores)>1 and scores[0][0] < .80 and scores[0][0]-scores[1][0] < .12:
            raise ConnectorError('Ambiguous search. Call youtube_search_'+('videos' if kind=='video' else 'playlists')+' and choose an exact ID.')
        return str(scores[0][1]['id'])

    async def play_video(self, video: str) -> dict[str, Any]:
        # Resolve outside lock: _search obtains it internally.
        ident = await self._resolve(video,'video')
        async with self._lock:
            old = extract_id(self._page.url,'video') if self._page is not None else None
            await self._navigate(youtube_watch_url(ident))
            started = await self._attempt_start_unlocked()
            if old: self._history.append(old)
            return {'ok':True,'opened':True,'playing_verified':started,'video_id':ident,
                    'url':self._page.url,'source':'youtube_browser',
                    'note':'Playback not confirmed; user gesture/login/consent may be required' if not started else 'Playback confirmed'}

    async def play_playlist(self, playlist: str) -> dict[str, Any]:
        ident = await self._resolve(playlist,'playlist')
        # Let legacy playlist navigation run with resolved identifier and its own lock.
        return await super().play_playlist(ident)

    async def seek(self, seconds: float) -> dict:
        self._range(seconds,'seconds',0,864000)
        async with self._lock: return await self._media('seek',seconds=seconds)
    async def seek_relative(self, seconds: float) -> dict:
        self._range(seconds,'seconds',-864000,864000)
        async with self._lock: return await self._media('seek_relative',seconds=seconds)
    async def skip_forward(self, seconds: float = 10) -> dict:
        return await self.seek_relative(self._range(seconds,'seconds',0,3600))
    async def skip_back(self, seconds: float = 10) -> dict:
        return await self.seek_relative(-self._range(seconds,'seconds',0,3600))
    async def seek_percent(self, percent: float) -> dict:
        self._range(percent,'percent',0,100)
        async with self._lock:
            info = await self._media('status')
            duration = info['state'].get('duration')
            if not isinstance(duration,(int,float)) or not math.isfinite(duration):
                raise UnsupportedAction('Duration unavailable for live streams')
            return await self._media('seek',seconds=duration*percent/100)
    async def seek_to_start(self) -> dict:
        return await self.seek(0)
    async def set_volume(self, percent: float) -> dict:
        self._range(percent,'percent',0,100)
        async with self._lock: return await self._media('volume',volume=percent)
    async def volume_up(self, percent: float = 10) -> dict:
        self._range(percent,'percent',0,100)
        async with self._lock:
            before = await self._media('status')
            return await self._media('volume',volume=min(100,before['state']['volume']+percent))
    async def volume_down(self, percent: float = 10) -> dict:
        self._range(percent,'percent',0,100)
        async with self._lock:
            before = await self._media('status')
            return await self._media('volume',volume=max(0,before['state']['volume']-percent))
    async def mute(self) -> dict:
        async with self._lock: return await self._media('mute')
    async def unmute(self) -> dict:
        async with self._lock: return await self._media('unmute')
    async def toggle_mute(self) -> dict:
        async with self._lock: return await self._media('toggle_mute')
    async def set_speed(self, rate: float) -> dict:
        self._range(rate,'rate',.25,2)
        async with self._lock: return await self._media('speed',rate=rate)
    async def speed_up(self, delta: float = .25) -> dict:
        self._range(delta,'delta',0,1)
        async with self._lock: return await self._media('speed_delta',delta=delta)
    async def speed_down(self, delta: float = .25) -> dict:
        self._range(delta,'delta',0,1)
        async with self._lock: return await self._media('speed_delta',delta=-delta)
    async def set_video_loop(self, enabled: bool) -> dict:
        async with self._lock: return await self._media('loop',enabled=enabled)
    async def media_status(self) -> dict:
        async with self._lock: return await self._media('status')
    async def restart_video(self) -> dict:
        return await self.seek_to_start()

    async def _click_control(self, selectors: tuple[str,...], description: str) -> dict:
        await self.connect()
        if urlsplit(self._page.url).hostname not in {'youtube.com','www.youtube.com','m.youtube.com'}:
            raise UnsupportedAction('Active page is not YouTube')
        for selector in selectors:
            loc = self._page.locator(selector).first
            try:
                visible = await loc.is_visible()
            except Exception:
                continue  # Read-only discovery may try another selector.
            if visible:
                # A click timeout may occur after the effect: never click another selector.
                await loc.click(timeout=3500)
                return {'ok':True,'action':description,'control':selector,'verified':False}
        raise UnsupportedAction(f'{description} control not currently available on page')

    async def toggle_fullscreen(self) -> dict:
        async with self._lock:
            out=await self._click_control(('.ytp-fullscreen-button',),'toggle_fullscreen')
            await self._page.wait_for_timeout(200)
            out['fullscreen']=await self._dom('() => Boolean(document.fullscreenElement)')
            out['verified']=True
            return out
    async def toggle_theater(self) -> dict:
        async with self._lock:
            return await self._click_control(('.ytp-size-button',),'toggle_theater')
    async def toggle_captions(self) -> dict:
        async with self._lock:
            return await self._click_control(('.ytp-subtitles-button',),'toggle_captions')
    async def open_settings(self) -> dict:
        async with self._lock:
            return await self._click_control(('.ytp-settings-button',),'open_settings')
    async def toggle_miniplayer(self) -> dict:
        async with self._lock:
            return await self._click_control(('.ytp-miniplayer-button',),'toggle_miniplayer')
    async def toggle_autoplay(self) -> dict:
        async with self._lock:
            return await self._click_control(('.ytp-autonav-toggle-button', '[aria-label*="Autoplay"]'), 'toggle_autoplay')
    async def next_frame(self) -> dict:
        async with self._lock:
            state = await self._video_state()
            if not state['paused']:
                raise UnsupportedAction('Frame stepping requires paused video')
            return await self._media('seek_relative',seconds=1/30)
    async def previous_frame(self) -> dict:
        async with self._lock:
            state = await self._video_state()
            if not state['paused']:
                raise UnsupportedAction('Frame stepping requires paused video')
            return await self._media('seek_relative',seconds=-1/30)
    async def get_video_title(self) -> dict:
        async with self._lock:
            await self._video_state()
            return {'ok':True,'title':await self._page.title(), 'url':self._page.url}
    async def get_current_video_id(self) -> dict:
        async with self._lock:
            await self.connect()
            return {'ok':True,'video_id':extract_id(self._page.url,'video')}
    async def get_current_playlist_id(self) -> dict:
        async with self._lock:
            await self.connect()
            return {'ok':True,'playlist_id':extract_id(self._page.url,'playlist')}
    async def get_current_url(self) -> dict:
        async with self._lock:
            await self.connect()
            return {'ok':True,'url':self._page.url}
    async def get_playback_time(self) -> dict:
        async with self._lock:
            state=await self._video_state()
            return {'ok':True,'seconds':state['current_time'], 'duration':state.get('duration')}
    async def get_volume(self) -> dict:
        async with self._lock:
            state=await self._media('status')
            return {'ok':True,'volume':state['state']['volume'],'muted':state['state']['muted']}
    async def get_speed(self) -> dict:
        async with self._lock:
            state=await self._media('status')
            return {'ok':True,'speed':state['state']['speed']}
    async def reconnect_browser(self) -> dict:
        if self._external_page:
            raise UnsupportedAction('Injected browser is Jarvis-owned; recovery must happen in its browser manager')
        async with self._lock:
            await self.close()
            await self.connect()
            return {'ok':True,'connected':bool(self._page),'recovered':True,'url':self._page.url}

    async def browser_reload(self) -> dict:
        async with self._lock:
            await self.connect()
            if urlsplit(self._page.url).hostname not in {'youtube.com','www.youtube.com','m.youtube.com'}:
                raise UnsupportedAction('Reload is limited to YouTube tabs')
            await self._page.reload(wait_until='domcontentloaded',timeout=30000)
            return {'ok':True,'url':self._page.url}
    async def open_youtube_home(self) -> dict:
        async with self._lock:
            await self._navigate('https://www.youtube.com/')
            return {'ok':True,'url':self._page.url}
    async def open_subscriptions(self) -> dict:
        async with self._lock:
            await self._navigate('https://www.youtube.com/feed/subscriptions')
            return {'ok':True,'url':self._page.url}
    async def open_history(self) -> dict:
        async with self._lock:
            await self._navigate('https://www.youtube.com/feed/history')
            return {'ok':True,'url':self._page.url}
    async def open_watch_later(self) -> dict:
        async with self._lock:
            await self._navigate('https://www.youtube.com/playlist?list=WL')
            return {'ok':True,'url':self._page.url}
    async def open_library(self) -> dict:
        async with self._lock:
            await self._navigate('https://www.youtube.com/feed/you')
            return {'ok':True,'url':self._page.url}
    async def open_channel(self, channel: str) -> dict:
        channel = self.require_text(channel, 'channel', 64)
        if not CHANNEL_ID.fullmatch(channel):raise ConnectorError('Expected official channel ID beginning UC')
        async with self._lock:
            await self._navigate('https://www.youtube.com/channel/'+channel)
            return {'ok':True,'url':self._page.url}
    async def open_playlist(self, playlist: str) -> dict:
        ident=extract_id(playlist,'playlist')
        if not ident: raise ConnectorError('Expected playlist ID or HTTPS playlist URL')
        async with self._lock:
            await self._navigate('https://www.youtube.com/playlist?'+urlencode({'list':ident}))
            return {'ok':True,'playlist_id':ident,'url':self._page.url}
    async def open_search(self, query: str) -> dict:
        query=self.require_text(query,'query',160)
        async with self._lock:
            await self._navigate('https://www.youtube.com/results?'+urlencode({'search_query':query}))
            return {'ok':True,'query':query,'url':self._page.url}
    async def open_video(self, video: str) -> dict:
        ident=extract_id(video,'video')
        if not ident:raise ConnectorError('Expected exact video ID or HTTPS watch URL')
        async with self._lock:
            await self._navigate(youtube_watch_url(ident))
            return {'ok':True,'video_id':ident,'opened':True,'playing_verified':False,'url':self._page.url}
    async def browser_back(self) -> dict:
        async with self._lock:
            await self.connect()
            await self._page.go_back(wait_until='domcontentloaded',timeout=20000)
            if urlsplit(self._page.url).hostname not in {'youtube.com','www.youtube.com','m.youtube.com'}:
                raise ConnectorError('Browser history navigated away from YouTube; control halted')
            return {'ok':True,'url':self._page.url}
    async def browser_forward(self) -> dict:
        async with self._lock:
            await self.connect()
            await self._page.go_forward(wait_until='domcontentloaded',timeout=20000)
            if urlsplit(self._page.url).hostname not in {'youtube.com','www.youtube.com','m.youtube.com'}:
                raise ConnectorError('Browser history navigated away from YouTube; control halted')
            return {'ok':True,'url':self._page.url}
    async def get_page_diagnostics(self) -> dict:
        async with self._lock:
            await self.connect()
            return {'ok':True,'url':self._page.url,'title':await self._page.title(),
                    'media_count':await self._page.locator('video.html5-main-video').count(),
                    'play_control_count':await self._page.locator('.ytp-play-button').count()}

    # This is an explicitly connector-managed queue, not YouTube's private UI queue.
    async def queue_add(self, video: str) -> dict:
        vid=extract_id(video,'video')
        if not vid:raise ConnectorError('Queue accepts video IDs or YouTube watch links')
        async with self._lock:
            if len(self._queue)>=500:raise ConnectorError('Queue limit 500 reached')
            self._queue.append(vid)
            return {'ok':True,'queued':vid,'size':len(self._queue),'queue_type':'jarvis_local'}
    async def queue_add_many(self, videos: list[str]) -> dict:
        if not isinstance(videos,list) or not 1<=len(videos)<=100:
            raise ConnectorError('videos must be a list of 1..100 identifiers')
        ids=[extract_id(x,'video') if isinstance(x,str) else None for x in videos]
        if any(x is None for x in ids):raise ConnectorError('One or more invalid video identifiers')
        async with self._lock:
            if len(self._queue)+len(ids)>500:raise ConnectorError('Queue capacity exceeded')
            self._queue.extend(ids)
            return {'ok':True,'added':len(ids),'size':len(self._queue),'queue_type':'jarvis_local'}
    async def queue_list(self) -> dict:
        async with self._lock:return {'ok':True,'videos':list(self._queue),'size':len(self._queue),'queue_type':'jarvis_local'}
    async def queue_clear(self) -> dict:
        async with self._lock:
            n=len(self._queue);self._queue.clear()
            return {'ok':True,'cleared':n,'size':0}
    async def queue_remove(self, index: int) -> dict:
        if isinstance(index,bool) or not isinstance(index,int):raise ConnectorError('index must be integer')
        async with self._lock:
            if index<0 or index>=len(self._queue):raise ConnectorError('index outside queue')
            removed=self._queue[index];del self._queue[index]
            return {'ok':True,'removed':removed,'size':len(self._queue)}
    async def queue_move(self, old_index: int, new_index: int) -> dict:
        if any(isinstance(v,bool) or not isinstance(v,int) for v in (old_index,new_index)):
            raise ConnectorError('Indices must be integers')
        async with self._lock:
            if min(old_index,new_index)<0 or max(old_index,new_index)>=len(self._queue):
                raise ConnectorError('Index outside queue')
            video=self._queue[old_index];del self._queue[old_index];self._queue.insert(new_index,video)
            return {'ok':True,'size':len(self._queue),'videos':list(self._queue)}
    async def queue_play_next(self) -> dict:
        async with self._lock:
            if not self._queue:raise ConnectorError('Jarvis queue empty')
            video=self._queue[0]
            old=extract_id(getattr(self._page,'url',''),'video') if self._page else None
            await self._navigate(youtube_watch_url(video))
            verified=await self._attempt_start_unlocked()
            if verified:
                self._queue.popleft()
                if old:self._history.append(old)
                if self._repeat_queue:self._queue.append(video)
            return {'ok':True,'opened':True,'playing_verified':verified,'video_id':video,
                    'outcome':'confirmed' if verified else 'opened_only',
                    'size':len(self._queue),'queue_type':'jarvis_local'}
    async def queue_set_repeat(self, enabled: bool) -> dict:
        if not isinstance(enabled,bool):raise ConnectorError('enabled must be boolean')
        async with self._lock:self._repeat_queue=enabled;return {'ok':True,'repeat_queue':enabled}
    async def queue_set_shuffle(self, enabled: bool) -> dict:
        if not isinstance(enabled,bool):raise ConnectorError('enabled must be boolean')
        import random
        async with self._lock:
            self._shuffle_queue=enabled
            if enabled:
                items=list(self._queue); random.SystemRandom().shuffle(items); self._queue=deque(items)
            return {'ok':True,'shuffle_queue':enabled,'videos':list(self._queue)}
    async def queue_shuffle_now(self) -> dict:
        import random
        async with self._lock:
            items=list(self._queue);random.SystemRandom().shuffle(items);self._queue=deque(items)
            return {'ok':True,'size':len(self._queue),'videos':list(self._queue)}
    async def queue_status(self) -> dict:
        async with self._lock:
            return {'ok':True,'size':len(self._queue),'repeat_queue':self._repeat_queue,
                    'shuffle_queue':self._shuffle_queue,'history_size':len(self._history),'queue_type':'jarvis_local'}
    async def queue_play_previous(self) -> dict:
        async with self._lock:
            if not self._history:raise ConnectorError('Jarvis queue playback history empty')
            video=self._history[-1]
            await self._navigate(youtube_watch_url(video))
            verified=await self._attempt_start_unlocked()
            if verified:self._history.pop()
            return {'ok':True,'opened':True,'playing_verified':verified,'video_id':video}

    # Official YouTube Data API: public metadata and optional OAuth account operations.
    async def _approve(self, action: str, context: dict) -> None:
        if self.approval_callback is None or not await self.approval_callback(action,context):
            raise ConnectorError('Account mutation blocked: trusted Jarvis approval callback required')

    async def _api(self, resource: str, *, params: dict | None = None,
                   method: str = 'GET', body: dict | None = None, oauth: bool = False) -> dict:
        return await self.data_api.request(resource,params=params,method=method,body=body,oauth=oauth)
    @staticmethod
    def _limit(limit: int) -> int:
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=50:
            raise ConnectorError('limit must be integer 1..50')
        return limit
    @staticmethod
    def _ident(value: str, kind: str = 'resource') -> str:
        if not isinstance(value,str) or not RESOURCE_ID.fullmatch(value):
            raise ConnectorError(f'Invalid {kind} identifier')
        return value
    async def search_channels(self, query: str, limit: int = 5) -> dict:
        return await self._api('search',params={'part':'snippet','q':self.require_text(query,'query',160),'type':'channel','maxResults':self._limit(limit)})
    async def search_videos_filtered(self, query: str, limit: int = 5, order: str = 'relevance', video_duration: str = 'any') -> dict:
        if order not in {'relevance','date','rating','title','videoCount','viewCount'}:raise ConnectorError('Invalid order')
        if video_duration not in {'any','short','medium','long'}:raise ConnectorError('Invalid duration')
        return await self._api('search',params={'part':'snippet','q':self.require_text(query,'query',160),
                'type':'video','maxResults':self._limit(limit),'order':order,'videoDuration':video_duration})
    async def get_video_details(self, video: str) -> dict:
        vid=extract_id(video,'video')
        if not vid:raise ConnectorError('Invalid video identifier')
        return await self._api('videos',params={'part':'snippet,contentDetails,statistics,status','id':vid})
    async def get_video_statistics(self, video: str) -> dict:
        vid=extract_id(video,'video')
        if not vid:raise ConnectorError('Invalid video identifier')
        return await self._api('videos',params={'part':'statistics','id':vid})
    async def get_video_captions_metadata(self, video: str) -> dict:
        vid=extract_id(video,'video')
        if not vid:raise ConnectorError('Invalid video identifier')
        return await self._api('captions',params={'part':'snippet','videoId':vid},oauth=True)
    async def get_channel_details(self, channel_id: str) -> dict:
        return await self._api('channels',params={'part':'snippet,statistics,contentDetails','id':self._ident(channel_id,'channel')})
    async def get_channel_videos(self, channel_id: str, limit: int = 10) -> dict:
        return await self._api('search',params={'part':'snippet','channelId':self._ident(channel_id,'channel'),
                'type':'video','order':'date','maxResults':self._limit(limit)})
    async def get_playlist_details(self, playlist: str) -> dict:
        pid=extract_id(playlist,'playlist')
        if not pid:raise ConnectorError('Invalid playlist ID')
        return await self._api('playlists',params={'part':'snippet,contentDetails,status','id':pid})
    async def get_playlist_items(self, playlist: str, limit: int = 50, page_token: str = '') -> dict:
        pid=extract_id(playlist,'playlist')
        if not pid:raise ConnectorError('Invalid playlist ID')
        return await self._api('playlistItems',params={'part':'snippet,contentDetails','playlistId':pid,
                    'maxResults':self._limit(limit),'pageToken':page_token or None})
    async def get_channel_playlists(self, channel_id: str, limit: int = 25) -> dict:
        return await self._api('playlists',params={'part':'snippet,contentDetails','channelId':self._ident(channel_id,'channel'),'maxResults':self._limit(limit)})
    async def get_video_comments(self, video: str, limit: int = 20) -> dict:
        vid=extract_id(video,'video')
        if not vid:raise ConnectorError('Invalid video ID')
        return await self._api('commentThreads',params={'part':'snippet,replies','videoId':vid,'maxResults':self._limit(limit)})
    async def get_comment_replies(self, parent_id: str, limit: int = 20) -> dict:
        return await self._api('comments',params={'part':'snippet','parentId':self._ident(parent_id,'parent comment'),'maxResults':self._limit(limit)})
    async def get_video_categories(self, region_code: str = 'US') -> dict:
        if not re.fullmatch('[A-Z]{2}',region_code):raise ConnectorError('region_code must be ISO 2-letter country code')
        return await self._api('videoCategories',params={'part':'snippet','regionCode':region_code})
    async def get_trending_videos(self, region_code: str = 'US', limit: int = 20) -> dict:
        if not re.fullmatch('[A-Z]{2}',region_code):raise ConnectorError('region_code must be ISO 2-letter country code')
        return await self._api('videos',params={'part':'snippet,statistics','chart':'mostPopular','regionCode':region_code,'maxResults':self._limit(limit)})
    async def get_my_channel(self) -> dict:
        return await self._api('channels',params={'part':'snippet,statistics,contentDetails','mine':'true'},oauth=True)
    async def get_my_playlists(self, limit: int = 25) -> dict:
        return await self._api('playlists',params={'part':'snippet,contentDetails,status','mine':'true','maxResults':self._limit(limit)},oauth=True)
    async def get_my_subscriptions(self, limit: int = 25) -> dict:
        return await self._api('subscriptions',params={'part':'snippet,contentDetails','mine':'true','maxResults':self._limit(limit)},oauth=True)
    async def get_my_liked_videos(self, limit: int = 25) -> dict:
        return await self._api('videos',params={'part':'snippet,contentDetails','myRating':'like','maxResults':self._limit(limit)},oauth=True)
    async def get_my_video_rating(self, video: str) -> dict:
        vid=extract_id(video,'video')
        if not vid:raise ConnectorError('Invalid video ID')
        return await self._api('videos/getRating',params={'id':vid},oauth=True)
    async def rate_video(self, video: str, rating: str) -> dict:
        if rating not in {'like','dislike','none'}:raise ConnectorError('Rating must be like/dislike/none')
        vid=extract_id(video,'video')
        if not vid:raise ConnectorError('Invalid video ID')
        await self._approve('rate_video',{'video_id':vid,'rating':rating})
        return await self._api('videos/rate',params={'id':vid,'rating':rating},method='POST',oauth=True)
    async def create_playlist(self, title: str, privacy: str = 'private', description: str = '') -> dict:
        if privacy not in {'private','public','unlisted'}:raise ConnectorError('Invalid privacy status')
        await self._approve('create_playlist',{'title':title,'privacy':privacy})
        return await self._api('playlists',params={'part':'snippet,status'},method='POST',oauth=True,
               body={'snippet':{'title':self.require_text(title,'title',150),'description':description[:5000]},
                     'status':{'privacyStatus':privacy}})
    async def update_playlist(self, playlist: str, title: str, description: str = '', privacy: str = 'private') -> dict:
        pid=extract_id(playlist,'playlist')
        if not pid:raise ConnectorError('Invalid playlist')
        if privacy not in {'private','public','unlisted'}:raise ConnectorError('Invalid privacy')
        await self._approve('update_playlist',{'playlist_id':pid,'title':title,'privacy':privacy})
        return await self._api('playlists',params={'part':'snippet,status'},method='PUT',oauth=True,
              body={'id':pid,'snippet':{'title':self.require_text(title,'title',150),'description':description[:5000]},'status':{'privacyStatus':privacy}})
    async def delete_playlist(self, playlist: str) -> dict:
        pid=extract_id(playlist,'playlist')
        if not pid:raise ConnectorError('Invalid playlist')
        await self._approve('delete_playlist',{'playlist_id':pid})
        return await self._api('playlists',params={'id':pid},method='DELETE',oauth=True)
    async def add_video_to_playlist(self, playlist: str, video: str) -> dict:
        pid=extract_id(playlist,'playlist');vid=extract_id(video,'video')
        if not pid or not vid:raise ConnectorError('Expected valid video and playlist identifiers')
        await self._approve('add_video_to_playlist',{'playlist_id':pid,'video_id':vid})
        return await self._api('playlistItems',params={'part':'snippet'},method='POST',oauth=True,
              body={'snippet':{'playlistId':pid,'resourceId':{'kind':'youtube#video','videoId':vid}}})
    async def remove_playlist_item(self, item_id: str) -> dict:
        iid=self._ident(item_id,'playlist item')
        await self._approve('remove_playlist_item',{'item_id':iid})
        return await self._api('playlistItems',params={'id':iid},method='DELETE',oauth=True)
    async def subscribe_channel(self, channel_id: str) -> dict:
        if not CHANNEL_ID.fullmatch(channel_id):raise ConnectorError('Invalid channel ID')
        await self._approve('subscribe_channel',{'channel_id':channel_id})
        return await self._api('subscriptions',params={'part':'snippet'},method='POST',oauth=True,
              body={'snippet':{'resourceId':{'kind':'youtube#channel','channelId':channel_id}}})
    async def unsubscribe_channel(self, subscription_id: str) -> dict:
        sid=self._ident(subscription_id,'subscription')
        await self._approve('unsubscribe_channel',{'subscription_id':sid})
        return await self._api('subscriptions',params={'id':sid},method='DELETE',oauth=True)
    async def add_comment(self, video: str, channel_id: str, text: str) -> dict:
        vid=extract_id(video,'video')
        if not vid or not CHANNEL_ID.fullmatch(channel_id):raise ConnectorError('Invalid video/channel ID')
        await self._approve('add_comment',{'video_id':vid,'channel_id':channel_id,'text':text})
        return await self._api('commentThreads',params={'part':'snippet'},method='POST',oauth=True,
              body={'snippet':{'videoId':vid,'channelId':channel_id,'topLevelComment':{'snippet':{'textOriginal':self.require_text(text,'comment',10000)}}}})
    async def reply_comment(self, parent_id: str, text: str) -> dict:
        pid=self._ident(parent_id,'comment')
        await self._approve('reply_comment',{'parent_id':pid,'text':text})
        return await self._api('comments',params={'part':'snippet'},method='POST',oauth=True,
              body={'snippet':{'parentId':self._ident(parent_id,'comment'),'textOriginal':self.require_text(text,'reply',10000)}})
    async def delete_my_comment(self, comment_id: str) -> dict:
        cid=self._ident(comment_id,'comment')
        await self._approve('delete_my_comment',{'comment_id':cid})
        return await self._api('comments',params={'id':cid},method='DELETE',oauth=True)
    async def get_quota_hint(self) -> dict:
        return {'ok':True,'note':'Google Cloud console is authoritative; this process cannot read live project quota usage.',
                'limits_documentation':'https://developers.google.com/youtube/v3/determine_quota_cost'}

# Declarative descriptions; every key must resolve to a *real*, callable async method.
COMMAND_DESCRIPTIONS: dict[str,str] = {
 'health':'Inspect connector state and API/browser availability',
 'search_videos':'Search videos using API key or visible browser',
 'search_playlists':'Search playlists using API key or visible browser',
 'play_video':'Find and play an exact video ID/URL or disambiguated query',
 'play_playlist':'Find/open and play a YouTube playlist',
 'pause':'Pause active YouTube video with verification',
 'resume':'Resume active YouTube video with verification',
 'next_video':'Next recommended video or playlist entry',
 'previous_video':'Previous playlist entry',
 'get_status':'Inspect YouTube player status',
 'seek':'Seek to time in seconds','seek_relative':'Seek relative seconds',
 'skip_forward':'Skip forward N seconds','skip_back':'Skip back N seconds','seek_percent':'Seek to percent of duration',
 'seek_to_start':'Seek to beginning','restart_video':'Restart video',
 'set_volume':'Set playback volume percent','volume_up':'Raise player volume','volume_down':'Lower player volume',
 'mute':'Mute video','unmute':'Unmute video','toggle_mute':'Toggle player mute',
 'set_speed':'Set playback speed','speed_up':'Increase speed','speed_down':'Decrease speed',
 'set_video_loop':'Toggle HTML5 current video repeat','media_status':'Inspect full HTML media player state',
 'toggle_fullscreen':'Toggle YouTube fullscreen','toggle_theater':'Toggle YouTube theater layout',
 'toggle_captions':'Toggle captions via player control','open_settings':'Open YouTube player settings',
 'toggle_miniplayer':'Toggle player miniplayer','toggle_autoplay':'Toggle autoplay through UI',
 'next_frame':'Advance approximate frame when paused','previous_frame':'Reverse approximate frame when paused',
 'get_video_title':'Get tab/video title','get_current_video_id':'Read active video ID',
 'get_current_playlist_id':'Read active playlist ID','get_current_url':'Read current URL',
 'get_playback_time':'Get player time/duration','get_volume':'Read volume/mute','get_speed':'Read playback speed',
 'reconnect_browser':'Recreate dedicated browser session if disconnected','browser_reload':'Reload current YouTube page','open_youtube_home':'Navigate YouTube home',
 'open_subscriptions':'Open subscriptions page','open_history':'Open YouTube history',
 'open_watch_later':'Open Watch Later playlist','open_library':'Open user library',
 'open_channel':'Open channel by ID','open_playlist':'Open playlist by ID','open_search':'Open visible search results',
 'open_video':'Open video without asserting playback started',
 'browser_back':'Navigate back in YouTube tab','browser_forward':'Navigate forward in YouTube tab',
 'get_page_diagnostics':'Inspect DOM player presence/controls',
 'queue_add':'Add single video to Jarvis-managed queue','queue_add_many':'Add many videos to Jarvis queue',
 'queue_list':'List Jarvis-managed queue','queue_clear':'Clear Jarvis queue',
 'queue_remove':'Remove video by queue index','queue_move':'Reorder queue item',
 'queue_play_next':'Play next Jarvis queued video',
 'queue_set_repeat':'Enable repetition of Jarvis local queue','queue_set_shuffle':'Set Jarvis queue shuffle preference',
 'queue_shuffle_now':'Randomize Jarvis queue order', 'queue_status':'Inspect local queue settings',
 'queue_play_previous':'Revisit last Jarvis-queued video',
 'search_channels':'Search channels with Data API',
 'search_videos_filtered':'Search videos with duration/sort filters using Data API',
 'get_video_details':'Get video metadata via Data API','get_video_statistics':'Get video stats via Data API',
 'get_video_captions_metadata':'Get captions metadata via OAuth',
 'get_channel_details':'Get channel metadata via Data API','get_channel_videos':'Get recent channel videos',
 'get_playlist_details':'Get playlist metadata','get_playlist_items':'Get list of playlist entries',
 'get_channel_playlists':'Get playlists of specified channel',
 'get_video_comments':'Read public comments','get_comment_replies':'Read comment replies',
 'get_video_categories':'Retrieve video categories by region','get_trending_videos':'Retrieve popular videos',
 'get_my_channel':'Read signed-in channel (OAuth)','get_my_playlists':'Read owned playlists (OAuth)',
 'get_my_subscriptions':'Read subscriptions (OAuth)','get_my_liked_videos':'Read liked videos (OAuth)',
 'get_my_video_rating':'Read my rating for specified video (OAuth)',
 'rate_video':'Like/dislike/unrate video (OAuth, approval)',
 'create_playlist':'Create playlist (OAuth, approval)','update_playlist':'Edit playlist (OAuth, approval)',
 'delete_playlist':'Delete playlist (OAuth, approval)','add_video_to_playlist':'Add video to playlist (OAuth, approval)',
 'remove_playlist_item':'Remove playlist entry (OAuth, approval)',
 'subscribe_channel':'Subscribe to channel (OAuth, approval)',
 'unsubscribe_channel':'Unsubscribe from channel (OAuth, approval)',
 'add_comment':'Post comment (OAuth, approval)','reply_comment':'Reply to comment (OAuth, approval)',
 'delete_my_comment':'Delete own comment (OAuth, approval)',
 'get_quota_hint':'Get quota guidance and restrictions'
}
