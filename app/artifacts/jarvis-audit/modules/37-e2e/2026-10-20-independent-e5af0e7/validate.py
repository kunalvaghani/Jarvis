import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p/'main.py').is_file())
SOURCE = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')
required=['inventory.md','baseline.json','tests.jsonl','failures.md','changes.md','cross-pillar-matrix.md',
          'benchmarks.csv','compatibility.md','security.md','rollback.md','codex-findings-reconciliation.md','verdict.md']
assert all((OUT/name).is_file() for name in required)
for path in OUT.glob('*.json'): json.loads(path.read_text(encoding='utf-8'))
for path in OUT.glob('*.jsonl'):
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip(): json.loads(line)
hashes=json.loads((OUT/'source-hashes.json').read_text())
assert all(hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
old=json.loads((OUT/'prior-evidence-hashes.json').read_text())
assert all(hashlib.sha256((APP/name).read_bytes()).hexdigest()==digest for name,digest in old.items())
patch=subprocess.run(['git','apply','--check','--cached',str(OUT/'new-test.patch')],cwd=SOURCE,capture_output=True,text=True)
assert patch.returncode==0,patch.stderr
checks=[(p,p.read_text(encoding='utf-8')) for p in OUT.glob('*.md')]
for path in [APP/'README.md',APP.parent/'README.md']:
    marker=re.search(r'<!-- prompt37-e5af-verification -->(.*?)<!-- /prompt37-e5af-verification -->',path.read_text(encoding='utf-8'),re.S)
    assert marker
    checks.append((path,marker.group(1)))
handoff=APP/'docs/CLAUDE_HANDOFF.md'
checks.append((handoff,handoff.read_text(encoding='utf-8').split('## Prompt 37 - independent committed-source continuation',1)[1].split('## Prompt 37 follow-up -',1)[0]))
count=0
for path,body in checks:
    for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)',body):
        if '://' in link or link.startswith('#'):continue
        assert (path.parent/link.split('#')[0]).exists(),(path,link)
        count+=1
samples=list(csv.DictReader((OUT/'benchmarks.csv').open(encoding='utf-8')))
summary={}
for variant in ['pinned','current']:
    rows=[r for r in samples if r['revision']==variant]
    values=sorted(int(r['elapsed_ns']) for r in rows)
    summary[variant]={'n':len(values),'p50_ns':statistics.median(values),'p95_ns_nearest_rank':values[math.ceil(.95*len(values))-1],
        'sample_variance_ns2':statistics.variance(values),'cleanup_successes':sum(r['cleanup_before_harness']=='True' for r in rows)}
summary['scope']='a9b4ce1 original demonstration vs e5af0e7 integrated code; fake observer-failure cleanup, durable write overhead, no assistant performance claim'
(OUT/'benchmark-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
assert subprocess.run(['git','diff','--check'],cwd=APP.parent).returncode==0
assert subprocess.run(['git','diff','--quiet'],cwd=SOURCE).returncode==0
data=json.loads((OUT/'validation.json').read_text())
data.update({'required_reports':len(required),'local_links_checked':count,'prior_packet_files_unchanged':len(old),
    'current_source_files_checked':len(hashes),'new_test_patch_applies_to_pinned_index':True,'pinned_tracked_tree_clean':True})
(OUT/'validation.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
print(json.dumps(data,indent=2))
