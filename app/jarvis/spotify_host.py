"""Deterministic Spotify routing through the existing ToolRegistry/MCP approval path."""
import json
import re

COMMON = ('spotify_status', 'spotify_pause', 'spotify_resume', 'spotify_next',
          'spotify_previous', 'spotify_search_tracks')


def plan_intent(goal, step):
    """A provider name alone never authorizes a planner-invented account mutation."""
    if not re.search(r'\bspotify\b', goal, re.I): return False
    if step.get('action') == 'mcp_list_tools': return True
    try: operation = json.loads(step.get('content') or '{}')['name']
    except (KeyError, ValueError, TypeError): return False
    if not isinstance(operation, str) or not operation.startswith('spotify_'): return False
    operation = operation[8:]
    verbs = {'remove_playlist_items':r'\bremove\b', 'replace_playlist_items':r'\breplace\b',
             'remove_saved_items':r'\b(?:remove|unsave)\b', 'remove_current_saved':r'\b(?:remove|unsave)\b',
             'update_playlist':r'\b(?:rename|edit|change|visibility|collaborat)\w*\b',
             'create_playlist':r'\bcreate\b', 'add_playlist_items':r'\badd\b',
             'add_current_to_playlist':r'\badd\b', 'reorder_playlist_items':r'\breorder\b',
             'save_items':r'\bsave\b', 'save_current':r'\bsave\b',
             'transfer':r'\b(?:switch|transfer)\b', 'add_to_queue':r'\b(?:add|queue)\b',
             'queue_search':r'\b(?:add|queue)\b'}
    if operation in verbs: return bool(re.search(verbs[operation], goal, re.I))
    if operation.startswith(('play_', 'local_play')) or operation in {'resume', 'toggle'}:
        return bool(re.search(r'\b(?:play|resume|toggle)\b', goal, re.I))
    return operation in {r['tool'][8:] for r in _matrix() if r['access']=='read'} or bool(
        re.search(r'\b(?:pause|stop|skip|next|previous|seek|rewind|volume|mute|shuffle|repeat)\b',goal,re.I))


def _matrix():
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parents[1]/'integrations/jarvis-connectors/connectors/apps/spotify/catalog.json').read_text())


def enabled(actions):
    from .mcp_bridge import _configured
    base = getattr(actions, 'base', None)
    if base is None:
        return False
    try:
        config = _configured(base).get('spotify', {})
    except (ValueError, OSError):
        return False  # A broken optional MCP file cannot disable unrelated legacy commands.
    return config.get('enabled') is True and config.get('trusted') is True


def discovery(rows, arguments):
    """Default context is six tools. Detailed groups are discovered on demand."""
    query = arguments.get('query', '')
    if not isinstance(query, str) or len(query) > 120 or set(arguments) - {'query', 'names_only'}:
        raise ValueError('Spotify discovery accepts a bounded query and names_only boolean.')
    if type(arguments.get('names_only', False)) is not bool:
        raise ValueError('names_only must be boolean.')
    if arguments.get('names_only'):
        return {'total': len(rows), 'tools': [r['name'] for r in rows]}
    selected = [r for r in rows if (query.casefold() in r['name'].casefold() if query else r['name'] in COMMON)]
    return {'total': len(rows), 'matching': len(selected), 'tools': selected[:6],
            'next': 'Narrow query by operation name to load other detailed schemas.'}


def parse_request(text):
    """Called only for phrases the established parser did not already handle."""
    from .commands import Command
    text = text.strip().rstrip('.!?')
    if re.search(r'(?:,\s*|\s+and\s+)(?:play|show|open|then|add)\b',text,re.I):
        return None  # Preserve the established multi-step media/task grammar.
    explicit = bool(re.search(r'\bspotify\b', text, re.I))
    if re.fullmatch(r'play (?:this |the )?spotify link',text,re.I):
        return Command('spotify_request','clarify',json.dumps({'provider':'spotify','arguments':{'detail':'Provide the exact Spotify URI or official HTTPS resource URL.'}}))
    if re.search(r'\b(?:youtube|vlc)\b', text, re.I):
        return None
    clean = re.sub(r'\b(?:on|in|from|using) spotify\b|\bspotify(?: only| app)?\b', '', text, flags=re.I)
    clean = ' '.join(clean.split())

    def request(operation, **arguments):
        return Command('spotify_request', operation, json.dumps({'provider': 'spotify' if explicit else 'auto',
                                                                'arguments': arguments}))
    controls = {'play':'resume', 'resume my':'resume', 'resume':'resume', 'pause':'pause',
                'pause music':'pause', 'stop the desktop session':'local_stop', 'stop desktop session':'local_stop',
                'skip song':'next', 'play previous track':'previous', 'is paused':'status',
                'which song is playing':'status', 'which device is active':'devices',
                'show my queue':'queue', 'show the queue':'queue', 'show queue':'queue', 'play my saved songs':'play_saved_tracks',
                'save this song':'save_current', 'unsave this track':'remove_current_saved',
                'list saved albums':'saved_albums', 'show recently played':'recently_played',
                'show my top tracks last month':'top_tracks', 'turn off shuffle':'shuffle',
                'repeat one song':'repeat', 'repeat playlist':'repeat', 'mute only':'local_mute'}
    if clean.casefold() in controls and (explicit or clean.casefold() not in {'play','resume','pause'}):
        op = controls[clean.casefold()]
        args = {'enabled': False} if op == 'shuffle' else ({'enabled': True} if op == 'local_mute' else {})
        if op == 'repeat': args['mode'] = 'track' if 'one' in clean else 'context'
        if op == 'top_tracks': args['time_range'] = 'short_term'
        return request(op, **args)
    match = re.fullmatch(r'(?:jump|skip) to (\d{1,3}) minutes?(?: (\d{1,2}) seconds?)?', clean, re.I)
    if match:
        return request('seek', position_ms=(int(match[1])*60+int(match[2] or 0))*1000)
    match = re.fullmatch(r'(?:make|set)(?: app)? (\d{1,3})\s*%', clean, re.I)
    if match and explicit:
        return request('local_volume', percent=int(match[1]))
    match = re.fullmatch(r'(raise|lower)(?: the)? volume by (\d{1,3})\s*%', clean, re.I)
    if match:
        return request('local_volume_relative', delta=int(match[2])*(1 if match[1].lower()=='raise' else -1))
    match = re.fullmatch(r'(?:open search for|search(?: songs)?(?: for)?) (.+)', clean, re.I)
    if match and (explicit or clean.lower().startswith('search songs by ')):
        query = 'artist:'+match[1][3:] if clean.lower().startswith('search songs by ') else match[1]
        return request('open_search' if clean.lower().startswith('open') else 'search_tracks', query=query)
    match = re.fullmatch(r'play (spotify:[^\s]+|https://open\.spotify\.com/[^\s]+)', text, re.I)
    if match:
        return request('play_resource', ref=match[1])
    match = re.fullmatch(r'create private playlist (.+)', clean, re.I)
    if match: return request('create_playlist', name=match[1], public=False)
    match = re.fullmatch(r'(?:add|queue) (?:song )?(.+?) to (?:my |the )?queue', clean, re.I)
    if match: return request('queue_search', query=match[1])
    match = re.fullmatch(r'(?:switch|transfer) playback to (.+?)(?: device)?', clean, re.I)
    if match: return request('transfer_named', device_name=match[1])
    match = re.fullmatch(r'play the (\d+)(?:st|nd|rd|th) item in playlist (.+)', clean, re.I)
    if not match:
        match = re.fullmatch(r'play the (first|second|third|fourth|fifth) item in playlist (.+)', clean, re.I)
    if match:
        ordinal = int(match[1]) if match[1].isdigit() else ['first','second','third','fourth','fifth'].index(match[1])+1
        return request('playlist_named', playlist_name=match[2], offset=ordinal-1)
    match = re.fullmatch(r'show my playlist (.+?) songs', clean, re.I)
    if match: return request('playlist_items_named', playlist_name=match[1])
    match = re.fullmatch(r'add current song to playlist (.+)', clean, re.I)
    if match: return request('add_current_named', playlist_name=match[1])
    match = re.fullmatch(r'rename playlist (.+?) to (.+)', clean, re.I)
    if match: return request('rename_named', playlist_name=match[1], new_name=match[2])
    if re.fullmatch(r'(?:add current song|show my playlist songs)',clean,re.I):
        return request('clarify',detail='Name the exact destination Spotify playlist or its URI.')
    if re.search(r'\b(?:rename playlist|remove .*playlist|reorder|replace .*playlist)\b', clean, re.I):
        return request('clarify', detail='Name an exact playlist URI and exact items/positions. Use Spotify tool discovery; destructive edits require a fresh approval.')
    return None


def call(actions, operation, arguments, cancelled):
    from .tools import ToolRegistry
    result = ToolRegistry(actions).execute({'action':'mcp_call', 'value':'spotify',
        'content':json.dumps({'name':'spotify_'+operation, 'arguments':arguments})}, cancelled)
    envelope = json.loads(result.evidence)
    data = envelope['structuredContent']['result']['untrusted_data']
    if isinstance(data, dict) and data.get('ok') is True and (
            data.get('accepted') or data.get('opened_requested') or data.get('search_opened') or data.get('verified')):
        actions.last_media = 'spotify'
    return data


def execute(actions, operation, arguments, cancelled):
    """Exact targets only; searches/readbacks never automatically repeat a write."""
    if operation == 'clarify':
        return arguments['detail']
    if operation == 'local_volume_relative':
        delta = arguments.get('delta')
        if type(delta) is not int or not -100 <= delta <= 100:
            raise ValueError('Choose a volume change between -100 and 100.')
        state = call(actions, 'local_volume_status', {}, cancelled)
        values = state.get('volume_percent', [])
        if not values or len(set(values)) != 1:
            raise ValueError('Spotify audio sessions have different volumes; set an exact percentage.')
        return call(actions, 'local_volume', {'percent':max(0,min(100,values[0]+delta))}, cancelled)
    if operation == 'transfer_named':
        data = call(actions, 'devices', {}, cancelled)
        wanted = arguments['device_name'].casefold()
        rows = [r for r in data.get('devices', []) if isinstance(r,dict) and r.get('name','').casefold()==wanted]
        if len(rows)!=1 or not rows[0].get('id') or rows[0].get('is_restricted') or not rows[0].get('is_active'):
            raise ValueError('Choose one exact, active, unrestricted Spotify device; no transfer was sent.')
        return call(actions,'transfer',{'device':rows[0]['id'],'play':False},cancelled)
    if operation in {'playlist_named','playlist_items_named','add_current_named','rename_named'}:
        data = call(actions,'my_playlists',{'limit':50},cancelled)
        rows = [r for r in data.get('items',[]) if isinstance(r,dict) and r.get('name','').casefold()==arguments['playlist_name'].casefold()]
        if data.get('next') or len(rows)!=1 or not rows[0].get('uri'):
            raise ValueError('Playlist name is ambiguous or its listing is incomplete; specify its exact Spotify URI.')
        args = {'playlist':rows[0]['uri']}
        op = {'playlist_named':'play_playlist','playlist_items_named':'playlist_items',
              'add_current_named':'add_current_to_playlist','rename_named':'update_playlist'}[operation]
        if operation=='playlist_named': args['offset']=arguments['offset']
        if operation=='rename_named': args['name']=arguments['new_name']
        return call(actions,op,args,cancelled)
    if operation == 'play_resource':
        # Parse using the same reviewed identifier code as the child, without fetching URLs.
        from urllib.parse import urlsplit
        value = arguments['ref']
        kind = value.split(':')[1] if value.startswith('spotify:') else urlsplit(value).path.strip('/').split('/')[-2]
        if kind not in {'track','album','artist','playlist','episode','show'}:
            raise ValueError('Name a playable exact Spotify resource URI.')
        return call(actions,'play_'+kind,{kind:value},cancelled)
    return call(actions, operation, arguments, cancelled)


def route(actions, command, cancelled):
    """Return (handled, evidence). Disabled registration preserves existing handlers."""
    if command.kind not in {'spotify_request','spotify_control','spotify_volume','media_control',
                            'spotify_search','media_search','open','play_media'}:
        return False, None
    if not enabled(actions):
        if command.kind == 'spotify_request':
            raise ValueError('Spotify child connector is disabled. Enable its reviewed registration first.')
        return False, None
    from .agent_events import check_policy
    check_policy(actions, command.kind)
    operation, arguments = None, {}
    if command.kind == 'spotify_request':
        payload = json.loads(command.extra)
        if payload['provider'] == 'auto':
            from .media_player import active_service
            if active_service(actions) != 'spotify':
                raise ValueError('The selected provider is not Spotify; explicitly name Spotify for this operation.')
        operation, arguments = command.value, payload['arguments']
    elif command.kind == 'spotify_control' or (command.kind=='media_control' and command.extra=='spotify'):
        value = command.value
        operation = {'play':'resume','pause':'pause','next':'next','previous':'previous','status':'status',
                     'stop':'local_stop','shuffle_on':'shuffle','shuffle_off':'shuffle',
                     'repeat_one':'repeat','repeat_all':'repeat','repeat_off':'repeat'}.get(value)
        if value.startswith('seek_'):
            operation, arguments = 'seek_relative', {'delta_ms':int(value[5:])*1000}
        elif value.startswith('volume_'):
            return route(actions,type(command)('spotify_volume',value[7:]),cancelled)
        elif value in {'mute','unmute'}:
            operation, arguments = 'local_mute', {'enabled':value=='mute'}
        if operation=='shuffle': arguments={'enabled':value.endswith('_on')}
        if operation=='repeat': arguments={'mode':{'repeat_one':'track','repeat_all':'context','repeat_off':'off'}[value]}
    elif command.kind == 'spotify_volume':
        if command.value in {'mute','unmute'}:
            operation, arguments = 'local_mute', {'enabled':command.value=='mute'}
        elif command.value in {'up','down'}:
            operation, arguments = 'local_volume_relative', {'delta':10 if command.value=='up' else -10}
        else: operation, arguments = 'local_volume', {'percent':int(command.value)}
    elif command.kind in {'spotify_search','media_search'} and (command.kind=='spotify_search' or command.extra=='spotify'):
        operation, arguments = 'open_search', {'query':command.value}
    elif command.kind == 'open' and command.value.casefold()=='spotify':
        operation = 'open_desktop'
    elif command.kind == 'play_media' and command.extra=='spotify':
        operation, arguments = 'play_search', {'query':command.value}
        match = re.fullmatch(r'(.+?) by (.+)', command.value, re.I)
        if match: arguments={'query':match[1],'artist':match[2]}
    if operation is None:
        return False, None
    if operation == 'play_search' and not arguments.get('query','').startswith(('spotify:', 'https://open.spotify.com/')):
        health = call(actions, 'health', {}, cancelled)
        if health.get('api_authorized') is False:
            # Retain the already-reviewed native UIA song picker, only when auth is absent.
            # It verifies title/artist and raises PlaybackUncertain after a possibly sent click.
            from .media_player import play_spotify
            query = arguments['query'] + (' by '+arguments['artist'] if arguments.get('artist') else '')
            return True, play_spotify(actions, query, cancelled)
    if operation == 'play_search' and arguments.get('query','').startswith(('spotify:', 'https://open.spotify.com/')):
        operation, arguments = 'play_resource', {'ref':arguments['query']}
    data = execute(actions, operation, arguments, cancelled)
    return True, describe(data, operation)


def describe(data, operation):
    """Plain spoken receipts without an LLM, preserving acceptance vs verification."""
    if isinstance(data,str): return data
    if not isinstance(data,dict): return json.dumps(data,ensure_ascii=False)
    if data.get('reason') in {'ambiguous_results','not_one_exact_match','no_results'}:
        return 'Spotify found no unique exact match. Specify the title and artist or an exact Spotify URI. '+json.dumps(data.get('candidates',[]),ensure_ascii=False)
    if data.get('opened_requested'):
        return 'Requested Spotify to open the app or item; playback is not verified.'
    if data.get('search_opened'):
        return 'Opened Spotify search. Choose a result to start playback.'
    if operation in {'status','local_status'}:
        state=data.get('playback') if data.get('source')=='spotify_web_api' else data
        if not state: return 'Spotify has no active player.'
        title=(state.get('item') or {}).get('name') or state.get('title') or 'Unknown track'
        status=('playing' if state.get('is_playing') else 'paused') if 'is_playing' in state else state.get('playback_status','unknown')
        return 'Spotify is '+str(status)+': '+str(title)[:200]+'.'
    playback=data.get('playback') if isinstance(data.get('playback'),dict) else data
    if playback.get('playing_verified'):
        return 'Spotify playback is verified.'
    if playback.get('accepted'):
        return ('Spotify '+operation.replace('_',' ')+' verified.' if playback.get('verified') else
                'Spotify accepted '+operation.replace('_',' ')+'. The updated state has not been verified.')
    return json.dumps({'provider':'spotify','result':data},ensure_ascii=False)
