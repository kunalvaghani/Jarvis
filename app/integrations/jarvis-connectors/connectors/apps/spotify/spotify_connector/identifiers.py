"""Validate untrusted track/playlist/artist etc. identifiers and Spotify URLs."""
from __future__ import annotations
import re
from urllib.parse import unquote, urlsplit
from .base import ConnectorError

ID = re.compile(r"^[A-Za-z0-9]{22}$")
DEVICE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
KINDS = frozenset({'track','album','artist','playlist','show','episode','audiobook','chapter'})

def spotify_uri(value: str, kinds: set[str] | frozenset[str] | tuple[str, ...] | None = None) -> str:
    """Accept official Spotify URL/URI only; normalize; block lookalike hostnames."""
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ConnectorError('Provide a Spotify URI or official URL')
    if any(ord(c) < 32 for c in value):
        raise ConnectorError('Control characters are not permitted in Spotify identifiers')
    v = value.strip()
    if v.startswith('spotify:'):
        parts = v.split(':')
        if len(parts) != 3:
            raise ConnectorError('Invalid Spotify URI')
        kind, ident = parts[1:]
    else:
        try:
            parsed = urlsplit(v)
            port = parsed.port
        except ValueError:
            raise ConnectorError('Malformed Spotify resource URL') from None
        if parsed.scheme != 'https' or parsed.hostname not in {'open.spotify.com', 'play.spotify.com'} or parsed.username or parsed.password or port not in {None,443}:
            raise ConnectorError('Only official Spotify HTTPS URLs are allowed')
        segments = unquote(parsed.path).strip('/').split('/')
        # Spotify URLs may use /intl-en/track/id
        if len(segments) == 3 and segments[0].startswith('intl-'):
            segments = segments[1:]
        if len(segments) != 2:
            raise ConnectorError('Invalid Spotify resource URL')
        kind, ident = segments
    if kind not in KINDS or (kinds is not None and kind not in kinds) or not ID.fullmatch(ident):
        raise ConnectorError('Unsupported Spotify resource type or malformed ID')
    return f'spotify:{kind}:{ident}'

def resource_id(value: str, kind: str) -> str:
    if not isinstance(value, str):
        raise ConnectorError(f'Invalid {kind}')
    if ID.fullmatch(value):
        return value
    return spotify_uri(value, {kind}).split(':')[2]

def device_id(value: str | None) -> str | None:
    if value is None or value == '':
        return None
    if not isinstance(value,str) or not DEVICE.fullmatch(value):
        raise ConnectorError('Invalid Spotify device ID')
    return value

def uri_list(items: list[str], kinds: set[str], max_items: int = 100) -> list[str]:
    if not isinstance(items, list) or not (1 <= len(items) <= max_items):
        raise ConnectorError(f'Expected 1..{max_items} Spotify items')
    return [spotify_uri(i, kinds) for i in items]

def bounded(value: int, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ConnectorError(f'{name} must be an integer between {low} and {high}')
    return value
