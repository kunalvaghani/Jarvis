"""Optional per-app Windows WASAPI volume via Pycaw.
Does not change master/system volume or volume of unrelated processes.
"""
from .base import ConnectorError, UnsupportedAction
from .identifiers import bounded

class WindowsSpotifyVolume:
    def __init__(self, sessions_provider=None):
        self.sessions_provider=sessions_provider

    def _sessions(self):
        if self.sessions_provider:
            sessions=self.sessions_provider()
        else:
            try:
                from jarvis.spotify import _audio_sessions
                sessions=_audio_sessions()
            except (ImportError,OSError):
                raise UnsupportedAction('Install pycaw on Windows for local Spotify volume') from None
        matches=[]
        for s in sessions:
            try:
                if s.Process and s.Process.name().casefold()=='spotify.exe' and s.SimpleAudioVolume:
                    matches.append(s.SimpleAudioVolume)
            except (OSError,AttributeError):
                continue
        if not matches:
            raise UnsupportedAction('No Spotify-specific Windows audio session found')
        return matches

    def status(self):
        matches=self._sessions()
        values=[int(round(v.GetMasterVolume()*100)) for v in matches]
        muted=[bool(v.GetMute()) for v in matches]
        return {'ok':True,'source':'windows_per_app_audio','volume_percent':values,
                'muted':muted,'session_count':len(values)}

    def volume(self,percent:int):
        val=bounded(percent,'percent',0,100)
        matches=self._sessions()
        for v in matches:
            try:v.SetMasterVolume(val/100,None)
            except Exception:raise ConnectorError('Spotify per-app volume change failed') from None
        actual=self.status()
        return {'ok':all(abs(p-val)<=1 for p in actual['volume_percent']),
                'accepted':True,'verified':all(abs(p-val)<=1 for p in actual['volume_percent']),
                'source':'windows_per_app_audio','requested_percent':val,'observed':actual}

    def mute(self,enabled:bool):
        if not isinstance(enabled,bool):raise ConnectorError('enabled must be boolean')
        matches=self._sessions()
        for v in matches:
            try:v.SetMute(int(enabled),None)
            except Exception:raise ConnectorError('Spotify per-app mute change failed') from None
        actual=self.status()
        return {'ok':all(x==enabled for x in actual['muted']),
                'accepted':True,'verified':all(x==enabled for x in actual['muted']),
                'source':'windows_per_app_audio','observed':actual}
