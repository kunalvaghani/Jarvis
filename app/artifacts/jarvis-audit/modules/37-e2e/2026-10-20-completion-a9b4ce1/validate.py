"""Validate completed packet and newly written documentation links."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
required = ['inventory.md', 'baseline.json', 'tests.jsonl', 'failures.md', 'changes.md', 'cross-pillar-matrix.md',
            'benchmarks.csv', 'compatibility.md', 'security.md', 'rollback.md', 'codex-findings-reconciliation.md', 'verdict.md']
assert all((OUT / name).is_file() for name in required)
for path in OUT.glob('*.json'): json.loads(path.read_text(encoding='utf-8'))
for path in OUT.glob('*.jsonl'):
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip(): json.loads(line)
hashes = json.loads((OUT / 'source-hashes.json').read_text())
assert all(hashlib.sha256((APP / p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())
cases = [json.loads(line) for line in (OUT / 'tests.jsonl').read_text().splitlines()]
assert len(cases) == len({c['id'] for c in cases}) == 26
assert sum(c['status'] == 'BLOCKED' for c in cases) == 26
checks = [(p, p.read_text(encoding='utf-8')) for p in OUT.glob('*.md')]
for path in [APP / 'README.md', APP.parent / 'README.md']:
    block = re.search(r'<!-- prompt37-e2e -->(.*?)<!-- /prompt37-e2e -->', path.read_text(encoding='utf-8'), re.S)
    assert block
    checks.append((path, block.group(1)))
handoff = APP / 'docs/CLAUDE_HANDOFF.md'
section = handoff.read_text(encoding='utf-8').split('## Prompt 37 —', 1)[1].split('## Prompt 36 —', 1)[0]
checks.append((handoff, section))
count = 0
for path, body in checks:
    for match in re.finditer(r'\[[^\]]+\]\(([^)]+)\)', body):
        link = match.group(1)
        if '://' in link or link.startswith('#'): continue
        assert (path.parent / link.split('#')[0]).exists(), (path, link)
        count += 1
result = subprocess.run(['git', 'diff', '--check'], cwd=APP.parent, capture_output=True, text=True)
assert result.returncode == 0, result.stdout + result.stderr
data = json.loads((OUT / 'validation.json').read_text())
data.update({'new_packet_readme_handoff_links_checked': count, 'json_jsonl_parse': 'PASS',
    'git_diff_check': 'PASS', 'source_hash_readback': 'PASS'})
(OUT / 'validation.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
print(json.dumps(data, indent=2))
