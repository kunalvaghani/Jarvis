"""Capture source/evidence lineage and overlay independent tests only for baseline."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
ROOT = APP.parent
BASE = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-codex-v2-baseline')
SHA = 'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6'
def git(*args, cwd=ROOT): return subprocess.check_output(['git', *args], cwd=cwd).decode('utf-8').strip()
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert git('rev-parse', 'HEAD', cwd=BASE) == SHA
assert not git('status', '--porcelain', cwd=BASE)
paths = [p for p in (APP / 'jarvis').rglob('*.py')] + list((APP / 'scripts').rglob('*.py')) + list((APP / 'evolution_eval').rglob('*.py'))
source = {p.relative_to(APP).as_posix(): digest(p) for p in paths}
(OUT / 'candidate-source-hashes.json').write_text(json.dumps(source, indent=2), encoding='utf-8')
evidence = {}
for directory in ['codex-independent-review', 'final-codex-handoff', 'modules', 'phase-01', 'phase-02', 'phase-03',
                  'phase-04', 'phase-05', 'phase-06', 'phase-07', 'reconciliation']:
    for p in (APP / 'artifacts/jarvis-audit' / directory).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            evidence[p.relative_to(APP).as_posix()] = {'sha256': digest(p), 'bytes': p.stat().st_size}
(OUT / 'parent-evidence-index.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
(OUT / 'review-revisions.json').write_text(json.dumps({'date': '2026-10-20', 'pinned_claude': git('rev-parse', 'claude'),
    'candidate_parent': git('rev-parse', 'HEAD'), 'candidate_commit': None, 'candidate_branch': git('branch', '--show-current'),
    'live_claude_dirty': git('status', '--short', cwd=Path('D:/Kunals GitHub Repo/Jarvis')),
    'candidate_dirty': git('status', '--short'), 'baseline_detached': True,
    'precondition': 'Claude has not integrated/committed the review proposals; dirty config excluded. Review is pinned source plus separately hashed local candidate.'}, indent=2), encoding='utf-8')
overlay = {}
for p in (APP / 'tests').glob('test_prompt3*.py'):
    target = BASE / 'app/tests' / p.name
    if not target.exists():
        shutil.copyfile(p, target); overlay[p.name] = digest(p)
(OUT / 'baseline-test-overlay.json').write_text(json.dumps({'tests_only': overlay, 'production_source_changes': 0}, indent=2), encoding='utf-8')
(OUT / 'source-only.patch').write_bytes(subprocess.check_output(['git', 'diff', SHA, '--', 'app/jarvis', 'app/scripts', 'app/evolution_eval'], cwd=ROOT))
print(json.dumps({'source_files': len(source), 'historical_artifacts': len(evidence), 'test_overlay': len(overlay)}))
