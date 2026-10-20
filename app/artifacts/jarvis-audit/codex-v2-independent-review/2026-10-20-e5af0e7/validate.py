"""Verify final patch/source/evidence/README links; preserve all earlier packets."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

out=Path(__file__).resolve().parent
app=out.parents[3]
pin=Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7')
candidate=Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-v2-mutants-e5af0e7')
live=Path('D:/Kunals GitHub Repo/Jarvis')
def git(*args,cwd):return subprocess.check_output(['git',*args],cwd=cwd).decode('utf-8').strip()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for path in out.glob('*.json'):json.loads(path.read_text(encoding='utf-8'))
for path in out.glob('*.jsonl'):
    for line in path.read_text(encoding='utf-8').splitlines():
        if line:json.loads(line)
source=json.loads((out/'candidate-source-hashes.json').read_text(encoding='utf-8'))
assert all(sha(candidate/'app'/name)==value for name,value in source.items())
parents=json.loads((out/'parent-evidence-index.json').read_text(encoding='utf-8'))
assert all(sha(app/name)==row['sha256'] for name,row in parents.items())
changed=git('diff','--name-only',cwd=candidate).splitlines()
assert set(changed)=={'app/jarvis/repair_authorization.py','app/scripts/setup/setup_brain.py'}
assert git('diff','--name-only',cwd=pin)==''
for relative in changed:
    assert sha(candidate/relative)==sha(app.parent/relative),relative
for patch in ['source-only.patch','new-test.patch','combined-new-tests.patch']:
    subprocess.run(['git','apply','--check','--cached',str(out/patch)],cwd=pin,check=True)
subprocess.run(['git','diff','--check'],cwd=app.parent,check=True)
checks=[(path,path.read_text(encoding='utf-8')) for path in out.glob('*.md')]
for path in [app/'README.md',app.parent/'README.md']:
    text=path.read_text(encoding='utf-8').split('<!-- prompt99-e5af-review -->',1)[1].split('\n\n',1)[0]
    checks.append((path,text))
handoff=app/'docs/CLAUDE_HANDOFF.md'
text=handoff.read_text(encoding='utf-8').split('## Prompt 99 - committed e5af0e7',1)[1].split('## Prompt 37',1)[0]
checks.append((handoff,text))
links=0
for path,body in checks:
    for link in re.findall(r'\]\(([^)]+)\)',body):
        if '://' not in link and not link.startswith('#'):
            assert (path.parent/link.split('#')[0]).exists(),(path,link)
            links+=1
journals=[json.loads(line) for line in (out/'candidate-workflow-journals.jsonl').read_text(encoding='utf-8').splitlines() if line]
assert len(journals)==3 and all(row['status']=='PASS' and row['actual_python_component_calls'] for row in journals)
summary=json.loads((out/'run-summary.json').read_text(encoding='utf-8'))
assert summary['runs']['candidate-final']['FAIL']==0
revisions=json.loads((out/'review-revisions.json').read_text(encoding='utf-8'))
revisions.update({'live_final_sha':git('rev-parse','HEAD',cwd=live),'live_final_dirty':git('status','--short',cwd=live),
    'candidate_parent_sha':git('rev-parse','HEAD',cwd=candidate),'candidate_tracked_changes':changed,
    'branch_preservation':'codex-review occupied by retained dirty earlier review; authored proposals there and validated exact e5af0e7-relative diff in detached candidate, without resetting/rebasing old branch'})
(out/'review-revisions.json').write_text(json.dumps(revisions,indent=2),encoding='utf-8')
report=json.loads((out/'validation.json').read_text(encoding='utf-8'))
report.update({'json_jsonl':'PASS','links_checked':links,'candidate_proposal_matches_review_files':True,
    'candidate_workflow_journals':3,'diff_check':'PASS','pin_tracked_clean':True,'combined_patches_check_root_index':'PASS'})
(out/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
