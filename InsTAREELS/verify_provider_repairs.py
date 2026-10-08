"""Fresh reads of previously failing providers and the documented Countries demo.

Receipts contain status/metadata only, never configured URLs, response bodies or keys.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch

from jarvis.realtime import settings
from jarvis.realtime_sources import Sources

BASE = Path(__file__).resolve().parent
CASES = {'arxiv': {'query': 'earth'}, 'bluesky': {'query': 'news'},
    'dictionary': {'id': 'hello'}, 'gdacs': {}, 'gdelt': {'query': 'climate'},
    'listenbrainz': {'id': 'iliekcomputers'}, 'open_notify': {},
    'semantic_scholar': {'query': 'earth'}, 'spacex': {}, 'worldtime': {'timezone': 'Asia/Kolkata'}}


def receipt(row, credential_scope='no_new_credentials'):
    return {key: row.get(key) for key in ('provider', 'status', 'detail', 'fetched_utc', 'reference')} | {
        'credential_scope': credential_scope,
        'records': len(row.get('data', [])) if isinstance(row.get('data'), (list, dict)) else 0}


def main():
    options = settings(json.loads((BASE/'config.json').read_text())['realtime'])
    def fetch(item):
        key, args = item
        row = receipt(Sources(options).fetch(key, args)); print(json.dumps(row), flush=True); return row
    with ThreadPoolExecutor(max_workers=2) as pool: rows = list(pool.map(fetch, CASES.items()))
    configured = receipt(Sources(options).fetch('countries', {'id': 'India'}), 'operator_local_configuration')
    rows.append(configured)
    # This is the openly documented demo token, not an operator credential or bypass.
    with patch.dict('os.environ', {'JARVIS_REALTIME_COUNTRIES_KEY': 'rc_live_demo'}):
        demo = Sources(options).fetch('countries', {'id': 'India'})
    rows.append(receipt(demo, 'provider_documented_public_demo_only'))
    record = {'date': datetime.now(timezone.utc).isoformat(), 'scope': 'Bounded live retest of ten previously unavailable reads; corrected Countries adapter separately with operator configuration and documented public demo. Demo success does not certify an operator key.', 'checks': rows}
    (BASE/'artifacts/production-provider-recheck.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(rows[-2:]), flush=True)


if __name__ == '__main__': main()
