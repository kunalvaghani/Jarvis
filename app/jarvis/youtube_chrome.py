"""YouTube in the user's own Chrome profile, with Jarvis's browser as the fallback.

Chrome (136+) refuses remote automation of the default profile, which protects the
user's logins, so Jarvis never automates it. It only:

* opens exact YouTube URLs there (``chrome.exe --profile-directory=<profile> <url>``);
* confirms playback through the Windows media session that Chrome publishes
  (source "Chrome", title = video title);
* controls the tab through that session (play/pause/next/previous) and through
  accessibility (media_ui: skip ad, captions, seek...).

Fallback rule (AGENTS.md: never replay after an uncertain outcome): Jarvis's own
browser is used only when nothing new started playing in the user's Chrome. If a
new Chrome media session appeared but could not be confirmed (for example a long
unskippable ad), the outcome is reported as uncertain and nothing is replayed.

Configuration (config.json ``media``): ``youtube_browser`` "user_chrome" (default)
or "jarvis"; ``youtube_chrome_profile`` the Chrome profile folder, default "Default".
``youtube_profile_only: true`` overrides the browser mode and forbids fallback.
"""
import asyncio
from difflib import SequenceMatcher
import re
import subprocess
import threading
import time
from urllib.parse import urlsplit

PROFILE = re.compile(r'(?:Default|Profile \d{1,3}|Guest Profile)')
YOUTUBE_HOSTS = {'www.youtube.com', 'youtube.com', 'm.youtube.com', 'youtu.be'}


def profile_only(actions):
    """A user preference, never a model-supplied claim or permission waiver."""
    config = getattr(actions, 'config', {})
    media = config.get('media', {}) if isinstance(config, dict) else {}
    value = media.get('youtube_profile_only', False) if isinstance(media, dict) else False
    if type(value) is not bool:
        raise ValueError('media.youtube_profile_only must be a boolean.')
    return value


def open_requested(actions, value, cancelled=lambda: False):
    """Route explicit YouTube navigation to the pinned profile; never infer playback."""
    if not profile_only(actions):
        return None
    from .browser import url_for
    try:
        url = url_for(value)
        host = urlsplit(url).hostname
    except ValueError:
        return None
    if host not in YOUTUBE_HOSTS:
        return None
    profile = settings(actions)
    open_url(actions, url, profile, cancelled)
    actions.youtube_target = 'user_chrome'
    actions.last_media = 'youtube'
    return {'outcome':'opened_only', 'url':url, 'profile':profile,
            'playing_verified':False, 'message':'Opened YouTube in your Chrome profile '+profile+'. Playback has not been verified.'}


class ChromeUnavailable(ValueError):
    """Nothing was started in the user's Chrome; falling back to Jarvis's browser is safe."""


class PlaybackUncertain(ValueError):
    """Something may be playing in the user's Chrome; do not replay elsewhere."""


def settings(actions):
    """``(profile_folder)`` when YouTube should use the user's Chrome, else ``None``."""
    media = actions.config.get('media', {}) if isinstance(getattr(actions, 'config', None), dict) else {}
    media = media if isinstance(media, dict) else {}
    if not profile_only(actions) and media.get('youtube_browser', 'user_chrome') != 'user_chrome':
        return None
    profile = media.get('youtube_chrome_profile', 'Default')
    if not isinstance(profile, str) or not PROFILE.fullmatch(profile):
        raise ValueError('media.youtube_chrome_profile must be a Chrome profile folder such as Default or Profile 1.')
    return profile


def open_url(actions, url, profile, cancelled=lambda: False):
    """Open one YouTube URL in the user's Chrome profile (no shell, no automation)."""
    parts = urlsplit(url)
    try:
        authority_ok = not (parts.username or parts.password) and parts.port in (None, 443)
    except ValueError:
        authority_ok = False
    if parts.scheme != 'https' or parts.hostname not in YOUTUBE_HOSTS or not authority_ok:
        raise ChromeUnavailable('Only https YouTube addresses are opened in your Chrome.')
    if not isinstance(profile, str) or not PROFILE.fullmatch(profile):
        raise ChromeUnavailable('A valid Chrome profile folder is required.')
    if profile_only(actions) and profile != settings(actions):
        raise ChromeUnavailable('YouTube is locked to your configured Chrome profile.')
    from .browser import browser_args
    try:
        executable = browser_args(getattr(actions, 'apps', None) or {}, 'chrome')[0]
    except (ValueError, IndexError, TypeError) as exc:
        raise ChromeUnavailable('Google Chrome is not configured: ' + str(exc)) from None
    if cancelled():
        raise ValueError('YouTube request cancelled before opening Chrome.')
    try:
        subprocess.Popen([executable, '--profile-directory=' + profile, url], shell=False)
    except OSError as exc:
        raise ChromeUnavailable('Chrome could not be started: ' + str(exc)[:120]) from None


# ----- Windows media session -------------------------------------------------------------
def _is_chrome(session):
    return 'chrome' in str(session.source_app_user_model_id).casefold()


async def _snapshot():
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    rows = []
    for session in manager.get_sessions():
        if not _is_chrome(session):
            continue
        properties = await session.try_get_media_properties_async()
        timeline = session.get_timeline_properties()
        rows.append({'title': (properties.title if properties else '')[:300],
                     'artist': (properties.artist if properties else '')[:300],
                     'status': session.get_playback_info().playback_status.name.lower(),
                     'position': max(0, timeline.position.total_seconds()),
                     'duration': max(0, timeline.end_time.total_seconds())})
    return rows


async def _act(action, title):
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    done = 0
    for session in manager.get_sessions():
        if not _is_chrome(session):
            continue
        properties = await session.try_get_media_properties_async()
        name = properties.title if properties else ''
        status = session.get_playback_info().playback_status.name.lower()
        if action == 'pause_others':
            if status == 'playing' and not matches(title, name):
                done += bool(await session.try_pause_async())
        elif matches(title, name):
            method = {'play': session.try_play_async, 'pause': session.try_pause_async,
                      'next': session.try_skip_next_async, 'previous': session.try_skip_previous_async}[action]
            done += bool(await method())
    return done


def _run(coroutine_factory, timeout=4.):
    """Run a WinRT coroutine on a fresh MTA thread (see media_player.spotify_now)."""
    found = {}

    def worker():
        initialized = False
        try:
            from winrt.runtime import ApartmentType, init_apartment, uninit_apartment
            init_apartment(ApartmentType.MULTI_THREADED)
            initialized = True
            found['value'] = asyncio.run(asyncio.wait_for(coroutine_factory(), timeout))
        except Exception as exc:  # reported to the caller as unavailable
            found['error'] = exc
        finally:
            if initialized:
                uninit_apartment()
    thread = threading.Thread(target=worker, daemon=True, name='jarvis-youtube-session')
    thread.start()
    thread.join(timeout + 1)
    if 'value' not in found:
        raise ChromeUnavailable('The Windows media session could not be read.')
    return found['value']


def sessions():
    return _run(_snapshot)


def act(action, title=''):
    return _run(lambda: _act(action, title))


def matches(expected, actual):
    """Media-session titles equal the video title; allow small differences (emoji, trimming)."""
    def norm(text):
        return ' '.join(re.sub(r'[^\w\s]', ' ', str(text).casefold()).split())
    a, b = norm(expected), norm(actual)
    if not a or not b:
        return False
    return a in b or b in a or SequenceMatcher(None, a, b).ratio() >= .75


# ----- play ----------------------------------------------------------------------------------
def play(actions, url, title, cancelled, timeout=40., clock=time.monotonic, sleep=time.sleep,
         read=sessions, send=act):
    """Open ``url`` in the user's Chrome and confirm ``title`` is playing; returns the session row."""
    profile = settings(actions)
    if profile is None:
        raise ChromeUnavailable('YouTube is configured to use Jarvis\'s browser.')
    before = {(row['title'], row['status']) for row in read()}
    try:
        send('pause_others', title)  # never two players at once
    except ChromeUnavailable:
        pass
    open_url(actions, url, profile, cancelled)
    started, nudged, appeared = clock(), False, False
    while clock() - started < timeout:
        if cancelled():
            raise PlaybackUncertain('Cancelled after opening YouTube in your Chrome; check the tab before repeating.')
        rows = read()
        mine = [row for row in rows if matches(title, row['title'])]
        appeared = appeared or bool(mine) or any((row['title'], row['status']) not in before
                                                 and row['status'] == 'playing' for row in rows)
        if any(row['status'] == 'playing' for row in mine):
            return next(row for row in mine if row['status'] == 'playing')
        if mine and not nudged and clock() - started > 6:
            send('play', title)  # autoplay held back: one play request is the user's intent
            nudged = True
        sleep(1)
    if appeared:
        raise PlaybackUncertain('YouTube opened in your Chrome but playback was not confirmed (an ad may still be '
                                'playing). Nothing was replayed; check the tab.')
    raise ChromeUnavailable('Your Chrome did not report any YouTube playback.')
