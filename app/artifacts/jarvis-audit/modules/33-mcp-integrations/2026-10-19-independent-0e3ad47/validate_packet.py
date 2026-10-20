"""Validate saved evidence references without rerunning application tests."""
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
required = ['inventory.md','baseline.json','tests.jsonl','failures.md','changes.md',
    'cross-pillar-matrix.md','benchmarks.csv','compatibility.md','security.md',
    'rollback.md','codex-findings-reconciliation.md','verdict.md']
for name in required:
    assert (OUT / name).is_file(), name
for listing in ['source-hashes.json','prior-evidence-hashes.json']:
    for name, digest in json.loads((OUT / listing).read_text(encoding='utf-8')).items():
        assert hashlib.sha256((APP / name).read_bytes()).hexdigest() == digest, name
cases = [json.loads(line) for line in (OUT / 'tests.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(cases) == len({r['id'] for r in cases}) == 22
results = [json.loads(line) for line in (OUT / 'executed-results.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(results) == 172
assert sum(r['status']=='PASS' for r in results)==169
assert sum(r['status']=='FAIL' for r in results)==3
for root in (APP / 'README.md', APP.parent / 'README.md'):
    paragraph = root.read_text(encoding='utf-8').split('\n\n')[1]
    for link in re.findall(r'\]\(([^)]+)\)', paragraph):
        assert (root.parent / link).is_file(), link
for doc in OUT.glob('*.md'):
    for link in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8')):
        assert (doc.parent / link).is_file(), (doc,link)
report = {'mandatory_deliverables':len(required),'stable_cases':len(cases),
    'executed_checks':len(results),'passed':169,'failed':3,
    'source_and_historical_hashes':'MATCH','local_report_and_new_readme_links':'PASS'}
(OUT / 'packet-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
