"""Public-content launch through real Jarvis methods in Chrome Default only.

This harness does not claim microphone, running GUI, MCP-v2, DOM or all-tool coverage.
It records only the named public media session, never other tabs/session titles.
"""
import json
from pathlib import Path
import statistics
import sys
import threading
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
APP = HERE.parents[1]/'app'
sys.path.insert(0, str(APP))
from jarvis.actions import Actions
from jarvis.commands import parse
from jarvis.tools import ToolRegistry
from jarvis import youtube_chrome


def main():
    config = json.loads((APP/'config/config.json').read_text(encoding='utf-8'))
    # Real dispatch methods, isolated bookkeeping. No replacement browser or model.
    a = Actions.__new__(Actions)
    a.base, a.config = APP, {'media': config['media']}
    a.apps = {'chrome':[r'C:\Program Files\Google\Chrome\Application\chrome.exe']}
    a.report = lambda *args: None
    a.projects = SimpleNamespace(pending=None)
    a.ui_controls = a.desktop = a.browser_automation = None
    a.last_media, a.youtube_target = None, ''
    a.closed = threading.Event()
    a._browser = lambda: (_ for _ in ()).throw(AssertionError('Alternate browser forbidden'))
    registry = ToolRegistry(a)
    rows = []
    title = 'Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film'
    private_session = '--current-session' in sys.argv
    if private_session:
        sessions = youtube_chrome.sessions()
        if len(sessions) != 1:
            raise ValueError('Exactly one Chrome media session is required; no action dispatched')
        title = sessions[0]['title']

    def run(text, step=None):
        start = time.perf_counter()
        try:
            command = parse(text)
            if step is None:
                if command.kind == 'open':
                    step = {'action':'browse','value':command.value,'browser':'chrome'}
                elif command.kind == 'browse':
                    step = {'action':'browse','value':command.value,'browser':'chrome'}
                elif command.kind == 'media_control':
                    step = {'action':'media_control','value':command.value,'platform':command.extra}
                else:
                    raise ValueError('Unsupported harness command: '+command.kind)
            result = registry.execute(step, lambda:False)
            evidence = result.evidence.replace(title, '[selected YouTube session]') if private_session else result.evidence
            rows.append({'text':text,'parsed':command.kind,'tool':step['action'], 'evidence':evidence,
                         'elapsed_ms':round((time.perf_counter()-start)*1000,3)})
        except Exception as exc:
            rows.append({'text':text,'error':str(exc)[:350], 'elapsed_ms':round((time.perf_counter()-start)*1000,3)})

    if '--controls-only' in sys.argv or private_session:
        a.youtube_target = 'user_chrome'
        a.last_media = 'youtube'
    else:
        run('open https://www.youtube.com/watch?v=aqz-KE-bpKQ')
    a.last_youtube = {'title':title}
    observed = []
    deadline = time.monotonic()+35
    while time.monotonic() < deadline:
        matches = [r for r in youtube_chrome.sessions() if youtube_chrome.matches(title, r['title'])]
        if len(matches) == 1:
            observed = matches
            break
        time.sleep(.5)
    if observed:
        run('pause on youtube')
        run('resume on youtube')
        for _ in range(5):
            run('what is playing on youtube')
        run('pause on youtube')
        if private_session and observed[0]['status'] == 'playing':
            run('resume on youtube')
    target = 'profile-current-controls-live.json' if private_session else 'profile-controls-live.json' if '--controls-only' in sys.argv else 'profile-live.json'
    (HERE/target).write_text(json.dumps({
        'profile':'Default', 'shortcut':'Comedy with - Chrome',
        'scope':'Real commands.parse -> ToolRegistry -> Actions -> Chrome/Windows media session; harness bookkeeping, not running GUI or v2 MCP',
        'session_observed': [{'status':r['status'], 'title':'[selected YouTube session]'} for r in observed] if private_session else observed,
        'results':rows,
        'warm_status_p50_ms':statistics.median([r['elapsed_ms'] for r in rows if r['text']=='what is playing on youtube']) if observed else None,
        'alternate_browser_started':False,
    }, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
