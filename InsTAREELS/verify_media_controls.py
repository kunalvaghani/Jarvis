"""Opt-in live search/launch check; no song/video playback or account writes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def windows():
    import win32gui
    found = set()
    win32gui.EnumWindows(lambda handle, _: found.add(handle) if win32gui.IsWindowVisible(handle) else None, None)
    return found


def inspect(handle):
    request = {'operation': 'list', 'handle': handle, 'owner_pid': os.getpid()}
    result = subprocess.run([sys.executable, '-m', 'jarvis.ui_worker', json.dumps(request)],
                            capture_output=True, text=True, timeout=25,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError('UI inspection worker failed.')
    snapshot = json.loads(result.stdout)
    if snapshot.get('error'):
        raise ValueError(snapshot['error'])
    return snapshot


def await_window(platform):
    from jarvis.media_ui import find_media_handle
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        handle = find_media_handle(platform)
        if handle:
            return handle
        time.sleep(.3)
    raise ValueError('The media window was not observed after launch.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Open a temporary YouTube test window and native Spotify, enter a generic YouTube query; never start playback.')
    args = parser.parse_args()
    if not args.live:
        parser.error('Use --live to opt in to visible app launch and a generic search.')
    import win32gui
    from jarvis.actions import Desktop
    from jarvis.browser import browser_args, music_search_url
    from jarvis.commands import Command
    from jarvis.media_ui import platform_of, search_current
    from jarvis.ui_controls import UIControls
    base = Path(__file__).resolve().parent
    config = json.loads((base / 'config.json').read_text(encoding='utf-8'))
    report = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'playback_tested': False}
    prior = windows()
    youtube = None
    try:
        subprocess.Popen([*browser_args(config['apps'], 'chrome'), '--new-window', music_search_url('Jarvis search test', 'youtube')], shell=False)
        youtube = await_window('youtube')
        snapshot = inspect(youtube)
        report['youtube'] = {'platform_detected': platform_of(snapshot), 'search_field_exposed': any(c['role'] == 'Edit' and c['name'] == 'Search' for c in snapshot['controls'])}
        ui = UIControls(Desktop())
        ui._handle = lambda: youtube
        query = 'Jarvis desktop media controls test'
        result = search_current(ui, 'youtube', query)
        report['youtube']['field_submission_attempted'] = result is not None
        report['youtube']['exact_text_verified_before_submission'] = bool(result and result.startswith('Entered and verified'))
        # Only read after the one submission; never retry a failed write.
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if query.casefold() in win32gui.GetWindowText(youtube).casefold():
                report['youtube']['results_title_verified'] = True
                break
            time.sleep(.3)
        report['youtube'].setdefault('results_title_verified', False)
    except Exception as exc:
        report.setdefault('youtube', {})['error'] = str(exc)[:300]
    finally:
        # Close only the additional test window observed after our --new-window
        # request. Never close a pre-existing window or kill shared Chrome.
        if youtube and youtube not in prior and win32gui.IsWindow(youtube):
            win32gui.PostMessage(youtube, 0x0010, 0, 0)
    try:
        from jarvis.actions import Actions
        actions = Actions(config, base, lambda *args: None)
        try:
            launched = actions.execute(Command('open', 'spotify'))
        finally:
            actions.close()
        handle = await_window('spotify')
        snapshot = inspect(handle)
        report['spotify'] = {'native_launch_reported': 'native Spotify' in launched,
                             'native_window_verified': platform_of(snapshot) == 'spotify',
                             'accessible_control_count': len(snapshot['controls'])}
    except Exception as exc:
        report['spotify'] = {'error': str(exc)[:300]}
    (base / 'artifacts/media-controls-check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
