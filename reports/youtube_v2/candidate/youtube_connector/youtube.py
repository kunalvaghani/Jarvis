"""YouTube child connector using browser UI + optional official Data API search.

No download, stream extraction, secret access, or undocumented YouTube JSON API.
The browser context is dedicated to this connector and never reuses Chrome's
real user profile by default. The injected `page` parameter supports Jarvis's
existing browser automation service without owning its lifecycle.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

from .base import ConnectorError, ConnectorInfo, UnsupportedAction

VIDEO_ID = re.compile(r"^[a-zA-Z0-9_-]{11}$")
PLAYLIST_ID = re.compile(r"^[a-zA-Z0-9_-]{10,128}$")
SEARCH_KIND = Literal["video", "playlist"]


def extract_id(value: str, kind: SEARCH_KIND) -> str | None:
    """Extract only YouTube identifiers, never navigate to user-supplied hosts."""
    value = value.strip()
    if kind == "video" and VIDEO_ID.fullmatch(value):
        return value
    if kind == "playlist" and PLAYLIST_ID.fullmatch(value) and value.startswith(("PL", "UU", "LL", "WL", "RD", "OLAK", "FL")):
        return value
    try:
        url = urlsplit(value)
    except ValueError:
        return None
    if url.scheme != "https":
        return None
    host = (url.hostname or "").lower()
    if host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"} or url.username or url.password:
        return None
    try:
        if url.port not in (None, 443):
            return None
    except ValueError:
        return None
    qs = parse_qs(url.query)
    if kind == "playlist":
        if url.path not in {"/watch", "/playlist", "/embed/videoseries"}:
            return None
        identifier = qs.get("list", [""])[0]
    elif host == "youtu.be":
        identifier = url.path.lstrip("/").split("/")[0]
    elif url.path == "/watch":
        identifier = qs.get("v", [""])[0]
    elif url.path.startswith("/shorts/"):
        identifier = url.path.split("/")[2]
    elif re.fullmatch(r'/embed/[A-Za-z0-9_-]{11}', url.path):
        identifier = url.path.split('/')[2]
    else:
        identifier = ""
    check = PLAYLIST_ID if kind == "playlist" else VIDEO_ID
    return identifier if check.fullmatch(identifier) else None


def youtube_watch_url(video_id: str, playlist_id: str | None = None) -> str:
    q = {"v": video_id}
    if playlist_id:
        q["list"] = playlist_id
    return "https://www.youtube.com/watch?" + urlencode(q)


class YouTubeConnector:
    """App-specific child exposing the YouTube media control contract."""

    def require_text(self, value: str, label: str, limit: int = 200) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ConnectorError(f'{label} must be a nonempty string')
        value = value.strip()
        if len(value) > limit:
            raise ConnectorError(f'{label} too long (maximum {limit} characters)')
        return value

    def __init__(self, page: Any | None = None, profile_dir: str | None = None,
                 api_key: str | None = None) -> None:
        self._page = page
        self._external_page = page is not None
        self._pw = None
        self._context = None
        self._profile_dir = Path(profile_dir or os.environ.get("JARVIS_YOUTUBE_PROFILE", "")).expanduser() if (profile_dir or os.environ.get("JARVIS_YOUTUBE_PROFILE")) else Path.home() / ".jarvis" / "youtube-playwright-profile"
        self._api_key = api_key if api_key is not None else os.environ.get("YOUTUBE_DATA_API_KEY", "")
        self._lock = asyncio.Lock()

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="YouTube", version="0.1.0", namespace="youtube",
            capabilities=("search_videos", "search_playlists", "play_video", "play_playlist",
                          "pause", "resume", "next_video", "previous_video", "get_status"),
        )

    async def connect(self) -> None:
        if self._page is not None:
            return
        raise UnsupportedAction('Chrome Default profile only: inject the accepted Jarvis profile adapter; no separate browser is launched')

    async def close(self) -> None:
        if not self._external_page:
            if self._context is not None:
                await self._context.close()
            if self._pw is not None:
                await self._pw.stop()
        self._context = None
        self._pw = None
        self._page = None if not self._external_page else self._page

    async def health(self) -> dict[str, Any]:
        return {"connector": "youtube", "browser_connected": bool(self._page),
                "api_search_enabled": bool(self._api_key), "capabilities": list(self.info.capabilities)}

    async def _navigate(self, url: str) -> None:
        await self.connect()
        assert self._page is not None
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        current = urlsplit(self._page.url)
        if current.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
            raise ConnectorError("Unexpected navigation outside YouTube; refusing action")

    def _api_search_sync(self, query: str, kind: SEARCH_KIND, limit: int) -> list[dict[str, str]]:
        params = {"part": "snippet", "type": kind, "q": query, "maxResults": limit,
                  "key": self._api_key, "safeSearch": "moderate"}
        url = "https://www.googleapis.com/youtube/v3/search?" + urlencode(params)
        try:
            with urlopen(url, timeout=12) as r:
                data = json.load(r)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise ConnectorError(f"Official YouTube search failed: {type(exc).__name__}") from exc
        key = "videoId" if kind == "video" else "playlistId"
        out: list[dict[str, str]] = []
        for item in data.get("items", []):
            ident = item.get("id", {}).get(key, "")
            valid = VIDEO_ID if kind == "video" else PLAYLIST_ID
            if not valid.fullmatch(ident):
                continue
            url = youtube_watch_url(ident) if kind == "video" else "https://www.youtube.com/playlist?" + urlencode({"list": ident})
            out.append({"id": ident, "title": item.get("snippet", {}).get("title", ""), "url": url})
        return out

    async def _browser_search(self, query: str, kind: SEARCH_KIND, limit: int) -> list[dict[str, str]]:
        # YouTube search UI, not an undocumented internal API. Filters/DOM can
        # change. When structured extraction fails, return a usable search page.
        from urllib.parse import quote
        base = "https://www.youtube.com/results?search_query=" + quote(query)
        # The playlist-filter token is a YouTube UI parameter, not a supported
        # public API contract. If it changes, a search page remains useful.
        search_url = base + ("&sp=EgIQAw%3D%3D" if kind == "playlist" else "")
        await self._navigate(search_url)
        assert self._page is not None
        selector = ('ytd-playlist-renderer a[href*="list="], '
                    'ytd-radio-renderer a[href*="list="]') if kind == "playlist" else (
                    'ytd-video-renderer a#video-title, '
                    'ytd-rich-item-renderer a#video-title-link')
        try:
            await self._page.locator(selector).first.wait_for(state="attached", timeout=8_000)
        except Exception:
            return [{"id": "", "title": f"Open {kind} search results", "url": search_url}]
        rows = []
        seen: set[str] = set()
        loc = self._page.locator(selector)
        for i in range(min(await loc.count(), 100)):
            a = loc.nth(i)
            href = await a.get_attribute("href") or ""
            ident = extract_id("https://www.youtube.com" + href if href.startswith("/") else href, kind)
            if not ident or ident in seen:
                continue
            seen.add(ident)
            title = (await a.get_attribute("title") or "").strip()
            if not title:
                title = (await a.inner_text()).strip().split("\n")[0]
            url = youtube_watch_url(ident) if kind == "video" else "https://www.youtube.com/playlist?list=" + ident
            rows.append({"id": ident, "title": title or f"YouTube {kind} {ident}", "url": url})
            if len(rows) >= limit:
                break
        return rows or [{"id": "", "title": f"Open {kind} search results", "url": search_url}]

    async def _search(self, query: str, kind: SEARCH_KIND, limit: int = 5) -> dict[str, Any]:
        query = self.require_text(query, "search query", limit=160)
        if not 1 <= limit <= 10:
            raise ConnectorError("limit must be 1..10")
        async with self._lock:
            if self._api_key:
                items = await asyncio.to_thread(self._api_search_sync, query, kind, limit)
                source = "youtube_data_api"
            else:
                items = await self._browser_search(query, kind, limit)
                source = "youtube_browser"
            return {"ok": True, "query": query, "kind": kind, "source": source, "results": items}

    async def search_videos(self, query: str, limit: int = 5) -> dict[str, Any]:
        return await self._search(query, "video", limit)

    async def search_playlists(self, query: str, limit: int = 5) -> dict[str, Any]:
        return await self._search(query, "playlist", limit)

    async def _resolve(self, value: str, kind: SEARCH_KIND) -> str:
        value = self.require_text(value, kind, 250)
        ident = extract_id(value, kind)
        if ident:
            return ident
        if value.startswith(("http://", "https://")):
            raise ConnectorError("Only YouTube HTTPS links or exact IDs are supported")
        search = self._api_search_sync(value, kind, 5) if self._api_key else None
        if search is None:
            search_response = await self._browser_search(value, kind, 5)
            search = search_response
        if not search or not search[0].get("id"):
            raise ConnectorError(f"No verified {kind} result found; open search and choose a result")
        return search[0]["id"]

    async def _attempt_start_unlocked(self) -> bool:
        """Best-effort autoplay with truthful observed state; caller holds lock."""
        try:
            state = await self._video_state()
            if state.get('ad'):
                return False
            if state["paused"]:
                await self._page.locator(".html5-video-player .ytp-play-button").click(timeout=4_000)
            await self._page.wait_for_function(
                "start => { const v=document.querySelector('video.html5-main-video'); return v && !document.querySelector('.ad-showing') && !v.paused && v.readyState>=3 && v.currentTime>start+.1; }",
                arg=state['current_time'],
                timeout=5_000,
            )
            return True
        except Exception:
            return False

    async def play_video(self, video: str) -> dict[str, Any]:
        """Open a YouTube video by link, ID, or text search; start playback if allowed."""
        async with self._lock:
            ident = await self._resolve(video, "video")
            await self._navigate(youtube_watch_url(ident))
            started = await self._attempt_start_unlocked()
            return {"ok": True, "opened": True, "playing_verified": started,
                    "video_id": ident, "url": self._page.url,
                    "note": "Playback not verified; consent or user interaction may be required." if not started else "Playback started."}

    async def play_playlist(self, playlist: str) -> dict[str, Any]:
        """Open and start the first entry of a YouTube playlist."""
        async with self._lock:
            ident = await self._resolve(playlist, "playlist")
            await self._navigate("https://www.youtube.com/playlist?list=" + ident)
            first_link = self._page.locator('ytd-playlist-video-renderer a#video-title').first
            try:
                await first_link.wait_for(state="attached", timeout=10_000)
                href = await first_link.get_attribute("href") or ""
                first_id = extract_id("https://www.youtube.com" + href if href.startswith("/") else href, "video")
                if not first_id:
                    raise ConnectorError("Cannot identify first video in playlist")
                await self._navigate(youtube_watch_url(first_id, ident))
                started = await self._attempt_start_unlocked()
                return {"ok": True, "opened": True, "playing_verified": started,
                        "playlist_id": ident, "video_id": first_id, "url": self._page.url,
                        "note": "Playback not verified; user interaction may be required." if not started else "Playlist playing."}
            except ConnectorError:
                raise
            except Exception as exc:
                raise ConnectorError("Playlist found but first playable item could not be identified") from exc

    async def _video_state(self) -> dict[str, Any]:
        await self.connect()
        if urlsplit(self._page.url).hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
            raise UnsupportedAction("Active page is not YouTube")
        try:
            return await self._page.locator("video.html5-main-video").evaluate("""v => ({paused: v.paused, current_time: v.currentTime, duration: Number.isFinite(v.duration) ? v.duration : null,
              ready_state:v.readyState,ad:!!document.querySelector('.ad-showing'),buffering:!v.paused&&v.readyState<3,
              video_id:new URL(location.href).searchParams.get('v')})""")
        except Exception as exc:
            raise UnsupportedAction("No accessible YouTube video element in active page") from exc

    async def _set_playback(self, play: bool) -> dict[str, Any]:
        async with self._lock:
            state = await self._video_state()
            desired_paused = not play
            if state["paused"] != desired_paused:
                try:
                    await self._page.locator(".html5-video-player .ytp-play-button").click(timeout=5000)
                    await self._page.wait_for_function(
                        "wanted => { const v=document.querySelector('video.html5-main-video'); return v && v.paused === wanted; }",
                        arg=desired_paused, timeout=5000,
                    )
                except Exception as exc:
                    raise ConnectorError("YouTube playback state could not be verified after control") from exc
            return {"ok": True, "action": "resume" if play else "pause", "paused": desired_paused, "url": self._page.url}

    async def pause(self) -> dict[str, Any]:
        return await self._set_playback(False)

    async def resume(self) -> dict[str, Any]:
        return await self._set_playback(True)

    async def _skip(self, direction: Literal["next", "previous"]) -> dict[str, Any]:
        async with self._lock:
            await self._video_state()
            previous_id = extract_id(self._page.url, "video")
            current_url = self._page.url
            playlist_id = extract_id(current_url, "playlist")
            if direction == "previous" and not playlist_id:
                raise UnsupportedAction("Previous video is supported only while playing a YouTube playlist")
            # Blur text fields to avoid typing shortcuts into the search box.
            await self._page.evaluate("() => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); }")
            await self._page.keyboard.press("Shift+N" if direction == "next" else "Shift+P")
            try:
                await self._page.wait_for_function(
                    "old => { const u=new URL(location.href); return u.searchParams.get('v') !== old; }",
                    arg=previous_id, timeout=7000,
                )
            except Exception as exc:
                # Playlist previous on the first item may seek to 0 without URL change.
                if direction == "previous":
                    state = await self._video_state()
                    if state["current_time"] <= 2:
                        return {"ok": True, "action": "previous", "note": "Restarted first playlist item", "url": self._page.url}
                raise ConnectorError(f"{direction} action did not cause a verified transition") from exc
            return {"ok": True, "action": direction, "url": self._page.url,
                    "video_id": extract_id(self._page.url, "video")}

    async def next_video(self) -> dict[str, Any]:
        return await self._skip("next")

    async def previous_video(self) -> dict[str, Any]:
        return await self._skip("previous")

    async def get_status(self) -> dict[str, Any]:
        async with self._lock:
            await self.connect()
            try:
                state = await self._video_state()
            except UnsupportedAction:
                return {"ok": True, "video_loaded": False, "url": self._page.url}
            return {"ok": True, "video_loaded": True, "url": self._page.url,
                    "video_id": extract_id(self._page.url, "video"),
                    "playlist_id": extract_id(self._page.url, "playlist"),
                    "title": await self._page.title(), **state}
