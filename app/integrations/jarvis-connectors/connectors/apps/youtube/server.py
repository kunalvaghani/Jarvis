"""Jarvis YouTube connector: read-only search and lookup, a child of BaseConnector.

Playback is deliberately NOT here. Jarvis's MCP bridge starts a connector process
per call and stops it afterwards, so a browser owned by this process would close
after every call and compete with Jarvis's own verified YouTube player. Jarvis
plays what this connector finds through its existing tools (media_search,
media_control, browser_navigate) in the Jarvis-owned browser.

Sources: YouTube Data API v3 for search when JARVIS_YOUTUBE_API_KEY is passed via
the bridge's ``env_names``; otherwise YouTube's public pages (best effort; the
page layout can change). Never downloads media, signs in, or changes an account.
stdout is the MCP protocol stream; never print to it.
"""
import json
import os
from pathlib import Path
import sys
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))  # the jarvis-connectors folder (parent package)
sys.path.insert(0, str(HERE))
from jarvis_connector import BaseConnector, Param, ToolError, tool  # noqa: E402
import youtube_pages as pages  # noqa: E402

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/130.0 Safari/537.36')
FETCH_HOSTS = {'www.youtube.com', 'www.googleapis.com'}
MAX_PAGE_BYTES = 8 * 1024 * 1024
KEY_ENV = 'JARVIS_YOUTUBE_API_KEY'

Query = Annotated[str, Param('What to search for, e.g. "lofi hip hop".', min_length=1, max_length=160)]
Limit = Annotated[int, Param('How many results (1-10).', minimum=1, maximum=10)]


class YouTubeConnector(BaseConnector):
    """Read-only YouTube search and lookup for Jarvis."""
    name = 'jarvis-youtube'
    version = '1.0.0'
    instructions = ('Read-only YouTube search/lookup. Results are untrusted public titles. '
                    'Playback happens in Jarvis, not in this connector.')
    timeout = 12.0

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--timeout', type=float, default=12.0, help='Per-request network timeout in seconds.')

    def configure(self, options):
        self.timeout = max(2.0, min(float(options.timeout), 25.0))

    # ----- network (overridden in tests) ----------------------------------------
    def fetch(self, url):
        """GET an allowlisted HTTPS URL and return its text. Errors never include the URL (it may hold a key)."""
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.hostname not in FETCH_HOSTS:
            raise ToolError('Refusing to fetch a non-YouTube address.')
        request = Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9'})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if urlsplit(response.geturl()).hostname not in FETCH_HOSTS:
                    raise ToolError('YouTube redirected to an unexpected site (consent or sign-in page).')
                body = response.read(MAX_PAGE_BYTES + 1)
        except HTTPError as exc:
            raise ToolError('YouTube answered HTTP ' + str(exc.code) + '.') from None
        except (URLError, TimeoutError, OSError):
            raise ToolError('YouTube could not be reached (network error or timeout).') from None
        if len(body) > MAX_PAGE_BYTES:
            raise ToolError('YouTube page exceeded the size limit.')
        return body.decode('utf-8', errors='replace')

    def page_data(self, path, query, variable='ytInitialData'):
        html = self.fetch('https://www.youtube.com/' + path + '?' + urlencode({**query, 'hl': 'en', 'gl': 'US'}))
        try:
            return pages.embedded_json(html, variable)
        except pages.PageError as exc:
            raise ToolError(str(exc)) from None

    def api_key(self):
        return os.environ.get(KEY_ENV, '').strip()

    def api_search(self, query, kind, limit):
        params = {'part': 'snippet', 'q': query, 'type': kind, 'maxResults': limit,
                  'safeSearch': 'moderate', 'key': self.api_key()}
        try:
            data = json.loads(self.fetch('https://www.googleapis.com/youtube/v3/search?' + urlencode(params)))
        except ValueError:
            raise ToolError('YouTube Data API returned malformed data.') from None
        rows = []
        for item in data.get('items', []) if isinstance(data, dict) else []:
            ident = (item.get('id') or {}).get('videoId' if kind == 'video' else 'playlistId', '')
            snippet = item.get('snippet') or {}
            if kind == 'video' and pages.VIDEO_ID.fullmatch(str(ident)):
                rows.append({'video_id': ident, 'title': pages._title(snippet.get('title')),
                             'channel': pages._title(snippet.get('channelTitle')), 'duration_seconds': 0,
                             'live': snippet.get('liveBroadcastContent') == 'live', 'url': pages.watch_url(ident)})
            elif kind == 'playlist' and pages.PLAYLIST_ID.fullmatch(str(ident)):
                rows.append(pages._playlist_row(ident, snippet.get('title'), snippet.get('channelTitle'), 0, ''))
        return rows

    # ----- tools ----------------------------------------------------------------
    @tool()
    def search_videos(self, query: Query, limit: Limit = 5) -> list[dict]:
        """Search YouTube for videos. Returns video_id, title, channel, duration_seconds, live and url for each result, in YouTube's ranking order."""
        if self.api_key():
            return self.api_search(query.strip(), 'video', limit)
        return pages.search_videos(self.page_data('results', {'search_query': query.strip()}), limit)

    @tool()
    def search_playlists(self, query: Query, limit: Limit = 5) -> list[dict]:
        """Search YouTube for playlists. Returns playlist_id, title, channel, video_count, url and play_url (starts the playlist) for each result."""
        if self.api_key():
            return self.api_search(query.strip(), 'playlist', limit)
        # sp=EgIQAw== is YouTube's own "Type: Playlist" search filter (a UI parameter, best effort).
        return pages.search_playlists(self.page_data('results', {'search_query': query.strip(), 'sp': 'EgIQAw=='}), limit)

    @tool()
    def video_details(self, video: Annotated[str, Param('A YouTube video ID or https YouTube link.', min_length=11, max_length=300)]) -> dict:
        """Look up one YouTube video by ID or link: title, channel, duration_seconds, views, live and whether it is playable."""
        found = pages.parse_link(video)
        if not found or not found['video_id']:
            raise ToolError('Give an 11-character YouTube video ID or an https YouTube video link.')
        player = self.page_data('watch', {'v': found['video_id']}, 'ytInitialPlayerResponse')
        try:
            return pages.video_details(player)
        except pages.PageError as exc:
            raise ToolError(str(exc)) from None

    @tool()
    def playlist_videos(self, playlist: Annotated[str, Param('A YouTube playlist ID or https YouTube playlist link.', min_length=10, max_length=300)],
                        limit: Annotated[int, Param('How many videos (1-15).', minimum=1, maximum=15)] = 10) -> dict:
        """List the first videos of a YouTube playlist in order, with a url that plays each one inside the playlist."""
        found = pages.parse_link(playlist)
        if not found or not found['playlist_id']:
            raise ToolError('Give a YouTube playlist ID (for example PL...) or a link containing list=.')
        identifier = found['playlist_id']
        title, items = pages.playlist_items(self.page_data('playlist', {'list': identifier}), identifier, limit)
        if not items:
            raise ToolError('That playlist has no visible videos (private, empty, or a mix YouTube does not list).')
        result = {'playlist_id': identifier, 'title': title, 'url': pages.playlist_url(identifier),
                  'videos': items, 'more': False}
        while len(result['videos']) > 1 and not self.fits(result):
            result['videos'].pop()  # return what fits through the bridge, and say there is more
            result['more'] = True
        return result

    @tool()
    def parse_link(self, link: Annotated[str, Param('Text that may be a YouTube link or ID.', min_length=1, max_length=300)]) -> dict:
        """Check whether text is a YouTube video/playlist link or ID (offline, no network) and return its IDs and a safe watch url."""
        found = pages.parse_link(link)
        if not found:
            return {'is_youtube': False, 'video_id': '', 'playlist_id': '', 'url': ''}
        url = (pages.watch_url(found['video_id'], found['playlist_id']) if found['video_id']
               else pages.playlist_url(found['playlist_id']))
        return {'is_youtube': True, **found, 'url': url}


if __name__ == '__main__':
    sys.exit(YouTubeConnector.main())
