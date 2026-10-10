"""Deterministic media phrases; transport still reads real app/player state."""
import re
from .commands import Command


def parse_media(text):
    text = text.strip().rstrip('.!?').strip()
    low = text.casefold()
    ordinal = re.fullmatch(r'(play|select|open|choose) (?:the )?(first|second|third|fourth|fifth|\d+(?:st|nd|rd|th)?) (?:song|track)(?: (?:on|in) spotify)?', low)
    if ordinal:
        number = {'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5'}.get(ordinal[2]) or re.match(r'\d+', ordinal[2])[0]
        return Command('select_context', number + ':track', 'play' if ordinal[1] == 'play' else 'select')
    if low in {'open spotify web', 'open spotify website', 'open spotify web player'}:
        return Command('browse', 'spotify', 'chrome')
    match = re.fullmatch(r'(?:search|find|look for)(?: for)? (.+?) (?:on|in|using) (youtube|spotify)', text, re.I)
    if not match:
        match = re.fullmatch(r'(youtube|spotify) search(?: for)? (.+)', text, re.I)
        if match:
            return Command('media_search', match[2], match[1].lower())
    else:
        return Command('media_search', match[1], match[2].lower())
    # Keep app-scoped controls out of generic song-name and web-search rules.
    match = re.fullmatch(r'(.+?) (?:on|in|for) (youtube|spotify)', low)
    if not match:
        match = re.fullmatch(r'(youtube|spotify) (.+)', low)
        if match:
            platform, phrase = match.groups()
        else:
            # Only the YouTube player has captions.
            platform, phrase = ('youtube', low) if re.search(r'\bvideo\b|caption|subtitle', low) else ('', '')
    else:
        phrase, platform = match.groups()
    phrase = re.sub(r'\b(?:the |video |video$)', '', phrase).strip()
    aliases = {
        'pause': 'pause', 'resume': 'play', 'play': 'play', 'next': 'next',
        'next video': 'next', 'previous': 'previous', 'previous video': 'previous',
        'mute': 'mute', 'unmute': 'unmute', 'volume up': 'volume_up', 'volume down': 'volume_down',
        'full screen': 'fullscreen', 'fullscreen': 'fullscreen', 'enter full screen': 'fullscreen',
        'exit full screen': 'exit_fullscreen', 'exit fullscreen': 'exit_fullscreen',
        'toggle captions': 'captions', 'toggle subtitles': 'captions',
        'captions': 'captions', 'subtitles': 'captions',
        'enable captions': 'captions_on', 'disable captions': 'captions_off',
        'enable subtitles': 'captions_on', 'disable subtitles': 'captions_off',
        'turn captions on': 'captions_on', 'turn captions off': 'captions_off',
        'turn on captions': 'captions_on', 'turn off captions': 'captions_off',
        'captions on': 'captions_on', 'captions off': 'captions_off',
        'subtitles on': 'captions_on', 'subtitles off': 'captions_off',
        'mini player': 'miniplayer', 'miniplayer': 'miniplayer', 'theater mode': 'theater',
        'faster': 'speed_up', 'slower': 'speed_down', 'speed up': 'speed_up', 'slow down': 'speed_down',
        'next chapter': 'next_chapter', 'previous chapter': 'previous_chapter',
        'next frame': 'next_frame', 'previous frame': 'previous_frame',
        'restart': 'restart', 'start over': 'restart', 'what is playing': 'status', "what's playing": 'status',
        'show queue': 'queue', 'open queue': 'queue', 'show library': 'library', 'open library': 'library',
        'show liked songs': 'liked_songs', 'open liked songs': 'liked_songs',
        'show lyrics': 'lyrics', 'open lyrics': 'lyrics', 'show home': 'home',
        'show playlists': 'playlists', 'show albums': 'albums', 'show artists': 'artists',
        'show podcasts': 'podcasts', 'show now playing': 'now_playing',
        'like this song': 'like', 'save this song': 'like', 'add this song to queue': 'add_queue',
        'shuffle on': 'shuffle_on', 'shuffle off': 'shuffle_off',
        'turn on shuffle': 'shuffle_on', 'turn off shuffle': 'shuffle_off',
        'enable shuffle': 'shuffle_on', 'disable shuffle': 'shuffle_off',
        'repeat one': 'repeat_one', 'repeat all': 'repeat_all', 'repeat on': 'repeat_all', 'repeat off': 'repeat_off',
    }
    action = aliases.get(phrase)
    if not platform:
        if low in {'full screen', 'fullscreen', 'exit full screen', 'exit fullscreen', 'toggle captions', 'toggle subtitles', 'mini player', 'miniplayer', 'theater mode', 'next chapter', 'previous chapter', 'next frame', 'previous frame'}:
            platform, action = 'youtube', aliases[low]
        elif low in {'show queue', 'open queue', 'show library', 'open library', 'show liked songs', 'open liked songs', 'show lyrics', 'open lyrics', 'show playlists', 'show albums', 'show artists', 'show podcasts', 'show now playing'}:
            platform, action = 'spotify', aliases[low]
    seek = re.fullmatch(r'(seek|skip|fast forward|rewind)(?: by)? (\d{1,4}) seconds?', phrase)
    volume = re.fullmatch(r'(?:set |change |turn )?volume (?:to )?(\d{1,3})(?: percent|%)?', phrase)
    position = re.fullmatch(r'(?:seek|jump|go) to (\d{1,3})(?: percent|%)', phrase)
    if seek:
        action = 'seek_' + ('-' if seek[1] == 'rewind' else '') + seek[2]
    elif volume:
        action = 'volume_' + volume[1]
    elif position and platform == 'youtube':
        action = 'position_' + position[1]
    if not action or not platform:
        return None
    if platform == 'spotify':
        if action in {'play', 'pause', 'next', 'previous', 'status', 'shuffle_on', 'shuffle_off', 'repeat_one', 'repeat_all', 'repeat_off'} or action.startswith('seek_'):
            return Command('spotify_control', action)
        if action in {'mute', 'unmute', 'volume_up', 'volume_down'} or action.startswith('volume_'):
            return Command('spotify_volume', action.removeprefix('volume_'))
    return Command('media_control', action, platform)
