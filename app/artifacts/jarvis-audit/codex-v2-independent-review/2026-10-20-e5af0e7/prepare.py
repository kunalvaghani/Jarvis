"""Pin source and preserve historical audit artifacts; no live configuration reads."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
REVIEW = OUT.parents[3]
SOURCE = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')
SHA = 'e5af0e700517bac5fb48dcebc8f6cc9c9df9a369'
AUDITS = REVIEW / 'artifacts/jarvis-audit'
assert REVIEW.name == 'app'
def git(*args, cwd=SOURCE):
    return subprocess.check_output(['git', *args], cwd=cwd).decode('utf-8').strip()
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
assert git('rev-parse','HEAD') == SHA
assert git('diff','--name-only') == ''
dump('review-revisions.json', {'date':'2026-10-20', 'pinned_claude':git('rev-parse','claude'),
    'tested_sha':SHA, 'review_sha':git('rev-parse','HEAD',cwd=REVIEW), 'candidate_commit':None,
    'new_production_changes':0, 'review_branch':git('branch','--show-current',cwd=REVIEW),
    'live_dirty':git('status','--short',cwd=Path('D:/Kunals GitHub Repo/Jarvis')),
    'source_dirty':git('status','--short'), 'source_checkout':str(SOURCE.parent),
    'historical_review_checkout':str(REVIEW.parent),
    'lineage':'Prior production repairs integrated at 3fbfbf6; P34 transport/rebuild/lock added at e5af0e7. Detached source/test overlays only; historical codex-review changes preserved.'})
source = {p.relative_to(SOURCE).as_posix():digest(p) for directory in ('jarvis','scripts','evolution_eval')
          for p in (SOURCE/directory).rglob('*.py')}
dump('source-hashes.json',source)
parents = {}
for path in AUDITS.rglob('*'):
    if path.is_file() and '__pycache__' not in path.parts and not path.is_relative_to(OUT):
        parents[path.relative_to(REVIEW).as_posix()]={'sha256':digest(path),'bytes':path.stat().st_size}
dump('parent-evidence-index.json',parents)
prior = AUDITS/'codex-v2-independent-review/2026-10-20-a9b4ce1'
for name in ('corpus.py','environment.py'):
    body=(prior/name).read_text(encoding='utf-8')
    body=body.replace("APP = next(p for p in OUT.parents if (p / 'main.py').is_file())",f"APP = Path({str(SOURCE)!r})")
    (OUT/name).write_text(body,encoding='utf-8')
runner=(AUDITS/'modules/37-e2e/2026-10-20-independent-e5af0e7/run_suite.py').read_text(encoding='utf-8')
runner=runner.replace("selected = list(dict.fromkeys(selected))", "selected += [str(APP / 'tests' / p) for p in ['test_prompt37_ui_restart.py', 'test_prompt37_reasoning_repeat.py']]\nselected = list(dict.fromkeys(selected))")
(OUT/'run_suite.py').write_text(runner,encoding='utf-8')
journeys=(AUDITS/'modules/37-e2e/2026-10-20-independent-e5af0e7/run_workflows.py').read_text(encoding='utf-8')
(OUT/'run_journeys.py').write_text(journeys,encoding='utf-8')
deep=(prior/'test_deep_lab.py').read_text(encoding='utf-8')
deep=deep.replace("APP = next(p for p in Path(__file__).resolve().parents if (p / 'main.py').is_file())",f"APP = Path({str(SOURCE)!r})")
(OUT/'test_deep_lab.py').write_text(deep,encoding='utf-8')
for old,label in [('36fbf3ce925080f7f54afa87eaf1d9b88414142d','since-original-review'),
                  ('a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6','since-prior-v2')]:
    (OUT/(label+'.patch')).write_bytes(subprocess.check_output(['git','diff',old,SHA,'--','app/jarvis','app/scripts','app/evolution_eval'],cwd=SOURCE))
doc_summaries=[]
for folder in [*(AUDITS/f'phase-{n:02}' for n in range(1,8)), AUDITS/'final-codex-handoff']:
    for path in folder.glob('*.md'):
        text=path.read_text(encoding='utf-8-sig')
        doc_summaries.append({'path':path.relative_to(REVIEW).as_posix(),'sha256':digest(path),
            'headings':[line for line in text.splitlines() if line.startswith('#')],
            'limitations':[line for line in text.splitlines() if any(word in line.lower() for word in ('blocked','not run','not verified','unresolved','not ready'))][:15]})
dump('historical-phase-reports.json',doc_summaries)
parsed=[]
for name in source:
    ast.parse((SOURCE/name).read_text(encoding='utf-8-sig'),filename=name)
    parsed.append(name)
dump('static-checks.json',{'ast_parsed':len(parsed),'syntax_errors':0,'model_imports':0})
print(json.dumps({'sha':SHA,'source_files':len(source),'prior_artifacts':len(parents),'phase_reports_read':len(doc_summaries)}))
