"""Optional Windows local Spotify control via official OS media-session API.
Never sends media keys to an arbitrary foreground app or controls other sessions.
Requires `winsdk` on Windows and Spotify to expose a media session.
"""
from __future__ import annotations
import os
import asyncio
from .base import ConnectorError, UnsupportedAction
from .identifiers import spotify_uri

class WindowsSpotify:
    def __init__(self, session_provider=None, opener=None):
        self.session_provider = session_provider
        self.opener = opener
        self._manager = None

    async def _session(self):
        if self.session_provider:
            sessions = await self.session_provider()
        else:
            if os.name != 'nt':
                raise UnsupportedAction('Windows media control requires Windows')
            try:
                from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
            except ImportError:
                raise UnsupportedAction('Install winrt-Windows.Media.Control to use Windows media controls') from None
            try:
                if self._manager is None:
                    self._manager = await Manager.request_async()
                sessions = self._manager.get_sessions()
            except Exception:
                raise ConnectorError('Windows media session discovery failed') from None
        spotify = [s for s in sessions if str(s.source_app_user_model_id).casefold() in {'spotify.exe','spotify','spotifyab.spotifymusic_zpdnekdrzrea0!spotify'}]
        if len(spotify) != 1:
            raise UnsupportedAction('Expected exactly one Spotify media session; found ' + str(len(spotify)))
        return spotify[0]

    async def status(self):
        return await self._state(await self._session())

    async def _state(self, s):
        try:
            props = await s.try_get_media_properties_async()
            info = s.get_playback_info()
            timeline = s.get_timeline_properties()
            return {'ok':True,'source':'windows_gsmtc','spotify_session':True,
                    'title':str(props.title or ''), 'artist':str(props.artist or ''),
                    'album':str(props.album_title or ''),
                    'playback_status':str(getattr(info.playback_status, 'name', info.playback_status)).lower(),
                    'position_ms':int(timeline.position.total_seconds()*1000)}
        except Exception:
            raise ConnectorError('Spotify local playback information unavailable') from None

    async def action(self, name: str, value=None):
        s = await self._session()
        methods = {'play':'try_play_async','pause':'try_pause_async',
                   'next':'try_skip_next_async','previous':'try_skip_previous_async',
                   'stop':'try_stop_async','toggle':'try_toggle_play_pause_async'}
        if name == 'seek':
            if not isinstance(value,int) or isinstance(value,bool) or value < 0 or value > 86_400_000:
                raise ConnectorError('Invalid seek position')
            method = 'try_change_playback_position_async'
            args = (value * 10_000,) # WinRT ticks = 100ns
        elif name == 'shuffle':
            if not isinstance(value,bool): raise ConnectorError('shuffle requires boolean')
            method = 'try_change_shuffle_active_async'; args = (value,)
        elif name == 'repeat':
            if value not in {'off','track','context'}: raise ConnectorError('Invalid repeat mode')
            from winrt.windows.media import MediaPlaybackAutoRepeatMode
            method='try_change_auto_repeat_mode_async'
            args=({'off':MediaPlaybackAutoRepeatMode.NONE,'track':MediaPlaybackAutoRepeatMode.TRACK,'context':MediaPlaybackAutoRepeatMode.LIST}[value],)
        elif name in methods:
            method=methods[name]; args=()
        else:
            raise UnsupportedAction('Unsupported local Spotify action')
        try:
            accepted = await getattr(s, method)(*args)
        except (AttributeError, NotImplementedError):
            raise UnsupportedAction('Spotify does not expose this local control') from None
        except Exception:
            raise ConnectorError(f'Windows Spotify {name} control failed') from None
        if not accepted:
            raise UnsupportedAction('Spotify media session rejected the control')
        verified = False
        observed = None
        # Only observations may repeat. Transport commands above are sent exactly once.
        for _ in range(3):
            try:
                await asyncio.sleep(.08)
                observed = await self._state(s)
                state = observed.get('playback_status')
                if name in {'play','pause','stop'}:
                    verified = state == {'play':'playing','pause':'paused','stop':'stopped'}[name]
                elif name == 'seek':
                    verified = abs(observed.get('position_ms',-999999)-value) <= 1500
                if verified: break
            except Exception:
                break  # Accepted remains accepted; missing readback is never a retry instruction.
        return {'ok':True,'accepted':True,'source':'windows_gsmtc','verified':verified,
                'playing_verified':bool(verified and name=='play'),
                'status':'playing_verified' if verified and name=='play' else 'verified' if verified else 'accepted',
                'action':name,'observed':observed}

    async def open(self, value: str | None = None):
        target = spotify_uri(value) if value else 'spotify:'
        if self.opener:
            self.opener(target)
        else:
            if os.name != 'nt' or not hasattr(os, 'startfile'):
                raise UnsupportedAction('Spotify desktop deep linking is supported only on Windows')
            try:
                os.startfile(target)
            except OSError:
                raise ConnectorError('Unable to launch Spotify desktop app') from None
        return {'ok':True,'opened_requested':True,'status':'opened_requested','playing_verified':False,'target':target,'source':'desktop_deep_link'}

    async def search(self, query: str):
        from urllib.parse import quote
        if not isinstance(query,str) or not 1 <= len(query.strip()) <= 160:
            raise ConnectorError('search query must be 1..160 characters')
        target='spotify:search:'+quote(query.strip(), safe='')
        if self.opener:
            self.opener(target)
        else:
            if os.name != 'nt' or not hasattr(os,'startfile'):
                raise UnsupportedAction('Desktop search opening requires Windows')
            try: os.startfile(target)
            except OSError: raise ConnectorError('Spotify desktop search could not be opened') from None
        return {'ok':True,'source':'desktop_deep_link','search_opened':True,'results_extracted':False,'query':query.strip()}
