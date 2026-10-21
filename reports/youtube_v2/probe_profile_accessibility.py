"""Read-only native adapter readiness; save only known media controls, no page text."""
import json
from pathlib import Path
import sys
import time
from collections import Counter

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'app'))
from jarvis.media_ui import find_media_handle, platform_of, LABELS
from jarvis.ui_transport import UITransport

transport = UITransport(HERE.parents[1]/'app')
result = {'scope':'read-only native accessibility; no browser launch, no media action', 'profile':'user-selected Default'}
start = time.perf_counter()
try:
    handle = find_media_handle('youtube')
    if not handle:
        raise ValueError('No visible YouTube media window; select its tab in Default Chrome')
    snapshot = transport.request({'operation':'list','handle':handle,'owner_pid':__import__('os').getpid()})
    result['youtube_window_observed'] = platform_of(snapshot)=='youtube'
    result['control_roles'] = dict(Counter(c.get('role','unknown') for c in snapshot.get('controls', [])))
    known = {label.casefold() for labels in LABELS.values() for label in labels}
    result['known_controls'] = [dict(name=c['name'],role=c['role']) for c in snapshot.get('controls', [])
        if c.get('name','').casefold() in known]
    result['sliders'] = [dict(role=c['role'],kind='volume' if 'volume' in c.get('name','').casefold() else 'seek')
        for c in snapshot.get('controls', []) if c.get('role')=='Slider'
        and any(word in c.get('name','').casefold() for word in ['volume','seek','progress','timeline'])]
except Exception as exc:
    result['error_type'] = type(exc).__name__
    result['reason'] = 'Native media observation unavailable; inspect selected YouTube tab before actions'
finally:
    transport.close()
    result['elapsed_ms'] = round((time.perf_counter()-start)*1000,3)
    (HERE/'profile-accessibility-readiness.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
