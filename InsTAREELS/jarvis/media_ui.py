"""Media controls resolved from fresh Windows accessibility evidence."""
import json
import os
import re
from pathlib import PureWindowsPath

from .ui_controls import label_key


YOUTUBE_KEYS = {'next': '+n', 'previous': '+p', 'seek_10': 'l', 'seek_-10': 'j',
                'speed_up': '>', 'speed_down': '<', 'next_chapter': '^{RIGHT}',
                'previous_chapter': '^{LEFT}', 'next_frame': '.', 'previous_frame': ',',
                'restart': '0', 'miniplayer': 'i'}
SPOTIFY_KEYS = {'queue': '%+q', 'library': '%+0', 'playlists': '%+1', 'podcasts': '%+2',
                'artists': '%+3', 'albums': '%+4', 'home': '%+h', 'now_playing': '%+j',
                'liked_songs': '%+s'}
LABELS = {'play': ['Play (k)', 'Play'], 'pause': ['Pause (k)', 'Pause'],
          'mute': ['Mute (m)', 'Mute'], 'unmute': ['Unmute (m)', 'Unmute'],
          'fullscreen': ['Full screen (f)', 'Full screen'],
          'exit_fullscreen': ['Exit full screen (f)', 'Exit full screen'],
          'theater': ['Theater mode (t)', 'Theater mode'], 'default_view': ['Default view (t)', 'Default view'],
          'captions': ['Subtitles/closed captions (c)', 'Subtitles/closed captions', 'Captions'],
          'lyrics': ['Lyrics', 'Show lyrics'], 'add_queue': ['Add to queue'],
          'like': ['Save to your Liked Songs', 'Add to Liked Songs', 'Save to Your Library', 'Add to your library']}
OPPOSITE = {'play': 'pause', 'pause': 'play', 'mute': 'unmute', 'unmute': 'mute',
            'fullscreen': 'exit_fullscreen', 'exit_fullscreen': 'fullscreen', 'theater': 'default_view'}


def platform_of(snapshot):
    try:
        executable = PureWindowsPath(json.loads(snapshot.get('context') or '[]')[0]).name.casefold()
    except (ValueError, IndexError, TypeError):
        return None
    if executable in {'spotify.exe', 'spotify'}:
        return 'spotify'
    if executable in {'chrome.exe', 'msedge.exe', 'firefox.exe'} and re.search(r'(?:^| - )youtube(?: - (?:google chrome|microsoft edge|mozilla firefox).*)?$', snapshot.get('title', ''), re.I):
        return 'youtube'
    return None


def find_media_handle(platform):
    import win32gui
    import win32process
    import psutil
    choices = []
    def collect(handle, _):
        if not win32gui.IsWindowVisible(handle) or not win32gui.GetWindowText(handle):
            return
        try:
            process = psutil.Process(win32process.GetWindowThreadProcessId(handle)[1])
            if platform_of({'context': json.dumps([process.exe()]), 'title': win32gui.GetWindowText(handle)}) == platform:
                choices.append(handle)
        except (OSError, psutil.Error):
            pass
    win32gui.EnumWindows(collect, None)
    if len(choices) > 1:
        raise ValueError('Multiple media windows are open; select the intended window first.')
    return choices[0] if choices else None


def snapshot_for(ui, cancelled, platform=None):
    if cancelled():
        raise ValueError('Media action cancelled.')
    try:
        handle = ui._handle()
    except ValueError:
        if not platform:
            raise
        handle = None
    snapshot = ui.runner({'operation': 'list', 'handle': handle, 'owner_pid': os.getpid()}, cancelled) if handle else {}
    if platform and platform_of(snapshot) != platform:
        found = find_media_handle(platform)
        if found:
            handle = found
            snapshot = ui.runner({'operation': 'list', 'handle': handle, 'owner_pid': os.getpid()}, cancelled)
    return handle, snapshot


def resolve(controls, labels, roles=None):
    for label in labels:
        choices = [c for c in controls if (not roles or c['role'] in roles)
                   and label_key(c['name']) == label_key(label)]
        if choices:
            if len(choices) != 1:
                raise ValueError('Multiple matching media controls are visible; name the intended player or result.')
            return choices[0]
    return None


def search_current(ui, platform, query, cancelled=lambda: False):
    """Return None only before any write, when the target site is not active."""
    if not query.strip() or len(query) > 300:
        raise ValueError('Use a media search query of 1 to 300 characters.')
    try:
        handle, snapshot = snapshot_for(ui, cancelled, platform)
    except ValueError:
        if cancelled():
            raise
        return None
    if platform_of(snapshot) != platform:
        return None
    field = resolve(snapshot['controls'], ['Search', 'Search YouTube', 'Search query', 'What do you want to play?', 'Search for songs, artists, or podcasts'], {'Edit'})
    if not field or field.get('password'):
        return None
    result = ui.runner({'operation': 'media_search_field', 'platform': platform, 'handle': handle,
                        'foreground_handle': snapshot.get('foreground_handle'),
                        'owner_pid': os.getpid(), 'control': field, 'content': query}, cancelled)
    ui.desktop.target = handle
    ui.clear_pending()
    return result['message']


def key_for(platform, action):
    mapping = YOUTUBE_KEYS if platform == 'youtube' else SPOTIFY_KEYS if platform == 'spotify' else {}
    if action in mapping:
        return mapping[action]
    if platform == 'youtube' and action.startswith('seek_'):
        seconds = int(action.removeprefix('seek_'))
        if not seconds or abs(seconds) > 300 or seconds % 10:
            raise ValueError('YouTube relative seeking supports multiples of 10 seconds up to 300; use seek to a percentage for another position.')
        return ('l' if seconds > 0 else 'j') * (abs(seconds) // 10)
    return None


def fill_search(element, target, text, handle):
    """Resolve input method before writing; never retry an uncertain SetValue."""
    from pywinauto.uia_defines import NoPatternInterfaceError
    if not target or target['role'] != 'Edit' or target.get('password') or not text.strip() or len(text) > 300:
        raise ValueError('Choose one non-password media search field and a short exact query.')
    try:
        interface = element.iface_value
    except NoPatternInterfaceError:
        # Verify a readable Text pattern BEFORE choosing keyboard input.
        readable = element.iface_text.DocumentRange
        element.set_focus()
        element.type_keys('^a', set_foreground=False)
        from .actions import Desktop
        desktop = Desktop()
        desktop.target = handle
        desktop.type(text, lambda: False)
        if element.iface_text.DocumentRange.GetText(-1).strip() != text:
            raise ValueError('Search text was entered but not verified; it was not submitted. Check the field before repeating.')
    else:
        if interface.CurrentIsReadOnly:
            raise ValueError('The media search field is read-only.')
        interface.SetValue(text)
        if interface.CurrentValue != text:
            raise ValueError('Search text was attempted but not verified; it was not submitted. Check the field before repeating.')
        element.set_focus()
    import win32gui
    if win32gui.GetForegroundWindow() != handle:
        raise ValueError('Focus changed after filling search; submission cancelled.')
    element.type_keys('{ENTER}', set_foreground=False)
    return 'Entered and verified media search text, then submitted: ' + text + '; playback has not started yet.'


def set_range(element, target, amount):
    if not target or target['role'] != 'Slider':
        raise ValueError('Select one accessible media slider.')
    interface = element.iface_range_value
    if interface.CurrentIsReadOnly:
        raise ValueError('The media slider is read-only.')
    low, high = interface.CurrentMinimum, interface.CurrentMaximum
    if high <= low:
        raise ValueError('The media slider exposes no usable range.')
    old = interface.CurrentValue
    if amount in {'up', 'down'}:
        value = max(low, min(high, old + (high - low) * (.05 if amount == 'up' else -.05)))
    else:
        percent = int(amount)
        if not 0 <= percent <= 100:
            raise ValueError('Choose a value from 0 to 100 percent.')
        value = low + (high - low) * percent / 100
    interface.SetValue(value)
    if abs(interface.CurrentValue - value) > max(.01, (high - low) * .01):
        raise ValueError('Media slider change was attempted but not verified. Check the player before repeating.')
    return f'{target["name"]} verified at {round((value - low) / (high - low) * 100)} percent.'


def control(ui, platform, action, cancelled=lambda: False):
    if platform not in {'youtube', 'spotify'}:
        raise ValueError('Choose YouTube or the native Spotify app.')
    handle, snapshot = snapshot_for(ui, cancelled, platform)
    if platform_of(snapshot) != platform:
        raise ValueError(f'Bring {platform} to the foreground first. No other app was controlled.')
    controls = snapshot['controls']
    snapshot['media_platform'] = platform
    if action == 'status':
        state = 'playing' if resolve(controls, LABELS['pause'], {'Button'}) else 'paused' if resolve(controls, LABELS['play'], {'Button'}) else 'unknown'
        return f'{platform}: {snapshot.get("title", "Unknown media")}; playback {state}.'
    base = 'captions' if action.startswith('captions_') else action
    if base in LABELS:
        target = resolve(controls, LABELS[base], {'Button', 'CheckBox', 'MenuItem'})
        if not target:
            if action == 'like' and resolve(controls, ['Remove from your Liked Songs', 'Remove from Liked Songs', 'Remove from Your Library'], {'Button'}):
                return 'Spotify song is already saved.'
            opposite = OPPOSITE.get(action)
            if opposite and resolve(controls, LABELS[opposite], {'Button'}):
                return f'{platform} already has the requested {action} state.'
            raise ValueError(f'The {action} control is not exposed in this player. Open the player or its menu first.')
        if action.startswith('captions_'):
            wanted = 1 if action == 'captions_on' else 0
            if 'toggle_state' not in target:
                raise ValueError('Caption state is not exposed. Say toggle captions on YouTube for one explicit toggle.')
            if target['toggle_state'] == wanted:
                return f'YouTube captions already {action.removeprefix("captions_")}.'
        if action in {'lyrics', 'like'} and target.get('toggle_state') == 1:
            return f'Spotify already has the requested {action} state.'
        result = ui._activate(handle, snapshot, target, 'click', cancelled)
        return result + '; media state will be observed before another action.'
    if action.startswith(('volume_', 'position_')):
        kind, amount = action.split('_', 1)
        sliders = [c for c in controls if c['role'] == 'Slider' and
                   (('volume' in label_key(c['name'])) if kind == 'volume' else bool(re.search(r'\b(?:seek|progress|timeline)\b', label_key(c['name']))))]
        if len(sliders) != 1:
            raise ValueError('One accessible player volume/seek slider is required; open its controls first.')
        if amount not in {'up', 'down'} and not 0 <= int(amount) <= 100:
            raise ValueError('Choose a value from 0 to 100 percent.')
        return ui.runner({'operation': 'media_range', 'platform': platform, 'handle': handle,
                          'foreground_handle': snapshot.get('foreground_handle'),
                          'owner_pid': os.getpid(), 'control': sliders[0], 'value': amount}, cancelled)['message']
    key = key_for(platform, action)
    if key is None:
        raise ValueError('Unsupported media operation. Use a named visible control for settings, quality, playlist edits, filters or menus.')
    target = None
    if platform == 'youtube':
        target = resolve(controls, LABELS['pause'], {'Button'}) or resolve(controls, LABELS['play'], {'Button'})
        if not target:
            raise ValueError('No YouTube player is exposed; open a video first.')
        if action in {'next_frame', 'previous_frame'} and resolve(controls, LABELS['pause'], {'Button'}):
            raise ValueError('Pause the video before stepping through frames.')
    return ui.runner({'operation': 'media_key', 'platform': platform, 'handle': handle,
                      'foreground_handle': snapshot.get('foreground_handle'),
                      'owner_pid': os.getpid(), 'control': target, 'value': action}, cancelled)['message']
