"""Validate saved evidence, references, identities and counts without rerunning tests."""
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
APP=next(p for p in OUT.parents if (p/'main.py').is_file())
required=['inventory.md','baseline.json','tests.jsonl','failures.md','changes.md','cross-pillar-matrix.md',
          'benchmarks.csv','compatibility.md','security.md','rollback.md','codex-findings-reconciliation.md','verdict.md']
for name in required:
    assert (OUT/name).is_file(),name
for manifest in ['source-hashes.json','prior-evidence-hashes.json']:
    for path,digest in json.loads((OUT/manifest).read_text(encoding='utf-8')).items():
        assert hashlib.sha256((APP/path).read_bytes()).hexdigest()==digest,path
rows=[json.loads(s) for s in (OUT/'executed-results.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(rows)==279
assert sum(r['status']=='PASS' for r in rows)==273
assert sum(r['status']=='FAIL' for r in rows)==6
cases=[json.loads(s) for s in (OUT/'tests.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(cases)==len({r['id'] for r in cases})==22
comp=json.loads((OUT/'replay-source-comparison.json').read_text(encoding='utf-8'))
assert comp['MCP_fixture_byte_identical'] and comp['recovery_fixture_byte_identical']
assert comp['optional_provider_source_unchanged_by_repair']
for path in OUT.glob('*.md'):
    for link in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        assert (path.parent/link).is_file(),(path,link)
for path in [APP/'README.md',APP.parent/'README.md',APP/'docs/CRASH_RECOVERY.md']:
    paragraph=path.read_text(encoding='utf-8').split('\n\n')[1]
    for link in re.findall(r'\]\(([^)]+)\)',paragraph):
        assert (path.parent/link).is_file(),(path,link)
report={'date':'2026-10-19','mandatory_reports':12,'stable_cases':22,'checks':279,'passed':273,'failed':6,
        'source_and_prior_packet_hashes':'MATCH','copied_repro_assertions':'BYTE IDENTICAL',
        'new_report_readme_links':'PASS','scope':'packet validation, not application acceptance'}
(OUT/'packet-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
