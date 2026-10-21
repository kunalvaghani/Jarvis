"""Official YouTube Data API client; no scraping of private or undocumented endpoints.

API keys are restricted to read-only public data. Private reads/writes require the
user's explicit OAuth grant and the correct OAuth scopes. Network operations stay
off the event loop. Application must enforce approval for external mutations.
"""
from __future__ import annotations
import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError, URLError
from .base import ConnectorError

YT_BASE = 'https://www.googleapis.com/youtube/v3/'
SAFE_RESOURCE = re.compile(r'^(?:[a-zA-Z][a-zA-Z0-9]*|videos/(?:getRating|rate))$')
SAFE_ID = re.compile(r'^[A-Za-z0-9_-]{1,150}$')
RESOURCES = {'captions', 'channels', 'comments', 'commentThreads', 'playlistItems',
             'playlists', 'search', 'subscriptions', 'videoCategories', 'videos',
             'videos/getRating', 'videos/rate'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConnectorError('YouTube API redirect refused; credentials were not forwarded')

class YouTubeDataAPI:
    def __init__(self, key: str = '', token: str = '', token_path: str = ''):
        self.key = key or os.environ.get('YOUTUBE_DATA_API_KEY', '')
        self.token = token or os.environ.get('YOUTUBE_OAUTH_ACCESS_TOKEN', '')
        configured_path = token_path or os.environ.get('YOUTUBE_OAUTH_TOKEN_PATH', '')
        self.token_path = Path(configured_path) if configured_path else Path.home()/'.jarvis'/'youtube-oauth-token.json'

    def _oauth_token(self) -> str:
        if self.token:
            return self.token
        if not self.token_path.is_file():
            raise ConnectorError('OAuth required. Run auth_login.py, then retry. Do not supply credentials in Jarvis chat.')
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as AuthRequest
        except ImportError as exc:
            raise ConnectorError('OAuth dependencies missing: pip install google-auth google-auth-oauthlib') from exc
        creds = Credentials.from_authorized_user_file(str(self.token_path))
        if not creds.valid:
            if not creds.refresh_token:
                raise ConnectorError('OAuth token expired without refresh permission. Run auth_login.py.')
            creds.refresh(AuthRequest())
            self.token_path.write_text(creds.to_json(), encoding='utf8')
            try: os.chmod(self.token_path, 0o600)
            except OSError: pass
        if not creds.token:
            raise ConnectorError('OAuth token unavailable')
        return creds.token

    @staticmethod
    def _fetch(url: str, *, method: str = 'GET', body: dict | None = None, token: str = '') -> dict:
        headers = {'Accept': 'application/json'}
        if token: headers['Authorization'] = 'Bearer ' + token
        data = None
        if body is not None:
            headers['Content-Type'] = 'application/json; charset=utf-8'
            data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=18) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ConnectorError('YouTube API response exceeds two megabytes')
                return json.loads(raw) if raw else {'ok': True, 'http_status': response.status}
        except HTTPError as exc:
            try:
                info = json.loads(exc.read(20000))
                err = info.get('error', {})
                reasons = [item.get('reason') for item in err.get('errors', []) if isinstance(item, dict)] if isinstance(err, dict) else []
            except Exception: reasons = []
            outcome = ('quota_exhausted' if any(r in {'quotaExceeded','dailyLimitExceeded'} for r in reasons)
                       else 'blocked_by_auth' if exc.code == 401
                       else 'retriable' if exc.code == 429 or exc.code >= 500 else 'failed')
            # Never reflect response text or request URLs: either can contain credentials.
            raise ConnectorError(f'YouTube API HTTP {exc.code}: {outcome}; inspect before retrying writes') from None
        except (URLError, TimeoutError, ValueError) as exc:
            raise ConnectorError(f'YouTube API connection/format error: {type(exc).__name__}') from exc

    async def request(self, resource: str, *, method: str = 'GET', params: dict | None = None,
                      body: dict | None = None, oauth: bool = False) -> dict:
        if resource not in RESOURCES:
            raise ConnectorError('Invalid API resource')
        if method not in {'GET','POST','PUT','DELETE'}:
            raise ConnectorError('Invalid API method')
        params = {k:v for k,v in (params or {}).items() if v is not None}
        if not oauth and method != 'GET':
            raise ConnectorError('Account-changing requests require OAuth')
        if not oauth and not self.key:
            raise ConnectorError('Read-only YouTube API needs YOUTUBE_DATA_API_KEY')
        token = await asyncio.to_thread(self._oauth_token) if oauth else ''
        if not oauth: params['key'] = self.key
        url = YT_BASE + resource + ('?' + urlencode(params, doseq=True) if params else '')
        return await asyncio.to_thread(self._fetch, url, method=method, body=body, token=token)
