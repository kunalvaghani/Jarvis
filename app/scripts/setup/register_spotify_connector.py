"""Explicit local Spotify registration/rollback; never login or change playback."""
import argparse
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parents[2]


def register(base=BASE, python=None, disable=False):
    base = Path(base).resolve(strict=True)
    server = base / 'integrations/jarvis-connectors/connectors/apps/spotify/server.py'
    path = base / '.jarvis/mcp.json'
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'servers': {}}
    if set(data) != {'servers'} or not isinstance(data['servers'], dict):
        raise ValueError('Existing MCP configuration is invalid; preserve and repair it first.')
    if path.exists():
        backup = base / '.jarvis-runtime/backups' / ('mcp-before-spotify-' + str(time.time_ns()) + '.json')
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(path.read_bytes())
    if disable:
        if 'spotify' in data['servers']:
            data['servers']['spotify']['enabled'] = False
    else:
        matrix = json.loads((base/'integrations/jarvis-connectors/connectors/apps/spotify/catalog.json').read_text())
        executable = Path(python or sys.executable).resolve(strict=True)
        data['servers']['spotify'] = {
            'enabled': True, 'trusted': True, 'persistent': True,
            'command': str(executable), 'args': [str(server), '--runtime', 'builtin', '--allow-write'],
            'allow_tools': [row['tool'] for row in matrix], 'env_names': ['SPOTIFY_CLIENT_ID'],
            'timeout_seconds': 50}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.spotify-tmp')
    temporary.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)
    return data['servers'].get('spotify', {})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', help='Existing absolute Python executable (no environment is installed).')
    parser.add_argument('--disable', action='store_true', help='Disable Spotify registration; retain all other servers.')
    options = parser.parse_args()
    register(python=options.python, disable=options.disable)
    print('Spotify registration disabled.' if options.disable else 'Spotify registered. OAuth login remains human-only.')
