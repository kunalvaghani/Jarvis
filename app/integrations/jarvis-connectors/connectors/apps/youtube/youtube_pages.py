"""Pure YouTube parsing: identifiers, links and the data embedded in public pages.

No network access here, so every rule is unit-testable offline. Only named fields
are extracted; raw page data (which includes viewer-specific stream URLs and the
requester's IP address) is never passed through.

Page shapes observed 2026-10-20: search results use ``videoRenderer`` for videos
and ``lockupViewModel`` (contentType LOCKUP_CONTENT_TYPE_PLAYLIST) for playlists;
playlist pages list items as ``lockupViewModel`` (LOCKUP_CONTENT_TYPE_VIDEO).
The older ``playlistRenderer``/``playlistVideoRenderer`` shapes are still accepted.
"""
import json
import re
import unicodedata
from urllib.parse import parse_qs, urlencode, urlsplit

VIDEO_ID = re.compile(r'[A-Za-z0-9_-]{11}')
PLAYLIST_ID = re.compile(r'(?:PL|UU|LL|FL|RD|OL|OLAK5uy_)[A-Za-z0-9_-]{8,80}')
HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}
TITLE_CHARS = 120


class PageError(ValueError):
    """The page did not contain the expected embedded data (consent page, layout change...)."""


def watch_url(video_id, playlist_id='', index=0):
    query = {'v': video_id}
    if playlist_id:
        query['list'] = playlist_id
        if index:
            query['index'] = index
    return 'https://www.youtube.com/watch?' + urlencode(query)


def playlist_url(playlist_id):
    return 'https://www.youtube.com/playlist?' + urlencode({'list': playlist_id})


def parse_link(value):
    """``{'video_id', 'playlist_id'}`` from a bare ID or an HTTPS YouTube link; ``None`` if not YouTube."""
    value = value.strip()
    if VIDEO_ID.fullmatch(value):
        return {'video_id': value, 'playlist_id': ''}
    if PLAYLIST_ID.fullmatch(value):
        return {'video_id': '', 'playlist_id': value}
    try:
        url = urlsplit(value)
        host = (url.hostname or '').lower()
    except ValueError:
        return None
    if url.scheme != 'https' or host not in HOSTS or url.username or url.password or url.port not in (None, 443):
        return None
    query = parse_qs(url.query)
    parts = [p for p in url.path.split('/') if p]
    if host == 'youtu.be':
        video = parts[0] if parts else ''
    elif url.path == '/watch':
        video = query.get('v', [''])[0]
    elif len(parts) == 2 and parts[0] in {'shorts', 'embed', 'live', 'v'}:
        video = parts[1]
    else:
        video = ''
    playlist = query.get('list', [''])[0] if url.path in {'/watch', '/playlist', '/embed/videoseries'} or host == 'youtu.be' else ''
    video = video if VIDEO_ID.fullmatch(video) else ''
    playlist = playlist if PLAYLIST_ID.fullmatch(playlist) else ''
    if not video and not playlist:
        return None
    return {'video_id': video, 'playlist_id': playlist}


def embedded_json(html, variable):
    """Decode ``var <variable> = {...};`` from a page, or raise PageError."""
    for marker in ('var ' + variable + ' = ', 'window["' + variable + '"] = ', variable + ' = '):
        start = html.find(marker)
        if start >= 0:
            try:
                data, _ = json.JSONDecoder().raw_decode(html, start + len(marker))
            except ValueError as exc:
                raise PageError('YouTube page data could not be decoded.') from exc
            if isinstance(data, dict):
                return data
    raise PageError('YouTube returned a page without its usual data (consent page or layout change).')


def _walk(node, key):
    """Yield every value stored under ``key`` (depth-first, document order)."""
    stack = [node]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if key in item:
                yield item[key]
            stack.extend(reversed(list(item.values())))
        elif isinstance(item, list):
            stack.extend(reversed(item))


def _text(node):
    if isinstance(node, dict):
        if isinstance(node.get('simpleText'), str):
            return node['simpleText']
        if isinstance(node.get('content'), str):
            return node['content']
        return ''.join(run.get('text', '') for run in node.get('runs', []) if isinstance(run, dict))
    return node if isinstance(node, str) else ''


def _title(value):
    # NFKC turns decorative full-width/compatibility letters (ＯＳＡＫＡ) into plain ones (OSAKA): the model
    # misread them as other words in the 2026-10-20 qwen3.5:9b evaluation, and speech reads them badly.
    value = ' '.join(unicodedata.normalize('NFKC', _text(value)).split())
    return value[:TITLE_CHARS - 1] + '…' if len(value) > TITLE_CHARS else value


def clock_seconds(text):
    if not isinstance(text, str) or not re.fullmatch(r'\d{1,3}(?::\d{2}){0,2}', text.strip()):
        return 0
    total = 0
    for part in text.strip().split(':'):
        total = total * 60 + int(part)
    return total


def _int(text):
    digits = re.sub(r'[^\d]', '', text or '')
    return int(digits) if digits and len(digits) < 16 else 0


def _lockup_rows(lockup):
    metadata = (lockup.get('metadata') or {}).get('lockupMetadataViewModel') or {}
    rows = ((metadata.get('metadata') or {}).get('contentMetadataViewModel') or {}).get('metadataRows') or []
    parts = [[_text(part.get('text')) for part in row.get('metadataParts', []) if isinstance(part, dict)]
             for row in rows if isinstance(row, dict)]
    badges = [b.get('text', '') for b in _walk(lockup, 'thumbnailBadgeViewModel') if isinstance(b, dict)]
    return metadata, parts, badges


def search_videos(data, limit):
    rows, seen = [], set()
    for video in _walk(data, 'videoRenderer'):
        if not isinstance(video, dict) or not VIDEO_ID.fullmatch(str(video.get('videoId', ''))):
            continue
        video_id = video['videoId']
        if video_id in seen:
            continue
        seen.add(video_id)
        length = _text(video.get('lengthText'))
        rows.append({'video_id': video_id, 'title': _title(video.get('title')),
                     'channel': _title(video.get('ownerText')), 'duration_seconds': clock_seconds(length),
                     'live': not length, 'url': watch_url(video_id)})
        if len(rows) >= limit:
            break
    return rows


def search_playlists(data, limit):
    rows, seen = [], set()
    for lockup in _walk(data, 'lockupViewModel'):
        if not isinstance(lockup, dict) or lockup.get('contentType') != 'LOCKUP_CONTENT_TYPE_PLAYLIST':
            continue
        playlist_id = str(lockup.get('contentId', ''))
        if not PLAYLIST_ID.fullmatch(playlist_id) or playlist_id in seen:
            continue
        metadata, parts, badges = _lockup_rows(lockup)
        first = next((w.get('videoId') for w in _walk(lockup, 'watchEndpoint') if isinstance(w, dict)), '')
        seen.add(playlist_id)
        rows.append(_playlist_row(playlist_id, metadata.get('title'), parts[0][0] if parts and parts[0] else '',
                                  next((_int(b) for b in badges if 'video' in b.lower() or 'episode' in b.lower()), 0), first))
        if len(rows) >= limit:
            return rows
    for playlist in _walk(data, 'playlistRenderer'):  # older layout
        if not isinstance(playlist, dict):
            continue
        playlist_id = str(playlist.get('playlistId', ''))
        if not PLAYLIST_ID.fullmatch(playlist_id) or playlist_id in seen:
            continue
        seen.add(playlist_id)
        first = ((playlist.get('navigationEndpoint') or {}).get('watchEndpoint') or {}).get('videoId', '')
        rows.append(_playlist_row(playlist_id, playlist.get('title'), _text(playlist.get('shortBylineText')),
                                  _int(str(playlist.get('videoCount', ''))), first))
        if len(rows) >= limit:
            break
    return rows


def _playlist_row(playlist_id, title, channel, count, first):
    first = first if isinstance(first, str) and VIDEO_ID.fullmatch(first) else ''
    return {'playlist_id': playlist_id, 'title': _title(title), 'channel': _title(channel), 'video_count': count,
            'url': playlist_url(playlist_id), 'play_url': watch_url(first, playlist_id) if first else ''}


def playlist_items(data, playlist_id, limit):
    """``(title, [items])`` from a playlist page."""
    title = next((_title(m.get('title')) for m in _walk(data, 'playlistMetadataRenderer') if isinstance(m, dict)), '')
    items, seen = [], set()
    for lockup in _walk(data, 'lockupViewModel'):
        if not isinstance(lockup, dict) or lockup.get('contentType') != 'LOCKUP_CONTENT_TYPE_VIDEO':
            continue
        video_id = str(lockup.get('contentId', ''))
        if not VIDEO_ID.fullmatch(video_id) or video_id in seen:
            continue
        seen.add(video_id)
        metadata, parts, badges = _lockup_rows(lockup)
        items.append(_item(video_id, playlist_id, len(items) + 1, metadata.get('title'),
                           parts[0][0] if parts and parts[0] else '', next((clock_seconds(b) for b in badges if clock_seconds(b)), 0)))
        if len(items) >= limit:
            return title, items
    for video in _walk(data, 'playlistVideoRenderer'):  # older layout
        if not isinstance(video, dict) or not VIDEO_ID.fullmatch(str(video.get('videoId', ''))) or video['videoId'] in seen:
            continue
        seen.add(video['videoId'])
        items.append(_item(video['videoId'], playlist_id, len(items) + 1, video.get('title'),
                           _text(video.get('shortBylineText')), _int(str(video.get('lengthSeconds', '')))))
        if len(items) >= limit:
            break
    return title, items


def _item(video_id, playlist_id, index, title, channel, seconds):
    return {'index': index, 'video_id': video_id, 'title': _title(title), 'channel': _title(channel),
            'duration_seconds': seconds, 'url': watch_url(video_id, playlist_id, index)}


def video_details(player):
    """Named fields from ``ytInitialPlayerResponse``; raises PageError when absent."""
    details = player.get('videoDetails')
    if not isinstance(details, dict) or not VIDEO_ID.fullmatch(str(details.get('videoId', ''))):
        status = (player.get('playabilityStatus') or {}).get('status', '')
        raise PageError('YouTube did not return details for that video' + (' (status ' + str(status)[:20] + ').' if status else '.'))
    status = str((player.get('playabilityStatus') or {}).get('status', ''))[:20]
    return {'video_id': details['videoId'], 'title': _title(details.get('title')), 'channel': _title(details.get('author')),
            'duration_seconds': _int(str(details.get('lengthSeconds', ''))), 'views': _int(str(details.get('viewCount', ''))),
            'live': details.get('isLiveContent') is True, 'playable': status == 'OK', 'status': status,
            'url': watch_url(details['videoId'])}
