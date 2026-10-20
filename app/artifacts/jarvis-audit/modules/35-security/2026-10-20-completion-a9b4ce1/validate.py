"""Validate final evidence integrity and links; never executes application actions."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
ROOT = APP.parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

required = ['inventory.md', 'baseline.json', 'tests.jsonl', 'failures.md', 'changes.md', 'cross-pillar-matrix.md',
            'benchmarks.csv', 'compatibility.md', 'security.md', 'rollback.md', 'codex-findings-reconciliation.md', 'verdict.md']
assert all((OUT / name).is_file() for name in required)
for path in OUT.glob('*.json'):
    json.loads(path.read_text(encoding='utf-8-sig'))
for path in OUT.glob('*.jsonl'):
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.strip(): json.loads(line)
rows = [json.loads(line) for line in (OUT / 'tests.jsonl').read_text(encoding='utf-8').splitlines()]
assert [r['id'] for r in rows] == [f'JRV-35-{i:03}' for i in range(1, 25)]
for name, expected in json.loads((OUT / 'source-hashes.json').read_text()).items():
    assert sha(APP / name) == expected, name
for name, expected in json.loads((OUT / 'prior-evidence-hashes.json').read_text()).items():
    assert sha(OUT.parent / name) == expected, name
previous = OUT.parent.parent / '34-dependencies/2026-10-20-completion-a9b4ce1'
expected = json.loads((previous / 'source-hashes.json').read_text())['jarvis/repair_authorization.py']
assert sha(APP / 'jarvis/repair_authorization.py') == expected
links = 0
for path in [*OUT.glob('*.md'), APP / 'docs/CLAUDE_HANDOFF.md']:
    for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        if '://' in link or link.startswith('#'): continue
        assert (path.parent / link.split('#')[0]).resolve().exists(), (str(path), link)
        links += 1
for path in [ROOT / 'README.md', APP / 'README.md']:
    section = path.read_text(encoding='utf-8').split('<!-- prompt35-security -->')[1].split('<!-- /prompt35-security -->')[0]
    for link in re.findall(r'\]\(([^)]+)\)', section):
        assert (path.parent / link).exists(), (path, link)
        links += 1
recon = APP / 'artifacts/jarvis-audit/reconciliation/35-2026-10-20-completion-a9b4ce1'
assert len(list(recon.iterdir())) == 9
cases = list(ET.parse(OUT / 'final-regression.xml').getroot().iter('testcase'))
assert not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
result = {'date': '2026-10-20', 'required_reports': len(required), 'reconciliation_files': 9, 'numbered_cases': len(rows),
          'final_pass': sum(c.find('skipped') is None for c in cases), 'final_skipped': sum(c.find('skipped') is not None for c in cases),
          'new_local_links_checked': links, 'original_module_evidence_unchanged': True,
          'current_source_hashes_match': True, 'Prompt34_repair_preserved': True, 'git_diff_check': 'PASS'}
(OUT / 'validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
