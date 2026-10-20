"""Spotify Web API transport; bounded I/O, fixed HTTPS endpoint, token redaction.

Spotify command errors raise, so Jarvis never mistakes a failed action for success.
Retries are bounded and restricted to read-only requests (except 401 auth refresh).
"""
from __future__ import annotations
import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from .base import ConnectorError

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConnectorError('Spotify redirect refused')

HTTP_OPENER = urllib.request.build_opener(NoRedirect)

API_ORIGIN = 'https://api.spotify.com/v1'
MAX_RESPONSE = 2_000_000

class SpotifyAPIError(ConnectorError):
    def __init__(self, status: int, message: str, retry_after: int | None = None):
        self.status = status
        self.retry_after = retry_after
        if status == 401:
            message = 'Unauthorized: login or token scopes may need refreshing'
        elif status == 403:
            message = 'Forbidden: Spotify Premium, app allowlisting, scopes, ownership or regional rights may be required'
        elif status == 429:
            message = 'Rate-limited by Spotify; retry later'
        elif status >= 500:
            message = 'Spotify service temporarily unavailable'
        else:
            message = 'request rejected; inspect configuration and permissions'
        super().__init__(f'Spotify API HTTP {status}: {message[:180]}')


def _sync_http(method: str, url: str, body: bytes | None, token: str, timeout: int) -> tuple[int, Any]:
    headers = {'Authorization': 'Bearer ' + token, 'Accept':'application/json'}
    if body is not None:
        headers['Content-Type']='application/json'
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with HTTP_OPENER.open(req, timeout=timeout) as r:
            data = r.read(MAX_RESPONSE+1)
            status = r.status
    except urllib.error.HTTPError as exc:
        retry = exc.headers.get('Retry-After') if exc.headers else None
        retry_int = min(int(retry), 60) if retry and retry.isdigit() else None
        raise SpotifyAPIError(exc.code, 'request rejected', retry_after=retry_int) from None
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        raise ConnectorError(f'Spotify network request failed: {type(exc).__name__}') from None
    if len(data) > MAX_RESPONSE:
        raise ConnectorError('Spotify response too large')
    if not data:
        return status, None
    try:
        def invalid_constant(value): raise ValueError('Non-finite JSON number')
        return status, json.loads(data, parse_constant=invalid_constant)
    except (ValueError,UnicodeError,RecursionError):
        raise ConnectorError('Invalid Spotify JSON response') from None

class SpotifyAPI:
    def __init__(self, token_manager, transport=None):
        self.auth = token_manager
        self.transport = transport or _sync_http
        self._last_request = 0.0
        self._min_interval = 0.08
        self._rate_lock = asyncio.Lock()

    async def request(self, method: str, path: str, *, params: dict | None = None, json_body: dict | None = None) -> Any:
        if method not in ('GET','POST','PUT','DELETE') or not isinstance(path,str) or not path.startswith('/') or path.startswith('//') or '://' in path or '?' in path or '..' in path or '%' in path or '#' in path or any(ord(c) < 32 for c in path) or '\\' in path:
            raise ConnectorError('Disallowed API request path/method')
        url = API_ORIGIN + path
        if params:
            clean = {k:v for k,v in params.items() if v is not None}
            if clean:
                url += '?' + urllib.parse.urlencode(clean)
        body = json.dumps(json_body,separators=(',',':')).encode() if json_body is not None else None
        token = await asyncio.to_thread(self.auth.access_token)
        async with self._rate_lock:
            delay = max(0, self._min_interval-(time.monotonic()-self._last_request))
            if delay: await asyncio.sleep(delay)
            self._last_request = time.monotonic()
        for attempt in range(2):
            try:
                _status, result = await asyncio.to_thread(self.transport, method,url,body,token,12)
                return result
            except SpotifyAPIError as exc:
                if exc.status == 401 and attempt == 0:
                    token = await asyncio.to_thread(self.auth.refresh_after_401)
                    continue
                # Only retry reads; mutating requests must not execute twice accidentally.
                if method == 'GET' and attempt == 0 and ((exc.status==429 and exc.retry_after is not None and exc.retry_after <= 3) or exc.status in (502,503,504)):
                    await asyncio.sleep(exc.retry_after if exc.status==429 else 0.3)
                    continue
                raise
        raise ConnectorError('Spotify request attempts exhausted')
