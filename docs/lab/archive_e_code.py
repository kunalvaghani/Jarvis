"""Recover the exact recorded live oracle snapshot, accepting only its recorded hash.

Two post-proof fail-closed catalogue/regression checks are reversed in memory.
No application source is modified or executed; both archive hashes must match
the original actual-run receipt before immutable text snapshots are written.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/lab/evidence'
record=json.loads((OUT/'e-local-acceptance.json').read_text())
current=(ROOT/'app/jarvis/discovery/acceptance.py').read_bytes().decode('utf-8')
old=current.replace("        status=('FAILED' if support['status']=='FAILED' else 'PARTIAL') if support else 'UNMET'\n",'')
old=old.replace("'status':status,","'status':'PARTIAL' if support else 'UNMET',")
old=old.replace("    if sum(r['outcome']=='failed' for r in current['reports'])!=current['failed']:\n        raise ValueError('regression failure count differs from actual reports')\n",'')
snapshots={'oracle':old.encode('utf-8'),'harness':(ROOT/'app/benchmarks/live/discovery_lab.py').read_bytes()}
for key,raw in snapshots.items():
    if hashlib.sha256(raw).hexdigest()!=record[key+'_sha256']:raise ValueError('cannot recover exact recorded '+key+' source')
for key,raw in snapshots.items():
    with (OUT/('e-'+key+'-executed.py.txt')).open('xb') as f:f.write(raw)
print(json.dumps({'recorded_live_source_hashes_matched':list(snapshots),'application_source_changed':False,'source_executed':False}))
