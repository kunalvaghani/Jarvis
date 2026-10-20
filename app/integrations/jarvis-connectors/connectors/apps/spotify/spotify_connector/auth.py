"""Authorization Code + PKCE and OS-keyring token storage. No client secret.

Auth login is an explicitly user-initiated one-time local CLI operation, not a
Jarvis LLM-exposed MCP command. Refresh happens automatically once authorized.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any
from .base import ConnectorError

KEYRING_SERVICE = 'jarvis-spotify-pkce'
DEFAULT_SCOPES = [
 'user-read-playback-state','user-modify-playback-state','user-read-currently-playing',
 'user-read-recently-played','user-top-read','user-library-read','user-library-modify',
 'playlist-read-private','playlist-read-collaborative','playlist-modify-private',
 'playlist-modify-public','user-follow-read','user-follow-modify',
]
TOKEN_URL = 'https://accounts.spotify.com/api/token'
AUTHORIZE_URL = 'https://accounts.spotify.com/authorize'


def pkce_pair() -> tuple[str,str]:
    verifier = secrets.token_urlsafe(72)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode().rstrip('=')
    return verifier, challenge


def redirect_uri(port: int = 8765) -> str:
    if not isinstance(port, int) or isinstance(port,bool) or not 1024 <= port <= 65535:
        raise ConnectorError('Invalid local redirect port')
    return f'http://127.0.0.1:{port}/callback'


def authorization_url(client_id: str, uri: str, state: str, challenge: str, scopes: list[str] | None = None) -> str:
    if not client_id or not state or not challenge:
        raise ConnectorError('Missing Spotify OAuth parameters')
    return AUTHORIZE_URL + '?' + urllib.parse.urlencode({
        'response_type': 'code', 'client_id': client_id, 'redirect_uri': uri,
        'scope': ' '.join(scopes or DEFAULT_SCOPES), 'state':state,
        'code_challenge_method':'S256','code_challenge':challenge,
    })


def exchange(form: dict[str,str], *, timeout: int = 15) -> dict[str, Any]:
    data = urllib.parse.urlencode(form).encode('utf-8')
    req = urllib.request.Request(TOKEN_URL, data=data, headers={'Content-Type':'application/x-www-form-urlencoded'}, method='POST')
    try:
        from .api import NoRedirect
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as resp:
            raw = resp.read(65537)
            if len(raw) > 65536: raise ConnectorError('Authorization response too large')
            result = json.loads(raw)
    except Exception as exc:
        raise ConnectorError(f'Spotify authorization failed ({type(exc).__name__}); re-authorize if needed') from None
    if (not isinstance(result,dict) or not isinstance(result.get('access_token'),str)
            or not 1 <= len(result['access_token']) <= 8192
            or type(result.get('expires_in',3600)) is not int or not 1 <= result.get('expires_in',3600) <= 86400
            or not isinstance(result.get('scope',''),str) or len(result.get('scope','')) > 2000
            or ('refresh_token' in result and (not isinstance(result['refresh_token'],str) or not 1 <= len(result['refresh_token']) <= 8192))):
        raise ConnectorError('Spotify returned an invalid authorization response')
    return result


class KeyringStore:
    """No plaintext fallback. Uses Windows Credential Manager through keyring."""
    def __init__(self, client_id: str):
        self.client_id = client_id
    def _keyring(self):
        try:
            if os.name != 'nt':
                raise ConnectorError('This connector requires Windows Credential Manager for OAuth storage')
            from keyring.backends.Windows import WinVaultKeyring
            keyring = WinVaultKeyring()
        except ImportError:
            raise ConnectorError('Install keyring for protected Spotify tokens: pip install keyring') from None
        return keyring
    def load(self) -> dict[str,Any] | None:
        try:
            s = self._keyring().get_password(KEYRING_SERVICE, self.client_id)
            if s and len(s) > 65536: raise ConnectorError('Stored Spotify authorization is invalid')
            value = json.loads(s) if s else None
            if value is not None and not isinstance(value, dict): raise ConnectorError('Stored Spotify authorization is invalid')
            return value
        except ConnectorError:
            raise
        except Exception:
            raise ConnectorError('Cannot access secure token storage') from None
    def save(self, token: dict[str,Any]) -> None:
        try:
            self._keyring().set_password(KEYRING_SERVICE, self.client_id, json.dumps(token))
        except ConnectorError:
            raise
        except Exception:
            raise ConnectorError('Cannot store tokens securely') from None
    def delete(self) -> None:
        try:
            self._keyring().delete_password(KEYRING_SERVICE, self.client_id)
        except Exception:
            raise ConnectorError('Unable to clear secure token storage') from None


class PKCETokenManager:
    def __init__(self, client_id: str | None = None, store=None):
        self._binding_key = secrets.token_bytes(32)
        self.expected_binding = None
        self.client_id = client_id if client_id is not None else os.environ.get('SPOTIFY_CLIENT_ID','').strip()
        self.store = store if store is not None else (KeyringStore(self.client_id) if self.client_id else None)
    def authenticated(self) -> bool:
        if not self.store:
            return False
        try:
            token = self.store.load()
            return bool(token and (token.get('refresh_token') or (token.get('access_token') and token.get('expires_at',0) > time.time())))
        except ConnectorError:
            raise
    def access_token(self) -> str:
        if not self.client_id or not self.store:
            raise ConnectorError('Spotify API not configured; set SPOTIFY_CLIENT_ID and run auth_login.py')
        token = self.store.load()
        if not token:
            raise ConnectorError('Spotify not authorized; run auth_login.py locally')
        if self.expected_binding is not None and self.expected_binding != self.binding(token):
            raise ConnectorError('Spotify credential changed after approval; no request sent')
        if token.get('expires_at',0) > time.time()+60 and token.get('access_token'):
            return token['access_token']
        if not token.get('refresh_token'):
            raise ConnectorError('Spotify token expired; run auth_login.py again')
        result = exchange({'grant_type':'refresh_token','refresh_token':token['refresh_token'],'client_id':self.client_id})
        result['refresh_token'] = result.get('refresh_token', token['refresh_token'])
        result['scope'] = result.get('scope', token.get('scope',''))
        result['jarvis_account_consent'] = token.get('jarvis_account_consent') is True
        result['expires_at'] = time.time() + int(result.get('expires_in',3600))
        self.store.save(result)
        return result['access_token']
    def refresh_after_401(self) -> str:
        if not self.store or not self.client_id:
            raise ConnectorError('Spotify not authorized')
        token = self.store.load()
        if not token or not token.get('refresh_token'):
            raise ConnectorError('Spotify refresh unavailable')
        if self.expected_binding is not None and self.expected_binding != self.binding(token):
            raise ConnectorError('Spotify credential changed before refresh; no request sent')
        result = exchange({'grant_type':'refresh_token','refresh_token':token['refresh_token'],'client_id':self.client_id})
        result['refresh_token'] = result.get('refresh_token', token['refresh_token'])
        result['scope'] = result.get('scope', token.get('scope',''))
        result['jarvis_account_consent'] = token.get('jarvis_account_consent') is True
        result['expires_at'] = time.time() + int(result.get('expires_in',3600))
        self.store.save(result)
        return result['access_token']

    def binding(self, token=None):
        token = self.store.load() if token is None and self.store else token
        if not token: return ''
        value = token.get('refresh_token') or token.get('access_token') or ''
        return hmac.new(self._binding_key, (self.client_id+'\0'+value).encode(), hashlib.sha256).hexdigest()[:32] if value else ''

    def require_request_scopes(self, method, path, params=None, body=None):
        if not self.store: raise ConnectorError('Spotify API authorization required; run auth_login.py manually')
        token = self.store.load()
        if not isinstance(token, dict) or token.get('jarvis_account_consent') is not True:
            raise ConnectorError('Human account consent required; run auth_login.py manually')
        if self.expected_binding != self.binding(token):
            raise ConnectorError('Spotify account credential changed or has not been approved; approve a fresh call')
        granted = set(str(token.get('scope','')).split())
        required = set()
        if path == '/me/player/currently-playing': required.add('user-read-currently-playing')
        elif path == '/me/player/recently-played': required.add('user-read-recently-played')
        elif path.startswith('/me/player'): required.add('user-read-playback-state' if method == 'GET' else 'user-modify-playback-state')
        elif path.startswith('/me/top/'): required.add('user-top-read')
        elif path == '/me/following': required.add('user-follow-read')
        elif path.startswith('/me/library') or path in {'/me/tracks','/me/albums','/me/shows','/me/episodes'}:
            required.add('user-library-read' if method=='GET' else 'user-library-modify')
            if path=='/me/library' and any(':playlist:' in x for x in str((params or {}).get('uris','')).split(',')):
                required.add('playlist-modify-public')
        elif path == '/me/playlists':
            required.add(('playlist-modify-public' if (body or {}).get('public') else 'playlist-modify-private') if method=='POST' else 'playlist-read-private')
        elif path.startswith('/playlists/') and method != 'GET':
            # Scope/ownership is checked against the actual target before an account write.
            if not granted.intersection({'playlist-modify-private','playlist-modify-public'}):
                raise ConnectorError('Missing Spotify playlist write scope')
        if required - granted: raise ConnectorError('Missing Spotify scope: ' + ', '.join(sorted(required-granted)))

    def require_playlist_scope(self, public):
        token = self.store.load() if self.store else {}
        required = 'playlist-modify-public' if public else 'playlist-modify-private'
        if required not in str((token or {}).get('scope','')).split():
            raise ConnectorError('Missing Spotify scope: '+required)
