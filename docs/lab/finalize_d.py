import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
r=json.loads((ROOT/'app/.jarvis-runtime/lab-validation/d-full-final.json').read_text(encoding='utf-8'))
b=json.loads((ROOT/'docs/lab/evidence/c4-full-final.json').read_text(encoding='utf-8'))
old=set(b['remaining_failure_ids']);now={x['test'] for x in r['reports'] if x['outcome']=='failed'}
a={k:v for k,v in r.items() if k!='reports'}
a.update(new_failure_ids=sorted(now-old),resolved_failure_ids=sorted(old-now),remaining_failure_ids=sorted(now),discovery_failures=sorted(x for x in now if 'test_discovery_' in x))
(ROOT/'docs/lab/evidence/d-full-final.json').write_text(json.dumps(a,indent=2),encoding='utf-8')
print(json.dumps(a))
if r['source_sha256_before']!=r['source_sha256_after']:raise ValueError('source changed during run')
if a['new_failure_ids'] or r['errors'] or r['collection_errors']:raise ValueError('new failures need triage')
