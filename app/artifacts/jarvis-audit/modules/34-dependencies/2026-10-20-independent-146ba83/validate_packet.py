"""Check audit references/counts/hash preservation without application operations."""
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
APP=next(p for p in OUT.parents if (p/'main.py').is_file())
required=['inventory.md','baseline.json','tests.jsonl','failures.md','changes.md','cross-pillar-matrix.md',
          'benchmarks.csv','compatibility.md','security.md','rollback.md','codex-findings-reconciliation.md','verdict.md']
for name in required: assert (OUT/name).is_file(),name
for name in ['source-hashes.json','prior-evidence-hashes.json']:
    for path,digest in json.loads((OUT/name).read_text(encoding='utf-8')).items():
        assert hashlib.sha256((APP/path).read_bytes()).hexdigest()==digest,path
rows=[json.loads(s) for s in (OUT/'executed-results.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(rows)==167
assert sum(r['status']=='PASS' for r in rows)==164
assert sum(r['status']=='FAIL' for r in rows)==2
assert sum(r['status']=='SKIPPED' for r in rows)==1
cases=[json.loads(s) for s in (OUT/'tests.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(cases)==len({r['id'] for r in cases})==22
sbom=json.loads((OUT/'environment-sbom.json').read_text(encoding='utf-8'))
assert len(sbom['environments'])==10
for name in ['environment-sbom.json','dependency-graph.json','lockfile-map.json','worker-interpreters.json','os-gpu-tools.json','ollama-models.json']:
    assert json.loads((OUT/name).read_text(encoding='utf-8'))
for path in OUT.glob('*.md'):
    for link in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        if not link.startswith('https://'): assert (path.parent/link).is_file(),(path,link)
for path in [APP/'README.md',APP.parent/'README.md',APP/'docs/CRASH_RECOVERY.md']:
    paragraph=path.read_text(encoding='utf-8').split('\n\n')[1]
    for link in re.findall(r'\]\(([^)]+)\)',paragraph): assert (path.parent/link).is_file(),(path,link)
report={'date':'2026-10-20','mandatory_reports':12,'stable_cases':22,'checks':167,'pass':164,'fail':2,'skipped':1,
        'actual_environments':10,'source_and_original_evidence_hashes':'MATCH','new_report_readme_links':'PASS',
        'scope':'Packet validation only; P1s remain open'}
(OUT/'packet-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
