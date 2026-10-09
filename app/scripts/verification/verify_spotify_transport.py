"""Opt-in live transport check; restore the observed playback state once.

Records operational metadata only. Does not search, select tracks or change
account/library data. An uncertain action is never repeated automatically.
"""
from jarvis.paths import APP_ROOT, artifact_path
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from jarvis.spotify import _control, _spotify_session


async def verify(live=False):
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    record = {'date': datetime.now(timezone.utc).isoformat(), 'live': live,
              'scope': 'Native Spotify source-scoped transport; no track or account metadata.'}
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    try:
        session = _spotify_session(manager)
        status = lambda: session.get_playback_info().playback_status.name.lower()
        before = status()
        record['initial_status'] = before
        if not live:
            record['passed'] = False
            record['observation_only'] = True
            return record
        if before not in {'playing', 'paused'}:
            raise ValueError('Playback state must be playing or paused before this live check.')
        target = 'pause' if before == 'playing' else 'play'
        restore = 'play' if before == 'playing' else 'pause'
        expected = 'paused' if target == 'pause' else 'playing'
        record['action'] = target
        try:
            record['response'] = await _control(target, lambda: False)
            record['status_observations'] = [status()]
            for _ in range(10):
                if record['status_observations'][-1] == expected:
                    break
                await asyncio.sleep(.2)
                record['status_observations'].append(status())
            record['observed_status'] = status()
        finally:
            # Inspect fresh state before the distinct restoration action. A
            # failed action is not retried; other unexpected states are retained.
            fresh = status()
            record['fresh_status_before_restore'] = fresh
            if fresh == expected:
                record['restore_response'] = await _control(restore, lambda: False)
            record['final_status'] = status()
        record['passed'] = record['observed_status'] == expected and record['final_status'] == before
    except Exception as exc:
        record.update(passed=False, error_type=type(exc).__name__)
    return record


if __name__ == '__main__':
    if sys.argv[1:] not in ([], ['--live']):
        raise SystemExit('Use --live only with operator-authorized playback testing.')
    try:
        receipt = asyncio.run(asyncio.wait_for(verify('--live' in sys.argv), 15))
    except (TimeoutError, KeyboardInterrupt):
        receipt = {'date': datetime.now(timezone.utc).isoformat(), 'passed': False,
                   'error': 'Observation/control deadline or interruption; inspect playback before repeating.',
                   'automatically_replayed': False}
    destination = artifact_path(Path(__file__).resolve().parents[2], 'production-spotify-transport.json')
    if destination.exists():
        history = destination.with_name('production-spotify-transport-history.json')
        rows = json.loads(history.read_text(encoding='utf-8')) if history.exists() else []
        rows.append(json.loads(destination.read_text(encoding='utf-8')))
        history.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    destination.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))
    raise SystemExit(0 if receipt['passed'] else 1)
