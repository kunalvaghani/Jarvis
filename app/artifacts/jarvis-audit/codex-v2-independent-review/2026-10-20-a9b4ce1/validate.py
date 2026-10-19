"""Check final evidence, report links and patches without changing the pinned index."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
BASELINE = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-codex-v2-baseline')
for path in OUT.glob('*.json'): json.loads(path.read_text(encoding='utf-8'))
for path in OUT.glob('*.jsonl'):
    for row in path.read_text(encoding='utf-8').splitlines():
        if row.strip(): json.loads(row)
checks = [(p, p.read_text(encoding='utf-8')) for p in OUT.glob('*.md')]
for path in [APP / 'README.md', APP.parent / 'README.md']:
    block = re.search(r'<!-- prompt99-review -->(.*?)<!-- /prompt99-review -->', path.read_text(encoding='utf-8'), re.S)
    assert block
    checks.append((path, block.group(1)))
handoff = APP / 'docs/CLAUDE_HANDOFF.md'
block = handoff.read_text(encoding='utf-8').split('## Prompt 99 -', 1)[1].split('## Prompt 37', 1)[0]
checks.append((handoff, block))
links = 0
for path, body in checks:
    for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)', body):
        if '://' in link or link.startswith('#'): continue
        assert (path.parent / link.split('#')[0]).exists(), (path, link)
        links += 1
patches = {}
for name in ['source-only.patch', 'test-change.patch']:
    result = subprocess.run(['git', 'apply', '--check', '--cached', str(OUT / name)], cwd=BASELINE, capture_output=True, text=True)
    patches[name] = {'returncode': result.returncode, 'diagnostic': result.stderr.strip()}
    assert result.returncode == 0, patches[name]
assert subprocess.run(['git', 'diff', '--quiet', '--', 'app/jarvis', 'app/scripts', 'app/evolution_eval'], cwd=BASELINE).returncode == 0
assert subprocess.run(['git', 'diff', '--check'], cwd=APP.parent).returncode == 0
summary = json.loads((OUT / 'run-summary.json').read_text())
assert summary['runs']['candidate-final']['FAIL'] == 0
manifest = json.loads((OUT / 'patch-manifest.json').read_text())
assert all(hashlib.sha256((APP / name).read_bytes()).hexdigest() == digest for name, digest in manifest.items())
data = json.loads((OUT / 'validation.json').read_text())
data.update({'report_links_checked': links, 'json_jsonl_parse': 'PASS', 'source_test_patches_apply_to_pinned_index': patches,
    'baseline_tracked_production_clean': True, 'patch_manifest_readback': 'PASS'})
(OUT / 'validation.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
print(json.dumps(data, indent=2))
